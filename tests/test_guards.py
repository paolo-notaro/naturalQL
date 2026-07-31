import pytest
from sqlglot import exp
from sqlglot.errors import ParseError

from naturalql.guards import QueryPolicy, QueryRejected, prepare_sql


@pytest.fixture
def policy() -> QueryPolicy:
    return QueryPolicy(result_limit=50, max_sql_length=2_000, max_ast_nodes=200)


def prepare(raw_sql: str, schema, policy: QueryPolicy) -> str:
    tables, columns = schema
    return prepare_sql(raw_sql, tables, columns, policy)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO movies VALUES (1)",
        "UPDATE movies SET title = 'x'",
        "DELETE FROM movies",
        "DROP TABLE movies",
        "CREATE TABLE example (id INTEGER)",
        "PRAGMA version",
        "ATTACH 'other.duckdb' AS other",
        "COPY movies TO 'movies.csv'",
    ],
)
def test_rejects_non_query_statements(sql, schema, policy):
    with pytest.raises(QueryRejected):
        prepare(sql, schema, policy)


def test_rejects_multiple_statements(schema, policy):
    with pytest.raises(QueryRejected, match="Exactly one"):
        prepare("SELECT title FROM movies; SELECT name FROM people", schema, policy)


def test_rejects_queries_without_application_data(schema, policy):
    with pytest.raises(QueryRejected, match="at least one application table"):
        prepare("SELECT 1492 AS year", schema, policy)


def test_unexpected_parser_failure_is_rejected(monkeypatch, schema, policy):
    def fail_to_parse(*args, **kwargs):
        raise RuntimeError("unexpected parser failure")

    monkeypatch.setattr("naturalql.guards.parse", fail_to_parse)

    with pytest.raises(QueryRejected, match="parsing failed unexpectedly"):
        prepare("SELECT title FROM movies", schema, policy)


def test_parser_error_is_rejected(monkeypatch, schema, policy):
    def fail_to_parse(*args, **kwargs):
        raise ParseError("invalid generated SQL")

    monkeypatch.setattr("naturalql.guards.parse", fail_to_parse)

    with pytest.raises(QueryRejected, match="SQL parse error"):
        prepare("SELECT title FROM movies", schema, policy)


def test_allows_dangerous_words_inside_literals(schema, policy):
    sql = prepare("SELECT 'drop table' AS note FROM movies LIMIT 1", schema, policy)
    assert "drop table" in sql
    assert "LIMIT 1" in sql


def test_extracts_a_single_markdown_fence(schema, policy):
    sql = prepare("```sql\nSELECT title FROM movies\n```", schema, policy)
    assert "movies.title" in sql


def test_rejects_an_empty_fenced_block(schema, policy):
    with pytest.raises(QueryRejected, match="empty query"):
        prepare("Response:\n```sql\n\n```", schema, policy)


def test_extracts_one_fence_with_surrounding_text(schema, policy):
    sql = prepare(
        "Here is the query:\n```sql\nSELECT title FROM movies\n```\nDone.",
        schema,
        policy,
    )
    assert "movies.title" in sql


def test_sql_length_applies_after_fence_extraction(schema):
    policy = QueryPolicy(result_limit=10, max_sql_length=40, max_ast_nodes=100)
    response = f"{'Background. ' * 20}\n```sql\nSELECT title FROM movies\n```"

    sql = prepare(response, schema, policy)

    assert "movies.title" in sql


def test_rejects_multiple_fenced_blocks(schema, policy):
    response = (
        "```sql\nSELECT title FROM movies\n```\n```sql\nSELECT name FROM people\n```"
    )
    with pytest.raises(QueryRejected, match="multiple fenced"):
        prepare(response, schema, policy)


@pytest.mark.parametrize(
    ("sql", "message"),
    [
        ("", "empty"),
        ("SELECT title FROM missing", "Unknown table"),
        ("SELECT missing FROM movies", "Column validation"),
        ("SELECT movie_id FROM movies JOIN screenings ON TRUE", "Column validation"),
        ("SELECT * FROM read_csv_auto('/tmp/data.csv')", "External"),
    ],
)
def test_rejects_invalid_or_external_queries(sql, message, schema, policy):
    with pytest.raises(QueryRejected, match=message):
        prepare(sql, schema, policy)


def test_resolves_aliases_and_qualified_columns(schema, policy):
    sql = prepare("SELECT m.title FROM movies AS m", schema, policy)
    assert "m.title" in sql


def test_supports_ctes_and_unions(schema, policy):
    sql = prepare(
        """
        WITH recent AS (SELECT movie_id, title FROM movies)
        SELECT title FROM recent
        UNION ALL
        SELECT title FROM movies
        """,
        schema,
        policy,
    )
    assert "WITH recent AS" in sql
    assert "UNION ALL" in sql
    assert sql.endswith("LIMIT 50")


def test_rejects_ctes_that_shadow_application_tables(schema, policy):
    with pytest.raises(QueryRejected, match="cannot shadow application tables: movies"):
        prepare(
            "WITH movies AS (SELECT 1 AS title) SELECT title FROM movies",
            schema,
            policy,
        )


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("SELECT title FROM movies", "LIMIT 50"),
        ("SELECT title FROM movies LIMIT 10", "LIMIT 10"),
        ("SELECT title FROM movies LIMIT 500", "LIMIT 50"),
        ("SELECT title FROM movies LIMIT 5 + 5", "LIMIT 50"),
        ("SELECT title FROM movies FETCH FIRST 10 ROWS ONLY", "LIMIT 10"),
        ("SELECT title FROM movies FETCH FIRST 500 ROWS ONLY", "LIMIT 50"),
    ],
)
def test_applies_result_limit(query, expected, schema, policy):
    assert prepare(query, schema, policy).endswith(expected)


def test_rejects_oversized_sql(schema):
    policy = QueryPolicy(result_limit=10, max_sql_length=10, max_ast_nodes=100)
    with pytest.raises(QueryRejected, match="too long"):
        prepare("SELECT title FROM movies", schema, policy)


def test_rejects_excessive_ast_complexity(schema):
    policy = QueryPolicy(result_limit=10, max_sql_length=2_000, max_ast_nodes=5)
    with pytest.raises(QueryRejected, match="too complex"):
        prepare("SELECT title FROM movies", schema, policy)


def test_rejects_prohibited_expression_nested_in_query(monkeypatch, schema, policy):
    monkeypatch.setattr(
        "naturalql.guards._prohibited_expression_types", lambda: (exp.Select,)
    )
    with pytest.raises(QueryRejected, match="prohibited operation"):
        prepare("SELECT title FROM movies", schema, policy)


def test_policy_values_must_be_positive():
    with pytest.raises(ValueError):
        QueryPolicy(result_limit=0)
