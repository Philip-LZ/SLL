# Embedding Offline Fine-tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提供能够校验 JSONL 数据、微调 embedding 模型、比较检索指标并保存可加载模型的独立命令行工具。

**Architecture:** 一个训练脚本负责数据准备和训练编排，Sentence Transformers 负责模型、对比损失、采样和评估。标准库测试验证数据边界；本地小模型验证真实训练链路。训练依赖与服务依赖分开。

**Tech Stack:** Python、argparse、unittest、PyTorch、Sentence Transformers、datasets。

**Spec:** `docs/superpowers/specs/2026-09-24-embedding-finetuning-design.md`

## Global Constraints

- 默认基础模型为 `nomic-ai/nomic-embed-text-v1.5`，允许指定其他兼容模型。
- 训练依赖安装在单独虚拟环境中，不加入后端服务的 requirements.txt。
- 数据加载和参数检查在模型下载前完成；输出目录已有内容时拒绝覆盖。
- 验证集为可选项；未提供时明确提示没有评估结果，不自动拆分或虚构指标。
- 使用固定种子，日志输出训练损失。
- 需要自定义模型代码时，由显式参数开启 trust_remote_code。
- 若环境无法运行真实训练，明确记录未验证项，不把数据测试等同于训练成功。
- 不修改数据库、在线检索或 Web 服务，不上传数据或模型。
- 用户补充：默认 auto 优先 CUDA GPU，不可用时 CPU；显式 cuda 不可用时报错。

## Review Focus

1. 同一查询有多个相关文档：评估必须合并相关集合，不能覆盖前一条标注；Task 1 测试。
2. 数据行数充足但无重复采样无法形成完整 batch：必须在训练前报错；Task 2 测试。
3. 自定义基础模型或本地路径：必须显式指定前缀（允许空字符串），不能自动加 Nomic 前缀；Task 1 测试。
4. 非有限学习率、非正训练参数和已有输出目录：必须在模型加载前拒绝；Task 1 测试。
5. 训练产物可能只保存配置而未更新权重：真实 CPU 小模型检查权重变化、加载、有限向量与指标；Task 2 测试。

## 文件边界

- 新增 `backend/finetune_embedding.py`：命令行、输入校验、训练、评估和输出。
- 新增 `backend/test_finetune_embedding.py`：标准库测试与显式开启的本地训练测试。
- 新增 `backend/requirements-embedding.txt`：独立训练依赖，安装成功后记录验证过的版本约束。
- 新增 `backend/EMBEDDING_FINETUNING.md`：中文安装、数据、运行与加载说明。
- 修改 `.gitignore`：忽略 `/backend/embedding-output/` 默认产物目录。

## Task 1: 数据准备与命令行校验

**Files:** Create `backend/finetune_embedding.py`, `backend/test_finetune_embedding.py`。

**Interfaces:**

- `load_pairs(path: Path) -> list[dict[str, str]]`：保留顺序、清理空白、去重后只返回 query/positive。
- `prepare_data(args: argparse.Namespace) -> tuple[list[dict[str, str]], list[dict[str, str]] | None]`：校验参数、目录和跨集合查询重复。
- `retrieval_data(pairs: list[dict[str, str]]) -> tuple[dict[str, str], dict[str, str], dict[str, set[str]]]`：返回 queries、corpus、relevant_docs。
- `parse_args(argv: list[str] | None = None) -> argparse.Namespace`：标准库解析，不导入训练依赖。

- [ ] **Step 1: 写失败的数据测试。** 用 `unittest.TestCase` 和 `TemporaryDirectory`，JSONL 内容通过 `json.dumps(..., ensure_ascii=False)` 写入，不使用真实用户数据。首先固定去重和多正例行为：

```python
pairs = [
    {"query": "q1", "positive": "d1"},
    {"query": "q1", "positive": "d2"},
    {"query": "q2", "positive": "d2"},
]
path.write_text("\n".join(json.dumps(row) for row in pairs + pairs), encoding="utf-8")
self.assertEqual(load_pairs(path), pairs)
queries, corpus, relevant = retrieval_data(pairs)
qid = next(key for key, value in queries.items() if value == "q1")
self.assertEqual({corpus[key] for key in relevant[qid]}, {"d1", "d2"})
```

用 subTest 覆盖非法 JSON、数组、缺字段、数字字段、空字符串、全空文件、只有一个独立查询或文档；错误包含路径，行级错误包含行号。

```python
for bad_line in ['{', '[]', '{}', '{"query": 1, "positive": "d"}',
                 '{"query": " ", "positive": "d"}']:
    with self.subTest(line=bad_line):
        path.write_text(bad_line, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, ":1"):
            load_pairs(path)
```

- [ ] **Step 2: 确认红灯。** 执行 `python3 -m unittest discover -s backend -p test_finetune_embedding.py -v`，此时应因模块/函数尚不存在失败。

- [ ] **Step 3: 实现数据函数。** `load_pairs` 逐行读取，跳过空行；捕获 JSONDecodeError 并附加路径/行号；对象和字段检查后用 `(query, positive)` 集合去重。最后分别检查两列不同值数量不少于 2。检索映射使用稳定 ID：

```python
def retrieval_data(pairs):
    query_ids, document_ids, relevant = {}, {}, {}
    for pair in pairs:
        qid = query_ids.setdefault(pair["query"], str(len(query_ids)))
        did = document_ids.setdefault(pair["positive"], str(len(document_ids)))
        relevant.setdefault(qid, set()).add(did)
    return ({qid: query for query, qid in query_ids.items()},
            {did: document for document, did in document_ids.items()}, relevant)
```

- [ ] **Step 4: 测试并实现 CLI 边界。** 参数为 `--train`（必选）、`--eval`、`--model`、`--output`（默认 `backend/embedding-output`）、`--batch-size`（16）、`--epochs`（1，正整数）、`--learning-rate`（2e-5）、`--max-length`（512）、`--seed`（42）、`--device`（auto/cpu/cuda）、`--query-prefix`、`--document-prefix`、`--trust-remote-code`。

```python
if args.batch_size < 2 or args.epochs < 1 or args.max_length < 1:
    raise ValueError("batch size 至少为 2，epochs 和 max length 必须为正数")
if not math.isfinite(args.learning_rate) or args.learning_rate <= 0:
    raise ValueError("learning rate 必须是有限正数")
if args.seed < 0 or args.seed >= 2**32:
    raise ValueError("seed 必须在 [0, 2**32) 内")
output = Path(args.output)
if output.exists() and (not output.is_dir() or any(output.iterdir())):
    raise ValueError("输出路径必须不存在或为空目录")
```

默认模型的未指定前缀补为 Nomic 前缀；自定义模型要求两个前缀均不为 None，空字符串合法。输入清理后检查 `{p['query'] for p in train} & {p['query'] for p in evaluation}` 非空则报错。暂不创建输出目录。测试对 nan/inf/零/负学习率、batch size 1、零 epochs、非空目录、输出为文件、自定义模型前缀缺失、空前缀和训练/验证查询重复逐项断言。

- [ ] **Step 5: 确认绿灯并提交。** 执行上述 unittest 命令及 `python3 backend/finetune_embedding.py --help`；数据准备阶段和帮助不应要求 torch。执行 `git diff --check`，只提交这两个文件，提交信息 `feat: validate embedding fine-tuning inputs`。

## Task 2: 训练、评估与可加载产物

**Files:** Modify Task 1 两个文件；Create `backend/requirements-embedding.txt`, `backend/EMBEDDING_FINETUNING.md`；Modify `.gitignore`。

**Interfaces:**

- 消费 Task 1 的 `parse_args`、`prepare_data`、`retrieval_data`。
- `train(args: argparse.Namespace) -> Path`：运行训练，返回 `output/model`。
- `main(argv: list[str] | None = None) -> None`：解析并执行；用户输入错误通过 parser.error 输出。
- 输出 `output/model/`、`output/run_config.json`、可选 `output/metrics.json`。

- [ ] **Step 1: 写真实链路失败测试。** 同一测试文件中的训练测试仅在 `SLL_EMBEDDING_SMOKE=1` 时启用；普通测试显式显示 skipped。使用 `BertConfig(vocab_size=16, hidden_size=16, num_hidden_layers=1, num_attention_heads=2, intermediate_size=32)`、本地 vocab 和 BertTokenizer 保存临时模型。用 `models.Transformer`、`models.Pooling` 包装为 SentenceTransformer 并保存本地目录，无需下载权重。

```python
before = {name: value.detach().clone() for name, value in base.named_parameters()}
result = train(args)
trained = SentenceTransformer(str(result), device="cpu")
self.assertTrue(any(not torch.equal(before[name], value)
                    for name, value in trained.named_parameters()))
vectors = trained.encode(["q1", "q2"])
self.assertEqual(vectors.shape, (2, 16))
self.assertTrue(np.isfinite(vectors).all())
metrics = json.loads((Path(args.output) / "metrics.json").read_text())
self.assertEqual(set(metrics), {"before", "after", "queries", "documents"})
```

训练测试构造至少四条不同 query/positive 的训练对和两个独立验证 query；batch size 2、epochs 1、max length 16、CPU、空前缀。将所有测试文本使用的 token 放入 vocab，防止全部变成同一个未知 token。分别测试无验证集时不产生 metrics.json，以及四行共享文档而 batch size 4 时拒绝训练。

- [ ] **Step 2: 建立独立环境，运行确认红灯。** 选择可用的受依赖支持 Python，优先 3.11/3.12；在 `/tmp/sll-embedding-venv` 安装 `sentence-transformers[train]` 与 Nomic 所需的 `einops`，确认实际 API 后将通过测试的直接依赖版本写入 requirements 文件。若环境安装受限，保存失败证据并继续标准库测试，明确真实训练未验证。

运行 `SLL_EMBEDDING_SMOKE=1 /tmp/sll-embedding-venv/bin/python -m unittest discover -s backend -p test_finetune_embedding.py -v`，预期因 train 尚未实现失败。

- [ ] **Step 3: 接入原生训练器。** 在 `prepare_data` 成功后延迟导入训练依赖并调用 `set_seed(args.seed)`。保持数据列顺序 query/positive，用显式前缀拼接训练文本；清空加载模型的 default_prompt_name 防止 encode 自动重复添加前缀。

```python
dataset = Dataset.from_list([
    {"query": args.query_prefix + row["query"],
     "positive": args.document_prefix + row["positive"]}
    for row in pairs
])
training_args = SentenceTransformerTrainingArguments(
    output_dir=str(Path(args.output) / "checkpoints"),
    num_train_epochs=args.epochs,
    per_device_train_batch_size=args.batch_size,
    learning_rate=args.learning_rate,
    batch_sampler=BatchSamplers.NO_DUPLICATES,
    dataloader_drop_last=True,
    seed=args.seed, data_seed=args.seed,
    use_cpu=args.device == "cpu",
    save_strategy="no", report_to=[], logging_steps=1,
)
```

只支持单进程训练；检测 WORLD_SIZE 大于 1 则明确报错。CUDA 显式请求而不可用时报错。用相同版本的 NoDuplicatesBatchSampler、seed 和 drop_last 检查至少有一个完整批次，随后重置采样随机状态，避免检查改变实际顺序；不要依赖 sampler 的估算长度。确认后加载模型、设置 max_seq_length，并构建 Trainer 和 MultipleNegativesRankingLoss。

- [ ] **Step 4: 接入训练前后评估并保存结果。** 用 retrieval_data 构建验证映射，传递显式 query_prompt/corpus_prompt 和余弦函数。

```python
evaluator = InformationRetrievalEvaluator(
    queries, corpus, relevant_docs,
    query_prompt=args.query_prefix, corpus_prompt=args.document_prefix,
    score_functions={"cosine": cos_sim},
    precision_recall_at_k=[1, 5, 10], mrr_at_k=[10],
    write_csv=False,
)
before_metrics = evaluator(model)
trainer.train()
if trainer.state.global_step < 1:
    raise RuntimeError("没有执行训练步骤，拒绝保存成功产物")
after_metrics = evaluator(model)
model.save_pretrained(str(Path(args.output) / "model"))
```

上述评估调用仅在提供验证集时执行，训练调用两条路径共用。筛选实际返回键中的 recall@1/5/10 和 mrr@10，转为 Python float；JSON 使用 allow_nan=False。记录验证查询与文档数。run_config.json 保存 CLI 参数、实际前缀、基础模型和 importlib.metadata.version 查得的训练依赖版本。最终模型保存后再报告成功，失败保留异常，不伪造完成信息。默认路径加入 .gitignore。

- [ ] **Step 5: 写中文使用说明。** 包含以下命令、两条 JSONL 格式示例和可执行加载示例；明确示例数据只演示格式，正式训练需用户数据，batch size 不得超过可组成的完整批次大小。说明全参数训练显存开销、验证候选集范围、默认模型的语言适用性应由实际验证集衡量、其他模型需显式设置前缀、首次下载与真正离线运行的区别。

```bash
python3.11 -m venv /tmp/sll-embedding-venv
/tmp/sll-embedding-venv/bin/python -m pip install -r backend/requirements-embedding.txt
/tmp/sll-embedding-venv/bin/python backend/finetune_embedding.py \
  --train /absolute/path/train.jsonl --eval /absolute/path/eval.jsonl \
  --output backend/embedding-output --trust-remote-code
```

```python
import json
from pathlib import Path
from sentence_transformers import SentenceTransformer
output = Path("backend/embedding-output")
config = json.loads((output / "run_config.json").read_text())
model = SentenceTransformer(str(output / "model"),
                            trust_remote_code=config["trust_remote_code"])
query = model.encode([config["query_prefix"] + "待检索的问题"], normalize_embeddings=True)
documents = model.encode([config["document_prefix"] + "相关文档内容"], normalize_embeddings=True)
print(query @ documents.T)
```

- [ ] **Step 6: 运行验收并提交。** 运行标准库测试、开启真实训练测试、CLI 帮助和 git diff --check。安装环境可用时全部必须通过；当前环境无法运行的检查写入交付说明。检查 git diff 确保没有数据/权重/环境产物混入。提交本任务文件，提交信息 `feat: add offline embedding training and evaluation`。

## 执行与交付

推荐由当前会话顺序实现：两个任务共享一个小脚本，不需要并行实现。用户也可选择子代理逐任务实现与审查。
最终报告给出脚本和说明链接、实际运行的检查、未验证的依赖或模型兼容性；不能把本地小模型测试说成已完成用户数据的正式微调。

实现依据：[原生训练参数](https://sbert.net/docs/package_reference/sentence_transformer/training_args.html)、[检索评估器](https://sbert.net/docs/package_reference/sentence_transformer/evaluation.html)。
