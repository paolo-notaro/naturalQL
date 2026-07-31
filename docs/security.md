# Security and reliability

The central rule in NaturalQL is simple: generated SQL is never trusted because
it came from the model.

OpenAI can propose a query, but it has no database connection or credentials.
Application code decides whether the query is structurally acceptable, and
DuckDB provides a second enforcement layer at execution time.

## What happens to generated SQL

Every initial or repaired query goes through the same sequence:

1. Extract SQL from the model response and reject empty or oversized output.
2. Parse exactly one statement using the DuckDB dialect.
3. Require a query expression and reject writes or database commands.
4. Check physical tables against the allowed application tables.
5. Resolve columns, aliases, and nested scopes against the live database
   structure.
6. Reject table-producing functions that could introduce an external source.
7. Reject an excessively large syntax tree.
8. Add or cap the result limit.
9. Execute through the read-only connection with external access disabled.

Working with a parsed syntax tree matters. A keyword search can reject harmless
text such as a movie title containing “drop,” while still missing a dangerous
operation expressed in an unexpected form.

## Defense in depth

The query policy is the first enforcement layer. It controls which SQL shapes
and database objects are accepted.

The DuckDB connection is the second layer. Generated queries use a connection
opened in read-only mode with external access disabled. Database initialization
and reset happen through a separate trusted connection that is closed before
query execution begins.

The model prompt is useful for query quality, but it is deliberately not counted
as a security layer.

## Reliability choices

- Relative dates use a fixed, configurable reference date.
- The model and validator use the structure read from the same database.
- Failed validation allows one repair attempt, not an open-ended loop.
- A repaired query starts the full validation process again.
- Explanations use the exact SQL that ran.
- Tests use mocked model responses and require no API key or network access.

## What remains outside the boundary

Passing validation means a query is allowed to run. It does not mean the query
correctly understood the question. The model can still choose a wrong join,
omit an important filter, or produce a misleading aggregate.

A row limit controls the size of the returned result, not CPU time, memory, or
the amount of data scanned. This demo also has no users, roles, audit trail, or
tenant isolation.

A production version should add database-native permissions, statement
timeouts, resource limits, audit logging, monitoring, and authorization rules
for the real data domain. NaturalQL's validator should complement those controls,
not replace them.
