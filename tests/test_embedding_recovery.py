import json
import tempfile
import unittest
from pathlib import Path

from backend.tools import finetune_embedding as ft
from backend.tools.benchmark_embedding import load_inputs


class RetrievalCorpusTests(unittest.TestCase):
    def test_fixed_candidates_include_distractors_and_all_positives(self):
        pairs = [{'query': 'q1', 'positive': 'p1'}, {'query': 'q2', 'positive': 'p2'}]
        queries, corpus, relevant = ft.retrieval_data(pairs, ['noise', 'p2', 'p1'])
        self.assertEqual(list(corpus.values()), ['noise', 'p2', 'p1'])
        self.assertEqual(relevant, {'0': {'2'}, '1': {'1'}})
        with self.assertRaisesRegex(ValueError, 'positive'):
            ft.retrieval_data(pairs, ['noise', 'p1'])

    def test_corpus_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'corpus.jsonl'
            path.write_text('{"text":" a "}\n{"text":"b"}\n', encoding='utf-8')
            self.assertEqual(ft.load_corpus(path), ['a', 'b'])
            for content in ['{"text":" "}', '{"text":3}', '{}', '{',
                            '{"text":"a"}\n{"text":" a "}', '']:
                path.write_text(content, encoding='utf-8')
                with self.subTest(content=content), self.assertRaises(ValueError):
                    ft.load_corpus(path)

    def test_bge_defaults_and_scale_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'train.jsonl'
            path.write_text('{"query":"q1","positive":"d1"}\n{"query":"q2","positive":"d2"}')
            args = ft.parse_args(['--train', str(path), '--output', str(Path(tmp)/'run')])
            ft.prepare_data(args)
            self.assertEqual(args.model, 'BAAI/bge-base-zh-v1.5')
            self.assertEqual(args.query_prefix, '为这个句子生成表示以用于检索相关文章：')
            self.assertEqual(args.document_prefix, '')
            for value in ['0', 'nan', '-1']:
                args = ft.parse_args(['--train', str(path), '--scale', value])
                with self.assertRaises(ValueError):
                    ft.prepare_data(args)

    def test_benchmark_uses_explicit_corpus_from_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'model').mkdir()
            for name in ['train', 'eval']:
                (root / f'{name}.jsonl').write_text('\n'.join(json.dumps(
                    {'query': f'{name}{i}', 'positive': f'd{i}'}) for i in range(2)))
            corpus = root / 'corpus.jsonl'
            corpus.write_text('\n'.join(json.dumps({'text': d}) for d in ['d0','d1','noise']))
            (root / 'run_config.json').write_text(json.dumps({
                'train': str(root/'train.jsonl'), 'eval': str(root/'eval.jsonl'),
                'corpus': str(corpus)}))
            result = load_inputs(root, None, None, 3)
            self.assertEqual(len(result[3]), 3)


class ExperimentSplitTests(unittest.TestCase):
    def test_deterministic_split_keeps_all_labels_and_excludes_held_out_text(self):
        from backend.tools.prepare_embedding_experiment import split_rows
        rows = [{'query': f'q{i}', 'positive': [f'p{i}', f'extra{i}'],
                 'negative': [f'n{i}', 'shared']} for i in range(30)]
        result = split_rows(rows, seed=42, train_count=8, eval_count=3, corpus_size=10)
        self.assertEqual(result, split_rows(rows, seed=42, train_count=8, eval_count=3, corpus_size=10))
        self.assertEqual(len(result['train']), 8)
        train_queries = {r['query'] for r in result['train']}
        for split in ['dev', 'test']:
            pairs, corpus = result[split], result[f'{split}_corpus']
            self.assertEqual(len(corpus), 10)
            self.assertEqual(len(set(corpus)), 10)
            self.assertEqual(len({r['query'] for r in pairs}), 3)
            self.assertEqual(len(pairs), 6)
            self.assertFalse(train_queries & {r['query'] for r in pairs})
            self.assertFalse({r['positive'] for r in result['train']} & set(corpus))
            self.assertTrue({r['positive'] for r in pairs} <= set(corpus))
        self.assertFalse({r['query'] for r in result['dev']} & {r['query'] for r in result['test']})
        with self.assertRaises(ValueError):
            split_rows(rows[:2], seed=42, train_count=8, eval_count=3, corpus_size=10)


class BenchmarkProvenanceTests(unittest.TestCase):
    def test_rejects_changed_training_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'model').mkdir()
            for name in ['train', 'eval']:
                (root / f'{name}.jsonl').write_text('\n'.join(json.dumps(
                    {'query': f'{name}{i}', 'positive': f'd{i}'}) for i in range(2)))
            (root / 'run_config.json').write_text(json.dumps({
                'train': str(root/'train.jsonl'), 'eval': str(root/'eval.jsonl'),
                'data_sha256': {'train': '0'*64}}))
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                load_inputs(root, None, None, 2)


class NegativeTrainingTests(unittest.TestCase):
    def test_negative_validation_and_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'train.jsonl'
            rows = [{'query':'q1','positive':'p1','negative':'n1'},
                    {'query':'q2','positive':'p2','negative':'n2'}]
            path.write_text('\n'.join(json.dumps(r) for r in rows))
            self.assertEqual(ft.load_pairs(path), rows)
            for bad in [None, '', 'p1', 1]:
                rows[0]['negative'] = bad
                path.write_text('\n'.join(json.dumps(r) for r in rows))
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    ft.load_pairs(path)
            rows[0].pop('negative')
            path.write_text('\n'.join(json.dumps(r) for r in rows))
            with self.assertRaises(ValueError):
                ft.load_pairs(path)

    def test_split_avoids_known_in_batch_false_negatives(self):
        from backend.tools.prepare_embedding_experiment import split_rows
        rows = [{'query':f'q{i}', 'positive':[f'p{i}', f'p{(i+1)%80}'],
                 'negative':[f'n{i}',f'x{i}',f'y{i}']} for i in range(80)]
        data = split_rows(rows, seed=42, train_count=20, eval_count=2, corpus_size=6,
                          include_negatives=True)
        pairs_only = split_rows(rows, seed=42, train_count=20, eval_count=2, corpus_size=6)
        self.assertEqual(pairs_only['train'], [{k:r[k] for k in ('query','positive')} for r in data['train']])
        chosen = {r['positive'] for r in data['train']}
        labels = {r['query']:set(r['positive']) for r in rows}
        for row in data['train']:
            self.assertEqual(chosen & labels[row['query']], {row['positive']})
            self.assertIn('negative', row)
            self.assertNotIn(row['negative'], labels[row['query']])


class ReportPreservationTests(unittest.TestCase):
    def test_existing_report_is_rejected_before_loading_models(self):
        import contextlib
        import io
        from backend.tools.benchmark_embedding import main
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'report.json'
            path.write_text('keep')
            error = io.StringIO()
            with contextlib.redirect_stderr(error), self.assertRaises(SystemExit):
                main(['--run-dir', str(Path(tmp)/'missing'), '--output', str(path)])
            self.assertIn('报告已存在', error.getvalue())
            self.assertEqual(path.read_text(), 'keep')
