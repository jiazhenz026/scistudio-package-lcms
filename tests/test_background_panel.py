"""The BackgroundSubtraction interactive panel asset is wired and well-formed."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scistudio_blocks_lcms.blocks import BackgroundSubtraction


def _panel_file() -> Path:
    manifest = BackgroundSubtraction.interactive_panel
    assert manifest.asset_root is not None
    # module_url ends with the served filename under asset_root.
    filename = manifest.module_url.rsplit("/", 1)[-1]
    return Path(manifest.asset_root) / filename


def test_panel_manifest_is_consistent() -> None:
    manifest = BackgroundSubtraction.interactive_panel
    assert manifest.panel_id in manifest.module_url
    assert manifest.module_url.startswith("/api/blocks/panels/")  # same-origin serve route
    assert manifest.api_version == "1"


def test_panel_asset_exists_and_is_packaged() -> None:
    panel = _panel_file()
    assert panel.is_file(), f"panel asset missing at {panel}"
    text = panel.read_text(encoding="utf-8")
    assert "export default" in text and "apiVersion" in text and "mount" in text
    assert "host.confirm" in text  # returns the decision the block's run() reads


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available to syntax-check the ES module")
def test_panel_is_valid_javascript() -> None:
    proc = subprocess.run(["node", "--check", str(_panel_file())], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
