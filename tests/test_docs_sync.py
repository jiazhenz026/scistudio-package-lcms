"""Docs/code sync: every registered block is documented in README + overview."""

from __future__ import annotations

from pathlib import Path

import scistudio_package_lcms as pkg

_ROOT = Path(__file__).resolve().parent.parent


def test_readme_lists_every_block() -> None:
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    _, blocks = pkg.get_block_package()
    for block in blocks:
        assert block.__name__ in readme, f"block {block.__name__!r} missing from README.md"


def test_overview_lists_every_block() -> None:
    overview = (_ROOT / "docs" / "package-overview.md").read_text(encoding="utf-8")
    # Class names appear in the overview catalog code spans.
    _, blocks = pkg.get_block_package()
    for block in blocks:
        assert block.__name__ in overview, f"block {block.__name__!r} missing from package-overview.md"
