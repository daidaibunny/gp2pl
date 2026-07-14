# Frozen Translation Delivery

This directory records the frozen model predictions for
`temporal-nl-v1-20260711-final`. The predictions were generated for the 475
unique natural-language translation inputs and were not edited after freezing.

## Configuration

| Field | Value |
| --- | --- |
| model identifier | `gpt-5.5` |
| response format | JSON object |
| temperature | `0` |
| maximum output tokens | `60000` |
| request timeout | `1000` seconds |
| semantic retry budget | `3` |
| accepted translations | `475/475`, each on its first semantic attempt |

The prompt configuration is `full`, with source commit
`8804f7347f40c908d6a58c2141f91a77efbfdba8`. All 475 recorded prompt-context
digests agree with the deterministic prompt renderer.

## Frozen Artifact and Validation

- `translation_predictions.jsonl` contains one prediction per translation
  identifier in worklist order.
- Its SHA-256 digest is
  `512c766b60e9c3d953d49b930a4845bfda6bceb9706675a2670084d45db47f41`.
- The sealed validation data were inaccessible to the model before this
  prediction file was frozen.
- Independent validation found `475/475` semantically equivalent LTLf
  translations and `1228/1228` accepted hidden construction witnesses.

The released delivery archive contains the frozen predictions, canonical
per-input records, attempt logs, and the successful validation output. Platform
metadata and unsuccessful validation diagnostics are excluded because they do
not constitute experimental evidence. The release verifier checks all published
hashes and counts; the archive normalization does not change predictions,
successful validation rows, or benchmark semantics.
