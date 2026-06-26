"""Example package previewers (optional).

This template ships **no live previewer**, so CI stays green out of the box and
``get_previewers`` returns an empty list. Previewers are optional: a package
that adds none still registers this entry point returning ``[]``.

To add a previewer, model it on ``scistudio-blocks-spectroscopy`` and the core
guide ``docs/block-development/previewers-and-plots.md``:

  1. Write backend provider callables (a ``providers.py`` module).
  2. Ship the frontend asset under ``assets/`` (e.g. ``viewer.js``) and list it
     in ``[tool.hatch.build.targets.wheel].artifacts`` in ``pyproject.toml``.
  3. Return ``PreviewerSpec`` records here, for example::

         from scistudio.previewers.models import (
             PREVIEWER_API_VERSION, FrontendManifest, OwnerKind, PreviewerSpec,
         )

         def get_previewers() -> list[PreviewerSpec]:
             return [PreviewerSpec(previewer_id="example.series.viewer", ...)]
"""

from __future__ import annotations

from typing import Any


def get_previewers() -> list[Any]:
    """Return the package's previewer specs for ``scistudio.previewers``.

    Empty by default. Replace with a list of ``PreviewerSpec`` records.
    """
    return []


__all__ = ["get_previewers"]
