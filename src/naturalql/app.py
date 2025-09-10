"""src/naturalql/app.py: Main application logic for NaturalQL."""

import re
from pathlib import Path

import duckdb

import streamlit as st
import streamlit.components.v1 as components
from naturalql.config import Settings
from naturalql import db, guards, llm
from naturalql.nlp import normalize_time_phrases


st.set_page_config(page_title="NaturalQL", page_icon="🎬", layout="centered")
APP_TITLE = "🎬 NaturalQL — Natural Language to Guardrailed SQL"

MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"
FENCE_RE = re.compile(r"```mermaid\s*(.*?)\s*```", re.S | re.I)


def render_mermaid_from_md(md_path: str | Path, *, height: int = 760):
    """
    Read a markdown file, extract the first ```mermaid``` block (or whole file),
    and render it with Mermaid via a simple startOnLoad init.
    """
    p = Path(md_path)
    if not p.exists():
        st.warning(f"Diagram file not found: {md_path}")
        return

    text = p.read_text(encoding="utf-8")
    m = FENCE_RE.search(text)
    code = (m.group(1) if m else text).strip()

    html = f"""
    <div class="mermaid" style="max-width:100%;">{code}</div>
    <script src="{MERMAID_CDN}"></script>
    <script>
      mermaid.initialize({{
        startOnLoad: true,
        securityLevel: "loose"
      }});
    </script>
    """
    components.html(html, height=height, scrolling=True)


def hero():
    """"""
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:12px;">
          <div style="font-size:42px;">🎬</div>
          <div>
            <div style="font-size:24px;font-weight:700;letter-spacing:.3px">NaturalQL</div>
            <div style="opacity:.7">Natural language → Guardrailed SQL on a cinema-like dataset</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_conn(path: str):
    if "conn" not in st.session_state:
        conn = db.connect(path)
        st.session_state["conn"] = conn
    # initialize schema + seed exactly once per app process
    if not st.session_state.get("db_initialized", False):
        db.init_db(
            st.session_state["conn"], force_rebuild=False
        )  # <-- no forced rebuild
        st.session_state["db_initialized"] = True
    return st.session_state["conn"]


def get_schema_and_sets(conn):
    return db.schema_text(conn), db.allowed_identifiers(conn)


def main():
    settings = Settings()
    conn = get_conn(settings.db_path)
    schema_text, (tables_ok, cols_ok) = get_schema_and_sets(conn)

    query_tab, about_tab = st.tabs(["Query", "About"])

    with query_tab:
        hero()
        st.write("")

        with st.sidebar:
            st.subheader("Settings")
            model = st.selectbox("OpenAI model", [settings.model, "gpt-4o"], index=0)
            limit = st.number_input(
                "Result limit", 10, 500, value=settings.result_limit, step=10
            )
            st.caption("Set OPENAI_API_KEY in your .env or environment.")

        nl = st.text_area(
            "Ask a question about movies, screenings, festivals, directors, cast, etc.",
            height=110,
            placeholder=(
                "e.g., Show all new Sci-Fi movies screened at Cinema Luna between 1 Jun and 31 Aug 2025, directed by debut directors, that never participated in A or S ranked festivals, share no cast member with any award-winning movie, have runtime ≥ 100 minutes, and were shown in 2D (not IMAX)."
            ),
        )

        examples = [
            "Show all new Sci-Fi movies screened at Cinema Luna between 1 Jun and 31 Aug 2025, directed by debut directors, that never participated in A or S ranked festivals, share no cast member with any award-winning movie, have runtime ≥ 100 minutes, and were shown in 2D (not IMAX).",
            "For each cinema, count how many new releases were screening in August 2025.",
            "List movies released in 2025 with their directors and primary genre.",
            "Find actors who worked with more than one director.",
            "Which movies screening at Cinema Luna in July 2025 have no festival participation?",
        ]
        st.caption("Examples:")
        st.write(" · " + "\n · ".join(examples))

        show_sql = st.checkbox("Show generated SQL")
        col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
        with col1:
            go = st.button("Generate & Run", type="primary", use_container_width=True)
        with col2:
            explain_btn = st.button("Explain SQL", use_container_width=True)
        with col3:
            if st.button("Reset demo DB", use_container_width=True):
                db.init_db(conn, force_rebuild=True)
                st.success("Database reset.")

        if go and nl.strip():
            nl_norm = normalize_time_phrases(nl)
            try:
                raw_sql = llm.generate_sql(nl_norm, schema_text, limit, model=model)
                sql = guards.sanitize_sql(raw_sql, limit)
                guards.validate_with_sqlglot(sql, tables_ok, cols_ok)
            except Exception as e:
                try:
                    repaired = llm.repair_sql(
                        nl_norm, str(e), schema_text, limit, model=model
                    )
                    sql = guards.sanitize_sql(repaired, limit)
                    guards.validate_with_sqlglot(sql, tables_ok, cols_ok)
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

        if explain_btn:
            if not show_sql:
                st.warning(
                    "Generate a query (and check 'Show generated SQL') first, then click Explain."
                )
            elif nl.strip():
                try:
                    raw_sql = llm.generate_sql(nl, schema_text, limit, model=model)
                    sql = guards.sanitize_sql(raw_sql, limit)
                    explanation = llm.explain_sql(sql, model=model)
                    st.write(explanation)
                except Exception as e:
                    st.error(f"Could not explain: {e}")

    with about_tab:
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

        st.markdown("### Table Relations (ERD)")
        erd_box = st.container()
        with erd_box:
            render_mermaid_from_md("docs/tables.md", height=760)


if __name__ == "__main__":
    main()
