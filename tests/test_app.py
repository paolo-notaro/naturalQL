from streamlit.testing.v1 import AppTest

from naturalql import app as app_module


def test_application_starts_without_api_key(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("NQL_DB_PATH", str(tmp_path / "app.duckdb"))

    app = AppTest.from_file("src/naturalql/app.py").run(timeout=20)

    assert not app.exception
    assert app.tabs[0].label == "Query"
    assert app.tabs[1].label == "About"


def test_get_conn_recovers_when_connection_is_missing(monkeypatch, tmp_path):
    path = str(tmp_path / "recovered.duckdb")
    app_module.db.initialize_database(path)
    first_connection = app_module.db.connect_for_queries(path)
    session_state = {"db_path": path}
    monkeypatch.setattr(app_module.st, "session_state", session_state)

    try:
        recovered = app_module.get_conn(path)
        assert recovered.execute("SELECT COUNT(*) FROM movies").fetchone() == (5,)
        assert session_state["conn"] is recovered
    finally:
        first_connection.close()
        session_state["conn"].close()


def test_failed_generation_clears_previous_sql(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("NQL_DB_PATH", str(tmp_path / "failure.duckdb"))
    app = AppTest.from_file("src/naturalql/app.py").run(timeout=20)
    app.session_state["last_sql"] = "SELECT title FROM movies LIMIT 1"

    app.text_area[0].set_value("List every movie")
    app.button[0].click().run(timeout=20)

    assert "last_sql" not in app.session_state
    assert "OPENAI_API_KEY is not set" in app.error[0].value
