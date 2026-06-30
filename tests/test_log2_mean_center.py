"""Tests for Log2MeanCenter: the transform maths and the block."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from scistudio.blocks.base import BlockConfig
from scistudio.core.types import Collection

from scistudio_blocks_lcms.blocks import Log2MeanCenter
from scistudio_blocks_lcms.blocks.log2_mean_center import _log2_mean_center
from scistudio_blocks_lcms.types import LCMSFeatureTable

_SAMPLES = ["S1", "S2"]


def _frame() -> pd.DataFrame:
    return pd.DataFrame({"compound": ["X", "Y"], "S1": [2.0, 8.0], "S2": [8.0, 2.0]})


def test_log2_mean_center_is_relative_log2fc() -> None:
    out = _log2_mean_center(_frame(), _SAMPLES, 0.1)
    # X: log2(2),log2(8) = 1,3 -> mean 2 -> -1,+1 ; Y: 3,1 -> +1,-1
    assert list(out["S1"]) == pytest.approx([-1.0, 1.0])
    assert list(out["S2"]) == pytest.approx([1.0, -1.0])
    assert list(out["compound"]) == ["X", "Y"]  # annotation passes through


def test_non_positive_is_floored_to_pseudocount() -> None:
    frame = pd.DataFrame({"compound": ["X"], "S1": [0.0], "S2": [4.0]})
    out = _log2_mean_center(frame, _SAMPLES, 0.1)
    # smallest positive is 4 -> pseudo 0.4; log2(0.4) and log2(4), centered.
    import numpy as np

    expected = np.array([np.log2(0.4), np.log2(4.0)])
    expected = expected - expected.mean()
    assert list(out.iloc[0][_SAMPLES]) == pytest.approx(list(expected))


def test_block_transforms_table(tmp_path: Path) -> None:
    table = LCMSFeatureTable.from_elmaven(_frame(), polarity="negative", sample_columns=_SAMPLES)
    table.save(tmp_path / "in.parquet")
    out = Log2MeanCenter().run({"features": Collection([table])}, BlockConfig(params={}))
    result = out["features"][0]
    assert isinstance(result, LCMSFeatureTable)
    assert result.meta.sample_columns == ("S1", "S2")
    result.save(tmp_path / "o.parquet")
    assert list(result.to_pandas()["S1"]) == pytest.approx([-1.0, 1.0])
