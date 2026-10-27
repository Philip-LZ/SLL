# Embedding recovery implementation plan

> Execute inline using superpowers:executing-plans; user approved the recommended approach in chat on 2026-10-27.

**Goal:** Rebuild a reproducible public Chinese retrieval experiment with 1200 training pairs, 100 held-out test queries, 1000 fixed candidates, BGE base and in-batch InfoNCE.
**Architecture:** Extend the existing two CLI tools; one deterministic preparation tool produces train/dev/test files and separate candidate corpora. Choose training hyperparameters/checkpoint on dev only; evaluate the selected run on test once.
**Tech Stack:** Existing Python, unittest, Sentence Transformers, PyTorch, PyArrow.
**Spec:** User-approved design in this chat: original data lost; use public Chinese data, preserve in-batch InfoNCE first, hard negatives only as a separate experiment if needed. Online deployment is outside this experiment.

## Constraints and review focus

- Preserve existing local edits and historical artifacts. No API/database changes or new dependencies.
- Fixed corpus must contain every labeled positive, validate duplicate/empty documents; keep pair-only compatibility.
- No train/dev/test query overlap; exclude held-out documents from training; retain all known positive labels in each evaluation corpus.
- Test data never selects hyperparameters/checkpoints. Report macro Recall@10 and MRR@10, not success rate mislabeled as recall.
- Record source/model revision, data hashes, prompts, sequence length and actual sample counts. Public data may overlap base pretraining; no promise of reproducing old percentages.

## Tasks

- [x] Write failing tests for explicit candidate corpus, BGE prompt defaults and training controls; implement in finetune_embedding.py and benchmark_embedding.py. Run embedding tests and tiny real training.
- [x] Write deterministic split tests; implement prepare_embedding_experiment.py for pinned local T2Reranking parquet, 1200/100/100 query split and dev/test corpora of 1000 documents with labeled hard distractors. Persist hashes and split assertions.
- [x] Run BGE-base CUDA training with two dev-only configurations (batch32/lr2e-5 and batch64/lr1e-5, up to 3 epochs); select by dev Recall@10, retaining baseline if no improvement. Benchmark selected checkpoint once on held-out test.
- [x] Add usage/results/limitations to docs/EMBEDDING_FINETUNING.md, save compact reproducibility report outside ignored artifacts, run full tests and diff whitespace check, review changes.


## Execution record

Implemented inline in the user's existing dirty checkout, preserving pre-existing restructuring. No commits or online deployment. Extended the approved negative ablation after dev failed to improve: same1200 pairs plus one source judged negative, all known-positive collisions excluded. Five final v3 configurations evaluated on dev; best fine-tune b64/lr1e-5 scored .875527 vs base .878464. Freeze `docs/experiments/2026-10-27-embedding/selection.json` before test; recommend base. One held-out comparison: Recall@10 .898770 -> .896768, MRR@10 .943333 -> .944167. No further tuning after test.

Review: separate reviewer found resolved-model revision fallback and report-overwrite risks; fixed. Optional negative preparation independently reviewed; actual data show equal1200 pairs and no known positive/negative collisions. CPU smoke uncovered a pre-existing cross-device comparison bug (fixed test base device) and new checkpoint serialization/Transformers interface compatibility issues (picklable sampler, model-level checkpoint enable); regression tests passed. No deferred review findings.

Ruling: keep large model/data outputs ignored but preserve manifests, configurations and final report under docs/experiments so results survive source-control backups; user still must back up weights and raw data. Ruling: final test compares best trained model even though dev recommends base, solely to document the failed fine-tuning experiment; deployment recommendation stays base.
