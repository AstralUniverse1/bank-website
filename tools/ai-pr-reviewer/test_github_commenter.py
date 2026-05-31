import json
import unittest
import urllib.error
from io import BytesIO
from unittest.mock import patch

from github_commenter import (
    AI_REVIEW_COMMENT_MARKER,
    GITHUB_API_VERSION,
    MAX_COMMENT_BODY_CHARS,
    TRUNCATION_MARKER,
    GitHubCommentError,
    format_review_comment,
    post_pr_comment,
)
from review_contract import ReviewFinding, ReviewOutput


class FormatReviewCommentTests(unittest.TestCase):
    def test_formats_no_findings(self):
        body = format_review_comment(
            ReviewOutput(summary="Looks fine", findings=[], questions=[])
        )

        self.assertTrue(body.startswith(AI_REVIEW_COMMENT_MARKER + "\n## AI PR Review"))
        self.assertIn("**Summary:** Looks fine", body)
        self.assertIn("No findings.", body)

    def test_formats_multiple_findings_with_locations(self):
        body = format_review_comment(
            ReviewOutput(
                summary="Needs work",
                findings=[
                    ReviewFinding(
                        severity="high",
                        title="Missing auth",
                        detail="Endpoint lacks permission check",
                        recommendation="Require user authorization",
                        file="app.py",
                        line=12,
                    ),
                    ReviewFinding(
                        severity="low",
                        title="Missing test",
                        detail="No regression test",
                        recommendation="Add a unit test",
                        file="tests/test_app.py",
                    ),
                ],
                questions=[],
            )
        )

        self.assertIn("1. **HIGH**: Missing auth", body)
        self.assertIn("`app.py`:12", body)
        self.assertIn("2. **LOW**: Missing test", body)
        self.assertIn("`tests/test_app.py`", body)

    def test_formats_questions(self):
        body = format_review_comment(
            ReviewOutput(
                summary="Question",
                findings=[],
                questions=["Should this handle retries?"],
            )
        )

        self.assertIn("### Questions", body)
        self.assertIn("- Should this handle retries?", body)

    def test_neutralizes_mentions_and_html(self):
        body = format_review_comment(
            ReviewOutput(
                summary="@team <script>",
                findings=[
                    ReviewFinding(
                        severity="medium",
                        title="@alice check <b>",
                        detail="Use <danger>",
                        recommendation="Ask @ops",
                        file="src/@file.py",
                    )
                ],
                questions=["Ping @here?"],
            )
        )

        self.assertIn("@\u200bteam", body)
        self.assertIn("&lt;script&gt;", body)
        self.assertIn("@\u200balice", body)
        self.assertIn("@\u200bops", body)
        self.assertIn("@\u200bhere", body)

    def test_truncates_deterministically(self):
        body = format_review_comment(
            ReviewOutput(summary="x" * (MAX_COMMENT_BODY_CHARS + 100), findings=[], questions=[])
        )

        self.assertLessEqual(len(body), MAX_COMMENT_BODY_CHARS)
        self.assertTrue(body.endswith(TRUNCATION_MARKER))


class PostPrCommentTests(unittest.TestCase):
    def test_posts_comment_with_expected_request(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return _FakeResponse(201, {"id": 123, "body": "ok"})

        with patch("urllib.request.urlopen", fake_urlopen):
            result = post_pr_comment(
                owner="octo-org",
                repo="octo-repo",
                pr_number=42,
                body="hello",
                token="secret-token",
            )

        request = captured["request"]
        self.assertEqual(result["id"], 123)
        self.assertEqual(captured["timeout"], 20)
        self.assertEqual(request.full_url, "https://api.github.com/repos/octo-org/octo-repo/issues/42/comments")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.headers["Authorization"], "Bearer secret-token")
        self.assertEqual(request.headers["Accept"], "application/vnd.github+json")
        self.assertEqual(request.headers["User-agent"], "ai-pr-reviewer")
        self.assertEqual(request.headers["X-github-api-version"], GITHUB_API_VERSION)
        self.assertEqual(json.loads(request.data.decode("utf-8")), {"body": "hello"})

    def test_rejects_missing_token(self):
        with self.assertRaisesRegex(GitHubCommentError, "token is required"):
            post_pr_comment("owner", "repo", 1, "body", "")

    def test_rejects_missing_body(self):
        with self.assertRaisesRegex(GitHubCommentError, "body is required"):
            post_pr_comment("owner", "repo", 1, "", "secret-token")

    def test_non_2xx_response_raises_without_token(self):
        token = "secret-token"

        def fake_urlopen(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                403,
                "Forbidden",
                hdrs=None,
                fp=BytesIO(b'{"message":"bad credentials"}'),
            )

        with patch("urllib.request.urlopen", fake_urlopen):
            with self.assertRaises(GitHubCommentError) as ctx:
                post_pr_comment("owner", "repo", 1, "body", token)

        self.assertNotIn(token, str(ctx.exception))
        self.assertIn("403", str(ctx.exception))

    def test_network_error_raises_without_token(self):
        token = "secret-token"

        def fake_urlopen(request, timeout):
            raise urllib.error.URLError("connection failed")

        with patch("urllib.request.urlopen", fake_urlopen):
            with self.assertRaises(GitHubCommentError) as ctx:
                post_pr_comment("owner", "repo", 1, "body", token)

        self.assertNotIn(token, str(ctx.exception))
        self.assertIn("network error", str(ctx.exception))

    def test_invalid_json_response_raises(self):
        def fake_urlopen(request, timeout):
            return _RawResponse(201, b"{bad")

        with patch("urllib.request.urlopen", fake_urlopen):
            with self.assertRaisesRegex(GitHubCommentError, "valid JSON"):
                post_pr_comment("owner", "repo", 1, "body", "secret-token")

    def test_unexpected_response_shape_raises(self):
        def fake_urlopen(request, timeout):
            return _FakeResponse(201, {"body": "missing id"})

        with patch("urllib.request.urlopen", fake_urlopen):
            with self.assertRaisesRegex(GitHubCommentError, "unexpected shape"):
                post_pr_comment("owner", "repo", 1, "body", "secret-token")

    def test_post_body_is_capped(self):
        def fake_urlopen(request, timeout):
            payload = json.loads(request.data.decode("utf-8"))
            self.assertLessEqual(len(payload["body"]), MAX_COMMENT_BODY_CHARS)
            self.assertTrue(payload["body"].endswith(TRUNCATION_MARKER))
            return _FakeResponse(201, {"id": 123})

        with patch("urllib.request.urlopen", fake_urlopen):
            post_pr_comment("owner", "repo", 1, "x" * (MAX_COMMENT_BODY_CHARS + 10), "secret-token")


class _FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class _RawResponse(_FakeResponse):
    def __init__(self, status, body):
        self.status = status
        self.body = body

    def read(self):
        return self.body


if __name__ == "__main__":
    unittest.main()
