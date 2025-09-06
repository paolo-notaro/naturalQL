"""src/naturalql/config.py: Configuration settings for NaturalQL."""

from dataclasses import dataclass
import os
from dotenv import load_dotenv, find_dotenv

# Load env vars from .env if present
load_dotenv(find_dotenv())


DEFAULT_MODEL = os.getenv("NQL_MODEL", "gpt-4o-mini")
TODAY = os.getenv("NQL_TODAY", "2025-09-10")  # deterministic demo date
DB_PATH = os.getenv("NQL_DB_PATH", "naturalql.duckdb")
RESULT_LIMIT_DEFAULT = int(os.getenv("NQL_RESULT_LIMIT", "50"))
# OpenAI SDK reads OPENAI_API_KEY from env automatically


@dataclass
class Settings:
    """Configuration settings for NaturalQL."""

    model: str = DEFAULT_MODEL
    today: str = TODAY
    db_path: str = DB_PATH
    result_limit: int = RESULT_LIMIT_DEFAULT
