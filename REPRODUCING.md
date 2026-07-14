# Reproducing GP2PL

This document identifies the complete public inputs needed to reproduce GP2PL
and its released evaluation. It is an execution guide, not part of the
theoretical contribution.

## Fixed Research Artifacts

| Artifact | Path | Purpose |
| --- | --- | --- |
| Temporal-goal benchmark | [`paper_artifacts/temporal_goal_benchmark/v1`](paper_artifacts/temporal_goal_benchmark/v1/README.md) | 475 unique natural-language translations and 1,228 bound query cases over 16 domains. |
| Semantic conformance suite | `paper_artifacts/temporal_semantic_conformance/v1` | Direct finite-trace semantics versus MONA-derived automata, including zero-action cases. |
| Evaluation release | `paper_artifacts/gp2pl_evaluation/v1` | Exact atomic libraries, one canonical five-seed record containing 6,140 Full GP2PL evaluations, the fixed 1,228-case temporal execution record, 29,472 paired ablation records, 2,456 external-reference records, 740 Raw MOOSE extension records, 13 certificate challenges, distribution summaries, and SHA-256 manifest. |

The release contains no machine-local absolute paths. The canonical benchmark,
per-domain views, frozen predictions, semantic validation rows, and source
archives are hash-identified across `manifest.json` and
`release_validation.json`.

## Tested Environment

- Apple M4, 10 CPU cores, 24 GB unified memory; no GPU is required.
- macOS 26.4.1, arm64.
- Python 3.12.7 and uv 0.8.19.
- Clingo 5.8.0, Tarski 0.9.1, ltlf2dfa 1.0.2, MONA 1.4-18.
- Jason 3.1.2, OpenJDK 24, Maven 3.9.11.
- Docker 28.5.1 and VAL revision
  `3c7a1f330bdab0ba28a4762bb45c3f06c27fb6d4`.

## Install Dependencies

```bash
uv sync --extra translation
bash scripts/setup_mona.sh
bash scripts/setup_moose.sh
bash scripts/setup_benchmark_sources.sh
uv run python scripts/materialize_achievement_benchmarks.py
```

The MOOSE and benchmark setup scripts refuse dirty upstream checkouts and check
every pinned commit. The materializer deterministically reconstructs all
train/test splits.

For Jason and VAL execution, install Java, Maven, and Docker. Jason 3.1.2 is
resolved from Maven. The VAL wrapper expects the pinned local VAL image or
binary configured by `scripts/validate_with_docker_val.sh`.

## Verify the Released Data

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/verify_public_teg_dataset.py
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/verify_public_result_release.py
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/audit_public_repository.py
```

The TEG verifier checks every count and hash, scans both ordinary files and
source archives for machine-local paths, and requires dataset-level license and
citation metadata. The public-repository audit scans every tracked file and all
archive members for secrets, machine-local paths, platform metadata, unsafe
archive entries, and development-only files. The result verifier independently
recomputes case uniqueness, variant coverage, success counts, status counts,
paired contrasts, PAR-2 values, and published-reference totals from the final
per-case records. The SHA-256 manifest establishes released-file integrity.

After materializing the PDDL corpus, regenerate the normalized evaluation
dataset and the reported LaTeX tables without any conference-specific tooling:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python \
  scripts/generate_evaluation_tables.py \
  --execution-summary \
  paper_artifacts/gp2pl_evaluation/v1/temporal_execution_summary.json \
  --benchmark-compatibility \
  paper_artifacts/gp2pl_evaluation/v1/benchmark_compatibility.json \
  --atomic-library-root \
  paper_artifacts/gp2pl_evaluation/v1/atomic_libraries \
  --output-dir artifacts/evaluation_tables
```

The output directory contains `evaluation_results.json`, `result_macros.tex`,
`result_domain_table.tex`, and `result_profile_table.tex`. The generator
rejects incomplete benchmark coverage and incomplete verifier outcomes rather
than silently producing a partial table.

The compatibility certificate is limited to explicitly named fields below the
benchmark's `provenance` object. It reconstructs the benchmark hash stored by the
execution record and cannot change domains, formulas, bindings, or expected
semantics.

## Registered Experimental Parameters

### Generalized-planning evidence

- MOOSE goal size: 1, fixed by the singleton-goal evidence definition.
- Goal permutations per training problem: 3, following MOOSE Algorithm 1.
- Repetition seeds: 0, 1, 2, 3, 4.
- Internal MOOSE workers per seed: 1, fixed so each seeded synthesis uses one
  deterministic rule-discovery stream.
- Synthesis limit: 12 hours per domain and seed.
- Process memory guard: 16 GiB. This is a declared deviation from MOOSE's
  reported 32 GB synthesis allowance.
- Test-time planning limit: 30 minutes and 8 GiB per instance.

Each seed is trained, compiled, and evaluated independently. Evidence and rules
are never pooled across seeds, and no best seed is selected.

### Validated policy-lifting compiler

- Candidate scope: all implemented certified candidate families.
- Schema regression depth: no numeric depth cutoff. Search stops at repeated
  alpha-normalized requirement/producer roles or resource modes.
- Branch selector: Clingo lexicographic optimization over recursive capability,
  acyclic preparation capability, branch count, context count, and body cost.
- Balanced controller branching factor: 2, fixed by the proved binary-tree
  construction and not tuned on benchmark outcomes.

### Temporal translation and execution

- Translation model: `gpt-5.5`.
- Temperature: 0; maximum output tokens: 60,000; request timeout: 1,000 seconds;
  semantic retries: at most 3; JSON-object response mode.
- Temporal compiler: certified balanced controller with primitive-step monitor.
- Jason and VAL timeout: 30 minutes each per query.
- Java thread stack: 64 MiB.
- Final registered validation workers: 8 within each seed. Seed evaluations
  are run sequentially, so this value controls test-instance throughput without
  pooling evidence or executing two seeds concurrently.

The compiler contains no learned numerical hyperparameters. Values above are
semantic bounds, external-method parameters, or resource controls. They are not
selected on the test set.

## Full MOOSE Evidence Reproduction

The five-seed matrix is expensive: each domain/seed synthesis may use the full
12-hour limit. The exact protocol uses one internal MOOSE worker per seed,
launches the five independent seed processes concurrently, and validates the
resulting libraries one seed at a time with eight Jason workers:

```bash
PYTHONDONTWRITEBYTECODE=1 \
RUN_ID=pddl-five-seed-$(date +%Y%m%d-%H%M%S) \
MOOSE_WORKERS=1 \
MOOSE_SEEDS="0 1 2 3 4" \
MOOSE_SEED_PARALLELISM=5 \
JASON_WORKERS=8 \
JASON_JAVA_STACK_SIZE=64m \
bash scripts/run_achievement_benchmark_batch.sh
```

This requires the official MOOSE repository installed by
`scripts/setup_moose.sh` and the planner environment described by
`scripts/setup_external_planning_references.sh`.
The script rejects any seed list other than five distinct seeds and requires
`MOOSE_WORKERS=1`; incomplete smoke matrices cannot be reported as this
registered result.

## Statistical Analysis Boundary

The fixed temporal release reports the complete per-query distribution. Across
1,228 cases, execution time has median 5.49 seconds, interquartile range
4.28--8.49 seconds, and sample standard deviation 13.66 seconds; action count
has median 2, interquartile range 1--2, and sample standard deviation 0.80.

The released Full GP2PL repetitions contain 6,059 Jason-plus-VAL successes in
6,140 evaluations, with mean seed coverage 98.68% and sample standard deviation
1.29 percentage points. The paired atomic ablation contains 24,560 per-case
records: Evidence Only solves 5,420 cases, Direct Producers 5,419, Maximum
Feasible 6,059, and Full GP2PL 6,059. The paired temporal ablation contains
4,912 per-case records: Unprotected Serialization solves 1,113 cases, Certified
Flat and Certified Balanced each solve 1,228, and Module-Return Monitor solves
1,212. The release also includes all 2,456 final per-case external-reference
records and the corresponding status and PAR-2 aggregates. The measured Raw
MOOSE extension solves 117 of 740 seed-case evaluations on the four project
extension domains; the separate published MOOSE reference reports a mean of
1,079.6 solved cases out of 1,080 on its original domain scope.

## Checklist Evidence Map

- All GP2PL-authored framework, experiment, preprocessing, validation, and
  analysis source is included in `src/` and `scripts/`, with the exact
  environment in `uv.lock`; it is released under Apache-2.0.
- Public third-party tools are installed at pinned revisions by the setup scripts
  and retain upstream terms. They are dependencies, not omitted GP2PL source.
- All novel temporal-goal data, including the construction audit sealed from the
  translation model during inference, is published under
  `paper_artifacts/temporal_goal_benchmark/v1` with CC BY 4.0 licensing, citation
  metadata, source archives, and integrity hashes.
- Existing PDDL datasets are publicly retrievable from cited, pinned revisions
  and are deterministically materialized. No non-public dataset is used.
- Complete per-instance records support descriptive distributions and the
  registered paired compiler comparisons. All released aggregates are checked
  against their final case-level records.

## Public Release

The public source, data, licenses, citation metadata, and versioned releases are
maintained at <https://github.com/daidaibunny/gp2pl>.
