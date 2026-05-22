from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.request
from typing import Any

from review_contract import ReviewOutput

GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
USER_AGENT = "ai-pr-reviewer"
MAX_COMMENT_BODY_CHARS = 20_000
TRUNCATION_MARKER = "\n\n_Comment truncated by ai-pr-reviewer._"

MENTION_PATTERN = re.compile(r"@(?=[A-Za-z0-9][A-Za-z0-9-]{0,38}\b)")


class GitHubCommentError(RuntimeError):
    pass


def format_review_comment(review_output: ReviewOutput) -> str:
    sections = [
        "## AI PR Review",
        "",
        f"**Summary:** {_safe_text(review_output.summary)}",
        "",
    ]

    if review_output.findings:
        sections.append("### Findings")
        for index, finding in enumerate(review_output.findings, start=1):
            sections.extend(
                [
                    f"{index}. **{finding.severity.upper()}**: {_safe_text(finding.title)}",
                    f"   - Detail: {_safe_text(finding.detail)}",
                    f"   - Recommendation: {_safe_text(finding.recommendation)}",
                ]
            )
            location = _format_location(finding.file, finding.line)
            if location:
                sections.append(f"   - Location: {location}")
    else:
        sections.extend(["### Findings", "No findings."])

    if review_output.questions:
        sections.extend(["", "### Questions"])
        for question in review_output.questions:
            sections.append(f"- {_safe_text(question)}")

    return _cap_comment_body("\n".join(sections).rstrip())


def post_pr_comment(
    owner: str,
    repo: str,
    pr_number: int,
    body: str,
    token: str,
) -> dict[str, object]:
    owner = _required_text(owner, "owner")
    repo = _required_text(repo, "repo")
    body = _required_text(body, "body")
    token = _required_text(token, "token")
    if not isinstance(pr_number, int) or pr_number < 1:
        raise GitHubCommentError("pr_number must be a positive integer")

    capped_body = _cap_comment_body(body)
    url = f"{GITHUB_API_BASE_URL}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    payload = json.dumps({"body": capped_body}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status = response.status
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        detail = _safe_response_excerpt(exc.read())
        raise GitHubCommentError(
            f"GitHub comment request failed with status {exc.code}: {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise GitHubCommentError("GitHub comment request failed due to a network error") from exc
    except OSError as exc:
        raise GitHubCommentError("GitHub comment request failed") from exc

    if status < 200 or status >= 300:
        raise GitHubCommentError(f"GitHub comment request failed with status {status}")

    try:
        parsed = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GitHubCommentError("GitHub comment response was not valid JSON") from exc

    if not isinstance(parsed, dict) or not isinstance(parsed.get("id"), int):
        raise GitHubCommentError("GitHub comment response had an unexpected shape")
    return parsed


def post_review_comment(
    owner: str,
    repo: str,
    pr_number: int,
    review_output: ReviewOutput,
    token: str,
) -> dict[str, object]:
    return post_pr_comment(
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        body=format_review_comment(review_output),
        token=token,
    )


def _format_location(file_path: str | None, line: int | None) -> str | None:
    if not file_path:
        return None
    location = f"`{_safe_code(file_path)}`"
    if line is not None:
        location = f"{location}:{line}"
    return location


def _safe_text(value: str) -> str:
    escaped = html.escape(value, quote=False)
    return MENTION_PATTERN.sub("@\u200b", escaped)


def _safe_code(value: str) -> str:
    return _safe_text(value).replace("`", "\\`")


def _cap_comment_body(body: str) -> str:
    if len(body) <= MAX_COMMENT_BODY_CHARS:
        return body
    keep_chars = MAX_COMMENT_BODY_CHARS - len(TRUNCATION_MARKER)
    if keep_chars < 0:
        raise GitHubCommentError("comment truncation marker exceeds comment size cap")
    return body[:keep_chars].rstrip() + TRUNCATION_MARKER


def _required_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GitHubCommentError(f"{name} is required")
    return value.strip()


def _safe_response_excerpt(response_body: bytes) -> str:
    text = response_body.decode("utf-8", errors="replace")
    return text[:500].replace("\n", " ")
