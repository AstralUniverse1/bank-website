from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


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

    return GitHubPullRequestContext(
        event_name=event_name,
        event_path=event_path,
        repo_owner=owner,
        repo_name=repo_name,
        pr_number=_required_int(pull_request, "number"),
        base_ref=_required_nested_str(pull_request, "base", "ref"),
        head_ref=_required_nested_str(pull_request, "head", "ref"),
        base_sha=_required_nested_str(pull_request, "base", "sha"),
        head_sha=_required_nested_str(pull_request, "head", "sha"),
    )


def ref_diff_inputs(context: GitHubPullRequestContext) -> tuple[str, str]:
    return context.base_sha, context.head_sha


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


def _required_int(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise GitHubContextError(f"missing or invalid integer in GitHub payload: {key}")
    return value


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
