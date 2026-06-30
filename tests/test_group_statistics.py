"""Tests for GroupStatistics: grouping heuristic, BH, the tests, and the block."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from scistudio.blocks.base import INTERACTIVE_RESPONSE_KEY, BlockConfig
from scistudio.core.types import Collection

from scistudio_blocks_lcms.blocks import GroupStatistics
from scistudio_blocks_lcms.blocks._group_stats import (
    benjamini_hochberg,
    compute_stats,
    split_group_replicate,
    suggest_groups,
)
from scistudio_blocks_lcms.types import LCMSFeatureTable

_SAMPLES = ["A1", "A2", "A3", "B1", "B2", "B3"]


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "compound": ["X", "Y"],
            "A1": [10.0, 5.0],
            "A2": [11.0, 5.0],
            "A3": [12.0, 5.0],
            "B1": [20.0, 5.0],
            "B2": [21.0, 5.0],
            "B3": [22.0, 6.0],
        }
    )


def test_split_and_suggest_groups() -> None:
    assert split_group_replicate("UL1") == ("UL", 1)
    assert split_group_replicate("D2_L") == ("D2_L", None)
    assert split_group_replicate("Acute_12") == ("Acute", 12)
    assert suggest_groups(["A1", "A2", "B1"]) == {"A1": "A", "A2": "A", "B1": "B"}


def test_benjamini_hochberg() -> None:
    assert benjamini_hochberg([0.01, 0.02, 0.03, 0.04]) == pytest.approx([0.04, 0.04, 0.04, 0.04])
    # NaN p-values stay NaN
    out = benjamini_hochberg([0.01, float("nan")])
    assert out[0] == pytest.approx(0.01) and out[1] != out[1]


def test_ttest_flags_the_changed_feature() -> None:
    result = compute_stats(
        _frame(),
        sample_columns=_SAMPLES,
        groups=suggest_groups(_SAMPLES),
        annotation_columns=["compound"],
        test="ttest",
        pair=("A", "B"),
    )
    row_x = result[result["compound"] == "X"].iloc[0]
    row_y = result[result["compound"] == "Y"].iloc[0]
    assert row_x["mean_A"] == pytest.approx(11.0) and row_x["mean_B"] == pytest.approx(21.0)
    assert row_x["diff"] == pytest.approx(-10.0)
    assert bool(row_x["significant"]) is True
    assert bool(row_y["significant"]) is False


def test_anova_and_linear_trend() -> None:
    frame = pd.DataFrame(
        {"compound": ["Z"], "A1": [1.0], "A2": [2.0], "B1": [3.0], "B2": [4.0], "C1": [5.0], "C2": [6.0]}
    )
    cols = ["A1", "A2", "B1", "B2", "C1", "C2"]
    groups = suggest_groups(cols)

    anova = compute_stats(frame, sample_columns=cols, groups=groups, annotation_columns=["compound"], test="anova")
    assert anova.iloc[0]["p_value"] < 0.05

    trend = compute_stats(
        frame,
        sample_columns=cols,
        groups=groups,
        annotation_columns=["compound"],
        test="linear_trend",
        levels={"A": 1, "B": 2, "C": 3},
    )
    assert trend.iloc[0]["estimate"] == pytest.approx(2.0, abs=0.3)  # ~+2 per level
    assert trend.iloc[0]["p_value"] < 0.05


def _persisted(tmp_path: Path) -> LCMSFeatureTable:
    table = LCMSFeatureTable.from_elmaven(_frame(), polarity="negative", sample_columns=_SAMPLES)
    table.save(tmp_path / "in.parquet")
    return table


def test_block_headless_runs_default_ttest(tmp_path: Path) -> None:
    table = _persisted(tmp_path)
    out = GroupStatistics().run({"features": Collection([table])}, BlockConfig(params={"test": "anova"}))
    stats = out["statistics"]
    assert stats.length == 1
    result = stats[0]
    result.save(tmp_path / "stats.parquet")
    frame = result.to_pandas()
    assert {"compound", "mean_A", "mean_B", "statistic", "p_value", "p_adj", "significant"} <= set(frame.columns)


def test_block_uses_panel_decision(tmp_path: Path) -> None:
    table = _persisted(tmp_path)
    response = {
        "test": "ttest",
        "fdr": "bh",
        "tables": [{"groups": {c: c[0] for c in _SAMPLES}, "pair": ["A", "B"]}],
    }
    out = GroupStatistics().run(
        {"features": Collection([table])}, BlockConfig(params={INTERACTIVE_RESPONSE_KEY: response})
    )
    result = out["statistics"][0]
    result.save(tmp_path / "stats.parquet")
    frame = result.to_pandas()
    assert "diff" in frame.columns
    assert bool(frame[frame["compound"] == "X"].iloc[0]["significant"]) is True
