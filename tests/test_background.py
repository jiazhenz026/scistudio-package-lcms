"""Behavior tests for BackgroundSelector and BackgroundSubtraction."""

from __future__ import annotations

import pandas as pd
from scistudio.blocks.base.config import BlockConfig
from scistudio.core.types.collection import Collection

from scistudio_package_lcms import _support
from scistudio_package_lcms.blocks.background import BackgroundSelector, BackgroundSubtraction
from scistudio_package_lcms.types import LCMSFeatures


def _features() -> LCMSFeatures:
    frame = pd.DataFrame(
        {
            "compound": ["X", "Y"],
            "formula": ["C1", "C2"],
            "A_1": [100.0, 200.0],
            "A_2": [110.0, 210.0],
            "BLANK1": [10.0, 20.0],
            "BLANK2": [20.0, 40.0],
        }
    )
    return _support.build_features(frame)


def _only(coll: Collection) -> LCMSFeatures:
    items = list(coll)
    assert len(items) == 1
    return items[0]


def test_selector_splits_samples_and_background_1to1() -> None:
    out = BackgroundSelector().run(
        {"features": _support.features_collection(_features())},
        BlockConfig(params={"background_patterns": ["BLANK*"], "sample_patterns": ["A_*"], "aggregation": "mean"}),
    )
    samples = _support.features_pandas(_only(out["samples"]))
    background = _support.features_pandas(_only(out["background"]))

    # Identifier columns carried into both; sample columns are A_*.
    assert list(samples.columns) == ["compound", "formula", "A_1", "A_2"]
    assert list(background.columns) == ["compound", "formula", "A_1", "A_2"]
    # Background profile = mean(BLANK1, BLANK2) broadcast across sample columns.
    assert background["A_1"].tolist() == [15.0, 30.0]
    assert background["A_2"].tolist() == [15.0, 30.0]
    # Samples are untouched.
    assert samples["A_1"].tolist() == [100.0, 200.0]


def test_selector_requires_matching_columns() -> None:
    import pytest

    with pytest.raises(ValueError):
        BackgroundSelector().run(
            {"features": _support.features_collection(_features())},
            BlockConfig(params={"background_patterns": ["NOPE*"], "sample_patterns": ["A_*"]}),
        )


def test_subtraction_elementwise_with_clip() -> None:
    feats = _features()
    sel = BackgroundSelector().run(
        {"features": _support.features_collection(feats)},
        BlockConfig(params={"background_patterns": ["BLANK*"], "sample_patterns": ["A_*"]}),
    )
    out = BackgroundSubtraction().run(
        {"samples": sel["samples"], "background": sel["background"]},
        BlockConfig(params={"clip_negative": True}),
    )
    result = _support.features_pandas(_only(out["result"]))
    # A_1 row0 = 100 - 15 = 85 ; A_2 row1 = 210 - 30 = 180.
    assert result["A_1"].tolist() == [85.0, 170.0]
    assert result["A_2"].tolist() == [95.0, 180.0]
    assert list(result.columns) == ["compound", "formula", "A_1", "A_2"]


def test_subtraction_clip_negative_floors_at_zero() -> None:
    samples = _support.build_features(pd.DataFrame({"id": ["a"], "S1": [5.0]}))
    background = _support.build_features(pd.DataFrame({"id": ["a"], "S1": [9.0]}))
    out = BackgroundSubtraction().run(
        {"samples": _support.features_collection(samples), "background": _support.features_collection(background)},
        BlockConfig(params={"clip_negative": True}),
    )
    assert _support.features_pandas(_only(out["result"]))["S1"].tolist() == [0.0]

    out_signed = BackgroundSubtraction().run(
        {"samples": _support.features_collection(samples), "background": _support.features_collection(background)},
        BlockConfig(params={"clip_negative": False}),
    )
    assert _support.features_pandas(_only(out_signed["result"]))["S1"].tolist() == [-4.0]


def test_subtraction_rejects_mismatched_row_counts() -> None:
    import pytest

    samples = _support.build_features(pd.DataFrame({"id": ["a", "b"], "S1": [1.0, 2.0]}))
    background = _support.build_features(pd.DataFrame({"id": ["a"], "S1": [1.0]}))
    with pytest.raises(ValueError):
        BackgroundSubtraction().run(
            {
                "samples": _support.features_collection(samples),
                "background": _support.features_collection(background),
            },
            BlockConfig(params={}),
        )
