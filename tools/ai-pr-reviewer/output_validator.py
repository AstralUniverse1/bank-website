from __future__ import annotations

import json
from typing import Any

from review_contract import ReviewFinding, ReviewOutput

VALID_SEVERITIES = {"critical", "high", "medium", "low"}
MAX_SUMMARY_CHARS = 600
MAX_FINDINGS = 8
MAX_QUESTIONS = 3


def validate_review_output(raw_output: str) -> ReviewOutput:
    try:
        data = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise ValueError("model output is not valid JSON") from exc

    if not isinstance(data, dict):
        raise ValueError("model output must be a JSON object")

    _require_keys(data, {"summary", "findings", "questions"})
    summary = _string(data["summary"], "summary", MAX_SUMMARY_CHARS)
    findings = _findings(data["findings"])
    questions = _questions(data["questions"])
    return ReviewOutput(summary=summary, findings=findings, questions=questions)


def _findings(value: Any) -> list[ReviewFinding]:
    if not isinstance(value, list):
        raise ValueError("findings must be a list")
    if len(value) > MAX_FINDINGS:
        raise ValueError(f"findings must contain at most {MAX_FINDINGS} items")

    findings = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"findings[{index}] must be an object")
        _require_keys(
            item,
            {"severity", "title", "detail", "recommendation", "file", "line"},
            f"findings[{index}]",
        )

        severity = _string(item["severity"], f"findings[{index}].severity", 20)
        if severity not in VALID_SEVERITIES:
            raise ValueError(f"findings[{index}].severity is invalid")

        findings.append(
            ReviewFinding(
                severity=severity,
                title=_string(item["title"], f"findings[{index}].title", 140),
                detail=_string(item["detail"], f"findings[{index}].detail", 1200),
                recommendation=_string(
                    item["recommendation"], f"findings[{index}].recommendation", 800
                ),
                file=_nullable_string(item["file"], f"findings[{index}].file", 260),
                line=_nullable_positive_int(item["line"], f"findings[{index}].line"),
            )
        )
    return findings


def _questions(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("questions must be a list")
    if len(value) > MAX_QUESTIONS:
        raise ValueError(f"questions must contain at most {MAX_QUESTIONS} items")
    return [_string(question, f"questions[{index}]", 240) for index, question in enumerate(value)]


def _require_keys(value: dict[str, Any], keys: set[str], name: str = "output") -> None:
    actual = set(value)
    missing = keys - actual
    extra = actual - keys
    if missing:
        raise ValueError(f"{name} missing required keys: {sorted(missing)}")
    if extra:
        raise ValueError(f"{name} contains unexpected keys: {sorted(extra)}")


def _string(value: Any, name: str, max_chars: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    if len(value) > max_chars:
        raise ValueError(f"{name} must be at most {max_chars} chars")
    return value


def _nullable_string(value: Any, name: str, max_chars: int) -> str | None:
    if value is None:
        return None
    return _string(value, name, max_chars)


def _nullable_positive_int(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer or null")
    return value
