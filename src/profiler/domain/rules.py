"""Rule_Set models (Req 3.1-3.3).

A rule is either a bare name (``"not_null"``) or an object with a ``name``
discriminator and parameters. Bare names are normalized before validation.
"""

import re
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ValueType = Literal["boolean", "integer", "float", "datetime", "string"]
RuleKind = Literal["completeness", "uniqueness", "validity"]

MAX_PATTERN_LENGTH = 200

_MODEL = ConfigDict(extra="forbid", frozen=True)


class NotNullRule(BaseModel):
    model_config = _MODEL
    name: Literal["not_null"]


class UniqueRule(BaseModel):
    model_config = _MODEL
    name: Literal["unique"]


class ValidEmailRule(BaseModel):
    model_config = _MODEL
    name: Literal["valid_email"]


class RegexRule(BaseModel):
    model_config = _MODEL
    name: Literal["regex"]
    pattern: str = Field(min_length=1, max_length=MAX_PATTERN_LENGTH)

    @field_validator("pattern")
    @classmethod
    def _compiles(cls, value: str) -> str:
        try:
            re.compile(value)
        except re.error as exc:
            raise ValueError(f"pattern does not compile: {exc}") from exc
        return value


class InRangeRule(BaseModel):
    model_config = _MODEL
    name: Literal["in_range"]
    min: Decimal | None = Field(default=None, allow_inf_nan=False)
    max: Decimal | None = Field(default=None, allow_inf_nan=False)

    @model_validator(mode="after")
    def _bounds(self) -> "InRangeRule":
        if self.min is None and self.max is None:
            raise ValueError("at least one of min or max is required")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("min must not be greater than max")
        return self


class AcceptedValuesRule(BaseModel):
    model_config = _MODEL
    name: Literal["accepted_values"]
    values: tuple[str, ...] = Field(min_length=1)


class TypeIsRule(BaseModel):
    model_config = _MODEL
    name: Literal["type_is"]
    type: ValueType


Rule = Annotated[
    NotNullRule
    | UniqueRule
    | ValidEmailRule
    | RegexRule
    | InRangeRule
    | AcceptedValuesRule
    | TypeIsRule,
    Field(discriminator="name"),
]


class ColumnRules(BaseModel):
    model_config = _MODEL
    column: str
    rules: tuple[Rule, ...] = Field(min_length=1)


class RuleSet(BaseModel):
    model_config = _MODEL
    business_key: tuple[str, ...] | None = Field(default=None, min_length=1)
    columns: tuple[ColumnRules, ...] = ()


def rule_kind(rule: Rule) -> RuleKind:
    """Classify a rule for scoring (Req 3.4)."""
    if isinstance(rule, NotNullRule):
        return "completeness"
    if isinstance(rule, UniqueRule):
        return "uniqueness"
    return "validity"


def rule_params(rule: Rule) -> dict[str, object]:
    """Return ``{"name": ..., <params>}`` in declaration order, JSON-ready."""
    data: dict[str, object] = {"name": rule.name}
    if isinstance(rule, RegexRule):
        data["pattern"] = rule.pattern
    elif isinstance(rule, InRangeRule):
        if rule.min is not None:
            data["min"] = _number(rule.min)
        if rule.max is not None:
            data["max"] = _number(rule.max)
    elif isinstance(rule, AcceptedValuesRule):
        data["values"] = list(rule.values)
    elif isinstance(rule, TypeIsRule):
        data["type"] = rule.type
    return data


def _number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral_value() else float(value)
