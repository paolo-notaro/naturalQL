from datetime import date

import pytest

from naturalql.config import Settings

ENV_NAMES = (
    "NQL_MODEL",
    "NQL_TODAY",
    "NQL_DB_PATH",
    "NQL_RESULT_LIMIT",
    "NQL_MAX_SQL_LENGTH",
    "NQL_MAX_AST_NODES",
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_loads_defaults():
    settings = Settings.from_env()
    assert settings.today == date(2025, 9, 10)
    assert settings.result_limit == 50


def test_loads_environment(monkeypatch):
    monkeypatch.setenv("NQL_MODEL", "test-model")
    monkeypatch.setenv("NQL_TODAY", "2026-07-31")
    monkeypatch.setenv("NQL_DB_PATH", "data/demo.duckdb")
    monkeypatch.setenv("NQL_RESULT_LIMIT", "25")
    monkeypatch.setenv("NQL_MAX_SQL_LENGTH", "1000")
    monkeypatch.setenv("NQL_MAX_AST_NODES", "100")

    settings = Settings.from_env()

    assert settings.model == "test-model"
    assert settings.today == date(2026, 7, 31)
    assert settings.db_path == "data/demo.duckdb"
    assert settings.result_limit == 25


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("NQL_TODAY", "31-07-2026", "YYYY-MM-DD"),
        ("NQL_RESULT_LIMIT", "many", "integer"),
        ("NQL_RESULT_LIMIT", "0", "greater than zero"),
        ("NQL_RESULT_LIMIT", "501", "cannot exceed"),
        ("NQL_MODEL", " ", "cannot be empty"),
        ("NQL_DB_PATH", " ", "cannot be empty"),
    ],
)
def test_rejects_invalid_configuration(monkeypatch, name, value, message):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=message):
        Settings.from_env()
