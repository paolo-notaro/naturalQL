"""Fail-closed validation for model-generated DuckDB queries."""

import re
from collections.abc import Mapping, Set
from dataclasses import dataclass

from sqlglot import exp, parse
from sqlglot.errors import ParseError
from sqlglot.optimizer.qualify import qualify

FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class QueryRejected(ValueError):
    """Raised when generated SQL violates the query policy."""


@dataclass(frozen=True)
class QueryPolicy:
    """Resource and result bounds applied before query execution."""

    result_limit: int
    max_sql_length: int = 20_000
    max_ast_nodes: int = 500

    def __post_init__(self) -> None:
        if min(self.result_limit, self.max_sql_length, self.max_ast_nodes) <= 0:
            raise ValueError("Query policy values must be greater than zero")


def _extract_sql(raw_sql: str, max_length: int) -> str:
    sql = raw_sql.strip()
    if not sql:
        raise QueryRejected("The model returned an empty query")
    if len(sql) > max_length:
        raise QueryRejected("The generated query is too long")

    fenced_blocks = FENCE_RE.findall(sql)
    if len(fenced_blocks) > 1:
        raise QueryRejected("The model returned multiple fenced SQL blocks")
    if fenced_blocks:
        sql = fenced_blocks[0].strip()
        if not sql:
            raise QueryRejected("The model returned an empty query")
    return sql


def _prohibited_expression_types() -> tuple[type[exp.Expression], ...]:
    names = (
        "Alter",
        "Attach",
        "Command",
        "Copy",
        "Create",
        "Delete",
        "Detach",
        "Drop",
        "Grant",
        "Insert",
        "LoadData",
        "Merge",
        "Pragma",
        "Revoke",
        "Set",
        "Transaction",
        "TruncateTable",
        "Update",
        "Use",
    )
    return tuple(
        expression_type
        for name in names
        if isinstance((expression_type := getattr(exp, name, None)), type)
    )


def _validate_sources(
    expression: exp.Expression,
    tables: Set[str],
) -> None:
    cte_names = {cte.alias_or_name.lower() for cte in expression.find_all(exp.CTE)}
    allowed_tables = {table.lower() for table in tables}
    physical_sources = 0

    for table in expression.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            raise QueryRejected(
                "External and table-producing functions are not allowed"
            )
        name = table.name.lower()
        if name not in allowed_tables and name not in cte_names:
            raise QueryRejected(f"Unknown table referenced: {table.name}")
        if name in allowed_tables:
            physical_sources += 1

    if physical_sources == 0:
        raise QueryRejected("The query must reference at least one application table")


def _apply_limit(expression: exp.Query, result_limit: int) -> None:
    current = expression.args.get("limit")
    if current is None:
        expression.set("limit", exp.Limit(expression=exp.Literal.number(result_limit)))
        return

    value = current.expression
    if not isinstance(value, exp.Literal) or not value.is_int:
        current.set("expression", exp.Literal.number(result_limit))
        return

    if int(value.this) > result_limit:
        current.set("expression", exp.Literal.number(result_limit))


def prepare_sql(
    raw_sql: str,
    tables: Set[str],
    columns: Mapping[str, Set[str]],
    policy: QueryPolicy,
) -> str:
    """Validate and normalize one read-only query for execution.

    The LLM prompt is not trusted. This function is the enforcement boundary for
    statement type, schema access, query complexity, and result size.
    """
    sql = _extract_sql(raw_sql, policy.max_sql_length)
    try:
        statements = [statement for statement in parse(sql, read="duckdb") if statement]
    except ParseError as exc:
        raise QueryRejected(f"SQL parse error: {exc}") from exc
    except Exception as exc:
        raise QueryRejected("SQL parsing failed unexpectedly") from exc

    if len(statements) != 1:
        raise QueryRejected("Exactly one SQL statement is required")

    expression = statements[0]
    if not isinstance(expression, exp.Query):
        raise QueryRejected("Only SELECT queries are allowed")
    if any(
        expression.find(expression_type)
        for expression_type in _prohibited_expression_types()
    ):
        raise QueryRejected("The query contains a prohibited operation")
    if sum(1 for _ in expression.walk()) > policy.max_ast_nodes:
        raise QueryRejected("The generated query is too complex")

    _validate_sources(expression, tables)
    schema = {
        table: {column: "UNKNOWN" for column in table_columns}
        for table, table_columns in columns.items()
    }
    try:
        expression = qualify(
            expression,
            dialect="duckdb",
            schema=schema,
            expand_stars=False,
            quote_identifiers=False,
            validate_qualify_columns=True,
        )
    except Exception as exc:
        raise QueryRejected(f"Column validation failed: {exc}") from exc

    _apply_limit(expression, policy.result_limit)
    return expression.sql(dialect="duckdb")
