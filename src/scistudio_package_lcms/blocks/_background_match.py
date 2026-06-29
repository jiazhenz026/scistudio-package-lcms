"""Heuristics for matching sample columns to background columns by name.

Internal helper for the ``BackgroundSubtraction`` interactive block. The block's
panel lets the user assign each sample column a role and a background, but doing
that from scratch over ~100 columns is tedious — so this module *suggests* a
starting assignment by reading the (often messy) column names, which the user
then corrects in the GUI. It is suggestion-only: nothing here is authoritative,
so imperfect guesses are fine.

It also applies a finalized assignment (the panel's decision, or the suggestion
when running headless) to a frame: subtract each sample's aggregated background
and drop the background/ignored columns. Subtraction never clamps negatives —
the reference pipeline keeps them.
"""

from __future__ import annotations

import re
from typing import Any

# Column roles.
SAMPLE = "sample"
BACKGROUND = "background"
QC = "qc"
IGNORE = "ignore"

# Keyword sets matched against a column's lowercased name tokens. Order of the
# checks (wash/ignore -> qc -> background) resolves overlaps like "blank_wash".
_BACKGROUND_WORDS = frozenset({"blank", "blk", "bg", "bgd", "bkg", "bk", "background", "blanks"})
_QC_WORDS = frozenset({"qc", "qcs", "poolqc", "pooledqc", "qcpool"})
_IGNORE_WORDS = frozenset({"wash", "washes", "equil", "equilibration", "cond", "conditioning", "blankwash"})

_TOKEN_SPLIT = re.compile(r"[^0-9a-z]+")
_LETTER_DIGIT = re.compile(r"(?<=[a-z])(?=[0-9])|(?<=[0-9])(?=[a-z])")


def _tokens(name: str) -> list[str]:
    """Split a column name into lowercased alphanumeric tokens.

    Splits on separators *and* on letter/digit boundaries, so ``"BLANK1"`` and
    ``"bg0"`` and ``"A_9_2_B"`` all decompose into their meaningful parts.
    """
    raw = _TOKEN_SPLIT.split(name.lower())
    tokens: list[str] = []
    for part in raw:
        if not part:
            continue
        tokens.extend(t for t in _LETTER_DIGIT.split(part) if t)
    return tokens


def classify_role(name: str) -> str:
    """Best-effort role for one column name. Suggestion only."""
    toks = _tokens(name)
    token_set = set(toks)
    joined = "".join(toks)

    if token_set & _IGNORE_WORDS or "blankwash" in joined or "wash" in token_set:
        return IGNORE
    if token_set & _QC_WORDS or joined.startswith("qc") or "qc" in token_set:
        return QC
    if token_set & _BACKGROUND_WORDS or "blank" in joined or "background" in joined:
        return BACKGROUND
    # subtract_bg.R convention: a replicate index of 0 marks a background.
    if toks and toks[-1] == "0":
        return BACKGROUND
    return SAMPLE


def group_key(name: str, role: str) -> str | None:
    """Extract a batch/group token so a sample matches its group's background.

    The group is the first alphabetic token that is not a role keyword. Returns
    ``None`` when no group token is present (e.g. a global ``BLANK1``), which the
    matcher treats as applying everywhere.
    """
    role_words = _BACKGROUND_WORDS | _QC_WORDS | _IGNORE_WORDS
    for tok in _tokens(name):
        if tok.isalpha() and tok not in role_words:
            return tok.upper()
    return None


def suggest(columns: list[str]) -> dict[str, Any]:
    """Suggest roles, background groups, and per-sample background assignments.

    Returns a JSON-safe decision the panel pre-fills and ``run`` can apply
    directly when headless::

        {
          "roles":       {col: role},
          "groups":      {col: group_or_null},
          "background_groups": {group_or_"_global": [bg_col, ...]},
          "assignments": {sample_col: [bg_col, ...]},   # resolved replicate cols
          "aggregation": "median",
          "drop":        [bg_col_or_ignored_col, ...],
        }
    """
    roles = {c: classify_role(c) for c in columns}
    groups = {c: group_key(c, roles[c]) for c in columns}

    background_groups: dict[str, list[str]] = {}
    for c in columns:
        if roles[c] == BACKGROUND:
            key = groups[c] or "_global"
            background_groups.setdefault(key, []).append(c)

    global_bgs = background_groups.get("_global", [])
    only_one_group = len(background_groups) == 1
    sole_group_cols = next(iter(background_groups.values())) if only_one_group else []

    assignments: dict[str, list[str]] = {}
    for c in columns:
        if roles[c] != SAMPLE:
            continue
        grp = groups[c]
        if grp is not None and grp in background_groups:
            assignments[c] = list(background_groups[grp])
        elif global_bgs:
            assignments[c] = list(global_bgs)
        elif only_one_group:
            assignments[c] = list(sole_group_cols)
        else:
            assignments[c] = []  # unassigned — surfaced to the user

    drop = [c for c in columns if roles[c] in (BACKGROUND, IGNORE)]
    return {
        "roles": roles,
        "groups": groups,
        "background_groups": background_groups,
        "assignments": assignments,
        "aggregation": "median",
        "drop": drop,
    }


def apply_subtraction(frame: Any, decision: dict[str, Any]) -> Any:
    """Apply a finalized assignment to a pandas frame and return the result.

    For each sample column, subtract the aggregate (mean/median) of its assigned
    background replicate columns; then drop the background/ignored columns.
    Negatives are kept (the reference pipeline does not clamp).
    """
    result = frame.copy()
    aggregation = str(decision.get("aggregation") or "median")
    assignments: dict[str, list[str]] = decision.get("assignments", {})

    for sample_col, bg_cols in assignments.items():
        present = [c for c in bg_cols if c in result.columns]
        if sample_col not in result.columns or not present:
            continue
        background = result[present].median(axis=1) if aggregation == "median" else result[present].mean(axis=1)
        result[sample_col] = result[sample_col] - background

    drop = [c for c in decision.get("drop", []) if c in result.columns]
    if drop:
        result = result.drop(columns=drop)
    return result
