"""Packaging / entry-point contract tests."""

from __future__ import annotations

from importlib.metadata import entry_points

import scistudio_blocks_lcms as pkg

DIST = "scistudio-blocks-lcms"
GROUPS = ("scistudio.blocks", "scistudio.types", "scistudio.previewers")


def _package_entry_points(group: str) -> list:
    return [ep for ep in entry_points(group=group) if (ep.dist and ep.dist.name == DIST)]


def test_block_package_metadata() -> None:
    info, blocks = pkg.get_block_package()
    assert info.name == DIST
    assert blocks, "package must export at least one block"


def test_three_entry_point_groups_declared() -> None:
    for group in GROUPS:
        assert _package_entry_points(group), f"missing entry point in group {group}"
