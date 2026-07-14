"""Normalize public evaluation records to scientific outcomes only."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


EXCLUDED_PUBLIC_KEYS = {
	"atomic_batch_root",
	"atomic_library_mode",
	"benchmark_file",
	"clean_git_state_required",
	"command",
	"commit",
	"compiler_freeze",
	"compiler_lock_wait_seconds",
	"completed_at",
	"created_at",
	"derived_metric_correction",
	"domain_file",
	"environment_dir",
	"finished_at",
	"failure_diagnostics",
	"fresh_validation",
	"hardware_equivalence_confirmed_by_experiment_owner",
	"infrastructure_retry",
	"method_source_equivalence",
	"model_file",
	"node_id",
	"planner_exit_code",
	"policy_file",
	"primary_num_workers",
	"problem_files",
	"provenance",
	"released_at",
	"return_code",
	"repair_num_workers",
	"revision",
	"run_id",
	"runtime_lock_wait_seconds",
	"sha256",
	"shared_jason_environments",
	"source_aggregate",
	"source_file",
	"source_method_label",
	"source_revision",
	"started_at",
	"stderr",
	"stdout",
	"tracked_change_seed_exceptions",
	"tracked_source_changes",
	"untracked_source_files",
	"nonzero_exit_count",
}
EXCLUDED_PUBLIC_DICTIONARY_ENTRIES = {
	"achievement_repair",
	"direct_temporal_repair",
}
EXCLUDED_PUBLIC_KEY_FRAGMENTS = (
	"byte_identical",
	"fingerprint",
)
EXCLUDED_PUBLIC_KEY_SUFFIXES = (
	"_bytes",
	"_commit",
	"_command",
	"_dir",
	"_directory",
	"_file",
	"_files",
	"_path",
	"_paths",
	"_revision",
	"_revisions",
	"_root",
	"_run_id",
	"_sha256",
)

_METHOD_BY_VARIANT = {
	"action_only_closure": "Direct Producers",
	"certified_balanced": "Certified Balanced",
	"certified_flat": "Certified Flat",
	"completion_boundary_monitor": "Module-Return Monitor",
	"dfa_aware_unprotected": "Unprotected Serialization",
	"full": "Full GP2PL",
	"maximal_certified_program": "Maximum Feasible",
	"validated_evidence_adapter": "Evidence Only",
}


def outcome_only_payload(value: Any) -> Any:
	"""Remove execution identity and internal repair metadata from results."""

	if isinstance(value, Mapping):
		payload = {
			str(key): outcome_only_payload(item)
			for key, item in value.items()
			if str(key) not in EXCLUDED_PUBLIC_DICTIONARY_ENTRIES
			and not is_excluded_public_key(str(key))
		}
		variant = str(payload.get("variant") or "")
		if variant in _METHOD_BY_VARIANT and "method" in payload:
			payload["method"] = _METHOD_BY_VARIANT[variant]
		return payload
	if isinstance(value, Sequence) and not isinstance(
		value,
		(str, bytes, bytearray),
	):
		return [outcome_only_payload(item) for item in value]
	return value


def is_excluded_public_key(key: str) -> bool:
	"""Return whether a key identifies a run, source snapshot, or byte digest."""

	return (
		key in EXCLUDED_PUBLIC_KEYS
		or key.endswith(EXCLUDED_PUBLIC_KEY_SUFFIXES)
		or any(fragment in key for fragment in EXCLUDED_PUBLIC_KEY_FRAGMENTS)
	)
