"""Application configuration loaded from environment variables."""

import os
from dataclasses import dataclass
from datetime import date

from dotenv import find_dotenv, load_dotenv

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TODAY = date(2025, 9, 10)
DEFAULT_DB_PATH = "naturalql.duckdb"
DEFAULT_RESULT_LIMIT = 50
DEFAULT_MAX_SQL_LENGTH = 20_000
DEFAULT_MAX_AST_NODES = 500


def _positive_int(name: str, default: int, *, maximum: int | None = None) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} cannot exceed {maximum}")
    return value


@dataclass(frozen=True)
class Settings:
    """Validated runtime settings for NaturalQL."""

    model: str = DEFAULT_MODEL
    today: date = DEFAULT_TODAY
    db_path: str = DEFAULT_DB_PATH
    result_limit: int = DEFAULT_RESULT_LIMIT
    max_sql_length: int = DEFAULT_MAX_SQL_LENGTH
    max_ast_nodes: int = DEFAULT_MAX_AST_NODES

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings from ``.env`` and the process environment."""
        load_dotenv(find_dotenv(), override=False)
        raw_today = os.getenv("NQL_TODAY", DEFAULT_TODAY.isoformat())
        try:
            today = date.fromisoformat(raw_today)
        except ValueError as exc:
            raise ValueError("NQL_TODAY must use YYYY-MM-DD format") from exc

        model = os.getenv("NQL_MODEL", DEFAULT_MODEL).strip()
        db_path = os.getenv("NQL_DB_PATH", DEFAULT_DB_PATH).strip()
        if not model:
            raise ValueError("NQL_MODEL cannot be empty")
        if not db_path:
            raise ValueError("NQL_DB_PATH cannot be empty")

        return cls(
            model=model,
            today=today,
            db_path=db_path,
            result_limit=_positive_int(
                "NQL_RESULT_LIMIT", DEFAULT_RESULT_LIMIT, maximum=500
            ),
            max_sql_length=_positive_int("NQL_MAX_SQL_LENGTH", DEFAULT_MAX_SQL_LENGTH),
            max_ast_nodes=_positive_int("NQL_MAX_AST_NODES", DEFAULT_MAX_AST_NODES),
        )
