from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class GitHubError(RuntimeError):
    pass


@dataclass
class GitHubClient:
    token: str | None = None
    api_base: str = "https://api.github.com"
    timeout: int = 20

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.api_base}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "github-repo-trust-lens",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = response.read().decode("utf-8")
                if not payload:
                    return None
                return json.loads(payload)
        except HTTPError as exc:
            if exc.code == 403 and exc.headers.get("X-RateLimit-Remaining") == "0":
                reset = exc.headers.get("X-RateLimit-Reset")
                suffix = ""
                if reset and reset.isdigit():
                    wait = max(int(reset) - int(time.time()), 0)
                    suffix = f" Rate limit resets in about {wait} seconds."
                raise GitHubError(f"rate limit exceeded.{suffix}") from exc
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                body = ""
            raise GitHubError(f"{exc.code} for {url}: {body[:300]}") from exc
        except URLError as exc:
            raise GitHubError(str(exc)) from exc

    def repo(self, owner: str, name: str) -> dict[str, Any]:
        return self.get(f"/repos/{owner}/{name}")

    def contents(self, owner: str, name: str, path: str) -> dict[str, Any] | list[Any] | None:
        try:
            return self.get(f"/repos/{owner}/{name}/contents/{path}")
        except GitHubError as exc:
            if "404" in str(exc):
                return None
            raise

    def pulls(self, owner: str, name: str, per_page: int = 50, page: int = 1) -> list[dict[str, Any]]:
        return self.get(
            f"/repos/{owner}/{name}/pulls",
            {"state": "closed", "sort": "updated", "direction": "desc", "per_page": per_page, "page": page},
        )

    def pull(self, owner: str, name: str, pull_number: int) -> dict[str, Any]:
        return self.get(f"/repos/{owner}/{name}/pulls/{pull_number}")

    def issues(self, owner: str, name: str, per_page: int = 40) -> list[dict[str, Any]]:
        return self.get(
            f"/repos/{owner}/{name}/issues",
            {"state": "closed", "sort": "updated", "direction": "desc", "per_page": per_page},
        )

    def issue_events(self, owner: str, name: str, issue_number: int) -> list[dict[str, Any]]:
        return self.get(f"/repos/{owner}/{name}/issues/{issue_number}/events", {"per_page": 100})

    def issue_comments(self, owner: str, name: str, issue_number: int) -> list[dict[str, Any]]:
        return self.get(f"/repos/{owner}/{name}/issues/{issue_number}/comments", {"per_page": 100})

    def pull_reviews(self, owner: str, name: str, pull_number: int) -> list[dict[str, Any]]:
        return self.get(f"/repos/{owner}/{name}/pulls/{pull_number}/reviews", {"per_page": 100})

    def releases(self, owner: str, name: str, per_page: int = 10) -> list[dict[str, Any]]:
        return self.get(f"/repos/{owner}/{name}/releases", {"per_page": per_page})

    def user(self, login: str) -> dict[str, Any]:
        return self.get(f"/users/{login}")
