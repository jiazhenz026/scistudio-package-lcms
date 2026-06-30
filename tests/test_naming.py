"""Display-name provenance: source_file on Meta, carried by from_wide, resolved by core."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from scistudio.blocks.base import BlockConfig
from scistudio.core.meta._display_name import resolve_display_name
from scistudio.core.types import Collection

from scistudio_blocks_lcms.blocks import Normalization
from scistudio_blocks_lcms.blocks._naming import derived_name, source_label
from scistudio_blocks_lcms.types import LCMSFeatureTable

_SAMPLES = ["S1", "S2"]


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"compound": ["X", "Y"], "isotopeLabel": ["C12 PARENT", "C12 PARENT"], "S1": [1.0, 2.0], "S2": [3.0, 4.0]}
    )


def _loaded(name: str) -> LCMSFeatureTable:
    table = LCMSFeatureTable.from_elmaven(
        _frame(), polarity="negative", sample_columns=_SAMPLES, source_file=f"{name}.csv"
    )
    table.user["display_name"] = name
    return table


def test_source_file_alone_resolves_via_core() -> None:
    # No explicit display_name → core infers the name from meta.source_file basename.
    table = LCMSFeatureTable.from_elmaven(_frame(), sample_columns=_SAMPLES, source_file="scan1_negative.csv")
    assert resolve_display_name(table, fallback="") == "scan1_negative.csv"


def test_from_wide_carries_source_provenance() -> None:
    src = _loaded("scan1")
    derived = LCMSFeatureTable.from_wide(_frame(), sample_columns=_SAMPLES, source=src)
    assert derived.meta.source_file == "scan1.csv"  # provenance carried on Meta
    assert derived.user["display_name"] == "scan1"  # name carried on user
    assert resolve_display_name(derived, fallback="") == "scan1"


def test_derived_name_composition() -> None:
    assert derived_name(_loaded("scan1"), "Corrected") == "scan1 · Corrected"
    assert source_label(_loaded("scan2_positive")) == "scan2_positive"
    # An unnamed source falls back to just the suffix.
    bare = LCMSFeatureTable.from_elmaven(_frame(), sample_columns=_SAMPLES)
    assert derived_name(bare, "Corrected") == "Corrected"


def test_transform_block_inherits_source_name(tmp_path: Path) -> None:
    table = _loaded("scan1")
    table.save(tmp_path / "in.parquet")
    out = Normalization().run({"features": Collection([table])}, BlockConfig(params={"method": "total"}))
    result = out["features"][0]
    # The 1:1 transform set no name itself — it flows from the source via from_wide.
    assert resolve_display_name(result, fallback="") == "scan1"
