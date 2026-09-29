---
inclusion: always
---

# Testing Standards

## Tools

- pytest for all tests; Hypothesis for property-based tests.
- FastAPI `TestClient` for integration tests.

## Structure

- `tests/unit/` - example-based tests and edge cases
- `tests/property/` - Hypothesis property tests
- `tests/integration/` - adapter tests (HTTP, CLI)
- `tests/strategies.py` - shared Hypothesis strategies
- `tests/fixtures/` - small, committed sample datasets

## Property-Based Tests

- Each correctness property in the design gets exactly one `@given` test.
- Use `@settings(max_examples=100)` or higher.
- Tag each test with `# Feature: dataset-profiling, Property N: <name>`.
- Compare against a simple reference model rather than re-implementing the same logic.
- Generators must include edge cases: empty values, whitespace, unicode, quotes, commas, newlines, near-duplicates.

## Unit Tests

- Name tests `test_<unit>_<behavior>`.
- One behavior per test; use Arrange / Act / Assert.
- Cover every error code and the documented edge cases from the requirements.

## Rules

- Tests must be deterministic: no network, no wall-clock time, no unseeded randomness.
- Do not mock `core` logic; test it directly. Mock only at I/O boundaries.
- Mark slow tests (e.g. 100 MB files) with `@pytest.mark.slow`.
- Coverage on `src/profiler/core` must be 90% or higher.
- Run tests in single-execution mode (`uv run pytest`), never watch mode.
- A task is not complete until lint, type check, and tests pass.