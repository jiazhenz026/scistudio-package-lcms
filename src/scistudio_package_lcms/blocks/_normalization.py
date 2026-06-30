"""Internal helpers for the ``Normalization`` block: reference resolution + apply.

Normalization here means *internal-standard* normalization — dividing each
feature's per-sample intensity by a reference, per sample column, to cancel
technical variation (extraction, injection volume). It is distinct from the
``Log2MeanCenter`` transform (which works *across* samples, per feature).

Four methods, all dividing each sample column by a per-column denominator:

* ``single_reference`` — one reference feature (e.g. a spiked standard like
  HEPES). Every feature ÷ that reference feature's intensity in the same sample.
* ``isotope_internal_standard`` — per metabolite, divide that compound's rows by
  one of its own isotopologue rows (the spiked labelled standard, located via
  ``isotopeLabel``); e.g. glucose ÷ ¹³C-glucose. Only the paired compounds are
  touched.
* ``total`` — each sample ÷ its column sum (total-ion normalization).
* ``median`` — each sample ÷ its column median.

The reference / internal-standard rows are dropped by default once consumed
(they are calibration signal, not data). This module is suggestion-and-apply
only: the interactive panel decides *which* reference; here we resolve and apply.
"""

from __future__ import annotations

import re
from typing import Any

#: Normalization methods, in the order the panel presents them.
METHODS = ("single_reference", "isotope_internal_standard", "total", "median")

#: Name fragments that hint a compound is a spiked internal standard, used only
#: to pre-fill the panel's reference pick (suggestion-only, never authoritative).
_STANDARD_HINTS = (
    "istd",
    "is_",
    "internal",
    "standard",
    "spike",
    "hepes",
)


def _norm_token(value: Any) -> str:
    return re.sub(r"[^0-9a-z]+", "", str(value).lower())


def suggest_reference(compounds: list[str]) -> str | None:
    """Best-effort guess of a single-reference compound from its name. Suggestion only."""
    for compound in compounds:
        token = _norm_token(compound)
        if any(hint.replace("_", "") in token for hint in _STANDARD_HINTS):
            return compound
    return None


def _reference_mask(
    frame: Any,
    reference: dict[str, Any],
    compound_column: str,
    label_column: str,
) -> Any:
    """Boolean row mask for the single reference feature.

    A reference is ``{"compound": name}`` and optionally ``{"isotopeLabel": lbl}``
    to pin one isotopologue row; without a label every row of the compound is the
    reference (their per-sample intensities are summed).
    """
    compound = reference.get("compound")
    mask = frame[compound_column].astype(str) == str(compound)
    label = reference.get("isotopeLabel")
    if label is not None and label_column in frame.columns:
        mask = mask & (frame[label_column].astype(str) == str(label))
    return mask


def apply_normalization(
    frame: Any,
    *,
    method: str,
    sample_columns: list[str],
    compound_column: str = "compound",
    label_column: str = "isotopeLabel",
    reference: dict[str, Any] | None = None,
    pairs: list[dict[str, Any]] | None = None,
    drop_reference: bool = True,
) -> Any:
    """Apply a normalization decision to a pandas frame and return the result.

    Annotation columns pass through untouched; only the sample (intensity)
    columns are divided. A zero / missing per-column denominator leaves that
    column unchanged (no divide-by-zero).
    """
    if method not in METHODS:
        raise ValueError(f"unknown normalization method {method!r}; expected one of {METHODS}")

    result = frame.copy()
    samples = [c for c in sample_columns if c in result.columns]

    if method in ("total", "median"):
        for col in samples:
            denom = result[col].sum() if method == "total" else result[col].median()
            if denom:
                result[col] = result[col] / denom
        return result

    if method == "single_reference":
        if not reference or reference.get("compound") is None:
            raise ValueError("single_reference normalization needs a reference compound")
        ref_mask = _reference_mask(result, reference, compound_column, label_column)
        if not ref_mask.any():
            raise ValueError(f"reference {reference!r} matched no rows")
        denom = result.loc[ref_mask, samples].sum(axis=0)
        for col in samples:
            value = denom.get(col)
            if value:
                result[col] = result[col] / value
        if drop_reference:
            result = result[~ref_mask]
        return result.reset_index(drop=True)

    # isotope_internal_standard
    consumed = result.index[:0]  # empty index of IS rows to drop
    for pair in pairs or []:
        compound = pair.get("compound")
        is_label = pair.get("is_label")
        if compound is None or is_label is None:
            continue
        compound_mask = result[compound_column].astype(str) == str(compound)
        is_mask = compound_mask & (result[label_column].astype(str) == str(is_label))
        target_mask = compound_mask & ~is_mask
        is_rows = result.loc[is_mask, samples]
        if is_rows.empty:
            continue
        denom = is_rows.iloc[0]
        for col in samples:
            value = denom.get(col)
            if value:
                result.loc[target_mask, col] = result.loc[target_mask, col] / value
        consumed = consumed.union(result.index[is_mask])
    if drop_reference and len(consumed):
        result = result.drop(index=consumed)
    return result.reset_index(drop=True)
