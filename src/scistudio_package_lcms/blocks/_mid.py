"""Mass isotopologue distribution (MID) and ¹³C enrichment for ``CalculateMID``.

Given a labelled feature table (one isotopologue *row* per compound — ``C12
PARENT``, ``C13-label-1`` …), for each compound and sample:

* **MID** — the isotopologue intensities normalized to sum to 1 (the M+0 / M+1 /
  … fractional distribution).
* **¹³C enrichment** — the average labelling, ``Σ(i · MID_i) / (n − 1)`` over the
  ``n`` isotopologues (index ``i`` in label order), a single number in ``[0, 1]``
  per compound per sample (the reference notebook's formula).

MID keeps the input's isotopologue-row shape (a feature table of fractions);
enrichment collapses to one row per compound (a feature table of scalars).
"""

from __future__ import annotations

import re
from typing import Any

_COMPOUND_COLUMN = "compound"
_LABEL_COLUMN = "isotopeLabel"


def _label_index(label: Any) -> int:
    """Isotopologue index from a label: ``C12 PARENT`` → 0, ``C13-label-3`` → 3."""
    text = str(label)
    if "parent" in text.lower():
        return 0
    digits = re.findall(r"\d+", text)
    return int(digits[-1]) if digits else 0


def compute_mid_and_enrichment(
    frame: Any,
    *,
    sample_columns: list[str],
    compound_column: str = _COMPOUND_COLUMN,
    label_column: str = _LABEL_COLUMN,
) -> tuple[Any, Any]:
    """Return ``(mid_frame, enrichment_frame)`` for a labelled feature table.

    ``mid_frame`` is *frame* with its sample columns replaced by per-compound,
    per-sample MID fractions. ``enrichment_frame`` has one row per compound with
    a ¹³C-enrichment value per sample column.
    """
    import numpy as np
    import pandas as pd

    samples = [c for c in sample_columns if c in frame.columns]
    mid = frame.copy()
    if label_column in frame.columns:
        index_of = frame[label_column].map(_label_index)
    else:
        index_of = pd.Series(0, index=frame.index)

    enrichment_rows: list[dict[str, Any]] = []
    for compound, sub in frame.groupby(compound_column, sort=False):
        order = index_of.loc[sub.index].sort_values().index
        record: dict[str, Any] = {compound_column: compound}
        for col in samples:
            values = pd.to_numeric(sub.loc[order, col], errors="coerce").to_numpy(dtype=float)
            total = np.nansum(values)
            fractions = values / total if total > 0 else np.zeros_like(values)
            mid.loc[order, col] = fractions
            n = len(fractions)
            if n > 1:
                indices = np.arange(n)
                record[col] = float(np.nansum(indices * fractions) / (n - 1))
            else:
                record[col] = 0.0
        enrichment_rows.append(record)

    enrichment = pd.DataFrame.from_records(enrichment_rows)
    return mid, enrichment
