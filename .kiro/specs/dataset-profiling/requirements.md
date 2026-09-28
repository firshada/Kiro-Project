# Requirements Document

## Introduction

Dataset Profiling computes summary statistics for an uploaded tabular dataset and returns the results as a deterministic JSON document. Dataset-level metrics are row count, column count, and duplicate row count. Column-level metrics are null count, unique count, and inferred data type.

## Glossary

- **Profiler**: The component that computes profiling metrics for a Dataset.
- **Upload_Handler**: The component that receives an uploaded file and validates it as a Dataset.
- **Dataset**: Tabular data with a header row that names each column, followed by zero or more data rows. The initial supported format is CSV (RFC 4180).
- **Valid_Dataset**: A Dataset that parses without errors, has at least one column, has unique non-empty column names, and has the same number of fields in every data row as in the header row.
- **Row**: A single data record in the Dataset, not counting the header row.
- **Null_Value**: A cell that is empty or contains only whitespace.
- **Duplicate_Row**: A Row whose values in every column exactly match an earlier Row in the Dataset.
- **Inferred_Type**: A column's data type, chosen from `integer`, `float`, `boolean`, `datetime`, `string`, or `null`.
- **Profile_Result**: The JSON document the Profiler produces.
- **Serializer**: The component that converts a Profile_Result into JSON text.
- **Parser**: The component that converts Profile_Result JSON text back into a Profile_Result object.

## Requirements

### Requirement 1: Dataset Upload and Validation

**User Story:** As a data analyst, I want to upload a dataset and have it validated, so that I only get profiles for well-formed data.

#### Acceptance Criteria

1. WHEN a Valid_Dataset is uploaded, THE Upload_Handler SHALL pass the Dataset to the Profiler.
2. IF the uploaded file fails to parse as CSV, THEN THE Upload_Handler SHALL return an error with code `INVALID_FORMAT` and a message describing the failure.
3. IF the uploaded Dataset has no header row, THEN THE Upload_Handler SHALL return an error with code `EMPTY_DATASET`.
4. IF the uploaded Dataset has duplicate or empty column names, THEN THE Upload_Handler SHALL return an error with code `INVALID_HEADER` that lists the problem column positions.
5. IF a Row has a different number of fields than the header row, THEN THE Upload_Handler SHALL return an error with code `ROW_LENGTH_MISMATCH` that includes the 1-based row number.
6. IF the uploaded file exceeds 100 MB, THEN THE Upload_Handler SHALL return an error with code `FILE_TOO_LARGE`.

### Requirement 2: Dataset-Level Metrics

**User Story:** As a data analyst, I want dataset-wide counts, so that I can understand the dataset's size and redundancy.

#### Acceptance Criteria

1. WHEN a Valid_Dataset is profiled, THE Profiler SHALL report the row count as the number of Rows, excluding the header row.
2. WHEN a Valid_Dataset is profiled, THE Profiler SHALL report the column count as the number of columns in the header row.
3. WHEN a Valid_Dataset is profiled, THE Profiler SHALL report the duplicate count as the number of Duplicate_Rows.
4. THE Profiler SHALL report a duplicate count equal to the row count minus the number of distinct Rows.
5. WHEN a Valid_Dataset with zero Rows is profiled, THE Profiler SHALL report a row count of 0 and a duplicate count of 0.

### Requirement 3: Column-Level Metrics

**User Story:** As a data analyst, I want per-column statistics, so that I can assess data quality for each field.

#### Acceptance Criteria

1. WHEN a Valid_Dataset is profiled, THE Profiler SHALL report, for each column, the null count as the number of Null_Values in that column.
2. WHEN a Valid_Dataset is profiled, THE Profiler SHALL report, for each column, the unique count as the number of distinct non-null values in that column.
3. THE Profiler SHALL report, for each column, a null count plus non-null value count equal to the row count.
4. THE Profiler SHALL report, for each column, a unique count less than or equal to the row count minus the null count.
5. WHEN a column is profiled, THE Profiler SHALL compare values for uniqueness using exact, case-sensitive string comparison after trimming leading and trailing whitespace.

### Requirement 4: Data Type Inference

**User Story:** As a data analyst, I want each column's data type inferred, so that I know how to treat the column downstream.

#### Acceptance Criteria

1. WHEN every non-null value in a column is a base-10 integer, THE Profiler SHALL report the Inferred_Type `integer`.
2. WHEN every non-null value in a column is numeric and at least one value is not an integer, THE Profiler SHALL report the Inferred_Type `float`.
3. WHEN every non-null value in a column is one of `true` or `false` (case-insensitive), THE Profiler SHALL report the Inferred_Type `boolean`.
4. WHEN every non-null value in a column is an ISO 8601 date or date-time, THE Profiler SHALL report the Inferred_Type `datetime`.
5. WHEN the non-null values in a column match none of the `integer`, `float`, `boolean`, or `datetime` types, THE Profiler SHALL report the Inferred_Type `string`.
6. WHEN every value in a column is a Null_Value, THE Profiler SHALL report the Inferred_Type `null`.
7. THE Profiler SHALL evaluate type rules in the order `null`, `boolean`, `integer`, `float`, `datetime`, `string` and report the first matching type.

### Requirement 5: Deterministic JSON Output

**User Story:** As an integrating developer, I want the profiling result in a stable JSON structure, so that I can parse, diff, and cache results reliably.

#### Acceptance Criteria

1. WHEN profiling completes, THE Profiler SHALL return a Profile_Result containing `row_count`, `column_count`, `duplicate_count`, and a `columns` array.
2. THE Profiler SHALL include, for each entry in `columns`, the fields `name`, `null_count`, `unique_count`, and `inferred_type`.
3. THE Profiler SHALL order entries in `columns` by their position in the Dataset header row.
4. THE Serializer SHALL emit object keys in a fixed documented order, with UTF-8 encoding and no environment-dependent values such as timestamps or random identifiers.
5. WHEN the same Dataset is profiled more than once, THE Serializer SHALL produce byte-identical JSON text on each run.
6. THE Parser SHALL parse Serializer output into a Profile_Result object.
7. FOR ALL valid Profile_Result objects, serializing then parsing then serializing SHALL produce byte-identical JSON text (round-trip property).
