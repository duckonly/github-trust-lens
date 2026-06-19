from __future__ import annotations

import re
from collections import Counter
from statistics import median
from typing import Any

from .scoring import account_age_years, clamp_score, days_between, inverse_ratio_score, ratio_score


DOC_PATHS = {
    "CODEOWNERS": [".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"],
    "MAINTAINERS": [".github/MAINTAINERS", "MAINTAINERS", "docs/MAINTAINERS"],
    "GOVERNANCE": [".github/GOVERNANCE.md", "GOVERNANCE.md", "docs/GOVERNANCE.md"],
    "SUPPORT": [".github/SUPPORT.md", "SUPPORT.md", "docs/SUPPORT.md"],
    "CONTRIBUTING": [".github/CONTRIBUTING.md", "CONTRIBUTING.md", "docs/CONTRIBUTING.md"],
}


def check_maintainer_discoverability(files: set[str]) -> dict[str, Any]:
    found = sorted(name for name in ("CODEOWNERS", "MAINTAINERS", "GOVERNANCE") if name in files)
    score = 100 if len(found) >= 2 else 70 if found else 20
    return {
        "id": "maintainer_discoverability",
        "title": "Maintainer discoverability",
        "score": score,
        "weight": 1.1,
        "summary": "Maintainer responsibility is documented." if found else "No maintainer ownership files were found.",
        "evidence": {"found": found},
    }


def check_governance_surface(files: set[str]) -> dict[str, Any]:
    found = sorted(name for name in ("GOVERNANCE", "SUPPORT", "CONTRIBUTING") if name in files)
    score = min(100, len(found) * 34)
    return {
        "id": "governance_surface",
        "title": "Governance surface",
        "score": score,
        "weight": 0.8,
        "summary": "Non-security governance and participation docs are present." if found else "No non-security governance docs were found.",
        "evidence": {"found": found},
    }


def check_inferred_maintainer_roles(maintainers: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not maintainers:
        return {
            "id": "inferred_maintainer_roles",
            "title": "Inferred maintainer roles",
            "score": 35,
            "weight": 1.0,
            "summary": "No maintainer-like activity was available.",
            "evidence": {},
        }

    role_counts = Counter(item["role"] for item in maintainers.values())
    strong_roles = role_counts.get("declared_maintainer", 0) + role_counts.get("active_maintainer", 0)
    probable = role_counts.get("probable_maintainer", 0)
    score = clamp_score(strong_roles * 30 + probable * 18 + role_counts.get("trusted_contributor", 0) * 8)
    summary = f"Found {strong_roles} declared/active and {probable} probable maintainers from files and activity."
    evidence = {
        "role_counts": dict(sorted(role_counts.items())),
        "maintainers": {
            login: {
                "role": item["role"],
                "confidence": item["confidence"],
                "signals": item["signals"],
            }
            for login, item in maintainers.items()
            if item["role"] != "contributor"
        },
    }
    return {
        "id": "inferred_maintainer_roles",
        "title": "Inferred maintainer roles",
        "score": round(score, 1),
        "weight": 1.0,
        "summary": summary,
        "evidence": evidence,
    }


def check_bus_factor(merged_prs: list[dict[str, Any]]) -> dict[str, Any]:
    mergers = [pr.get("merged_by", {}).get("login") for pr in merged_prs if pr.get("merged_by")]
    mergers = [login for login in mergers if login]
    if not mergers:
        return {
            "id": "maintainer_bus_factor",
            "title": "Maintainer bus factor",
            "score": 35,
            "weight": 1.4,
            "summary": "No recent merged PR merger data was available.",
            "evidence": {"merged_prs": 0},
        }

    counts = Counter(mergers)
    top_login, top_count = counts.most_common(1)[0]
    top_ratio = top_count / len(mergers)
    distinct = len(counts)
    concentration_score = inverse_ratio_score(max(top_ratio - 0.25, 0) / 0.75)
    diversity_bonus = min(distinct / 4, 1.0) * 20
    score = clamp_score(concentration_score * 0.8 + diversity_bonus)
    return {
        "id": "maintainer_bus_factor",
        "title": "Maintainer bus factor",
        "score": round(score, 1),
        "weight": 1.4,
        "summary": f"{top_login} merged {top_count}/{len(mergers)} recent PRs.",
        "evidence": {"top_merger": top_login, "top_ratio": round(top_ratio, 3), "distinct_mergers": distinct},
    }


def check_account_maturity(users: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not users:
        return {
            "id": "maintainer_account_maturity",
            "title": "Maintainer account maturity",
            "score": 35,
            "weight": 1.1,
            "summary": "No maintainer account data was available.",
            "evidence": {},
        }

    ages = [account_age_years(user) for user in users.values()]
    repo_counts = [user.get("public_repos") or 0 for user in users.values()]
    follower_counts = [user.get("followers") or 0 for user in users.values()]
    age_component = min(median(ages) / 5, 1.0) * 55
    repo_component = min(median(repo_counts) / 20, 1.0) * 25
    follower_component = min(median(follower_counts) / 25, 1.0) * 20
    score = clamp_score(age_component + repo_component + follower_component)
    return {
        "id": "maintainer_account_maturity",
        "title": "Maintainer account maturity",
        "score": round(score, 1),
        "weight": 1.1,
        "summary": f"Median maintainer account age is {median(ages):.1f} years.",
        "evidence": {
            "median_account_age_years": round(median(ages), 2),
            "median_public_repos": median(repo_counts),
            "median_followers": median(follower_counts),
        },
    }


def check_profile_transparency(users: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not users:
        return {
            "id": "maintainer_transparency",
            "title": "Maintainer transparency",
            "score": 35,
            "weight": 0.7,
            "summary": "No maintainer profiles were available.",
            "evidence": {},
        }

    fields = ("name", "company", "blog", "location", "email", "bio")
    ratios = []
    per_user = {}
    for login, user in users.items():
        present = [field for field in fields if user.get(field)]
        ratios.append(len(present) / len(fields))
        per_user[login] = present

    score = ratio_score(sum(ratios) / len(ratios))
    return {
        "id": "maintainer_transparency",
        "title": "Maintainer transparency",
        "score": round(score, 1),
        "weight": 0.7,
        "summary": "Recent merger profiles expose public identity context.",
        "evidence": {"profile_fields_present": per_user},
    }


def check_issue_response(
    issues: list[dict[str, Any]],
    issue_events: dict[int, list[dict[str, Any]]] | None = None,
    issue_comments: dict[int, list[dict[str, Any]]] | None = None,
    maintainers: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    real_issues = [issue for issue in issues if "pull_request" not in issue]
    if not real_issues:
        return {
            "id": "issue_handling_transparency",
            "title": "Issue handling transparency",
            "score": 50,
            "weight": 0.9,
            "summary": "No recently closed issues were available.",
            "evidence": {},
        }

    issue_events = issue_events or {}
    issue_comments = issue_comments or {}
    maintainers = maintainers or {}
    maintainer_logins = {
        login
        for login, item in maintainers.items()
        if item.get("role") in {"declared_maintainer", "active_maintainer", "probable_maintainer"}
    }

    close_times = [days_between(issue.get("created_at"), issue.get("closed_at")) for issue in real_issues]
    close_times = [days for days in close_times if days is not None]
    median_close = median(close_times) if close_times else 999

    discussed = 0
    maintainer_touched = 0
    explained_closure = 0
    referenced_work = 0
    silent_closures = 0

    for issue in real_issues:
        number = issue.get("number")
        comments = issue_comments.get(number, [])
        events = issue_events.get(number, [])
        if (issue.get("comments") or 0) > 0:
            discussed += 1
        if issue_has_maintainer_touch(comments, events, maintainer_logins):
            maintainer_touched += 1
        if issue_has_explained_closure(issue, events):
            explained_closure += 1
        if issue_references_work(comments, events):
            referenced_work += 1
        if (issue.get("comments") or 0) == 0 and not issue_has_explained_closure(issue, events):
            silent_closures += 1

    total = len(real_issues)
    discussion_ratio = discussed / total
    maintainer_touch_ratio = maintainer_touched / total
    explained_closure_ratio = explained_closure / total
    reference_ratio = referenced_work / total
    silent_closure_ratio = silent_closures / total
    timing_score = max(0, 100 - min(median_close, 180) / 180 * 100)
    score = clamp_score(
        maintainer_touch_ratio * 35
        + explained_closure_ratio * 25
        + reference_ratio * 15
        + discussion_ratio * 15
        + timing_score * 0.10
        - silent_closure_ratio * 20
    )
    return {
        "id": "issue_handling_transparency",
        "title": "Issue handling transparency",
        "score": round(score, 1),
        "weight": 0.9,
        "summary": f"{explained_closure}/{total} recently closed issues had an explainable closure signal.",
        "evidence": {
            "discussion_ratio": round(discussion_ratio, 3),
            "maintainer_touch_ratio": round(maintainer_touch_ratio, 3),
            "explained_closure_ratio": round(explained_closure_ratio, 3),
            "referenced_work_ratio": round(reference_ratio, 3),
            "silent_closure_ratio": round(silent_closure_ratio, 3),
            "median_days_to_close": median_close,
        },
    }


def issue_has_maintainer_touch(
    comments: list[dict[str, Any]],
    events: list[dict[str, Any]],
    maintainer_logins: set[str],
) -> bool:
    if not maintainer_logins:
        return False
    comment_authors = {(comment.get("user") or {}).get("login") for comment in comments}
    event_actors = {(event.get("actor") or {}).get("login") for event in events}
    return bool((comment_authors | event_actors) & maintainer_logins)


def issue_has_explained_closure(issue: dict[str, Any], events: list[dict[str, Any]]) -> bool:
    state_reason = issue.get("state_reason")
    if state_reason in {"completed", "not_planned", "duplicate"}:
        return True
    explanation_events = {"closed", "referenced", "marked_as_duplicate", "labeled"}
    return any(event.get("event") in explanation_events for event in events)


def issue_references_work(comments: list[dict[str, Any]], events: list[dict[str, Any]]) -> bool:
    if any(event.get("event") in {"referenced", "cross-referenced", "connected"} for event in events):
        return True
    pattern = re.compile(r"(#[0-9]+|https://github\.com/.+/(pull|commit|releases?)/|\\b[a-f0-9]{7,40}\\b)", re.IGNORECASE)
    return any(pattern.search(comment.get("body") or "") for comment in comments)


def check_release_notes(releases: list[dict[str, Any]]) -> dict[str, Any]:
    if not releases:
        return {
            "id": "release_note_quality",
            "title": "Release note quality",
            "score": 45,
            "weight": 0.7,
            "summary": "No GitHub releases were available.",
            "evidence": {},
        }

    meaningful = []
    for release in releases:
        body = (release.get("body") or "").strip()
        name = (release.get("name") or "").strip()
        tag = (release.get("tag_name") or "").strip()
        has_notes = len(body) >= 80 or (len(body) >= 30 and any(marker in body.lower() for marker in ("fix", "change", "security", "breaking", "add")))
        meaningful.append(bool(has_notes or (name and name != tag and len(name) >= 20)))

    ratio = sum(meaningful) / len(meaningful)
    score = ratio_score(ratio)
    return {
        "id": "release_note_quality",
        "title": "Release note quality",
        "score": round(score, 1),
        "weight": 0.7,
        "summary": f"{sum(meaningful)}/{len(releases)} recent releases had meaningful notes.",
        "evidence": {"meaningful_release_note_ratio": round(ratio, 3)},
    }


def check_suspicious_churn(merged_prs: list[dict[str, Any]]) -> dict[str, Any]:
    mergers = [pr.get("merged_by", {}).get("login") for pr in merged_prs if pr.get("merged_by")]
    mergers = [login for login in mergers if login]
    if len(mergers) < 12:
        return {
            "id": "suspicious_maintainer_churn",
            "title": "Suspicious maintainer churn",
            "score": 60,
            "weight": 1.0,
            "summary": "Not enough recent merged PR data to assess churn.",
            "evidence": {"merged_prs": len(mergers)},
        }

    newest = mergers[: max(6, len(mergers) // 3)]
    older = mergers[max(6, len(mergers) // 3):]
    newest_counts = Counter(newest)
    older_set = set(older)
    top_new, top_new_count = newest_counts.most_common(1)[0]
    new_dominance = top_new_count / len(newest)
    is_new_actor = top_new not in older_set
    penalty = 70 if is_new_actor and new_dominance >= 0.6 else 30 if is_new_actor and new_dominance >= 0.4 else 0
    score = clamp_score(100 - penalty)
    return {
        "id": "suspicious_maintainer_churn",
        "title": "Suspicious maintainer churn",
        "score": score,
        "weight": 1.0,
        "summary": f"Newest PR merger leader is {top_new} with {top_new_count}/{len(newest)} merges.",
        "evidence": {"top_new_merger": top_new, "new_dominance": round(new_dominance, 3), "absent_from_older_sample": is_new_actor},
    }
