"""Streamlit interface for NaturalQL."""

import re
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from naturalql import db, guards, llm
from naturalql.config import Settings
from naturalql.nlp import normalize_time_phrases

st.set_page_config(page_title="NaturalQL", page_icon="🎬", layout="centered")

MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"
FENCE_RE = re.compile(r"```mermaid\s*(.*?)\s*```", re.S | re.I)


def render_mermaid_from_md(md_path: str | Path, *, height: int = 760) -> None:
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


def hero() -> None:
    """Render the application heading."""
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
    """Return a read-only query connection for the configured database."""
    existing = st.session_state.get("conn")
    if st.session_state.get("db_path") != path or existing is None:
        existing = st.session_state.pop("conn", None)
        if existing is not None:
            existing.close()
        db.initialize_database(path)
        st.session_state["conn"] = db.connect_for_queries(path)
        st.session_state["db_path"] = path
    return st.session_state["conn"]


def get_schema_and_sets(conn):
    return db.schema_text(conn), db.allowed_identifiers(conn)


def reset_database(path: str) -> None:
    """Rebuild the demo database, then restore its read-only query connection."""
    conn = st.session_state.pop("conn", None)
    if conn is not None:
        conn.close()
    db.initialize_database(path, force_rebuild=True)
    st.session_state["conn"] = db.connect_for_queries(path)


def main() -> None:
    settings = Settings.from_env()
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
                "Result limit", 1, 500, value=settings.result_limit, step=10
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
        with st.expander("Example questions"):
            st.markdown("\n".join(f"- {example}" for example in examples))

        show_sql = st.checkbox("Show generated SQL")
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            go = st.button("Generate & Run", type="primary", use_container_width=True)
        with col2:
            explain_btn = st.button("Explain SQL", use_container_width=True)
        with col3:
            if st.button("Reset demo DB", use_container_width=True):
                reset_database(settings.db_path)
                st.success("Database reset.")

        if go and nl.strip():
            st.session_state.pop("last_sql", None)
            nl_norm = normalize_time_phrases(nl, settings.today)
            policy = guards.QueryPolicy(
                result_limit=int(limit),
                max_sql_length=settings.max_sql_length,
                max_ast_nodes=settings.max_ast_nodes,
            )
            try:
                raw_sql = llm.generate_sql(
                    nl_norm,
                    schema_text,
                    int(limit),
                    today=settings.today,
                    model=model,
                )
            except llm.LLMConfigurationError as error:
                st.error(str(error))
                sql = None
            except Exception as error:
                st.error(f"SQL generation failed: {error}")
                sql = None
            else:
                try:
                    sql = guards.prepare_sql(raw_sql, tables_ok, cols_ok, policy)
                except guards.QueryRejected as initial_error:
                    try:
                        repaired = llm.repair_sql(
                            nl_norm,
                            str(initial_error),
                            schema_text,
                            int(limit),
                            model=model,
                        )
                        sql = guards.prepare_sql(repaired, tables_ok, cols_ok, policy)
                        st.info("First attempt failed; used repair pass.")
                    except Exception as repair_error:
                        st.error(
                            "Could not produce a query that satisfies the policy."
                            f"\n\n{repair_error}"
                        )
                        sql = None

            if sql:
                if show_sql:
                    st.code(sql, language="sql")
                try:
                    df = conn.execute(sql).df()
                    st.session_state["last_sql"] = sql
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.success(f"Returned {len(df)} row(s).")
                except Exception as e:
                    st.error(f"Execution error: {e}")

        if explain_btn:
            last_sql = st.session_state.get("last_sql")
            if not last_sql:
                st.warning("Generate and run a query first.")
            else:
                try:
                    explanation = llm.explain_sql(last_sql, model=model)
                    st.write(explanation)
                except Exception as e:
                    st.error(f"Could not explain: {e}")

    with about_tab:
        hero()
        st.markdown("### About this demo")
        st.markdown(
            """
NaturalQL converts a question into DuckDB SQL over a small cinema dataset.
The model proposes a query; deterministic application code decides whether it
may run.

Generated output must contain one query, reference the known schema, stay
within configured size and result bounds, and avoid external data sources. It
then runs through a separate read-only database connection. A failed query can
be repaired once and must pass the complete policy again.

These controls constrain database access, but they do not prove that a query
correctly represents the user's intent. Production systems also need database
roles, workload limits, audit logging, and domain-specific authorization.

The implementation uses OpenAI, sqlglot, DuckDB, and Streamlit.
"""
        )

        st.markdown("### Table Relations (ERD)")
        render_mermaid_from_md("docs/tables.md", height=760)


if __name__ == "__main__":
    main()
