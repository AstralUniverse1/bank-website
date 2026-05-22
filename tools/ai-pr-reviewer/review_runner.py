from __future__ import annotations

import os
import sys
from typing import Mapping

from git_diff import GitDiffResult, get_local_working_tree_diff, get_ref_diff
from github_context import load_github_pull_request_context, ref_diff_inputs
from review_contract import ReviewOutput, SanitizedReviewInput
from sanitizer import sanitize_review_input


def build_sanitized_input_for_diff(
    diff_result: GitDiffResult,
    project_context: str,
    pr_summary: str,
) -> SanitizedReviewInput:
    return sanitize_review_input(
        project_context=project_context,
        pr_summary=pr_summary,
        changed_files=diff_result.changed_files,
        diff=diff_result.diff,
    )


def run_review_for_diff(
    diff_result: GitDiffResult,
    project_context: str,
    pr_summary: str,
    prompt_name: str = "qa_review",
) -> ReviewOutput:
    sanitized_input = build_sanitized_input_for_diff(
        diff_result=diff_result,
        project_context=project_context,
        pr_summary=pr_summary,
    )
    return _call_llm(prompt_name, sanitized_input)


def run_local_review(
    repo_path: str,
    project_context: str,
    pr_summary: str,
    prompt_name: str = "qa_review",
) -> ReviewOutput:
    diff_result = get_local_working_tree_diff(repo_path)
    return run_review_for_diff(
        diff_result=diff_result,
        project_context=project_context,
        pr_summary=pr_summary,
        prompt_name=prompt_name,
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
        pr_summary=pr_summary,
        prompt_name=prompt_name,
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


def dry_run_for_diff(
    diff_result: GitDiffResult,
    project_context: str,
    pr_summary: str,
) -> SanitizedReviewInput:
    return build_sanitized_input_for_diff(
        diff_result=diff_result,
        project_context=project_context,
        pr_summary=pr_summary,
    )


def dry_run_local(
    repo_path: str,
    project_context: str,
    pr_summary: str,
) -> SanitizedReviewInput:
    diff_result = get_local_working_tree_diff(repo_path)
    return dry_run_for_diff(
        diff_result=diff_result,
        project_context=project_context,
        pr_summary=pr_summary,
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
        pr_summary=pr_summary,
    )


def _get_github_diff(
    repo_path: str,
    context,
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
