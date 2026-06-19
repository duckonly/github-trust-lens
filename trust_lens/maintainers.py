from __future__ import annotations

import base64
import re
from collections import defaultdict
from typing import Any


DECLARED_MAINTAINER_PATHS = {
    "CODEOWNERS": [".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"],
    "MAINTAINERS": [".github/MAINTAINERS", "MAINTAINERS", "docs/MAINTAINERS"],
}


def infer_maintainers(
    declared_logins: set[str],
    merged_prs: list[dict[str, Any]],
    releases: list[dict[str, Any]],
    pr_reviews: dict[int, list[dict[str, Any]]] | None = None,
    issue_events: dict[int, list[dict[str, Any]]] | None = None,
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    pr_reviews = pr_reviews or {}
    issue_events = issue_events or {}

    def record(login: str) -> dict[str, Any]:
        normalized = login.strip()
        if normalized not in records:
            records[normalized] = {
                "login": normalized,
                "role": "contributor",
                "confidence": 0,
                "hard_score": 0,
                "soft_score": 0,
                "signals": defaultdict(int),
                "sources": [],
            }
        return records[normalized]

    for login in sorted(declared_logins):
        if is_human_login(login):
            item = record(login)
            item["hard_score"] += 4
            item["signals"]["declared_in_ownership_file"] += 1
            item["sources"].append("ownership_file")

    for pr in merged_prs:
        merger = (pr.get("merged_by") or {}).get("login")
        if merger and is_human_login(merger):
            item = record(merger)
            item["hard_score"] += 5
            item["signals"]["merged_pr"] += 1
            item["sources"].append(f"pr:{pr.get('number')}")

    for release in releases:
        author = (release.get("author") or {}).get("login")
        if author and is_human_login(author):
            item = record(author)
            item["hard_score"] += 5
            item["signals"]["created_release"] += 1
            item["sources"].append(f"release:{release.get('tag_name')}")

    seen_review_signals = set()
    for pr_number, reviews in pr_reviews.items():
        for review in reviews:
            state = review.get("state")
            login = (review.get("user") or {}).get("login")
            signal_key = (login, pr_number)
            if (
                state in {"APPROVED", "CHANGES_REQUESTED"}
                and login
                and is_human_login(login)
                and signal_key not in seen_review_signals
            ):
                seen_review_signals.add(signal_key)
                item = record(login)
                item["soft_score"] += 2
                item["signals"]["reviewed_pr"] += 1
                item["sources"].append(f"review:{pr_number}")

    closer_events = {"closed", "labeled", "unlabeled", "assigned", "milestoned"}
    seen_issue_signals = set()
    for issue_number, events in issue_events.items():
        for event in events:
            login = (event.get("actor") or {}).get("login")
            event_name = event.get("event")
            signal_key = (login, issue_number, event_name)
            if (
                event_name in closer_events
                and login
                and is_human_login(login)
                and signal_key not in seen_issue_signals
            ):
                seen_issue_signals.add(signal_key)
                item = record(login)
                item["soft_score"] += 2 if event_name == "closed" else 1
                item["signals"][f"issue_{event_name}"] += 1
                item["sources"].append(f"issue:{issue_number}")

    for item in records.values():
        hard_score = item["hard_score"]
        soft_score = item["soft_score"]
        item["confidence"] = hard_score + soft_score
        if item["signals"].get("declared_in_ownership_file"):
            item["role"] = "declared_maintainer"
        elif item["signals"].get("merged_pr", 0) >= 2 or item["signals"].get("created_release"):
            item["role"] = "active_maintainer"
        elif soft_score >= 6:
            item["role"] = "probable_maintainer"
        elif soft_score >= 3:
            item["role"] = "trusted_contributor"
        else:
            item["role"] = "contributor"
        item["signals"] = dict(sorted(item["signals"].items()))
        item["sources"] = sorted(set(item["sources"]))[:20]

    return dict(sorted(records.items()))


def extract_declared_maintainers(contents_by_path: dict[str, str]) -> set[str]:
    logins = set()
    for path, content in contents_by_path.items():
        if path.endswith("CODEOWNERS"):
            logins.update(extract_codeowners_logins(content))
        else:
            logins.update(extract_maintainers_logins(content))
    return {login for login in logins if is_human_login(login)}


def decode_content_file(content_file: dict[str, Any] | list[Any] | None) -> str | None:
    if not isinstance(content_file, dict):
        return None
    encoded = content_file.get("content")
    if not encoded:
        return None
    try:
        return base64.b64decode(encoded).decode("utf-8", errors="replace")
    except Exception:
        return None


def extract_codeowners_logins(content: str) -> set[str]:
    logins = set()
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for mention in re.findall(r"@([A-Za-z0-9-]+(?:/[A-Za-z0-9-]+)?)", stripped):
            if "/" not in mention:
                logins.add(mention)
    return logins


def extract_maintainers_logins(content: str) -> set[str]:
    logins = set()
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        mentions = re.findall(r"@([A-Za-z0-9-]+)", stripped)
        if mentions:
            logins.update(mentions)
            continue
        if re.fullmatch(r"[A-Za-z0-9-]{1,39}", stripped):
            logins.add(stripped)
    return logins


def is_human_login(login: str) -> bool:
    lowered = login.lower()
    return not (lowered.endswith("[bot]") or lowered.endswith("-bot") or lowered in {"dependabot", "renovate"})
