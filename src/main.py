"""
Compile reusable atomic libraries, compose queries, and execute them with Jason.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

_src_dir = str(Path(__file__).parent)
if _src_dir not in sys.path:
	sys.path.insert(0, _src_dir)

from domain_level_planning import (  # noqa: E402
	append_lifted_temporal_goal_case_to_library,
	compile_policy_evidence_program_to_minimal_module_asl_library,
	evidence_program_from_moose_readable_policy,
	load_lifted_ltlf_goal_dataset,
)
from evaluation.jason_runtime import JasonPlanLibraryRunner  # noqa: E402
from plan_library.models import PlanLibrary  # noqa: E402
from plan_library.rendering import render_plan_library_asl  # noqa: E402
from utils.pddl_parser import PDDLParser  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOMAIN_LIBRARY_ROOT = PROJECT_ROOT / "artifacts" / "domain_libraries"


def _absolute_path(path_text: str | None) -> str | None:
	if not path_text:
		return None
	return str(Path(path_text).expanduser().resolve())


def _require_existing_path(path_text: str | None, *, label: str) -> str:
	resolved_path = _absolute_path(path_text)
	if not resolved_path or not Path(resolved_path).exists():
		print("=" * 80)
		print(f"ERROR: {label} Not Found")
		print("=" * 80)
		print(f"\nProvided path does not exist:\n{resolved_path}")
		sys.exit(1)
	return resolved_path


def build_argument_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		description=(
			"Build domain-level lifted AgentSpeak(L) atomic libraries from external "
			"generalized-planning singleton-goal policy files, then append validated "
			"lifted LTLf/DFA query wrappers."
		),
		formatter_class=argparse.RawDescriptionHelpFormatter,
		epilog="""
Examples:
  gp2pl compile-moose-atomic-library --policy-file artifacts/moose/ferry.model.readable --domain-file src/domains/ferry/domain.pddl --domain-name ferry
  gp2pl append-lifted-temporal-goal --domain-file src/domains/ferry/domain.pddl --ltlf-goal-json artifacts/input/query.json --query-id query_1
  gp2pl validate-jason-plan-library --domain-file src/domains/ferry/domain.pddl --problem-file src/domains/ferry/test/p0_01.pddl --goal-name g_query_1
		""",
	)
	subparsers = parser.add_subparsers(dest="command")

	moose_parser = subparsers.add_parser(
		"compile-moose-atomic-library",
		help="Compile a MOOSE readable singleton-goal policy into a domain atomic ASL library.",
	)
	moose_parser.add_argument("--policy-file", required=True, help="MOOSE readable policy file.")
	moose_parser.add_argument("--domain-name", required=True, help="PDDL domain name for the output library.")
	moose_parser.add_argument(
		"--domain-file",
		required=True,
		help="PDDL domain file for policy lifting, certification, and atomic synthesis.",
	)
	moose_parser.add_argument(
		"--library-root",
		default=str(DEFAULT_DOMAIN_LIBRARY_ROOT),
		help=(
			"Root directory for canonical per-domain libraries. The command writes "
			"<library-root>/<domain>/plan_library.{json,asl}."
		),
	)
	moose_parser.add_argument(
		"--overwrite",
		action="store_true",
		help="Allow rebuilding an existing canonical domain library.",
	)

	append_temporal_parser = subparsers.add_parser(
		"append-lifted-temporal-goal",
		help=(
			"Append lifted LTLf/DFA query wrappers to an existing domain atomic "
			"ASL library."
		),
	)
	append_temporal_parser.add_argument("--domain-file", required=True, help="Path to the PDDL domain file.")
	append_temporal_parser.add_argument(
		"--plan-library-file",
		help=(
			"Existing canonical domain plan_library.json file. Defaults to "
			"<library-root>/<domain>/plan_library.json and must match it if provided."
		),
	)
	append_temporal_parser.add_argument(
		"--ltlf-goal-json",
		required=True,
		help="Lifted LTLf goal JSON produced by the external Input component.",
	)
	append_temporal_parser.add_argument(
		"--query-id",
		action="append",
		help="Query id to append. Repeat for multiple queries. Defaults to all cases.",
	)
	append_temporal_parser.add_argument(
		"--library-root",
		default=str(DEFAULT_DOMAIN_LIBRARY_ROOT),
		help=(
			"Root directory for canonical per-domain libraries. The command updates "
			"<library-root>/<domain>/plan_library.{json,asl} in place."
		),
	)

	jason_parser = subparsers.add_parser(
		"validate-jason-plan-library",
		help="Run a canonical domain AgentSpeak(L) library in the real Jason interpreter.",
	)
	jason_parser.add_argument("--domain-file", required=True, help="Path to the PDDL domain file.")
	jason_parser.add_argument("--problem-file", required=True, help="Path to the PDDL problem file.")
	jason_parser.add_argument(
		"--goal-name",
		required=True,
		help="Top-level AgentSpeak achievement goal to run, for example g_blocks_user_goal_1.",
	)
	jason_parser.add_argument(
		"--reference-template-file",
		help="Optional reference goal-template JSON for independent query trace validation.",
	)
	jason_parser.add_argument(
		"--plan-library-asl",
		help=(
			"Canonical plan_library.asl file. Defaults to "
			"<library-root>/<domain>/plan_library.asl and must match it if provided."
		),
	)
	jason_parser.add_argument(
		"--library-root",
		default=str(DEFAULT_DOMAIN_LIBRARY_ROOT),
		help="Root directory for canonical per-domain libraries.",
	)
	jason_parser.add_argument(
		"--output-dir",
		help="Directory for Jason runtime files. Defaults to artifacts/jason_validation/<domain>/<goal>.",
	)
	jason_parser.add_argument(
		"--timeout-seconds",
		type=int,
		default=1800,
		help="Hard timeout for the Jason runtime process.",
	)
	jason_parser.add_argument(
		"--jason-java-stack-size",
		default="64m",
		help=(
			"Java thread stack size for Jason, passed as -Xss<size>. "
			"Defaults to 64m for recursive plan execution."
		),
	)
	jason_parser.add_argument(
		"--plan-verifier-command",
		help=(
			"Explicit VAL or IPC verifier command. Query trace validation otherwise "
			"uses the environment or PATH."
		),
	)
	jason_parser.add_argument(
		"--require-plan-verifier",
		action=argparse.BooleanOptionalAction,
		default=False,
		help="Require exported PDDL plan trace validation with VAL/IPC verifier.",
	)
	jason_parser.add_argument(
		"--plan-verifier-timeout-seconds",
		type=int,
		default=1800,
		help="Hard timeout for VAL/IPC plan verification.",
	)
	return parser


def main() -> None:
	parser = build_argument_parser()
	args = parser.parse_args()
	if not args.command:
		parser.print_help()
		sys.exit(2)

	if args.command == "compile-moose-atomic-library":
		results = _compile_moose_atomic_library(args)
	elif args.command == "append-lifted-temporal-goal":
		results = _append_lifted_temporal_goal(args)
	elif args.command == "validate-jason-plan-library":
		results = _validate_jason_plan_library(args)
	else:
		parser.error(f"Unsupported command {args.command!r}")
		return

	print(json.dumps(results, indent=2, default=str))
	sys.exit(0 if results.get("success", False) else 1)


def _compile_moose_atomic_library(args: argparse.Namespace) -> dict[str, Any]:
	policy_file = _require_existing_path(args.policy_file, label="MOOSE Policy File")
	domain_file = _require_existing_path(args.domain_file, label="Domain File")
	pddl_domain_name = PDDLParser.parse_domain(domain_file).name
	source_metadata = _domain_source_metadata(domain_file)
	domain_name = _canonical_domain_key_for_domain_file(
		domain_file,
		fallback_domain_name=str(args.domain_name).strip(),
	)
	output_root = _canonical_domain_library_dir(
		library_root=args.library_root,
		domain_name=domain_name,
	)
	policy_text = Path(policy_file).read_text(encoding="utf-8")
	source_name = Path(policy_file).stem.replace(".model", "")
	evidence_program = evidence_program_from_moose_readable_policy(
		policy_text,
		source_name=source_name,
		policy_file=policy_file,
	)
	library = compile_policy_evidence_program_to_minimal_module_asl_library(
		evidence_program,
		domain_file=domain_file,
		domain_name=domain_name,
	)
	artifact_paths = _persist_current_plan_library(
		plan_library=library,
		output_root=output_root,
		metadata={
			"artifact_kind": "validated_policy_lifting_atomic_library",
			"evidence_provider": "moose",
			"domain_file": domain_file,
			"pddl_domain_name": pddl_domain_name,
			"validated_policy_lifting": True,
			"policy_file": policy_file,
			"source_name": source_name,
			"source_metadata": source_metadata,
		},
		allow_overwrite=bool(getattr(args, "overwrite", False)),
	)
	return {
		"success": True,
		"domain_name": library.domain_name,
		"plan_count": len(library.plans),
		"artifact_paths": artifact_paths,
	}


def _append_lifted_temporal_goal(args: argparse.Namespace) -> dict[str, Any]:
	domain_file = _require_existing_path(args.domain_file, label="Domain File")
	domain = PDDLParser.parse_domain(domain_file)
	domain_key = _canonical_domain_key_for_domain_file(
		domain_file,
		fallback_domain_name=domain.name,
	)
	output_root = _canonical_domain_library_dir(
		library_root=args.library_root,
		domain_name=domain_key,
	)
	canonical_plan_library_file = str(Path(output_root) / "plan_library.json")
	plan_library_file = _require_existing_path(
		args.plan_library_file or canonical_plan_library_file,
		label="Plan Library File",
	)
	if Path(plan_library_file).resolve() != Path(canonical_plan_library_file).resolve():
		raise ValueError(
			"noncanonical_domain_library: append-lifted-temporal-goal must update "
			f"the canonical library for domain {domain.name!r}: "
			f"{canonical_plan_library_file}",
		)
	ltlf_goal_json = _require_existing_path(
		args.ltlf_goal_json,
		label="Lifted LTLf Goal JSON",
	)
	library = PlanLibrary.from_dict(
		json.loads(Path(plan_library_file).read_text(encoding="utf-8")),
	)
	if library.domain_name not in {domain_key, domain.name}:
		raise ValueError(
			"domain_library_mismatch: loaded plan library domain "
			f"{library.domain_name!r} does not match canonical domain key "
			f"{domain_key!r} or PDDL domain {domain.name!r}.",
		)
	dataset = load_lifted_ltlf_goal_dataset(ltlf_goal_json)
	selected_query_ids = {
		str(query_id).strip()
		for query_id in tuple(args.query_id or ())
		if str(query_id).strip()
	}
	selected_cases = tuple(
		case
		for case in dataset.cases
		if not selected_query_ids or case.query_id in selected_query_ids
	)
	if selected_query_ids and len(selected_cases) != len(selected_query_ids):
		found = {case.query_id for case in selected_cases}
		missing = sorted(selected_query_ids - found)
		raise ValueError(f"Unknown lifted LTLf query ids: {', '.join(missing)}")

	from evaluation.temporal_compilation import DFABuilder

	dfa_builder = DFABuilder()
	existing_metadata = _existing_artifact_metadata(output_root)
	queries = dict(existing_metadata.get("queries") or {})
	updated_library = library
	errors: list[dict[str, object]] = []
	for case in selected_cases:
		try:
			updated_library, dfa_payload = append_lifted_temporal_goal_case_to_library(
				plan_library=updated_library,
				goal_case=case,
				domain_file=domain_file,
				dfa_builder=dfa_builder,
			)
			queries[case.goal_name] = {
				"query": {
					**dataset.to_dict(),
					"cases": {case.query_id: case.to_dict()},
				},
				"dfa": dict(dfa_payload),
			}
		except Exception as error:  # noqa: BLE001 - returned as validator feedback.
			errors.append(
				{
					"query_id": case.query_id,
					"goal_name": case.goal_name,
					"error_type": _temporal_append_error_type(error),
					"message": str(error),
				},
			)
	if errors:
		return {"success": False, "errors": errors}

	artifact_paths = _persist_current_plan_library(
		plan_library=updated_library,
		output_root=output_root,
		metadata={
			**existing_metadata,
			"base_artifact_kind": existing_metadata.get("artifact_kind"),
			"artifact_kind": "domain_library_with_temporal_append",
			"source_plan_library_file": plan_library_file,
			"ltlf_goal_json": ltlf_goal_json,
			"pddl_domain_name": domain.name,
			"queries": queries,
		},
		allow_overwrite=True,
	)
	results = {
		"success": True,
		"domain_name": updated_library.domain_name,
		"appended_query_count": len(selected_cases),
		"plan_count": len(updated_library.plans),
		"artifact_paths": artifact_paths,
	}
	return results


def _validate_jason_plan_library(args: argparse.Namespace) -> dict[str, Any]:
	domain_file = _require_existing_path(args.domain_file, label="Domain File")
	problem_file = _require_existing_path(args.problem_file, label="Problem File")
	domain = PDDLParser.parse_domain(domain_file)
	domain_key = _canonical_domain_key_for_domain_file(
		domain_file,
		fallback_domain_name=domain.name,
	)
	output_root = _canonical_domain_library_dir(
		library_root=args.library_root,
		domain_name=domain_key,
	)
	canonical_asl = Path(output_root) / "plan_library.asl"
	plan_library_asl = _require_existing_path(
		args.plan_library_asl or str(canonical_asl),
		label="Plan Library ASL File",
	)
	if Path(plan_library_asl).resolve() != canonical_asl.resolve():
		raise ValueError(
			"noncanonical_domain_library: validate-jason-plan-library must run "
			f"the canonical ASL library for domain {domain_key!r}: {canonical_asl}",
		)
	goal_name = str(args.goal_name or "").strip()
	if not goal_name:
		raise ValueError("goal_name is required for Jason validation.")
	output_dir = (
		Path(args.output_dir).expanduser().resolve()
		if args.output_dir
		else PROJECT_ROOT
		/ "artifacts"
		/ "jason_validation"
		/ domain_key
		/ goal_name
	)
	query_record = dict(_existing_artifact_metadata(output_root).get("queries") or {}).get(
		goal_name,
	)
	goal_case = None
	dfa_payload = None
	prediction = None
	reference = None
	runtime_problem = problem_file
	if query_record is not None:
		from domain_level_planning.lifted_ltlf_goal_schema import parse_lifted_ltlf_goal_dataset
		from evaluation.temporal_goal_validation import execution_specification_from_goal_case
		from evaluation.temporal_goal_validation import rewrite_problem_with_neutral_goal
		from temporal_input.query_generation import load_domain_catalog
		from temporal_specification.prediction_validation import validate_prediction_payload
		from temporal_specification.query_semantics import execution_ltlf_formula
		from temporal_specification.translation import bind_goal_template

		goal_case = parse_lifted_ltlf_goal_dataset(query_record["query"]).cases[0]
		if goal_case.goal_name != goal_name or Path(goal_case.problem_file).resolve() != Path(
			problem_file,
		).resolve():
			raise ValueError("Run the query against the problem used for its parameter binding.")
		dfa_payload = query_record["dfa"]
		prediction = execution_specification_from_goal_case(
			goal_case=goal_case, domain_file=domain_file,
		)
		if args.reference_template_file:
			reference_payload = json.loads(
				Path(args.reference_template_file).read_text(encoding="utf-8"),
			)
			reference_payload = reference_payload.get("reference", reference_payload)
			reference = validate_prediction_payload(
				reference_payload, expected_sample=reference_payload,
				catalog=load_domain_catalog(domain_file),
			)
			bind_goal_template(reference, domain_file=domain_file, problem_file=problem_file,
				bindings=goal_case.bindings)
			reference = replace(reference, ltlf_formula=execution_ltlf_formula(reference.ltlf_formula))
		runtime_problem = str(rewrite_problem_with_neutral_goal(
			problem_file, output_dir / "neutral_goal_problem.pddl",
		))
	elif args.reference_template_file:
		raise ValueError("A reference template requires an appended query goal.")
	runner = JasonPlanLibraryRunner(
		timeout_seconds=max(1, int(args.timeout_seconds or 1800)),
		jason_java_stack_size=args.jason_java_stack_size,
		plan_verifier_command=args.plan_verifier_command if goal_case is None else None,
		require_plan_verifier=bool(args.require_plan_verifier) and goal_case is None,
		plan_verifier_timeout_seconds=max(
			1,
			int(args.plan_verifier_timeout_seconds or 1800),
		),
	)
	result = runner.validate(
		domain_file=domain_file,
		problem_file=runtime_problem,
		plan_library_asl=plan_library_asl,
		goal_name=goal_name,
		output_dir=output_dir,
		temporal_dfa_payload=dfa_payload,
	)
	payload = result.to_dict()
	if result.success and goal_case is not None and prediction is not None:
		from evaluation.temporal_goal_validation import validate_execution_trace

		validation = validate_execution_trace(
			reference=reference or prediction, prediction=prediction,
			bindings=goal_case.bindings, domain_file=domain_file, problem_file=problem_file,
			plan_file=result.artifacts["committed_plan_trace"],
			output_dir=output_dir / "query_validation",
			plan_verifier_command=args.plan_verifier_command,
			plan_verifier_timeout_seconds=max(1, int(args.plan_verifier_timeout_seconds)),
		)
		query_validation = validation.to_dict()
		query_validation["reference_accepted"] = (
			query_validation.pop("gold_accepted") if reference is not None else None
		)
		query_validation.pop("gold_accepted", None)
		payload["query_validation"] = query_validation
		payload["success"] = validation.success
		if not validation.success:
			payload["status"] = "query_validation_failed"
			payload["error"] = validation.plan_verifier_error or "Query DFA rejected the action trace."
		Path(result.artifacts["result"]).write_text(
			json.dumps(payload, indent=2) + "\n", encoding="utf-8",
		)
	return payload


def _canonical_domain_library_dir(
	*,
	library_root: str | None,
	domain_name: str,
) -> str:
	root = Path(library_root or DEFAULT_DOMAIN_LIBRARY_ROOT).expanduser().resolve()
	domain_key = _domain_library_key(domain_name)
	canonical_dir = (root / domain_key).resolve()
	return str(canonical_dir)


def _canonical_domain_key_for_domain_file(
	domain_file: str | Path | None,
	*,
	fallback_domain_name: str,
) -> str:
	if domain_file is None:
		return _domain_library_key(fallback_domain_name)
	path = Path(domain_file).expanduser().resolve()
	if path.parent.parent.name == "domains" and path.name == "domain.pddl":
		return _domain_library_key(path.parent.name)
	return _domain_library_key(fallback_domain_name)


def _domain_library_key(domain_name: str) -> str:
	key = str(domain_name or "").strip().lower()
	if not key:
		raise ValueError("Domain name is required for canonical library storage.")
	if "/" in key or "\\" in key or key in {".", ".."}:
		raise ValueError(f"Invalid domain name for library storage: {domain_name!r}")
	return key


def _persist_current_plan_library(
	*,
	plan_library: PlanLibrary,
	output_root: str,
	metadata: dict[str, object],
	allow_overwrite: bool,
) -> dict[str, str]:
	root = Path(output_root).expanduser().resolve()
	root.mkdir(parents=True, exist_ok=True)
	library_json = root / "plan_library.json"
	library_asl = root / "plan_library.asl"
	metadata_file = root / "artifact_metadata.json"
	if not allow_overwrite and (library_json.exists() or library_asl.exists()):
		raise ValueError(
			"domain_library_exists: refusing to overwrite the canonical domain "
			f"library for {plan_library.domain_name!r}. Use --overwrite only when "
			"you intentionally want to rebuild the base atomic library.",
		)
	library_json.write_text(
		json.dumps(plan_library.to_dict(), indent=2, sort_keys=True) + "\n",
		encoding="utf-8",
	)
	library_asl.write_text(render_plan_library_asl(plan_library), encoding="utf-8")
	metadata_file.write_text(
		json.dumps(
			{
				**dict(metadata),
				"canonical_domain_library": True,
				"domain_library_dir": str(root),
				"domain_name": plan_library.domain_name,
				"plan_count": len(plan_library.plans),
				"library_quality": dict(plan_library.metadata.get("library_quality") or {}),
			},
			indent=2,
			sort_keys=True,
			default=str,
		)
		+ "\n",
		encoding="utf-8",
	)
	return {
		"plan_library": str(library_json),
		"plan_library_asl": str(library_asl),
		"artifact_metadata": str(metadata_file),
	}


def _existing_artifact_metadata(output_root: str) -> dict[str, Any]:
	metadata_file = Path(output_root).expanduser().resolve() / "artifact_metadata.json"
	if not metadata_file.exists():
		return {}
	try:
		payload = json.loads(metadata_file.read_text(encoding="utf-8"))
	except json.JSONDecodeError:
		return {}
	return dict(payload) if isinstance(payload, dict) else {}


def _domain_source_metadata(domain_file: str | None) -> dict[str, object]:
	if not domain_file:
		return {}
	source_file = Path(domain_file).resolve().parent / "source.json"
	if not source_file.exists():
		return {}
	try:
		payload = json.loads(source_file.read_text(encoding="utf-8"))
	except json.JSONDecodeError:
		return {"source_file": str(source_file), "source_parse_error": True}
	return dict(payload) if isinstance(payload, dict) else {"source_file": str(source_file)}


def _temporal_append_error_type(error: Exception) -> str:
	message = str(error)
	if "duplicate_temporal_goal" in message:
		return "duplicate_temporal_goal"
	if "singleton-literal transition contract" in message:
		return "dfa_singleton_literal_validation_failed"
	if "Failed to convert LTLf to DFA" in message:
		return "ltlf_to_dfa_execution_failure"
	if "negative_literal_template_not_supported" in message:
		return "negative_literal_template_not_supported"
	if "nonlinear_temporal_goal_not_supported" in message:
		return "nonlinear_temporal_goal_not_supported"
	if "undeclared PDDL predicate" in message:
		return "unsupported_predicate"
	if "wrong arity" in message:
		return "wrong_arity"
	return type(error).__name__


if __name__ == "__main__":
	main()
