"""Turn a question plus retrieved schema blocks into one DuckDB SELECT using Claude."""
import os

from .validator import strip_fences

MODEL = os.getenv("T2S_MODEL", "claude-sonnet-5-5")

SYSTEM = """You are a senior analytics engineer writing SQL for a supply-chain warehouse.
Dialect: DuckDB. Return exactly one SELECT (or WITH ... SELECT) statement and nothing else: no prose, no markdown.
Rules:
- Use only the tables and columns in the schema below. Use the JOIN hints for join keys.
- ORDER_DATE is an ISO-8601 string such as 2024-11-15T08:30:00.000Z; compare it with CAST(order_date AS TIMESTAMPTZ).
- Data covers 2024. Use explicit dates instead of CURRENT_DATE.
- IS_ACTIVE is boolean. Use LOWER(col) LIKE '%x%' for fuzzy text matches.
- Add ORDER BY only when the question asks for a ranking or order; add LIMIT for "top N".
- Give aggregate columns short snake_case aliases.

Business rules from the semantic model:
{instructions}

Schema:
{schema}
"""


def build_prompt(question: str, schema_blocks: list, instructions: str = "") -> tuple:
    system = SYSTEM.format(instructions=instructions or "(none)", schema="\n\n".join(schema_blocks))
    return system, question


def generate_sql(question: str, schema_blocks: list, instructions: str = "", error: str | None = None) -> tuple:
    import anthropic  # imported lazily so retrieval/eval of golden SQL works without the SDK or a key

    system, user = build_prompt(question, schema_blocks, instructions)
    if error:
        user += f"\n\nYour previous SQL failed with: {error}\nReturn a corrected query."
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    msg = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        temperature=0,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = strip_fences("".join(b.text for b in msg.content if b.type == "text"))
    return text, msg.usage.input_tokens, msg.usage.output_tokens
