# Protocol

Chengyi Xu and Nexora — Nexora Research, October 2026.

This protocol accompanies *From GGUF to Native MLX*. It states exactly what was
run, so that each number in the paper and in `results/processed/evidence.json`
can be traced to a condition. It deliberately does not publish prompts, tool
output, repository source or agent transcripts.

## Host

- Apple M4 Max, 40 GPU cores, 64 GiB unified memory.
- One shared workstation, actively used during the runs. Sampled swap was
  17–19 GB; background load varied. Unrelated processes were not killed and
  contention is not inferred to have caused any specific outcome.
- AC power, battery at 100%. No thermal or power-saving warning was reported.
  Fan mode and OS power settings were not changed.

## Checkpoint conversion

- Source: Coder390 BF16 shards at revision `a3a1170a` (49,825,162,976 +
  4,888,445,168 bytes) plus an 849,400,424-byte MTP sidecar; Fable used an
  exporter declaring the same BF16 parent at revision `0542355a`.
- Every source file verified against a pinned byte size and full SHA-256
  before use. Sizes alone are never treated as integrity.
- Conversion ran on CPU with `mx.set_default_device(mx.cpu)`, 128-row chunks,
  and no model instantiation. Layout rules were imported from a SHA-pinned
  upstream sanitizer rather than reimplemented; unrecognized tensor names
  abort the run.
- Peak RSS 3,082,305,536 bytes. Conversion body 493.33 s; 523.97 s including
  source rehashing.
- Output verified by: full SHA-256 of all 39 files; index/header/payload
  parity across 31 shards; element-wise equality of 686 non-quantized tensors
  against the pinned sanitizer; byte equality of packed weights, scales and
  biases for sampled rows of six modules against official quantization;
  module-shape construction matching all 2,180 names with no missing or extra
  tensors; five tokenizer parity cases and an identical thinking-low chat
  template.

### Known non-conclusion

A CPU BF16 quantized matmul differed from a matched float32 reference by
0.048 absolute on synthetic cancellation-heavy inputs (8.2–12.4% of peak).
The original gate was **not** widened. Matched-float32 arithmetic on both
sides matched exactly. This is a CPU arithmetic property, not a GPU result;
GPU numerical behaviour of the artifact is unmeasured.

### MTP packaging

An export that embeds `mtp.*` in trunk shards causes the loader to add 1.0 to
already-normalized RMSNorm gains, producing incoherent output and zero draft
acceptance. The fix repacks the MTP tensors into a sidecar in a container the
loader selects instead of the shards, preserving every tensor payload byte.
The repack re-hashes each payload; it performs no normalization, quantization
or reordering. Two contract tests failed before the helper existed and pass
after.

## Synthetic conditions

- One prompt of 8,159 tokens, greedy, thinking at low effort, unquantized KV
  cache, 512-token output cap.
- Four arms per condition in the order plain, speculative, speculative, plain.
- Every arm in every condition emitted the same 304 greedy tokens; parity is
  reported per condition.
- Conditions:
  1. official mlx-vlm 0.6.15, source-trained MTP depth 3, 512-row prefill;
  2. mlx-dspark 0.19.0, DFlash2, derived cap 2, 512-row prefill, CPU/GPU
     co-prefill explicitly off after its calibrator hit a Metal command-buffer
     timeout;
  3. mlx-dspark 0.20.3, DFlash2, derived cap 7, newer verification kernels;
  4. mlx-dspark 0.19.0, DFlash2, cap 2, 2,048-row prefill.
- Two observations per arm, balanced order within a condition, conditions
  themselves unpaired. Reported as configuration medians, not a runtime
  ranking.

## Agent repairs

- Fresh clone of the real client repository at revision `45f07540`, per run.
- One injected defect inverts a retry-delay cap from `min` to `max`. The
  independent gate fails before any model work; that gate, not the injected
  edit, is the regression proof.
- The agent must add coverage for an initial delay exceeding the cap, restore
  the implementation without changing the public API or status policy, and run
  offline tests.
- Real Pi session through the Magpie gateway, ordinary tool and extension
  discovery, thinking at low effort, 262,144 configured context, 4,096 output.
- No request-budget hook, no task-specific schema, no post-generation answer
  repair. The agent acts only inside the isolated clone.
- Parent review checks restored source, remaining tracked diff, independent
  gate and full suite.

## Memory policy

- Observed refusal: prefill stopped at a chunk boundary; runtime reported
  16.7 GiB compressed, 0.6 GiB free, 1.7 GiB floor.
- Independently verified: quarter-of-RAM compressor line 16 GiB on this host;
  about 9.6 GiB available supply; 1.47 GiB immediately free; 2.41 GiB derived
  abort floor.
- Change: the runtime's documented system-memory guard switch was set to off
  in the service process only. The 36 GiB engine allocator budget was left
  unchanged. The effective value was read back from the live native child.
- After the change the same 25,676-token input completed in 359.85 s with the
  exact expected marker and no reduction of tools, extensions, prompts or
  budgets. Single before/after pair at matched input size; a quieter machine
  cannot be fully excluded as a co-factor.

## Protocol matrix

For each of the native backend (port 7871) and the Magpie gateway (port 3425),
three dialects were exercised, streaming and non-streaming:
`/v1/chat/completions`, `/v1/responses`, `/v1/messages`. Success required HTTP
200, the exact expected marker in the answer, and — for streaming — at least
one text-delta event plus a terminal event. Twelve of twelve passed.

## Deployment and cleanup

- Native 262,144 context, MTP depth 3, turbo profile, 128-row prefill, Q8 KV,
  temperature 0.6, medium default reasoning effort.
- Transcript rewriting explicitly off; transcript mutation counters verified
  at zero on the measured requests.
- Separate private credential; service logs filtered so browser-auth startup
  URLs cannot leak it; wrapper terminates its own native child on shutdown.
- The retired abliterated checkpoint and its owned prepared cache were deleted
  only after the replacement reported ready, the retired file's full hash
  matched its recorded identity, and no process held it open:
  42,386,495,264 logical bytes across 43 entries. Logical bytes are not a
  claim of equivalent physical reclamation under APFS.
- Normal Ornith and the image service were preserved and re-verified,
  including an image handoff that restored the text backend before returning.

## Reproducible build

`paper/main.pdf` is byte-reproducible given `SOURCE_DATE_EPOCH=1761696000`.
Two consecutive rebuilds with that variable produced identical SHA-256; without
it the embedded creation date changes the digest on every run. `SHA256SUMS`
records the reproducible build.

## Excluded by construction

Prompts, tool output, repository source, agent transcripts, model weights,
credentials and absolute local paths. The exporter enforces this and the test
suite proves a poisoned input is rejected.
