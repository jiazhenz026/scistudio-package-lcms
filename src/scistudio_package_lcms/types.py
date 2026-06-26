"""Package-owned data type for the LCMS package.

A single domain type, :class:`LCMSFeatures`, modelled directly on what an
LC-MS peak picker (El-MAVEN, MZmine, ...) exports: a wide feature/peak table.
It subclasses the core ``DataFrame`` rather than imposing a fixed column
schema, because "whatever the peak picker exports" *is* the table.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from scistudio.core.types.dataframe import DataFrame


class LCMSFeatures(DataFrame):
    """An LC-MS feature / peak table as exported by a peak-picking tool.

    Subclasses core :class:`~scistudio.core.types.dataframe.DataFrame` and holds
    the exported table verbatim: one row per detected feature (or per
    isotopologue, for an isotope-tracing experiment) and one column per sample,
    alongside the peak picker's identifying columns (``compound``, ``formula``,
    m/z, retention time, isotope label, ...).

    The package deliberately does **not** pin a fixed column schema: the columns
    are exactly those the upstream tool produced. The only domain addition over
    a bare ``DataFrame`` is the typed :class:`Meta` carrying table-level
    provenance that downstream blocks (e.g. isotope correction) rely on.
    """

    class Meta(BaseModel):
        """Table-level provenance metadata.

        Frozen so :meth:`DataFrame.with_meta` immutable updates stay sound.
        Every field is nullable: it records what is known, ``None`` when not.
        """

        model_config = ConfigDict(frozen=True)

        #: Acquisition polarity for the whole table: ``"positive"`` /
        #: ``"negative"`` (carried down so isotope correction can infer charge).
        polarity: str | None = None
        #: Peak-picking tool the table came from, e.g. ``"elmaven"``.
        source_tool: str | None = None
        #: Original file the table was loaded from.
        source_file: str | None = None
        #: Whether the table carries isotopologue rows (isotope-tracing run).
        labeled: bool | None = None


def get_types() -> list[type]:
    """Return the package's exported ``DataObject`` types for ``scistudio.types``."""
    return [LCMSFeatures]


__all__ = ["LCMSFeatures", "get_types"]
