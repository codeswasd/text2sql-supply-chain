import pytest

from t2s.validator import has_order_by, results_match, strip_fences, validate_sql


def test_accepts_select_and_with():
    assert validate_sql("SELECT 1;") == "SELECT 1"
    assert validate_sql("WITH x AS (SELECT 1) SELECT * FROM x")


def test_strips_markdown_fences():
    assert strip_fences("```sql\nSELECT 1\n```") == "SELECT 1"


@pytest.mark.parametrize("sql", [
    "DROP TABLE orders",
    "SELECT 1; DELETE FROM orders",
    "INSERT INTO orders VALUES (1)",
    "WITH x AS (SELECT 1) UPDATE orders SET a = 1",
    "",
])
def test_rejects_writes_and_multi_statements(sql):
    with pytest.raises(ValueError):
        validate_sql(sql)


def test_keyword_inside_string_literal_is_allowed():
    assert validate_sql("SELECT * FROM orders WHERE status = 'update; drop'")


def test_results_match_ignores_order_unless_asked():
    assert results_match([(1, "a"), (2, "b")], [(2, "b"), (1, "a")])
    assert not results_match([(1, "a"), (2, "b")], [(2, "b"), (1, "a")], ordered=True)


def test_results_match_tolerates_extra_columns_and_float_noise():
    assert results_match([(3.00001,)], [("x", 3.000012)])


def test_has_order_by():
    assert has_order_by("select a from t order  by a")
    assert not has_order_by("select a from t")
