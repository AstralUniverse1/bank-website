from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from review_contract import ChangedFile, FileStatus

DiffMode = Literal["local", "refs"]

GIT_COMMAND_TIMEOUT_SECONDS = 20
# These caps are checked after subprocess output is captured. They are useful MVP
# guardrails, not streaming memory limits.
MAX_GIT_STDOUT_BYTES = 1_000_000
MAX_GIT_STDERR_BYTES = 20_000

DIFF_FLAGS = [
    "--no-color",
    "--no-ext-diff",
    "--find-renames",
    "--find-copies",
]

STATUS_MAP: dict[str, FileStatus] = {
    "A": "added",
    "M": "modified",
    "D": "deleted",
    "R": "renamed",
    "C": "copied",
    "T": "type_changed",
    "U": "unmerged",
}


class GitDiffError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitDiffResult:
    changed_files: list[ChangedFile]
    diff: str
    base_ref: str | None
    head_ref: str | None
    mode: DiffMode


def get_local_working_tree_diff(repo_path: str | Path = ".") -> GitDiffResult:
    repo = Path(repo_path)
    _ensure_git_repo(repo)

    tracked_diff = _git_capture(
        repo,
        ["git", "diff", *DIFF_FLAGS, "--binary", "HEAD", "--"],
    )
    staged_status = parse_name_status_z(
        _git_capture_bytes(
            repo,
            ["git", "diff", *DIFF_FLAGS, "--name-status", "-z", "--cached", "HEAD", "--"],
        )
    )
    unstaged_status = parse_name_status_z(
        _git_capture_bytes(
            repo,
            ["git", "diff", *DIFF_FLAGS, "--name-status", "-z", "--",],
        )
    )
    untracked_status = _untracked_files(repo)

    files = _merge_changed_files(
        [*staged_status, *unstaged_status, *untracked_status],
        _binary_paths_from_diff(tracked_diff),
    )
    return GitDiffResult(
        changed_files=files,
        diff=tracked_diff,
        base_ref="HEAD",
        head_ref=None,
        mode="local",
    )


def get_ref_diff(
    base_ref: str,
    head_ref: str,
    repo_path: str | Path = ".",
) -> GitDiffResult:
    repo = Path(repo_path)
    _ensure_git_repo(repo)
    _verify_ref(repo, base_ref, "base_ref")
    _verify_ref(repo, head_ref, "head_ref")

    revision_range = f"{base_ref}...{head_ref}"
    diff = _git_capture(
        repo,
        ["git", "diff", *DIFF_FLAGS, "--binary", revision_range, "--"],
    )
    files = parse_name_status_z(
        _git_capture_bytes(
            repo,
            ["git", "diff", *DIFF_FLAGS, "--name-status", "-z", revision_range, "--"],
        )
    )
    return GitDiffResult(
        changed_files=_merge_changed_files(files, _binary_paths_from_diff(diff)),
        diff=diff,
        base_ref=base_ref,
        head_ref=head_ref,
        mode="refs",
    )


def changed_file_paths(result: GitDiffResult) -> list[str]:
    return [changed_file.path for changed_file in result.changed_files]


def parse_name_status_z(output: bytes) -> list[ChangedFile]:
    tokens = _split_z(output)
    files = []
    index = 0

    while index < len(tokens):
        status_token = tokens[index]
        index += 1
        if not status_token:
            continue

        status_code = status_token[:1]
        status = STATUS_MAP.get(status_code, "unknown")
        if status in {"renamed", "copied"}:
            if index + 1 >= len(tokens):
                raise GitDiffError("git name-status output ended during rename/copy record")
            old_path = tokens[index]
            path = tokens[index + 1]
            index += 2
            files.append(ChangedFile(path=path, status=status, old_path=old_path))
            continue

        if index >= len(tokens):
            raise GitDiffError("git name-status output ended during file record")
        path = tokens[index]
        index += 1
        files.append(ChangedFile(path=path, status=status))

    return files


def _git_capture(repo_path: Path, args: list[str]) -> str:
    return _decode(_git_capture_bytes(repo_path, args))


def _git_capture_bytes(repo_path: Path, args: list[str]) -> bytes:
    try:
        result = subprocess.run(
            args,
            cwd=repo_path,
            shell=False,
            capture_output=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitDiffError(f"git command timed out: {_command_name(args)}") from exc
    except OSError as exc:
        raise GitDiffError(f"failed to run git command: {_command_name(args)}") from exc

    if len(result.stdout) > MAX_GIT_STDOUT_BYTES:
        raise GitDiffError(
            f"git stdout exceeded {MAX_GIT_STDOUT_BYTES} bytes for {_command_name(args)}"
        )
    if len(result.stderr) > MAX_GIT_STDERR_BYTES:
        raise GitDiffError(
            f"git stderr exceeded {MAX_GIT_STDERR_BYTES} bytes for {_command_name(args)}"
        )
    if result.returncode != 0:
        stderr = _decode(result.stderr).strip()
        detail = f": {stderr}" if stderr else ""
        raise GitDiffError(f"git command failed: {_command_name(args)}{detail}")

    return result.stdout


def _ensure_git_repo(repo_path: Path) -> None:
    try:
        _git_capture_bytes(repo_path, ["git", "rev-parse", "--is-inside-work-tree"])
    except GitDiffError as exc:
        raise GitDiffError(f"not a git repository: {repo_path}") from exc


def _verify_ref(repo_path: Path, ref: str, label: str) -> None:
    try:
        _git_capture_bytes(repo_path, ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"])
    except GitDiffError as exc:
        raise GitDiffError(f"invalid {label}: {ref}") from exc


def _untracked_files(repo_path: Path) -> list[ChangedFile]:
    output = _git_capture_bytes(
        repo_path,
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
    )
    return [
        ChangedFile(path=path, status="unknown")
        for path in _split_z(output)
        if path
    ]


def _merge_changed_files(
    files: list[ChangedFile],
    binary_paths: set[str],
) -> list[ChangedFile]:
    merged: dict[str, ChangedFile] = {}
    for changed_file in files:
        existing = merged.get(changed_file.path)
        is_binary = changed_file.is_binary or changed_file.path in binary_paths
        if existing is None:
            merged[changed_file.path] = ChangedFile(
                path=changed_file.path,
                status=changed_file.status,
                old_path=changed_file.old_path,
                is_binary=is_binary,
            )
            continue

        status = existing.status
        if status == "unknown" and changed_file.status != "unknown":
            status = changed_file.status
        old_path = existing.old_path or changed_file.old_path
        merged[changed_file.path] = ChangedFile(
            path=changed_file.path,
            status=status,
            old_path=old_path,
            is_binary=existing.is_binary or is_binary,
        )
    return list(merged.values())


def _binary_paths_from_diff(diff: str) -> set[str]:
    binary_paths = set()
    current_path: str | None = None

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            current_path = _path_from_diff_header(line)
            continue
        if current_path and (
            line.startswith("Binary files ")
            or line == "GIT binary patch"
            or line.startswith("literal ")
            or line.startswith("delta ")
        ):
            binary_paths.add(current_path)

    return binary_paths


def _path_from_diff_header(line: str) -> str | None:
    parts = line.split(" ")
    if len(parts) < 4:
        return None
    b_path = parts[3]
    if b_path == "/dev/null":
        return None
    if b_path.startswith("b/"):
        return b_path[2:]
    return b_path


def _split_z(output: bytes) -> list[str]:
    if not output:
        return []
    return [
        _decode(part)
        for part in output.rstrip(b"\0").split(b"\0")
    ]


def _decode(value: bytes) -> str:
    try:
        return value.decode("utf-8", errors="surrogateescape")
    except UnicodeError as exc:
        raise GitDiffError("failed to decode git output") from exc


def _command_name(args: list[str]) -> str:
    return " ".join(args[:4])
