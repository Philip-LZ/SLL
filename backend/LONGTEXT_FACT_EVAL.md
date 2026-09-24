# 长文事实准确率人工评测

对同一批写作题目，分别用基线模型和当前长文流程生成文章。人工将每篇文章拆成可核实的事实主张，为每条主张标 `correct=1`（有证据支持）或 `correct=0`（错误或无证据支持），并在 `evidence` 写出处或核查备注。把标注存为 UTF-8 CSV：

```csv
sample_id,system,claim_id,correct,evidence
topic-1,baseline,1,1,资料A第2段
topic-1,baseline,2,0,资料B第1段与主张矛盾
topic-1,candidate,1,1,资料A第2段
topic-1,candidate,2,1,资料B第1段
```

`system` 仅填 `baseline` 或 `candidate`。两组必须覆盖相同的 `sample_id`，每篇至少标一条主张；同篇文章内的 `claim_id` 不得重复。正式评测应固定题目、可用资料与核查标准，并记录基线模型、提示词及当前流程设置。

```bash
python3 -m backend.score_longtext_facts \
  --annotations /absolute/path/claims.csv \
  --baseline-name '基线模型名称' --baseline-setting '模型版本、提示词与资料设置' \
  --candidate-name '当前长文流程' --candidate-setting '流程版本、提示词与资料设置'
```

输出 `claims.report.json`。主指标先算每篇文章的正确主张比例，再对文章取算术平均；提升值是两组平均准确率之差，单位为百分点。报告也列出逐主张汇总的准确率和核查主张数，便于发现长文章对汇总分数的影响。标注样例仅说明格式，不能当作真实性能结果。
