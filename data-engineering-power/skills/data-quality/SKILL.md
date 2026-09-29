---
name: data-quality
description: Suggest and define data quality rules from a dataset profile, such as completeness, uniqueness, validity, and consistency checks. Use after profiling, or when the user asks for validation rules or data checks.
---

# Data Quality

## Input

Use the JSON profile from `data-profiling`. If you don't have one, run that skill first. Only suggest rules the evidence supports, and cite the metric behind each one.

## Step 1: Derive rule candidates

| Evidence in the profile | Suggested rule | Default severity |
|---|---|---|
| `null_count == 0` | `not_null(<col>)` | error |
| `0 < null_pct < 20` | `null_pct(<col>) <= <observed pct rounded up>` | warn |
| `unique_count == row_count - null_count` and `null_count == 0` | `unique(<col>)` (candidate key) | error |
| `duplicate_count > 0` | `no_duplicate_rows` | warn |
| `inferred_type` is `integer`, `float`, `boolean`, or `datetime` | `type_is(<col>, <type>)` | error |
| `unique_count` is small (≤ 10) and `row_count` ≥ 50 | `accepted_values(<col>, [...])` from the full distinct set | warn |
| Column names like `*_id`, `*_at`, `*_date`, `email` | a format rule, such as `matches(<col>, <regex>)` | warn |

Don't hard-code thresholds that can't be explained. Take them from the observed values and say so.

## Step 2: Define every rule completely

Each rule needs all five fields. A rule missing any of them is not ready.

1. Rule name: `snake_case` and unique
2. Input column(s)
3. Validation logic: precise and executable, such as a predicate or SQL expression
4. Failure condition: when the rule fails, with any threshold
5. Result format: for example `{"rule", "passed": bool, "failed_count": int, "sample_failures": [...]}`

## Step 3: Output

Show the rules as a table using the "Suggested quality rules" section of the profiling report template.

Where a rule maps to a Scrubby rule (`not_null`, `unique`, `valid_email`, `regex`, `in_range`, `accepted_values`, `type_is`), also emit a Scrubby Rule_Set and run it with `quality_report(path, rules)`:

```json
{"business_key": ["customer_id"],
 "columns": [{"column": "email", "rules": ["not_null", "valid_email"]},
             {"column": "amount", "rules": [{"name": "in_range", "min": 0}]}]}
```

If the user asks for executable checks outside Scrubby, write them as:
- Python for pandas: read with `dtype=str, keep_default_na=False`
- SQL: parameterized, no `SELECT *`

Mark each rule as "observed" when the data already passes it, or "aspirational" when the data currently fails it.
