"""Tests for the LoadPeakTable El-MAVEN loader block."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from scistudio_blocks_lcms.blocks import LoadPeakTable
from scistudio_blocks_lcms.types import LCMSFeatureTable


def _write_elmaven_csv(path: Path, *, sep: str = ",") -> None:
    """Write a minimal El-MAVEN peaks export to *path*."""
    frame = pd.DataFrame(
        {
            "isotopeLabel": ["C12 PARENT", "C13-label-1"],
            "medMz": [180.066, 181.070],
            "medRt": [10.07, 10.06],
            "compound": ["L-Tyrosine", "L-Tyrosine"],
            "Sample_A": [1608868.0, 161615.45],
            "Sample_B": [1743866.38, 163117.81],
        }
    )
    frame.to_csv(path, sep=sep, index=False)


def test_synthesized_capability() -> None:
    """The framework synthesizes a load capability for LCMSFeatureTable."""
    (cap,) = LoadPeakTable.get_format_capabilities()
    assert cap.direction == "load"
    assert cap.data_type is LCMSFeatureTable
    assert ".csv" in cap.extensions and ".tab" in cap.extensions
    assert cap.handler == "load_file"


def test_load_csv_infers_negative_polarity_from_name(tmp_path: Path) -> None:
    """An auto polarity is inferred from the conventional file name."""
    csv = tmp_path / "scan1_negative_peaks_IL2.csv"
    _write_elmaven_csv(csv)

    table = LoadPeakTable().load_file(csv, {"polarity": "auto"})

    assert isinstance(table, LCMSFeatureTable)
    assert table.row_count == 2
    assert table.meta.polarity == "negative"
    assert table.meta.software == "El-MAVEN"
    assert table.meta.labeled is True
    assert table.meta.sample_columns == ("Sample_A", "Sample_B")


def test_explicit_polarity_overrides_name(tmp_path: Path) -> None:
    """An explicit polarity wins over the file-name inference."""
    csv = tmp_path / "scan2_negative_peaks.csv"
    _write_elmaven_csv(csv)

    table = LoadPeakTable().load_file(csv, {"polarity": "positive"})

    assert table.meta.polarity == "positive"


def test_load_tab_delimited(tmp_path: Path) -> None:
    """A ``.tab`` export is read as tab-delimited."""
    tab = tmp_path / "hydrolysates.tab"
    _write_elmaven_csv(tab, sep="\t")

    table = LoadPeakTable().load_file(tab, {})

    assert isinstance(table, LCMSFeatureTable)
    assert table.columns is not None and "Sample_A" in table.columns
