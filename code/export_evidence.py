"""Whitelist-only export of the Coder390/Fable MLX and deployment study.

Reads private raw evidence under the lab and writes finite, path-free JSON.
Never copies prompts, tool output, repository source, transcripts, credentials
or local absolute paths into the public artifact.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # real-agent-lab
LOCAL = ROOT / "coder390" / "mlx-native" / "raw"
FABLE = ROOT / "fable" / "deployment" / "raw"
GUARD = ROOT / "fable" / "memory-guard-fix" / "raw"

RUN_ID = re.compile(r"^[A-Za-z0-9_\-.]{1,120}$")
DENY = ("/Users/", "/Volumes/", "hf_", "sk-", "Bearer ", "api-key", "api_key", "token=", "@")
PRIVATE_BLOB_MARKERS = ("/Users/", "/Volumes/", "sk-", "hf_", "Bearer ", "api-key", "api_key")


def assert_public(blob):
    """Refuse any serialized artifact carrying a private marker."""
    for bad in PRIVATE_BLOB_MARKERS:
        if bad in blob:
            raise ValueError(f"refusing to export private marker: {bad}")
    return blob


def finite(value, label):
    if value is None:
        return None
    if type(value) is bool:
        raise ValueError(f"{label}: boolean where number expected")
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{label}: non-finite numeric metric")
    return value


def flag(value, label):
    if value is None:
        return None
    if type(value) is not bool:
        raise ValueError(f"{label}: non-boolean flag")
    return value


def text(value, label, limit=200):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{label}: not a string")
    if any(bad in value for bad in DENY):
        raise ValueError(f"{label}: contains a private marker")
    return value[:limit]


def read(rel, base=LOCAL):
    path = base / rel if not str(rel).startswith("/") else Path(rel)
    if not path.is_file():
        raise FileNotFoundError(str(rel))
    return path, path.read_bytes()


def load(rel, base=LOCAL):
    _, raw = read(rel, base)
    return json.loads(raw)


def digest(rel, base=LOCAL):
    _, raw = read(rel, base)
    return hashlib.sha256(raw).hexdigest()


def windows(base, prefix):
    """Summarize owned inference-window receipts without local paths."""
    out = []
    for path in sorted(base.glob(prefix + "*/window.json")):
        row = json.loads(path.read_text())
        name = path.parent.name
        if not RUN_ID.match(name):
            raise ValueError("unsafe window name")
        out.append({
            "window": name,
            "restored": flag(row.get("restored"), "window.restored"),
            "worker_returncode": finite(row.get("worker_returncode"), "window.returncode"),
            "timed_out": flag(row.get("timed_out"), "window.timed_out"),
            "blocked_before_unload": row.get("phase") == "blocked_before_unload",
        })
    return out


def trial_rows(record):
    rows = []
    for trial in record.get("trials", []):
        if not isinstance(trial, dict):
            continue
        label = text(trial.get("label") or trial.get("arm") or "trial", "trial.label", 80)
        spec = trial.get("spec_message") or trial.get("speculative_stats") or ""
        rows.append({
            "label": label,
            "prompt_tokens": finite(trial.get("prompt_tokens"), "trial.prompt_tokens"),
            "generated_tokens": finite(
                trial.get("generation_tokens_including_reasoning_and_tool")
                or trial.get("num_tokens"), "trial.generated_tokens"),
            "client_ttft_s": finite(trial.get("client_ttft_s") or trial.get("first_text_ttft_s"), "trial.ttft"),
            "whole_request_s": finite(trial.get("whole_request_s") or trial.get("measured_whole_request_s"), "trial.wall"),
            "decode_tps": finite(trial.get("decode_tps") or trial.get("reported_generation_tps"), "trial.decode"),
            "prompt_tps": finite(trial.get("reported_prompt_tps"), "trial.prompt_tps"),
            "prefill_s": finite(trial.get("prefill_seconds"), "trial.prefill"),
            "finish_reason": text(trial.get("finish_reason"), "trial.finish", 24),
            "mean_accept_len": finite(trial.get("mean_accept_len") or trial.get("mean_accept"), "trial.accept"),
            "speculative": bool(spec) if spec is not None else None,
            "peak_memory_gb": finite(trial.get("peak_memory_gb_decimal") or trial.get("peak_memory_gb"), "trial.peak"),
        })
    return rows


def build():
    summary = load("continued-acceleration-reviewed.json")
    mlx = load("mlx-trial-reviewed-summary.json")
    conversion = load("output-verification.json")
    parity = load("real-tensor-parity.json")
    layout = load("strict-module-layout.json")
    tokproof = load("tokenizer-processor-proof.json")
    mtp = load("mtp-verification.json")
    source_layout = load("source-layout-audit.json")
    cpu = load("cpu-arithmetic-proof.json")
    audit = load("final-trial-service-audit.json")
    contention = load("contention-timing.json")

    cutover = load("cutover-receipt.json", FABLE)
    final_cutover = load("final-cutover-audit.json", FABLE)
    cleanup = load("retired-abliterated-cleanup-receipt.json", FABLE)
    image_handoff = load("image-handoff-proof.json", FABLE)
    switch = load("normal-and-fable-switch-proof.json", FABLE)
    live_api = load("live-api-proof.json", FABLE)
    live_svc = load("live-service-proof.json", FABLE)
    mem_policy = load("memory-policy-before.json", FABLE)
    mem_refusal = load("pi-prefill128-proof.json", FABLE)
    final_audit = load("final-cutover-audit.json", FABLE)

    guard_state = load("final-state.json", GUARD)
    guard_protocol = load("protocol-proof.json", GUARD)
    guard_stream = load("stream-protocol-proof.json", GUARD)
    guard_pi = load("pi-full-route-proof.json", GUARD)

    # Per-condition synthetic 8k comparisons, in declared arm order.
    conditions = []
    for name, note in [
        ("vlm-bf16-8k-mtp-r2", "official mlx-vlm, source MTP depth 3"),
        ("dspark-dflash-8k-cpuoff-r3", "mlx-dspark 0.19.0 DFlash2, cpu co-prefill off"),
        ("dspark0203-dflash-8k-r5", "mlx-dspark 0.20.3 DFlash2, newer kernels"),
        ("dspark019-dflash-8k-prefill2048-r6", "mlx-dspark 0.19.0 DFlash2, 2048-row prefill"),
    ]:
        rec = load(f"{name}/results.json")
        conditions.append({
            "condition": name,
            "note": note,
            "engine": text(rec.get("engine") or rec.get("runtime"), "engine", 120),
            "input_tokens": finite(rec.get("actual_input_tokens") or
                                   (rec.get("trials") or [{}])[0].get("prompt_tokens"), "input_tokens"),
            "prefill_chunk": finite(rec.get("prefill_chunk"), "prefill_chunk"),
            "draft_cap": finite(rec.get("derived_draft_cap"), "draft_cap"),
            "greedy_token_parity": flag(rec.get("greedy_token_parity"), "parity"),
            "trials": trial_rows(rec),
        })

    # Actual agent repairs with speculation (private clones, sanitized scalars).
    repairs = []
    for name in ("mtp-bf16-real-repair-r3", "dflash-bf16-real-repair-r4"):
        rec = load(f"{name}/repair.summary.json")
        turns = rec.get("turns") or []
        repairs.append({
            "run": name,
            "speculation": text(rec.get("speculation"), "speculation", 24),
            "trained_mtp": flag(rec.get("trained_mtp"), "trained_mtp"),
            "completed": flag(rec.get("completed"), "completed"),
            "elapsed_s": finite(rec.get("elapsed_s"), "elapsed_s"),
            "timed_out": flag(rec.get("timed_out"), "timed_out"),
            "tool_calls": finite(rec.get("tool_calls"), "tool_calls"),
            "tool_errors": finite(rec.get("tool_errors"), "tool_errors"),
            "independent_gate_pass": flag(rec.get("independent_gate_pass"), "gate"),
            "full_suite_pass": flag(rec.get("full_suite_pass"), "suite"),
            "source_restored": flag(rec.get("source_restored"), "restored"),
            "context_capacity_configured": finite(rec.get("context_capacity_configured"), "context"),
            "actual256k_qualified": flag(rec.get("actual256k_qualified"), "actual256k"),
            "initial_input_tokens": finite(turns[0]["usage"]["input"], "first_input") if turns else None,
            "initial_ttft_s": finite(turns[0].get("ttft_s"), "first_ttft") if turns else None,
            "turn_decode_tps": [finite(t.get("decode_tps"), "turn decode") for t in turns],
        })

    artifact = {
        "schema_version": 1,
        "title": "Fable MLX migration and native memory-policy study (sanitized evidence)",
        "authors": ["Chengyi Xu", "Nexora"],
        "brand": "Nexora Research",
        "scope": (
            "Descriptive deployment engineering on one Apple M4 Max 64 GiB host. "
            "Whitelisted finite scalars only; no prompts, tool output, repository "
            "source, transcripts, credentials or local absolute paths."
        ),
        "qualification": {
            "minimum_20_tps_met": False,
            "actual_near_limit_context_met": False,
            "peer_review_claimed": False,
            "ranked_intelligence_claimed": False,
        },
        "checkpoint": {
            "conversion": conversion,
            "nonquantized_tensor_parity": parity.get("raw_tensor_full_element_parity"),
            "quantized_rows_verified": parity.get("quantized_linears_sampled"),
            "module_layout": {k: layout.get(k) for k in
                              ("module_parameters", "checkpoint_tensors", "missing", "extra")},
            "tokenizer": {k: tokproof.get(k) for k in
                          ("tokenizer_parity_cases", "chat_template_parity", "vocab_size")},
            "mtp_tensors": len(mtp.get("files", {})),
            "source_tensor_categories": source_layout.get("categories_source_bytes"),
            "cpu_arithmetic": {
                "probes": cpu.get("probes"),
                "full_model_loaded": cpu.get("full_model_loaded"),
            },
        },
        "synthetic_conditions": conditions,
        "speculative_repairs": repairs,
        "reviewed_summary": {
            "smoke_plain_tps": mlx["smoke"]["plain_generation_tps"],
            "smoke_mtp_tps": mlx["smoke"]["mtp_generation_tps"],
            "smoke_greedy_parity": mlx["smoke"]["greedy_token_parity"],
            "short_input_tokens": 74,
            "repair_backend_metrics": mlx.get("actual_repair_backend_metrics"),
            "all_windows_restored": mlx.get("all_executed_windows_restored"),
        },
        "memory_policy": {
            "observed": {
                "kernel_free_target_bytes": mem_policy["kernel_free_target_bytes"],
                "floors": mem_policy["floors"],
                "compressor_bytes": mem_policy["live_reading"]["compressor_bytes"],
                "available_bytes": mem_policy["live_reading"]["available_bytes"],
                "free_bytes": mem_policy["live_reading"]["free_bytes"],
            },
            "refusal_before_switch": {
                "completed": mem_refusal.get("completed"),
                "prefill_chunk": mem_refusal.get("prefill_chunk"),
                "error_class": "runtime prefill system-memory guard",
            },
            "after_supported_switch_off": {
                "same_input_tokens": guard_pi["messages"][0]["usage"]["input"] if guard_pi.get("messages") else None,
                "completed": guard_pi.get("completed"),
                "elapsed_s": guard_pi.get("elapsed_s"),
                "exact_marker": guard_pi["messages"][0]["text"] if guard_pi.get("messages") else None,
                "prompt_reduced": False,
            },
            "effective_child_setting": guard_state["native_child_env"],
        },
        "protocol_matrix": {
            "non_streaming": [{"endpoint": r["endpoint"], "protocol": r["protocol"],
                               "status": r["status"], "passed": r["passed"]}
                              for r in guard_protocol["results"]],
            "streaming": [{"endpoint": r["endpoint"], "protocol": r["protocol"],
                           "status": r["status"], "terminal_received": r["terminal_received"],
                           "passed": r["passed"]} for r in guard_stream],
        },
        "deployment": {
            "cutover_ready": cutover.get("fable_ready"),
            "unrelated_providers_identical": cutover.get("unrelated_provider_records_identical"),
            "context_window": final_cutover.get("context_window"),
            "mtp_depth": final_cutover.get("mtp_depth"),
            "runtime_profile": final_cutover.get("runtime_profile"),
            "prefill_chunk": final_cutover.get("prefill_chunk"),
            "live_backend_reply_ok": bool(live_api.get("backend_answer")),
            "live_gateway_reply_ok": bool(live_api.get("magpie_answer")),
            "service_idle_verified": live_svc.get("idle_verified"),
            "image_handoff_restored": image_handoff.get("restored"),
            "normal_switch_verified": switch.get("normal_start_verified"),
            "retired_logical_bytes": cleanup.get("logical_bytes"),
            "retired_entry_count": len(cleanup.get("deleted", [])),
        },
        "windows_restored": {
            "coder390_mlx": windows(LOCAL, ""),
            "fable_deployment": windows(FABLE, ""),
        },
        "contention": {
            "external_start_estimated_during_window": contention.get(
                "external_start_estimated_during_window"),
            "exclusive_execution_proven": contention.get("exclusive_execution_proven"),
        },
        "final_state": {
            "fable_promoted": audit.get("candidate_promoted"),
            "near_limit_qualified": final_audit.get("near_limit_context_qualified"),
            "trial_ports_closed": final_audit.get("experiment_ports_closed") or
                                 audit.get("lab_ports_closed"),
        },
    }

    # Every string is already vetted by text(); assert no absolute path escaped.
    blob = json.dumps(artifact, indent=2, sort_keys=False)
    return assert_public(blob), artifact


def main():
    dest = Path(sys.argv[1])
    try:
        blob, _artifact = build()
    except ValueError as error:
        raise SystemExit(str(error)) from None
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(blob + "\n")
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
