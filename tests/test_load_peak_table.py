"""Behavior tests for the :class:`LoadPeakTable` IO block."""

from __future__ import annotations

from pathlib import Path

from scistudio.blocks.base.config import BlockConfig

from scistudio_package_lcms import _support
from scistudio_package_lcms.blocks.load_peak_table import LoadPeakTable
from scistudio_package_lcms.types import LCMSFeatures

#: A minimal El-MAVEN-style export: metadata columns + sample columns, one row
#: per isotopologue.
_CSV = (
    "label,metaGroupId,groupId,medMz,medRt,isotopeLabel,compound,formula,parent,"
    "A_1,A_2,BLANK1\n"
    ",1,1,180.066,10.0,C12 PARENT,L-Tyrosine,C9H11NO3,180.066,1000,1100,5\n"
    ",1,2,181.069,10.0,C13-label-1,L-Tyrosine,C9H11NO3,180.066,50,60,0\n"
)


def _write_csv(tmp_path: Path) -> Path:
    path = tmp_path / "peaks_negative.csv"
    path.write_text(_CSV, encoding="utf-8")
    return path


def test_output_port_is_lcmsfeatures() -> None:
    ports = LoadPeakTable.output_ports
    assert len(ports) == 1
    assert ports[0].name == "features"
    assert LCMSFeatures in ports[0].accepted_types


def test_load_keeps_columns_verbatim_and_tags_meta(tmp_path: Path) -> None:
    path = _write_csv(tmp_path)
    out = LoadPeakTable().load(
        BlockConfig(params={"path": str(path), "polarity": "negative", "source_tool": "elmaven"})
    )
    assert isinstance(out, LCMSFeatures)
    assert out.row_count == 2
    df = _support.features_pandas(out)
    # Every exported column is preserved, including the sample + blank columns.
    assert list(df.columns) == [
        "label",
        "metaGroupId",
        "groupId",
        "medMz",
        "medRt",
        "isotopeLabel",
        "compound",
        "formula",
        "parent",
        "A_1",
        "A_2",
        "BLANK1",
    ]
    assert out.meta is not None
    assert out.meta.polarity == "negative"
    assert out.meta.source_tool == "elmaven"
    assert out.meta.source_file == "peaks_negative.csv"
    # isotopeLabel column is present -> detected as a labeled (tracing) table.
    assert out.meta.labeled is True


def test_unknown_polarity_becomes_none(tmp_path: Path) -> None:
    path = _write_csv(tmp_path)
    out = LoadPeakTable().load(BlockConfig(params={"path": str(path), "polarity": "unknown"}))
    assert isinstance(out, LCMSFeatures)
    assert out.meta is not None and out.meta.polarity is None


def test_missing_file_raises(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(FileNotFoundError):
        LoadPeakTable().load(BlockConfig(params={"path": str(tmp_path / "nope.csv")}))
