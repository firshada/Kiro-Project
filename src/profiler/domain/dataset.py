"""The Dataset domain type."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Dataset:
    """A validated CSV Dataset: a header plus rows of raw, untrimmed cell values.

    Raises:
        ValueError: if any row width differs from the header width. The
            Upload_Handler reports this as ROW_LENGTH_MISMATCH before a Dataset
            is built, so this guard only protects programmatic construction.
    """

    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        width = len(self.header)
        for index, row in enumerate(self.rows):
            if len(row) != width:
                raise ValueError(f"row {index} has {len(row)} cells, expected {width}")
