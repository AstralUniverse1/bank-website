from __future__ import annotations

import json
import re

from config import MAX_INPUT_CHARS
from review_contract import (
    ChangedFile,
    DiffStats,
    FileCategory,
    FileStatus,
    ReviewHints,
    SanitizedChangedFile,
    SanitizedReviewInput,
)

DEFAULT_REVIEW_RULES = [
    "Use only the provided sanitized input.",
    "Do not assume hidden files or runtime state.",
    "Do not request secrets.",
    "Prioritize missing tests, edge cases, validation issues, auth risks, and regressions.",
]

PROJECT_RULES = [
    "AI receives sanitized input only.",
    "AI has no repo, shell, filesystem, network, or tool access.",
    "No autonomous retries or loops.",
    "GitHub behavior is comment-only.",
    "pull_request_target must only run trusted base-branch code.",
    "PR head may be used only as diff data.",
    "Do not expose raw files, raw secrets, or unsanitized diff text.",
]

SECRET_PATTERNS = [
    re.compile(r"\b(sk-[A-Za-z0-9_-]{20,})\b"),
    re.compile(r"\b(gh[pousr]_[A-Za-z0-9_]{20,})\b"),
    re.compile(
        r'(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*[\'"]?[^\'"\s]+'
    ),
]

CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SAFE_FILE_PATH = re.compile(r"^[A-Za-z0-9._/\-]+$")
SECURITY_PATH_WORDS = {
    "auth",
    "authentication",
    "authorization",
    "crypto",
    "jwt",
    "oauth",
    "password",
    "permission",
    "permissions",
    "secret",
    "security",
    "token",
}
SOURCE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".scala",
    ".sh",
    ".ts",
    ".tsx",
}
DOC_EXTENSIONS = {".adoc", ".md", ".rst", ".txt"}
CONFIG_FILENAMES = {
    ".env.example",
    ".gitignore",
    ".pre-commit-config.yaml",
    "dockerfile",
    "makefile",
    "package-lock.json",
    "package.json",
    "poetry.lock",
    "pyproject.toml",
    "requirements-dev.txt",
    "requirements.txt",
    "setup.cfg",
    "setup.py",
    "tox.ini",
}


def sanitize_review_input(
    *,
    project_context: str,
    pr_summary: str,
    changed_files: list[ChangedFile],
    diff: str,
    rules: list[str] | None = None,
) -> SanitizedReviewInput:
    cleaned_project_context = _clean_text(project_context)
    cleaned_pr_summary = _clean_text(pr_summary)
    cleaned_files = _clean_changed_files(changed_files)
    cleaned_diff = _clean_text(diff)
    cleaned_rules = _clean_rules(rules or DEFAULT_REVIEW_RULES)
    return _fit_size_limit(
        project_context=cleaned_project_context,
        pr_summary=cleaned_pr_summary,
        changed_files=cleaned_files,
        diff=cleaned_diff,
        rules=cleaned_rules,
    )


def render_review_input(review_input: SanitizedReviewInput) -> str:
    return json.dumps(review_input.to_model_payload(), indent=2, sort_keys=True)


def _clean_text(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("review input fields must be strings")

    cleaned = CONTROL_CHARS.sub("", value).replace("\r\n", "\n").replace("\r", "\n")
    for pattern in SECRET_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned.strip()


def _clean_changed_files(changed_files: list[ChangedFile]) -> list[ChangedFile]:
    if not isinstance(changed_files, list):
        raise TypeError("changed_files must be a list of ChangedFile objects")

    result = []
    seen = set()
    for changed_file in changed_files:
        if not isinstance(changed_file, ChangedFile):
            raise TypeError("changed_files must contain ChangedFile objects")

        cleaned_path = _clean_path(changed_file.path)
        if not cleaned_path or cleaned_path in seen:
            continue

        cleaned_old_path = None
        if changed_file.old_path is not None:
            cleaned_old_path = _clean_path(changed_file.old_path)
            if cleaned_old_path is None:
                continue

        status = _clean_status(changed_file.status)
        is_binary = bool(changed_file.is_binary)
        result.append(
            ChangedFile(
                path=cleaned_path,
                status=status,
                old_path=cleaned_old_path,
                is_binary=is_binary,
            )
        )
        seen.add(cleaned_path)
    return result


def _fit_size_limit(
    *,
    project_context: str,
    pr_summary: str,
    changed_files: list[ChangedFile],
    diff: str,
    rules: list[str],
) -> SanitizedReviewInput:
    review_input = _build_review_input(
        project_context=project_context,
        pr_summary=pr_summary,
        changed_files=changed_files,
        diff=diff,
        rules=rules,
        input_truncated=False,
    )
    if len(render_review_input(review_input)) <= MAX_INPUT_CHARS:
        return review_input

    truncated_diff = diff
    while True:
        payload_size = len(render_review_input(review_input))
        excess = payload_size - MAX_INPUT_CHARS
        keep_chars = max(0, len(truncated_diff) - excess - 200)
        truncated_diff = truncated_diff[:keep_chars].rstrip()
        review_input = _build_review_input(
            project_context=project_context,
            pr_summary=pr_summary,
            changed_files=changed_files,
            diff=truncated_diff,
            rules=rules,
            input_truncated=True,
        )
        if len(render_review_input(review_input)) <= MAX_INPUT_CHARS:
            return review_input
        if keep_chars == 0:
            raise ValueError(
                f"sanitized review metadata exceeds limit of {MAX_INPUT_CHARS} chars without diff"
            )


def _build_review_input(
    *,
    project_context: str,
    pr_summary: str,
    changed_files: list[ChangedFile],
    diff: str,
    rules: list[str],
    input_truncated: bool,
) -> SanitizedReviewInput:
    line_stats = _line_stats_by_file(diff)
    enriched_files = [_enrich_changed_file(changed_file, line_stats) for changed_file in changed_files]
    diff_stats = DiffStats(
        total_files_changed=len(enriched_files),
        total_added_lines=sum(file.added_lines for file in enriched_files),
        total_deleted_lines=sum(file.deleted_lines for file in enriched_files),
        input_truncated=input_truncated,
    )
    return SanitizedReviewInput(
        project_context=project_context,
        pr_summary=pr_summary,
        changed_files=enriched_files,
        diff=diff,
        rules=rules,
        diff_stats=diff_stats,
        review_hints=_review_hints(enriched_files),
        project_rules=PROJECT_RULES,
    )


def _line_stats_by_file(diff: str) -> dict[str, tuple[int, int]]:
    stats: dict[str, list[int]] = {}
    current_path: str | None = None
    unscoped_added = 0
    unscoped_deleted = 0

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            current_path = _path_from_diff_header(line)
            if current_path:
                stats.setdefault(current_path, [0, 0])
            continue
        if line.startswith("+") and not line.startswith("+++"):
            if current_path:
                stats.setdefault(current_path, [0, 0])[0] += 1
            else:
                unscoped_added += 1
            continue
        if line.startswith("-") and not line.startswith("---"):
            if current_path:
                stats.setdefault(current_path, [0, 0])[1] += 1
            else:
                unscoped_deleted += 1

    if len(stats) == 1:
        only_path = next(iter(stats))
        stats[only_path][0] += unscoped_added
        stats[only_path][1] += unscoped_deleted
    return {path: (counts[0], counts[1]) for path, counts in stats.items()}


def _path_from_diff_header(line: str) -> str | None:
    parts = line.split(" ")
    if len(parts) < 4:
        return None
    b_path = parts[3]
    if b_path == "/dev/null":
        return None
    if b_path.startswith("b/"):
        return _clean_path(b_path[2:])
    return _clean_path(b_path)


def _enrich_changed_file(
    changed_file: ChangedFile,
    line_stats: dict[str, tuple[int, int]],
) -> SanitizedChangedFile:
    added_lines, deleted_lines = line_stats.get(changed_file.path, (0, 0))
    extension = _extension(changed_file.path)
    category = _file_category(changed_file.path, extension)
    return SanitizedChangedFile(
        path=changed_file.path,
        status=changed_file.status,
        old_path=changed_file.old_path,
        is_binary=changed_file.is_binary,
        added_lines=added_lines,
        deleted_lines=deleted_lines,
        extension=extension,
        file_category=category,
        is_test_file=category == "test",
        is_ci_file=category == "ci",
        is_security_sensitive_path=_is_security_sensitive_path(changed_file.path),
    )


def _review_hints(changed_files: list[SanitizedChangedFile]) -> ReviewHints:
    touched_tests = any(file.is_test_file for file in changed_files)
    source_files = [file.path for file in changed_files if file.file_category == "source"]
    possible_missing_coverage = source_files[:10] if source_files and not touched_tests else []
    return ReviewHints(
        touched_tests=touched_tests,
        touched_source_without_tests=bool(possible_missing_coverage),
        requirements_changed=any(_is_requirements_path(file.path) for file in changed_files),
        workflow_changed=any(file.is_ci_file for file in changed_files),
        possible_missing_test_coverage=possible_missing_coverage,
    )


def _clean_path(path: str) -> str | None:
    cleaned = _clean_text(path)
    if not cleaned:
        return None
    if cleaned.startswith("/") or ".." in cleaned.split("/"):
        return None
    if not SAFE_FILE_PATH.match(cleaned):
        return None
    return cleaned


def _clean_status(status: str) -> FileStatus:
    allowed = {
        "added",
        "modified",
        "deleted",
        "renamed",
        "copied",
        "type_changed",
        "unmerged",
        "unknown",
    }
    if status not in allowed:
        return "unknown"
    return status


def _clean_rules(rules: list[str]) -> list[str]:
    if not isinstance(rules, list):
        raise TypeError("rules must be a list of strings")
    return [_clean_text(rule) for rule in rules if _clean_text(rule)]


def _extension(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    if "." not in name or name.startswith(".") and name.count(".") == 1:
        return ""
    return "." + name.rsplit(".", 1)[-1].lower()


def _file_category(path: str, extension: str) -> FileCategory:
    lower_path = path.lower()
    name = lower_path.rsplit("/", 1)[-1]
    if _is_ci_path(lower_path):
        return "ci"
    if _is_test_path(lower_path):
        return "test"
    if name in CONFIG_FILENAMES or extension in {".cfg", ".conf", ".ini", ".json", ".toml", ".yaml", ".yml"}:
        return "config"
    if lower_path.startswith("docs/") or name.startswith("readme") or extension in DOC_EXTENSIONS:
        return "docs"
    if extension in SOURCE_EXTENSIONS:
        return "source"
    return "unknown"


def _is_test_path(path: str) -> bool:
    parts = path.split("/")
    name = parts[-1]
    return (
        "test" in parts
        or "tests" in parts
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".test.js")
        or name.endswith(".test.ts")
        or name.endswith(".spec.js")
        or name.endswith(".spec.ts")
    )


def _is_ci_path(path: str) -> bool:
    return (
        path.startswith(".github/workflows/")
        or path.startswith(".github/actions/")
        or path.startswith(".gitlab-ci")
        or path.startswith(".circleci/")
        or path.startswith("ci/")
    )


def _is_requirements_path(path: str) -> bool:
    name = path.lower().rsplit("/", 1)[-1]
    return name in {"requirements.txt", "requirements-dev.txt", "pyproject.toml", "poetry.lock"}


def _is_security_sensitive_path(path: str) -> bool:
    words = re.split(r"[^a-z0-9]+", path.lower())
    return any(word in SECURITY_PATH_WORDS for word in words)
