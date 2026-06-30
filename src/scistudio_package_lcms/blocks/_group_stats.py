"""Group-assignment heuristic and per-feature statistics for ``GroupStatistics``.

Sample columns are assigned to experimental *groups*; then, per feature (row),
the per-group sample values are compared by a chosen test:

* ``ttest`` — Welch's two-sample t-test between two groups (unequal variance).
* ``anova`` — one-way ANOVA across all groups.
* ``linear_trend`` — linear regression of intensity on an ordered numeric level
  per group (e.g. a stiffness / dose gradient); the slope is the effect.

P-values across features are corrected for multiple testing (Benjamini-Hochberg
by default). The group assignment is pre-filled by stripping a trailing
replicate index from the column name (``UL1``/``UL2`` -> ``UL``) — suggestion
only; the panel lets the user correct it.
"""

from __future__ import annotations

import re
from typing import Any

#: Supported tests, in the order the panel presents them.
TESTS = ("ttest", "anova", "linear_trend")
#: Supported multiple-testing corrections.
FDR_METHODS = ("bh", "bonferroni", "none")

_REPLICATE = re.compile(r"^(.*?)[ _\-.]*(\d+)\s*$")


def split_group_replicate(name: str) -> tuple[str, int | None]:
    """Split a sample name into ``(group, replicate)`` (``UL1`` -> ``("UL", 1)``)."""
    match = _REPLICATE.match(str(name))
    if match and match.group(1).strip(" _-."):
        return match.group(1).rstrip(" _-."), int(match.group(2))
    return str(name), None


def suggest_groups(columns: list[str]) -> dict[str, str]:
    """Suggest a ``column -> group`` map by stripping the replicate index. Suggestion only."""
    return {c: (split_group_replicate(c)[0] or str(c)) for c in columns}


def benjamini_hochberg(pvalues: list[float]) -> list[float]:
    """Benjamini-Hochberg FDR-adjusted p-values; NaNs (untested features) stay NaN."""
    import numpy as np

    p = np.asarray(pvalues, dtype=float)
    adjusted = np.full(p.shape, np.nan)
    valid = ~np.isnan(p)
    m = int(valid.sum())
    if m == 0:
        return adjusted.tolist()
    pv = p[valid]
    order = np.argsort(pv)
    ranks = np.arange(1, m + 1)
    adj_sorted = pv[order] * m / ranks
    adj_sorted = np.minimum.accumulate(adj_sorted[::-1])[::-1]
    adj_sorted = np.clip(adj_sorted, 0.0, 1.0)
    out = np.empty(m)
    out[order] = adj_sorted
    adjusted[valid] = out
    return adjusted.tolist()


def _grouped_columns(sample_columns: list[str], groups: dict[str, str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for col in sample_columns:
        group = groups.get(col)
        if group is None or group == "":
            continue
        grouped.setdefault(str(group), []).append(col)
    return grouped


def compute_stats(
    frame: Any,
    *,
    sample_columns: list[str],
    groups: dict[str, str],
    annotation_columns: list[str],
    test: str = "ttest",
    pair: tuple[str, str] | None = None,
    levels: dict[str, float] | None = None,
    fdr: str = "bh",
    alpha: float = 0.05,
) -> Any:
    """Compute per-feature group statistics and return a tidy result frame."""
    import numpy as np
    import pandas as pd
    from scipy import stats

    if test not in TESTS:
        raise ValueError(f"unknown test {test!r}; expected one of {TESTS}")

    cols = [c for c in sample_columns if c in frame.columns]
    grouped = _grouped_columns(cols, groups)
    group_names = list(grouped)
    anno = [c for c in annotation_columns if c in frame.columns]

    def _values(row: Any, columns: list[str]) -> Any:
        series = pd.to_numeric(pd.Series([row[c] for c in columns]), errors="coerce").dropna()
        return series.to_numpy()

    records: list[dict[str, Any]] = []
    pvalues: list[float] = []
    for _, row in frame.iterrows():
        record: dict[str, Any] = {a: row[a] for a in anno}
        data = {g: _values(row, gc) for g, gc in grouped.items()}
        for g in group_names:
            record[f"mean_{g}"] = float(np.mean(data[g])) if data[g].size else np.nan

        statistic = np.nan
        p_value = np.nan
        if test == "ttest":
            a_name, b_name = pair if pair else (group_names + [None, None])[:2]
            a = data.get(a_name, np.array([])) if a_name else np.array([])
            b = data.get(b_name, np.array([])) if b_name else np.array([])
            if a.size >= 2 and b.size >= 2:
                t_stat, p_value = stats.ttest_ind(a, b, equal_var=False)
                statistic = float(t_stat)
            record["diff"] = (float(np.mean(a)) if a.size else np.nan) - (float(np.mean(b)) if b.size else np.nan)
        elif test == "anova":
            samples = [data[g] for g in group_names if data[g].size >= 2]
            if len(samples) >= 2:
                f_stat, p_value = stats.f_oneway(*samples)
                statistic = float(f_stat)
        else:  # linear_trend
            xs: list[float] = []
            ys: list[float] = []
            for g, gc in grouped.items():
                level = (levels or {}).get(g)
                if level is None:
                    continue
                for c in gc:
                    value = row[c]
                    if pd.notna(value):
                        xs.append(float(level))
                        ys.append(float(value))
            if len(set(xs)) >= 2 and len(xs) >= 3:
                fit = stats.linregress(xs, ys)
                statistic = float(fit.slope)
                p_value = float(fit.pvalue)
            record["estimate"] = statistic

        record["statistic"] = statistic
        record["p_value"] = float(p_value) if p_value == p_value else np.nan  # NaN-safe
        records.append(record)
        pvalues.append(record["p_value"])

    result = pd.DataFrame.from_records(records)
    if fdr == "bh":
        result["p_adj"] = benjamini_hochberg(pvalues)
    elif fdr == "bonferroni":
        m = int(np.sum(~np.isnan(pvalues)))
        result["p_adj"] = np.clip(np.asarray(pvalues, dtype=float) * max(m, 1), 0.0, 1.0)
    else:
        result["p_adj"] = pvalues
    result["significant"] = result["p_adj"] < alpha
    return result
