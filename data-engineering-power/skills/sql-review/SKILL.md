---
name: sql-review
description: Review SQL queries for security, correctness, performance, and readability. Use when the user asks to review, audit, or improve SQL.
---

# SQL Review

## Step 1: Establish context

Identify the dialect (PostgreSQL, MySQL, SQLite, BigQuery, and so on) and whether the query runs in production. If you can't tell the dialect, say which one you assumed.

## Step 2: Check, in priority order

1. Security
   - User input concatenated or interpolated into SQL means injection risk. Require parameterized queries.
   - Hardcoded credentials, connection strings, or tokens.
   - Access that's too broad, such as `GRANT ALL`, or reading tables the task doesn't need.
2. Destructive statements
   - `DELETE` or `UPDATE` without a `WHERE`, `TRUNCATE`, or `DROP`.
   - Flag these as high risk and recommend running them in a transaction plus a dry-run `SELECT COUNT(*)`.
3. Correctness
   - `NULL` comparisons that use `=` instead of `IS NULL`.
   - `NOT IN` against a subquery that can return NULLs.
   - Joins that multiply rows (fan-out), and missing join conditions.
   - Aggregates with non-aggregated columns missing from `GROUP BY`.
   - Implicit type casts, time zone handling, and integer division.
4. Performance
   - `SELECT *` in production-oriented queries.
   - Functions wrapped around indexed columns in `WHERE`.
   - Leading-wildcard `LIKE`, correlated subqueries, and missing `LIMIT` on exploration queries.
   - Suggest `EXPLAIN`, or `EXPLAIN ANALYZE` on a safe copy, instead of guessing.
5. Readability
   - Consistent keyword casing, meaningful aliases, CTEs instead of deep nesting, and comments on business logic.

## Step 3: Report

For each finding, give its severity (`critical`, `high`, `medium`, `low`), the line or fragment, why it matters, and a corrected snippet. End with the full revised query.

Never run the query yourself against a real database unless the user explicitly asks. If they do, use a read-only connection.
