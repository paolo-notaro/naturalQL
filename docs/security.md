# Security and reliability

NaturalQL treats language-model output as untrusted input. Prompt instructions
improve generation quality, but they are not part of the security boundary.

## Trust boundary

Only SQL accepted by the deterministic query policy is sent to DuckDB. The
policy parses one statement, admits query expressions, checks physical sources
and columns against the live schema, rejects external table functions, bounds
query size and complexity, and caps returned rows. A repaired query is checked
from the beginning rather than inheriting trust from the first attempt.

Database creation and reset use a short-lived administrative connection.
Generated queries run through a separate read-only connection configured with
external access disabled. This is a second line of defense if validation has an
unexpected gap.

## Reliability controls

- A fixed, configurable reference date makes supported relative phrases
  reproducible.
- Schema text supplied to the model is derived from the same database used by
  the validator.
- Validation failures permit one repair attempt, avoiding unbounded agent loops.
- SQL explanations use the exact validated query that was executed.
- Tests use mocked model responses and a malicious-query regression set.

## Limitations

The validator establishes a syntactic and access-control boundary; it does not
establish semantic equivalence between a question and a query. Valid SQL can
still misunderstand intent, choose an incorrect join, or produce misleading
aggregates.

A result limit controls returned rows, not CPU time, memory, or rows scanned.
DuckDB is embedded in the application and this demo does not provide tenant
isolation, query timeouts, audit storage, or user authorization. Those controls
belong in the database and execution environment of a production system.

Do not expose this demo directly to untrusted multi-tenant traffic or substitute
its validator for database permissions.
