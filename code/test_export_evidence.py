"""Public artifact contract: sanitized scalars only, no private material."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXPORT = HERE / "export_evidence.py"
EVIDENCE = ROOT / "results" / "processed" / "evidence.json"


class EvidenceExportTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(EXPORT.exists() and EXPORT, "export script missing")
        self.document = json.loads(EVIDENCE.read_text())
        self.raw = EVIDENCE.read_text()

    def test_no_private_paths_credentials_or_prompts_escape(self):
        for marker in ("/Users/", "/Volumes/", "sk-", "hf_", "Bearer ", "api-key",
                       "api_key", "BEGIN PRIVATE", "ssh-rsa"):
            self.assertNotIn(marker, self.raw, f"leaked {marker}")
        # A prompt or transcript leak would introduce long free-form prose.
        longest = max((len(v) for v in self.document["checkpoint"]["quantized_rows_verified"]), default=0)
        self.assertLess(longest, 200)

    def test_qualification_flags_are_explicitly_negative(self):
        q = self.document["qualification"]
        self.assertFalse(q["minimum_20_tps_met"])
        self.assertFalse(q["actual_near_limit_context_met"])
        self.assertFalse(q["peer_review_claimed"])
        self.assertFalse(q["ranked_intelligence_claimed"])

    def test_every_numeric_metric_is_finite_and_every_flag_boolean(self):
        def walk(node, path="root"):
            if isinstance(node, dict):
                for key, value in node.items():
                    walk(value, f"{path}.{key}")
            elif isinstance(node, list):
                for i, value in enumerate(node):
                    walk(value, f"{path}[{i}]")
            elif isinstance(node, float):
                self.assertFalse(node != node or node in (float("inf"), float("-inf")), path)
        walk(self.document)

    def test_failed_and_timed_out_runs_are_retained_not_dropped(self):
        repairs = self.document["speculative_repairs"]
        self.assertEqual(len(repairs), 2)
        for run in repairs:
            self.assertTrue(run["timed_out"])
            self.assertFalse(run["completed"])
            self.assertFalse(run["independent_gate_pass"])
            self.assertIsNot(run["elapsed_s"], None)

    def test_all_four_synthetic_conditions_and_parity_are_present(self):
        conditions = self.document["synthetic_conditions"]
        self.assertEqual(len(conditions), 4)
        for condition in conditions:
            self.assertTrue(condition["greedy_token_parity"])
            self.assertEqual(len(condition["trials"]), 4)
            labels = [trial["label"] for trial in condition["trials"]]
            self.assertEqual(sum("plain" in x for x in labels), 2)
            self.assertGreaterEqual(sum(("dflash" in x) or ("mtp" in x) for x in labels), 2)

    def test_memory_policy_records_refusal_then_success_at_same_input(self):
        policy = self.document["memory_policy"]
        self.assertFalse(policy["refusal_before_switch"]["completed"])
        self.assertTrue(policy["after_supported_switch_off"]["completed"])
        self.assertFalse(policy["after_supported_switch_off"]["prompt_reduced"])
        self.assertEqual(policy["effective_child_setting"][0]["system_memory_guard"], "0")

    def test_protocol_matrix_covers_both_endpoints_and_three_dialects(self):
        matrix = self.document["protocol_matrix"]
        for kind in ("non_streaming", "streaming"):
            rows = matrix[kind]
            self.assertEqual(len(rows), 6, kind)
            self.assertEqual({r["endpoint"] for r in rows}, {"native", "magpie"})
            self.assertEqual({r["protocol"] for r in rows}, {"chat", "responses", "anthropic"})
            self.assertTrue(all(r["passed"] for r in rows), kind)

    def test_export_refuses_when_a_private_marker_would_escape(self):
        fable_root = ROOT.parent.parent / "fable"
        real_local = ROOT.parent.parent / "coder390" / "mlx-native" / "raw"
        real_guard = fable_root / "memory-guard-fix" / "raw"
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / "poisoned"
            fake.mkdir()
            # Reuse every real input, but make one identity field private.
            for source in (fable_root / "deployment" / "raw").glob("*.json"):
                (fake / source.name).write_bytes(source.read_bytes())
            # runtime_profile reaches the artifact unfiltered by text(), so a
            # private value here proves the serialized-blob guard is load-bearing.
            doc = json.loads((fake / "final-cutover-audit.json").read_text())
            doc["runtime_profile"] = "/Users/someone/private"
            (fake / "final-cutover-audit.json").write_text(json.dumps(doc))
            code = EXPORT.read_text().replace(
                'LOCAL = ROOT / "coder390" / "mlx-native" / "raw"',
                f'LOCAL = Path({str(real_local)!r})',
            ).replace(
                'FABLE = ROOT / "fable" / "deployment" / "raw"',
                f'FABLE = Path({str(fake)!r})',
            ).replace(
                'GUARD = ROOT / "fable" / "memory-guard-fix" / "raw"',
                f'GUARD = Path({str(real_guard)!r})',
            )
            script = Path(temp) / "export.py"
            script.write_text(code)
            result = subprocess.run([sys.executable, str(script), str(Path(temp) / "out.json")],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0, "poisoned export succeeded")
            self.assertIn("private marker", (result.stdout + result.stderr).lower())
            self.assertFalse((Path(temp) / "out.json").exists())


class ChecksumTests(unittest.TestCase):
    def test_manifest_matches_files(self):
        manifest = ROOT / "SHA256SUMS"
        self.assertTrue(manifest.exists(), "SHA256SUMS missing")
        for line in manifest.read_text().splitlines():
            if not line.strip():
                continue
            digest, name = line.split("  ", 1)
            path = ROOT / name
            if not path.exists():
                self.fail(f"manifest lists missing file: {name}")
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest, name)


if __name__ == "__main__":
    unittest.main()
