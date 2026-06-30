"""Tests for MetaboliteExport: the ID join and the block."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from scistudio.blocks.base import BlockConfig

from scistudio_package_lcms.blocks import MetaboliteExport
from scistudio_package_lcms.blocks._results import dataframe_from_pandas
from scistudio_package_lcms.blocks.metabolite_export import _annotate


def _table() -> pd.DataFrame:
    return pd.DataFrame({"compound": ["glucose", "mystery"], "mean_A": [1.0, 2.0], "p_value": [0.01, 0.5]})


def _id_map() -> pd.DataFrame:
    return pd.DataFrame({"compound": ["glucose", "lactate"], "HMDB": ["HMDB0000122", "HMDB0000190"]})


def test_annotate_joins_and_drops_unmapped() -> None:
    out = _annotate(
        _table(),
        _id_map(),
        compound_column="compound",
        map_name_column="compound",
        map_id_column="HMDB",
        output_id_column="HMDB",
        require_id=True,
    )
    assert list(out.columns) == ["compound", "HMDB", "mean_A", "p_value"]  # ID right after compound
    assert list(out["compound"]) == ["glucose"]  # unmapped 'mystery' dropped
    assert out.iloc[0]["HMDB"] == "HMDB0000122"


def test_annotate_keeps_unmapped_when_not_required() -> None:
    out = _annotate(
        _table(),
        _id_map(),
        compound_column="compound",
        map_name_column="compound",
        map_id_column="HMDB",
        output_id_column="HMDB",
        require_id=False,
    )
    assert list(out["compound"]) == ["glucose", "mystery"]
    assert pd.isna(out.iloc[1]["HMDB"])


def test_block_annotates_table(tmp_path: Path) -> None:
    table = dataframe_from_pandas(_table())
    table.save(tmp_path / "table.parquet")
    id_map = dataframe_from_pandas(_id_map())
    id_map.save(tmp_path / "map.parquet")

    out = MetaboliteExport().run({"table": table, "id_map": id_map}, BlockConfig(params={}))
    result = out["exported"]
    result.save(tmp_path / "out.parquet")
    frame = result.to_pandas()
    assert list(frame["compound"]) == ["glucose"]
    assert frame.iloc[0]["HMDB"] == "HMDB0000122"
