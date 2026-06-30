"""Helpers for naming a derived table after its source.

SciStudio's display-name resolver (#1812) names an item from
``user['display_name']`` first, then ``meta.source_file``. The package leans on
that: the loader stamps both, and :meth:`LCMSFeatureTable.from_wide` carries them
forward when given ``source=``, so simple 1:1 transforms get a name for free.

Blocks that emit a *specifically named* product (the corrector matrices, the MID
/ enrichment tables, a statistics result) still want an explicit override — but
it must stay distinguishable across input files. :func:`derived_name` composes
``"<source name> · <suffix>"`` so e.g. two files' corrected tables read
``scan1_negative · Corrected`` and ``scan2_positive · Corrected`` instead of two
identical ``Corrected``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def source_label(source: Any) -> str | None:
    """The source table's user-facing name: its ``display_name`` (or ``sheet_name``),
    else the stem of its ``meta.source_file``. ``None`` when nothing is known.
    """
    user = getattr(source, "user", None) or {}
    name = user.get("display_name") or user.get("sheet_name")
    if name:
        return str(name)
    meta = getattr(source, "meta", None)
    source_file = getattr(meta, "source_file", None) if meta is not None else None
    if isinstance(source_file, str) and source_file:
        return Path(source_file).stem
    return None


def derived_name(source: Any, suffix: str) -> str:
    """Compose ``"<source name> · <suffix>"`` (or just *suffix* when the source is unnamed)."""
    base = source_label(source)
    return f"{base} · {suffix}" if base else suffix
