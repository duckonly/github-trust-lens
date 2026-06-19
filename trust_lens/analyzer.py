from __future__ import annotations

from typing import Any

from .checks import (
    DOC_PATHS,
    check_account_maturity,
    check_bus_factor,
    check_governance_surface,
    check_inferred_maintainer_roles,
    check_issue_response,
    check_maintainer_discoverability,
    check_profile_transparency,
    check_release_notes,
    check_suspicious_churn,
)
from .github_client import GitHubClient
from .maintainers import (
    DECLARED_MAINTAINER_PATHS,
    decode_content_file,
    extract_declared_maintainers,
    infer_maintainers,
)
from .scoring import grade_for


SCORECARD_CHECKS_EXCLUDED = [
    "Binary-Artifacts",
    "Branch-Protection",
    "CI-Tests",
    "CII-Best-Practices",
    "Code-Review",
    "Contributors",
    "Dependency-Update-Tool",
    "Fuzzing",
    "License",
    "Maintained",
    "Packaging",
    "Pinned-Dependencies",
    "SAST",
    "SBOM",
    "Security-Policy",
    "Signed-Releases",
    "Token-Permissions",
    "Vulnerabilities",
    "Webhooks",
]


def analyze_repository(
    client: GitHubClient,
    repo_slug: str,
    merged_pr_limit: int = 50,
    issue_limit: int = 40,
    release_limit: int = 10,
) -> dict[str, Any]:
    owner, name = repo_slug.split("/", 1)
    repo = client.repo(owner, name)
    found_docs = discover_docs(client, owner, name)
    declared_maintainer_files = fetch_declared_maintainer_files(client, owner, name)
    declared_maintainers = extract_declared_maintainers(declared_maintainer_files)
    pulls = fetch_merged_pulls(client, owner, name, merged_pr_limit)
    issues = client.issues(owner, name, per_page=issue_limit)
    releases = client.releases(owner, name, per_page=release_limit)
    pr_reviews = fetch_pr_reviews(client, owner, name, pulls[: min(len(pulls), 20)])
    inspected_issues = issues[: min(len(issues), 20)]
    issue_events = fetch_issue_events(client, owner, name, inspected_issues)
    issue_comments = fetch_issue_comments(client, owner, name, inspected_issues)
    inferred_maintainers = infer_maintainers(declared_maintainers, pulls, releases, pr_reviews, issue_events)
    maintainer_users = fetch_maintainer_users(client, inferred_maintainers)

    checks = [
        check_maintainer_discoverability(found_docs),
        check_governance_surface(found_docs),
        check_inferred_maintainer_roles(inferred_maintainers),
        check_bus_factor(pulls),
        check_account_maturity(maintainer_users),
        check_profile_transparency(maintainer_users),
        check_issue_response(issues, issue_events, issue_comments, inferred_maintainers),
        check_release_notes(releases),
        check_suspicious_churn(pulls),
    ]

    total_weight = sum(check["weight"] for check in checks)
    score = round(sum(check["score"] * check["weight"] for check in checks) / total_weight, 1)

    return {
        "repository": repo.get("full_name", repo_slug),
        "description": repo.get("description"),
        "archived": repo.get("archived"),
        "private": repo.get("private"),
        "score": score,
        "grade": grade_for(score),
        "scope": {
            "purpose": "Complementary trust analysis; intentionally does not duplicate OpenSSF Scorecard checks.",
            "excluded_openssf_scorecard_checks": SCORECARD_CHECKS_EXCLUDED,
        },
        "maintainers": inferred_maintainers,
        "checks": checks,
    }


def discover_docs(client: GitHubClient, owner: str, name: str) -> set[str]:
    found = set()
    for doc_name, paths in DOC_PATHS.items():
        for path in paths:
            if client.contents(owner, name, path):
                found.add(doc_name)
                break
    return found


def fetch_declared_maintainer_files(client: GitHubClient, owner: str, name: str) -> dict[str, str]:
    files = {}
    for paths in DECLARED_MAINTAINER_PATHS.values():
        for path in paths:
            content = decode_content_file(client.contents(owner, name, path))
            if content:
                files[path] = content
                break
    return files


def fetch_pr_reviews(
    client: GitHubClient,
    owner: str,
    name: str,
    pulls: list[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    reviews = {}
    for pr in pulls:
        number = pr.get("number")
        if number:
            reviews[number] = client.pull_reviews(owner, name, number)
    return reviews


def fetch_merged_pulls(
    client: GitHubClient,
    owner: str,
    name: str,
    limit: int,
    max_pages: int = 5,
) -> list[dict[str, Any]]:
    merged = []
    seen_numbers = set()
    per_page = min(100, max(30, limit))

    for page in range(1, max_pages + 1):
        candidates = client.pulls(owner, name, per_page=per_page, page=page)
        if not candidates:
            break

        for candidate in candidates:
            number = candidate.get("number")
            if not candidate.get("merged_at") or not number or number in seen_numbers:
                continue
            seen_numbers.add(number)
            merged.append(client.pull(owner, name, number))
            if len(merged) >= limit:
                return merged

        if len(candidates) < per_page:
            break

    return merged


def fetch_issue_events(
    client: GitHubClient,
    owner: str,
    name: str,
    issues: list[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    events = {}
    for issue in issues:
        if "pull_request" in issue:
            continue
        number = issue.get("number")
        if number:
            events[number] = client.issue_events(owner, name, number)
    return events


def fetch_issue_comments(
    client: GitHubClient,
    owner: str,
    name: str,
    issues: list[dict[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    comments = {}
    for issue in issues:
        if "pull_request" in issue:
            continue
        number = issue.get("number")
        if number:
            comments[number] = client.issue_comments(owner, name, number)
    return comments


def fetch_maintainer_users(client: GitHubClient, maintainers: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    users = {}
    for login, item in maintainers.items():
        if item["role"] in {"declared_maintainer", "active_maintainer", "probable_maintainer"}:
            users[login] = client.user(login)
    return users
