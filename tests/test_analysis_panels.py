"""The downstream interactive-panel assets are wired and well-formed.

Covers the panels added with the downstream-analysis blocks (Normalization,
GroupStatistics, ConsumptionRelease), mirroring ``test_background_panel.py``:
manifest consistency, the asset is present and packaged, and it is valid
JavaScript (``node --check`` when node is available).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scistudio_blocks_lcms.blocks import ConsumptionRelease, GroupStatistics, Normalization

_INTERACTIVE_BLOCKS = [Normalization, GroupStatistics, ConsumptionRelease]


def _panel_file(block: type) -> Path:
    manifest = block.interactive_panel
    assert manifest.asset_root is not None
    filename = manifest.module_url.rsplit("/", 1)[-1]
    return Path(manifest.asset_root) / filename


@pytest.mark.parametrize("block", _INTERACTIVE_BLOCKS)
def test_panel_manifest_is_consistent(block: type) -> None:
    manifest = block.interactive_panel
    assert manifest.panel_id in manifest.module_url
    assert manifest.module_url.startswith("/api/blocks/panels/")
    assert manifest.api_version == "1"


@pytest.mark.parametrize("block", _INTERACTIVE_BLOCKS)
def test_panel_asset_exists_and_is_packaged(block: type) -> None:
    panel = _panel_file(block)
    assert panel.is_file(), f"panel asset missing at {panel}"
    text = panel.read_text(encoding="utf-8")
    assert "export default" in text and "apiVersion" in text and "mount" in text
    assert "host.confirm" in text


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available to syntax-check the ES module")
@pytest.mark.parametrize("block", _INTERACTIVE_BLOCKS)
def test_panel_is_valid_javascript(block: type) -> None:
    proc = subprocess.run(["node", "--check", str(_panel_file(block))], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
