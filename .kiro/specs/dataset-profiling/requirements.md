# Requirements Document

## Introduction

Scrubby is a stateless data quality service. A user uploads one or more CSV datasets to the Scrubby API. For each dataset the service validates the file, profiles every column, evaluates validation rules, detects duplicate records, computes a deterministic quality score from 0 to 100, and returns a quality report as JSON or HTML. Nothing is stored between requests.

## Glossary

- **Scrubby_API**: The FastAPI HTTP adapter that receives uploads and returns reports.
- **Upload_Handler**: The component that validates an uploaded file and builds a Dataset.
- **Profiler**: The component that computes dataset-level and column-level metrics.
- **Rule_Engine**: The component that evaluates validation rules against a Dataset.
- **Deduplicator**: The component that detects duplicate records.
- **Scorer**: The component that computes quality dimensions and the quality score.
- **Reporter**: The component that renders a Quality_Report as JSON or HTML.
- **Dataset**: A CSV file (RFC 4180, UTF-8) with a header row naming each column, followed by zero or more Rows.
- **Valid_Dataset**: A Dataset that passes every check in Requirement 1.
- **Row** / **Record**: One data line of the Dataset, not counting the header.
- **Cell**: The raw, untrimmed string value of one column in one Row.
- **Null_Value**: A Cell that is empty or contains only whitespace. `NA`, `null`, and `None` are ordinary values.
- **Trimmed_Value**: A Cell with leading and trailing whitespace removed.
- **Value_Type**: The type a single Trimmed_Value satisfies first in the order `boolean`, `integer`, `float`, `datetime`, `string` (definitions in Requirement 2).
- **Inferred_Type**: A column's type: one of `boolean`, `integer`, `float`, `datetime`, `string`, `null`.
- **Rule**: A named check applied to one column, listed in Requirement 3.
- **Rule_Set**: The rules and optional Business_Key for one Dataset, either supplied by the user or suggested by the system.
- **Business_Key**: An ordered list of one or more columns whose values identify a Record.
- **Duplicate_Record**: A Record whose key equals the key of an earlier Record (see Requirement 4). The first occurrence is not a duplicate.
- **Quality_Report**: The result for one Dataset: profile, rule results, duplicate results, dimensions, score, and issues.
- **Percentage**: A number from 0 to 100, computed exactly and rounded to 1 decimal place using round-half-even.

## Requirements

### Requirement 1: Dataset Ingestion

**User Story:** As a data analyst, I want to upload one or more CSV files and have each one validated, so that I only get reports for well-formed data.

#### Acceptance Criteria

1. WHEN one or more CSV files are uploaded in a single request, THE Scrubby_API SHALL process each file independently and return one result per file, in upload order.
2. THE Scrubby_API SHALL accept at most 10 files per request and SHALL reject a request with more files with code `TOO_MANY_FILES` without processing any file.
3. IF a file is larger than 100 MB (104,857,600 bytes), THEN THE Upload_Handler SHALL return the error `FILE_TOO_LARGE` for that file without parsing it.
4. IF a file is 0 bytes or has no header row, THEN THE Upload_Handler SHALL return the error `EMPTY_DATASET`.
5. IF a file is not valid UTF-8 or fails strict RFC 4180 parsing, THEN THE Upload_Handler SHALL return the error `INVALID_FORMAT` with the 1-based line number when it can be determined.
6. IF the header contains empty names (empty or whitespace only) or exact, case-sensitive duplicate names, THEN THE Upload_Handler SHALL return the error `INVALID_HEADER` listing the 1-based positions of all problem columns in ascending order.
7. IF any Row has a different number of fields than the header, THEN THE Upload_Handler SHALL return the error `ROW_LENGTH_MISMATCH` with the row number of the first mismatched Row, where the header is row 1.
8. IF a file fails more than one check, THEN THE Upload_Handler SHALL return only the first failing code in the order `FILE_TOO_LARGE`, `EMPTY_DATASET`, `INVALID_FORMAT`, `INVALID_HEADER`, `ROW_LENGTH_MISMATCH`.
9. WHEN a file has a valid header and zero Rows, THE Upload_Handler SHALL treat it as a Valid_Dataset.
10. WHEN one file in a request fails validation, THE Scrubby_API SHALL still return reports for the other files in that request.
11. THE Upload_Handler SHALL keep every Cell as its raw string and SHALL NOT convert `NA`, `null`, numbers, or leading zeros.

### Requirement 2: Data Profiling

**User Story:** As a data analyst, I want dataset and column statistics, so that I understand the size, shape, and content of my data.

#### Acceptance Criteria

1. WHEN a Valid_Dataset is profiled, THE Profiler SHALL report `row_count` (Rows excluding the header), `column_count`, `null_count` (total Null_Value Cells), `duplicate_count` (from Requirement 4), and `potential_issues` (from Requirement 6.3).
2. WHEN a Valid_Dataset is profiled, THE Profiler SHALL report for each column, in header order: `name`, `inferred_type`, `null_count`, `null_pct`, `unique_count`, `unique_pct`, and `invalid_count`.
3. THE Profiler SHALL compute `null_pct` as `null_count / row_count` as a Percentage, and 0 when `row_count` is 0.
4. THE Profiler SHALL compute `unique_count` as the number of distinct Trimmed_Values among non-null Cells, compared exactly and case-sensitively, and `unique_pct` as `unique_count / non_null_count` as a Percentage, and 0 when the column has no non-null Cells.
5. WHEN a column's Inferred_Type is `integer` or `float`, THE Profiler SHALL report `min` and `max` as the Trimmed_Values of the smallest and largest numeric values, compared by exact decimal value. For all other types, `min` and `max` SHALL be `null`.
6. THE Profiler SHALL compute `invalid_count` for a column as the number of distinct Rows that fail at least one validity Rule (Requirement 3.4) on that column.
7. THE Profiler SHALL determine the Value_Type of a Trimmed_Value using these definitions:
   - `boolean`: `true` or `false`, case-insensitive. `1`, `0`, `yes`, `no`, `t`, and `f` are not boolean.
   - `integer`: an optional `+` or `-` followed by one or more ASCII digits.
   - `float`: an optional sign, ASCII digits with at most one decimal point, and an optional exponent (`e`/`E`, optional sign, digits), with a finite value. `NaN`, `Infinity`, hexadecimal, and thousands separators are not numeric.
   - `datetime`: an ISO 8601 date `YYYY-MM-DD` or date-time `YYYY-MM-DDTHH:MM[:SS[.fraction]]` with an optional `Z` or `±HH:MM` offset, which is a real calendar date and time (hour 0-23, minute and second 0-59, offset hours 0-23 and minutes 0-59).
   - `string`: anything else.
8. THE Profiler SHALL report a column's Inferred_Type as the first type in the order `null`, `boolean`, `integer`, `float`, `datetime`, `string` that every non-null Trimmed_Value satisfies, where an `integer` value also satisfies `float`, and `null` means the column has no non-null Cells.

### Requirement 3: Validation Rules

**User Story:** As a data engineer, I want to declare validation rules per column and see which pass or fail, so that I can find bad records.

#### Acceptance Criteria

1. THE Scrubby_API SHALL accept an optional Rule_Set per request as JSON of the form `{"business_key": ["col", ...], "columns": [{"column": "email", "rules": ["not_null", "unique", "valid_email", {"name": "regex", "pattern": "..."}]}]}`. The same Rule_Set applies to every file in the request, and entries naming columns that a file does not have SHALL be reported as rule results with status `SKIPPED`.
2. IF the Rule_Set is not valid JSON, names an unknown Rule, is missing a required parameter, has an invalid parameter (for example an uncompilable pattern, a pattern longer than 200 characters, or `min > max`), or has an unknown field, THEN THE Scrubby_API SHALL reject the whole request with code `INVALID_RULES` and a message naming the offending entry, without processing any file.
3. THE Rule_Engine SHALL support these Rules:
   - `not_null`: fails for each Row whose Cell is a Null_Value.
   - `unique`: fails for each non-null Row whose Trimmed_Value equals that of an earlier non-null Row.
   - `valid_email`: fails for each non-null Trimmed_Value that does not fully match `^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$`.
   - `regex` (`pattern`): fails for each non-null Trimmed_Value that does not fully match `pattern`.
   - `in_range` (`min`, `max`, both optional, at least one given): fails for each non-null Trimmed_Value that is not `integer` or `float`, or whose value is outside `[min, max]` inclusive.
   - `accepted_values` (`values`: non-empty list of strings): fails for each non-null Trimmed_Value not in `values` (exact, case-sensitive).
   - `type_is` (`type`: `boolean`, `integer`, `float`, `datetime`, or `string`): fails for each non-null Trimmed_Value that does not satisfy `type`, where `integer` values satisfy `float` and every value satisfies `string`.
4. THE Rule_Engine SHALL classify `not_null` as a completeness Rule, `unique` as a uniqueness Rule, and all other Rules as validity Rules. Only `not_null` SHALL evaluate Null_Values; every other Rule SHALL skip them.
5. WHEN a Rule is evaluated, THE Rule_Engine SHALL report `column`, `rule` (name and parameters), `status` (`PASS` if zero Rows fail, `FAIL` otherwise, or `SKIPPED`), `evaluated_count`, `failed_count`, and `failed_rows` (the first 10 failing row numbers, ascending, header = row 1). It SHALL NOT include Cell values.
6. WHEN no Rule_Set is supplied, THE Rule_Engine SHALL use a suggested Rule_Set derived only from the profile, and SHALL mark each result with `source: "suggested"` (user rules get `source: "user"`). For each column with at least one non-null Cell:
   - `not_null` when `null_count` is 0;
   - `unique` when `null_count` is 0 and `unique_count` equals `row_count`;
   - `type_is` with the Inferred_Type when it is `boolean`, `integer`, `float`, or `datetime`;
   - `valid_email` when the column name contains `email`, case-insensitive.
7. THE Rule_Engine SHALL order rule results by column header position, then in the order the Rules were declared (user) or listed in criterion 6 (suggested).

### Requirement 4: Duplicate Detection

**User Story:** As a data engineer, I want duplicate records detected by a business key or by the whole row, so that I can remove redundant data.

#### Acceptance Criteria

1. WHEN a Business_Key is supplied, THE Deduplicator SHALL compare Records by the tuple of Trimmed_Values of the key columns, exact and case-sensitive. WHEN no Business_Key is supplied, THE Deduplicator SHALL compare whole Rows by their raw Cells, exact and case-sensitive, without trimming.
2. IF a supplied Business_Key names a column that a file does not have, THEN THE Deduplicator SHALL fall back to whole-row comparison for that file and SHALL report `key_status: "MISSING_COLUMNS"` with the missing names.
3. THE Deduplicator SHALL report `key` (the Business_Key columns, or `null` for whole-row), `total_records`, `unique_records`, `duplicate_records`, and `duplicate_rows` (the first 10 duplicate row numbers, ascending).
4. THE Deduplicator SHALL satisfy `duplicate_records = total_records - unique_records`, `unique_records <= total_records`, and `unique_records >= 1` whenever `total_records >= 1`.
5. WHEN a Dataset has zero Rows, THE Deduplicator SHALL report 0 for all counts.

### Requirement 5: Quality Score

**User Story:** As a data lead, I want one deterministic score from 0 to 100 with a clear breakdown, so that I can compare datasets and track them over time.

#### Acceptance Criteria

1. THE Scorer SHALL compute four dimensions, each a Percentage:
   - `completeness` = non-null Cells / total Cells.
   - `uniqueness` = `unique_records / total_records` from Requirement 4.
   - `validity` = (Rows evaluated minus Rows failed) / Rows evaluated, summed over all validity Rule results with status `PASS` or `FAIL`.
   - `consistency` = non-null Cells whose Value_Type equals their column's Dominant_Type / total non-null Cells, where a column's Dominant_Type is its most frequent Value_Type among non-null Cells, with ties broken by the order `boolean`, `integer`, `float`, `datetime`, `string`, and `integer` Cells count as `float` in a column whose Inferred_Type is `float`.
2. WHEN a dimension has a zero denominator (no Cells, no Records, no validity Rules evaluated, or no non-null Cells), THE Scorer SHALL report that dimension as 100.
3. THE Scorer SHALL compute `score` as the weighted mean of the four unrounded dimensions with weights completeness 0.25, uniqueness 0.25, validity 0.25, consistency 0.25, as a Percentage.
4. THE Scorer SHALL use exact rational arithmetic until the final rounding, so the score and dimensions are identical on every platform and run.
5. FOR ALL Valid_Datasets and Rule_Sets, every dimension and the score SHALL be within [0, 100].
6. WHEN a Record that is complete, not a duplicate, and passes every Rule is appended to a Dataset, THE Scorer SHALL NOT report lower `completeness`, `uniqueness`, or `validity`.

### Requirement 6: Quality Report

**User Story:** As a data analyst, I want a JSON or HTML report per dataset, so that I can read the results or feed them into other tools.

#### Acceptance Criteria

1. THE Reporter SHALL produce for each Valid_Dataset a Quality_Report containing, in this order: `dataset` (the uploaded file name), `score`, `issues`, `dimensions`, `summary` (Requirement 2.1 dataset metrics), `columns` (Requirement 2.2), `rules` (Requirement 3.5), and `duplicates` (Requirement 4.3).
2. THE Reporter SHALL compute `issues` as the sum of `failed_count` over all Rule results with status `FAIL`, plus `duplicate_records`.
3. THE Reporter SHALL compute `potential_issues` as the number of Rule results with status `FAIL`, plus 1 if `duplicate_records > 0`.
4. WHEN a file fails validation, THE Reporter SHALL return for that file `{"dataset", "error": {"code", "message", "line", "positions", "row_number"}}` and no other fields.
5. WHEN JSON output is requested, THE Reporter SHALL emit UTF-8 JSON without a BOM, with keys in the documented order, no NaN or Infinity, and Percentages as JSON numbers with at most 1 decimal place.
6. WHEN HTML output is requested, THE Reporter SHALL emit a single self-contained HTML5 document per request, with no external scripts, styles, fonts, or images, that shows for each file the score, dimensions, summary, column table, rule results with PASS/FAIL/SKIPPED, and duplicates, or the error.
7. THE Reporter SHALL HTML-escape every value that comes from the uploaded file or the Rule_Set, including file names and column names.
8. THE HTML report SHALL use semantic tables with header cells and captions, a document language, and SHALL NOT convey PASS/FAIL by color alone.
9. THE Reporter SHALL NOT include timestamps, random identifiers, hostnames, absolute paths, Cell values, or locale-dependent formatting in the report body.
10. WHEN the CLI writes a report to disk, THE CLI SHALL name it `reports/quality-report-<YYYY-MM-DD>.<json|html>` using the current UTC date, and SHALL NOT overwrite an existing file (it appends `-2`, `-3`, and so on).

### Requirement 7: Scrubby API

**User Story:** As an integrating developer, I want a small HTTP API, so that I can call Scrubby from other systems.

#### Acceptance Criteria

1. THE Scrubby_API SHALL expose `POST /v1/reports`, accepting multipart form data with one or more `files` and an optional `rules` field (Rule_Set JSON), and a query parameter `format` of `json` (default) or `html`.
2. WHEN the request is processed, THE Scrubby_API SHALL return status 200 with `{"reports": [...]}` for JSON, or `text/html; charset=utf-8` for HTML, including when some files failed validation.
3. IF the request has no files, more than 10 files, invalid rules, or an unknown `format`, THEN THE Scrubby_API SHALL return status 422 with `{"code", "message"}` and SHALL NOT process any file.
4. IF the total request body exceeds 10 × 100 MB, THEN THE Scrubby_API SHALL reject it with status 413 and code `REQUEST_TOO_LARGE` before parsing any file.
5. THE Scrubby_API SHALL expose `GET /health` returning `{"status": "ok"}`.
6. IF an unexpected error occurs, THEN THE Scrubby_API SHALL return status 500 with `{"code": "INTERNAL_ERROR", "message": "internal error"}` and SHALL NOT include stack traces or file contents.
7. THE Scrubby_API SHALL NOT store uploaded files or reports after the response is sent.

### Requirement 8: Determinism

**User Story:** As an integrating developer, I want identical input to give identical output, so that I can diff and cache reports.

#### Acceptance Criteria

1. WHEN the same files, file names, Rule_Set, and format are processed more than once, including across separate processes, THE Scrubby_API SHALL return byte-identical report bodies.
2. THE Rule_Engine, Deduplicator, Scorer, and Reporter SHALL NOT depend on wall-clock time, randomness, environment variables, locale, or hash seed ordering.
