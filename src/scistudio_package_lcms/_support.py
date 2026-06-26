"""Shared data-model plumbing for the LCMS package (internal).

Every block builds, reads, and derives :class:`LCMSFeatures` values through
these helpers so the storage model stays consistent across the package.
Implementers MUST NOT touch ``_transient_data`` / ``storage_ref`` directly.

Storage model: an :class:`LCMSFeatures` payload is a wide ``pyarrow.Table``
(one row per feature / isotopologue, one column per sample plus the peak
picker's identifying columns). In-memory tables carry it on the transient
slot; persisted tables read it back through ``to_memory()``.

This module depends only on ``pandas`` + ``pyarrow`` (both core dependencies).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import pandas as pd
import pyarrow as pa
from scistudio.core.types.base import DataObject, FrameworkMeta
from scistudio.core.types.collection import Collection

from scistudio_package_lcms.types import LCMSFeatures

PACKAGE_SOURCE = "scistudio-package-lcms"


# ---------------------------------------------------------------------------
# Arrow plumbing
# ---------------------------------------------------------------------------


def _to_arrow(data: Any) -> pa.Table:
    """Coerce a table-like payload (Arrow / pandas / column mapping) to Arrow."""
    if isinstance(data, pa.Table):
        return data
    if isinstance(data, pd.DataFrame):
        return pa.Table.from_pandas(data, preserve_index=False)
    if isinstance(data, Mapping):
        return pa.table({str(name): pa.array(values) for name, values in data.items()})
    raise TypeError(f"Cannot build an LCMSFeatures table from {type(data).__name__}")


# ---------------------------------------------------------------------------
# LCMSFeatures build / read / derive
# ---------------------------------------------------------------------------


def build_features(
    data: pa.Table | pd.DataFrame | Mapping[str, Any],
    *,
    meta: LCMSFeatures.Meta | None = None,
    user: dict[str, Any] | None = None,
    framework: FrameworkMeta | None = None,
    source: str | None = None,
) -> LCMSFeatures:
    """Construct a fresh :class:`LCMSFeatures` from a table-like payload."""
    table = _to_arrow(data)
    return LCMSFeatures(
        columns=list(table.column_names),
        row_count=table.num_rows,
        data=table,
        meta=meta,
        user=dict(user) if user else None,
        framework=framework or FrameworkMeta(source=source or PACKAGE_SOURCE),
    )


def features_table(features: LCMSFeatures) -> pa.Table:
    """Return the backing wide ``pyarrow.Table`` of an :class:`LCMSFeatures`."""
    payload = features.to_memory() if features.storage_ref is not None else features._transient_data
    if payload is None:
        raise ValueError("LCMSFeatures has no in-memory or persisted payload.")
    if isinstance(payload, pa.Table):
        return payload
    if isinstance(payload, pd.DataFrame):
        return pa.Table.from_pandas(payload, preserve_index=False)
    return pa.table(payload)


def features_pandas(features: LCMSFeatures) -> pd.DataFrame:
    """Return the backing payload of an :class:`LCMSFeatures` as a pandas frame."""
    return features_table(features).to_pandas()


def derive_features(
    source: LCMSFeatures,
    data: pa.Table | pd.DataFrame | Mapping[str, Any],
    *,
    meta: LCMSFeatures.Meta | None = None,
    meta_changes: Mapping[str, Any] | None = None,
) -> LCMSFeatures:
    """Derive a new :class:`LCMSFeatures` from ``source``, preserving lineage.

    Reuses ``source`` metadata and user dict unless overridden, and derives a
    fresh framework so provenance (``derived_from``) is recorded.
    """
    table = _to_arrow(data)
    resolved_meta = meta if meta is not None else source.meta
    if resolved_meta is not None and meta_changes:
        from scistudio.core.meta import with_meta_changes

        resolved_meta = cast(LCMSFeatures.Meta, with_meta_changes(resolved_meta, **dict(meta_changes)))
    return LCMSFeatures(
        columns=list(table.column_names),
        row_count=table.num_rows,
        data=table,
        meta=resolved_meta,
        user=dict(source.user) if source.user else None,
        framework=source.framework.derive(),
    )


# ---------------------------------------------------------------------------
# Collection / coercion helpers
# ---------------------------------------------------------------------------


def coerce_features(value: Any, *, block: str = "block", port: str = "features") -> LCMSFeatures:
    """Normalise a port value to one :class:`LCMSFeatures`.

    Accepts a bare :class:`LCMSFeatures` or a single-item ``Collection``. Raises
    ``ValueError`` with a block-qualified message otherwise.
    """
    if value is None:
        raise ValueError(f"{block}: missing required '{port}' input")
    if isinstance(value, LCMSFeatures):
        return value
    if isinstance(value, Collection):
        items = list(value)
        if len(items) == 1 and isinstance(items[0], LCMSFeatures):
            return cast(LCMSFeatures, items[0])
    raise ValueError(f"{block}: '{port}' expected LCMSFeatures, got {type(value).__name__}")


def features_collection(features: LCMSFeatures) -> Collection:
    """Wrap one :class:`LCMSFeatures` in a ``Collection`` for an output port."""
    return Collection(items=cast(list[DataObject], [features]), item_type=LCMSFeatures)


__all__ = [
    "PACKAGE_SOURCE",
    "build_features",
    "coerce_features",
    "derive_features",
    "features_collection",
    "features_pandas",
    "features_table",
]
