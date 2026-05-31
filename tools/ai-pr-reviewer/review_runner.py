from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping

from git_diff import GitDiffResult, get_local_working_tree_diff, get_ref_diff
from github_context import (
    GitHubIssueCommentContext,
    GitHubPullRequestContext,
    load_github_issue_comment_context,
    load_github_pull_request_context,
    load_pull_request_context_from_api,
    ref_diff_inputs,
)
from review_contract import ConversationComment, ReviewOutput, SanitizedReviewInput
from sanitizer import sanitize_review_input

AI_REVIEW_COMMAND = "/ai-reviewer"
PROJECT_RULE_PATHS = (
    ".ai-pr-reviewer.md",
    ".github/ai-pr-reviewer.md",
)


def build_sanitized_input_for_diff(
    diff_result: GitDiffResult,
    project_context: str,
    pr_summary: str,
    pr_description: str = "",
    project_rules: list[str] | None = None,
    conversation_comments: list[ConversationComment] | None = None,
) -> SanitizedReviewInput:
    return sanitize_review_input(
        project_context=project_context,
        pr_summary=pr_summary,
        pr_description=pr_description,
        changed_files=diff_result.changed_files,
        diff=diff_result.diff,
        project_rules=project_rules,
        conversation_comments=conversation_comments,
    )


def run_review_for_diff(
    diff_result: GitDiffResult,
    project_context: str,
    pr_summary: str,
    pr_description: str = "",
    prompt_name: str = "qa_review",
    project_rules: list[str] | None = None,
    conversation_comments: list[ConversationComment] | None = None,
) -> ReviewOutput:
    sanitized_input = build_sanitized_input_for_diff(
        diff_result=diff_result,
        project_context=project_context,
        pr_summary=pr_summary,
        pr_description=pr_description,
        project_rules=project_rules,
        conversation_comments=conversation_comments,
    )
    return _call_llm(prompt_name, sanitized_input)


def run_local_review(
    repo_path: str,
    project_context: str,
    pr_summary: str,
    pr_description: str = "",
    prompt_name: str = "qa_review",
) -> ReviewOutput:
    diff_result = get_local_working_tree_diff(repo_path)
    return run_review_for_diff(
        diff_result=diff_result,
        project_context=project_context,
        pr_summary=pr_summary,
        pr_description=pr_description,
        prompt_name=prompt_name,
        project_rules=load_project_rules(repo_path),
    )


def run_github_review(
    repo_path: str,
    project_context: str,
    pr_summary: str,
    prompt_name: str = "qa_review",
    token: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    print("ai-pr-reviewer: loading GitHub PR context", file=sys.stderr)
    context = load_github_pull_request_context(env)
    print("ai-pr-reviewer: collecting PR diff", file=sys.stderr)
    diff_result = _get_github_diff(repo_path, context)
    print("ai-pr-reviewer: calling OpenAI review model", file=sys.stderr)
    review_output = run_review_for_diff(
        diff_result=diff_result,
        project_context=project_context,
        pr_summary=context.title or pr_summary,
        pr_description=context.body,
        prompt_name=prompt_name,
        project_rules=load_project_rules(repo_path),
    )
    github_token = token if token is not None else os.environ.get("GITHUB_TOKEN", "")
    print("ai-pr-reviewer: posting GitHub PR comment", file=sys.stderr)
    result = _post_review_comment(
        owner=context.repo_owner,
        repo=context.repo_name,
        pr_number=context.pr_number,
        review_output=review_output,
        token=github_token,
    )
    print("ai-pr-reviewer: posted GitHub PR comment", file=sys.stderr)
    return result


def run_github_followup_review(
    repo_path: str,
    project_context: str,
    pr_summary: str,
    prompt_name: str = "qa_review",
    token: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    github_token = token if token is not None else os.environ.get("GITHUB_TOKEN", "")
    print("ai-pr-reviewer: loading GitHub issue comment context", file=sys.stderr)
    comment_context = load_github_issue_comment_context(env)
    skip_reason = _followup_skip_reason(comment_context)
    if skip_reason:
        print(f"ai-pr-reviewer: skipping follow-up: {skip_reason}", file=sys.stderr)
        return {"skipped": True, "reason": skip_reason}

    print("ai-pr-reviewer: loading PR metadata for follow-up", file=sys.stderr)
    pr_context = load_pull_request_context_from_api(
        owner=comment_context.repo_owner,
        repo=comment_context.repo_name,
        pr_number=comment_context.pr_number,
        token=github_token,
        event_name=comment_context.event_name,
        event_path=comment_context.event_path,
    )
    print("ai-pr-reviewer: collecting PR diff", file=sys.stderr)
    diff_result = _get_github_diff(repo_path, pr_context)
    print("ai-pr-reviewer: collecting relevant PR comments", file=sys.stderr)
    conversation_comments = _conversation_comments_for_followup(comment_context, github_token)
    print("ai-pr-reviewer: calling OpenAI follow-up model", file=sys.stderr)
    review_output = run_review_for_diff(
        diff_result=diff_result,
        project_context=project_context,
        pr_summary=pr_context.title or pr_summary,
        pr_description=pr_context.body,
        prompt_name=prompt_name,
        project_rules=load_project_rules(repo_path),
        conversation_comments=conversation_comments,
    )
    print("ai-pr-reviewer: posting GitHub PR follow-up comment", file=sys.stderr)
    result = _post_review_comment(
        owner=comment_context.repo_owner,
        repo=comment_context.repo_name,
        pr_number=comment_context.pr_number,
        review_output=review_output,
        token=github_token,
    )
    print("ai-pr-reviewer: posted GitHub PR follow-up comment", file=sys.stderr)
    return result


def dry_run_for_diff(
    diff_result: GitDiffResult,
    project_context: str,
    pr_summary: str,
    pr_description: str = "",
    project_rules: list[str] | None = None,
    conversation_comments: list[ConversationComment] | None = None,
) -> SanitizedReviewInput:
    return build_sanitized_input_for_diff(
        diff_result=diff_result,
        project_context=project_context,
        pr_summary=pr_summary,
        pr_description=pr_description,
        project_rules=project_rules,
        conversation_comments=conversation_comments,
    )


def dry_run_local(
    repo_path: str,
    project_context: str,
    pr_summary: str,
    pr_description: str = "",
) -> SanitizedReviewInput:
    diff_result = get_local_working_tree_diff(repo_path)
    return dry_run_for_diff(
        diff_result=diff_result,
        project_context=project_context,
        pr_summary=pr_summary,
        pr_description=pr_description,
        project_rules=load_project_rules(repo_path),
    )


def dry_run_github(
    repo_path: str,
    project_context: str,
    pr_summary: str,
    env: Mapping[str, str] | None = None,
) -> SanitizedReviewInput:
    context = load_github_pull_request_context(env)
    return dry_run_for_diff(
        diff_result=_get_github_diff(repo_path, context),
        project_context=project_context,
        pr_summary=context.title or pr_summary,
        pr_description=context.body,
        project_rules=load_project_rules(repo_path),
    )


def dry_run_github_followup(
    repo_path: str,
    project_context: str,
    pr_summary: str,
    token: str | None = None,
    env: Mapping[str, str] | None = None,
) -> SanitizedReviewInput:
    github_token = token if token is not None else os.environ.get("GITHUB_TOKEN", "")
    comment_context = load_github_issue_comment_context(env)
    skip_reason = _followup_skip_reason(comment_context)
    if skip_reason:
        raise RuntimeError(f"follow-up review skipped: {skip_reason}")
    pr_context = load_pull_request_context_from_api(
        owner=comment_context.repo_owner,
        repo=comment_context.repo_name,
        pr_number=comment_context.pr_number,
        token=github_token,
        event_name=comment_context.event_name,
        event_path=comment_context.event_path,
    )
    return dry_run_for_diff(
        diff_result=_get_github_diff(repo_path, pr_context),
        project_context=project_context,
        pr_summary=pr_context.title or pr_summary,
        pr_description=pr_context.body,
        project_rules=load_project_rules(repo_path),
        conversation_comments=_conversation_comments_for_followup(comment_context, github_token),
    )


def load_project_rules(repo_path: str) -> list[str]:
    repo = Path(repo_path)
    rules = []
    for relative_path in PROJECT_RULE_PATHS:
        path = repo / relative_path
        if not path.is_file():
            continue
        try:
            rules.append(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise RuntimeError(f"failed to read project rules: {relative_path}") from exc
    return rules


def _followup_skip_reason(context: GitHubIssueCommentContext) -> str | None:
    if not context.is_pr:
        return "comment is not on a pull request"
    if context.comment_user_type == "Bot":
        return "comment author is a bot"
    if AI_REVIEW_COMMAND not in context.comment_body:
        return f"comment does not contain {AI_REVIEW_COMMAND}"
    return None


def _conversation_comments_for_followup(
    context: GitHubIssueCommentContext,
    token: str,
) -> list[ConversationComment]:
    comments = _list_issue_comments(
        owner=context.repo_owner,
        repo=context.repo_name,
        pr_number=context.pr_number,
        token=token,
    )
    result = []
    for comment in comments:
        body = _comment_str(comment, "body")
        user = comment.get("user") if isinstance(comment.get("user"), dict) else {}
        user_type = _comment_str(user, "type")
        is_bot = user_type == "Bot"
        is_triggering = comment.get("id") == context.comment_id
        is_ai_review_comment = is_bot and _is_ai_reviewer_comment(body)
        is_ai_tagged_human_comment = not is_bot and AI_REVIEW_COMMAND in body
        if not (is_ai_review_comment or is_ai_tagged_human_comment or is_triggering):
            continue
        result.append(
            ConversationComment(
                author=_comment_str(user, "login"),
                author_type=_comment_str(comment, "author_association"),
                created_at=_comment_str(comment, "created_at"),
                body=body,
                is_bot=is_bot,
                is_triggering=is_triggering,
            )
        )
    return result


def _is_ai_reviewer_comment(body: str) -> bool:
    from github_commenter import AI_REVIEW_COMMENT_MARKER

    return AI_REVIEW_COMMENT_MARKER in body


def _comment_str(payload, key: str) -> str:
    if not isinstance(payload, dict):
        return ""
    value = payload.get(key)
    return value if isinstance(value, str) else ""


def _get_github_diff(
    repo_path: str,
    context: GitHubPullRequestContext,
) -> GitDiffResult:
    base_ref, head_ref = ref_diff_inputs(context)
    return get_ref_diff(base_ref=base_ref, head_ref=head_ref, repo_path=repo_path)


def _call_llm(prompt_name: str, sanitized_input: SanitizedReviewInput) -> ReviewOutput:
    from llm_client import call_llm

    return call_llm(prompt_name, sanitized_input)


def _post_review_comment(
    owner: str,
    repo: str,
    pr_number: int,
    review_output: ReviewOutput,
    token: str,
) -> dict[str, object]:
    from github_commenter import post_review_comment

    return post_review_comment(
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        review_output=review_output,
        token=token,
    )


def _list_issue_comments(
    owner: str,
    repo: str,
    pr_number: int,
    token: str,
) -> list[dict[str, object]]:
    from github_commenter import list_issue_comments

    return list_issue_comments(
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        token=token,
    )
