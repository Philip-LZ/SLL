"""Prepare JSONL query/document pairs for offline embedding fine-tuning."""

import argparse
import json
import math
from pathlib import Path


DEFAULT_MODEL = "nomic-ai/nomic-embed-text-v1.5"


def load_pairs(path: Path) -> list[dict[str, str]]:
    pairs = []
    seen = set()
    try:
        with path.open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"{path}:{line_number}: invalid JSON: {error.msg}") from error
                if (not isinstance(row, dict)
                        or any(not isinstance(row.get(field), str) for field in ("query", "positive"))):
                    raise ValueError(f"{path}:{line_number}: query and positive must be strings")
                query, positive = row["query"].strip(), row["positive"].strip()
                if not query or not positive:
                    raise ValueError(f"{path}:{line_number}: query and positive must be nonempty")
                pair = (query, positive)
                if pair not in seen:
                    seen.add(pair)
                    pairs.append({"query": query, "positive": positive})
    except OSError as error:
        raise ValueError(f"{path}: {error}") from error
    if len({pair["query"] for pair in pairs}) < 2 or len({pair["positive"] for pair in pairs}) < 2:
        raise ValueError(f"{path}: requires at least two distinct queries and documents")
    return pairs


def retrieval_data(pairs: list[dict[str, str]]) -> tuple[dict[str, str], dict[str, str], dict[str, set[str]]]:
    query_ids, document_ids, relevant = {}, {}, {}
    for pair in pairs:
        qid = query_ids.setdefault(pair["query"], str(len(query_ids)))
        did = document_ids.setdefault(pair["positive"], str(len(document_ids)))
        relevant.setdefault(qid, set()).add(did)
    return ({qid: query for query, qid in query_ids.items()},
            {did: document for document, did in document_ids.items()}, relevant)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tune an embedding model from JSONL pairs")
    parser.add_argument("--train", required=True)
    parser.add_argument("--eval")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output", default="backend/embedding-output")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--query-prefix")
    parser.add_argument("--document-prefix")
    parser.add_argument("--trust-remote-code", action="store_true")
    return parser.parse_args(argv)


def prepare_data(args: argparse.Namespace) -> tuple[list[dict[str, str]], list[dict[str, str]] | None]:
    if args.batch_size < 2 or args.epochs < 1 or args.max_length < 1:
        raise ValueError("batch size 至少为 2，epochs 和 max length 必须为正数")
    if not math.isfinite(args.learning_rate) or args.learning_rate <= 0:
        raise ValueError("learning rate 必须是有限正数")
    if args.seed < 0 or args.seed >= 2**32:
        raise ValueError("seed 必须在 [0, 2**32) 内")
    output = Path(args.output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("输出路径必须不存在或为空目录")
    if args.model == DEFAULT_MODEL:
        if args.query_prefix is None:
            args.query_prefix = "search_query: "
        if args.document_prefix is None:
            args.document_prefix = "search_document: "
    elif args.query_prefix is None or args.document_prefix is None:
        raise ValueError("自定义模型必须明确指定 query 和 document 前缀")

    train = load_pairs(Path(args.train))
    evaluation = load_pairs(Path(args.eval)) if args.eval else None
    if evaluation and {pair["query"] for pair in train} & {pair["query"] for pair in evaluation}:
        raise ValueError("训练集和验证集的 query 不能重复")
    return train, evaluation


if __name__ == "__main__":
    parse_args()
