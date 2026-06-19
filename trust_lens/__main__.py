from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .analyzer import analyze_repository
from .github_client import GitHubClient, GitHubError
from .reporting import format_human_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trust-lens",
        description="Analyze GitHub repository trust signals not covered by OpenSSF Scorecard.",
    )
    parser.add_argument("repo", help="Repository in owner/name format, for example: ossf/scorecard")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a human report.")
    parser.add_argument("--output", type=Path, help="Write the report to this file.")
    parser.add_argument("--token", help="GitHub token. Defaults to GITHUB_TOKEN.")
    parser.add_argument("--merged-prs", type=int, default=50, help="Merged PRs to inspect. Default: 50.")
    parser.add_argument("--issues", type=int, default=40, help="Closed issues to inspect. Default: 40.")
    parser.add_argument("--releases", type=int, default=10, help="Releases to inspect. Default: 10.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if "/" not in args.repo:
        print("Repository must use owner/name format.", file=sys.stderr)
        return 2

    token = args.token or os.getenv("GITHUB_TOKEN")
    client = GitHubClient(token=token)

    try:
        report = analyze_repository(
            client,
            args.repo,
            merged_pr_limit=args.merged_prs,
            issue_limit=args.issues,
            release_limit=args.releases,
        )
    except GitHubError as exc:
        print(f"GitHub API error: {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(report, indent=2, ensure_ascii=False) if args.json else format_human_report(report)

    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
