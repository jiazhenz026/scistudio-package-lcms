"""Block exports for the example package.

``BLOCKS`` is the single source of truth for which block classes the package
registers. ``get_blocks()`` in the package root returns ``list(BLOCKS)``.
"""

from __future__ import annotations

from scistudio_blocks_lcms.blocks.background_subtraction import BackgroundSubtraction
from scistudio_blocks_lcms.blocks.calculate_mid import CalculateMID
from scistudio_blocks_lcms.blocks.consumption_release import ConsumptionRelease
from scistudio_blocks_lcms.blocks.elmaven import ElMaven
from scistudio_blocks_lcms.blocks.example import ExampleBlock
from scistudio_blocks_lcms.blocks.group_statistics import GroupStatistics
from scistudio_blocks_lcms.blocks.isotope_correction import IsotopeCorrection
from scistudio_blocks_lcms.blocks.load_peak_table import LoadPeakTable
from scistudio_blocks_lcms.blocks.log2_mean_center import Log2MeanCenter
from scistudio_blocks_lcms.blocks.metabolite_export import MetaboliteExport
from scistudio_blocks_lcms.blocks.normalization import Normalization

BLOCKS: tuple[type, ...] = (
    ElMaven,
    LoadPeakTable,
    BackgroundSubtraction,
    Normalization,
    Log2MeanCenter,
    GroupStatistics,
    ConsumptionRelease,
    CalculateMID,
    MetaboliteExport,
    IsotopeCorrection,
    ExampleBlock,
)

__all__ = [
    "BLOCKS",
    "BackgroundSubtraction",
    "CalculateMID",
    "ConsumptionRelease",
    "ElMaven",
    "ExampleBlock",
    "GroupStatistics",
    "IsotopeCorrection",
    "LoadPeakTable",
    "Log2MeanCenter",
    "MetaboliteExport",
    "Normalization",
]
