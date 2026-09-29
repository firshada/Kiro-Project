"""Shared Hypothesis strategies for Scrubby tests."""

from hypothesis import strategies as st

from profiler.domain import Dataset, Rule, RuleSet, ValueType
from profiler.domain.rules import (
    AcceptedValuesRule,
    ColumnRules,
    InRangeRule,
    NotNullRule,
    RegexRule,
    TypeIsRule,
    UniqueRule,
    ValidEmailRule,
)

# Edge-case cells from the testing standards (empty, whitespace, unicode, quotes,
# commas, newlines, case/padding near-misses) plus typed values and near-misses.
EDGE_CELLS: tuple[str, ...] = (
    "",
    " ",
    "\t",
    "  \n ",
    '"',
    '""',
    ",",
    "a,b",
    "line\nbreak",
    "\r\n",
    "abc",
    "Abc",
    " abc",
    "abc ",
    "NA",
    "null",
    "é",
    "日本",
    "🙂",
    "<b>&'\"",
    "0",
    "7",
    " -12 ",
    "+3",
    "2.5",
    "1e3",
    ".5",
    "NaN",
    "Infinity",
    "0x1F",
    "1,000",
    "true",
    "FALSE",
    "yes",
    "2024-02-29",
    "2023-02-30",
    "2024-13-01",
    "2024-03-01T10:30:00Z",
    "a@example.com",
    "not-an-email@",
)

cells: st.SearchStrategy[str] = st.one_of(st.sampled_from(EDGE_CELLS), st.text(max_size=8))

non_null_cells: st.SearchStrategy[str] = cells.filter(lambda c: c.strip() != "")

names: st.SearchStrategy[str] = st.one_of(
    st.sampled_from(("id", "email", "Email_Address", "amount", "<script>", "a&b", 'q"')),
    st.text(min_size=1, max_size=6),
).filter(lambda n: n.strip() != "")

headers: st.SearchStrategy[tuple[str, ...]] = st.lists(
    names, min_size=1, max_size=5, unique=True
).map(tuple)


def _near_duplicate(row: tuple[str, ...], draw: st.DrawFn) -> tuple[str, ...]:
    """Return an exact copy of ``row`` or a copy differing only in case/padding."""
    mutation = draw(st.sampled_from(("exact", "upper", "pad")))
    if mutation == "exact" or not row:
        return row
    index = draw(st.integers(min_value=0, max_value=len(row) - 1))
    cell = row[index]
    changed = cell.swapcase() if mutation == "upper" else f" {cell}"
    return row[:index] + (changed,) + row[index + 1 :]


@st.composite
def datasets(draw: st.DrawFn, min_rows: int = 0, max_rows: int = 12) -> Dataset:
    """Generate valid Datasets, biased towards exact and near-duplicate rows."""
    header = draw(headers)
    row = st.tuples(*([cells] * len(header)))
    base = draw(st.lists(row, min_size=min_rows, max_size=max_rows))
    rows = list(base)
    if base:
        for _ in range(draw(st.integers(min_value=0, max_value=4))):
            source = draw(st.sampled_from(base))
            rows.insert(
                draw(st.integers(min_value=0, max_value=len(rows))), _near_duplicate(source, draw)
            )
    return Dataset(header=header, rows=tuple(rows))


def complete_rows(width: int) -> st.SearchStrategy[tuple[str, ...]]:
    """Generate a row of ``width`` non-null cells."""
    return st.tuples(*([non_null_cells] * width))


VALUE_TYPES: tuple[ValueType, ...] = ("boolean", "integer", "float", "datetime", "string")

_bounds = st.decimals(min_value=-100, max_value=100, allow_nan=False, places=1)


@st.composite
def _in_range(draw: st.DrawFn) -> InRangeRule:
    low = draw(st.none() | _bounds)
    high = draw(st.none() | _bounds) if low is not None else draw(_bounds)
    if low is not None and high is not None and low > high:
        low, high = high, low
    return InRangeRule(name="in_range", min=low, max=high)


rules: st.SearchStrategy[Rule] = st.one_of(
    st.just(NotNullRule(name="not_null")),
    st.just(UniqueRule(name="unique")),
    st.just(ValidEmailRule(name="valid_email")),
    st.sampled_from((r"[a-z]+", r"\d+", r".*", r"[A-Z].*")).map(
        lambda p: RegexRule(name="regex", pattern=p)
    ),
    _in_range(),
    st.lists(st.sampled_from(("abc", "7", "true", "é", "<b>&'\"")), min_size=1, max_size=3).map(
        lambda v: AcceptedValuesRule(name="accepted_values", values=tuple(v))
    ),
    st.sampled_from(VALUE_TYPES).map(lambda t: TypeIsRule(name="type_is", type=t)),
)


@st.composite
def rule_sets(draw: st.DrawFn, header: tuple[str, ...]) -> RuleSet:
    """Rule_Sets over ``header``, sometimes naming a missing column or using a business key."""
    column_names = st.sampled_from((*header, "missing_col"))
    entries = draw(
        st.lists(
            st.builds(
                lambda c, r: ColumnRules(column=c, rules=tuple(r)),
                column_names,
                st.lists(rules, min_size=1, max_size=3),
            ),
            max_size=4,
        )
    )
    key = draw(st.none() | st.lists(column_names, min_size=1, max_size=2, unique=True).map(tuple))
    return RuleSet(business_key=key, columns=tuple(entries))
