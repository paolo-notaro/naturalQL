from datetime import date
from types import SimpleNamespace

import pytest

from naturalql import llm


class FakeCompletions:
    def __init__(self, content: str):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


def fake_client(content: str):
    completions = FakeCompletions(content)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


def test_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(
        llm.LLMConfigurationError, match=".env or the process environment"
    ):
        llm._client()


def test_generate_sql_uses_configured_date_and_limit(monkeypatch):
    client, completions = fake_client("```sql\nSELECT title FROM movies\n```")
    monkeypatch.setattr(llm, "_client", lambda: client)

    result = llm.generate_sql(
        "list movies",
        "movies(movie_id INTEGER, title VARCHAR)",
        25,
        today=date(2026, 7, 31),
        model="test-model",
    )

    assert result.startswith("```sql")
    call = completions.calls[0]
    assert call["model"] == "test-model"
    assert "temperature" not in call
    assert "2026-07-31" in call["messages"][0]["content"]
    assert "LIMIT 25" in call["messages"][0]["content"]


def test_repair_sql_includes_validation_error(monkeypatch):
    client, completions = fake_client("SELECT title FROM movies LIMIT 10")
    monkeypatch.setattr(llm, "_client", lambda: client)
    result = llm.repair_sql("list movies", "unknown column", "movies(title)", 10)
    assert result.endswith("LIMIT 10")
    assert "temperature" not in completions.calls[0]
    assert "unknown column" in completions.calls[0]["messages"][1]["content"]


def test_explain_sql_uses_supplied_query(monkeypatch):
    client, completions = fake_client("Returns movie titles.")
    monkeypatch.setattr(llm, "_client", lambda: client)
    sql = "SELECT title FROM movies LIMIT 10"
    assert llm.explain_sql(sql) == "Returns movie titles."
    assert "temperature" not in completions.calls[0]
    assert sql in completions.calls[0]["messages"][1]["content"]
