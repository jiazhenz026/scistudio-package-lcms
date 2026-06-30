"""ADR-052 §13.1 developer-facing contract tests.

These pin the self-enforcing contract the template ships (spec §13.3): the MUST
skeletons raise until implemented, every public symbol carries an ADR-052 §5
stability marker against the package's own version line, and the example type
satisfies the §13.1 member set. They run the *same* ``_validate_reuse_surface``
the contract script and CI use, so the test and the gate cannot disagree.

When you implement a skeleton (``LCMSFeatureTable.from_elmaven`` /
``describe_public_api``), replace the matching ``raises(NotImplementedError)``
test with one that asserts your real behavior.
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from types import ModuleType

import pandas as pd
import pytest
from scistudio.core.types import DataObject
from scistudio.stability import get_stability

import scistudio_blocks_lcms as pkg
from scistudio_blocks_lcms.blocks import ExampleBlock
from scistudio_blocks_lcms.types import LCMSFeatureTable


def _elmaven_frame() -> pd.DataFrame:
    """A minimal El-MAVEN peaks frame: two annotation columns + two samples."""
    return pd.DataFrame(
        {
            "isotopeLabel": ["C12 PARENT", "C13-label-1"],
            "medMz": [180.066, 181.070],
            "medRt": [10.07, 10.06],
            "compound": ["L-Tyrosine", "L-Tyrosine"],
            "Sample_A": [1608868.0, 161615.45],
            "Sample_B": [1743866.38, 163117.81],
        }
    )


def _load_validator() -> ModuleType:
    """Import ``scripts/validate_contract.py`` as a module (it is not a package)."""
    path = Path(__file__).resolve().parent.parent / "scripts" / "validate_contract.py"
    spec = importlib.util.spec_from_file_location("validate_contract", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_reuse_surface_validator_passes() -> None:
    """The shipped template satisfies the package-agnostic §13.1 validator."""
    validator = _load_validator()
    # Raises SystemExit on any violation; passing means the surface is compliant.
    validator._validate_reuse_surface("scistudio_blocks_lcms", pkg.get_types())


def test_from_elmaven_packs_a_feature_table() -> None:
    """The MUST-shape domain constructor packs an El-MAVEN frame into the type."""
    table = LCMSFeatureTable.from_elmaven(_elmaven_frame(), polarity="negative")

    assert isinstance(table, LCMSFeatureTable)
    assert table.row_count == 2
    assert table.columns is not None and "Sample_A" in table.columns
    # The annotation/sample split, polarity, software, and label flag travel on Meta.
    meta = table.meta
    assert meta.sample_columns == ("Sample_A", "Sample_B")
    assert meta.annotation_columns == ("medMz", "medRt", "isotopeLabel", "compound")
    assert meta.polarity == "negative"
    assert meta.software == "El-MAVEN"
    assert meta.labeled is True


def test_from_elmaven_rejects_a_non_peaks_frame() -> None:
    """A frame with no El-MAVEN annotation columns is not a peaks export."""
    with pytest.raises(ValueError, match="annotation columns"):
        LCMSFeatureTable.from_elmaven(pd.DataFrame({"a": [1], "b": [2]}))


def test_describe_public_api_is_unimplemented_skeleton() -> None:
    """The discovery hook (ADR-052 §4.4) raises until the author fills it in."""
    with pytest.raises(NotImplementedError):
        pkg.describe_public_api()


def test_feature_table_contract_members() -> None:
    """``LCMSFeatureTable`` satisfies the §13.1 member set."""
    # Public at the package top level — never a deep import path.
    assert pkg.LCMSFeatureTable is LCMSFeatureTable
    # Subclasses a core DataObject.
    assert issubclass(LCMSFeatureTable, DataObject)
    # Typed metadata schema lives on the type.
    assert isinstance(LCMSFeatureTable.Meta, type)
    # The domain constructor is a classmethod ON the type, not a free function.
    assert isinstance(inspect.getattr_static(LCMSFeatureTable, "from_elmaven"), classmethod)
    # Never shadows the inherited ergonomic accessors (spec §10).
    assert "to_pandas" not in vars(LCMSFeatureTable)
    assert "to_numpy" not in vars(LCMSFeatureTable)


def test_public_api_carries_stability_markers() -> None:
    """Every public symbol carries an ADR-052 §5 tier + ``Since`` on the package line."""
    stable_symbols = (
        pkg.LCMSFeatureTable,
        LCMSFeatureTable.Meta,
        LCMSFeatureTable.from_elmaven,
        LCMSFeatureTable.from_wide,
        ExampleBlock,
        pkg.get_types,
        pkg.get_block_package,
        pkg.get_blocks,
        pkg.get_package_info,
        pkg.get_previewers,
    )
    for symbol in stable_symbols:
        info = get_stability(symbol)
        assert info is not None, f"{symbol!r} carries no stability marker"
        assert info.tier == "stable"
        assert info.since == pkg.__version__

    # Discovery is provisional — its manifest shape is still settling (§4.4).
    discovery = get_stability(pkg.describe_public_api)
    assert discovery is not None
    assert discovery.tier == "provisional"
    assert discovery.since == pkg.__version__
