"""Usage: python -m t2s.cli "How many active plants do we have?"   (add --dry to only show retrieved tables)"""
import argparse

from .pipeline import Assistant


def main():
    p = argparse.ArgumentParser(description="Ask the supply-chain warehouse a question in plain English.")
    p.add_argument("question")
    p.add_argument("-k", type=int, default=3, help="tables to retrieve before expansion")
    p.add_argument("--dry", action="store_true", help="show retrieved tables only, no LLM call")
    a = p.parse_args()

    bot = Assistant(k=a.k)
    if a.dry:
        print("tables:", ", ".join(bot.retriever.retrieve(a.question, k=a.k)))
        return
    ans = bot.ask(a.question)
    print("tables:", ", ".join(ans.tables))
    print("sql:\n" + ans.sql)
    print(f"tokens in/out: {ans.input_tokens}/{ans.output_tokens} | latency: {ans.latency_s:.1f}s | attempts: {ans.attempts}")
    if ans.error:
        print("error:", ans.error)
        return
    print(" | ".join(ans.columns))
    for r in ans.rows[:50]:
        print(" | ".join(str(x) for x in r))


if __name__ == "__main__":
    main()
