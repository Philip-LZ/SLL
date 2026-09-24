# 离线 Embedding 微调

此命令用 Sentence Transformers 对查询与相关文档做全参数对比学习。首次使用远程基础模型需要下载；模型已缓存或 `--model` 指向本地目录后才能真正离线运行。训练依赖单独安装，不影响后端服务环境。

```bash
python3.11 -m venv /tmp/sll-embedding-venv
/tmp/sll-embedding-venv/bin/python -m pip install -r backend/requirements-embedding.txt
/tmp/sll-embedding-venv/bin/python backend/finetune_embedding.py \
  --train /absolute/path/train.jsonl --eval /absolute/path/eval.jsonl \
  --output backend/embedding-output
```

`train.jsonl` 每行是一组查询与相关文档，例如：

```json
{"query": "如何减少模型训练时的显存占用？", "positive": "减小批大小和序列长度可以降低训练显存开销。"}
{"query": "如何验证检索模型？", "positive": "使用独立验证集比较检索指标。"}
```

上述两行只演示格式。正式训练需要用户提供足够多的真实、清洗后的训练对；每批文档互为负例，所以不同查询不能共享未标注的相关文档。`--batch-size` 至少为 2，且不能超过可组成的无重复完整批次。验证集用相同格式单独提供，查询不得与训练集重复；可省略 `--eval`，此时不会生成指标。

默认基础模型为 `nomic-ai/nomic-embed-text-v1.5`，默认查询前缀为 `search_query: `、文档前缀为 `search_document: `。其他模型必须同时明确传入 `--query-prefix` 和 `--document-prefix`，不需要前缀时传空字符串。需要执行模型自定义代码时才传 `--trust-remote-code`。默认 `--device auto` 优先 CUDA，未检测到时用 CPU；也可显式传 `--device cpu` 或 `--device cuda`。若要指定 PyTorch 的 CUDA 构建，请按 PyTorch 官方安装指引先在这个虚拟环境中安装适配显卡驱动的版本，再安装其余依赖；本项目的小模型验收仅在 CPU 上运行过。

全参数训练需要较多显存，可以减小 `--batch-size`、`--max-length`；默认最大长度 512。验证指标在验证集 positive 去重后的候选文档中计算 Recall@1/5/10 和 MRR@10，并不代表生产知识库的效果。默认模型对目标语言是否适用应由实际验证集判断。

产物位于 `output/model/`、`output/run_config.json`，有验证集时还有 `output/metrics.json`。按保存的前缀编码查询和文档：

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

要在同一份独立评测集上重新比较基础模型与微调模型，运行：

```bash
/tmp/sll-embedding-venv/bin/python -m backend.benchmark_embedding \
  --run-dir backend/embedding-output --k 5
```

脚本默认读取 `run_config.json` 中记录的训练集与验证集路径；文件迁移后可用 `--train`、`--eval` 指定新路径。输出 `benchmark.json`，包含当前训练文件去重后的样本数、模型名称、`MultipleNegativesRankingLoss`、查询与候选文档规模、数据文件 SHA-256、余弦相似度、Recall@K 和 MRR@K 的微调前后数值。统计训练样本数时需确保训练文件与当时微调使用的文件相同。K 不得大于候选文档数，训练与评测的 query 不能重叠。正式报告应使用足够大的独立评测语料，并保持基础模型权重版本、前缀和最大长度一致；两条样本的示例只能验证脚本可运行，不能证明效果提升。

接入现有在线检索是后续工作；届时需要用新模型重建文档向量。
