"""Run validated SQL on DuckDB, with one view per CSV in data/ (view name = file stem)."""
from pathlib import Path

import duckdb

from .validator import validate_sql

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class Warehouse:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.con = duckdb.connect(":memory:")
        for csv in sorted(Path(data_dir).glob("*.csv")):
            # DuckDB identifiers are case-insensitive, so view "orders" also answers to ORDERS.
            path = csv.as_posix().replace("'", "''")
            self.con.execute(f"CREATE VIEW {csv.stem} AS SELECT * FROM read_csv_auto('{path}', header=true)")

    def run(self, sql: str, limit: int = 1000):
        sql = validate_sql(sql)
        cur = self.con.execute(sql)
        cols = [d[0] for d in cur.description]
        return cols, cur.fetchmany(limit)

    def tables(self) -> list:
        return [r[0] for r in self.con.execute("SELECT view_name FROM duckdb_views() WHERE NOT internal").fetchall()]
