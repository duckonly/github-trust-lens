from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_github_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def days_between(start: str | None, end: str | None) -> int | None:
    start_dt = parse_github_time(start)
    end_dt = parse_github_time(end)
    if not start_dt or not end_dt:
        return None
    return max((end_dt - start_dt).days, 0)


def account_age_years(user: dict[str, Any]) -> float:
    created = parse_github_time(user.get("created_at"))
    if not created:
        return 0.0
    return max((datetime.now(timezone.utc) - created).days / 365.25, 0.0)


def clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def grade_for(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "E"


def ratio_score(ratio: float) -> float:
    return clamp_score(ratio * 100.0)


def inverse_ratio_score(ratio: float) -> float:
    return clamp_score((1.0 - ratio) * 100.0)
