# 合成中文企业知识库检索实验

用户要求自行生成数据再运行一次。本实验使用手写中文模板、同义问法和固定种子的虚构政策字段，不调用外部模型 API，不包含真实企业制度，也不恢复原来的简历实验。

## 训练前固定的设计

- 120 个虚构的城市/部门团队，固定种子 20261027，按团队分成训练/开发/测试各 40 个，实例事实不跨集合。
- 每个团队 10 类操作 × 3 种环境。训练 1200 条 query–positive；开发和测试各固定 1000 篇候选文档，抽取其中 100 个事实生成独立查询。
- 每个查询恰好一个相关文档，按团队、环境和事项共同判定；Recall@10 因此等于 Hit@10，100 查询的数值以1个百分点变化。文档和查询均不注入事实 ID。
- 各集合使用不同的提问模板、事项同义表达、环境同义表达和文档模板；主题概念与部分城市/部门词汇共享。这是实体组合泛化，不能说成未见过新领域的泛化。
- 全部数据、候选库和标注在模型评分前生成并冻结，不按模型表现筛选题目。
- 从固定版本 BAAI/bge-base-zh-v1.5 开始，纯批内 InfoNCE，scale20、max length256、seed42、bf16、梯度检查点、10% warmup。预先固定两组训练配置：batch64/lr1e-5/5epochs，batch32/lr2e-5/5epochs。
- 每组仅按开发集 Recall@10 选 checkpoint，再在两组中按开发集选择，平局用开发集 MRR@10。最终测试只比较一次基础模型与选中的微调模型；测试后不调参。基础模型若在开发集更优，推荐保留基础模型。
- 基础权重、历史公开数据实验及其结果均保留。仅新增生成器、测试和独立实验产物，不修改线上检索。

## 复现

```bash
python -m backend.tools.generate_synthetic_embedding \
  --seed 20261027 --output backend/embedding-output/synthetic-data-v1
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 python -m backend.tools.finetune_embedding \
  --train "$PWD/backend/embedding-output/synthetic-data-v1/train.jsonl" \
  --eval "$PWD/backend/embedding-output/synthetic-data-v1/dev.jsonl" \
  --corpus "$PWD/backend/embedding-output/synthetic-data-v1/dev_corpus.jsonl" \
  --model "$PWD/backend/embedding-output/bge-base-zh-v1.5" \
  --revision f03589ceff5aac7111bd60cfc7d497ca17ecac65 \
  --query-prefix '为这个句子生成表示以用于检索相关文章：' --document-prefix '' \
  --output backend/embedding-output/synthetic-v1-b64 \
  --batch-size 64 --learning-rate 1e-5 --epochs 5 --max-length 256 \
  --device cuda --bf16 --gradient-checkpointing
```

第二组改为 batch32、学习率2e-5、输出 `synthetic-v1-b32`，其余相同。模型下载方法见上一级微调说明。

## 限制

这是窄领域、有限模板与槽位组成的合成测试，程序标注保证的是人为定义的适用范围，未做自然语言人工逐条判定。真实用户可能接受同事项其他团队的通用说明，而本数据按团队和环境严格区分。因此即使大幅提升，也只能说明模型学会了该合成任务；不能替代真实业务检索效果，不能拿来证实原来72.4%→81.6%的结果。


## 实际结果（RTX 5070 Ti）

两组均从原始基础模型训练，未从上次公开数据微调权重继续训练：

| 设置 | 开发集 Recall@10 | 开发集 MRR@10 |
| --- | ---: | ---: |
| 基础模型 | 68.00% | 36.11% |
| synthetic-v1-b64 | 93.00% | 56.35% |
| synthetic-v1-b32 | 92.00% | 53.49% |

按开发集选择 `synthetic-v1-b64`，最佳 checkpoint 在第2轮（step36）；完整执行5轮共90步后由训练器加载最佳权重。选型记录在测试评分之前写入 [selection.json](selection.json)。

| 最终独立合成测试：100查询、固定1000候选文档 | 基础模型 | 微调模型 | 差值 |
| --- | ---: | ---: | ---: |
| Recall@10 | 80.00% | 100.00% | +20.00个百分点 |
| MRR@10 | 47.01% | 58.72% | +11.72个百分点 |

完整报告：[test.json](test.json)；数据与生成器哈希：[manifest.json](manifest.json)；三组各一条示例：[examples.json](examples.json)。没有根据这个测试结果再改数据、模板或训练参数。Recall@10为100%只代表所有查询的唯一标注正例都在前10条，MRR说明排序仍不完美，不能理解为全部top1命中。

这次结果表明现有训练流程能够学会这套有限模板任务中按团队、环境、操作事项匹配的规则。它不否定前一次真实公开数据上没有收益的结果，也不能证明现实业务召回提升了20个百分点。两次测试的语言分布、相关性定义、候选文档和正例数量均不同，不能横向比较百分比。

最终重载评测命令：

```bash
HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 python -m backend.tools.benchmark_embedding \
  --run-dir backend/embedding-output/synthetic-v1-b64 \
  --eval "$PWD/backend/embedding-output/synthetic-data-v1/test.jsonl" \
  --corpus "$PWD/backend/embedding-output/synthetic-data-v1/test_corpus.jsonl" \
  --k 10 --device cuda --output /absolute/path/to/new-synthetic-report.json
```

已生成的数据位于 `backend/embedding-output/synthetic-data-v1/`，包含训练对、开发/测试查询、两份候选库、全部事实映射和元数据。权重及日志位于 `backend/embedding-output/synthetic-v1-b64/` 和 `synthetic-v1-b32/`。这些目录被Git忽略；生成器可以重建数据，训练权重仍需自行备份。

验证：完整测试35项中34项通过、1项跳过（当前GPU可用，跳过不可用分支）；生成器独立审查未发现数据/标注/集合隔离缺陷。实际执行了两组GPU训练及一次最终模型重载评测。未做多随机种子实验或真实业务外部验证。
