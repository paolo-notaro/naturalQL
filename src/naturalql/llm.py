"""OpenAI-backed SQL generation and explanation."""

import os
from datetime import date

from openai import OpenAI

from naturalql.config import DEFAULT_MODEL

PROMPT_HEADER = (
    "You convert natural language to DuckDB SQL. HARD REQUIREMENTS:\n"
    "1) Output ONLY a single SELECT statement (no DDL/DML). No comments.\n"
    "2) Use ONLY provided tables/columns. Explicit JOINs with ON.\n"
    "3) Assume TODAY is {today}. Resolve relative dates against {year}.\n"
    "   Northern Hemisphere seasons: summer=Jun1-Aug31, spring=Mar1-May31, autumn=Sep1-Nov30, winter=Dec1-Feb28/29.\n"
    "   When filtering screenings by a time window, use OVERLAP logic: (screenings.start_date <= <window_end>) AND (screenings.end_date >= <window_start>).\n"
    "4) Always include 'LIMIT {result_limit}' unless a lower LIMIT is specified.\n"
    "5) Prefer ANSI SQL compatible with DuckDB. Use table-qualified columns when ambiguous.\n"
    "6) In aggregate queries, include ALL non-aggregated selected columns in GROUP BY.\n"
    "7) Use NOT EXISTS for anti-conditions (e.g., 'no X', 'never').\n"
    "8) 'New releases' must filter with screenings.is_new_release = TRUE.\n"
    "9) The festival ranking column is festivals.festival_rank.\n"
    "10) When filtering by cinema name, join to cinemas and filter by cinemas.name.\n"
    "11) Prefer explicit column names; avoid SELECT * unless the user explicitly asks for all columns.\n"
    "12) Interpret 'cast never acted in an award-winning movie' as: none of the movie_cast persons for the target movie appear in movie_cast for any movie where movie_awards.is_winner = TRUE. Use NOT EXISTS with a subquery over cast persons.\n"
)


class LLMConfigurationError(RuntimeError):
    """Raised when required LLM configuration is unavailable."""


def _client() -> OpenAI:
    """Initialize an OpenAI client after checking local configuration."""
    if not os.getenv("OPENAI_API_KEY"):
        raise LLMConfigurationError(
            "OPENAI_API_KEY is not set. Add it to .env or the process environment "
            "before generating SQL."
        )
    return OpenAI()


def generate_sql(
    nl_query: str,
    schema_text: str,
    result_limit: int,
    *,
    today: date,
    model: str | None = None,
) -> str:
    """Generate a SQL query from a natural language query using an LLM."""
    model = model or DEFAULT_MODEL
    client = _client()
    sys = PROMPT_HEADER.format(
        result_limit=result_limit, today=today.isoformat(), year=today.year
    )
    user = (
        f"SCHEMA:\n{schema_text}\n\n"
        "TASK: Convert the user question to a single safe SELECT query. Return ONLY the SQL inside triple backticks.\n\n"
        f"USER QUESTION: {nl_query}\n"
    )
    r = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
    )
    return r.choices[0].message.content


def repair_sql(
    nl_query: str,
    error_msg: str,
    schema_text: str,
    result_limit: int,
    model: str | None = None,
) -> str:
    model = model or DEFAULT_MODEL
    client = _client()
    sys = "You repair DuckDB SQL under strict constraints (SELECT-only, no DDL/DML)."
    user = (
        f"SCHEMA:\n{schema_text}\n\n"
        f"The previous attempt failed with this error:\n{error_msg}\n\n"
        f"USER QUESTION: {nl_query}\n\n"
        f"Please return ONLY a corrected SELECT query with LIMIT {result_limit} inside triple backticks."
    )
    r = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
    )
    return r.choices[0].message.content


def explain_sql(sql_text: str, model: str | None = None) -> str:
    model = model or DEFAULT_MODEL
    client = _client()
    prompt = f"Explain, in 2–3 sentences, what this SQL does at a high level (no step-by-step reasoning):\n\n{sql_text}"
    r = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful data analyst."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return r.choices[0].message.content.strip()
