# Architecture

NaturalQL has one job: turn a question into SQL without letting generated text
go straight to the database. The application is intentionally small, so the
entire path from prompt to result can be followed in one diagram.

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Inter,Segoe UI,Arial,Helvetica,sans-serif",
    "primaryColor": "#E0F2FE",
    "primaryBorderColor": "#0284C7",
    "primaryTextColor": "#0F172A",
    "lineColor": "#94A3B8"
  }
}}%%
flowchart LR
  classDef user  fill:#FEF3C7,stroke:#F59E0B,stroke-width:2px,color:#111827;
  classDef ui    fill:#E0F2FE,stroke:#0284C7,stroke-width:2px,color:#0C4A6E;
  classDef llm   fill:#EDE9FE,stroke:#7C3AED,stroke-width:2px,color:#1E1B4B;
  classDef guard fill:#ECFCCB,stroke:#65A30D,stroke-width:2px,color:#14532D;
  classDef data  fill:#FAE8FF,stroke:#A21CAF,stroke-width:2px,color:#3B0764;
  classDef db    fill:#F1F5F9,stroke:#334155,stroke-width:2px,color:#0F172A;

  U([Question]):::user --> UI[Streamlit UI]:::ui
  UI -->|Question + rules| LLM[OpenAI]:::llm
  SCH[Database structure]:::data --> LLM
  LLM -->|Candidate SQL| GR[Parse and validate]:::guard
  GR -->|Accepted SQL| DB[(Read-only DuckDB)]:::db
  GR -. validation error .-> RP[One repair attempt]:::guard
  RP --> LLM
  DB -->|SQL + results| UI

  linkStyle default stroke:#94A3B8,stroke-width:2.2px,opacity:0.95
```

## The request path

1. **Streamlit collects the question.** Supported relative phrases such as
   “this summer” are converted into explicit dates using a configured reference
   date.
2. **OpenAI proposes SQL.** The prompt includes the database tables and columns,
   the DuckDB dialect, and rules for common joins and filters.
3. **The application validates the proposal.** sqlglot parses the SQL into an
   abstract syntax tree, or AST. Working with the parsed structure avoids the
   false positives and gaps of searching raw text for keywords.
4. **DuckDB runs accepted SQL.** Generated queries use a separate read-only
   connection with external access disabled.
5. **Streamlit shows the evidence.** The user can inspect the SQL next to the
   returned rows and ask for an explanation of that exact query.

## Why the repair loop is bounded

If the first query fails validation, NaturalQL sends the error and the database
structure back to the model once. The repaired query receives no special trust:
it starts at the beginning of the same validation process.

One attempt is enough to demonstrate useful recovery without creating an
open-ended agent loop, unpredictable latency, or repeated API costs.

## Connection boundaries

Database setup and reset are trusted application operations. They use a
short-lived connection that can create and populate tables. Model-generated SQL
never uses that connection; it reaches only the read-only query connection.

This separation complements the SQL validator. A bug in one layer should not
silently turn generated SQL into a database write.
