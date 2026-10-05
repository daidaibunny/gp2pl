#!/usr/bin/env python3
"""Generate singleton-goal policy evidence with a resource-limited MOOSE runtime."""

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


def train_moose(
	*,
	domain_file: Path,
	training_dir: Path,
	model_file: Path,
	moose_command: str,
	seed: int = 0,
	workers: int = 1,
	permutations: int = 3,
	max_rss_gb: float = 16,
	timeout_seconds: float = 1800,
) -> Path:
	"""Train the provider and dump its readable policy, guarding both processes."""
	if not domain_file.is_file() or not training_dir.is_dir():
		raise ValueError("Provide a domain file and a directory of training problems.")
	if not any(training_dir.glob("*.pddl")):
		raise ValueError("The training directory contains no PDDL problems.")
	if not 0 < max_rss_gb <= 16 or timeout_seconds <= 0 or min(workers, permutations) < 1:
		raise ValueError("Use positive limits with a memory ceiling of at most 16 GiB.")
	prefix = shlex.split(moose_command)
	if not prefix:
		raise ValueError("Specify the MOOSE runtime command.")
	model = model_file.resolve()
	readable = model.with_suffix(model.suffix + ".readable")
	if model.exists() or readable.exists():
		raise FileExistsError(f"Choose an unused model path: {model}.")
	model.parent.mkdir(parents=True, exist_ok=True)
	guard = [
		sys.executable, str(Path(__file__).with_name("resource_guard.py")),
		"--max-rss-gb", str(max_rss_gb), "--timeout-seconds", str(timeout_seconds),
		"--label", "MOOSE", "--",
	]
	print(f"Training MOOSE: seed={seed}, workers={workers}, model={model}", flush=True)
	subprocess.run([
		*guard, *prefix, "train", str(domain_file.resolve()), str(training_dir.resolve()),
		"--save-file", str(model), "--random-seed", str(seed),
		"--num_workers", str(workers), "--num-permutations", str(permutations),
		"--goal-max-size", "1", "--num-training", "-1", "--num-validation", "-1",
	], check=True)
	if not model.is_file():
		raise RuntimeError("MOOSE exited without saving its model.")
	print("Dumping readable policy", flush=True)
	temporary = readable.with_suffix(readable.suffix + ".tmp")
	with temporary.open("w", encoding="utf-8") as output:
		subprocess.run(
			[*guard, *prefix, "policy", str(model), "--dump-policy"],
			stdout=output, check=True,
		)
	if not temporary.stat().st_size:
		raise RuntimeError("MOOSE returned an empty readable policy.")
	temporary.replace(readable)
	return readable


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--domain-file", type=Path, required=True)
	parser.add_argument("--training-dir", type=Path, required=True)
	parser.add_argument("--model-file", type=Path, required=True)
	parser.add_argument("--moose-command", required=True,
		help="Runtime prefix, for example 'apptainer run .external/moose/moose.sif'.")
	parser.add_argument("--seed", type=int, default=0)
	parser.add_argument("--workers", type=int, default=1)
	parser.add_argument("--permutations", type=int, default=3)
	parser.add_argument("--max-rss-gb", type=float, default=16)
	parser.add_argument("--timeout-seconds", type=float, default=1800)
	args = parser.parse_args()
	try:
		print(train_moose(**vars(args)))
	except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as error:
		parser.error(str(error))


if __name__ == "__main__":
	main()
