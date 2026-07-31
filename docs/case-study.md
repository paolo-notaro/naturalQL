# Building NaturalQL

Natural-language-to-SQL demos often stop at the most impressive moment: the
model returns a plausible query. NaturalQL follows the query through the less
flashy but more important next step—deciding whether it should run.

The result is a compact application where a user can ask a surprisingly rich
question, inspect the generated SQL, and see the answer without setting up a
database server.

## The starting point

The interface needed to feel immediate, so NaturalQL includes a local movie
database with cinemas, schedules, people, festivals, and awards. The domain is
easy to understand while still producing interesting queries with many-to-many
joins, overlapping dates, aggregates, and exclusions.

DuckDB keeps the data local. Streamlit keeps the interface focused on three
things: the question, the SQL, and the result.

## Making generation useful

OpenAI receives the current database structure and a concise set of DuckDB
rules. Those rules cover details that commonly make generated queries brittle:

- use explicit joins;
- qualify ambiguous columns;
- handle cinema schedules as overlapping date ranges;
- use `NOT EXISTS` for “never” conditions;
- apply a result limit.

A small date normalizer resolves supported phrases such as “this summer” before
the question reaches the model. The reference date is configurable, so the same
demo question behaves consistently later.

## Making generation safe to run

The prompt improves the first attempt, but it does not enforce anything.
NaturalQL treats the returned text like any other untrusted input.

sqlglot parses the candidate query and resolves its tables, columns, aliases,
and nested scopes against DuckDB's actual structure. The policy rejects writes,
database commands, multiple statements, external sources, and queries outside
the configured size and complexity bounds. It also applies the maximum result
limit to the parsed query rather than editing SQL as a string.

Accepted SQL runs through a read-only DuckDB connection with external access
disabled. Setup and reset operations use a different, short-lived connection.

## Recovering without hiding failures

Generated SQL will sometimes be wrong. If the first attempt fails validation,
NaturalQL gives OpenAI the validation error and one chance to repair it. The new
query must pass every check again.

The loop stops there. A single retry keeps the behavior understandable and the
cost bounded, while still recovering from common mistakes such as an incorrect
column name or grouping rule.

## What this project proves—and what it does not

NaturalQL demonstrates that LLM-generated SQL can be placed behind concrete,
testable access controls. It does not prove that accepted SQL is the best or
even the correct interpretation of a question.

That remaining gap is the most interesting direction for future work:

- compare results against a curated evaluation set;
- check whether required filters and relationships appear in the query;
- record generation latency, validation failures, and repair success;
- enforce database-native workload and authorization policies.

The project stays intentionally small so those trade-offs remain visible rather
than disappearing behind infrastructure.
