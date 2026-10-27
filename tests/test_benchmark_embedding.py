import json
import tempfile
import unittest
from pathlib import Path

from backend.tools.benchmark_embedding import load_inputs, summarize


class BenchmarkInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run_dir = self.root / "run"
        (self.run_dir / "model").mkdir(parents=True)
        self.train = self.root / "train.jsonl"
        self.eval = self.root / "eval.jsonl"
        self.train.write_text('\n'.join([
            '{"query":"train 1","positive":"doc 1"}',
            '{"query":"train 2","positive":"doc 2"}',
            '{"query":"train 1","positive":"doc 1"}',
        ]), encoding="utf-8")
        self.eval.write_text('\n'.join([
            '{"query":"eval 1","positive":"answer 1"}',
            '{"query":"eval 2","positive":"answer 2"}',
        ]), encoding="utf-8")
        (self.run_dir / "run_config.json").write_text(json.dumps({
            "train": str(self.train), "eval": str(self.eval),
            "model": "nomic-ai/nomic-embed-text-v1.5", "max_length": 512,
            "query_prefix": "search_query: ", "document_prefix": "search_document: ",
            "trust_remote_code": False,
        }), encoding="utf-8")

    def test_uses_deduplicated_training_count_and_shared_eval_corpus(self):
        config, train, queries, corpus, relevant, train_digest, eval_digest = load_inputs(self.run_dir, None, None, 2)
        self.assertEqual(len(train), 2)
        self.assertEqual((len(queries), len(corpus)), (2, 2))
        self.assertEqual({frozenset(ids) for ids in relevant.values()}, {frozenset({"0"}), frozenset({"1"})})
        self.assertEqual(len(train_digest), 64)
        self.assertEqual(len(eval_digest), 64)
        self.assertNotEqual(train_digest, eval_digest)
        self.assertEqual(config["max_length"], 512)

    def test_rejects_leakage_and_k_larger_than_corpus(self):
        with self.assertRaisesRegex(ValueError, "候选文档数"):
            load_inputs(self.run_dir, None, None, 3)
        self.eval.write_text('\n'.join([
            '{"query":"train 1","positive":"answer 1"}',
            '{"query":"eval 2","positive":"answer 2"}',
        ]), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "重复"):
            load_inputs(self.run_dir, None, None, 2)

    def test_reports_same_comparison_conditions_and_percentage_points(self):
        result = summarize(
            "nomic-ai/nomic-embed-text-v1.5", 200, 20, 100, 5, "abc", "cpu",
            {"cosine_recall@5": 0.4, "cosine_mrr@5": 0.3},
            {"cosine_recall@5": 0.65, "cosine_mrr@5": 0.5},
        )
        self.assertEqual(result["training"]["pairs"], 200)
        self.assertEqual(result["training"]["loss"], "MultipleNegativesRankingLoss")
        self.assertEqual(result["evaluation"]["queries"], 20)
        self.assertEqual(result["evaluation"]["candidate_documents"], 100)
        self.assertEqual(result["metrics"]["recall_at_k"]["delta_percentage_points"], 25.0)
        self.assertEqual(result["metrics"]["mrr_at_k"]["after"], 0.5)


if __name__ == "__main__":
    unittest.main()
