"""Score the assistant on eval/golden.yaml.

    python -m eval.run_eval                  # retrieval recall@k + execution accuracy (needs ANTHROPIC_API_KEY)
    python -m eval.run_eval --retrieval-only # recall@k only, no API key needed

Writes eval/results.md.
"""
import argparse
from pathlib import Path

import yaml

from t2s.executor import Warehouse
from t2s.pipeline import Assistant
from t2s.validator import has_order_by, results_match

HERE = Path(__file__).resolve().parent


def load_cases(path: Path = HERE / "golden.yaml") -> list:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-k", type=int, default=3)
    p.add_argument("--retrieval-only", action="store_true")
    a = p.parse_args()

    cases = load_cases()
    bot = Assistant(k=a.k)
    wh = bot.wh if not a.retrieval_only else Warehouse()
    rows, hits, correct = [], 0, 0
    tok_in = tok_out = retried = 0
    lat = 0.0

    for c in cases:
        got = bot.retriever.retrieve(c["question"], k=a.k)
        expected = {t.lower() for t in c["expected_tables"]}
        recall_ok = expected <= {t.lower() for t in got}
        hits += recall_ok
        status = "-"
        if not a.retrieval_only:
            _, gold = wh.run(c["sql"])
            ans = bot.ask(c["question"])
            tok_in += ans.input_tokens
            tok_out += ans.output_tokens
            lat += ans.latency_s
            retried += ans.attempts > 1
            ok = ans.error is None and results_match(gold, ans.rows, ordered=has_order_by(c["sql"]))
            correct += ok
            status = "pass" if ok else ("error" if ans.error else "wrong")
        rows.append(f"| {c['id']} | {c['difficulty']} | {'yes' if recall_ok else 'no'} | {status} |")

    n = len(cases)
    summary = [f"- Table recall@{a.k} (all expected tables retrieved): **{hits}/{n} = {hits / n:.0%}**"]
    if not a.retrieval_only:
        summary.append(f"- Execution accuracy (result matches golden SQL): **{correct}/{n} = {correct / n:.0%}**")
        summary.append(f"- Tokens in/out: {tok_in}/{tok_out} total, {tok_in // n}/{tok_out // n} per question")
        summary.append(f"- Avg latency: {lat / n:.1f}s per question; {retried}/{n} needed a retry")
    report = "\n".join(
        ["# Eval results", "", *summary, "", "| case | difficulty | recall | execution |", "|---|---|---|---|", *rows, ""]
    )
    (HERE / "results.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
