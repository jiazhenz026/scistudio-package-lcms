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

Every public symbol carries an ADR-052 §5 stability marker (``stable`` /
``provisional``) with a ``Since`` against **this package's** version line, read
back by the contract validator, the surface freeze test, and the generated
reference. See ``docs/package-overview.md`` for the developer-facing contract.
"""

from __future__ import annotations

from typing import Any

from scistudio.blocks.base import PackageInfo, PackageOtaSource
from scistudio.stability import provisional, stable

from scistudio_package_lcms.blocks import BLOCKS
from scistudio_package_lcms.previewers import get_previewers
from scistudio_package_lcms.types import LCMSFeatureTable, get_types

__version__ = "0.1.0"

# OTA hot-update source (#1784). The in-app Package Manager reads this to check
# for newer releases. Keep these constants in sync with the
# ``[tool.scistudio.ota]`` table in pyproject.toml (the publish-time source of
# truth): ``scripts/validate_contract.py`` enforces that they match, and
# ``scripts/ota_publish.py`` publishes to this exact manifest URL.
OTA_MANIFEST_URL = "https://github.com/jiazhenz026/scistudio-package-lcms/releases/download/ota-alpha/manifest.json"
OTA_CHANNEL = "alpha"


@stable(since="0.1.0")
def get_package_info() -> PackageInfo:
    """Return package metadata for the ``scistudio.blocks`` registry."""
    return PackageInfo(
        name="scistudio-package-lcms",
        description="SciStudio LCMS package.",
        author="SciStudio Contributors",
        version=__version__,
        ota=PackageOtaSource(manifest_url=OTA_MANIFEST_URL, channel=OTA_CHANNEL),
    )


@stable(since="0.1.0")
def get_blocks() -> list[type]:
    """Return the package's exported concrete block classes."""
    return list(BLOCKS)


@stable(since="0.1.0")
def get_block_package() -> tuple[PackageInfo, list[type]]:
    """Return package metadata and block classes for ``scistudio.blocks``."""
    return get_package_info(), get_blocks()


@provisional(since="0.1.0")
def describe_public_api() -> dict[str, Any]:
    """Enumerate the package's public reuse surface (ADR-052 §4.4 discovery).

    The discovery hook an author or the embedded agent calls to learn *what
    public types and constructors a package exports* without reading its source
    — the failure mode behind #1817. It returns a manifest of the package's
    developer-facing surface (its public types, their domain constructors, and
    any public helpers), each with the ADR-052 §5 tier and ``Since`` already on
    the symbol.

    The exact manifest schema and the cross-package enumerator
    (a ``scistudio.plugins``-style core API and/or an MCP tool) are still
    settling, so this hook is ``provisional``. The template ships it as a
    skeleton that raises (ADR-052 §13.3); implement it to return your manifest
    — typically by reflecting over this package's ``__all__`` and reading each
    symbol's :func:`scistudio.stability.get_stability` marker.
    """
    raise NotImplementedError(
        "describe_public_api is an ADR-052 §4.4 discovery skeleton; implement "
        "it to return this package's public reuse-surface manifest."
    )


__all__ = [
    "LCMSFeatureTable",
    "__version__",
    "describe_public_api",
    "get_block_package",
    "get_blocks",
    "get_package_info",
    "get_previewers",
    "get_types",
]
