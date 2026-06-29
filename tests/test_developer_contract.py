"""ADR-052 §13.1 developer-facing contract tests.

These pin the self-enforcing contract the template ships (spec §13.3): the MUST
skeletons raise until implemented, every public symbol carries an ADR-052 §5
stability marker against the package's own version line, and the example type
satisfies the §13.1 member set. They run the *same* ``_validate_reuse_surface``
the contract script and CI use, so the test and the gate cannot disagree.

When you implement a skeleton (``ExampleSeries.from_arrays`` /
``describe_public_api``), replace the matching ``raises(NotImplementedError)``
test with one that asserts your real behavior.
"""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
from types import ModuleType

import pytest
from scistudio.core.types.base import DataObject
from scistudio.stability import get_stability

import scistudio_package_lcms as pkg
from scistudio_package_lcms.blocks import ExampleBlock
from scistudio_package_lcms.types import ExampleSeries


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
    validator._validate_reuse_surface("scistudio_package_lcms", pkg.get_types())


def test_from_arrays_is_unimplemented_skeleton() -> None:
    """The MUST-shape domain constructor raises until the author fills it in."""
    with pytest.raises(NotImplementedError):
        ExampleSeries.from_arrays([0, 1, 2], [10.0, 20.0, 30.0])


def test_describe_public_api_is_unimplemented_skeleton() -> None:
    """The discovery hook (ADR-052 §4.4) raises until the author fills it in."""
    with pytest.raises(NotImplementedError):
        pkg.describe_public_api()


def test_example_series_contract_members() -> None:
    """``ExampleSeries`` satisfies the §13.1 member set."""
    # Public at the package top level — never a deep import path.
    assert pkg.ExampleSeries is ExampleSeries
    # Subclasses a core DataObject.
    assert issubclass(ExampleSeries, DataObject)
    # Typed metadata schema lives on the type.
    assert isinstance(ExampleSeries.Meta, type)
    # The domain constructor is a classmethod ON the type, not a free function.
    assert isinstance(inspect.getattr_static(ExampleSeries, "from_arrays"), classmethod)
    # Never shadows the inherited ergonomic accessors (spec §10).
    assert "to_pandas" not in vars(ExampleSeries)
    assert "to_numpy" not in vars(ExampleSeries)


def test_public_api_carries_stability_markers() -> None:
    """Every public symbol carries an ADR-052 §5 tier + ``Since`` on the package line."""
    stable_symbols = (
        pkg.ExampleSeries,
        ExampleSeries.Meta,
        ExampleSeries.from_arrays,
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
