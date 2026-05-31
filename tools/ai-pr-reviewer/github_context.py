from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
USER_AGENT = "ai-pr-reviewer"


class GitHubContextError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitHubPullRequestContext:
    event_name: str
    event_path: str
    repo_owner: str
    repo_name: str
    pr_number: int
    base_ref: str
    head_ref: str
    base_sha: str
    head_sha: str
    title: str = ""
    body: str = ""


@dataclass(frozen=True)
class GitHubIssueCommentContext:
    event_name: str
    event_path: str
    repo_owner: str
    repo_name: str
    pr_number: int
    comment_id: int
    comment_body: str
    comment_author: str
    comment_author_type: str
    comment_created_at: str
    comment_user_type: str
    is_pr: bool


def load_github_pull_request_context(
    env: Mapping[str, str] | None = None,
) -> GitHubPullRequestContext:
    source_env = env if env is not None else os.environ
    event_name = _required_env(source_env, "GITHUB_EVENT_NAME")
    event_path = _required_env(source_env, "GITHUB_EVENT_PATH")
    repository = _required_env(source_env, "GITHUB_REPOSITORY")

    if event_name not in {"pull_request", "pull_request_target"}:
        raise GitHubContextError(f"unsupported GitHub event: {event_name}")

    payload = _load_event_payload(event_path)
    owner, repo_name = _parse_repository(repository)
    pull_request = _required_object(payload, "pull_request")

    return _pull_request_context_from_payload(
        event_name=event_name,
        event_path=event_path,
        repo_owner=owner,
        repo_name=repo_name,
        pull_request=pull_request,
    )


def load_github_issue_comment_context(
    env: Mapping[str, str] | None = None,
) -> GitHubIssueCommentContext:
    source_env = env if env is not None else os.environ
    event_name = _required_env(source_env, "GITHUB_EVENT_NAME")
    event_path = _required_env(source_env, "GITHUB_EVENT_PATH")
    repository = _required_env(source_env, "GITHUB_REPOSITORY")

    if event_name != "issue_comment":
        raise GitHubContextError(f"unsupported GitHub event: {event_name}")

    payload = _load_event_payload(event_path)
    owner, repo_name = _parse_repository(repository)
    issue = _required_object(payload, "issue")
    comment = _required_object(payload, "comment")
    user = _optional_object(comment, "user")

    return GitHubIssueCommentContext(
        event_name=event_name,
        event_path=event_path,
        repo_owner=owner,
        repo_name=repo_name,
        pr_number=_required_int(issue, "number"),
        comment_id=_required_int(comment, "id"),
        comment_body=_optional_str(comment, "body"),
        comment_author=_optional_str(user, "login"),
        comment_author_type=_optional_str(comment, "author_association"),
        comment_created_at=_optional_str(comment, "created_at"),
        comment_user_type=_optional_str(user, "type"),
        is_pr=isinstance(issue.get("pull_request"), dict),
    )


def load_pull_request_context_from_api(
    *,
    owner: str,
    repo: str,
    pr_number: int,
    token: str,
    event_name: str = "issue_comment",
    event_path: str = "",
) -> GitHubPullRequestContext:
    payload = _github_api_get(
        f"/repos/{owner}/{repo}/pulls/{pr_number}",
        token=token,
    )
    if not isinstance(payload, dict):
        raise GitHubContextError("GitHub PR API response must be a JSON object")
    return _pull_request_context_from_payload(
        event_name=event_name,
        event_path=event_path,
        repo_owner=owner,
        repo_name=repo,
        pull_request=payload,
    )


def ref_diff_inputs(context: GitHubPullRequestContext) -> tuple[str, str]:
    return context.base_sha, context.head_sha


def _pull_request_context_from_payload(
    *,
    event_name: str,
    event_path: str,
    repo_owner: str,
    repo_name: str,
    pull_request: Mapping[str, object],
) -> GitHubPullRequestContext:
    return GitHubPullRequestContext(
        event_name=event_name,
        event_path=event_path,
        repo_owner=repo_owner,
        repo_name=repo_name,
        pr_number=_required_int(pull_request, "number"),
        base_ref=_required_nested_str(pull_request, "base", "ref"),
        head_ref=_required_nested_str(pull_request, "head", "ref"),
        base_sha=_required_nested_str(pull_request, "base", "sha"),
        head_sha=_required_nested_str(pull_request, "head", "sha"),
        title=_optional_str(pull_request, "title"),
        body=_optional_str(pull_request, "body"),
    )


def _required_env(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if not value:
        raise GitHubContextError(f"missing required environment variable: {name}")
    return value


def _load_event_payload(event_path: str) -> dict[str, object]:
    path = Path(event_path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GitHubContextError(f"failed to read GitHub event payload: {event_path}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GitHubContextError(f"invalid GitHub event payload JSON: {event_path}") from exc

    if not isinstance(payload, dict):
        raise GitHubContextError("GitHub event payload must be a JSON object")
    return payload


def _parse_repository(repository: str) -> tuple[str, str]:
    parts = repository.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise GitHubContextError("GITHUB_REPOSITORY must be in owner/name format")
    return parts[0], parts[1]


def _required_object(payload: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise GitHubContextError(f"missing or invalid object in GitHub payload: {key}")
    return value


def _optional_object(payload: Mapping[str, object], key: str) -> Mapping[str, object]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _required_int(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise GitHubContextError(f"missing or invalid integer in GitHub payload: {key}")
    return value


def _optional_str(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def _required_nested_str(
    payload: Mapping[str, object],
    object_key: str,
    value_key: str,
) -> str:
    nested = _required_object(payload, object_key)
    value = nested.get(value_key)
    if not isinstance(value, str) or not value:
        raise GitHubContextError(
            f"missing or invalid string in GitHub payload: {object_key}.{value_key}"
        )
    return value


def _github_api_get(path: str, *, token: str) -> object:
    if not token.strip():
        raise GitHubContextError("GitHub token is required")
    request = urllib.request.Request(
        f"{GITHUB_API_BASE_URL}{path}",
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response_body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500].replace("\n", " ")
        raise GitHubContextError(
            f"GitHub API request failed with status {exc.code}: {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise GitHubContextError("GitHub API request failed due to a network error") from exc
    except OSError as exc:
        raise GitHubContextError("GitHub API request failed") from exc

    try:
        return json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GitHubContextError("GitHub API response was not valid JSON") from exc
