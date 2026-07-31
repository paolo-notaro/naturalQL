from collections.abc import Iterator

import duckdb
import pytest

from naturalql import db


@pytest.fixture
def seeded_connection() -> Iterator[duckdb.DuckDBPyConnection]:
    conn = db.connect(":memory:")
    db.init_db(conn)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def schema(seeded_connection):
    return db.allowed_identifiers(seeded_connection)
