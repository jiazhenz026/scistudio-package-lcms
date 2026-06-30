"""Tests for ConsumptionRelease: the difference/rate maths and the block."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from scistudio.blocks.base import INTERACTIVE_RESPONSE_KEY, BlockConfig
from scistudio.core.types import Collection

from scistudio_blocks_lcms.blocks import ConsumptionRelease
from scistudio_blocks_lcms.blocks._consumption import compute_consumption, suggest_reference_group
from scistudio_blocks_lcms.blocks._group_stats import suggest_groups
from scistudio_blocks_lcms.blocks._results import dataframe_from_pandas
from scistudio_blocks_lcms.types import LCMSFeatureTable

_SAMPLES = ["fresh1", "fresh2", "spent1", "spent2"]


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "compound": ["X", "Y"],
            "fresh1": [100.0, 10.0],
            "fresh2": [100.0, 10.0],
            "spent1": [60.0, 30.0],
            "spent2": [40.0, 50.0],
        }
    )


def test_suggest_reference_group() -> None:
    assert suggest_reference_group(["Acute", "fresh_media", "Chronic"]) == "fresh_media"
    assert suggest_reference_group(["A", "B"]) is None


def test_consumption_negative_release_positive() -> None:
    out = compute_consumption(
        _frame(),
        sample_columns=_SAMPLES,
        groups=suggest_groups(_SAMPLES),
        reference_group="fresh",
        annotation_columns=["compound"],
    )
    assert list(out.columns) == ["compound", "spent1", "spent2"]  # reference cols dropped
    row_x = out[out["compound"] == "X"].iloc[0]
    assert row_x["spent1"] == pytest.approx(-40.0) and row_x["spent2"] == pytest.approx(-60.0)  # consumed
    row_y = out[out["compound"] == "Y"].iloc[0]
    assert row_y["spent1"] == pytest.approx(20.0) and row_y["spent2"] == pytest.approx(40.0)  # released


def test_rate_scales_by_cell_number_and_time() -> None:
    out = compute_consumption(
        _frame(),
        sample_columns=_SAMPLES,
        groups=suggest_groups(_SAMPLES),
        reference_group="fresh",
        annotation_columns=["compound"],
        cell_numbers={"spent1": 2.0, "spent2": 1.0},
        dt=2.0,
    )
    row_x = out[out["compound"] == "X"].iloc[0]
    assert row_x["spent1"] == pytest.approx(-40.0 / (2.0 * 2.0))  # -10
    assert row_x["spent2"] == pytest.approx(-60.0 / (1.0 * 2.0))  # -30


def _persisted(tmp_path: Path) -> LCMSFeatureTable:
    table = LCMSFeatureTable.from_elmaven(_frame(), polarity="negative", sample_columns=_SAMPLES)
    table.save(tmp_path / "in.parquet")
    return table


def test_block_headless_guesses_reference(tmp_path: Path) -> None:
    table = _persisted(tmp_path)
    # "fresh" group name is auto-detected as the reference.
    out = ConsumptionRelease().run({"features": Collection([table])}, BlockConfig(params={}))
    result = out["rates"][0]
    result.save(tmp_path / "o.parquet")
    frame = result.to_pandas()
    assert "fresh1" not in frame.columns
    assert frame[frame["compound"] == "X"].iloc[0]["spent1"] == pytest.approx(-40.0)


def test_block_uses_metadata_for_rate(tmp_path: Path) -> None:
    table = _persisted(tmp_path)
    meta = dataframe_from_pandas(pd.DataFrame({"sample": ["spent1", "spent2"], "cell_number": [2.0, 1.0]}))
    meta.save(tmp_path / "meta.parquet")
    response = {"tables": [{"groups": suggest_groups(_SAMPLES), "reference_group": "fresh"}]}
    config = BlockConfig(params={INTERACTIVE_RESPONSE_KEY: response, "dt": 1.0})

    out = ConsumptionRelease().run({"features": Collection([table]), "metadata": meta}, config)
    result = out["rates"][0]
    result.save(tmp_path / "o.parquet")
    row_x = result.to_pandas()
    assert row_x[row_x["compound"] == "X"].iloc[0]["spent1"] == pytest.approx(-20.0)  # -40 / (2*1)
