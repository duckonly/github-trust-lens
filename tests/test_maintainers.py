import unittest

from trust_lens.maintainers import extract_codeowners_logins, extract_maintainers_logins, infer_maintainers


class MaintainerInferenceTests(unittest.TestCase):
    def test_extract_codeowners_ignores_teams(self):
        content = "*.py @alice @org/security-team\n/docs @bob\n"
        self.assertEqual(extract_codeowners_logins(content), {"alice", "bob"})

    def test_extract_maintainers_accepts_mentions_and_plain_logins(self):
        content = "@alice\nbob\n# comment\n"
        self.assertEqual(extract_maintainers_logins(content), {"alice", "bob"})

    def test_probable_maintainer_from_soft_activity(self):
        inferred = infer_maintainers(
            declared_logins=set(),
            merged_prs=[],
            releases=[],
            pr_reviews={
                1: [{"state": "APPROVED", "user": {"login": "alice"}}],
                2: [{"state": "CHANGES_REQUESTED", "user": {"login": "alice"}}],
            },
            issue_events={3: [{"event": "closed", "actor": {"login": "alice"}}]},
        )
        self.assertEqual(inferred["alice"]["role"], "probable_maintainer")

    def test_multiple_reviews_on_same_pr_count_once(self):
        inferred = infer_maintainers(
            declared_logins=set(),
            merged_prs=[],
            releases=[],
            pr_reviews={
                1: [
                    {"state": "APPROVED", "user": {"login": "alice"}},
                    {"state": "CHANGES_REQUESTED", "user": {"login": "alice"}},
                ],
            },
        )
        self.assertEqual(inferred["alice"]["signals"]["reviewed_pr"], 1)
        self.assertEqual(inferred["alice"]["soft_score"], 2)

    def test_active_maintainer_from_repeated_merges(self):
        inferred = infer_maintainers(
            declared_logins=set(),
            merged_prs=[
                {"number": 1, "merged_by": {"login": "alice"}},
                {"number": 2, "merged_by": {"login": "alice"}},
            ],
            releases=[],
        )
        self.assertEqual(inferred["alice"]["role"], "active_maintainer")
