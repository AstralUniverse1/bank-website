from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from review_runner import (
    dry_run_github,
    dry_run_github_followup,
    dry_run_local,
    run_github_followup_review,
    run_github_review,
    run_local_review,
)
from sanitizer import render_review_input


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an AI PR review.")
    parser.add_argument("--repo-path", default=".")
    parser.add_argument("--project-context", required=True)
    parser.add_argument("--pr-summary", required=True)
    parser.add_argument("--pr-description", default="")
    parser.add_argument("--prompt", default="qa_review")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--github",
        action="store_true",
        help="Use GitHub Actions PR context and post the review as a PR comment.",
    )
    parser.add_argument(
        "--follow-up",
        action="store_true",
        help="Use GitHub issue_comment context for a stateless follow-up review.",
    )
    args = parser.parse_args()

    try:
        if args.dry_run:
            if args.github and args.follow_up:
                sanitized_input = dry_run_github_followup(
                    repo_path=args.repo_path,
                    project_context=args.project_context,
                    pr_summary=args.pr_summary,
                )
            elif args.github:
                sanitized_input = dry_run_github(
                    repo_path=args.repo_path,
                    project_context=args.project_context,
                    pr_summary=args.pr_summary,
                )
            else:
                sanitized_input = dry_run_local(
                    repo_path=args.repo_path,
                    project_context=args.project_context,
                    pr_summary=args.pr_summary,
                    pr_description=args.pr_description,
                )
            print(render_review_input(sanitized_input))
            return 0

        if args.github and args.follow_up:
            result = run_github_followup_review(
                repo_path=args.repo_path,
                project_context=args.project_context,
                pr_summary=args.pr_summary,
                prompt_name=args.prompt,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0

        if args.github:
            result = run_github_review(
                repo_path=args.repo_path,
                project_context=args.project_context,
                pr_summary=args.pr_summary,
                prompt_name=args.prompt,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0

        result = run_local_review(
            repo_path=args.repo_path,
            project_context=args.project_context,
            pr_summary=args.pr_summary,
            pr_description=args.pr_description,
            prompt_name=args.prompt,
        )
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
