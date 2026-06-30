"""LCMS feature table — the package's primary data type.

A :class:`LCMSFeatureTable` is a **wide** feature table from an untargeted /
isotope-tracing LCMS run: a fixed block of per-feature *annotation* columns
(identity, m/z, retention time, isotopologue label, compound annotation)
followed by one *intensity* column per sample. It is the shape El-MAVEN's peaks
export produces and what the LCMS blocks (background subtraction, isotope
correction, flux) operate on.

This module is the package's **developer-facing reuse surface** (ADR-052 §4.2,
spec §13.1): the type an author imports to name on a port and to build. Its
standardized member set, against this package's own version line:

* ``LCMSFeatureTable`` — public at the package top level, subclasses core
  :class:`~scistudio.core.types.dataframe.DataFrame` (``stable``).
* ``LCMSFeatureTable(columns=…, row_count=…, schema=…, data=…)`` — canonical
  construction, inherited from core; the signature is not redefined
  (``stable``).
* ``LCMSFeatureTable.Meta`` — typed, frozen metadata schema carrying the
  annotation/sample column split and acquisition context (``stable``).
* ``LCMSFeatureTable.from_elmaven(…)`` — the *MUST-shape* domain-native packing
  constructor **on the type** (never a module-level builder): it takes an
  El-MAVEN peaks frame and returns a populated table (``stable``).
* ``to_memory`` / ``to_pandas`` / ``to_numpy`` / ``with_meta`` — inherited from
  core and **never shadowed** (the ergonomic accessors stay core's, spec §10).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from scistudio.core.types import DataFrame
from scistudio.stability import stable

#: The fixed El-MAVEN peaks-export annotation columns, in export order. Every
#: column to the right of ``parent`` is a per-sample intensity column.
ELMAVEN_ANNOTATION_COLUMNS = (
    "label",
    "metaGroupId",
    "groupId",
    "goodPeakCount",
    "medMz",
    "medRt",
    "maxQuality",
    "isotopeLabel",
    "compound",
    "compoundId",
    "formula",
    "expectedRtDiff",
    "ppmDiff",
    "parent",
)


@stable(since="0.1.0")
class LCMSFeatureTable(DataFrame):
    """A wide LCMS feature table: annotation columns + one intensity column per sample.

    Subclasses core :class:`~scistudio.core.types.dataframe.DataFrame`, so the
    table is Arrow/Parquet-backed and large tables load lazily. The LCMS
    semantics — which columns are feature annotation versus sample intensity,
    the acquisition polarity, whether the table carries isotopologue labels —
    travel on :class:`Meta` so downstream blocks read them without re-parsing.
    """

    @stable(since="0.1.0")
    class Meta(BaseModel):
        """Per-table typed metadata. Frozen for immutable ``with_meta`` updates."""

        model_config = ConfigDict(frozen=True)

        #: Acquisition polarity, when known.
        polarity: Literal["positive", "negative"] | None = None
        #: Source tool that produced the table (e.g. ``"El-MAVEN"``).
        software: str | None = None
        #: Whether the table carries isotopologue labels (an ``isotopeLabel``
        #: column) — the precondition for isotope correction and flux.
        labeled: bool = False
        #: The feature-annotation columns, in order.
        annotation_columns: tuple[str, ...] = ()
        #: The per-sample intensity columns, in order.
        sample_columns: tuple[str, ...] = ()

    @classmethod
    @stable(since="0.1.0")
    def from_elmaven(
        cls,
        frame: Any,
        *,
        polarity: Literal["positive", "negative"] | None = None,
        sample_columns: list[str] | None = None,
    ) -> LCMSFeatureTable:
        """Construct a table from an El-MAVEN peaks export.

        The ADR-052 §13.1 *MUST-shape* member: a domain-native packing
        constructor that lives **on the type**. It takes the author's natural
        input — a :class:`pandas.DataFrame` read from an El-MAVEN
        ``*_peaks_*.csv`` export — splits its columns into the fixed annotation
        block and the per-sample intensity block, packs the frame into the
        canonical Arrow payload, and returns a populated
        :class:`LCMSFeatureTable`. File IO stays in the loader block; the type
        only packs an in-memory frame.

        Args:
            frame: A :class:`pandas.DataFrame` of El-MAVEN peaks, with the
                annotation columns of :data:`ELMAVEN_ANNOTATION_COLUMNS`
                followed by one column per sample.
            polarity: Acquisition polarity, recorded on :class:`Meta`. El-MAVEN
                does not encode polarity in the export, so the caller supplies
                it (the reference pipeline names files ``*_negative_*`` /
                ``*_positive_*``).
            sample_columns: The sample-intensity column names. When ``None``,
                inferred as every column not in the annotation block.

        Returns:
            A :class:`LCMSFeatureTable` holding the frame, with the
            annotation/sample split, polarity, software, and label flag on
            :class:`Meta`.

        Raises:
            ValueError: if *frame* has no annotation columns (not an El-MAVEN
                peaks export) or no sample columns.
        """
        import pyarrow as pa

        columns = [str(c) for c in frame.columns]
        annotation = [c for c in ELMAVEN_ANNOTATION_COLUMNS if c in columns]
        if not annotation:
            raise ValueError(
                "frame has none of the El-MAVEN annotation columns "
                f"({', '.join(ELMAVEN_ANNOTATION_COLUMNS)}); is it a peaks export?"
            )
        if sample_columns is None:
            sample_columns = [c for c in columns if c not in annotation]
        if not sample_columns:
            raise ValueError("frame has no per-sample intensity columns")

        table = pa.Table.from_pandas(frame, preserve_index=False)
        meta = cls.Meta(
            polarity=polarity,
            software="El-MAVEN",
            labeled="isotopeLabel" in columns,
            annotation_columns=tuple(annotation),
            sample_columns=tuple(sample_columns),
        )
        return cls(
            columns=columns,
            row_count=int(frame.shape[0]),
            schema={c: str(dtype) for c, dtype in zip(columns, frame.dtypes, strict=False)},
            data=table,
            meta=meta,
        )

    @classmethod
    @stable(since="0.1.0")
    def from_wide(
        cls,
        frame: Any,
        *,
        sample_columns: list[str] | tuple[str, ...],
        polarity: Literal["positive", "negative"] | None = None,
        software: str | None = None,
        labeled: bool = False,
    ) -> LCMSFeatureTable:
        """Build a standard table from a wide frame and its known sample columns.

        The canonical reconstruction for blocks that *derive* a table (corrected,
        normalized, background-subtracted): annotation columns are inferred as
        every column that is not a sample column, and the acquisition context is
        carried on :class:`Meta`. Upstream annotation columns a step drops (for
        example m/z or retention time) are simply absent — that header loss is
        expected and allowed.

        Args:
            frame: A :class:`pandas.DataFrame` whose columns are the (possibly
                reduced) annotation columns plus the per-sample columns.
            sample_columns: The sample-intensity column names; those still
                present in *frame* become the table's ``sample_columns``.
            polarity: Acquisition polarity to record on :class:`Meta`.
            software: Producing tool / step to record on :class:`Meta`.
            labeled: Whether the table carries isotopologue labels.

        Returns:
            A standard :class:`LCMSFeatureTable`.
        """
        import pyarrow as pa

        columns = [str(c) for c in frame.columns]
        samples = [c for c in sample_columns if c in columns]
        annotation = [c for c in columns if c not in samples]
        meta = cls.Meta(
            polarity=polarity,
            software=software,
            labeled=labeled,
            annotation_columns=tuple(annotation),
            sample_columns=tuple(samples),
        )
        table = pa.Table.from_pandas(frame, preserve_index=False)
        return cls(
            columns=columns,
            row_count=int(frame.shape[0]),
            schema={c: str(dtype) for c, dtype in zip(columns, frame.dtypes, strict=False)},
            data=table,
            meta=meta,
        )


@stable(since="0.1.0")
def get_types() -> list[type]:
    """Return the package's exported ``DataObject`` types for ``scistudio.types``."""
    return [LCMSFeatureTable]


__all__ = ["ELMAVEN_ANNOTATION_COLUMNS", "LCMSFeatureTable", "get_types"]
