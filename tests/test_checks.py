import unittest

from trust_lens.checks import check_bus_factor, check_issue_response, check_maintainer_discoverability


class CheckTests(unittest.TestCase):
    def test_discoverability_scores_with_owner_docs(self):
        result = check_maintainer_discoverability({"CODEOWNERS", "GOVERNANCE"})
        self.assertEqual(result["score"], 100)

    def test_bus_factor_penalizes_single_merger(self):
        prs = [{"merged_by": {"login": "alice"}} for _ in range(10)]
        result = check_bus_factor(prs)
        self.assertLess(result["score"], 50)

    def test_bus_factor_rewards_distribution(self):
        prs = [{"merged_by": {"login": login}} for login in ["a", "b", "c", "d"] * 3]
        result = check_bus_factor(prs)
        self.assertGreaterEqual(result["score"], 80)

    def test_issue_handling_rewards_explainable_closure(self):
        issues = [
            {"number": 1, "comments": 1, "state_reason": "completed", "created_at": "2026-01-01T00:00:00Z", "closed_at": "2026-01-02T00:00:00Z"},
            {"number": 2, "comments": 1, "state_reason": "completed", "created_at": "2026-01-01T00:00:00Z", "closed_at": "2026-01-03T00:00:00Z"},
        ]
        result = check_issue_response(issues)
        self.assertEqual(result["id"], "issue_handling_transparency")
        self.assertGreaterEqual(result["score"], 49)

    def test_issue_handling_discussion_alone_is_not_full_score(self):
        issues = [
            {"number": 1, "comments": 1, "created_at": "2026-01-01T00:00:00Z", "closed_at": "2026-06-01T00:00:00Z"},
            {"number": 2, "comments": 1, "created_at": "2026-01-01T00:00:00Z", "closed_at": "2026-06-01T00:00:00Z"},
        ]
        result = check_issue_response(issues)
        self.assertLess(result["score"], 40)
