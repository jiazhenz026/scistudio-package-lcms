"""Packaging / entry-point contract tests."""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from importlib.metadata import entry_points
from pathlib import Path

import scistudio_blocks_lcms as pkg

DIST = "scistudio-blocks-lcms"
GROUPS = ("scistudio.blocks", "scistudio.types", "scistudio.previewers")
ROOT = Path(__file__).resolve().parent.parent


def _package_entry_points(group: str) -> list:
    return [ep for ep in entry_points(group=group) if (ep.dist and ep.dist.name == DIST)]


def test_block_package_metadata() -> None:
    info, blocks = pkg.get_block_package()
    assert info.name == DIST
    assert blocks, "package must export at least one block"


def test_three_entry_point_groups_declared() -> None:
    for group in GROUPS:
        assert _package_entry_points(group), f"missing entry point in group {group}"


def test_wheel_includes_scistudio_docs_bundle(tmp_path: Path) -> None:
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path)],
        cwd=ROOT,
        check=True,
    )
    wheel = next(tmp_path.glob("*.whl"))

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        prefix = "scistudio_blocks_lcms/_scistudio_docs/"
        assert f"{prefix}manifest.json" in names
        assert f"{prefix}agent-reference/README.md" in names
        assert f"{prefix}api-reference/index.md" in names
        assert f"{prefix}api-reference/mkdocs-reference.md" in names
        assert f"{prefix}api-reference/package-overview.md" in names
        assert f"{prefix}api-reference/public_surface.snapshot.json" in names
        assert f"{prefix}user-guide/README.md" in names
        assert f"{prefix}user-guide/package-overview.md" in names

        manifest = json.loads(archive.read(f"{prefix}manifest.json"))
        api_reference = archive.read(f"{prefix}api-reference/index.md").decode("utf-8")

    assert manifest["package_name"] == DIST
    assert manifest["slug"] == DIST
    assert "| Symbol | Kind | Stability | Since |" in api_reference
    assert "`scistudio_blocks_lcms.types:LCMSFeatureTable`" in api_reference
