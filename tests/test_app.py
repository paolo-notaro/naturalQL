from streamlit.testing.v1 import AppTest


def test_application_starts_without_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("NQL_DB_PATH", str(tmp_path / "app.duckdb"))

    app = AppTest.from_file("src/naturalql/app.py").run(timeout=20)

    assert not app.exception
    assert app.tabs[0].label == "Query"
    assert app.tabs[1].label == "About"
