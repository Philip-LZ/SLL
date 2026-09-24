"""Summarize human fact checks for paired long-form articles."""

import argparse
import csv
import hashlib
import json
from pathlib import Path


def score(path: Path, baseline_name: str, baseline_setting: str,
          candidate_name: str, candidate_setting: str) -> dict:
    counts = {"baseline": {}, "candidate": {}}
    seen = set()
    required = {"sample_id", "system", "claim_id", "correct", "evidence"}
    try:
        with path.open(newline="", encoding="utf-8-sig") as source:
            reader = csv.DictReader(source)
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError(f"{path}: 需要列 {', '.join(sorted(required))}")
            for line, row in enumerate(reader, 2):
                sample = (row["sample_id"] or "").strip()
                system = (row["system"] or "").strip()
                claim = (row["claim_id"] or "").strip()
                label = (row["correct"] or "").strip()
                evidence = (row["evidence"] or "").strip()
                if not sample or not claim or system not in counts or label not in ("0", "1") or not evidence:
                    raise ValueError(f"{path}:{line}: 需要 sample_id、baseline/candidate、claim_id、correct=0/1 和 evidence")
                key = (sample, system, claim)
                if key in seen:
                    raise ValueError(f"{path}:{line}: 重复的 sample_id/system/claim_id")
                seen.add(key)
                correct, total = counts[system].get(sample, (0, 0))
                counts[system][sample] = (correct + int(label), total + 1)
    except OSError as error:
        raise ValueError(f"{path}: {error}") from error

    if not counts["baseline"] or counts["baseline"].keys() != counts["candidate"].keys():
        raise ValueError("baseline 与 candidate 必须评测同一批文章，每篇至少一条事实主张")

    def stats(system):
        articles = counts[system].values()
        correct = sum(item[0] for item in articles)
        total = sum(item[1] for item in articles)
        article_mean = sum(ok / checked for ok, checked in counts[system].values()) / len(counts[system])
        return {"name": baseline_name if system == "baseline" else candidate_name,
                "setting": baseline_setting if system == "baseline" else candidate_setting,
                "claims": total, "correct_claims": correct,
                "pooled_accuracy": correct / total,
                "article_mean_accuracy": article_mean}

    baseline, candidate = stats("baseline"), stats("candidate")
    return {"articles": len(counts["baseline"]),
            "scoring": "逐条人工核实事实主张，正确=1、错误=0；每篇正确率=正确主张数/核实主张数；主指标为配对文章正确率的算术平均",
            "annotations_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "baseline": baseline, "candidate": candidate,
            "delta_percentage_points": round((candidate["article_mean_accuracy"] - baseline["article_mean_accuracy"]) * 100, 4)}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Score paired, manually checked long-form articles")
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--baseline-name", required=True)
    parser.add_argument("--baseline-setting", required=True)
    parser.add_argument("--candidate-name", required=True)
    parser.add_argument("--candidate-setting", required=True)
    parser.add_argument("--output", type=Path, help="JSON 报告路径")
    args = parser.parse_args(argv)
    try:
        result = score(args.annotations, args.baseline_name, args.baseline_setting,
                       args.candidate_name, args.candidate_setting)
        output = args.output or args.annotations.with_suffix(".report.json")
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(f"{result['articles']} 篇文章；事实准确率 "
          f"{result['baseline']['article_mean_accuracy']:.2%} → "
          f"{result['candidate']['article_mean_accuracy']:.2%} "
          f"({result['delta_percentage_points']:+.2f} 个百分点)")
    print(f"报告：{output}")


if __name__ == "__main__":
    main()
