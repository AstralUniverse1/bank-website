import json
import tempfile
import unittest
from pathlib import Path

from github_context import (
    GitHubContextError,
    GitHubIssueCommentContext,
    GitHubPullRequestContext,
    load_github_issue_comment_context,
    load_github_pull_request_context,
    ref_diff_inputs,
)


class GitHubContextTests(unittest.TestCase):
    def test_loads_pull_request_context(self):
        with _event_file(_pull_request_payload()) as event_path:
            context = load_github_pull_request_context(
                {
                    "GITHUB_EVENT_NAME": "pull_request",
                    "GITHUB_EVENT_PATH": event_path,
                    "GITHUB_REPOSITORY": "octo-org/octo-repo",
                }
            )

        self.assertEqual(
            context,
            GitHubPullRequestContext(
                event_name="pull_request",
                event_path=event_path,
                repo_owner="octo-org",
                repo_name="octo-repo",
                pr_number=42,
                base_ref="main",
                head_ref="feature",
                base_sha="base-sha",
                head_sha="head-sha",
                title="Add feature",
                body="Implements the thing",
            ),
        )
        self.assertEqual(ref_diff_inputs(context), ("base-sha", "head-sha"))

    def test_loads_null_pull_request_body_as_empty_string(self):
        payload = _pull_request_payload()
        payload["pull_request"]["body"] = None
        with _event_file(payload) as event_path:
            context = load_github_pull_request_context(
                {
                    "GITHUB_EVENT_NAME": "pull_request_target",
                    "GITHUB_EVENT_PATH": event_path,
                    "GITHUB_REPOSITORY": "octo-org/octo-repo",
                }
            )

        self.assertEqual(context.body, "")

    def test_loads_issue_comment_context(self):
        with _event_file(_issue_comment_payload()) as event_path:
            context = load_github_issue_comment_context(
                {
                    "GITHUB_EVENT_NAME": "issue_comment",
                    "GITHUB_EVENT_PATH": event_path,
                    "GITHUB_REPOSITORY": "octo-org/octo-repo",
                }
            )

        self.assertEqual(
            context,
            GitHubIssueCommentContext(
                event_name="issue_comment",
                event_path=event_path,
                repo_owner="octo-org",
                repo_name="octo-repo",
                pr_number=42,
                comment_id=1001,
                comment_body="/ai-reviewer please recheck",
                comment_author="alice",
                comment_author_type="MEMBER",
                comment_created_at="2026-05-31T00:00:00Z",
                comment_user_type="User",
                is_pr=True,
            ),
        )

    def test_rejects_missing_env(self):
        with self.assertRaisesRegex(GitHubContextError, "GITHUB_EVENT_NAME"):
            load_github_pull_request_context({})

    def test_rejects_non_pr_event(self):
        with _event_file(_pull_request_payload()) as event_path:
            with self.assertRaisesRegex(GitHubContextError, "unsupported GitHub event"):
                load_github_pull_request_context(
                    {
                        "GITHUB_EVENT_NAME": "push",
                        "GITHUB_EVENT_PATH": event_path,
                        "GITHUB_REPOSITORY": "octo-org/octo-repo",
                    }
                )

    def test_rejects_missing_event_file(self):
        with self.assertRaisesRegex(GitHubContextError, "failed to read"):
            load_github_pull_request_context(
                {
                    "GITHUB_EVENT_NAME": "pull_request",
                    "GITHUB_EVENT_PATH": "/tmp/does-not-exist-github-event.json",
                    "GITHUB_REPOSITORY": "octo-org/octo-repo",
                }
            )

    def test_rejects_malformed_payload(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write("{bad")
            event_path = handle.name

        try:
            with self.assertRaisesRegex(GitHubContextError, "invalid GitHub event payload"):
                load_github_pull_request_context(
                    {
                        "GITHUB_EVENT_NAME": "pull_request",
                        "GITHUB_EVENT_PATH": event_path,
                        "GITHUB_REPOSITORY": "octo-org/octo-repo",
                    }
                )
        finally:
            Path(event_path).unlink(missing_ok=True)

    def test_rejects_missing_pr_payload(self):
        with _event_file({"repository": {"full_name": "octo-org/octo-repo"}}) as event_path:
            with self.assertRaisesRegex(GitHubContextError, "pull_request"):
                load_github_pull_request_context(
                    {
                        "GITHUB_EVENT_NAME": "pull_request",
                        "GITHUB_EVENT_PATH": event_path,
                        "GITHUB_REPOSITORY": "octo-org/octo-repo",
                    }
                )


def _pull_request_payload():
    return {
        "pull_request": {
            "number": 42,
            "title": "Add feature",
            "body": "Implements the thing",
            "base": {"ref": "main", "sha": "base-sha"},
            "head": {"ref": "feature", "sha": "head-sha"},
        }
    }


def _issue_comment_payload():
    return {
        "issue": {"number": 42, "pull_request": {"url": "https://api.github.test/pr"}},
        "comment": {
            "id": 1001,
            "body": "/ai-reviewer please recheck",
            "author_association": "MEMBER",
            "created_at": "2026-05-31T00:00:00Z",
            "user": {"login": "alice", "type": "User"},
        },
    }


class _event_file:
    def __init__(self, payload):
        self.payload = payload
        self.path = None

    def __enter__(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            json.dump(self.payload, handle)
            self.path = handle.name
        return self.path

    def __exit__(self, exc_type, exc, tb):
        Path(self.path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
