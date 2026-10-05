"""Translate one controlled-language request with validated correction retries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from language_model.openai_compatible import create_openai_compatible_json_completion
from temporal_input.query_generation import load_domain_catalog
from utils.pddl_parser import PDDLParser

from .errors import NON_RETRYABLE_ERROR_CODES, TranslationErrorCode, build_retry_feedback
from .prediction_validation import (
	PredictionValidationError,
	ValidatedLTLfPrediction,
	validate_prediction_payload,
)
from .prompts import (
	build_lifted_ltlf_system_prompt,
	build_lifted_ltlf_user_prompt,
	build_retry_user_message,
)
from .query_semantics import classify_ltlf_query


def translate_goal(
	request: Mapping[str, Any],
	*,
	catalog: Mapping[str, Any],
	client: Any,
	model: str,
	max_retries: int = 3,
	timeout: float = 1000,
	max_tokens: int = 12000,
) -> ValidatedLTLfPrediction:
	"""Translate without exposing bindings, reference formulas, or action traces.

	Only schema and semantic errors receive correction retries. Transport errors
	propagate to the caller without consuming further model calls here.
	"""
	if max_retries < 0 or timeout <= 0 or max_tokens < 1 or not model.strip():
		raise ValueError("Specify a model, positive limits, and non-negative retries.")
	messages = [
		{"role": "system", "content": build_lifted_ltlf_system_prompt(catalog)},
		{"role": "user", "content": build_lifted_ltlf_user_prompt(request)},
	]
	for attempt in range(max_retries + 1):
		response = create_openai_compatible_json_completion(
			client, model=model, messages=messages, timeout=timeout,
			max_tokens=max_tokens, stream=True, temperature=0.0,
		)
		raw = str(response.choices[0].message.content or "")
		payload: object = None
		try:
			try:
				payload = json.loads(raw)
			except json.JSONDecodeError as error:
				raise PredictionValidationError(
					TranslationErrorCode.E_JSON_FORMAT, f"Invalid JSON: {error.msg}.",
				) from error
			if not isinstance(payload, Mapping):
				raise PredictionValidationError(
					TranslationErrorCode.E_JSON_FORMAT, "The response must be a JSON object.",
				)
			return validate_prediction_payload(
				payload, expected_sample=request, catalog=catalog,
			)
		except PredictionValidationError as error:
			if error.code in NON_RETRYABLE_ERROR_CODES or attempt == max_retries:
				raise
			previous = str(payload.get("ltlf_formula") or "") if isinstance(payload, Mapping) else ""
			feedback = build_retry_feedback(
				previous_ltlf=previous, error_code=error.code,
				error_detail=str(error), attempt=attempt + 2,
			)
			messages.extend([
				{"role": "assistant", "content": raw},
				{"role": "user", "content": build_retry_user_message(feedback)},
			])
	raise AssertionError("Translation retry loop must return or raise.")


def bind_goal_template(
	template: ValidatedLTLfPrediction,
	*,
	domain_file: str | Path,
	problem_file: str | Path,
	bindings: Mapping[str, str],
	source_text: str = "",
) -> dict[str, object]:
	"""Check an invocation's objects and types, then produce compiler input JSON."""
	catalog = load_domain_catalog(domain_file)
	validate_prediction_payload(template.to_payload(), expected_sample={
		"sample_id": template.sample_id,
		"declared_parameters": template.to_payload()["declared_parameters"],
		"constraints": template.to_payload()["constraints"],
	}, catalog=catalog)
	problem = PDDLParser.parse_problem(problem_file)
	if problem.domain_name != catalog["domain"]:
		raise ValueError("The problem and goal template must use the same domain.")
	if set(bindings) != {name for name, _ in template.declared_parameters}:
		raise ValueError("Provide exactly one binding for every declared parameter.")
	object_types = {
		**{str(item["name"]): str(item["pddl_type"]) for item in catalog["constants"]},
		**{name: problem.object_types.get(name, "object") for name in problem.objects},
	}
	parents = catalog["type_parents"]
	for name, expected_type in template.declared_parameters:
		actual_type = object_types.get(bindings[name])
		seen: set[str] = set()
		while actual_type and actual_type not in seen and actual_type != expected_type:
			seen.add(actual_type)
			actual_type = parents.get(actual_type, "object") if actual_type != "object" else None
		if actual_type != expected_type:
			raise ValueError(f"Binding {name}={bindings[name]!r} is not a {expected_type} object.")
	for encoded in template.constraints:
		constraint = json.loads(encoded)
		left = bindings.get(constraint["left"], constraint["left"])
		right = bindings.get(constraint["right"], constraint["right"])
		if left == right:
			raise ValueError(f"Binding violates constraint {constraint}.")
	atoms = [
		{
			"symbol": atom.symbol, "predicate": atom.name,
			"args": [*atom.args, str(atom.value)]
			if atom.kind == "numeric_equality" else list(atom.args),
		}
		for atom in template.atoms
	]
	payload = {
		"schema_version": 1,
		"goal_specification_kind": classify_ltlf_query(template.ltlf_formula).value,
		"temporal_logic": "LTLf", "domain": catalog["domain"],
		"cases": {template.sample_id: {
			"goal_name": f"g_{template.sample_id}",
			"problem_file": str(Path(problem_file).resolve()),
			"source_text": source_text, "ltlf_formula": template.ltlf_formula,
			"atoms": atoms, "bindings": dict(bindings),
			"atom_vocabulary": "pddl_fluents", "status": "supported",
		}},
	}
	from domain_level_planning.lifted_ltlf_goal_schema import parse_lifted_ltlf_goal_dataset

	parse_lifted_ltlf_goal_dataset(payload)
	return payload
