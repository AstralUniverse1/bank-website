import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from git_diff import GitDiffResult
from github_commenter import AI_REVIEW_COMMENT_MARKER
from github_context import GitHubIssueCommentContext, GitHubPullRequestContext
from review_contract import ChangedFile, ReviewOutput
from review_runner import (
    dry_run_for_diff,
    dry_run_github,
    load_project_rules,
    run_github_followup_review,
    run_github_review,
    run_review_for_diff,
)


class ReviewRunnerTests(unittest.TestCase):
    def test_dry_run_for_diff_returns_sanitized_input_without_llm(self):
        diff_result = GitDiffResult(
            changed_files=[ChangedFile(path="app.py", status="modified")],
            diff="+ api_key=secret",
            base_ref="HEAD",
            head_ref=None,
            mode="local",
        )

        result = dry_run_for_diff(diff_result, "ctx", "summary", pr_description="body token=abc123")

        self.assertEqual(result.changed_files[0].path, "app.py")
        self.assertEqual(result.changed_files[0].status, "modified")
        self.assertEqual(result.changed_files[0].file_category, "source")
        self.assertEqual(result.pr_description, "body [REDACTED]")
        self.assertEqual(result.diff, "+ [REDACTED]")

    def test_run_review_for_diff_calls_llm_with_sanitized_input(self):
        diff_result = GitDiffResult(
            changed_files=[ChangedFile(path="app.py", status="modified")],
            diff="+ token=abc123",
            base_ref="HEAD",
            head_ref=None,
            mode="local",
        )
        expected = ReviewOutput(summary="ok", findings=[], questions=[])

        with patch("review_runner._call_llm", return_value=expected) as call_llm:
            result = run_review_for_diff(diff_result, "ctx", "summary")

        self.assertEqual(result, expected)
        sanitized_input = call_llm.call_args.args[1]
        self.assertEqual(sanitized_input.diff, "+ [REDACTED]")

    def test_dry_run_github_uses_event_context_and_ref_diff(self):
        context = _github_context()
        diff_result = GitDiffResult(
            changed_files=[ChangedFile(path="app.py", status="modified")],
            diff="+ password=secret",
            base_ref="base-sha",
            head_ref="head-sha",
            mode="refs",
        )

        with patch("review_runner.load_github_pull_request_context", return_value=context) as load_context:
            with patch("review_runner.get_ref_diff", return_value=diff_result) as get_ref_diff:
                result = dry_run_github(".", "ctx", "fallback", env={"GITHUB_EVENT_NAME": "pull_request"})

        load_context.assert_called_once_with({"GITHUB_EVENT_NAME": "pull_request"})
        get_ref_diff.assert_called_once_with(base_ref="base-sha", head_ref="head-sha", repo_path=".")
        self.assertEqual(result.pr_summary, "PR title")
        self.assertEqual(result.pr_description, "PR body")
        self.assertEqual(result.diff, "+ [REDACTED]")

    def test_run_github_review_posts_review_comment(self):
        context = _github_context()
        diff_result = GitDiffResult(
            changed_files=[ChangedFile(path="app.py", status="modified")],
            diff="+ change",
            base_ref="base-sha",
            head_ref="head-sha",
            mode="refs",
        )
        review_output = ReviewOutput(summary="ok", findings=[], questions=[])

        with patch("review_runner.load_github_pull_request_context", return_value=context):
            with patch("review_runner.get_ref_diff", return_value=diff_result):
                with patch("review_runner._call_llm", return_value=review_output) as call_llm:
                    with patch("review_runner._post_review_comment", return_value={"id": 123}) as post_comment:
                        result = run_github_review(
                            repo_path=".",
                            project_context="ctx",
                            pr_summary="summary",
                            prompt_name="qa_review",
                            token="github-token",
                            env={"GITHUB_EVENT_NAME": "pull_request"},
                        )

        self.assertEqual(result, {"id": 123})
        sanitized_input = call_llm.call_args.args[1]
        self.assertEqual(sanitized_input.pr_description, "PR body")
        post_comment.assert_called_once_with(
            owner="octo-org",
            repo="octo-repo",
            pr_number=42,
            review_output=review_output,
            token="github-token",
        )

    def test_load_project_rules_reads_allowlisted_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            (repo / ".github").mkdir()
            (repo / ".ai-pr-reviewer.md").write_text("Root rules", encoding="utf-8")
            (repo / ".github" / "ai-pr-reviewer.md").write_text("GitHub rules", encoding="utf-8")

            self.assertEqual(load_project_rules(temp_dir), ["Root rules", "GitHub rules"])

    def test_run_github_followup_filters_relevant_comments(self):
        comment_context = GitHubIssueCommentContext(
            event_name="issue_comment",
            event_path="/tmp/event.json",
            repo_owner="octo-org",
            repo_name="octo-repo",
            pr_number=42,
            comment_id=4,
            comment_body="/ai-reviewer please recheck",
            comment_author="alice",
            comment_author_type="MEMBER",
            comment_created_at="2026-05-31T00:00:00Z",
            comment_user_type="User",
            is_pr=True,
        )
        pr_context = _github_context(event_name="issue_comment")
        diff_result = GitDiffResult(
            changed_files=[ChangedFile(path="app.py", status="modified")],
            diff="+ change",
            base_ref="base-sha",
            head_ref="head-sha",
            mode="refs",
        )
        comments = [
            _comment(1, "github-actions[bot]", "Bot", "NONE", "## AI PR Review\nheading only"),
            _comment(2, "github-actions[bot]", "Bot", "NONE", f"{AI_REVIEW_COMMENT_MARKER}\n## AI PR Review\nold"),
            _comment(3, "bob", "User", "MEMBER", "unrelated"),
            _comment(4, "alice", "User", "MEMBER", "/ai-reviewer please recheck"),
        ]
        review_output = ReviewOutput(summary="ok", findings=[], questions=[])

        with patch("review_runner.load_github_issue_comment_context", return_value=comment_context):
            with patch("review_runner.load_pull_request_context_from_api", return_value=pr_context):
                with patch("review_runner.get_ref_diff", return_value=diff_result):
                    with patch("review_runner._list_issue_comments", return_value=comments):
                        with patch("review_runner._call_llm", return_value=review_output) as call_llm:
                            with patch("review_runner._post_review_comment", return_value={"id": 321}):
                                result = run_github_followup_review(
                                    repo_path=".",
                                    project_context="ctx",
                                    pr_summary="summary",
                                    token="github-token",
                                    env={"GITHUB_EVENT_NAME": "issue_comment"},
                                )

        self.assertEqual(result, {"id": 321})
        sanitized_input = call_llm.call_args.args[1]
        bodies = [comment.body for comment in sanitized_input.conversation.comments]
        self.assertEqual(bodies, [f"{AI_REVIEW_COMMENT_MARKER}\n## AI PR Review\nold", "/ai-reviewer please recheck"])
        self.assertNotIn("## AI PR Review\nheading only", bodies)
        self.assertTrue(sanitized_input.conversation.comments[1].is_triggering)

    def test_run_github_followup_skips_bot_trigger(self):
        comment_context = GitHubIssueCommentContext(
            event_name="issue_comment",
            event_path="/tmp/event.json",
            repo_owner="octo-org",
            repo_name="octo-repo",
            pr_number=42,
            comment_id=3,
            comment_body="/ai-reviewer",
            comment_author="github-actions[bot]",
            comment_author_type="NONE",
            comment_created_at="2026-05-31T00:00:00Z",
            comment_user_type="Bot",
            is_pr=True,
        )

        with patch("review_runner.load_github_issue_comment_context", return_value=comment_context):
            result = run_github_followup_review(".", "ctx", "summary", token="github-token")

        self.assertTrue(result["skipped"])
        self.assertEqual(result["reason"], "comment author is a bot")


def _github_context(event_name="pull_request"):
    return GitHubPullRequestContext(
        event_name=event_name,
        event_path="/tmp/event.json",
        repo_owner="octo-org",
        repo_name="octo-repo",
        pr_number=42,
        base_ref="main",
        head_ref="feature",
        base_sha="base-sha",
        head_sha="head-sha",
        title="PR title",
        body="PR body",
    )


def _comment(comment_id, login, user_type, association, body):
    return {
        "id": comment_id,
        "body": body,
        "author_association": association,
        "created_at": "2026-05-31T00:00:00Z",
        "user": {"login": login, "type": user_type},
    }


if __name__ == "__main__":
    unittest.main()
