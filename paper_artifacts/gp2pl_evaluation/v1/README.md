# GP2PL Evaluation Release

This directory contains the canonical libraries and final case-level outcomes
used by the reported evaluation. The temporal benchmark is
`paper_artifacts/temporal_goal_benchmark/v1/benchmark.json`.

- `atomic_libraries/` contains the structured and AgentSpeak(L) library for
  each of the 16 domains.
- `five_seed_full_compiler_summary.json` contains all 6,140 Full GP2PL
  evaluations: 1,228 cases for each of five independently trained seeds.
- `paired_ablation_results.json` contains 24,560 atomic and 4,912 temporal
  paired-ablation records, plus an integrated 6,140-record cross-seed extension
  for the selected Certified Balanced compiler.
- `temporal_execution_summary.json` contains the 1,228 final bound-query
  executions and all required verifier outcomes.
- `external_reference_results.json` contains the 2,456 registered external
  planning records and their PAR-2 aggregates.
- `raw_moose_extension_five_seed_summary.json` contains 740 measured Raw MOOSE
  extension records across five seeds.
- `moose_published_reference.json` records the MOOSE values reported by its
  authors; it is a bibliographic reference, not a local runtime measurement.
- `certificate_challenge_summary.json` records the 13 final certificate
  challenge outcomes.
- `execution_distribution.json` records aggregate execution distributions.
- `benchmark_compatibility.json` proves that the execution-time and portable
  benchmark differ only at listed fields below `provenance`.
- `manifest.json` binds every released file by SHA-256.

The five Full GP2PL seeds produce 6,059 valid Jason-plus-VAL traces among 6,140
evaluations. Of the 1,228 distinct cases, 1,180 succeed under every seed, 46 are
seed-sensitive, and 2 fail under every seed. Evidence is not pooled across
seeds, and no best seed is selected.

The atomic variants produce 5,420, 5,419, 6,059, and 6,059 valid traces for
Evidence Only, Direct Producers, Maximum Feasible, and Full GP2PL. The temporal
variants produce 1,113, 1,228, 1,228, and 1,212 valid traces for Unprotected
Serialization, Certified Flat, Certified Balanced, and Module-Return Monitor.
The temporal ablation uses the seed-0 Full GP2PL library. Its integrated
cross-seed extension evaluates Certified Balanced over all five independently
seeded Full GP2PL libraries: every seed validates all 1,228 queries, and every
query retains the same primitive-action count across seeds. This extension
tests the selected method's seed robustness; it does not rerun every temporal
ablation variant over five seeds.
`scripts/verify_public_result_release.py` recomputes these totals, paired case
sets, status counts, and PAR-2 values from the released records.

Each method-case key has one final scientific outcome. SHA-256 values in
`manifest.json` establish released-file integrity.
