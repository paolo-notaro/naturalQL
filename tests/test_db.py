import duckdb
import pytest

from naturalql import db


def test_initialization_is_idempotent(seeded_connection):
    before = seeded_connection.execute("SELECT COUNT(*) FROM movies").fetchone()
    db.init_db(seeded_connection)
    after = seeded_connection.execute("SELECT COUNT(*) FROM movies").fetchone()
    assert before == after == (5,)


def test_force_rebuild_restores_seed_data(seeded_connection):
    seeded_connection.execute("DELETE FROM movies")
    db.init_db(seeded_connection, force_rebuild=True)
    assert seeded_connection.execute("SELECT COUNT(*) FROM movies").fetchone() == (5,)


def test_file_database_uses_read_only_query_connection(tmp_path):
    path = str(tmp_path / "demo.duckdb")
    db.initialize_database(path)

    conn = db.connect_for_queries(path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM movies").fetchone() == (5,)
        with pytest.raises(duckdb.Error):
            conn.execute("DELETE FROM movies")
        with pytest.raises(duckdb.Error):
            conn.execute("SELECT * FROM read_csv_auto('/tmp/missing.csv')")
    finally:
        conn.close()


def test_schema_helpers_describe_seeded_database(seeded_connection):
    text = db.schema_text(seeded_connection)
    tables, columns = db.allowed_identifiers(seeded_connection)
    assert "movies(movie_id INTEGER" in text
    assert "movies" in tables
    assert "title" in columns["movies"]
