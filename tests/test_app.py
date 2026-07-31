from streamlit.testing.v1 import AppTest

from naturalql import app as app_module


def test_application_starts_without_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("NQL_DB_PATH", str(tmp_path / "app.duckdb"))

    app = AppTest.from_file("src/naturalql/app.py").run(timeout=20)

    assert not app.exception
    assert app.tabs[0].label == "Query"
    assert app.tabs[1].label == "About"


def test_get_conn_recovers_when_connection_is_missing(monkeypatch, tmp_path):
    path = str(tmp_path / "recovered.duckdb")
    session_state = {"db_path": path}
    monkeypatch.setattr(app_module.st, "session_state", session_state)

    conn = app_module.get_conn(path)

    try:
        assert conn.execute("SELECT COUNT(*) FROM movies").fetchone() == (5,)
        assert session_state["conn"] is conn
    finally:
        conn.close()
