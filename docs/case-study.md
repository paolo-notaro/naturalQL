# NaturalQL case study

NaturalQL explores a narrow question: how much deterministic control can be
placed between a language model that proposes SQL and a database that executes
it?

## Design

The application uses a seeded cinema schema because it is immediately
understandable while still supporting non-trivial questions about screenings,
directors, casts, genres, festivals, and awards. DuckDB keeps the demonstration
local and repeatable; Streamlit provides a minimal query interface.

The language model receives the current schema and a concise set of DuckDB
generation rules. Its response is not executed directly. NaturalQL parses it
with sqlglot, validates its sources and identifiers, rejects operations outside
the query policy, and applies an output limit. A failure may be returned to the
model once for repair, after which the full policy runs again.

## Why deterministic validation matters

Prompt instructions are probabilistic. They can reduce malformed output, but
they cannot guarantee that a model will obey a read-only requirement or use the
right schema. The validator therefore owns enforcement, while the prompt owns
generation quality.

The database connection used for generated SQL is also read-only and has
external access disabled. That second boundary reduces reliance on any single
parser or validation rule.

## Trade-offs

NaturalQL deliberately favors a small, inspectable policy over broad SQL
compatibility. It demonstrates structural safety and reproducible behavior, not
semantic proof. A query can satisfy every policy rule and still answer the wrong
question.

The result cap is likewise not a resource sandbox. Production execution would
need database-native permissions, workload limits, observability, and approval
rules appropriate to the underlying data.

## Further work

- Compare generated SQL with a curated evaluation set.
- Add semantic checks for required filters and join paths.
- Record latency, token usage, validation failures, and repair outcomes.
- Move execution behind a database role with domain-specific authorization.
- Add explicit CPU, memory, and wall-clock limits outside the application.
