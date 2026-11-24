"""Build one retrievable document per table from the semantic model YAML and the DDL comments."""
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT / "semantic" / "supply_chain_network.yaml"
DDL_PATH = ROOT / "sql" / "1_supply_chain_ddl.sql"

TABLE_RE = re.compile(
    r"create\s+or\s+replace\s+table\s+(\w+)\s*\((.*?)\)\s*COMMENT\s*=\s*'([^']*)'", re.S | re.I
)
COLUMN_RE = re.compile(r"^\s*(\w+)\s+([A-Z]+(?:\([\d,]+\))?).*?COMMENT\s+'([^']*)'", re.I)


@dataclass
class TableDoc:
    name: str  # upper-case table name, e.g. MFG_PLANT
    description: str = ""
    columns: dict = field(default_factory=dict)  # col -> (type, comment)
    synonyms: list = field(default_factory=list)
    sample_values: dict = field(default_factory=dict)
    related: set = field(default_factory=set)
    joins: list = field(default_factory=list)  # human-readable join hints

    def text(self) -> str:
        """Text indexed by the retriever."""
        parts = [self.name.replace("_", " "), self.description, " ".join(self.synonyms)]
        for col, (_, comment) in self.columns.items():
            parts.append(f"{col.replace('_', ' ')} {comment}")
        for vals in self.sample_values.values():
            parts.append(" ".join(str(v) for v in vals))
        return " ".join(parts)

    def prompt_block(self) -> str:
        """Compact schema block sent to the LLM."""
        lines = [f"TABLE {self.name}  -- {self.description}"]
        for col, (typ, comment) in self.columns.items():
            sv = self.sample_values.get(col)
            sample = f" e.g. {', '.join(map(str, sv[:3]))}" if sv else ""
            lines.append(f"  {col} {typ}  -- {comment}{sample}")
        for j in self.joins:
            lines.append(f"  JOIN {j}")
        return "\n".join(lines)


def parse_ddl(path: Path = DDL_PATH) -> dict:
    docs = {}
    for name, body, comment in TABLE_RE.findall(path.read_text(encoding="utf-8")):
        doc = TableDoc(name=name.upper(), description=comment)
        for line in body.splitlines():
            m = COLUMN_RE.match(line)
            if m:
                doc.columns[m.group(1).upper()] = (m.group(2).upper(), m.group(3))
        docs[doc.name] = doc
    return docs


def load_semantic(path: Path = YAML_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def build_docs(yaml_path: Path = YAML_PATH, ddl_path: Path = DDL_PATH) -> dict:
    docs = parse_ddl(ddl_path)
    model = load_semantic(yaml_path)

    for t in model.get("tables", []):
        name = t.get("name", "").upper()
        doc = docs.setdefault(name, TableDoc(name=name))
        doc.description = doc.description or t.get("description", "")
        doc.synonyms += t.get("synonyms", []) or []
        for section in ("dimensions", "facts", "time_dimensions"):
            for item in t.get(section, []) or []:
                col = str(item.get("expr", item.get("name", ""))).upper()
                doc.synonyms += item.get("synonyms", []) or []
                if col not in doc.columns:
                    doc.columns[col] = (str(item.get("data_type", "")).upper(), item.get("description", ""))
                if item.get("sample_values"):
                    doc.sample_values[col] = item["sample_values"]

    for rel in model.get("relationships", []) or []:
        left, right = rel.get("left_table", "").upper(), rel.get("right_table", "").upper()
        cond = " AND ".join(
            f"{left}.{c['left_column']} = {right}.{c['right_column']}" for c in rel.get("relationship_columns", [])
        )
        for a, b in ((left, right), (right, left)):
            if a in docs:
                docs[a].related.add(b)
                docs[a].joins.append(f"{b} ON {cond}")
    csvs = {p.stem.upper() for p in (ROOT / "data").glob("*.csv")}  # only tables that exist in the warehouse
    return {k: v for k, v in docs.items() if k in csvs}


def custom_instructions(yaml_path: Path = YAML_PATH) -> str:
    block = load_semantic(yaml_path).get("module_custom_instructions", {}) or {}
    return "\n".join(str(v).strip() for v in block.values() if v)
