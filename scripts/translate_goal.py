#!/usr/bin/env python3
"""Translate or validate one goal template and optionally bind it to an instance."""

import argparse
import json
from pathlib import Path

from language_model.openai_compatible import create_openai_compatible_client
from temporal_input.query_generation import load_domain_catalog
from temporal_specification.prediction_validation import validate_prediction_payload
from temporal_specification.translation import bind_goal_template, translate_goal
from utils.config import get_config


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--domain-file", type=Path, required=True)
	inputs = parser.add_mutually_exclusive_group(required=True)
	inputs.add_argument("--request-file", type=Path)
	inputs.add_argument("--template-file", type=Path)
	parser.add_argument("--problem-file", type=Path)
	parser.add_argument("--bindings-file", type=Path)
	parser.add_argument("--output", type=Path, required=True)
	args = parser.parse_args()
	if args.bindings_file and not args.problem_file:
		parser.error("--bindings-file requires --problem-file.")
	try:
		catalog = load_domain_catalog(args.domain_file)
		input_file = args.request_file or args.template_file
		query = json.loads(input_file.read_text(encoding="utf-8"))
		if not isinstance(query, dict):
			raise ValueError("The input must be a JSON object.")
		request = query.get("request", query)
		if not isinstance(request, dict):
			raise ValueError("The request must be a JSON object.")
		if args.template_file:
			template = validate_prediction_payload(query, expected_sample=query, catalog=catalog)
		else:
			config = get_config()
			if not config.ltlf_generation_api_key:
				parser.error("Set LANGUAGE_MODEL_API_KEY before requesting translation.")
			client = create_openai_compatible_client(
				api_key=config.ltlf_generation_api_key,
				base_url=config.ltlf_generation_base_url,
				timeout=config.ltlf_generation_timeout,
			)
			template = translate_goal(
				request, catalog=catalog, client=client, model=config.ltlf_generation_model,
				max_retries=config.input_pipeline_max_semantic_retries,
				timeout=config.ltlf_generation_timeout,
				max_tokens=config.ltlf_generation_max_tokens,
			)
		payload = template.to_payload()
		if args.problem_file:
			bindings = json.loads(args.bindings_file.read_text(encoding="utf-8")) \
				if args.bindings_file else query.get("bindings", {})
			if not isinstance(bindings, dict) or not all(
				isinstance(name, str) and isinstance(value, str) for name, value in bindings.items()
			):
				raise ValueError("Bindings must map parameter names to object names.")
			payload = bind_goal_template(
				template, domain_file=args.domain_file, problem_file=args.problem_file,
				bindings=bindings, source_text=str(request.get("source_text", "")),
			)
		args.output.parent.mkdir(parents=True, exist_ok=True)
		args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
		print(args.output)
	except (ValueError, OSError) as error:
		parser.error(str(error))


if __name__ == "__main__":
	main()
