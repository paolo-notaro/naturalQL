"""
app.py - Natural Language to Guardrailed SQL demo with Streamlit & DuckDB.

Authors: Paolo Notaro (@paolo-notaro).
Date: 2024-09-10
"""

import re
from datetime import date
import streamlit as st
import duckdb
from sqlglot import parse_one, exp
from datetime import date

# --- OpenAI client (SDK v1) ---
try:
    from openai import OpenAI

    oai = OpenAI()
except Exception as e:
    oai = None

APP_TITLE = "🎬 CineQL — Natural Language to SQL (Guardrailed)"
DB_PATH = "cineql.duckdb"
DEFAULT_LIMIT = 50
MODEL = "gpt-4o-mini"  # fast & cheap; swap to gpt-4o if desired

# ------------------------------
#   DB bootstrap & sample data
# ------------------------------
DDL = """
-- Drop & create deterministic demo schema
DROP TABLE IF EXISTS cinemas;
DROP TABLE IF EXISTS movies;
DROP TABLE IF EXISTS people;
DROP TABLE IF EXISTS movie_directors;
DROP TABLE IF EXISTS movie_cast;
DROP TABLE IF EXISTS genres;
DROP TABLE IF EXISTS movie_genres;
DROP TABLE IF EXISTS festivals;
DROP TABLE IF EXISTS festival_entries;
DROP TABLE IF EXISTS awards;
DROP TABLE IF EXISTS movie_awards;
DROP TABLE IF EXISTS screenings;

CREATE TABLE cinemas (
  cinema_id INTEGER,
  name VARCHAR,
  city VARCHAR,
  PRIMARY KEY (cinema_id)
);

CREATE TABLE movies (
  movie_id INTEGER,
  title VARCHAR,
  release_date DATE,
  runtime_min INTEGER,
  country VARCHAR,
  language VARCHAR,
  rating_cert VARCHAR,
  box_office_musd DOUBLE,
  PRIMARY KEY (movie_id)
);

CREATE TABLE people (
  person_id INTEGER,
  name VARCHAR,
  kind VARCHAR, -- 'director' or 'actor'
  PRIMARY KEY (person_id)
);

CREATE TABLE movie_directors (
  movie_id INTEGER,
  person_id INTEGER,
  is_debut BOOLEAN DEFAULT FALSE
);

CREATE TABLE movie_cast (
  movie_id INTEGER,
  person_id INTEGER,
  role_name VARCHAR
);

CREATE TABLE genres (
  genre_id INTEGER,
  name VARCHAR,
  PRIMARY KEY (genre_id)
);

CREATE TABLE movie_genres (
  movie_id INTEGER,
  genre_id INTEGER
);

CREATE TABLE festivals (
  festival_id INTEGER,
  name VARCHAR,
  year INTEGER,
  rank VARCHAR -- 'S','A','B','C' (S highest)
);

CREATE TABLE festival_entries (
  festival_id INTEGER,
  movie_id INTEGER,
  competition VARCHAR,
  award_won BOOLEAN DEFAULT FALSE
);

CREATE TABLE awards (
  award_id INTEGER,
  name VARCHAR,
  awarding_body VARCHAR,
  PRIMARY KEY (award_id)
);

CREATE TABLE movie_awards (
  movie_id INTEGER,
  award_id INTEGER,
  year INTEGER,
  is_winner BOOLEAN
);

CREATE TABLE screenings (
  cinema_id INTEGER,
  movie_id INTEGER,
  start_date DATE,
  end_date DATE,
  screen_format VARCHAR, -- '2D','3D','IMAX'
  is_new_release BOOLEAN
);
"""

SEED = {
    "cinemas": [
        (1, "Cinema Luna", "Milan"),
        (2, "Cinema Aurora", "Rome"),
        (3, "Cinema Odeon", "Turin"),
    ],
    "genres": [
        (1, "Sci-Fi"),
        (2, "Drama"),
        (3, "Thriller"),
        (4, "Comedy"),
        (5, "Romance"),
    ],
    "people": [
        (1, "Alice Verdi", "director"),
        (2, "Bruno Neri", "director"),
        (3, "Carla Russo", "director"),
        (4, "Dario Bianchi", "director"),
        (10, "Diego Conti", "actor"),
        (11, "Eva Moretti", "actor"),
        (12, "Gian Luca", "actor"),
        (13, "Hana Ito", "actor"),
    ],
    "movies": [
        (100, "Neon Dreams", date(2025, 6, 21), 118, "Italy", "IT/EN", "PG-13", 5.0),
        (101, "Summer Tides", date(2025, 7, 5), 106, "Italy", "IT", "PG", 7.5),
        (102, "City Shadows", date(2024, 11, 10), 122, "Italy", "IT", "R", 18.3),
        (103, "Comic Relief", date(2025, 8, 1), 97, "Italy", "IT", "PG", 3.2),
        (104, "Parallel Lines", date(2025, 6, 15), 110, "Japan", "JA", "PG-13", 21.7),
    ],
    "movie_directors": [
        (100, 1, True),  # Neon Dreams — Alice Verdi (debut)
        (101, 2, False),  # Summer Tides — Bruno Neri
        (102, 3, False),  # City Shadows — Carla Russo
        (103, 2, False),  # Comic Relief — Bruno Neri
        (104, 4, True),  # Parallel Lines — Dario Bianchi (debut)
    ],
    "movie_cast": [
        (100, 10, "Lead"),
        (100, 11, "Lead"),  # Neon Dreams: Diego, Eva
        (101, 11, "Lead"),  # Summer Tides: Eva
        (102, 12, "Lead"),  # City Shadows: Gian
        (103, 10, "Cameo"),  # Comic Relief: Diego
        (104, 13, "Lead"),  # Parallel Lines: Hana Ito
    ],
    "movie_genres": [
        (100, 1),  # Neon Dreams -> Sci-Fi
        (101, 2),  # Summer Tides -> Drama
        (102, 3),  # City Shadows -> Thriller
        (103, 4),  # Comic Relief -> Comedy
        (104, 1),  # Parallel Lines -> Sci-Fi
    ],
    "festivals": [
        (200, "EuroFilm Fest", 2025, "A"),
        (201, "Indie Nights", 2025, "B"),
        (202, "MicroFest", 2025, "C"),
    ],
    "festival_entries": [
        (
            200,
            104,
            "Main Competition",
            False,
        ),  # Parallel Lines at rank A (disqualifies)
        (201, 101, "Panorama", False),  # Summer Tides at rank B (OK)
        (202, 103, "Comedy Block", False),  # Comic Relief at rank C (OK)
    ],
    "awards": [
        (300, "Best Picture", "International Film Awards"),
        (301, "Best Actor", "International Film Awards"),
    ],
    "movie_awards": [
        (102, 300, 2024, True),  # City Shadows won Best Picture
        (102, 301, 2024, True),  # ...and Best Actor
    ],
    "screenings": [
        # Neon Dreams at Cinema Luna (summer new release)
        (1, 100, date(2025, 6, 21), date(2025, 7, 31), "2D", True),
        # Parallel Lines also at Luna (but festival rank A -> should be filtered in complex query)
        (1, 104, date(2025, 6, 20), date(2025, 7, 15), "IMAX", True),
        # Comic Relief at Luna (Comedy)
        (1, 103, date(2025, 8, 5), date(2025, 9, 15), "2D", True),
        # Summer Tides at Aurora
        (2, 101, date(2025, 7, 10), date(2025, 8, 20), "2D", True),
        # City Shadows older screening at Odeon
        (3, 102, date(2024, 12, 1), date(2025, 1, 15), "2D", False),
    ],
}


def init_db(conn: duckdb.DuckDBPyConnection, force_rebuild=False):
    tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    if force_rebuild or not tables:
        conn.execute(DDL)
        # Insert seeds
        conn.executemany("INSERT INTO cinemas VALUES (?, ?, ?)", SEED["cinemas"])
        conn.executemany("INSERT INTO genres VALUES (?, ?)", SEED["genres"])
        conn.executemany("INSERT INTO people VALUES (?, ?, ?)", SEED["people"])
        conn.executemany(
            "INSERT INTO movies VALUES (?, ?, ?, ?, ?, ?, ?, ?)", SEED["movies"]
        )
        conn.executemany(
            "INSERT INTO movie_directors VALUES (?, ?, ?)", SEED["movie_directors"]
        )
        conn.executemany("INSERT INTO movie_cast VALUES (?, ?, ?)", SEED["movie_cast"])
        conn.executemany("INSERT INTO movie_genres VALUES (?, ?)", SEED["movie_genres"])
        conn.executemany("INSERT INTO festivals VALUES (?, ?, ?, ?)", SEED["festivals"])
        conn.executemany(
            "INSERT INTO festival_entries VALUES (?, ?, ?, ?)", SEED["festival_entries"]
        )
        conn.executemany("INSERT INTO awards VALUES (?, ?, ?)", SEED["awards"])
        conn.executemany(
            "INSERT INTO movie_awards VALUES (?, ?, ?, ?)", SEED["movie_awards"]
        )
        conn.executemany(
            "INSERT INTO screenings VALUES (?, ?, ?, ?, ?, ?)", SEED["screenings"]
        )


def get_schema_text(conn):
    # Provide concise, model-friendly schema description
    schema = []
    for t in conn.execute("SHOW TABLES").df()["name"].tolist():
        cols = (
            conn.execute(f"DESCRIBE {t}")
            .df()[["column_name", "column_type"]]
            .values.tolist()
        )
        cols_str = ", ".join([f"{c} {ct}" for c, ct in cols])
        schema.append(f"{t}({cols_str})")
    return "\n".join(schema)


def allowed_identifiers(conn):
    # Return sets of valid tables and columns for guardrail validation
    tables = conn.execute("SHOW TABLES").df()["name"].tolist()
    cols = {}
    for t in tables:
        cdf = conn.execute(f"DESCRIBE {t}").df()
        cols[t] = set(cdf["column_name"].tolist())
    return set(tables), cols


# ------------------------------
#     Guardrails & helpers
# ------------------------------
DANGEROUS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "attach",
    "copy",
    "pragma",
    "replace",
    "vacuum",
    "grant",
}


def normalize_time_phrases(nl: str) -> str:
    y = date.today().year  # 2025 in demo
    repl = {
        r"\bthis summer\b": f"between {y}-06-01 and {y}-08-31",
        r"\bthis july\b": f"between {y}-07-01 and {y}-07-31",
        # add more if you like
    }
    s = nl
    for pat, val in repl.items():
        s = re.sub(pat, val, s, flags=re.I)
    return s


def sanitize_sql(sql: str, result_limit: int):
    # strip code fences, semicolons, enforce select-only, add LIMIT
    s = sql.strip()
    m = re.search(r"```(?:sql)?\s*(.*?)\s*```", s, re.S | re.I)
    if m:
        s = m.group(1).strip()
    s = s.replace(";", " ")
    if re.search(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|COPY|PRAGMA|REPLACE|VACUUM|GRANT)\b",
        s,
        re.I,
    ):
        raise ValueError("Only SELECT queries are allowed.")
    if not re.search(r"^\s*SELECT\b", s, re.I):
        raise ValueError("Query must start with SELECT.")
    # ensure LIMIT present
    if not re.search(r"\bLIMIT\s+\d+\b", s, re.I):
        s += f" LIMIT {int(result_limit)}"
    return s.strip()


def validate_with_sqlglot(sql: str, tables_ok: set, cols_ok: dict):
    try:
        tree = parse_one(sql, read="duckdb")
    except Exception as e:
        raise ValueError(f"SQL parse error: {e}")

    if not isinstance(tree, (exp.Select, exp.Union)):
        raise ValueError("Only SELECT/UNION SELECT queries are permitted.")

    # Build alias -> base table map and validate base table names
    alias_map = {}
    for tbl in tree.find_all(exp.Table):
        base = tbl.name  # the real table name
        if base not in tables_ok:
            raise ValueError(f"Unknown table referenced: {base}")
        alias_expr = tbl.args.get("alias")
        if alias_expr and getattr(alias_expr, "name", None):
            alias_map[alias_expr.name] = base

    # Validate column references (resolve aliases to base tables)
    for col in tree.find_all(exp.Column):
        if col.table:
            ref = col.table  # could be alias or real table
            real = alias_map.get(ref, ref)
            if real not in cols_ok:
                raise ValueError(f"Unknown table in column reference: {ref}")
            if col.name not in cols_ok[real]:
                raise ValueError(
                    f"Unknown column {ref}.{col.name} (resolved to {real})"
                )


def explain_sql(sql_text: str):
    if not oai:
        return "OpenAI not configured."
    prompt = f"Explain, in 2-3 sentences, what this SQL does at a high level (no step-by-step reasoning):\n\n{sql_text}"
    r = oai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a helpful data analyst."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return r.choices[0].message.content.strip()


def generate_sql(nl_query: str, schema_text: str, result_limit: int):
    if not oai:
        raise RuntimeError("OpenAI client not configured (missing OPENAI_API_KEY).")

    # Prompt: schema + strict constraints
    sys = (
        "You convert natural language to DuckDB SQL. HARD REQUIREMENTS:\n"
        "1) Output ONLY a single SELECT statement (no DDL/DML). No comments.\n"
        "2) Use ONLY provided tables/columns. Explicit JOINs with ON.\n"
        "3) Assume TODAY is 2025-09-10. Resolve relative dates against 2025.\n"
        "   Northern Hemisphere seasons: summer=Jun1-Aug31, spring=Mar1-May31, autumn=Sep1-Nov30, winter=Dec1-Feb28/29.\n"
        "   When filtering screenings by a time window, use OVERLAP logic:\n"
        "   (screenings.start_date <= <window_end>) AND (screenings.end_date >= <window_start>).\n"
        "4) Always include 'LIMIT {result_limit}' unless a lower LIMIT is specified.\n"
        "5) Prefer ANSI SQL compatible with DuckDB. Use table-qualified columns when ambiguous.\n"
        "6) In aggregate queries, include ALL non-aggregated selected columns in GROUP BY (SQL-92).\n"
        "7) Use NOT EXISTS for 'no X', 'none of', or anti-conditions to avoid false positives.\n"
        "8) 'New releases' must filter with screenings.is_new_release = TRUE.\n"
        "9) The festival ranking column is festivals.festival_rank (not 'rank').\n"
        "10) When filtering by cinema name, join to cinemas and filter by cinemas.name (avoid subqueries).\n"
    )
    user = (
        f"SCHEMA:\n{schema_text}\n\n"
        "TASK: Convert the user question to a single safe SELECT query. "
        "Return ONLY the SQL inside triple backticks.\n\n"
        f"USER QUESTION: {nl_query}\n"
    )
    r = oai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
    )
    sql = r.choices[0].message.content
    return sql


def repair_sql(original_nl: str, error_msg: str, schema_text: str, result_limit: int):
    # Ask model to fix the SQL, given the error
    sys = "You repair DuckDB SQL under strict constraints (SELECT-only, no DDL/DML)."
    user = (
        f"SCHEMA:\n{schema_text}\n\n"
        f"The previous attempt failed with this error:\n{error_msg}\n\n"
        f"USER QUESTION: {original_nl}\n\n"
        f"Please return ONLY a corrected SELECT query with LIMIT {result_limit} inside triple backticks."
    )
    r = oai.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
    )
    return r.choices[0].message.content


# ------------------------------
#              UI
# ------------------------------
st.set_page_config(
    page_title="NaturalQL - Natural Language to Guardrailed SQL",
    page_icon="🎬",
    layout="centered",
)


def hero():
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:12px;">
          <div style="font-size:42px;">🎬</div>
          <div>
            <div style="font-size:24px;font-weight:700;letter-spacing:.3px">NaturalQL</div>
            <div style="opacity:.7">Natural Language → Guardrailed SQL on a mini cinema dataset</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# DB connection in session
if "conn" not in st.session_state:
    st.session_state.conn = duckdb.connect(DB_PATH)
    init_db(st.session_state.conn, force_rebuild=True)

tabs = st.tabs(["Query", "About"])

with tabs[0]:
    hero()
    st.write("")
    colA, colB = st.columns([3, 1])
    with colB:
        limit = st.number_input("Result limit", 10, 500, value=DEFAULT_LIMIT, step=10)
    with colA:
        nl = st.text_area(
            "Ask a question about movies, screenings, festivals, directors, cast, etc.",
            height=110,
            placeholder="e.g., Show all new Sci-Fi movies screening at Cinema Luna this summer from debut directors "
            "who never participated in festivals ranked A or S, and whose cast never acted in an award-winning movie.",
        )

    examples = [
        "Show all new Sci-Fi movies screening at Cinema Luna this summer from debut directors who never participated in festivals ranked A or S, and whose cast never acted in an award-winning movie.",
        "For each cinema, count how many new releases were screening in August 2025.",
        "List movies released in 2025 with their directors and primary genre.",
        "Find actors who worked with more than one director.",
        "Which movies screening at Cinema Luna in July 2025 have no festival participation?",
    ]
    st.caption("Examples:")
    st.write(" · " + "\n · ".join(examples))

    show_sql = st.checkbox("Show generated SQL")
    btns = st.columns([1, 1, 1, 2])
    with btns[0]:
        go = st.button("Generate & Run", type="primary", use_container_width=True)
    with btns[1]:
        exp_btn = st.button("Explain SQL", use_container_width=True)
    with btns[2]:
        if st.button("Reset demo DB", use_container_width=True):
            init_db(st.session_state.conn, force_rebuild=True)
            st.success("Database reset.")

    conn = st.session_state.conn
    schema_text = get_schema_text(conn)
    tables_ok, cols_ok = allowed_identifiers(conn)

    if go and nl.strip():
        try:
            nl_norm = normalize_time_phrases(nl)
            raw_sql = generate_sql(nl_norm, schema_text, limit)
            sql = sanitize_sql(raw_sql, limit)
            validate_with_sqlglot(sql, tables_ok, cols_ok)
        except Exception as e:
            # Try a single repair
            try:
                repaired = repair_sql(nl, str(e), schema_text, limit)
                sql = sanitize_sql(repaired, limit)
                validate_with_sqlglot(sql, tables_ok, cols_ok)
                st.info("First attempt failed; used repair pass.")
            except Exception as e2:
                st.error(f"Could not generate a safe query.\n\n{e2}")
                sql = None

        if sql:
            if show_sql:
                st.code(sql, language="sql")
            try:
                df = conn.execute(sql).df()
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.success(f"Returned {len(df)} row(s).")
            except Exception as e:
                st.error(f"Execution error: {e}")

    if exp_btn:
        if not show_sql:
            st.warning(
                "Generate a query (and check 'Show generated SQL') first, then click Explain."
            )
        else:
            # Try to pull the last displayed SQL from Streamlit's stateful element? Simpler: regenerate best-effort.
            if nl.strip():
                try:
                    raw_sql = generate_sql(nl, schema_text, limit)
                    sql = sanitize_sql(raw_sql, limit)
                    explanation = explain_sql(sql)
                    st.write(explanation)
                except Exception as e:
                    st.error(f"Could not explain: {e}")

with tabs[1]:
    hero()
    st.markdown("### About this demo")
    st.markdown(
        """
**Goal.** Ask questions in natural language; get **safe SQL** and results on a film/cinema dataset.

**Baseline:**  
- LLM translates NL → SQL (DuckDB dialect).  
- Small curated schema: `cinemas, movies, people, movie_directors, cast, genres, movie_genres, festivals, festival_entries, awards, movie_awards, screenings`.  
- One-click examples; optional “Show SQL”.

**Guardrails (Advanced):**  
- **SELECT-only**; block DDL/DML keywords.  
- **LIMIT** enforced.  
- **Schema-bounded** generation (we pass the exact schema).  
- **SQL parsing** with `sqlglot` + validation of table/column names.  
- **Repair loop** (retries once with error feedback).  
- Optional **Explain** step via LLM (no chain-of-thought, just high-level intent).

**Tech Stack:**  
- **DuckDB** (file-based OLAP, zero-ops).  
- **Streamlit** UI (fast dev).  
- **OpenAI** for NL→SQL + brief explanations.  
- **sqlglot** for robust parsing and static checks.

**Extend in minutes:**  
- Self-verification agent: run a second pass that checks query vs. constraints and proposes a fix.  
- Add cost/latency telemetry, caching (e.g., `st.cache_data`).  
- Add row-level security or “safe columns only” whitelist.  
- Swap in company schema / connect to Postgres.  
"""
    )
