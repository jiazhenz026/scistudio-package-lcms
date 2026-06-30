"""Tests for Normalization: the four methods, the suggestion, and the block.

The reference-resolution and division maths are pure Python and fully covered
here. The block is tested headless (configured method applied) and with a
supplied panel decision (single reference + isotope internal standard).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from scistudio.blocks.base import INTERACTIVE_RESPONSE_KEY, BlockConfig
from scistudio.core.types import Collection

from scistudio_blocks_lcms.blocks import Normalization
from scistudio_blocks_lcms.blocks._normalization import apply_normalization, suggest_reference
from scistudio_blocks_lcms.types import LCMSFeatureTable

_SAMPLES = ["S1", "S2"]


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "isotopeLabel": ["C12 PARENT", "C13-label-1", "C12 PARENT"],
            "compound": ["glucose", "glucose", "HEPES"],
            "formula": ["C6", "C6", "C8"],
            "S1": [10.0, 2.0, 5.0],
            "S2": [20.0, 4.0, 10.0],
        }
    )


def test_total_and_median_normalization() -> None:
    total = apply_normalization(_frame(), method="total", sample_columns=_SAMPLES)
    assert total["S1"].sum() == pytest.approx(1.0)
    assert total["S2"].sum() == pytest.approx(1.0)

    median = apply_normalization(_frame(), method="median", sample_columns=_SAMPLES)
    # S1 median of [10,2,5] = 5; S2 median of [20,4,10] = 10
    assert list(median["S1"]) == [2.0, 0.4, 1.0]
    assert list(median["S2"]) == [2.0, 0.4, 1.0]


def test_single_reference_divides_and_drops_reference() -> None:
    out = apply_normalization(
        _frame(), method="single_reference", sample_columns=_SAMPLES, reference={"compound": "HEPES"}
    )
    # HEPES row dropped; every remaining feature ÷ HEPES (S1=5, S2=10).
    assert list(out["compound"]) == ["glucose", "glucose"]
    assert list(out["S1"]) == [2.0, 0.4]
    assert list(out["S2"]) == [2.0, 0.4]


def test_single_reference_keep_reference() -> None:
    out = apply_normalization(
        _frame(),
        method="single_reference",
        sample_columns=_SAMPLES,
        reference={"compound": "HEPES"},
        drop_reference=False,
    )
    assert list(out["compound"]) == ["glucose", "glucose", "HEPES"]
    assert list(out["S1"]) == [2.0, 0.4, 1.0]  # HEPES self-normalizes to 1


def test_isotope_internal_standard_per_metabolite() -> None:
    out = apply_normalization(
        _frame(),
        method="isotope_internal_standard",
        sample_columns=_SAMPLES,
        pairs=[{"compound": "glucose", "is_label": "C13-label-1"}],
    )
    # glucose C12 PARENT ÷ its C13-label-1 IS (S1=2, S2=4); IS row dropped; HEPES untouched.
    assert list(out["compound"]) == ["glucose", "HEPES"]
    assert list(out["isotopeLabel"]) == ["C12 PARENT", "C12 PARENT"]
    assert list(out["S1"]) == [5.0, 5.0]
    assert list(out["S2"]) == [5.0, 10.0]


def test_zero_denominator_leaves_column_unchanged() -> None:
    frame = _frame()
    frame["S3"] = [0.0, 0.0, 0.0]
    out = apply_normalization(
        frame, method="single_reference", sample_columns=["S1", "S3"], reference={"compound": "HEPES"}
    )
    assert list(out["S3"]) == [0.0, 0.0]  # zero reference → untouched, no divide-by-zero


def test_suggest_reference_flags_standards() -> None:
    assert suggest_reference(["glucose", "HEPES", "lactate"]) == "HEPES"
    assert suggest_reference(["d3-Leucine_ISTD", "glucose"]) == "d3-Leucine_ISTD"
    assert suggest_reference(["glucose", "lactate"]) is None


def _persisted(tmp_path: Path) -> LCMSFeatureTable:
    table = LCMSFeatureTable.from_elmaven(_frame(), polarity="negative", sample_columns=_SAMPLES)
    table.save(tmp_path / "in.parquet")
    return table


def test_block_headless_uses_configured_method(tmp_path: Path) -> None:
    table = _persisted(tmp_path)
    out = Normalization().run({"features": Collection([table])}, BlockConfig(params={"method": "median"}))
    result = out["features"][0]
    assert isinstance(result, LCMSFeatureTable)
    result.save(tmp_path / "o.parquet")
    assert list(result.to_pandas()["S1"]) == [2.0, 0.4, 1.0]


def test_block_uses_panel_single_reference(tmp_path: Path) -> None:
    table = _persisted(tmp_path)
    response = {"method": "single_reference", "drop_reference": True, "tables": [{"reference": {"compound": "HEPES"}}]}
    out = Normalization().run(
        {"features": Collection([table])}, BlockConfig(params={INTERACTIVE_RESPONSE_KEY: response})
    )
    result = out["features"][0]
    assert result.meta.sample_columns == ("S1", "S2")
    result.save(tmp_path / "o.parquet")
    assert "HEPES" not in list(result.to_pandas()["compound"])


def test_block_uses_panel_isotope_is(tmp_path: Path) -> None:
    table = _persisted(tmp_path)
    response = {
        "method": "isotope_internal_standard",
        "tables": [{"pairs": [{"compound": "glucose", "is_label": "C13-label-1"}]}],
    }
    out = Normalization().run(
        {"features": Collection([table])}, BlockConfig(params={INTERACTIVE_RESPONSE_KEY: response})
    )
    result = out["features"][0]
    result.save(tmp_path / "o.parquet")
    assert list(result.to_pandas()["S1"]) == [5.0, 5.0]


def test_prepare_prompt_is_json_safe(tmp_path: Path) -> None:
    table = _persisted(tmp_path)
    prompt = Normalization().prepare_prompt({"features": Collection([table])}, BlockConfig(params={}))
    payload = prompt.panel_payload
    assert payload["tables"][0]["suggestion"]["single_reference"] == "HEPES"
    assert {"compound": "glucose", "labels": ["C12 PARENT", "C13-label-1"]} in payload["tables"][0]["compounds"]
    json.dumps(payload)
