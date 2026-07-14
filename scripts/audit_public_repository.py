#!/usr/bin/env python3
"""Fail closed when a tracked public-release file contains local or transient data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from pathlib import PurePosixPath
import re
import subprocess
import tarfile
from typing import Iterable


_DISALLOWED_COMPONENTS = frozenset(
	{
		".codex",
		".external",
		".idea",
		".pytest_cache",
		".ruff_cache",
		".vscode",
		"__pycache__",
		"build",
		"dist",
		"external",
		"latex_code",
		"node_modules",
		"share",
		"snapshots",
		"tests",
	}
)
_DISALLOWED_FILENAMES = frozenset(
	{
		".DS_Store",
		"AGENTS.md",
		"CLAUDE.md",
		"TO-DO-LIST.md",
		"TODO.md",
		"run_parser_order_full_val_batch.sh",
		"test_ordered_sequence_dfa_fast_path.py",
	}
)
_DISALLOWED_SUFFIXES = (
	".aux",
	".bbl",
	".blg",
	".fdb_latexmk",
	".fls",
	".log",
	".pyc",
	".synctex.gz",
)
_LOCAL_USER_PATH = re.compile(
	r"/(?:Users|home)/(?!example(?:/|$)|user(?:/|$)|username(?:/|$))[\w.-]+(?=[/'\"\s]|$)",
)
_WINDOWS_USER_PATH = re.compile(r"(?i)[a-z]:[\\/](?:users|documents and settings)[\\/]")
_DEVELOPMENT_REPOSITORY_NAME = "llm-bdi-" + "pipeline-dev"
_LOCAL_ENDPOINT = re.compile(
	"(?:" + "local" + "host|" + "127" + r"\.0\.0\.1|0\.0\.0\.0)(?::\d+)?",
	re.IGNORECASE,
)
_FILE_URI = re.compile("file" + ":///", re.IGNORECASE)
_SECRET_PATTERNS = {
	"openai_key": re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
	"github_token": re.compile(r"(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{30,}"),
	"github_pat": re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
	"aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
	"private_key": re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
}


@dataclass(frozen=True)
class AuditFinding:
	"""One portable-release violation without exposing matched content."""

	path: str
	category: str


@dataclass(frozen=True)
class AuditReport:
	"""The complete scan result for every tracked file and archive member."""

	archive_member_count: int
	findings: tuple[AuditFinding, ...]
	tracked_file_count: int


def audit_public_repository(project_root: str | Path) -> AuditReport:
	"""Audit every Git-tracked file below ``project_root``."""

	root = Path(project_root).expanduser().resolve()
	completed = subprocess.run(
		("git", "-C", str(root), "ls-files", "-z"),
		check=True,
		capture_output=True,
	)
	tracked = tuple(
		Path(item.decode("utf-8")) for item in completed.stdout.split(b"\0") if item
	)
	return audit_paths(root, tracked)


def audit_paths(project_root: str | Path, paths: Iterable[Path]) -> AuditReport:
	"""Audit an explicit relative-path collection for production and tests."""

	root = Path(project_root).expanduser().resolve()
	findings: list[AuditFinding] = []
	archive_member_count = 0
	tracked = tuple(sorted((Path(path) for path in paths), key=lambda path: str(path)))
	for relative_path in tracked:
		relative = relative_path.as_posix()
		absolute = root / relative_path
		if not absolute.is_file():
			findings.append(AuditFinding(relative, "missing_tracked_file"))
			continue
		findings.extend(_path_findings(relative_path))
		findings.extend(_content_findings(relative, absolute.read_bytes()))
		if absolute.name.endswith(".tar.gz"):
			member_count, archive_findings = _archive_findings(relative, absolute)
			archive_member_count += member_count
			findings.extend(archive_findings)
	return AuditReport(
		archive_member_count=archive_member_count,
		findings=tuple(sorted(set(findings), key=lambda item: (item.path, item.category))),
		tracked_file_count=len(tracked),
	)


def _path_findings(path: Path) -> tuple[AuditFinding, ...]:
	relative = path.as_posix()
	findings: list[AuditFinding] = []
	if any(part in _DISALLOWED_COMPONENTS for part in path.parts):
		findings.append(AuditFinding(relative, "development_directory"))
	if path.name in _DISALLOWED_FILENAMES:
		findings.append(AuditFinding(relative, "development_filename"))
	if path.name.endswith(_DISALLOWED_SUFFIXES):
		findings.append(AuditFinding(relative, "generated_file"))
	if path.name.startswith("generate_aaai_"):
		findings.append(AuditFinding(relative, "conference_specific_generator"))
	return tuple(findings)


def _content_findings(relative: str, data: bytes) -> tuple[AuditFinding, ...]:
	text = data.decode("utf-8", errors="ignore")
	findings: list[AuditFinding] = []
	if _LOCAL_USER_PATH.search(text):
		findings.append(AuditFinding(relative, "machine_local_user_path"))
	if _WINDOWS_USER_PATH.search(text):
		findings.append(AuditFinding(relative, "windows_user_path"))
	if _DEVELOPMENT_REPOSITORY_NAME in text:
		findings.append(AuditFinding(relative, "development_repository_path"))
	if _LOCAL_ENDPOINT.search(text):
		findings.append(AuditFinding(relative, "local_service_endpoint"))
	if _FILE_URI.search(text):
		findings.append(AuditFinding(relative, "file_uri"))
	for category, pattern in _SECRET_PATTERNS.items():
		if pattern.search(text):
			findings.append(AuditFinding(relative, category))
	return tuple(findings)


def _archive_findings(relative: str, archive: Path) -> tuple[int, tuple[AuditFinding, ...]]:
	findings: list[AuditFinding] = []
	member_count = 0
	with tarfile.open(archive, mode="r:gz") as bundle:
		for member in bundle.getmembers():
			member_count += 1
			member_path = PurePosixPath(member.name)
			member_relative = f"{relative}:{member.name}"
			if member_path.is_absolute() or ".." in member_path.parts:
				findings.append(AuditFinding(member_relative, "unsafe_archive_member"))
				continue
			if member.issym() or member.islnk():
				findings.append(AuditFinding(member_relative, "archive_link"))
				continue
			if _is_platform_metadata(member_path):
				findings.append(AuditFinding(member_relative, "archive_platform_metadata"))
				continue
			if _is_transient_validation_diagnostic(member_path):
				findings.append(
					AuditFinding(member_relative, "archive_transient_validation_diagnostic"),
				)
				continue
			if member.isfile():
				extracted = bundle.extractfile(member)
				if extracted is None:
					findings.append(AuditFinding(member_relative, "unreadable_archive_member"))
					continue
				findings.extend(_content_findings(member_relative, extracted.read()))
	return member_count, tuple(findings)


def _is_platform_metadata(path: PurePosixPath) -> bool:
	return any(
		part == "__MACOSX" or part == ".DS_Store" or part.startswith("._")
		for part in path.parts
	)


def _is_transient_validation_diagnostic(path: PurePosixPath) -> bool:
	return any(
		part.startswith("goal_validation_infra_error_") for part in path.parts
	)


def main() -> int:
	project_root = Path(__file__).resolve().parents[1]
	report = audit_public_repository(project_root)
	if report.findings:
		for finding in report.findings:
			print(f"[fail] {finding.category} path={finding.path}")
		return 1
	print(
		"[ok] public repository audit "
		f"tracked_files={report.tracked_file_count} "
		f"archive_members={report.archive_member_count}",
	)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
