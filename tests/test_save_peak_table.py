"""Tests for SavePeakTable: single-file and multi-file (one CSV per table)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from scistudio.blocks.base import BlockConfig
from scistudio.core.types import Collection

from scistudio_blocks_lcms.blocks import SavePeakTable
from scistudio_blocks_lcms.types import LCMSFeatureTable


def _table(tmp_path: Path, name: str, value: float) -> LCMSFeatureTable:
    frame = pd.DataFrame({"compound": ["X"], "isotopeLabel": ["C12 PARENT"], "S1": [value]})
    table = LCMSFeatureTable.from_elmaven(frame, polarity="negative", sample_columns=["S1"])
    table.user["display_name"] = name
    table.save(tmp_path / f"{name}_{value}.parquet")  # persist (unique path) so to_pandas() works
    return table


def test_synthesized_save_capability() -> None:
    (cap,) = SavePeakTable.get_format_capabilities()
    assert cap.direction == "save"
    assert cap.data_type is LCMSFeatureTable
    assert ".csv" in cap.extensions


def test_save_single_table_to_csv(tmp_path: Path) -> None:
    table = _table(tmp_path, "Corrected", 42.0)
    out = tmp_path / "out.csv"
    SavePeakTable().save(Collection([table]), BlockConfig(params={"path": str(out)}))
    assert out.is_file()
    assert pd.read_csv(out)["S1"].iloc[0] == 42.0


def test_save_multiple_tables_one_csv_each_named_by_display_name(tmp_path: Path) -> None:
    tables = [_table(tmp_path, "scan1", 1.0), _table(tmp_path, "scan2", 2.0)]
    out_dir = tmp_path / "exported"
    SavePeakTable().save(Collection(tables), BlockConfig(params={"path": str(out_dir)}))

    assert (out_dir / "scan1.csv").is_file()
    assert (out_dir / "scan2.csv").is_file()
    assert pd.read_csv(out_dir / "scan2.csv")["S1"].iloc[0] == 2.0


def test_save_dedupes_colliding_names(tmp_path: Path) -> None:
    tables = [_table(tmp_path, "dup", 1.0), _table(tmp_path, "dup", 2.0)]
    out_dir = tmp_path / "exported"
    SavePeakTable().save(Collection(tables), BlockConfig(params={"path": str(out_dir)}))
    assert (out_dir / "dup.csv").is_file()
    assert (out_dir / "dup_2.csv").is_file()  # second collision suffixed
