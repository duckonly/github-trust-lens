import unittest

from trust_lens.scoring import clamp_score, grade_for


class ScoringTests(unittest.TestCase):
    def test_clamp_score(self):
        self.assertEqual(clamp_score(-1), 0)
        self.assertEqual(clamp_score(50), 50)
        self.assertEqual(clamp_score(120), 100)

    def test_grade_for(self):
        self.assertEqual(grade_for(90), "A")
        self.assertEqual(grade_for(75), "B")
        self.assertEqual(grade_for(60), "C")
        self.assertEqual(grade_for(45), "D")
        self.assertEqual(grade_for(10), "E")
