"""Read-only SQL guard and result comparison used by the executor and the eval harness."""
import math
import re

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|create|alter|truncate|grant|revoke|copy|attach|detach|install|load|pragma|call|set)\b",
    re.I,
)


def strip_fences(sql: str) -> str:
    sql = re.sub(r"^```(?:sql)?\s*|\s*```$", "", sql.strip(), flags=re.I)
    return sql.strip().rstrip(";").strip()


def validate_sql(sql: str) -> str:
    """Return cleaned SQL or raise ValueError. Allows one SELECT/WITH statement only."""
    sql = strip_fences(sql)
    if not sql:
        raise ValueError("empty SQL")
    # Drop string literals before keyword checks so 'update' inside a value is not a false hit.
    bare = re.sub(r"'(?:[^']|'')*'", "''", sql)
    bare = re.sub(r"--[^\n]*|/\*.*?\*/", " ", bare, flags=re.S)
    if ";" in bare:
        raise ValueError("multiple statements are not allowed")
    if not re.match(r"^\s*(select|with)\b", bare, re.I):
        raise ValueError("only SELECT or WITH queries are allowed")
    if FORBIDDEN.search(bare):
        raise ValueError(f"forbidden keyword: {FORBIDDEN.search(bare).group(0)}")
    return sql


def _norm(v, ndigits: int = 4):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) or type(v).__name__ == "Decimal":
        f = float(v)
        return None if math.isnan(f) else round(f, ndigits)
    return str(v).strip()


def results_match(expected: list, actual: list, ordered: bool = False) -> bool:
    """Compare row values only (column names ignored). Row order matters only when ordered=True."""
    exp = [tuple(_norm(x) for x in r) for r in expected]
    act = [tuple(_norm(x) for x in r) for r in actual]
    if len(exp) != len(act):
        return False
    if exp and act and len(exp[0]) != len(act[0]):
        # Model picked extra/fewer columns: accept if every expected column appears in the actual rows.
        return _columns_subset(exp, act, ordered)
    if ordered:
        return exp == act
    key = lambda r: tuple((x is None, str(x)) for x in r)
    return sorted(exp, key=key) == sorted(act, key=key)


def _columns_subset(exp: list, act: list, ordered: bool) -> bool:
    act_cols = list(zip(*act))
    for col in zip(*exp):
        if ordered:
            if col not in act_cols:
                return False
        elif sorted(map(str, col)) not in [sorted(map(str, c)) for c in act_cols]:
            return False
    return True


def has_order_by(sql: str) -> bool:
    return re.search(r"\border\s+by\b", sql, re.I) is not None
