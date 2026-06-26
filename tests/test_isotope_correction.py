"""Tests for the IsotopeCorrection block.

Pure-Python prep logic (label parsing, dual reshaping) runs everywhere. The R
integration tests are skipped automatically when R / AccuCor / AccuCor2 are not
installed (e.g. on CI), so the suite stays green without R.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest
from scistudio.blocks.base.config import BlockConfig

from scistudio_package_lcms import _support
from scistudio_package_lcms.blocks.isotope_correction import (
    IsotopeCorrection,
    parse_isotope_label,
    prep_dual_inputs,
    sample_columns,
)
from scistudio_package_lcms.types import LCMSFeatures

# --------------------------------------------------------------------------- #
# Pure-Python tests (no R required)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("C12 PARENT", (0, 0)),
        ("C13-label-1", (1, 0)),
        ("C13-label-3", (3, 0)),
        ("D2-label-2", (0, 2)),
    ],
)
def test_parse_isotope_label(label: str, expected: tuple[int, int]) -> None:
    assert parse_isotope_label(label) == expected


def test_sample_columns_excludes_identifiers() -> None:
    frame = pd.DataFrame(
        {"compound": ["x"], "formula": ["C1"], "medMz": [1.0], "parent": [1.0], "A_1": [10.0], "QC_1": [5.0]}
    )
    assert sample_columns(frame) == ["A_1", "QC_1"]


def _labeled_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "compound": ["L-Tyrosine", "L-Tyrosine", "L-Tyrosine"],
            "formula": ["C9H11NO3", "C9H11NO3", "C9H11NO3"],
            "parent": [180.066, 180.066, 180.066],
            "isotopeLabel": ["C12 PARENT", "C13-label-1", "C13-label-2"],
            "A_1": [1000.0, 50.0, 5.0],
            "A_2": [1100.0, 60.0, 6.0],
        }
    )


def test_prep_dual_inputs_shape_and_charge() -> None:
    input_df, formula_df = prep_dual_inputs(_labeled_frame(), polarity="negative")
    assert list(input_df.columns) == ["Compound", "parent", "13C#", "2H#", "Expected?", "A_1", "A_2"]
    assert input_df["13C#"].tolist() == [0, 1, 2]
    assert input_df["2H#"].tolist() == [0, 0, 0]
    assert list(formula_df.columns) == ["compoundId", "formula", "charge"]
    assert formula_df["charge"].tolist() == [-1]  # negative polarity
    assert formula_df["compoundId"].tolist() == ["L-Tyrosine"]


def test_prep_dual_inputs_positive_charge() -> None:
    _, formula_df = prep_dual_inputs(_labeled_frame(), polarity="positive")
    assert formula_df["charge"].tolist() == [1]


def test_prep_dual_inputs_requires_polarity() -> None:
    with pytest.raises(ValueError, match="polarity"):
        prep_dual_inputs(_labeled_frame(), polarity=None)


def test_block_declares_three_outputs() -> None:
    names = [p.name for p in IsotopeCorrection.output_ports]
    assert names == ["corrected", "mid", "pool_size"]
    for port in IsotopeCorrection.output_ports:
        assert LCMSFeatures in port.accepted_types


# --------------------------------------------------------------------------- #
# R integration tests (skipped when R / AccuCor unavailable)
# --------------------------------------------------------------------------- #


def _r_has(pkg: str) -> bool:
    rscript = shutil.which("Rscript")
    if rscript is None:
        return False
    proc = subprocess.run(
        [rscript, "-e", f'quit(status = as.integer(!requireNamespace("{pkg}", quietly = TRUE)))'],
        capture_output=True,
    )
    return proc.returncode == 0


def _accucor_example_csv() -> Path | None:
    rscript = shutil.which("Rscript")
    if rscript is None:
        return None
    proc = subprocess.run(
        [rscript, "-e", 'cat(system.file("extdata", "elmaven_export.csv", package = "accucor"))'],
        capture_output=True,
        text=True,
    )
    path = Path(proc.stdout.strip())
    return path if path.is_file() else None


@pytest.mark.skipif(not _r_has("accucor"), reason="R package 'accucor' not installed")
def test_single_correction_against_accucor_example() -> None:
    csv = _accucor_example_csv()
    if csv is None:
        pytest.skip("accucor example data not found")
    feats = _support.build_features(pd.read_csv(csv), meta=LCMSFeatures.Meta(polarity="positive"))
    out = IsotopeCorrection().run(
        {"features": _support.features_collection(feats)},
        BlockConfig(params={"mode": "single", "tracer": "13C", "resolution": 140000}),
    )
    assert set(out) == {"corrected", "mid", "pool_size"}
    mid = _support.features_pandas(list(out["mid"])[0])
    # Each compound's MID is a fraction that sums to 1 within a sample.
    sample = [c for c in mid.columns if c not in ("Compound", "C_Label")][0]
    sums = mid.groupby("Compound")[sample].sum()
    assert all(abs(v - 1.0) < 1e-6 for v in sums)


@pytest.mark.skipif(not _r_has("accucor2"), reason="R package 'accucor2' not installed")
def test_dual_correction_produces_mid_summing_to_one() -> None:
    feats = _support.build_features(_labeled_frame(), meta=LCMSFeatures.Meta(polarity="negative"))
    out = IsotopeCorrection().run(
        {"features": _support.features_collection(feats)},
        BlockConfig(params={"mode": "dual", "resolution": 140000, "c13_purity": 1.0, "h2n15_purity": 1.0}),
    )
    assert set(out) == {"corrected", "mid", "pool_size"}
    mid = _support.features_pandas(list(out["mid"])[0])
    assert {"Compound", "C13", "H2"}.issubset(mid.columns)
    sample = [c for c in mid.columns if c not in ("Compound", "C13", "H2")][0]
    total = mid.groupby("Compound")[sample].sum().iloc[0]
    assert abs(total - 1.0) < 1e-6
