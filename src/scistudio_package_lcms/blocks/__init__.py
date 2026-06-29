"""Block exports for the example package.

``BLOCKS`` is the single source of truth for which block classes the package
registers. ``get_blocks()`` in the package root returns ``list(BLOCKS)``.
"""

from __future__ import annotations

from scistudio_package_lcms.blocks.background_subtraction import BackgroundSubtraction
from scistudio_package_lcms.blocks.elmaven import ElMaven
from scistudio_package_lcms.blocks.example import ExampleBlock
from scistudio_package_lcms.blocks.isotope_correction import IsotopeCorrection
from scistudio_package_lcms.blocks.load_peak_table import LoadPeakTable

BLOCKS: tuple[type, ...] = (ElMaven, LoadPeakTable, BackgroundSubtraction, IsotopeCorrection, ExampleBlock)

__all__ = [
    "BLOCKS",
    "BackgroundSubtraction",
    "ElMaven",
    "ExampleBlock",
    "IsotopeCorrection",
    "LoadPeakTable",
]
