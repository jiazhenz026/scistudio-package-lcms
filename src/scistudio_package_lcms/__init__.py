"""Example SciStudio package — the reference layout for a plugin package.

Copy this template ("Use this template" on GitHub), then:

  1. Rename ``src/scistudio_package_lcms`` to your module name.
  2. Update the distribution name and the three entry points in
     ``pyproject.toml``.
  3. Replace the example type/block/previewer with your own.

Three entry points register the package with SciStudio core (mirroring
``scistudio-blocks-spectroscopy``):

- ``scistudio.blocks``     -> :func:`get_block_package`
- ``scistudio.types``      -> :func:`get_types`
- ``scistudio.previewers`` -> :func:`scistudio_package_lcms.previewers.get_previewers`
"""

from __future__ import annotations

from scistudio.blocks.base.package_info import PackageInfo

from scistudio_package_lcms.blocks import BLOCKS
from scistudio_package_lcms.previewers import get_previewers
from scistudio_package_lcms.types import ExampleSeries, get_types

__version__ = "0.1.0"


def get_package_info() -> PackageInfo:
    """Return package metadata for the ``scistudio.blocks`` registry."""
    return PackageInfo(
        name="scistudio-package-lcms",
        description="SciStudio LCMS package.",
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
    "ExampleSeries",
    "__version__",
    "get_block_package",
    "get_blocks",
    "get_package_info",
    "get_previewers",
    "get_types",
]
