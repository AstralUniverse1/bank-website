from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

FindingSeverity = Literal["critical", "high", "medium", "low"]
FileStatus = Literal[
    "added",
    "modified",
    "deleted",
    "renamed",
    "copied",
    "type_changed",
    "unmerged",
    "unknown",
]
FileCategory = Literal["source", "test", "config", "ci", "docs", "unknown"]


@dataclass(frozen=True)
class ChangedFile:
    path: str
    status: FileStatus
    old_path: str | None = None
    is_binary: bool = False


@dataclass(frozen=True)
class SanitizedChangedFile:
    path: str
    status: FileStatus
    old_path: str | None = None
    is_binary: bool = False
    added_lines: int = 0
    deleted_lines: int = 0
    extension: str = ""
    file_category: FileCategory = "unknown"
    is_test_file: bool = False
    is_ci_file: bool = False
    is_security_sensitive_path: bool = False


@dataclass(frozen=True)
class ConversationComment:
    author: str
    author_type: str
    created_at: str
    body: str
    is_bot: bool = False
    is_triggering: bool = False


@dataclass(frozen=True)
class SanitizedConversationComment:
    author: str
    author_type: str
    created_at: str
    body: str
    is_bot: bool = False
    is_triggering: bool = False


@dataclass(frozen=True)
class ConversationContext:
    comments: list[SanitizedConversationComment]
    total_relevant_comments: int
    omitted_comments: int


@dataclass(frozen=True)
class DiffStats:
    total_files_changed: int
    total_added_lines: int
    total_deleted_lines: int
    input_truncated: bool


@dataclass(frozen=True)
class ReviewHints:
    touched_tests: bool
    touched_source_without_tests: bool
    requirements_changed: bool
    workflow_changed: bool
    possible_missing_test_coverage: list[str]


@dataclass(frozen=True)
class SanitizedReviewInput:
    project_context: str
    pr_summary: str
    pr_description: str
    changed_files: list[SanitizedChangedFile]
    diff: str
    rules: list[str]
    diff_stats: DiffStats
    review_hints: ReviewHints
    reviewer_safety_rules: list[str]
    project_rules: list[str]
    conversation: ConversationContext

    def to_model_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewFinding:
    severity: FindingSeverity
    title: str
    detail: str
    recommendation: str
    file: str | None = None
    line: int | None = None


@dataclass(frozen=True)
class ReviewOutput:
    summary: str
    findings: list[ReviewFinding]
    questions: list[str]


REVIEW_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "findings", "questions"],
    "properties": {
        "summary": {"type": "string", "maxLength": 600},
        "findings": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "severity",
                    "title",
                    "detail",
                    "recommendation",
                    "file",
                    "line",
                ],
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "high", "medium", "low"],
                    },
                    "title": {"type": "string", "maxLength": 140},
                    "detail": {"type": "string", "maxLength": 1200},
                    "recommendation": {"type": "string", "maxLength": 800},
                    "file": {"type": ["string", "null"], "maxLength": 260},
                    "line": {"type": ["integer", "null"], "minimum": 1},
                },
            },
        },
        "questions": {
            "type": "array",
            "maxItems": 3,
            "items": {"type": "string", "maxLength": 240},
        },
    },
}
