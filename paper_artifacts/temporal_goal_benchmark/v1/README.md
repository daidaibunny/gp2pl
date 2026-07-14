# GP2PL Temporally Extended Goal Benchmark v1

This is the version-1 public dataset for GP2PL temporally extended goals
(TEGs). A TEG specifies a condition over a finite state trace rather than only
the final state. For example, `(a0 U a1)` requires `a0` to remain true until
`a1` first becomes true.

Public access:

- Repository: <https://github.com/daidaibunny/gp2pl/tree/main/paper_artifacts/temporal_goal_benchmark/v1>
- Versioned release: <https://github.com/daidaibunny/gp2pl/releases/tag/teg-benchmark-v1>

## Scope

The dataset contains:

- 16 Planning Domain Definition Language (PDDL) domains;
- 475 distinct controlled-language translation inputs;
- 1,228 problem-specific parameter bindings;
- 475 model-produced JSON translations that are language-equivalent to the
  sealed reference formulas; and
- 1,228 legal construction witnesses accepted by both the reference and
  predicted deterministic finite automata.

The supported finite-trace temporal-logic fragment contains `F`, `X`, strong
`U`, conjunction, and literal negation. It excludes disjunction and unrestricted
arithmetic. The five construction profiles are ordered two- and three-milestone
goals, persistence-until goals, same-state conjunctions, and same-state
conjunctions with negation.

## Files

| Path | Contents |
| --- | --- |
| `benchmark.json` | Canonical multi-domain benchmark with public inputs, model translations, bindings, and validation certificates. |
| `domains/<domain>.json` | Operational per-domain views accepted by the GP2PL temporal-goal appender. |
| `model_run/translation_predictions.jsonl` | Frozen model responses for the 475 distinct translation inputs. |
| `validation/translation_validation_results.jsonl` | Exact reference/prediction automaton-language equivalence results. |
| `validation/problem_validation_results.jsonl` | PDDL witness replay and dual-automaton acceptance results for 1,228 bindings. |
| `manifest.json` | Counts, per-domain file hashes, source-archive hashes, and benchmark hash. |
| `release_validation.json` | Independent reproduction checks and the MONA version and digest. |
| `source/` | Frozen input, validation, and model-run archives plus `SHA256SUMS`. |

Each canonical case records a source utterance, typed parameters, constraints,
an atom table, a lifted LTLf formula, a concrete parameter binding, and compact
translation and witness certificates. Hidden reference formulas, witness action
sequences, and state fingerprints are not included in `benchmark.json`; they
remain in the now-released sealed validation archive so that the independent
validator can reproduce the certificates.

The historical filename containing `private-validation` means that the archive
was withheld from the translation model during inference. It is part of this
public release and contains no personal or secret user data.

## Validation Boundary

This dataset evaluates translation and construction-witness validity. Its
`execution_attempted_count` is zero by design. It must not be cited as the
runtime controller result. Jason, VAL, and full trace-acceptance records are a
separate release under `paper_artifacts/gp2pl_evaluation/v1`.

## Integrity and Reproduction

From the repository root, run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/verify_public_teg_dataset.py
```

The verifier checks every published hash and count, source-archive safety,
dataset licensing metadata, and the absence of machine-local absolute paths.
All released source archives are deterministically repacked without platform
metadata or unsuccessful validation diagnostics. The model delivery archive
also normalizes the two metadata fields that originally recorded local output
directories. The original delivery-archive SHA-256 remains in the normalization
provenance; predictions, successful validation rows, and benchmark semantics
are unchanged.

To reconstruct the release from its public archives after installing MONA and
materializing the pinned PDDL corpus, run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/build_temporal_goal_benchmark.py \
  --delivery-archive paper_artifacts/temporal_goal_benchmark/v1/source/temporal-nl-v1-20260712-145052-predictions-and-validation.tar.gz \
  --delivery-archive-sha256 37cc42df9760670fc4a1b0bf964846b067b26e29cb056de01ce03a6dd1b80c38 \
  --delivery-archive-origin-sha256 8cd7f9d92f6c19e304a5dea5e60e11cf02d30f6be00664aa7dd13669a6713033 \
  --public-handoff-archive paper_artifacts/temporal_goal_benchmark/v1/source/temporal-nl-v1-20260711-final-public-handoff.tar.gz \
  --public-handoff-archive-sha256 0bc219c619b434995361ed60c3b7ad8f80701d1875c8fc32adbfee00dadefebc \
  --private-validation-archive paper_artifacts/temporal_goal_benchmark/v1/source/temporal-nl-v1-20260711-final-private-validation.tar.gz \
  --private-validation-archive-sha256 6d8e15ed50f472df976ae7093d221bff9e832cae0fad7285a435ce4e34ebbbc5 \
  --benchmark-id temporal-nl-v1-20260711-final \
  --run-id temporal-nl-v1-20260712-145052 \
  --output-dir /tmp/gp2pl-teg-benchmark-v1 \
  --validation-implementation-commit 25be3041bc200cd95cd1d6667c578df3e97283f7
```

## License and Citation

Original GP2PL data in this directory is licensed under CC BY 4.0; see
`LICENSE.md`. Third-party PDDL instances are not bundled as GP2PL-licensed data
and are reconstructed from pinned upstream sources. Citation metadata is in
`CITATION.cff`.
