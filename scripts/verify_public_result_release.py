#!/usr/bin/env python3
"""Verify the canonical, outcome-only GP2PL evaluation release."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import statistics
from typing import Any, Mapping, Sequence


ATOMIC_VARIANTS = {
	"validated_evidence_adapter": 5_420,
	"action_only_closure": 5_419,
	"maximal_certified_program": 6_059,
	"full": 6_059,
}
TEMPORAL_VARIANTS = {
	"dfa_aware_unprotected": 1_113,
	"certified_flat": 1_228,
	"certified_balanced": 1_228,
	"completion_boundary_monitor": 1_212,
}
CROSS_SEED_TEMPORAL_SEEDS = (0, 1, 2, 3, 4)
CROSS_SEED_TEMPORAL_RECORD_KEYS = frozenset(
	{
		"action_count",
		"domain",
		"duration_seconds",
		"gold_accepted",
		"jason_status",
		"prediction_accepted",
		"profile",
		"sample_id",
		"seed",
		"status",
		"val_attempted",
		"val_success",
		"valid",
	}
)
EXTERNAL_STATUS_COUNTS = {
	"achievement": {
		"no_plan": 4,
		"planner_failed": 272,
		"timeout": 108,
		"valid": 844,
	},
	"direct_temporal_by_method": {
		"FOND4LTLf + LAMA": {
			"compiler_failed": 109,
			"planner_failed": 85,
			"unsupported_identifier_encoding": 376,
			"unsupported_numeric_pddl": 360,
			"valid": 298,
		},
		"TIDE + LAMA": {
			"no_plan": 188,
			"planner_timeout": 5,
			"unsupported_numeric_formula": 207,
			"unsupported_numeric_pddl": 153,
			"valid": 675,
		},
	},
}
OUTCOME_FILES = (
	"certificate_challenge_summary.json",
	"external_reference_results.json",
	"five_seed_full_compiler_summary.json",
	"moose_published_reference.json",
	"paired_ablation_results.json",
	"raw_moose_extension_five_seed_summary.json",
	"temporal_execution_summary.json",
)
FORBIDDEN_OUTCOME_KEYS = {
	"command",
	"commit",
	"compiler_freeze",
	"compiler_lock_wait_seconds",
	"infrastructure_retry",
	"method_source_equivalence",
	"planner_exit_code",
	"provenance",
	"repair_num_workers",
	"revision",
	"run_id",
	"runtime_lock_wait_seconds",
	"sha256",
	"source_aggregate",
	"source_revision",
	"stderr",
	"stdout",
	"tracked_source_changes",
}
FORBIDDEN_KEY_FRAGMENTS = (
	"byte_identical",
	"fingerprint",
	"replaced_case",
	"replacement_case",
	"retry_",
)
FORBIDDEN_KEY_SUFFIXES = (
	"_commit",
	"_revision",
	"_run_id",
	"_sha256",
)
NON_PORTABLE_TEXT_MARKERS = (
	"/" + "users/",
	"file" + ":///",
	"llm-bdi-" + "pipeline-dev",
)


def verify_public_result_release(release_root: str | Path) -> dict[str, int]:
	"""Recompute all public aggregates from canonical per-case outcomes."""

	root = Path(release_root).expanduser().resolve()
	manifest = _verify_manifest(root)
	_verify_outcome_only_payloads(root)
	_verify_benchmark_compatibility(root)
	five_seed_count = _verify_five_seed_results(
		_read_json(root / "five_seed_full_compiler_summary.json"),
	)
	atomic_count, temporal_count, cross_seed_temporal_count = _verify_paired_ablation(
		_read_json(root / "paired_ablation_results.json"),
	)
	if manifest.get("paired_ablation_temporal_cross_seed_record_count") != (
		cross_seed_temporal_count
	):
		raise ValueError("manifest cross-seed temporal record count mismatch")
	if manifest.get("paired_ablation_temporal_cross_seed_seed_count") != len(
		CROSS_SEED_TEMPORAL_SEEDS
	):
		raise ValueError("manifest cross-seed temporal seed count mismatch")
	external_count = _verify_external_references(
		_read_json(root / "external_reference_results.json"),
	)
	moose_case_count = _verify_moose_reference(
		_read_json(root / "moose_published_reference.json"),
	)
	raw_moose_count = _verify_raw_moose_extension(
		_read_json(root / "raw_moose_extension_five_seed_summary.json"),
	)
	temporal_execution_count = _verify_temporal_execution(
		_read_json(root / "temporal_execution_summary.json"),
	)
	_verify_execution_distribution(
		_read_json(root / "execution_distribution.json"),
		_read_json(root / "temporal_execution_summary.json"),
	)
	challenge_count = _verify_challenges(
		_read_json(root / "certificate_challenge_summary.json"),
	)
	return {
		"atomic_ablation_record_count": atomic_count,
		"certificate_challenge_count": challenge_count,
		"external_reference_record_count": external_count,
		"five_seed_record_count": five_seed_count,
		"moose_published_case_count": moose_case_count,
		"raw_moose_extension_record_count": raw_moose_count,
		"temporal_ablation_record_count": temporal_count,
		"temporal_cross_seed_record_count": cross_seed_temporal_count,
		"temporal_execution_record_count": temporal_execution_count,
	}


def _verify_manifest(root: Path) -> dict[str, Any]:
	manifest = _read_json(root / "manifest.json")
	if manifest.get("artifact_kind") != "gp2pl_reproducibility_release":
		raise ValueError("unexpected evaluation manifest kind")
	declared = dict(manifest.get("files") or {})
	actual = {
		str(path.relative_to(root)): _sha256(path)
		for path in sorted(root.rglob("*"))
		if path.is_file() and path.name != "manifest.json"
	}
	if declared != actual:
		raise ValueError("evaluation manifest does not match released files")
	return manifest


def _verify_outcome_only_payloads(root: Path) -> None:
	for filename in OUTCOME_FILES:
		payload = _read_json(root / filename)
		serialized = json.dumps(payload, sort_keys=True).lower()
		for marker in NON_PORTABLE_TEXT_MARKERS:
			if marker in serialized:
				raise ValueError(f"{filename} contains non-portable marker {marker}")
		for key in _mapping_keys(payload):
			lowered = key.lower()
			if lowered in FORBIDDEN_OUTCOME_KEYS:
				raise ValueError(f"{filename} contains internal result key {key}")
			if lowered.endswith(FORBIDDEN_KEY_SUFFIXES):
				raise ValueError(f"{filename} contains source identity key {key}")
			if any(fragment in lowered for fragment in FORBIDDEN_KEY_FRAGMENTS):
				raise ValueError(f"{filename} contains process metadata key {key}")


def _verify_benchmark_compatibility(root: Path) -> None:
	certificate = _read_json(root / "benchmark_compatibility.json")
	if certificate.get("artifact_kind") != "benchmark_provenance_compatibility":
		raise ValueError("unexpected benchmark compatibility certificate kind")
	project_root = root.parents[2]
	benchmark_file = project_root / (
		"paper_artifacts/temporal_goal_benchmark/v1/benchmark.json"
	)
	if _sha256(benchmark_file) != certificate.get("current_benchmark_sha256"):
		raise ValueError("portable benchmark digest differs from its certificate")
	reconstructed = deepcopy(_read_json(benchmark_file))
	for replacement in certificate.get("replacements") or ():
		pointer = str(replacement.get("json_pointer") or "")
		if not pointer.startswith("/provenance/"):
			raise ValueError("benchmark normalization may only replace provenance")
		_set_json_pointer(reconstructed, pointer, replacement.get("execution_value"))
	if _json_sha256(reconstructed) != certificate.get("execution_benchmark_sha256"):
		raise ValueError("benchmark normalization certificate does not reconstruct source")


def _verify_five_seed_results(payload: Mapping[str, Any]) -> int:
	if payload.get("artifact_kind") != (
		"gp2pl_five_seed_full_compiler_submission_result"
	):
		raise ValueError("unexpected five-seed artifact kind")
	records = tuple(payload.get("case_records") or ())
	identities = {
		(int(row["seed"]), str(row["domain"]), str(row["test_id"]))
		for row in records
	}
	if len(records) != 6_140 or len(identities) != len(records):
		raise ValueError("five-seed records are incomplete or duplicated")
	case_sets = {
		seed: {
			(str(row["domain"]), str(row["test_id"]))
			for row in records
			if int(row["seed"]) == seed
		}
		for seed in range(5)
	}
	if any(len(case_set) != 1_228 for case_set in case_sets.values()):
		raise ValueError("five-seed case coverage is incomplete")
	if any(case_set != case_sets[0] for case_set in case_sets.values()):
		raise ValueError("five-seed repetitions do not share the same case set")
	for row in records:
		_require_case_measurements(row, runtime_key="jason_run_seconds")
		if row["valid"] is True and row.get("val_success") is not True:
			raise ValueError("valid five-seed trace lacks VAL acceptance")
	valid_count = sum(row["valid"] is True for row in records)
	aggregate = dict(payload.get("aggregate") or {})
	if valid_count != 6_059 or aggregate.get("pooled_success_count") != valid_count:
		raise ValueError("five-seed success aggregate mismatch")
	seed_results = tuple(payload.get("seed_results") or ())
	for seed in range(5):
		expected = sum(
			row["valid"] is True for row in records if int(row["seed"]) == seed
		)
		result = next(row for row in seed_results if int(row["seed"]) == seed)
		if int(result["success_count"]) != expected:
			raise ValueError(f"five-seed aggregate mismatch for seed {seed}")
	return len(records)


def _verify_paired_ablation(payload: Mapping[str, Any]) -> tuple[int, int, int]:
	if payload.get("artifact_kind") != "gp2pl_paired_ablation_results":
		raise ValueError("unexpected paired ablation artifact kind")
	atomic_records = tuple(payload.get("atomic_records") or ())
	temporal_records = tuple(payload.get("temporal_records") or ())
	_assert_variant_case_sets(
		atomic_records,
		identity_fields=("seed", "case_id"),
		variants=tuple(ATOMIC_VARIANTS),
		expected_case_count=6_140,
	)
	_assert_variant_case_sets(
		temporal_records,
		identity_fields=("sample_id",),
		variants=tuple(TEMPORAL_VARIANTS),
		expected_case_count=1_228,
	)
	for row in atomic_records:
		_require_case_measurements(row, runtime_key="duration_seconds")
		if row["valid"] is True and row.get("val_success") is not True:
			raise ValueError("valid atomic ablation trace lacks VAL acceptance")
	for row in temporal_records:
		_require_case_measurements(row, runtime_key="duration_seconds")
		if row["valid"] is True and not all(
			row.get(key) is True
			for key in ("val_success", "gold_accepted", "prediction_accepted")
		):
			raise ValueError("valid temporal ablation trace lacks a verifier outcome")
	_verify_variant_aggregates(payload.get("atomic") or (), atomic_records, ATOMIC_VARIANTS)
	_verify_variant_aggregates(
		payload.get("temporal") or (),
		temporal_records,
		TEMPORAL_VARIANTS,
	)
	cross_seed_temporal_count = _verify_cross_seed_temporal(payload)
	return len(atomic_records), len(temporal_records), cross_seed_temporal_count


def _verify_cross_seed_temporal(payload: Mapping[str, Any]) -> int:
	extension = dict(payload.get("temporal_cross_seed") or {})
	if extension.get("artifact_kind") != (
		"gp2pl_cross_seed_temporal_robustness_extension"
	):
		raise ValueError("unexpected cross-seed temporal artifact kind")
	protocol = dict(extension.get("protocol") or {})
	expected_protocol = {
		"atomic_compiler_variant": "full",
		"best_seed_selection": False,
		"case_count_per_seed": 1_228,
		"domain_count": 16,
		"evidence_union": False,
		"independent_seed_atomic_libraries": True,
		"jason_java_stack_size": "64m",
		"jason_timeout_seconds": 1_800,
		"method": "Certified Balanced",
		"plan_verifier_timeout_seconds": 1_800,
		"seeds": list(CROSS_SEED_TEMPORAL_SEEDS),
		"temporal_compiler_variant": "certified_balanced",
		"validated_seed_zero_correction_count": 1,
		"validation_workers": 6,
	}
	for key, expected in expected_protocol.items():
		if protocol.get(key) != expected:
			raise ValueError(f"cross-seed temporal protocol mismatch for {key}")

	records = tuple(payload.get("temporal_cross_seed_records") or ())
	if len(records) != 6_140:
		raise ValueError("cross-seed temporal records are incomplete")
	by_seed: dict[int, dict[tuple[str, str], Mapping[str, Any]]] = {}
	for seed in CROSS_SEED_TEMPORAL_SEEDS:
		seed_records = tuple(row for row in records if int(row.get("seed", -1)) == seed)
		if len(seed_records) != 1_228:
			raise ValueError(f"cross-seed temporal coverage mismatch for seed {seed}")
		by_case: dict[tuple[str, str], Mapping[str, Any]] = {}
		for row in seed_records:
			if set(row) != CROSS_SEED_TEMPORAL_RECORD_KEYS:
				raise ValueError("cross-seed temporal record schema mismatch")
			case = (str(row["domain"]), str(row["sample_id"]))
			if not all(case) or case in by_case:
				raise ValueError("duplicate or empty cross-seed temporal case")
			_require_case_measurements(row, runtime_key="duration_seconds")
			if not all(
				(
					row["valid"] is True,
					row["status"] == "success",
					row["jason_status"] == "success",
					row["val_attempted"] is True,
					row["val_success"] is True,
					row["gold_accepted"] is True,
					row["prediction_accepted"] is True,
				)
			):
				raise ValueError("cross-seed temporal record lacks complete acceptance")
			by_case[case] = row
		by_seed[seed] = by_case

	baseline_cases = set(by_seed[CROSS_SEED_TEMPORAL_SEEDS[0]])
	if any(set(by_seed[seed]) != baseline_cases for seed in CROSS_SEED_TEMPORAL_SEEDS[1:]):
		raise ValueError("cross-seed temporal repetitions use different case sets")
	seed_zero_ablation = {
		(str(row["domain"]), str(row["sample_id"])): row
		for row in payload.get("temporal_records") or ()
		if row.get("variant") == "certified_balanced"
	}
	if set(seed_zero_ablation) != baseline_cases:
		raise ValueError("seed-0 cross-seed records differ from the paired ablation cases")
	shared_outcome_fields = (
		"action_count",
		"domain",
		"duration_seconds",
		"gold_accepted",
		"jason_status",
		"prediction_accepted",
		"profile",
		"sample_id",
		"status",
		"val_attempted",
		"val_success",
		"valid",
	)
	for case in sorted(baseline_cases):
		cross_seed_row = by_seed[0][case]
		ablation_row = seed_zero_ablation[case]
		if any(
			cross_seed_row[field] != ablation_row[field]
			for field in shared_outcome_fields
		):
			raise ValueError(
				"seed-0 cross-seed outcome differs from its paired ablation record",
			)

	expected_seed_results = []
	for seed in CROSS_SEED_TEMPORAL_SEEDS:
		seed_records = tuple(by_seed[seed].values())
		valid_records = tuple(row for row in seed_records if row["valid"] is True)
		status_counts = Counter(str(row["status"]) for row in seed_records)
		par2_values = [
			float(row["duration_seconds"]) if row["valid"] is True else 3_600.0
			for row in seed_records
		]
		expected_seed_results.append(
			{
				"evaluation_count": len(seed_records),
				"failure_count": len(seed_records) - len(valid_records),
				"median_action_count": statistics.median(
					[int(row["action_count"]) for row in valid_records],
				),
				"median_valid_seconds": statistics.median(
					[float(row["duration_seconds"]) for row in valid_records],
				),
				"par2_seconds": statistics.mean(par2_values),
				"seed": seed,
				"status_counts": dict(sorted(status_counts.items())),
				"success_count": len(valid_records),
				"success_rate": len(valid_records) / len(seed_records),
			}
		)
	if list(extension.get("seed_results") or ()) != expected_seed_results:
		raise ValueError("cross-seed temporal seed aggregates differ from records")
	balanced_aggregate = next(
		row
		for row in payload.get("temporal") or ()
		if row.get("variant") == "certified_balanced"
	)
	if balanced_aggregate.get("par2_seconds") != expected_seed_results[0]["par2_seconds"]:
		raise ValueError("seed-0 Certified Balanced PAR-2 differs across release views")

	patterns: Counter[str] = Counter()
	persistent_failures: list[dict[str, str]] = []
	seed_sensitive_cases: list[dict[str, str]] = []
	action_count_variant_cases: list[dict[str, Any]] = []
	action_count_invariant_count = 0
	action_count_unavailable_count = 0
	group_patterns: dict[str, dict[str, list[str]]] = {
		"domain": {},
		"profile": {},
	}
	for domain, sample_id in sorted(baseline_cases):
		case_rows = [by_seed[seed][(domain, sample_id)] for seed in CROSS_SEED_TEMPORAL_SEEDS]
		profile = str(case_rows[0]["profile"])
		if not profile or any(str(row["profile"]) != profile for row in case_rows):
			raise ValueError("cross-seed temporal profile differs across seeds")
		pattern = "".join("1" if row["valid"] is True else "0" for row in case_rows)
		patterns[pattern] += 1
		group_patterns["domain"].setdefault(domain, []).append(pattern)
		group_patterns["profile"].setdefault(profile, []).append(pattern)
		identity = {"domain": domain, "sample_id": sample_id}
		if pattern == "00000":
			persistent_failures.append(identity)
		elif "0" in pattern and "1" in pattern:
			seed_sensitive_cases.append({**identity, "pattern": pattern})
		actions = [row.get("action_count") for row in case_rows]
		if any(action is None for action in actions):
			action_count_unavailable_count += 1
		elif len({int(action) for action in actions}) == 1:
			action_count_invariant_count += 1
		else:
			action_count_variant_cases.append(
				{**identity, "action_counts": [int(action) for action in actions]},
			)

	if dict(extension.get("case_outcomes") or {}) != {
		"action_count_variant_cases": action_count_variant_cases,
		"pattern_counts": dict(sorted(patterns.items())),
		"persistent_failures": persistent_failures,
		"seed_sensitive_cases": seed_sensitive_cases,
	}:
		raise ValueError("cross-seed temporal case patterns differ from records")

	seed_success_counts = [int(row["success_count"]) for row in expected_seed_results]
	seed_success_rates = [float(row["success_rate"]) for row in expected_seed_results]
	seed_par2 = [float(row["par2_seconds"]) for row in expected_seed_results]
	expected_aggregate = {
		"action_count_invariant_case_count": action_count_invariant_count,
		"action_count_unavailable_case_count": action_count_unavailable_count,
		"action_count_variant_case_count": len(action_count_variant_cases),
		"all_seed_failure_case_count": patterns["00000"],
		"all_seed_success_case_count": patterns["11111"],
		"at_least_one_seed_success_case_count": len(baseline_cases) - patterns["00000"],
		"failure_count": 6_140 - sum(seed_success_counts),
		"maximum_seed_par2_seconds": max(seed_par2),
		"mean_seed_par2_seconds": statistics.mean(seed_par2),
		"mean_success_count": statistics.mean(seed_success_counts),
		"mean_success_rate": statistics.mean(seed_success_rates),
		"minimum_seed_par2_seconds": min(seed_par2),
		"pooled_evaluation_count": 6_140,
		"pooled_success_count": sum(seed_success_counts),
		"sample_sd_seed_par2_seconds": statistics.stdev(seed_par2),
		"sample_sd_success_count": statistics.stdev(seed_success_counts),
		"sample_sd_success_rate": statistics.stdev(seed_success_rates),
		"seed_sensitive_case_count": sum(
			count for pattern, count in patterns.items() if "0" in pattern and "1" in pattern
		),
	}
	if dict(extension.get("aggregate") or {}) != expected_aggregate:
		raise ValueError("cross-seed temporal aggregate differs from records")
	if list(extension.get("domains") or ()) != _cross_seed_group_rows(
		group_patterns["domain"],
		group_name="domain",
	):
		raise ValueError("cross-seed temporal domain rows differ from records")
	if list(extension.get("profiles") or ()) != _cross_seed_group_rows(
		group_patterns["profile"],
		group_name="profile",
	):
		raise ValueError("cross-seed temporal profile rows differ from records")
	return len(records)


def _cross_seed_group_rows(
	patterns_by_group: Mapping[str, Sequence[str]],
	*,
	group_name: str,
) -> list[dict[str, Any]]:
	rows = []
	for name in sorted(patterns_by_group):
		patterns = tuple(patterns_by_group[name])
		success_counts = [
			sum(pattern[index] == "1" for pattern in patterns)
			for index in range(len(CROSS_SEED_TEMPORAL_SEEDS))
		]
		rates = [count / len(patterns) for count in success_counts]
		rows.append(
			{
				group_name: name,
				"case_count_per_seed": len(patterns),
				"success_counts": success_counts,
				"mean_success_rate": statistics.mean(rates),
				"sample_sd_success_rate": statistics.stdev(rates),
				"all_seed_success_case_count": patterns.count("11111"),
				"seed_sensitive_case_count": sum(
					"0" in pattern and "1" in pattern for pattern in patterns
				),
				"all_seed_failure_case_count": patterns.count("00000"),
			}
		)
	return rows


def _verify_external_references(payload: Mapping[str, Any]) -> int:
	if payload.get("artifact_kind") != "gp2pl_external_reference_results":
		raise ValueError("unexpected external-reference artifact kind")
	if payload.get("schema_version") != 2:
		raise ValueError("unexpected external-reference schema version")
	records = tuple(payload.get("records") or ())
	identities = {
		(str(row["record_kind"]), str(row["method"]), str(row["case_id"]))
		for row in records
	}
	if len(records) != 3_684 or len(identities) != len(records):
		raise ValueError("external records are incomplete or duplicated")
	protocol = dict(payload.get("protocol") or {})
	if (
		protocol.get("record_count") != 3_684
		or protocol.get("achievement_case_count") != 1_228
		or protocol.get("temporal_case_count_per_method") != 1_228
		or protocol.get("tide_num_workers") != 12
	):
		raise ValueError("external-reference protocol mismatch")
	for row in records:
		_require_case_measurements(row, runtime_key="elapsed_seconds")
		if row["valid"] is True and row["record_kind"] == "direct_temporal":
			validation = dict(row.get("execution_validation") or {})
			if not all(
				validation.get(key) is True
				for key in (
					"replay_valid",
					"val_success",
					"gold_accepted",
					"prediction_accepted",
				)
			):
				raise ValueError("valid direct temporal result lacks verifier acceptance")
	status_counts = {
		"achievement": dict(
			sorted(
				Counter(
					str(row["status"])
					for row in records
					if row["record_kind"] == "achievement"
				).items(),
			),
		),
		"direct_temporal_by_method": {
			method: dict(
				sorted(
					Counter(
						str(row["status"])
						for row in records
						if row["record_kind"] == "direct_temporal"
						and row["method"] == method
					).items(),
				),
			)
			for method in ("FOND4LTLf + LAMA", "TIDE + LAMA")
		},
	}
	if status_counts != EXTERNAL_STATUS_COUNTS:
		raise ValueError("external status aggregate mismatch")
	if dict(payload.get("status_counts") or {}) != status_counts:
		raise ValueError("published external status counts differ from records")
	_verify_external_rows(payload, records)
	return len(records)


def _verify_external_rows(
	payload: Mapping[str, Any],
	records: Sequence[Mapping[str, Any]],
) -> None:
	rows = {str(row["method"]): row for row in payload.get("rows") or ()}
	for variant, method, expected_count, expected_valid in (
		("lama", "LAMA", 868, 591),
		("enhsp_hmrphj", "MRP+HJ", 360, 253),
	):
		method_records = tuple(row for row in records if row["variant"] == variant)
		_verify_measured_row(
			rows[method],
			method_records,
			expected_count=expected_count,
			expected_valid=expected_valid,
		)
	temporal_records = tuple(
		row
		for row in records
		if row["variant"] == "fond4ltlf_lama" and row["supported"] is True
	)
	_verify_measured_row(
		rows["FOND4LTLf + LAMA"],
		temporal_records,
		expected_count=492,
		expected_valid=298,
	)
	tide_records = tuple(
		row
		for row in records
		if row["variant"] == "tide_lama" and row["supported"] is True
	)
	_verify_measured_row(
		rows["TIDE + LAMA"],
		tide_records,
		expected_count=868,
		expected_valid=675,
	)
	if rows["FOND4LTLf + LAMA"]["unsupported_case_count"] != 736:
		raise ValueError("FOND4LTLf unsupported-case count mismatch")
	if rows["TIDE + LAMA"]["unsupported_case_count"] != 360:
		raise ValueError("TIDE unsupported-case count mismatch")


def _verify_measured_row(
	row: Mapping[str, Any],
	records: Sequence[Mapping[str, Any]],
	*,
	expected_count: int,
	expected_valid: int,
) -> None:
	if len(records) != expected_count:
		raise ValueError(f"external case count mismatch for {row['method']}")
	valid_count = sum(record["valid"] is True for record in records)
	if valid_count != expected_valid:
		raise ValueError(f"external valid count mismatch for {row['method']}")
	par2_seconds = sum(
		float(record["elapsed_seconds"]) if record["valid"] is True else 3_600.0
		for record in records
	) / len(records)
	if row["case_count"] != len(records) or row["valid_trace_count"] != valid_count:
		raise ValueError(f"external row count mismatch for {row['method']}")
	if abs(float(row["par2_seconds"]) - par2_seconds) > 1e-9:
		raise ValueError(f"external row PAR-2 mismatch for {row['method']}")


def _verify_moose_reference(payload: Mapping[str, Any]) -> int:
	if payload.get("artifact_kind") != "published_moose_planning_coverage_reference":
		raise ValueError("unexpected published MOOSE reference artifact kind")
	results = dict(payload.get("published_results") or {})
	domains = tuple(results.get("domains") or ())
	case_count = sum(int(row["case_count_per_seed"]) for row in domains)
	mean_solved = sum(float(row["mean_solved_count"]) for row in domains)
	if len(domains) != 12 or case_count != 1_080:
		raise ValueError("published MOOSE domain coverage mismatch")
	if results.get("case_count_per_seed") != case_count:
		raise ValueError("published MOOSE case count mismatch")
	if abs(float(results["mean_solved_count"]) - mean_solved) > 1e-9:
		raise ValueError("published MOOSE solved count mismatch")
	return case_count


def _verify_raw_moose_extension(payload: Mapping[str, Any]) -> int:
	if payload.get("artifact_kind") != "gp2pl_raw_moose_extension_five_seed_result":
		raise ValueError("unexpected Raw MOOSE extension artifact kind")
	records = tuple(payload.get("records") or ())
	identities = {(int(row["seed"]), str(row["case_id"])) for row in records}
	if len(records) != 740 or len(identities) != len(records):
		raise ValueError("Raw MOOSE extension records are incomplete or duplicated")
	for row in records:
		_require_case_measurements(row, runtime_key="elapsed_seconds")
	valid_count = sum(row["valid"] is True for row in records)
	aggregate = dict(payload.get("aggregate") or {})
	if valid_count != 117 or aggregate.get("pooled_valid_count") != valid_count:
		raise ValueError("Raw MOOSE extension aggregate mismatch")
	return len(records)


def _verify_temporal_execution(payload: Mapping[str, Any]) -> int:
	if payload.get("artifact_kind") != "temporal_goal_execution_validation":
		raise ValueError("unexpected temporal execution artifact kind")
	records = tuple(payload.get("results") or ())
	identities = {str(row["sample_id"]) for row in records}
	if len(records) != 1_228 or len(identities) != len(records):
		raise ValueError("temporal execution records are incomplete or duplicated")
	for row in records:
		_require_case_measurements(row, runtime_key="duration_seconds")
		validation = dict(row.get("execution_validation") or {})
		if row.get("success") is not True or not all(
			validation.get(key) is True
			for key in (
				"replay_valid",
				"val_success",
				"gold_accepted",
				"prediction_accepted",
			)
		):
			raise ValueError("temporal execution record lacks full acceptance")
	if int(dict(payload.get("aggregate") or {}).get("success_count", -1)) != 1_228:
		raise ValueError("temporal execution aggregate mismatch")
	return len(records)


def _verify_execution_distribution(
	payload: Mapping[str, Any],
	execution: Mapping[str, Any],
) -> None:
	records = tuple(execution.get("results") or ())
	expected = {
		"result_count": len(records),
		"duration_seconds": _distribution(
			[float(record["duration_seconds"]) for record in records],
		),
		"action_count": _distribution(
			[int(record["action_count"]) for record in records],
		),
	}
	if dict(payload) != expected:
		raise ValueError("execution distribution differs from temporal case records")


def _verify_challenges(payload: Mapping[str, Any]) -> int:
	records = tuple(payload.get("records") or ())
	if len(records) != 13 or len({str(row.get("name")) for row in records}) != 13:
		raise ValueError("certificate challenge records are incomplete or duplicated")
	if payload.get("success") is not True or sum(
		row.get("success") is True for row in records
	) != 13:
		raise ValueError("certificate challenge matrix is not fully successful")
	return len(records)


def _verify_variant_aggregates(
	aggregates: Sequence[Mapping[str, Any]],
	records: Sequence[Mapping[str, Any]],
	expected: Mapping[str, int],
) -> None:
	by_variant = {str(row["variant"]): row for row in aggregates}
	if set(by_variant) != set(expected):
		raise ValueError("ablation aggregate variants differ from the registered set")
	for variant, expected_valid in expected.items():
		variant_records = tuple(row for row in records if row["variant"] == variant)
		valid_count = sum(row["valid"] is True for row in variant_records)
		aggregate = by_variant[variant]
		if valid_count != expected_valid:
			raise ValueError(f"unexpected valid count for {variant}")
		if int(aggregate["test_count"]) != len(variant_records):
			raise ValueError(f"test count mismatch for {variant}")
		if int(aggregate["valid_trace_count"]) != valid_count:
			raise ValueError(f"aggregate valid count mismatch for {variant}")


def _assert_variant_case_sets(
	records: Sequence[Mapping[str, Any]],
	*,
	identity_fields: Sequence[str],
	variants: Sequence[str],
	expected_case_count: int,
) -> None:
	all_identities = [
		(str(row["variant"]), *(row[field] for field in identity_fields))
		for row in records
	]
	if len(all_identities) != len(set(all_identities)):
		raise ValueError("duplicate paired ablation record")
	case_sets = {
		variant: {
			tuple(row[field] for field in identity_fields)
			for row in records
			if row["variant"] == variant
		}
		for variant in variants
	}
	if any(len(case_set) != expected_case_count for case_set in case_sets.values()):
		raise ValueError("paired ablation variant coverage is incomplete")
	first = case_sets[variants[0]]
	if any(case_set != first for case_set in case_sets.values()):
		raise ValueError("paired ablation variants do not share the same case set")


def _require_case_measurements(
	record: Mapping[str, Any],
	*,
	runtime_key: str,
) -> None:
	if float(record.get(runtime_key, -1.0)) < 0:
		raise ValueError(f"case record lacks non-negative {runtime_key}")
	if "action_count" not in record:
		raise ValueError("case record lacks an action-count outcome")
	action_count = record.get("action_count")
	if action_count is None:
		if record.get("valid") is True or record.get("success") is True:
			raise ValueError("successful case record lacks an action count")
	elif int(action_count) < 0:
		raise ValueError("case record contains a negative action count")
	if not str(record.get("status") or ""):
		raise ValueError("case record lacks a final status")


def _distribution(values: Sequence[float | int]) -> dict[str, float | int]:
	quartiles = statistics.quantiles(values, n=4, method="inclusive")
	return {
		"minimum": min(values),
		"first_quartile": quartiles[0],
		"median": statistics.median(values),
		"third_quartile": quartiles[2],
		"maximum": max(values),
		"mean": statistics.mean(values),
		"sample_standard_deviation": statistics.stdev(values),
	}


def _set_json_pointer(payload: dict[str, Any], pointer: str, value: Any) -> None:
	parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]]
	current: dict[str, Any] = payload
	for part in parts[:-1]:
		next_value = current.get(part)
		if not isinstance(next_value, dict):
			raise ValueError(f"benchmark compatibility pointer is invalid: {pointer}")
		current = next_value
	current[parts[-1]] = deepcopy(value)


def _mapping_keys(payload: Any) -> tuple[str, ...]:
	keys: list[str] = []
	if isinstance(payload, Mapping):
		for key, value in payload.items():
			keys.append(str(key))
			keys.extend(_mapping_keys(value))
	elif isinstance(payload, Sequence) and not isinstance(
		payload,
		(str, bytes, bytearray),
	):
		for value in payload:
			keys.extend(_mapping_keys(value))
	return tuple(keys)


def _read_json(path: Path) -> dict[str, Any]:
	if not path.is_file():
		raise FileNotFoundError(f"Missing result artifact: {path}")
	payload = json.loads(path.read_text(encoding="utf-8"))
	if not isinstance(payload, dict):
		raise ValueError(f"Result artifact must contain a JSON object: {path}")
	return payload


def _json_sha256(payload: Any) -> str:
	serialized = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
	return hashlib.sha256(serialized).hexdigest()


def _sha256(path: Path) -> str:
	return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
	release_root = Path(__file__).resolve().parents[1] / (
		"paper_artifacts/gp2pl_evaluation/v1"
	)
	report = verify_public_result_release(release_root)
	print(
		"[ok] public result release "
		+ " ".join(f"{key}={value}" for key, value in sorted(report.items())),
	)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
