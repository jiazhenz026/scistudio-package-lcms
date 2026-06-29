"""Tests for BackgroundSubtraction: the name heuristic, subtraction, and the block.

The name heuristic and the subtraction maths are pure Python and fully covered
here. The interactive panel itself (the frontend) is exercised separately; the
block is tested both headless (auto-suggestion applied) and with a supplied
panel decision.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from scistudio.blocks.base import INTERACTIVE_RESPONSE_KEY, BlockConfig
from scistudio.core.types import Collection

from scistudio_package_lcms.blocks import BackgroundSubtraction
from scistudio_package_lcms.blocks._background_match import (
    BACKGROUND,
    IGNORE,
    QC,
    SAMPLE,
    apply_subtraction,
    classify_role,
    suggest,
)
from scistudio_package_lcms.types import LCMSFeatureTable


def test_classify_role_handles_messy_names() -> None:
    assert classify_role("A_9_2_B") == SAMPLE
    assert classify_role("BLANK1") == BACKGROUND
    assert classify_role("bg 0") == BACKGROUND
    assert classify_role("Background_C") == BACKGROUND
    assert classify_role("BK_neg") == BACKGROUND
    assert classify_role("QC_1") == QC
    assert classify_role("pooledQC") == QC
    assert classify_role("WASH1") == IGNORE
    assert classify_role("blank_wash") == IGNORE  # wash wins over blank
    assert classify_role("SAMPLE_0") == BACKGROUND  # replicate-0 convention


def test_suggest_matches_samples_to_group_background() -> None:
    decision = suggest(["A_0", "A_1", "A_2", "BLANK1", "C_1"])
    roles = decision["roles"]
    assert roles["A_0"] == BACKGROUND and roles["A_1"] == SAMPLE
    assert roles["BLANK1"] == BACKGROUND
    # Group A samples take group A's background; the ungrouped C sample falls
    # back to the global BLANK.
    assert decision["assignments"]["A_1"] == ["A_0"]
    assert decision["assignments"]["C_1"] == ["BLANK1"]
    assert set(decision["drop"]) == {"A_0", "BLANK1"}


def test_apply_subtraction_keeps_negatives_and_drops_backgrounds() -> None:
    frame = pd.DataFrame({"compound": ["X", "Y"], "A_0": [5.0, 2.0], "A_1": [15.0, 12.0], "A_2": [25.0, 1.0]})
    decision = {"assignments": {"A_1": ["A_0"], "A_2": ["A_0"]}, "aggregation": "median", "drop": ["A_0"]}

    out = apply_subtraction(frame, decision)

    assert list(out.columns) == ["compound", "A_1", "A_2"]  # background dropped
    assert list(out["A_1"]) == [10.0, 10.0]
    assert list(out["A_2"]) == [20.0, -1.0]  # negative preserved, not clamped


def _persisted_table(tmp_path: Path) -> LCMSFeatureTable:
    frame = pd.DataFrame(
        {
            "isotopeLabel": ["C12 PARENT", "C13-label-1"],
            "compound": ["X", "X"],
            "formula": ["C5", "C5"],
            "medMz": [100.0, 101.0],
            "medRt": [1.0, 1.0],
            "A_0": [5.0, 2.0],
            "A_1": [15.0, 12.0],
            "A_2": [25.0, 1.0],
        }
    )
    table = LCMSFeatureTable.from_elmaven(frame, polarity="negative")
    table.save(tmp_path / "input.parquet")
    return table


def test_block_headless_applies_suggestion(tmp_path: Path) -> None:
    table = _persisted_table(tmp_path)
    outputs = BackgroundSubtraction().run({"features": Collection([table])}, BlockConfig(params={}))

    coll = outputs["features"]
    assert coll.length == 1
    result = coll[0]
    assert isinstance(result, LCMSFeatureTable)
    # A_0 is the group-A background (replicate 0) → subtracted then dropped.
    assert "A_0" not in (result.columns or [])
    assert result.meta.sample_columns == ("A_1", "A_2")
    assert result.meta.polarity == "negative"
    result.save(tmp_path / "out.parquet")
    assert list(result.to_pandas()["A_1"]) == [10.0, 10.0]


def test_block_uses_panel_decision(tmp_path: Path) -> None:
    table = _persisted_table(tmp_path)
    decision = {
        "tables": [
            {"assignments": {"A_1": ["A_2"]}, "aggregation": "median", "drop": ["A_0", "A_2"]},
        ]
    }
    config = BlockConfig(params={INTERACTIVE_RESPONSE_KEY: decision})

    result = BackgroundSubtraction().run({"features": Collection([table])}, config)["features"][0]

    cols = result.columns or []
    assert "A_0" not in cols and "A_2" not in cols
    result.save(tmp_path / "out.parquet")
    assert list(result.to_pandas()["A_1"]) == [15.0 - 25.0, 12.0 - 1.0]


def test_prepare_prompt_is_json_safe_with_tabs(tmp_path: Path) -> None:
    table = _persisted_table(tmp_path)
    prompt = BackgroundSubtraction().prepare_prompt({"features": Collection([table, table])}, BlockConfig(params={}))

    payload = prompt.panel_payload
    assert len(payload["tables"]) == 2  # one tab per input table
    assert payload["tables"][0]["suggestion"]["roles"]["A_0"] == BACKGROUND
    json.dumps(payload)  # must be JSON-serialisable for the wire
