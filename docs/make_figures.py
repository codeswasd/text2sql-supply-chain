"""Regenerate every figure in docs/ from the repo's own data.

    python docs/make_figures.py

Needs matplotlib. Numbers come from the retriever, the golden set and the CSVs,
so the figures cannot drift from the code.
"""
import math
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.run_eval import load_cases  # noqa: E402
from t2s.retriever import SchemaRetriever  # noqa: E402
from t2s.schema_docs import build_docs, load_semantic  # noqa: E402

OUT = ROOT / "docs"
BLUE, ORANGE, GREEN, GREY, INK = "#2a6fdb", "#e0782b", "#2f9e6f", "#8a94a6", "#1f2933"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False})


def save(fig, name):
    fig.savefig(OUT / name, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", name)


def box(ax, x, y, w, h, title, sub, color):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=color, ec="none"))
    ax.text(x + w / 2, y + h * 0.62, title, ha="center", va="center", color="white", fontsize=11, fontweight="bold")
    ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center", color="white", fontsize=8)


def arrow(ax, p, q, style="-|>", color=INK, ls="-"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=14, color=color, lw=1.6, ls=ls))


def pipeline():
    fig, ax = plt.subplots(figsize=(13.4, 3.6))
    ax.set_xlim(0, 13.4)
    ax.set_ylim(0.9, 4.2)
    ax.axis("off")
    steps = [
        ("Question", "plain English", GREY),
        ("Retriever", "BM25 + 1-hop\nrelationships", BLUE),
        ("Claude", "SQL from top-k\ntable docs", ORANGE),
        ("Validator", "one SELECT / WITH\nread-only", GREEN),
        ("DuckDB", "views over\ndata/*.csv", BLUE),
        ("Answer", "SQL + rows\n+ tokens, latency", GREY),
    ]
    w, h, gap = 1.8, 1.3, 0.42
    for i, (t, s, c) in enumerate(steps):
        x = 0.2 + i * (w + gap)
        box(ax, x, 2.2, w, h, t, s, c)
        if i:
            arrow(ax, (x - gap + 0.02, 2.85), (x - 0.02, 2.85))
    # retry loop: validator/DuckDB error -> Claude
    x_claude = 0.2 + 2 * (w + gap) + w / 2
    x_duck = 0.2 + 4 * (w + gap) + w / 2
    # rad<0 bows the curve downward, under the boxes
    ax.add_patch(FancyArrowPatch((x_duck, 2.15), (x_claude, 2.15), connectionstyle="arc3,rad=-0.3",
                                 arrowstyle="-|>", mutation_scale=14, color=ORANGE, lw=1.6, ls="--"))
    ax.text((x_claude + x_duck) / 2, 1.2, "error text sent back once (retries=1)", ha="center", color=ORANGE, fontsize=9)
    # schema docs feeding the retriever
    ax.text(0.2 + (w + gap) + w / 2, 4.0, "Schema docs: semantic YAML + DDL comments", ha="center", color=INK, fontsize=9)
    arrow(ax, (0.2 + (w + gap) + w / 2, 3.88), (0.2 + (w + gap) + w / 2, 3.52))
    ax.set_title("Request path", loc="left", fontsize=13, fontweight="bold", color=INK)
    save(fig, "pipeline.png")


def er(docs):
    names = sorted(docs)
    pos = {n: (math.cos(2 * math.pi * i / len(names) - math.pi / 2), math.sin(2 * math.pi * i / len(names) - math.pi / 2))
           for i, n in enumerate(names)}
    edges = set()
    for rel in load_semantic().get("relationships", []) or []:
        a, b = rel["left_table"].upper(), rel["right_table"].upper()
        if a in docs and b in docs and a != b:
            edges.add(tuple(sorted((a, b))))
    fig, ax = plt.subplots(figsize=(8.5, 8.5))
    ax.set_xlim(-1.6, 1.6)
    ax.set_ylim(-1.45, 1.45)
    ax.axis("off")
    for a, b in edges:
        ax.plot(*zip(pos[a], pos[b]), color=GREY, lw=1.5, zorder=1)
    deg = Counter(x for e in edges for x in e)
    for n, (x, y) in pos.items():
        ax.scatter([x], [y], s=1500, color=BLUE, zorder=2)
        ax.text(x, y, str(deg[n]), color="white", ha="center", va="center", fontsize=12, fontweight="bold", zorder=3)
        ax.text(x * 1.27, y * 1.22, n.lower(), ha="center", va="center", fontsize=9.5, color=INK)
    ax.set_title(f"{len(names)} tables, {len(edges)} declared relationships (node label = join count)",
                 loc="left", fontsize=12, fontweight="bold", color=INK)
    save(fig, "schema_graph.png")


def recall_curve(docs, cases):
    ks = range(1, 6)
    res = {}
    for expand in (False, True):
        r = SchemaRetriever(docs)
        ys = []
        for k in ks:
            hit = 0
            for c in cases:
                got = {getattr(t, "name", t).lower() for t in r.retrieve(c["question"], k=k, expand=expand)}
                hit += {t.lower() for t in c["expected_tables"]} <= got
            ys.append(100 * hit / len(cases))
        res[expand] = ys
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.plot(ks, res[False], marker="o", color=GREY, lw=2, label="BM25 only")
    ax.plot(ks, res[True], marker="o", color=BLUE, lw=2.4, label="BM25 + relationship expansion")
    for k, v in zip(ks, res[True]):
        ax.annotate(f"{v:.0f}%", (k, v), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9, color=BLUE)
    ax.set_ylim(0, 108)
    ax.set_xticks(list(ks))
    ax.set_xlabel("k (tables sent to the model)")
    ax.set_ylabel("cases with all needed tables (%)")
    ax.set_title(f"Table recall@k on the {len(cases)}-question golden set", loc="left", fontweight="bold", color=INK)
    ax.legend(frameon=False, loc="lower right")
    ax.grid(axis="y", alpha=0.25)
    save(fig, "recall_at_k.png")
    return res


def golden(cases):
    diff = Counter(c["difficulty"] for c in cases)
    tabs = Counter(t.lower() for c in cases for t in c["expected_tables"])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4), gridspec_kw={"width_ratios": [1, 2], "wspace": 0.5})
    order = [d for d in ("easy", "medium", "hard") if d in diff]
    a1.bar(order, [diff[d] for d in order], color=[GREEN, ORANGE, BLUE][: len(order)])
    for i, d in enumerate(order):
        a1.text(i, diff[d] + 0.15, str(diff[d]), ha="center", fontweight="bold", color=INK)
    a1.set_title("Questions by difficulty", loc="left", fontweight="bold", color=INK)
    a1.set_yticks([])
    a1.spines["left"].set_visible(False)
    items = tabs.most_common()[::-1]
    a2.barh([t for t, _ in items], [n for _, n in items], color=BLUE)
    for i, (_, n) in enumerate(items):
        a2.text(n + 0.1, i, str(n), va="center", fontsize=9, color=INK)
    a2.set_title("Questions that need each table", loc="left", fontweight="bold", color=INK)
    a2.set_xticks([])
    a2.spines["bottom"].set_visible(False)
    save(fig, "golden_set.png")


def data_size():
    rows = {}
    for p in sorted((ROOT / "data").glob("*.csv")):
        with open(p, encoding="utf-8") as f:
            rows[p.stem] = sum(1 for _ in f) - 1
    items = sorted(rows.items(), key=lambda kv: kv[1])
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.barh([k for k, _ in items], [v for _, v in items], color=BLUE)
    for i, (_, v) in enumerate(items):
        ax.text(v + 6, i, str(v), va="center", fontsize=9, color=INK)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.set_title(f"Warehouse: {len(rows)} tables, {sum(rows.values()):,} rows", loc="left", fontweight="bold", color=INK)
    save(fig, "warehouse_rows.png")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    docs, cases = build_docs(), load_cases()
    pipeline()
    er(docs)
    print(recall_curve(docs, cases))
    golden(cases)
    data_size()
