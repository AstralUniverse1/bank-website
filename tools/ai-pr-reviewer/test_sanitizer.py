import json
import unittest
from unittest.mock import patch

from review_contract import ChangedFile, ConversationComment
from sanitizer import render_review_input, sanitize_review_input


class SanitizerTests(unittest.TestCase):
    def test_preserves_and_enriches_modified_file_metadata(self):
        result = sanitize_review_input(
            project_context="ctx",
            pr_summary="summary",
            changed_files=[ChangedFile(path="app.py", status="modified")],
            diff=_diff_for("app.py", ["+new line", "-old line"]),
        )

        self.assertEqual(result.changed_files[0].path, "app.py")
        self.assertEqual(result.changed_files[0].status, "modified")
        self.assertEqual(result.changed_files[0].added_lines, 1)
        self.assertEqual(result.changed_files[0].deleted_lines, 1)
        self.assertEqual(result.changed_files[0].extension, ".py")
        self.assertEqual(result.changed_files[0].file_category, "source")
        self.assertFalse(result.changed_files[0].is_test_file)
        self.assertEqual(result.diff_stats.total_files_changed, 1)
        self.assertEqual(result.diff_stats.total_added_lines, 1)
        self.assertEqual(result.diff_stats.total_deleted_lines, 1)
        self.assertFalse(result.diff_stats.input_truncated)

    def test_preserves_renamed_file_metadata(self):
        result = sanitize_review_input(
            project_context="ctx",
            pr_summary="summary",
            changed_files=[
                ChangedFile(path="new.py", status="renamed", old_path="legacy.py")
            ],
            diff="+ change",
        )

        self.assertEqual(result.changed_files[0].path, "new.py")
        self.assertEqual(result.changed_files[0].old_path, "legacy.py")

    def test_preserves_binary_file_metadata(self):
        result = sanitize_review_input(
            project_context="ctx",
            pr_summary="summary",
            changed_files=[
                ChangedFile(path="image.png", status="modified", is_binary=True)
            ],
            diff="",
        )

        self.assertTrue(result.changed_files[0].is_binary)

    def test_filters_unsafe_paths(self):
        result = sanitize_review_input(
            project_context="ctx",
            pr_summary="summary",
            changed_files=[
                ChangedFile(path="../secret.py", status="modified"),
                ChangedFile(path="/abs.py", status="modified"),
                ChangedFile(path="safe.py", status="modified"),
            ],
            diff="+ token=abc123",
        )

        self.assertEqual([file.path for file in result.changed_files], ["safe.py"])

    def test_render_outputs_json_friendly_metadata(self):
        result = sanitize_review_input(
            project_context="ctx api_key=secret",
            pr_summary="summary",
            pr_description="body password=secret",
            project_rules=["Prefer tests for auth token=abc123"],
            changed_files=[ChangedFile(path="app.py", status="modified")],
            diff="+ token=abc123",
        )

        payload = json.loads(render_review_input(result))
        self.assertEqual(payload["changed_files"][0]["path"], "app.py")
        self.assertEqual(payload["changed_files"][0]["extension"], ".py")
        self.assertEqual(payload["changed_files"][0]["file_category"], "source")
        self.assertEqual(payload["diff_stats"]["total_files_changed"], 1)
        self.assertEqual(payload["review_hints"]["possible_missing_test_coverage"], ["app.py"])
        self.assertIn("pull_request_target", " ".join(payload["reviewer_safety_rules"]))
        self.assertEqual(payload["project_rules"], ["Prefer tests for auth [REDACTED]"])
        self.assertEqual(payload["project_context"], "ctx [REDACTED]")
        self.assertEqual(payload["pr_description"], "body [REDACTED]")
        self.assertEqual(payload["diff"], "+ [REDACTED]")
        self.assertEqual(payload["conversation"]["comments"], [])

    def test_sanitizes_conversation_and_preserves_full_comments_only(self):
        comments = [
            ConversationComment(
                author="alice",
                author_type="MEMBER",
                created_at="2026-05-31T00:00:00Z",
                body="/ai-reviewer small token=abc123",
            ),
            ConversationComment(
                author="bob",
                author_type="MEMBER",
                created_at="2026-05-31T00:01:00Z",
                body="/ai-reviewer " + "x" * 500,
            ),
            ConversationComment(
                author="github-actions[bot]",
                author_type="NONE",
                created_at="2026-05-31T00:02:00Z",
                body="## AI PR Review\nlatest",
                is_bot=True,
                is_triggering=True,
            ),
        ]

        with patch("sanitizer.MAX_CONVERSATION_CHARS", 420):
            result = sanitize_review_input(
                project_context="ctx",
                pr_summary="summary",
                changed_files=[ChangedFile(path="app.py", status="modified")],
                diff="+ change",
                conversation_comments=comments,
            )

        bodies = [comment.body for comment in result.conversation.comments]
        self.assertIn("## AI PR Review\nlatest", bodies)
        self.assertNotIn("/ai-reviewer " + "x" * 500, bodies)
        self.assertTrue(all("[TRUNCATED]" not in body for body in bodies))
        self.assertEqual(result.conversation.total_relevant_comments, 3)
        self.assertGreaterEqual(result.conversation.omitted_comments, 1)

    def test_classifies_tests_ci_requirements_and_security_paths(self):
        result = sanitize_review_input(
            project_context="ctx",
            pr_summary="summary",
            changed_files=[
                ChangedFile(path="test_app.py", status="modified"),
                ChangedFile(path=".github/workflows/ai-pr-review.yml", status="modified"),
                ChangedFile(path="requirements.txt", status="modified"),
                ChangedFile(path="src/auth/token.py", status="modified"),
            ],
            diff="",
        )

        files = {file.path: file for file in result.changed_files}
        self.assertTrue(files["test_app.py"].is_test_file)
        self.assertTrue(files[".github/workflows/ai-pr-review.yml"].is_ci_file)
        self.assertEqual(files["requirements.txt"].file_category, "config")
        self.assertTrue(files["src/auth/token.py"].is_security_sensitive_path)
        self.assertTrue(result.review_hints.touched_tests)
        self.assertTrue(result.review_hints.requirements_changed)
        self.assertTrue(result.review_hints.workflow_changed)
        self.assertFalse(result.review_hints.touched_source_without_tests)

    def test_flags_source_without_tests(self):
        result = sanitize_review_input(
            project_context="ctx",
            pr_summary="summary",
            changed_files=[ChangedFile(path="src/app.py", status="modified")],
            diff="",
        )

        self.assertTrue(result.review_hints.touched_source_without_tests)
        self.assertEqual(result.review_hints.possible_missing_test_coverage, ["src/app.py"])

    def test_truncates_sanitized_diff_when_payload_exceeds_limit(self):
        long_diff = _diff_for("app.py", ["+" + "x" * 100 for _ in range(40)])

        with patch("sanitizer.MAX_INPUT_CHARS", 3000):
            result = sanitize_review_input(
                project_context="ctx",
                pr_summary="summary",
                changed_files=[ChangedFile(path="app.py", status="modified")],
                diff=long_diff,
            )

        payload = render_review_input(result)
        self.assertLessEqual(len(payload), 3000)
        self.assertTrue(result.diff_stats.input_truncated)
        self.assertNotIn("token=", payload)


def _diff_for(path, lines):
    return "\n".join(
        [
            f"diff --git a/{path} b/{path}",
            f"--- a/{path}",
            f"+++ b/{path}",
            *lines,
        ]
    )


if __name__ == "__main__":
    unittest.main()
