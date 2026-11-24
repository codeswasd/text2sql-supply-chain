import pytest

from eval.run_eval import load_cases
from t2s.executor import Warehouse

CASES = load_cases()


@pytest.fixture(scope="module")
def wh():
    return Warehouse()


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_golden_sql_runs(wh, case):
    cols, rows = wh.run(case["sql"])
    assert cols
    assert rows, "golden query returned no rows"
