from eval.run_eval import load_cases
from t2s.retriever import SchemaRetriever
from t2s.schema_docs import build_docs


def test_every_table_has_a_doc():
    docs = build_docs()
    assert len(docs) == 11


def test_recall_on_golden_set():
    retriever = SchemaRetriever(build_docs())
    cases = load_cases()
    hits = sum(
        set(c["expected_tables"]) <= {t.lower() for t in retriever.retrieve(c["question"], k=3)} for c in cases
    )
    # Floor, not a target: guards against retrieval regressions.
    assert hits / len(cases) >= 0.8
