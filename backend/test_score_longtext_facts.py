import csv
import tempfile
import unittest
from pathlib import Path

from backend.score_longtext_facts import score


class LongtextFactsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "claims.csv"

    def write_rows(self, rows):
        with self.path.open("w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=["sample_id", "system", "claim_id", "correct", "evidence"])
            writer.writeheader()
            writer.writerows(rows)

    def test_paired_article_mean_and_pooled_accuracy(self):
        self.write_rows([
            {"sample_id": "a", "system": "baseline", "claim_id": "1", "correct": "1", "evidence": "source a"},
            {"sample_id": "a", "system": "baseline", "claim_id": "2", "correct": "0", "evidence": "source a"},
            {"sample_id": "b", "system": "baseline", "claim_id": "1", "correct": "0", "evidence": "source b"},
            {"sample_id": "a", "system": "candidate", "claim_id": "1", "correct": "1", "evidence": "source a"},
            {"sample_id": "b", "system": "candidate", "claim_id": "1", "correct": "1", "evidence": "source b"},
        ])
        result = score(self.path, "base-model", "prompt=v1", "new-pipeline", "prompt=v2")
        self.assertEqual(result["articles"], 2)
        self.assertEqual(result["baseline"]["claims"], 3)
        self.assertAlmostEqual(result["baseline"]["pooled_accuracy"], 1 / 3)
        self.assertEqual(result["baseline"]["article_mean_accuracy"], 0.25)
        self.assertEqual(result["candidate"]["article_mean_accuracy"], 1.0)
        self.assertEqual(result["delta_percentage_points"], 75.0)

    def test_rejects_unpaired_samples_and_missing_evidence(self):
        rows = [
            {"sample_id": "a", "system": "baseline", "claim_id": "1", "correct": "1", "evidence": "source"},
            {"sample_id": "b", "system": "candidate", "claim_id": "1", "correct": "1", "evidence": "source"},
        ]
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "同一批文章"):
            score(self.path, "base", "v1", "new", "v2")
        rows[1]["sample_id"] = "a"
        rows[1]["evidence"] = ""
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "evidence"):
            score(self.path, "base", "v1", "new", "v2")


if __name__ == "__main__":
    unittest.main()
