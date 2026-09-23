import json
import os
import tempfile
import unittest
from pathlib import Path

from backend import finetune_embedding
from backend.finetune_embedding import load_pairs, parse_args, prepare_data, retrieval_data


class FineTuneEmbeddingDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "pairs.jsonl"

    def write_rows(self, rows):
        self.path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
            encoding="utf-8",
        )

    def valid_rows(self):
        return [
            {"query": "q1", "positive": "d1"},
            {"query": "q1", "positive": "d2"},
            {"query": "q2", "positive": "d2"},
        ]

    def test_deduplication_and_multiple_relevant_documents(self):
        pairs = self.valid_rows()
        self.write_rows(pairs + pairs)
        self.assertEqual(load_pairs(self.path), pairs)
        queries, corpus, relevant = retrieval_data(pairs)
        qid = next(key for key, value in queries.items() if value == "q1")
        self.assertEqual({corpus[key] for key in relevant[qid]}, {"d1", "d2"})
        self.assertEqual(list(queries.values()), ["q1", "q2"])
        self.assertEqual(list(corpus.values()), ["d1", "d2"])

    def test_whitespace_and_blank_lines(self):
        self.path.write_text(
            '\n{"query": " q1 ", "positive": " d1 ", "extra": 1}\n\n'
            '{"query": "q2", "positive": "d2"}\n'
            '{"query": "q1", "positive": "d1"}\n',
            encoding="utf-8",
        )
        self.assertEqual(load_pairs(self.path), [
            {"query": "q1", "positive": "d1"},
            {"query": "q2", "positive": "d2"},
        ])

    def test_invalid_lines_include_path_and_line(self):
        for bad_line in ['{', '[]', '{}', '{"query": 1, "positive": "d"}',
                         '{"query": " ", "positive": "d"}']:
            with self.subTest(line=bad_line):
                self.path.write_text("\n" + bad_line, encoding="utf-8")
                with self.assertRaises(ValueError) as error:
                    load_pairs(self.path)
                self.assertIn(f"{self.path}:2", str(error.exception))

    def test_insufficient_distinct_queries_or_documents(self):
        for rows in ([], [{"query": "q1", "positive": "d1"}],
                     [{"query": "q1", "positive": "d1"},
                      {"query": "q1", "positive": "d2"}],
                     [{"query": "q1", "positive": "d1"},
                      {"query": "q2", "positive": "d1"}]):
            with self.subTest(rows=rows):
                self.write_rows(rows)
                with self.assertRaises(ValueError) as error:
                    load_pairs(self.path)
                self.assertIn(str(self.path), str(error.exception))

    def test_cli_defaults_and_prefixes(self):
        self.write_rows(self.valid_rows())
        args = parse_args(["--train", str(self.path)])
        train, evaluation = prepare_data(args)
        self.assertEqual(train, self.valid_rows())
        self.assertIsNone(evaluation)
        self.assertEqual(args.model, "nomic-ai/nomic-embed-text-v1.5")
        self.assertEqual(args.query_prefix, "search_query: ")
        self.assertEqual(args.document_prefix, "search_document: ")
        self.assertEqual(args.batch_size, 16)
        self.assertEqual(args.epochs, 1)
        self.assertEqual(args.learning_rate, 2e-5)
        self.assertEqual(args.max_length, 512)
        self.assertEqual(args.seed, 42)
        self.assertEqual(args.device, "auto")
        self.assertEqual(args.output, "backend/embedding-output")

    def test_invalid_training_options(self):
        self.write_rows(self.valid_rows())
        for option, value in [
            ("--batch-size", "1"), ("--epochs", "0"),
            ("--max-length", "0"), ("--learning-rate", "nan"),
            ("--learning-rate", "inf"), ("--learning-rate", "0"),
            ("--learning-rate", "-1"), ("--seed", "-1"),
            ("--seed", str(2**32)),
        ]:
            with self.subTest(option=option, value=value):
                args = parse_args(["--train", str(self.path), option, value])
                with self.assertRaises(ValueError):
                    prepare_data(args)

    def test_output_must_be_new_or_empty_directory(self):
        self.write_rows(self.valid_rows())
        output = Path(self.temp.name) / "output"
        output.mkdir()
        prepare_data(parse_args(["--train", str(self.path), "--output", str(output)]))
        (output / "existing").touch()
        with self.assertRaises(ValueError):
            prepare_data(parse_args(["--train", str(self.path), "--output", str(output)]))
        file_path = Path(self.temp.name) / "file"
        file_path.touch()
        with self.assertRaises(ValueError):
            prepare_data(parse_args(["--train", str(self.path), "--output", str(file_path)]))

    def test_custom_model_requires_both_prefixes_but_allows_empty(self):
        self.write_rows(self.valid_rows())
        base = ["--train", str(self.path), "--model", "custom/model"]
        for flags in ([], ["--query-prefix", ""], ["--document-prefix", ""]):
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                prepare_data(parse_args(base + flags))
        args = parse_args(base + ["--query-prefix", "", "--document-prefix", ""])
        prepare_data(args)
        self.assertEqual((args.query_prefix, args.document_prefix), ("", ""))

    def test_evaluation_query_overlap_after_cleaning(self):
        self.write_rows(self.valid_rows())
        evaluation = Path(self.temp.name) / "evaluation.jsonl"
        evaluation.write_text(
            '\n'.join(json.dumps(row, ensure_ascii=False) for row in [
                {"query": " q1 ", "positive": "x"},
                {"query": "q3", "positive": "y"},
            ]), encoding="utf-8")
        with self.assertRaises(ValueError):
            prepare_data(parse_args(["--train", str(self.path), "--eval", str(evaluation)]))
        evaluation.write_text(
            '\n'.join(json.dumps(row, ensure_ascii=False) for row in [
                {"query": "q3", "positive": "x"},
                {"query": "q4", "positive": "y"},
            ]), encoding="utf-8")
        _, eval_rows = prepare_data(parse_args([
            "--train", str(self.path), "--eval", str(evaluation)]))
        self.assertEqual(len(eval_rows), 2)

    def test_explicit_empty_evaluation_path_is_invalid(self):
        self.write_rows(self.valid_rows())
        with self.assertRaises(ValueError):
            prepare_data(parse_args(["--train", str(self.path), "--eval", ""]))


@unittest.skipUnless(os.environ.get("SLL_EMBEDDING_SMOKE") == "1", "set SLL_EMBEDDING_SMOKE=1")
class FineTuneEmbeddingSmokeTests(unittest.TestCase):
    def setUp(self):
        from sentence_transformers import SentenceTransformer
        from sentence_transformers.sentence_transformer.modules import Pooling, Transformer
        from transformers import BertConfig, BertModel, BertTokenizer

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        encoder = self.root / "encoder"
        encoder.mkdir()
        tokens = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", "q1", "q2", "q3", "q4", "q5", "q6", "d1", "d2", "d3", "d4", "d5"]
        (encoder / "vocab.txt").write_text("\n".join(tokens), encoding="utf-8")
        BertTokenizer(vocab_file=str(encoder / "vocab.txt")).save_pretrained(str(encoder))
        BertModel(BertConfig(vocab_size=16, hidden_size=16, num_hidden_layers=1,
                             num_attention_heads=2, intermediate_size=32)).save_pretrained(str(encoder))
        base = SentenceTransformer(modules=[Transformer(str(encoder), max_seq_length=16), Pooling(16)])
        self.before = {name: value.detach().clone() for name, value in base.named_parameters()}
        self.model_path = self.root / "base"
        base.save_pretrained(str(self.model_path))
        self.train_path = self.root / "train.jsonl"
        self.eval_path = self.root / "eval.jsonl"
        self.write_rows(self.train_path, [(f"q{i}", f"d{i}") for i in range(1, 5)])
        self.write_rows(self.eval_path, [("q5", "d5"), ("q6", "d1")])
        self.args = parse_args(["--train", str(self.train_path), "--eval", str(self.eval_path),
                                "--model", str(self.model_path), "--output", str(self.root / "output"),
                                "--query-prefix", "", "--document-prefix", "", "--batch-size", "2",
                                "--epochs", "1", "--max-length", "16", "--device", "cpu"])

    def write_rows(self, path, rows):
        path.write_text("\n".join(json.dumps({"query": query, "positive": positive})
                                  for query, positive in rows), encoding="utf-8")

    def test_training_updates_weights_and_saves_evaluation(self):
        import numpy as np
        import torch
        from sentence_transformers import SentenceTransformer

        result = finetune_embedding.train(self.args)
        trained = SentenceTransformer(str(result), device="cpu")
        self.assertTrue(any(not torch.equal(self.before[name], value)
                            for name, value in trained.named_parameters()))
        vectors = trained.encode(["q1", "q2"])
        self.assertEqual(vectors.shape, (2, 16))
        self.assertTrue(np.isfinite(vectors).all())
        metrics = json.loads((Path(self.args.output) / "metrics.json").read_text())
        self.assertEqual(set(metrics), {"before", "after", "queries", "documents"})
        self.assertEqual((metrics["queries"], metrics["documents"]), (2, 2))
        self.assertEqual(set(metrics["before"]), {"recall@1", "recall@5", "recall@10", "mrr@10"})
        self.assertTrue((Path(self.args.output) / "run_config.json").is_file())

    def test_training_without_evaluation_has_no_metrics(self):
        self.args.eval = None
        result = finetune_embedding.train(self.args)
        self.assertTrue(result.is_dir())
        self.assertFalse((Path(self.args.output) / "metrics.json").exists())

    def test_duplicate_documents_cannot_form_a_full_batch(self):
        self.write_rows(self.train_path, [("q1", "d1"), ("q2", "d1"),
                                          ("q3", "d1"), ("q4", "d2")])
        self.args.batch_size = 4
        with self.assertRaisesRegex(ValueError, "完整批次"):
            finetune_embedding.train(self.args)

    def test_explicit_cuda_requires_available_gpu(self):
        import torch
        if torch.cuda.is_available():
            self.skipTest("CUDA is available")
        self.args.device = "cuda"
        with self.assertRaisesRegex(ValueError, "CUDA"):
            finetune_embedding.train(self.args)


if __name__ == "__main__":
    unittest.main()
