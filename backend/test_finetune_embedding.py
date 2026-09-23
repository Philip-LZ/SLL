import json
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
