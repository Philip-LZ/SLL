"""Compare a saved embedding run with its base model on one held-out corpus."""

import argparse
import hashlib
import json
from pathlib import Path

from backend.tools.finetune_embedding import load_corpus, load_pairs, retrieval_data


def load_inputs(run_dir: Path, train_path: str | None, eval_path: str | None, k: int, corpus_path: str | None = None):
    if k < 1:
        raise ValueError("K 必须为正整数")
    try:
        config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"无法读取训练配置: {error}") from error
    if not (run_dir / "model").is_dir():
        raise ValueError(f"{run_dir / 'model'}: 未找到微调模型")
    train_file = train_path if train_path is not None else config.get("train")
    eval_file = eval_path if eval_path is not None else config.get("eval")
    if not train_file or not eval_file:
        raise ValueError("必须提供训练集和独立评测集，可用 --train/--eval 指定路径")
    train, evaluation = load_pairs(Path(train_file)), load_pairs(Path(eval_file))
    if {row["query"] for row in train} & {row["query"] for row in evaluation}:
        raise ValueError("训练集和评测集的 query 不能重复")
    corpus_file = corpus_path if corpus_path is not None else config.get("corpus")
    queries, corpus, relevant = retrieval_data(evaluation, load_corpus(Path(corpus_file)) if corpus_file else None)
    if k > len(corpus):
        raise ValueError(f"K={k} 超过评测候选文档数 {len(corpus)}")
    train_digest = hashlib.sha256(Path(train_file).read_bytes()).hexdigest()
    if config.get("data_sha256", {}).get("train", train_digest) != train_digest:
        raise ValueError("训练集 SHA-256 与训练时不一致，拒绝报告错误的样本数")
    eval_digest = hashlib.sha256(Path(eval_file).read_bytes()).hexdigest()
    return config, train, queries, corpus, relevant, train_digest, eval_digest


def summarize(model_name, train_count, query_count, document_count, k, digest, device,
              before, after):
    def metric(values, name):
        try:
            return float(next(value for key, value in values.items() if key.endswith(name)))
        except StopIteration as error:
            raise ValueError(f"评测器没有返回 {name} 指标") from error

    def change(name):
        first, last = metric(before, name), metric(after, name)
        return {"before": first, "after": last,
                "delta_percentage_points": round((last - first) * 100, 4)}

    return {
        "training": {"base_model": model_name, "pairs": train_count,
                     "loss": "MultipleNegativesRankingLoss"},
        "evaluation": {"queries": query_count, "candidate_documents": document_count,
                       "k": k, "data_sha256": digest, "similarity": "cosine", "device": device},
        "metrics": {"recall_at_k": change(f"recall@{k}"),
                    "mrr_at_k": change(f"mrr@{k}")},
    }


def benchmark(run_dir: Path, train_path: str | None, eval_path: str | None,
              k: int, device: str, corpus_path: str | None = None):
    config, train, queries, corpus, relevant, train_digest, eval_digest = load_inputs(run_dir, train_path, eval_path, k, corpus_path)

    import torch
    from sentence_transformers import SentenceTransformer
    from sentence_transformers.sentence_transformer.evaluation import InformationRetrievalEvaluator
    from sentence_transformers.util import cos_sim

    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("请求 CUDA，但当前环境没有可用 CUDA GPU")
    actual_device = "cuda" if device == "cuda" or (device == "auto" and torch.cuda.is_available()) else "cpu"
    evaluator = InformationRetrievalEvaluator(
        queries, corpus, relevant,
        query_prompt=config["query_prefix"], corpus_prompt=config["document_prefix"],
        score_functions={"cosine": cos_sim}, precision_recall_at_k=[k],
        mrr_at_k=[k], write_csv=False,
    )

    def evaluate(model_path):
        model = SentenceTransformer(model_path, device=actual_device,
                                    trust_remote_code=config["trust_remote_code"],
                                    revision=(config.get("revision") or config.get("model_revision"))
                                    if model_path == config["model"] else None)
        model.default_prompt_name = None
        model.max_seq_length = config["max_length"]
        return evaluator(model)

    before = evaluate(config["model"])
    after = evaluate(str(run_dir / "model"))
    report = summarize(config["model"], len(train), len(queries), len(corpus), k,
                       eval_digest, actual_device, before, after)
    report["training"].update({"data_sha256": train_digest,
                               "count_source": "current training JSONL, after deduplication"})
    report["evaluation"].update({"query_prefix": config["query_prefix"],
                                 "document_prefix": config["document_prefix"],
                                 "max_length": config["max_length"],
                                 "positive_pairs": sum(map(len, relevant.values())),
                                 "recall_at_k_ceiling": sum(min(k, len(ids))/len(ids) for ids in relevant.values())/len(relevant)})
    corpus_file = corpus_path if corpus_path is not None else config.get("corpus")
    report["evaluation"]["corpus_sha256"] = (hashlib.sha256(Path(corpus_file).read_bytes()).hexdigest()
                                             if corpus_file else None)
    report["evaluation"]["recall_definition"] = "macro mean of retrieved relevant / all labeled relevant per query"
    report["training"]["scale"] = config.get("scale", 20.0)
    report["training"]["explicit_negative_pairs"] = sum("negative" in row for row in train)
    report["training"]["model_revision"] = config.get("model_revision")
    return report


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Compare base and fine-tuned embedding retrieval")
    parser.add_argument("--run-dir", type=Path, required=True, help="finetune_embedding.py 的输出目录")
    parser.add_argument("--train", help="原训练集路径；默认读取 run_config.json")
    parser.add_argument("--eval", help="独立评测集路径；默认读取 run_config.json")
    parser.add_argument("--corpus", help="固定候选库；默认读取训练配置")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--output", type=Path, help="JSON 报告路径；默认写入 run-dir/benchmark.json")
    args = parser.parse_args(argv)
    try:
        output = args.output or args.run_dir / "benchmark.json"
        if output.exists():
            raise ValueError(f"{output}: 报告已存在，请指定新路径")
        result = benchmark(args.run_dir, args.train, args.eval, args.k, args.device, args.corpus)
        with output.open("x", encoding="utf-8") as destination:
            destination.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
    recall = result["metrics"]["recall_at_k"]
    print(f"训练样本 {result['training']['pairs']} 条；评测 query {result['evaluation']['queries']} 条、"
          f"候选文档 {result['evaluation']['candidate_documents']} 条；"
          f"Recall@{args.k} {recall['before']:.4f} → {recall['after']:.4f} "
          f"({recall['delta_percentage_points']:+.2f} 个百分点)")
    print(f"报告：{output}")


if __name__ == "__main__":
    main()
