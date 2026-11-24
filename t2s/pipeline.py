"""End-to-end: retrieve tables, generate SQL, validate, execute, retry once on error."""
import time
from dataclasses import dataclass, field

from .executor import Warehouse
from .generator import generate_sql
from .retriever import SchemaRetriever
from .schema_docs import build_docs, custom_instructions


@dataclass
class Answer:
    question: str
    tables: list
    sql: str = ""
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    attempts: int = 0


class Assistant:
    def __init__(self, k: int = 3):
        self.docs = build_docs()
        self.retriever = SchemaRetriever(self.docs)
        self.instructions = custom_instructions()
        self.wh = Warehouse()
        self.k = k

    def ask(self, question: str, retries: int = 1) -> Answer:
        tables = self.retriever.retrieve(question, k=self.k)
        blocks = [self.docs[t].prompt_block() for t in tables]
        ans = Answer(question, tables)
        error = None
        t0 = time.perf_counter()
        try:
            for _ in range(retries + 1):
                ans.sql, tin, tout = generate_sql(question, blocks, self.instructions, error)
                ans.attempts += 1
                ans.input_tokens += tin
                ans.output_tokens += tout
                try:
                    ans.columns, ans.rows = self.wh.run(ans.sql)
                    ans.error = None
                    return ans
                except Exception as e:  # validation or DuckDB error: feed it back to the model once
                    error = ans.error = str(e)
            return ans
        finally:
            ans.latency_s = time.perf_counter() - t0
