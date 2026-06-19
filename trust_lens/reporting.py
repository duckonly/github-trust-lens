from __future__ import annotations

from typing import Any


def format_human_report(report: dict[str, Any]) -> str:
    lines = [
        f"# Trust Lens Report: {report['repository']}",
        "",
        f"Score: {report['score']}/100 ({report['grade']})",
        "",
        "Scope: complementary trust analysis only. OpenSSF Scorecard checks are intentionally excluded.",
        "",
        "Checks:",
    ]

    for check in report["checks"]:
        lines.append(f"- {check['title']}: {check['score']}/100 - {check['summary']}")

    maintainers = report.get("maintainers") or {}
    visible_maintainers = [item for item in maintainers.values() if item.get("role") != "contributor"]
    if visible_maintainers:
        lines.extend(["", "Inferred maintainers:"])
        for item in visible_maintainers:
            lines.append(f"- {item['login']}: {item['role']} ({item['confidence']} confidence)")

    lines.extend(
        [
            "",
            "Excluded OpenSSF Scorecard checks:",
            ", ".join(report["scope"]["excluded_openssf_scorecard_checks"]),
        ]
    )
    return "\n".join(lines)
