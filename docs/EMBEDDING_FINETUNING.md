# 离线 Embedding 微调

此命令用 Sentence Transformers 对查询与相关文档做全参数对比学习。首次使用远程基础模型需要下载；模型已缓存或 `--model` 指向本地目录后才能真正离线运行。训练依赖单独安装，不影响后端服务环境。

从仓库根目录创建并激活 Conda 环境（Python 3.12）：

```bash
conda env create -f environment.yml
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate SLL
python -m pip check
python -m backend.tools.finetune_embedding \
  --train /absolute/path/train.jsonl --eval /absolute/path/eval.jsonl \
  --output backend/embedding-output
```

`train.jsonl` 每行是一组查询与相关文档，例如：

```json
{"query": "如何减少模型训练时的显存占用？", "positive": "减小批大小和序列长度可以降低训练显存开销。"}
{"query": "如何验证检索模型？", "positive": "使用独立验证集比较检索指标。"}
```

上述两行只演示格式。正式训练需要用户提供足够多的真实、清洗后的训练对；每批文档互为负例，所以不同查询不能共享未标注的相关文档。`--batch-size` 至少为 2，且不能超过可组成的无重复完整批次。验证集用相同格式单独提供，查询不得与训练集重复；可省略 `--eval`，此时不会生成指标。

默认基础模型为 `BAAI/bge-base-zh-v1.5`，默认查询前缀为 `为这个句子生成表示以用于检索相关文章：`、文档前缀为空。显式使用 `nomic-ai/nomic-embed-text-v1.5` 时仍自动使用它的 `search_query: ` / `search_document: ` 前缀。其他模型必须同时明确传入 `--query-prefix` 和 `--document-prefix`，不需要前缀时传空字符串。需要执行模型自定义代码时才传 `--trust-remote-code`。默认 `--device auto` 优先 CUDA，未检测到时用 CPU；也可显式传 `--device cpu` 或 `--device cuda`。若要指定 PyTorch 的 CUDA 构建，请按 PyTorch 官方安装指引先在这个虚拟环境中安装适配显卡驱动的版本，再安装其余依赖；小模型冒烟验收在 CPU 上执行，BGE base 正式实验已在本机 CUDA 上执行，结果见文末。

全参数训练需要较多显存，可以减小 `--batch-size`、`--max-length`；默认最大长度 512。通过 `--corpus` 传入固定候选文档 JSONL（每行 `{"text":"文档内容"}`），必须包含所有标注正例，不能有重复或空文档。不传时，兼容旧流程，在验证集 positive 去重后的候选文档中计算 Recall@1/5/10 和 MRR@10。`--eval` 是开发集：每轮评测并按 Recall@10 加载最佳 checkpoint 后保存最终模型，不应传入最终测试集。评测不代表生产知识库的效果。默认模型对目标语言是否适用应由实际验证集判断。

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
python -m backend.tools.benchmark_embedding \
  --run-dir backend/embedding-output --k 5
```

脚本默认读取 `run_config.json` 中记录的训练集与验证集路径；文件迁移后可用 `--train`、`--eval` 指定新路径。输出 `benchmark.json`，包含当前训练文件去重后的样本数、模型名称、`MultipleNegativesRankingLoss`、查询与候选文档规模、数据文件 SHA-256、余弦相似度、Recall@K 和 MRR@K 的微调前后数值。统计训练样本数时需确保训练文件与当时微调使用的文件相同。K 默认 10，不得大于候选文档数，训练与评测的 query 不能重叠。新训练记录训练文件 SHA-256；重新评测时若文件变化则拒绝报告。正式报告应使用足够大的独立评测语料，并保持基础模型权重版本、前缀和最大长度一致；两条样本的示例只能验证脚本可运行，不能证明效果提升。

接入现有在线检索是后续工作；届时需要用新模型重建文档向量。

## 环境验证与离线运行

环境仅安装独立训练和评测依赖，不包含 API、数据库及长文服务的运行环境。已有 `SLL` 环境时，直接激活后运行 `python -m pip install -r backend/requirements-embedding.txt`，无需重复创建。

无 GPU 的机器可以先安装 CPU 构建，再安装其余依赖：

```bash
conda create -n SLL python=3.12 pip --override-channels -c conda-forge -y
conda activate SLL
python -m pip install torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r backend/requirements-embedding.txt
```

检查 GPU 和训练流程；训练冒烟测试使用临时创建的小模型与合成样本，不下载权重，也不代表实际检索效果：

```bash
python -c "import torch; print('torch:', torch.__version__, 'CUDA:', torch.cuda.is_available())"
SLL_EMBEDDING_SMOKE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 python -m unittest discover -s tests -v
```

正式离线训练前，先在联网环境下载基础模型（默认缓存位于 Hugging Face 缓存目录），然后设置离线变量：

```bash
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-base-zh-v1.5')"
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 python -m backend.tools.finetune_embedding \
  --train /absolute/path/train.jsonl --eval /absolute/path/eval.jsonl \
  --output backend/embedding-output --batch-size 16 --device auto
```

本机 RTX 5070 Ti 使用 CUDA 13.0 构建，在已有环境中替换 CPU 版：

```bash
conda activate SLL
python -m pip install 'torch==2.14.0+cu130' --index-url https://download.pytorch.org/whl/cu130
python -m pip check
python -c "import torch; assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0)); x = torch.ones(2, device='cuda'); assert (x + x).cpu().tolist() == [2.0, 2.0]"
```

WSL 下可用 `/usr/lib/wsl/lib/nvidia-smi` 检查驱动。若报告操作系统禁止访问 GPU，先在普通 WSL 终端或沙箱外复查：本机 Codex 沙箱不暴露 `/dev/dxg`，会产生此报错。若沙箱外也失败，再修复宿主机/WSL 的 GPU 访问；仅安装 CUDA 版 PyTorch 不能解除访问限制。WSL 使用 Windows 提供的驱动，不要在 WSL 内另装 Linux 显卡驱动，参见 [NVIDIA WSL 指引](https://docs.nvidia.com/cuda/wsl-user-guide/)。

2026-10-27 已在沙箱外验证：`torch 2.14.0+cu130`、CUDA runtime 13.0、RTX 5070 Ti，`torch.cuda.is_available()` 返回 `True`，GPU 矩阵乘法及反向传播通过，`pip check` 无依赖冲突。此检查未重跑完整微调实验。

## 本机实验（2026-10-27）

初次实验创建 Conda 环境 `SLL`（Python 3.12.16，当时为 PyTorch 2.14.0+cpu）。沙箱内 NVIDIA 工具报告 `GPU access blocked by the operating system`，以下实验使用 CPU；后续已按上节切换为 CUDA 构建，并确认沙箱外 GPU 可用。

使用公开中文数据 [C-MTEB/T2Reranking](https://huggingface.co/datasets/C-MTEB/T2Reranking) 的 dev 数据自行划分实验子集：随机种子 42，512 条 query–positive 训练样本，128 个验证 query，940 篇验证候选文档。验证查询保留全部正例；训练与验证没有完全相同的 query 或正例文档。数据来源、版本、划分说明和 SHA-256 保存在 `backend/embedding-output/data/manifest.json`，划分脚本为 `backend/embedding-output/prepare_experiment.py`。

基础模型为 [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5)，固定 revision `7999e1d3359715c523056ef9478215996d62a620`。沿用 `MultipleNegativesRankingLoss`，学习率 2e-5，batch size 8，最大长度 128，训练 1 轮（64 步）。以下命令全部使用本地模型和数据，训练与评测阶段不联网：

```bash
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate SLL
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
python -m backend.tools.finetune_embedding \
  --train "$PWD/backend/embedding-output/data/train.jsonl" \
  --eval "$PWD/backend/embedding-output/data/eval.jsonl" \
  --model "$PWD/backend/embedding-output/base-model" \
  --query-prefix '为这个句子生成表示以用于检索相关文章：' --document-prefix '' \
  --output backend/embedding-output/t2-bge-run --batch-size 8 --epochs 1 \
  --learning-rate 2e-5 --max-length 128 --device auto

HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
python -m backend.tools.benchmark_embedding \
  --run-dir backend/embedding-output/t2-bge-run --k 5 --device auto
```

本次已占用 `t2-bge-run` 输出目录；重跑训练时改用新目录，避免覆盖已有模型。结果、配置和重新加载后的评测报告均保存在该目录。基础模型、数据、模型产物及完整依赖快照保存在 Git 忽略的 `backend/embedding-output/`，需自行备份。

在相同前缀、最大长度和余弦检索设置下，Recall@5 从 **68.28% 提升至 68.98%（+0.70 个百分点）**。这是公开 dev 集的自定义小规模划分，候选库仅含验证正例，不包含原始 hard negatives；未排除基础模型预训练见过数据的可能，也未做多随机种子显著性检验，不能视作官方榜单成绩或真实业务效果。


## 恢复实验流程（2026-10-27）

原始 1200 条样本及评测数据已丢失，历史实验无法复现。以下是重新划分公开中文 T2Reranking dev 的新实验，不代表恢复了简历中的 72.4% → 81.6%。新增划分脚本进入版本管理，模型和数据仍保存在忽略目录；请备份该目录。

下载固定版本的源数据和基础模型（只需联网执行一次）：

```bash
python - <<'PYTHON'
from huggingface_hub import hf_hub_download, snapshot_download
hf_hub_download('C-MTEB/T2Reranking', 'data/dev-00000-of-00001-65d96bde8023d9b9.parquet',
                repo_type='dataset', revision='76631901a18387f85eaa53e5450019b87ad58ef9',
                local_dir='backend/embedding-output/t2-source')
snapshot_download('BAAI/bge-base-zh-v1.5',
                  revision='f03589ceff5aac7111bd60cfc7d497ca17ecac65',
                  local_dir='backend/embedding-output/bge-base-zh-v1.5',
                  allow_patterns=['*.json', 'pytorch_model.bin', 'vocab.txt', '1_Pooling/*'])
PYTHON
python -m backend.tools.prepare_embedding_experiment \
  --source backend/embedding-output/t2-source/data/dev-00000-of-00001-65d96bde8023d9b9.parquet \
  --output backend/embedding-output/recovery-data-v3
```

脚本校验固定源文件 SHA-256，种子 42，生成 1200 条训练对、开发集和测试集各 100 个查询，以及各自的 1000 篇固定候选文档。保留查询的全部已知正例，以原数据的标注负例填充候选库；查询跨集合不重叠，训练排除两个评测候选库中的文档，并利用源数据的全部已知正例排除训练查询之间的正例冲突。为使正负例对照使用相同样本，两组划分都预留一篇有效原始负例；纯 pair 训练不会读取它。默认训练仍只使用 query–positive，两组评测候选库中的负例不参与训练。开发集有 708 个正例标注，测试集有 831 个；这两个数字是相关文档标注数量，不是查询数。

GPU 训练第一组设置（输出目录必须为空；更换目录重跑）：

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 python -m backend.tools.finetune_embedding \
  --train "$PWD/backend/embedding-output/recovery-data-v3/train.jsonl" \
  --eval "$PWD/backend/embedding-output/recovery-data-v3/dev.jsonl" \
  --corpus "$PWD/backend/embedding-output/recovery-data-v3/dev_corpus.jsonl" \
  --model "$PWD/backend/embedding-output/bge-base-zh-v1.5" \
  --revision f03589ceff5aac7111bd60cfc7d497ca17ecac65 \
  --query-prefix '为这个句子生成表示以用于检索相关文章：' --document-prefix '' \
  --output backend/embedding-output/recovery-v3-b32 \
  --batch-size 32 --epochs 3 --learning-rate 2e-5 --max-length 256 \
  --device cuda --bf16 --gradient-checkpointing
```

第二组仅将 batch size 改为 64、learning rate 改为 1e-5，输出改为 `recovery-v3-b64`。比较两个目录的 `metrics.json` 中开发集 `after.recall@10`，选择最高者；若均低于基础模型，保留基础模型，不宣称成功提升。`--scale` 默认 20，即 InfoNCE 温度 0.05；较大 batch 增加批内负例数量，普通梯度累积不能替代这一点。`--bf16` 和 `--gradient-checkpointing` 用来减少 GPU 显存，CPU 上不要启用 bf16。

确定配置后，仅对选中的模型执行最终测试（将 run-dir 替换为选中目录）：

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 python -m backend.tools.benchmark_embedding \
  --run-dir backend/embedding-output/recovery-v3-b32 \
  --eval "$PWD/backend/embedding-output/recovery-data-v3/test.jsonl" \
  --corpus "$PWD/backend/embedding-output/recovery-data-v3/test_corpus.jsonl" \
  --k 10 --device cuda --output backend/embedding-output/recovery-test.json
```

基础模型和微调模型使用同一候选库、同一查询、同一前缀和最大长度，以余弦相似度全量排序；新模型的文档向量重新编码。Recall@10 定义为各查询“前十条中的相关文档数 / 全部已标注相关文档数”的宏平均。多个查询超过 10 篇正例，因此测试集理论上限约 93.71%，不能与 Hit@10（前十条命中任意一篇）混用。

这是公开 dev 集的自定义划分，基础模型可能预训练见过数据，相关标注也未必完整。新实验不能承诺复现旧数字；测试集不用于挑选训练参数或 checkpoint。


原始标注负例对照单独生成，默认的 pair 流程不变：

```bash
python -m backend.tools.prepare_embedding_experiment \
  --source backend/embedding-output/t2-source/data/dev-00000-of-00001-65d96bde8023d9b9.parquet \
  --output backend/embedding-output/recovery-hard-data-v3 --include-negatives
```

该目录的 `train.jsonl` 增加非空字符串 `negative` 字段，整份文件必须全部提供或全部不提供，负例不能是该查询的已知正例。它使用与 pair 组完全相同的 1200 个 query–positive，只补充原始数据按顺序选出的第一篇有效标注负例；排除所有训练查询的已知正例及两个评测候选库文本，不执行模型挖掘。训练器原生 MultipleNegativesRankingLoss 同时使用批内负例和显式负例。用上述训练命令替换数据目录为 `recovery-hard-data-v3`、batch size 64、学习率 1e-5、输出 `recovery-v3-negative-b64` 即可复现。若采用此结果写简历，应说明加入了显式标注负例，不能仍写成仅使用 query–positive 的实验。

所有新报告拒绝覆盖已有路径。当前 Transformers 5.17 / Sentence Transformers 6.1 在 Trainer 自动启用梯度检查点时有参数接口差异；脚本直接通过模型启用，真实 CPU 冒烟训练覆盖这条路径。梯度检查点不会改变批内对比学习的 batch size。


## 恢复实验结果与结论

本机 RTX 5070 Ti、PyTorch 2.14.0+cu130，在相同 v3 训练划分上执行下表五组设置。均从同一固定版本 BGE base 开始，最大长度 256、3 epochs、seed 42、10% warmup、bf16、梯度检查点；每组只按开发集 Recall@10 选择 checkpoint，未用测试集挑参数。

| 训练输入 | batch size | 学习率 | 温度 | 开发集 Recall@10 |
| --- | ---: | ---: | ---: | ---: |
| 基础模型 | — | — | — | 87.8464% |
| query–positive | 32 | 2e-5 | 0.05 | 86.3420% |
| query–positive | 64 | 1e-5 | 0.05 | **87.5527%** |
| 加一篇原始标注负例 | 64 | 1e-5 | 0.05 | 87.0214% |
| query–positive | 128 | 5e-6 | 0.02 | 87.5429% |
| 加一篇原始标注负例 | 128 | 5e-6 | 0.02 | 86.9141% |

后两组在上述命令基础上设置 `--batch-size 128 --learning-rate 5e-6 --scale 50`，输出分别为 `recovery-v3-b128-t002`、`recovery-v3-negative-b128-t002`。显式负例组改用 `recovery-hard-data-v3`，其余不变。

开发集最佳微调目录是 `backend/embedding-output/recovery-v3-b64`。由于其开发集成绩低于基础模型，**实际建议保留基础模型**。在测试前先写入 [选型记录](experiments/2026-10-27-embedding/selection.json)，随后仅比较一次基础模型与开发集最佳微调模型，用于记录实验结论；没有根据测试结果再训练。

| 最终独立测试（100 查询、同一 1000 篇候选文档） | 基础模型 | 最佳微调模型 | 差值 |
| --- | ---: | ---: | ---: |
| Recall@10 | 89.8770% | 89.6768% | -0.2002 个百分点 |
| MRR@10 | 94.3333% | 94.4167% | +0.0833 个百分点 |

完整测试报告：[test.json](experiments/2026-10-27-embedding/test.json)。数据版本和哈希：[pair 划分](experiments/2026-10-27-embedding/pairs-manifest.json)、[负例对照划分](experiments/2026-10-27-embedding/negatives-manifest.json)。选型记录包含各轮配置、依赖版本、开发集指标，以及基础/最终模型权重文件 SHA-256。实际训练日志、checkpoint 和模型在被 Git 忽略的各输出目录中，需另行备份。早期 `recovery-b32` / `recovery-b64` 和 v1/v2 数据目录属于准备阶段探索，未用于最终选择或测试；以本节的 v3 文件哈希为准。

这次实验没有验证到 Recall@10 提升。基础模型在这份公开子集上已达到 89.88%，相对于理论上限 93.71% 仅剩约 3.83 个百分点空间，不能在这份数据上承诺原简历的 +9.2 个百分点。增加 batch、减小学习率和补充原始负例都没有在开发集上带来收益；仅凭训练 loss 下降不能判断检索改善。基础模型可能见过公开数据、标注不完整、少量训练数据与目标任务的差异都需要进一步调查，当前结果不足以区分这些原因。

下一步应重建真实业务查询与相关文档标注，扩大独立评测并人工复核困难负例；用新开发/测试划分继续实验，避免对当前 100 条测试查询反复调参。原 72.4% → 81.6% 没有留下可复核证据，不能用本次结果替代证明。当前简历可以描述实际完成的 BGE/InfoNCE 流程、数据校验和固定候选库评测，先去掉未经复现的提升数字。

验证：`SLL_EMBEDDING_SMOKE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 python -m unittest discover -s tests -v`，33 项中 32 项通过、1 项跳过（当前有 GPU，跳过“CUDA 不可用”分支）；涵盖真实小模型训练、权重更新、checkpoint 保存重载、显式负例、候选库和数据划分校验。另已实际执行上述五组 GPU 训练和最终模型重载评测。未接入在线数据库检索，未验证真实业务数据上的收益。


## 后续：用户要求生成数据再实验

新增独立的[中文模板合成实验](experiments/2026-10-27-synthetic-embedding/README.md)，生成器为 `python -m backend.tools.generate_synthetic_embedding`。使用1200条虚构企业知识库训练对，团队及事实跨集合隔离，开发/测试各100查询和1000候选文档。两组预定配置按开发集选择后，最终合成测试 Recall@10 为80%→100%，MRR@10为47.01%→58.72%。这是有限模板任务的结果，不能替代前文公开数据实验或原简历数字，也没有验证真实业务收益。完整数据、模板、版本、选型记录和报告见链接。
