#!/usr/bin/env python3
"""Materialize the selected achievement-goal benchmark corpus."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import subprocess
from fnmatch import fnmatch
from typing import NamedTuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOMAINS_ROOT = PROJECT_ROOT / "src" / "domains"
STRUCTURAL_TRAIN_RATIO = 1 / 4
DEPOTS_SMALL_INSTANCE_TRAIN_RATIO = 1 / 2


class SourceSpec(NamedTuple):
	source_id: str
	name: str
	url: str
	local_root: Path
	commit: str


class DomainSpec(NamedTuple):
	domain_id: str
	source_id: str
	source_path: str
	problem_globs: tuple[str, ...]
	source_domain_file: str = "domain.pddl"
	split_strategy: str = "ratio"
	train_ratio: float = 2 / 3
	split_policy: str = "floor(2/3 * instance_count) train, remaining test"
	test_source_path: str | None = None
	test_problem_globs: tuple[str, ...] = ()


SOURCES: dict[str, SourceSpec] = {
	"pddl_instances": SourceSpec(
		"pddl_instances",
		"potassco/pddl-instances",
		"https://github.com/potassco/pddl-instances",
		PROJECT_ROOT / ".external" / "benchmark-sources" / "pddl-instances",
		"cf19edf7c53d1540ddbb396c642595e0926ee552",
	),
	"moose_dataset": SourceSpec(
		"moose_dataset",
		"DillonZChen/moose-dataset",
		"https://github.com/DillonZChen/moose-dataset",
		PROJECT_ROOT / ".external" / "moose-dataset",
		"e00970516154e9042b783a4613a1ed7286c9beee",
	),
	"kr2025_policies": SourceSpec(
		"kr2025_policies",
		"bonetblai/learner-policies-from-examples",
		"https://github.com/bonetblai/learner-policies-from-examples",
		PROJECT_ROOT
		/ ".external"
		/ "gp-backends"
		/ "learner-policies-from-examples",
		"9991926f7655c4b6c8dc2f0404123639e42056f2",
	),
	"d2l": SourceSpec(
		"d2l",
		"rleap-project/d2l",
		"https://github.com/rleap-project/d2l",
		PROJECT_ROOT / ".external" / "gp-backends" / "d2l",
		"0620e169c894d79b3c84f435dba1462996f7c270",
	),
}


def main() -> None:
	"""Fetch optional benchmark inputs without replacing existing domains."""

	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--domains", nargs="+", help="Fetch only these domain names.")
	args = parser.parse_args()
	specs = _domain_specs()
	if args.domains:
		known = {spec.domain_id for spec in specs}
		unknown = set(args.domains) - known
		if unknown:
			parser.error(f"Unknown domains: {sorted(unknown)}")
		specs = tuple(spec for spec in specs if spec.domain_id in args.domains)
	_validate_source(specs)
	for spec in specs:
		if (DOMAINS_ROOT / spec.domain_id).exists():
			parser.error(f"Destination already exists: {DOMAINS_ROOT / spec.domain_id}")
	for spec in specs:
		_materialize_domain(spec)
	print(f"materialized {len(specs)} selected achievement benchmark domains")


def _validate_source(specs: tuple[DomainSpec, ...]) -> None:
	used_source_ids = {spec.source_id for spec in specs}
	for source in SOURCES.values():
		if source.source_id not in used_source_ids:
			continue
		if not source.local_root.exists():
			raise FileNotFoundError(
				f"missing benchmark source {source.local_root}; clone {source.name} first",
			)
		head = subprocess.check_output(
			("git", "-C", str(source.local_root), "rev-parse", "HEAD"),
			text=True,
		).strip()
		if head != source.commit:
			raise RuntimeError(
				f"unexpected {source.name} commit {head}; expected {source.commit}",
			)


def _domain_specs() -> tuple[DomainSpec, ...]:
	moose_domains = (
		"ferry", "gripper", "logistics", "miconic", "transport", "barman",
		"rovers", "satellite", "numeric-ferry", "numeric-miconic",
		"numeric-minecraft", "numeric-transport",
	)
	return (
		*(
			DomainSpec(
				name, "moose_dataset", name, ("training/*.pddl", "testing/*.pddl"),
				split_strategy="source_directories",
				split_policy="training/ as train and testing/ as test",
			)
			for name in moose_domains
		),
		*(
			DomainSpec(
				f"blocksworld-{goal}", "kr2025_policies",
				f"learning/benchmarks/tractable/blocks_4_{goal}_no_constants",
				("training/easy/*.pddl",),
				split_strategy="paired_source_directories",
				split_policy="official no-constants training/testing split",
				test_source_path=f"testing/benchmarks/blocks_4_{goal}_no_constants",
				test_problem_globs=("*.pddl",),
			)
			for goal in ("clear", "on")
		),
		DomainSpec(
			"blocksworld-tower", "pddl_instances",
			"ipc-2000/domains/blocks-strips-typed", ("instances/*.pddl",),
			train_ratio=STRUCTURAL_TRAIN_RATIO,
			split_policy="floor(1/4 * instance_count) train, remaining test",
		),
		DomainSpec(
			"depots", "d2l", "domains/depot", ("p*.pddl",),
			train_ratio=DEPOTS_SMALL_INSTANCE_TRAIN_RATIO,
			split_policy="floor(1/2 * instance_count) train, remaining test",
		),
	)


def _materialize_domain(spec: DomainSpec) -> None:
	domain_root = DOMAINS_ROOT / spec.domain_id
	train_root = domain_root / "train"
	test_root = domain_root / "test"
	train_root.mkdir(parents=True)
	test_root.mkdir(parents=True)
	problem_paths = _source_problem_paths(spec)
	if not problem_paths:
		raise RuntimeError(
			f"{spec.domain_id} has no benchmark instances in {spec.source_path}",
		)
	domain_file = domain_root / "domain.pddl"
	_copy_source_file(spec, spec.source_domain_file, domain_file)
	expected_domain_name = _declared_domain_name(domain_file.read_text(encoding="utf-8"))
	train_paths, test_paths = _split_problem_paths(spec, problem_paths)
	normalized_domain_reference_count = 0
	for source_problem in train_paths:
		normalized_domain_reference_count += _copy_problem_source_file(
			spec,
			source_problem,
			train_root / Path(source_problem).name,
			expected_domain_name=expected_domain_name,
		)
	for source_problem in test_paths:
		normalized_domain_reference_count += _copy_problem_source_file(
			spec,
			source_problem,
			test_root / Path(source_problem).name,
			expected_domain_name=expected_domain_name,
		)
	source = SOURCES[spec.source_id]
	source_record = {
		"source": source.name,
		"source_id": source.source_id,
		"source_url": source.url,
		"source_commit": source.commit,
		"source_path": spec.source_path,
		"test_source_path": spec.test_source_path,
		"source_domain_file": f"{spec.source_path}/{spec.source_domain_file}",
		"source_problem_globs": list(spec.problem_globs),
		"test_source_problem_globs": list(spec.test_problem_globs),
		"instance_count": len(problem_paths),
		"train_count": len(train_paths),
		"test_count": len(test_paths),
		"split_policy": spec.split_policy,
		"normalized_problem_domain_reference_count": normalized_domain_reference_count,
	}
	(domain_root / "source.json").write_text(
		json.dumps(source_record, indent=2, sort_keys=True) + "\n",
		encoding="utf-8",
	)


def _split_problem_paths(
	spec: DomainSpec,
	problem_paths: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
	if spec.split_strategy == "source_directories":
		train_paths = tuple(path for path in problem_paths if path.startswith("training/"))
		test_paths = tuple(path for path in problem_paths if path.startswith("testing/"))
		if not train_paths or not test_paths:
			raise RuntimeError(
				f"{spec.domain_id} expects source training/ and testing/ directories",
			)
		return train_paths, test_paths
	if spec.split_strategy == "paired_source_directories":
		train_paths = tuple(path for path in problem_paths if path.startswith("training/"))
		test_paths = tuple(path for path in problem_paths if path.startswith("testing/"))
		if not train_paths or not test_paths:
			raise RuntimeError(
				f"{spec.domain_id} expects paired source training/ and testing/ data",
			)
		return train_paths, test_paths
	if spec.split_strategy == "ratio":
		split = math.floor(len(problem_paths) * spec.train_ratio)
		return problem_paths[:split], problem_paths[split:]
	raise ValueError(f"unknown split strategy {spec.split_strategy!r}")


def _source_problem_paths(spec: DomainSpec) -> tuple[str, ...]:
	if spec.split_strategy == "paired_source_directories":
		if spec.test_source_path is None:
			raise RuntimeError(f"{spec.domain_id} is missing test_source_path")
		train_paths = _source_problem_paths_under(
			spec.source_id,
			spec.source_path,
			spec.problem_globs,
			spec.source_domain_file,
		)
		test_paths = _source_problem_paths_under(
			spec.source_id,
			spec.test_source_path,
			spec.test_problem_globs,
			spec.source_domain_file,
		)
		return tuple(
			str(Path("training") / path)
			if not str(path).startswith("training/")
			else str(path)
			for path in train_paths
		) + tuple(str(Path("testing") / path) for path in test_paths)
	return _source_problem_paths_under(
		spec.source_id,
		spec.source_path,
		spec.problem_globs,
		spec.source_domain_file,
	)


def _source_problem_paths_under(
	source_id: str,
	source_path: str,
	problem_globs: tuple[str, ...],
	source_domain_file: str,
) -> tuple[str, ...]:
	output = subprocess.check_output(
		(
			"git",
			"-C",
			str(SOURCES[source_id].local_root),
			"ls-tree",
			"-r",
			"--name-only",
			f"HEAD:{source_path}",
		),
		text=True,
	)
	paths: list[Path] = []
	source_paths = tuple(
		line
		for line in output.splitlines()
		if line.endswith(".pddl") and Path(line).name != source_domain_file
	)
	for glob_text in problem_globs:
		paths.extend(
			Path(path)
			for path in source_paths
			if fnmatch(path, glob_text)
		)
	return tuple(str(path) for path in sorted(paths, key=_instance_sort_key))


def _instance_sort_key(path: str | Path) -> tuple[tuple[int, ...], str]:
	text = str(path)
	numbers = tuple(int(item) for item in re.findall(r"\d+", text))
	return (numbers or (10**9,), text)


def _copy_source_file(spec: DomainSpec, relative_path: str, target_path: Path) -> None:
	content = _read_source_file(spec, relative_path)
	_write_pddl_snapshot(content, target_path)


def _copy_problem_source_file(
	spec: DomainSpec,
	relative_path: str,
	target_path: Path,
	*,
	expected_domain_name: str,
) -> int:
	content = _read_source_file(spec, relative_path)
	normalized, changed = _normalize_problem_domain_reference(
		content,
		expected_domain_name=expected_domain_name,
	)
	_write_pddl_snapshot(normalized, target_path)
	return int(changed)


def _normalize_problem_domain_reference(
	content: bytes,
	*,
	expected_domain_name: str,
) -> tuple[bytes, bool]:
	"""Make a materialized problem reference its actual materialized domain schema."""

	name = str(expected_domain_name or "").strip().lower()
	if not name or re.fullmatch(r"[^\s()]+", name) is None:
		raise ValueError(f"Invalid materialized PDDL domain name {expected_domain_name!r}.")
	text = content.decode("utf-8")
	pattern = re.compile(r"(\(\s*:domain\s+)([^\s()]+)(\s*\))", flags=re.IGNORECASE)
	matches = tuple(pattern.finditer(text))
	if len(matches) != 1:
		raise ValueError(
			"A materialized PDDL problem must contain exactly one :domain reference; "
			f"found {len(matches)}.",
		)
	current_name = matches[0].group(2)
	if current_name.lower() == name:
		return content, False
	normalized = pattern.sub(lambda match: f"{match.group(1)}{name}{match.group(3)}", text)
	return normalized.encode("utf-8"), True


def _declared_domain_name(content: str) -> str:
	matches = tuple(
		re.finditer(r"\(\s*define\s*\(\s*domain\s+([^\s()]+)\s*\)", content, re.IGNORECASE),
	)
	if len(matches) != 1:
		raise ValueError(f"Expected exactly one PDDL domain declaration; found {len(matches)}.")
	return matches[0].group(1).lower()


def _read_source_file(spec: DomainSpec, relative_path: str) -> bytes:
	source = SOURCES[spec.source_id]
	source_path = spec.source_path
	source_relative_path = relative_path
	if relative_path.startswith("testing/") and spec.test_source_path is not None:
		source_path = spec.test_source_path
		source_relative_path = relative_path.removeprefix("testing/")
	full_path = f"{source_path}/{source_relative_path}"
	return subprocess.check_output(
		(
			"git",
			"-C",
			str(source.local_root),
			"show",
			f"HEAD:{full_path}",
		),
	)


def _write_pddl_snapshot(content: bytes, target_path: Path) -> None:
	text = content.decode("utf-8")
	lines = [
		line.replace("\t", "  ").rstrip()
		for line in text.replace("\r\n", "\n").split("\n")
	]
	target_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
	main()
