"""Block exports for the example package.

``BLOCKS`` is the single source of truth for which block classes the package
registers. ``get_blocks()`` in the package root returns ``list(BLOCKS)``.
"""

from __future__ import annotations

from scistudio_package_lcms.blocks.example import ExampleBlock

BLOCKS: tuple[type, ...] = (ExampleBlock,)

__all__ = ["BLOCKS", "ExampleBlock"]
