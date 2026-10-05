#!/usr/bin/env python3
"""Generate controlled temporal requests from a supplied PDDL problem."""

import argparse
import json
from pathlib import Path

from temporal_input.query_generation import BuildConfig, generate_temporal_queries


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--domain-file", type=Path, required=True)
	parser.add_argument("--problem-file", type=Path, required=True)
	parser.add_argument("--output-dir", type=Path, required=True)
	parser.add_argument("--max-queries", type=int, default=5)
	parser.add_argument("--max-actions-per-state", type=int, default=12)
	parser.add_argument("--max-join-bindings", type=int, default=64)
	args = parser.parse_args()
	if min(args.max_queries, args.max_actions_per_state, args.max_join_bindings) < 1:
		parser.error("Query and exploration limits must be positive.")
	queries = generate_temporal_queries(
		domain_file=args.domain_file, problem_file=args.problem_file,
		max_queries=args.max_queries, config=BuildConfig(
			max_actions_per_state=args.max_actions_per_state,
			max_join_bindings=args.max_join_bindings,
		),
	)
	if not queries:
		parser.error("No supported temporal query was found within the exploration limits.")
	args.output_dir.mkdir(parents=True, exist_ok=True)
	for query in queries:
		output = args.output_dir / f"{query['request']['sample_id']}.json"
		output.write_text(json.dumps(query, indent=2) + "\n", encoding="utf-8")
		print(output)


if __name__ == "__main__":
	main()
