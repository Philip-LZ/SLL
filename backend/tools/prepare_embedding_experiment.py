"""Make a deterministic, query-disjoint public T2Reranking experiment."""

import argparse
import hashlib
import json
import random
from pathlib import Path


DATASET_REVISION = '76631901a18387f85eaa53e5450019b87ad58ef9'
SOURCE_SHA256 = 'ceaf1ba1a4777dbb7aecad86fb8aa9cae7a678af6d711d5529c238e89bb6adff'


def split_rows(rows, *, seed=42, train_count=1200, eval_count=100, corpus_size=1000,
               include_negatives=False):
    if min(train_count, eval_count) < 2 or corpus_size < eval_count:
        raise ValueError('Need >=2 queries per split and corpus_size >= eval_count')
    grouped = {}
    for row in rows:
        query = row['query'].strip()
        if not query:
            continue
        entry = grouped.setdefault(query, {'positive': {}, 'negative': {}})
        for field in ('positive', 'negative'):
            entry[field].update(dict.fromkeys(text.strip() for text in row[field] if text.strip()))
    queries = [q for q in grouped if grouped[q]['positive']]
    random.Random(seed).shuffle(queries)
    if len(queries) < train_count + 2 * eval_count:
        raise ValueError('Not enough distinct queries')
    result = {}
    held_out_documents = set()
    for split, selected in [('test', queries[:eval_count]),
                            ('dev', queries[eval_count:2*eval_count])]:
        positives = list(dict.fromkeys(p for q in selected for p in grouped[q]['positive']))
        if len(positives) > corpus_size:
            raise ValueError(f'{split}: all labeled positives exceed corpus size; increase --corpus-size')
        documents = dict.fromkeys(positives)
        # Original judged distractors make the fixed corpus harder than positives alone.
        candidates = list(dict.fromkeys(n for q in selected for n in grouped[q]['negative']))
        random.Random(seed).shuffle(candidates)
        for text in candidates:
            if len(documents) == corpus_size:
                break
            documents[text] = None
        if len(documents) != corpus_size:
            raise ValueError(f'{split}: not enough original negative documents for fixed corpus')
        result[split] = [{'query': q, 'positive': p} for q in selected for p in grouped[q]['positive']]
        result[f'{split}_corpus'] = list(documents)
        held_out_documents.update(documents)
    training, seen_documents, known_positives, used_negatives = [], set(), set(), set()
    for query in queries[2*eval_count:]:
        if (held_out_documents | seen_documents | used_negatives).intersection(grouped[query]['positive']):
            continue
        positive = next((p for p in grouped[query]['positive'] if p not in known_positives), None)
        negative = next((n for n in grouped[query]['negative']
                         if n not in held_out_documents and n not in known_positives
                         and n not in grouped[query]['positive']), None)
        if positive is not None and negative is not None:
            training.append({'query': query, 'positive': positive})
            seen_documents.add(positive)
            known_positives.update(grouped[query]['positive'])
            used_negatives.add(negative)
            if include_negatives:
                training[-1]['negative'] = negative
        if len(training) == train_count:
            break
    if len(training) != train_count:
        raise ValueError('Not enough non-overlapping training pairs')
    result['train'] = training
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Pinned T2Reranking dev parquet')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--include-negatives', action='store_true',
                        help='Separate ablation: include one original judged negative per train query')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--train-count', type=int, default=1200)
    parser.add_argument('--eval-count', type=int, default=100)
    parser.add_argument('--corpus-size', type=int, default=1000)
    args = parser.parse_args(argv)
    try:
        if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())):
            raise ValueError('Output directory must be new or empty')
        source_digest = hashlib.sha256(args.source.read_bytes()).hexdigest()
        if source_digest != SOURCE_SHA256:
            raise ValueError('Source SHA-256 differs from pinned public dataset')
        import pyarrow.parquet as pq
        data = split_rows(pq.read_table(args.source).to_pylist(), seed=args.seed,
                          train_count=args.train_count, eval_count=args.eval_count,
                          corpus_size=args.corpus_size, include_negatives=args.include_negatives)
        args.output.mkdir(parents=True, exist_ok=True)
        files = {}
        for name, rows in data.items():
            if name.endswith('_corpus'):
                rows = [{'text': text} for text in rows]
            path = args.output / f'{name}.jsonl'
            path.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
            files[name] = {'rows': len(rows), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        manifest = {
            'dataset': 'C-MTEB/T2Reranking', 'source_split': 'dev',
            'revision': DATASET_REVISION, 'source_sha256': source_digest, 'seed': args.seed,
            'source_url': f'https://huggingface.co/datasets/C-MTEB/T2Reranking/tree/{DATASET_REVISION}',
            'train_pairs': args.train_count, 'queries_per_eval_split': args.eval_count,
            'candidate_documents_per_eval_split': args.corpus_size, 'files': files,
            'explicit_training_negatives': args.include_negatives,
            'selection': 'Shuffle unique queries; first test, then dev, then eligible training queries. '
                         'All known positives retained; fill corpora with original judged negatives. '
                         'Training excludes held-out corpus text and known cross-query positive collisions. '
                         'Optional training negatives use original order, excluding all known training positives '
                         'and held-out corpus text; no model-based mining.',
            'limitations': 'Custom public dev split; base pretraining overlap and semantic near-duplicates '
                           'not excluded; relevance labels may be incomplete; not an official benchmark.',
        }
        (args.output/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
