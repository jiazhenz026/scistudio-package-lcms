"""SciStudio LCMS package — LC-MS metabolomics & isotope-tracing blocks.

Extends the SciStudio core runtime through three entry points discovered at
startup:

- ``scistudio.blocks``     -> :func:`get_block_package`
- ``scistudio.types``      -> :func:`get_types`
- ``scistudio.previewers`` -> :func:`scistudio_package_lcms.previewers.get_previewers`
"""

from __future__ import annotations

from scistudio.blocks.base.package_info import PackageInfo

from scistudio_package_lcms.blocks import BLOCKS
from scistudio_package_lcms.previewers import get_previewers
from scistudio_package_lcms.types import LCMSFeatures, get_types

__version__ = "0.1.0"


def get_package_info() -> PackageInfo:
    """Return package metadata for the ``scistudio.blocks`` registry."""
    return PackageInfo(
        name="scistudio-package-lcms",
        description="LC-MS metabolomics and isotope-tracing blocks for SciStudio.",
        author="SciStudio Contributors",
        version=__version__,
    )


def get_blocks() -> list[type]:
    """Return the package's exported concrete block classes."""
    return list(BLOCKS)


def get_block_package() -> tuple[PackageInfo, list[type]]:
    """Return package metadata and block classes for ``scistudio.blocks``."""
    return get_package_info(), get_blocks()


__all__ = [
    "LCMSFeatures",
    "__version__",
    "get_block_package",
    "get_blocks",
    "get_package_info",
    "get_previewers",
    "get_types",
]
