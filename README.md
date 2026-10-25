# From GGUF to Native MLX

A reproducible migration of the TURBO-Fable 27B checkpoint to native MLX on an
Apple M4 Max, the speculative-decoding measurements that bounded it, and the
serving-runtime memory policy that blocked real agent traffic.

**Chengyi Xu and Nexora** — Nexora Research, October 2026.

- Paper: [`paper/main.pdf`](paper/main.pdf) (7 pages)
- Source: [`paper/main.tex`](paper/main.tex)
- Evidence: [`results/processed/evidence.json`](results/processed/evidence.json)
- Protocol: [`protocol.md`](protocol.md)

## What this report establishes

1. **A bounded, verifiable conversion.** A mixed-precision MLX artifact was
   produced from the pinned BF16 parent without materializing the checkpoint:
   128-row chunks, 3.08 GB peak resident memory, 493 s conversion body time.
   All 686 non-quantized tensors matched the pinned sanitizer element by
   element; sampled rows of six real modules matched official quantization
   byte for byte; all 2,180 tensor names and shapes matched.

2. **Speculation helps, but not enough, and not everywhere.** On one
   8,159-token prompt, DFlash2 reached 8.40 tok/s against 5.34 plain
   (1.57× decode, ~13% on the whole request) in the best of four interleaved
   conditions. A newer kernel generation and a wider prefill both erased the
   gain. Stock MLX-VLM MTP gave 6.05 against 5.08. **No condition reached
   20 tok/s.**

3. **Both real agent sessions timed out.** MTP depth 3 and DFlash2 each ran
   ~900 s with 25,778-token initial input, made 4 and 6 tool calls, left the
   injected defect unfixed, and failed the independent gate and full suite.

4. **The blocking failure was policy, not the model.** A serving-runtime
   system-memory guard refused an ~25k-token prefill because macOS held
   16.7 GiB compressed and free pages sat under a 1.7 GiB floor. Disabling
   that documented guard — leaving the 36 GiB engine budget intact — turned
   the identical 25,676-token request into a completed reply in 359.85 s,
   with no prompt, tool or budget reduction.

5. **Twelve protocol checks pass.** OpenAI Chat Completions, OpenAI Responses
   and Anthropic Messages each answered on both the native backend and the
   Magpie gateway, streaming and non-streaming, with exact markers and
   terminal stream events.

## What this report does not claim

- **No peer review.** This is a deployment engineering report.
- **No ranked intelligence.** We did not measure reasoning or coding accuracy
  beyond one injected-defect task, which failed.
- **No 20 tok/s floor.** No configuration reached it.
- **No near-limit context qualification.** 262,144 is allocation metadata
  here; the largest recorded actual request is 32,014 tokens.
- **No equivalence claim** between the MLX quantization and the BF16 parent,
  or between the MLX artifact and the GGUF release. Layout and sampling were
  verified; task accuracy was not.
- **No endorsement of ``uncensored``/``Heretic`` use.** Those are provenance
  labels; no refusal-removal or harmful-generation evaluation was performed.

## Reproducing the evidence

```bash
python3 code/export_evidence.py results/processed/evidence.json
python3 code/test_export_evidence.py
cd paper && SOURCE_DATE_EPOCH=1761696000 tectonic --untrusted main.tex
```

`SOURCE_DATE_EPOCH` is required for a byte-identical rebuild: without it the
PDF embeds the build timestamp and its SHA-256 changes on every run. With it
the PDF is reproducible, which is what makes `SHA256SUMS` meaningful.

The exporter is whitelist-only. It reads finite scalars and enumerated flags,
rejects any string carrying a private path or credential marker, and refuses
to write an artifact whose serialized form contains one. Prompts, tool output,
repository source, agent transcripts and absolute local paths are excluded by
construction, and the test suite proves that a poisoned input is refused.

## Artifact contents

```
paper/main.tex        LaTeX source
paper/main.pdf        built paper, 7 pages
paper/nexora-paper.sty
code/export_evidence.py       whitelist-only exporter
code/test_export_evidence.py  contract tests
results/processed/evidence.json
protocol.md
SHA256SUMS
```

## Licence and citation

Code and text: see [`LICENSE`](LICENSE). The model weights are governed by
their upstream licences and are **not** redistributed here.
Citation metadata: [`CITATION.cff`](CITATION.cff).
