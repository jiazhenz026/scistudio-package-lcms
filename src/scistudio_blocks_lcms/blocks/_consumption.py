"""Reference-group consumption / release for ``ConsumptionRelease``.

For each feature, every (non-reference) sample is compared against a *reference*
group — typically fresh / unspent medium or a ``t0`` sample. The difference

    delta = sample - mean(reference group)

is negative when the cells *consumed* the metabolite (the spent sample is lower
than fresh) and positive when they *released* it (matching the reference
pipeline's "consumption negative, release positive" convention).

When per-sample cell numbers and a time interval Δt are supplied, the difference
is divided by ``cell_number × Δt`` to give a per-cell-per-time *rate*; otherwise
the raw difference is returned. The reference group is pre-filled by a name
heuristic (fresh / media / control / t0 …) — suggestion only.
"""

from __future__ import annotations

import re
from typing import Any

_REFERENCE_HINTS = (
    "fresh",
    "media",
    "medium",
    "blank",
    "control",
    "ctrl",
    "ref",
    "unspent",
    "t0",
    "d0",
    "day0",
)


def _norm(value: Any) -> str:
    return re.sub(r"[^0-9a-z]+", "", str(value).lower())


def suggest_reference_group(group_names: list[str]) -> str | None:
    """Best-effort guess of the reference group from its name. Suggestion only."""
    for group in group_names:
        token = _norm(group)
        if any(hint in token for hint in _REFERENCE_HINTS):
            return group
    return None


def compute_consumption(
    frame: Any,
    *,
    sample_columns: list[str],
    groups: dict[str, str],
    reference_group: str,
    annotation_columns: list[str],
    cell_numbers: dict[str, float] | None = None,
    dt: float = 1.0,
) -> Any:
    """Return a frame of per-sample consumption / release (or rate) per feature."""
    import pandas as pd

    cols = [c for c in sample_columns if c in frame.columns]
    ref_cols = [c for c in cols if str(groups.get(c)) == str(reference_group)]
    if not ref_cols:
        raise ValueError(f"reference group {reference_group!r} matched no sample columns")
    target_cols = [c for c in cols if c not in ref_cols and groups.get(c)]

    anno = [c for c in annotation_columns if c in frame.columns]
    result = frame[anno].copy()
    reference_mean = frame[ref_cols].apply(pd.to_numeric, errors="coerce").mean(axis=1)

    scale = bool(cell_numbers) and dt
    for col in target_cols:
        delta = pd.to_numeric(frame[col], errors="coerce") - reference_mean
        if scale:
            denom = (cell_numbers or {}).get(col)
            if denom:
                delta = delta / (float(denom) * float(dt))
        result[col] = delta
    return result
