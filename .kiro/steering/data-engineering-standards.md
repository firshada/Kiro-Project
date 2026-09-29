---
inclusion: always
---

# Data Engineering Standards

## Data Processing

- Use pandas for tabular processing by default.
  - Exception (dataset-profiling): the Upload_Handler and Profiler use the standard library `csv` module (`strict=True`) and plain Python. This keeps RFC 4180 validation strict, gives exact line numbers for `INVALID_FORMAT`, and keeps every cell as a raw, untrimmed string so null, unique, and duplicate counts and type inference follow the spec exactly (pandas would coerce types and parse `NA`/`null` as missing by default). Use pandas here only for analysis beyond the spec, reading with `dtype=str, keep_default_na=False`.
- Avoid loading unnecessarily large datasets into memory.
- Data transformations must be deterministic.
- Business rules must be separated from infrastructure code.

## Data Quality

Every quality rule must define:

1. Rule name
2. Input column(s)
3. Validation logic
4. Failure condition
5. Result format

## SQL

- Use parameterized queries.
- Never hardcode credentials.
- Avoid SELECT * in production-oriented queries.