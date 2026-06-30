"""Tests for CalculateMID: MID fractions, enrichment, and the block."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from scistudio.blocks.base import BlockConfig
from scistudio.core.types import Collection

from scistudio_package_lcms.blocks import CalculateMID
from scistudio_package_lcms.blocks._mid import _label_index, compute_mid_and_enrichment
from scistudio_package_lcms.types import LCMSFeatureTable

_SAMPLES = ["S1"]


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "isotopeLabel": ["C12 PARENT", "C13-label-1", "C13-label-2"],
            "compound": ["glucose", "glucose", "glucose"],
            "formula": ["C6", "C6", "C6"],
            "S1": [60.0, 30.0, 10.0],
        }
    )


def test_label_index() -> None:
    assert _label_index("C12 PARENT") == 0
    assert _label_index("C13-label-1") == 1
    assert _label_index("C13-label-12") == 12


def test_mid_fractions_and_enrichment() -> None:
    mid, enrichment = compute_mid_and_enrichment(_frame(), sample_columns=_SAMPLES)
    # MID fractions sum to 1: 60/100, 30/100, 10/100
    assert list(mid["S1"]) == pytest.approx([0.6, 0.3, 0.1])
    # enrichment = (0*0.6 + 1*0.3 + 2*0.1) / (3-1) = 0.5/2 = 0.25
    assert enrichment.shape[0] == 1
    assert enrichment.iloc[0]["compound"] == "glucose"
    assert enrichment.iloc[0]["S1"] == pytest.approx(0.25)


def test_zero_intensity_gives_zero_mid() -> None:
    frame = _frame()
    frame["S2"] = [0.0, 0.0, 0.0]
    mid, enrichment = compute_mid_and_enrichment(frame, sample_columns=["S1", "S2"])
    assert list(mid["S2"]) == [0.0, 0.0, 0.0]
    assert enrichment.iloc[0]["S2"] == pytest.approx(0.0)


def test_block_emits_mid_and_enrichment(tmp_path: Path) -> None:
    table = LCMSFeatureTable.from_elmaven(_frame(), polarity="negative", sample_columns=_SAMPLES)
    table.save(tmp_path / "in.parquet")
    out = CalculateMID().run({"features": Collection([table])}, BlockConfig(params={}))

    mid = out["mid"][0]
    enrichment = out["enrichment"][0]
    assert isinstance(mid, LCMSFeatureTable) and isinstance(enrichment, LCMSFeatureTable)
    mid.save(tmp_path / "mid.parquet")
    enrichment.save(tmp_path / "enr.parquet")
    assert list(mid.to_pandas()["S1"]) == pytest.approx([0.6, 0.3, 0.1])
    enr_frame = enrichment.to_pandas()
    assert enr_frame.shape[0] == 1  # collapsed to one row per compound
    assert enr_frame.iloc[0]["S1"] == pytest.approx(0.25)
