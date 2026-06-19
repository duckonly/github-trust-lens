import unittest

from trust_lens.analyzer import fetch_merged_pulls


class FakeGitHubClient:
    def __init__(self):
        self.detail_calls = []

    def pulls(self, owner, name, per_page=50, page=1):
        if page > 1:
            return []
        return [
            {"number": 3, "merged_at": None},
            {"number": 2, "merged_at": "2026-01-02T00:00:00Z"},
            {"number": 1, "merged_at": "2026-01-01T00:00:00Z"},
        ]

    def pull(self, owner, name, pull_number):
        self.detail_calls.append(pull_number)
        return {
            "number": pull_number,
            "merged_at": "2026-01-01T00:00:00Z",
            "merged_by": {"login": f"maintainer-{pull_number}"},
        }


class AnalyzerTests(unittest.TestCase):
    def test_fetch_merged_pulls_loads_detail_for_merged_candidates(self):
        client = FakeGitHubClient()
        pulls = fetch_merged_pulls(client, "owner", "repo", limit=2)

        self.assertEqual(client.detail_calls, [2, 1])
        self.assertEqual([pull["merged_by"]["login"] for pull in pulls], ["maintainer-2", "maintainer-1"])
