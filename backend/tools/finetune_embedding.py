"""Prepare JSONL query/document pairs for offline embedding fine-tuning."""

import argparse
import importlib.metadata
import hashlib
from functools import partial
import json
import math
import os
from pathlib import Path


DEFAULT_MODEL = "BAAI/bge-base-zh-v1.5"


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
                negative = row.get("negative")
                if "negative" in row and (not isinstance(negative, str) or not negative.strip()):
                    raise ValueError(f"{path}:{line_number}: negative must be a nonempty string")
                pair = (query, positive, negative.strip() if negative is not None else None)
                if pair not in seen:
                    seen.add(pair)
                    pairs.append({"query": query, "positive": positive})
                    if negative is not None:
                        pairs[-1]["negative"] = negative.strip()
    except OSError as error:
        raise ValueError(f"{path}: {error}") from error
    if len({pair["query"] for pair in pairs}) < 2 or len({pair["positive"] for pair in pairs}) < 2:
        raise ValueError(f"{path}: requires at least two distinct queries and documents")
    if any("negative" in row for row in pairs):
        if not all("negative" in row for row in pairs):
            raise ValueError(f"{path}: negative must be provided for every training row")
        positives = {}
        for row in pairs:
            positives.setdefault(row["query"], set()).add(row["positive"])
        if any(row["negative"] in positives[row["query"]] for row in pairs):
            raise ValueError(f"{path}: negative cannot be a known positive for the query")
    return pairs


def load_corpus(path: Path) -> list[str]:
    documents = []
    seen = set()
    try:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{number}: invalid JSON") from error
            text = row.get("text") if isinstance(row, dict) else None
            if not isinstance(text, str) or not text.strip() or text.strip() in seen:
                raise ValueError(f"{path}:{number}: text must be nonempty and unique")
            documents.append(text.strip())
            seen.add(text.strip())
    except OSError as error:
        raise ValueError(f"{path}: {error}") from error
    if not documents:
        raise ValueError(f"{path}: corpus is empty")
    return documents


def retrieval_data(pairs: list[dict[str, str]], documents: list[str] | None = None
                   ) -> tuple[dict[str, str], dict[str, str], dict[str, set[str]]]:
    query_ids, relevant = {}, {}
    if documents is None:
        documents = list(dict.fromkeys(pair["positive"] for pair in pairs))
    document_ids = {text: str(i) for i, text in enumerate(documents)}
    for pair in pairs:
        qid = query_ids.setdefault(pair["query"], str(len(query_ids)))
        if pair["positive"] not in document_ids:
            raise ValueError("corpus must contain every labeled positive")
        relevant.setdefault(qid, set()).add(document_ids[pair["positive"]])
    return ({qid: query for query, qid in query_ids.items()},
            {did: document for document, did in document_ids.items()}, relevant)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tune an embedding model from JSONL pairs")
    parser.add_argument("--train", required=True)
    parser.add_argument("--eval", help="开发集，用于按 Recall@10 选择 checkpoint")
    parser.add_argument("--corpus", help="开发集固定候选库 JSONL，每行 text 字段")
    parser.add_argument("--scale", type=float, default=20.0, help="InfoNCE 的逆温度")
    parser.add_argument("--bf16", action="store_true")
    parser.add_argument("--gradient-checkpointing", action="store_true")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--revision", help="基础模型的固定 Hugging Face commit")
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
    if not math.isfinite(args.scale) or args.scale <= 0:
        raise ValueError("scale 必须是有限正数")
    if args.corpus and not args.eval:
        raise ValueError("--corpus 需要 --eval")
    output = Path(args.output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("输出路径必须不存在或为空目录")
    if args.model == DEFAULT_MODEL:
        if args.query_prefix is None:
            args.query_prefix = "为这个句子生成表示以用于检索相关文章："
        if args.document_prefix is None:
            args.document_prefix = ""
    elif args.model == "nomic-ai/nomic-embed-text-v1.5":
        if args.query_prefix is None:
            args.query_prefix = "search_query: "
        if args.document_prefix is None:
            args.document_prefix = "search_document: "
    elif args.query_prefix is None or args.document_prefix is None:
        raise ValueError("自定义模型必须明确指定 query 和 document 前缀")

    train = load_pairs(Path(args.train))
    evaluation = load_pairs(Path(args.eval)) if args.eval is not None else None
    if evaluation and {pair["query"] for pair in train} & {pair["query"] for pair in evaluation}:
        raise ValueError("训练集和验证集的 query 不能重复")
    if args.corpus:
        retrieval_data(evaluation, load_corpus(Path(args.corpus)))
    return train, evaluation


def seeded_batch_sampler(data, run_seed, **kwargs):
    from sentence_transformers.base.sampler import NoDuplicatesBatchSampler
    return NoDuplicatesBatchSampler(data, **(kwargs | {"seed": run_seed}))


def train(args: argparse.Namespace) -> Path:
    pairs, evaluation = prepare_data(args)
    if int(os.environ.get("WORLD_SIZE", "1")) > 1:
        raise ValueError("仅支持单进程训练")

    import torch
    from datasets import Dataset
    from sentence_transformers import (SentenceTransformer, SentenceTransformerTrainer,
                                       SentenceTransformerTrainingArguments)
    from sentence_transformers.sentence_transformer.evaluation import InformationRetrievalEvaluator
    from sentence_transformers.sentence_transformer.losses import MultipleNegativesRankingLoss
    from sentence_transformers.util import cos_sim
    from transformers import set_seed

    if args.device == "cuda" and not torch.cuda.is_available():
        raise ValueError("请求 CUDA，但当前环境没有可用 CUDA GPU")
    device = "cuda" if args.device == "cuda" or (args.device == "auto" and torch.cuda.is_available()) else "cpu"
    if args.bf16 and (device != "cuda" or not torch.cuda.is_bf16_supported()):
        raise ValueError("bf16 需要受支持的 CUDA GPU")
    set_seed(args.seed)
    dataset = Dataset.from_list([
        {"query": args.query_prefix + row["query"],
         "positive": args.document_prefix + row["positive"],
         **({"negative": args.document_prefix + row["negative"]} if "negative" in row else {})}
        for row in pairs
    ])
    seeded_sampler = partial(seeded_batch_sampler, run_seed=args.seed)

    sampler = seeded_sampler(dataset, batch_size=args.batch_size, drop_last=True,
                             generator=torch.Generator().manual_seed(args.seed))
    for epoch in range(args.epochs):
        sampler.set_epoch(epoch)
        if next(iter(sampler), None) is None:
            raise ValueError(f"第 {epoch + 1} 轮训练数据无法组成无重复文本的完整批次")

    model = SentenceTransformer(args.model, device=device, trust_remote_code=args.trust_remote_code, revision=args.revision)
    model.default_prompt_name = None
    model.max_seq_length = args.max_length
    if args.gradient_checkpointing:
        # Trainer 5.17 passes unsupported kwargs to Sentence Transformers 6.1.
        model.gradient_checkpointing_enable()
    output = Path(args.output)
    training_args = SentenceTransformerTrainingArguments(
        output_dir=str(output / "checkpoints"),
        num_train_epochs=args.epochs, per_device_train_batch_size=args.batch_size,
        learning_rate=args.learning_rate, batch_sampler=seeded_sampler,
        dataloader_drop_last=True, seed=args.seed, data_seed=args.seed,
        use_cpu=device == "cpu", report_to=[], logging_steps=1,
        bf16=args.bf16,
        eval_strategy="epoch" if evaluation else "no",
        save_strategy="epoch" if evaluation else "no",
        load_best_model_at_end=bool(evaluation),
        metric_for_best_model="eval_cosine_recall@10" if evaluation else None,
        greater_is_better=True, save_total_limit=1, save_only_model=True,
        warmup_steps=0.1,
    )
    evaluator = None
    if evaluation is not None:
        queries, corpus, relevant_docs = retrieval_data(evaluation, load_corpus(Path(args.corpus)) if args.corpus else None)
        evaluator = InformationRetrievalEvaluator(
            queries, corpus, relevant_docs,
            query_prompt=args.query_prefix, corpus_prompt=args.document_prefix,
            score_functions={"cosine": cos_sim},
            precision_recall_at_k=[1, 5, 10], mrr_at_k=[10], write_csv=False,
        )
        before = evaluator(model)

    trainer = SentenceTransformerTrainer(
        model=model, args=training_args, train_dataset=dataset,
        loss=MultipleNegativesRankingLoss(model, scale=args.scale), evaluator=evaluator,
    )
    trainer.train()
    if trainer.state.global_step < 1:
        raise RuntimeError("没有执行训练步骤，拒绝保存成功产物")
    if evaluator is not None:
        after = evaluator(model)

    model_path = output / "model"
    model.save_pretrained(str(model_path))
    config = vars(args).copy()
    config["actual_device"] = device
    config["warmup_ratio"] = 0.1
    config["selection_metric"] = "dev cosine_recall@10" if evaluation else None
    config["training_format"] = "query-positive-negative" if "negative" in pairs[0] else "query-positive"
    config["global_step"] = trainer.state.global_step
    config["best_checkpoint"] = trainer.state.best_model_checkpoint
    config["best_dev_recall_at_10"] = trainer.state.best_metric
    config["data_sha256"] = {name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                             for name in ("train", "eval", "corpus")
                             if (path := getattr(args, name)) is not None}
    config["model_revision"] = args.revision or getattr(model[0].auto_model.config, "_commit_hash", None)
    config["dependencies"] = {name: importlib.metadata.version(name) for name in
                              ("torch", "sentence-transformers", "transformers", "datasets", "accelerate", "einops")}
    (output / "run_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    if evaluator is not None:
        def selected(metrics):
            return {name: float(next(value for key, value in metrics.items() if key.endswith(name)))
                    for name in ("recall@1", "recall@5", "recall@10", "mrr@10")}
        metrics = {"before": selected(before), "after": selected(after),
                   "queries": len(queries), "documents": len(corpus)}
        (output / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    else:
        print("未提供验证集，没有评估结果")
    return model_path


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    try:
        model_path = train(args)
    except ValueError as error:
        argparse.ArgumentParser(prog="finetune_embedding.py").error(str(error))
    print(f"模型已保存至 {model_path}")


if __name__ == "__main__":
    main()
