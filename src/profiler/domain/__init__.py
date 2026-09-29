"""Immutable domain types for Scrubby."""

from profiler.domain.dataset import Dataset
from profiler.domain.errors import ErrorCode, RulesError, ValidationError
from profiler.domain.report import (
    MAX_LISTED_ROWS,
    ColumnProfile,
    Dimensions,
    DuplicateResult,
    FileError,
    FileResult,
    InferredType,
    QualityReport,
    RuleResult,
    Summary,
)
from profiler.domain.rules import Rule, RuleSet, ValueType

__all__ = [
    "MAX_LISTED_ROWS",
    "ColumnProfile",
    "Dataset",
    "Dimensions",
    "DuplicateResult",
    "ErrorCode",
    "FileError",
    "FileResult",
    "InferredType",
    "QualityReport",
    "Rule",
    "RuleResult",
    "RuleSet",
    "RulesError",
    "Summary",
    "ValidationError",
    "ValueType",
]
