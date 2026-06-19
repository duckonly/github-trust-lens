from __future__ import annotations

import argparse
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .analyzer import analyze_repository
from .github_client import GitHubClient, GitHubError


STATIC_DIR = Path(__file__).with_name("static")
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".png": "image/png",
}


class TrustLensRequestHandler(BaseHTTPRequestHandler):
    server_version = "TrustLensUI/0.1"

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._serve_static("index.html")
            return

        requested = self.path.lstrip("/")
        if requested in {"app.css", "app.js", "trust-lens-logo.png"}:
            self._serve_static(requested)
            return

        self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/api/analyze":
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return

        try:
            payload = self._read_json()
            repo = str(payload.get("repo", "")).strip()
            if "/" not in repo:
                self._send_json({"error": "Repository must use owner/name format."}, HTTPStatus.BAD_REQUEST)
                return

            token = str(payload.get("token", "")).strip() or os.getenv("GITHUB_TOKEN")
            client = GitHubClient(token=token)
            report = analyze_repository(
                client,
                repo,
                merged_pr_limit=self._bounded_int(payload.get("merged_prs"), default=50, low=10, high=100),
                issue_limit=self._bounded_int(payload.get("issues"), default=40, low=10, high=100),
                release_limit=self._bounded_int(payload.get("releases"), default=10, low=1, high=30),
            )
        except GitHubError as exc:
            self._send_json({"error": f"GitHub API error: {exc}"}, HTTPStatus.BAD_GATEWAY)
            return
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:
            self._send_json({"error": f"Unexpected server error: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json(report)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _serve_static(self, name: str) -> None:
        path = STATIC_DIR / name
        if not path.exists():
            self._send_json({"error": "Static asset missing"}, HTTPStatus.NOT_FOUND)
            return

        content = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", CONTENT_TYPES.get(path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    @staticmethod
    def _bounded_int(value: Any, default: int, low: int, high: int) -> int:
        if value in (None, ""):
            return default
        number = int(value)
        if number < low or number > high:
            raise ValueError(f"Value must be between {low} and {high}.")
        return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start the Trust Lens local web UI.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind. Default: 127.0.0.1.")
    parser.add_argument("--port", type=int, default=8787, help="Port to bind. Default: 8787.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), TrustLensRequestHandler)
    print(f"Trust Lens UI running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Trust Lens UI.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
