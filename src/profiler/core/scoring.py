"""Scorer: four quality dimensions and the 0-100 score (Req 5).

Formula (all ratios exact, rounded once for output):

    completeness = non_null_cells / total_cells
    uniqueness   = unique_records / total_records
    validity     = sum(evaluated - failed) / sum(evaluated)   over validity rules, PASS/FAIL
    consistency  = cells matching their column's Dominant_Type / non_null_cells
    score        = weighted mean of the four, WEIGHTS below

A zero denominator yields 1 (100%).
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from profiler.core.percent import ratio, to_percentage
from profiler.core.profiling import column_cells, is_null
from profiler.core.type_inference import infer_type, value_type
from profiler.domain import Dataset, Dimensions, DuplicateResult, RuleResult, ValueType

WEIGHTS: dict[str, Fraction] = {
    "completeness": Fraction(1, 4),
    "uniqueness": Fraction(1, 4),
    "validity": Fraction(1, 4),
    "consistency": Fraction(1, 4),
}

_TYPE_ORDER: tuple[ValueType, ...] = ("boolean", "integer", "float", "datetime", "string")
_ONE = Fraction(1)


@dataclass(frozen=True)
class ExactDimensions:
    """Unrounded dimension ratios in [0, 1]."""

    completeness: Fraction
    uniqueness: Fraction
    validity: Fraction
    consistency: Fraction

    def score(self) -> Fraction:
        """Weighted mean of the dimensions (Req 5.3)."""
        return sum(
            (WEIGHTS[name] * getattr(self, name) for name in WEIGHTS),
            start=Fraction(0),
        )

    def rounded(self) -> Dimensions:
        """Dimensions as Percentages."""
        return Dimensions(
            completeness=to_percentage(self.completeness),
            uniqueness=to_percentage(self.uniqueness),
            validity=to_percentage(self.validity),
            consistency=to_percentage(self.consistency),
        )


def compute_dimensions(
    dataset: Dataset, rules: Sequence[RuleResult], duplicates: DuplicateResult
) -> ExactDimensions:
    """Compute the exact dimensions (Req 5.1, 5.2)."""
    total_cells = len(dataset.rows) * len(dataset.header)
    non_null = sum(1 for row in dataset.rows for cell in row if not is_null(cell))

    validity_rules = [r for r in rules if r.kind == "validity" and r.status != "SKIPPED"]
    evaluated = sum(r.evaluated_count for r in validity_rules)
    failed = sum(r.failed_count for r in validity_rules)

    consistent = sum(
        _consistent_cells(column_cells(dataset, i)) for i in range(len(dataset.header))
    )
    return ExactDimensions(
        completeness=ratio(non_null, total_cells, empty=_ONE),
        uniqueness=ratio(duplicates.unique_records, duplicates.total_records, empty=_ONE),
        validity=ratio(evaluated - failed, evaluated, empty=_ONE),
        consistency=ratio(consistent, non_null, empty=_ONE),
    )


def _consistent_cells(cells: tuple[str, ...]) -> int:
    """Count non-null cells whose Value_Type equals the column's Dominant_Type."""
    present = [cell.strip() for cell in cells if not is_null(cell)]
    if not present:
        return 0
    widen = infer_type(cells) == "float"
    types = Counter(
        "float" if widen and t == "integer" else t for t in (value_type(v) for v in present)
    )
    dominant = max(_TYPE_ORDER, key=lambda t: (types[t], -_TYPE_ORDER.index(t)))
    return types[dominant]
