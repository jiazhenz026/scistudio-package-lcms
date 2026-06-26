"""Contract-shape tests: entry-point callables return the contracted types."""

from __future__ import annotations

from scistudio.blocks.base.block import Block
from scistudio.blocks.base.package_info import PackageInfo

import scistudio_package_lcms as pkg
from scistudio_package_lcms.types import ExampleSeries


def test_get_block_package_shape() -> None:
    info, blocks = pkg.get_block_package()
    assert isinstance(info, PackageInfo)
    for block in blocks:
        assert isinstance(block, type) and issubclass(block, Block)


def test_get_types_returns_classes() -> None:
    types = pkg.get_types()
    assert ExampleSeries in types
    assert all(isinstance(t, type) for t in types)


def test_get_previewers_returns_list() -> None:
    assert isinstance(pkg.get_previewers(), list)
