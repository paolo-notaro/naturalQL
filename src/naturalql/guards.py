"""src/naturalql/guards.py: SQL sanitization and validation."""

import re
from typing import Dict, Set
from sqlglot import parse_one, exp


DANGEROUS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "attach",
    "copy",
    "pragma",
    "replace",
    "vacuum",
    "grant",
}

RESERVED_HINTS = {
    ("festivals", "rank"): "Use festivals.festival_rank instead of 'rank'"
}


def sanitize_sql(sql: str, result_limit: int) -> str:
    s = sql.strip()
    m = re.search(r"```(?:sql)?\s*(.*?)\s*```", s, re.S | re.I)
    if m:
        s = m.group(1).strip()
    s = s.replace(";", " ")
    if re.search(r"\b(" + "|".join(k.upper() for k in DANGEROUS) + r")\b", s, re.I):
        raise ValueError("Only SELECT queries are allowed.")
    if not re.search(r"^\s*SELECT\b", s, re.I):
        raise ValueError("Query must start with SELECT.")
    if not re.search(r"\bLIMIT\s+\d+\b", s, re.I):
        s += f" LIMIT {int(result_limit)}"
    return s.strip()


def validate_with_sqlglot(sql: str, tables_ok: Set[str], cols_ok: Dict[str, Set[str]]):
    try:
        tree = parse_one(sql, read="duckdb")
    except Exception as e:
        raise ValueError(f"SQL parse error: {e}")

    if not isinstance(tree, (exp.Select, exp.Union)):
        raise ValueError("Only SELECT/UNION SELECT queries are permitted.")

    # Alias map
    alias_map = {}
    for tbl in tree.find_all(exp.Table):
        base = tbl.name
        if base not in tables_ok:
            raise ValueError(f"Unknown table referenced: {base}")
        alias_expr = tbl.args.get("alias")
        if alias_expr and getattr(alias_expr, "name", None):
            alias_map[alias_expr.name] = base

    # Accept table-qualified stars like m.* (validate the table/alias exists)
    for star in tree.find_all(exp.Star):
        t = star.args.get("table")
        if t:
            real = alias_map.get(t, t)
            if real not in tables_ok:
                raise ValueError(f"Unknown table for star: {t}")

    # Validate normal columns (skip stars)
    for col in tree.find_all(exp.Column):
        # Some sqlglot versions represent m.* as Column(name='*', table='m')
        if col.name == "*":
            # just validate the table/alias if present
            if col.table:
                real = alias_map.get(col.table, col.table)
                if real not in tables_ok:
                    raise ValueError(f"Unknown table for star: {col.table}")
            continue

        if col.table:
            ref = col.table
            real = alias_map.get(ref, ref)
            if real not in cols_ok:
                raise ValueError(f"Unknown table in column reference: {ref}")
            if col.name not in cols_ok[real]:
                raise ValueError(
                    f"Unknown column {ref}.{col.name} (resolved to {real})"
                )
