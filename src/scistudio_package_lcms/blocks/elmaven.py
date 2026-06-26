"""El-MAVEN AppBlock — open mzML files in El-MAVEN, collect the peak export.

El-MAVEN is an interactive desktop peak picker. This block opens the user's
mzML inputs in El-MAVEN (via the core :class:`AppBlock` file-exchange machinery)
and, when the user exports a peak table into the watched output directory,
parses that export into a typed :class:`LCMSFeatures` so downstream blocks
receive structured data rather than an opaque file.

The launch / watch / cleanup lifecycle is inherited unchanged from core
``AppBlock``; this subclass only declares the El-MAVEN ports and turns the
collected export files into ``LCMSFeatures`` (reusing the same parser as the
standalone :class:`~scistudio_package_lcms.blocks.load_peak_table.LoadPeakTable`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from scistudio.blocks.app.app_block import AppBlock
from scistudio.blocks.base.config import BlockConfig
from scistudio.blocks.base.ports import InputPort, OutputPort
from scistudio.blocks.base.state import ExecutionMode
from scistudio.core.types.artifact import Artifact
from scistudio.core.types.collection import Collection

from scistudio_package_lcms.blocks.load_peak_table import features_from_frame, read_peak_table
from scistudio_package_lcms.types import LCMSFeatures


class ElMaven(AppBlock):
    """Open mzML inputs in El-MAVEN and collect the exported peak table.

    Inputs are mzML files (opaque :class:`Artifact` blobs); the user curates
    peaks in El-MAVEN and exports a CSV/TSV, which this block parses into
    :class:`LCMSFeatures`.
    """

    type_name: ClassVar[str] = "lcms.elmaven"
    name: ClassVar[str] = "El-MAVEN"
    description: ClassVar[str] = "Open mzML files in El-MAVEN; collect the exported peak table as LCMSFeatures."
    version: ClassVar[str] = "0.1.0"
    subcategory: ClassVar[str] = "interactive"

    #: Default executable; override per-machine via the ``app_command`` config.
    app_command: ClassVar[str] = "elmaven"
    execution_mode: ClassVar[ExecutionMode] = ExecutionMode.EXTERNAL
    output_patterns: ClassVar[list[str]] = ["*.csv", "*.tab", "*.tsv"]

    input_ports: ClassVar[list[InputPort]] = [
        InputPort(
            name="mzml",
            accepted_types=[Artifact],
            is_collection=True,
            required=True,
            description="mzML file(s) to open in El-MAVEN.",
        ),
    ]
    output_ports: ClassVar[list[OutputPort]] = [
        OutputPort(
            name="peaks",
            accepted_types=[LCMSFeatures],
            is_collection=True,
            required=False,
            description="Peak table(s) exported from El-MAVEN.",
        ),
    ]

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "polarity": {
                "type": "string",
                "enum": ["positive", "negative", "unknown"],
                "default": "unknown",
                "title": "Acquisition polarity",
            },
        },
    }

    def run(self, inputs: dict[str, Collection], config: BlockConfig) -> dict[str, Collection]:
        """Launch El-MAVEN (core machinery) then parse exports to LCMSFeatures."""
        raw = super().run(inputs, config)
        features = self._features_from_outputs(raw, config)
        return {"peaks": Collection(features, item_type=LCMSFeatures)}

    def _features_from_outputs(self, raw: dict[str, Collection], config: BlockConfig) -> list[LCMSFeatures]:
        """Parse every collected output item into an :class:`LCMSFeatures`.

        Core ``AppBlock.run`` returns the exported files as ``Artifact``
        collections (keyed by file stem when no port editor is used). Items
        already typed as ``LCMSFeatures`` (e.g. via a future format capability)
        pass through unchanged.
        """
        polarity_raw = str(config.get("polarity", "unknown"))
        polarity = None if polarity_raw == "unknown" else polarity_raw

        out: list[LCMSFeatures] = []
        for collection in raw.values():
            for item in collection:
                if isinstance(item, LCMSFeatures):
                    out.append(item)
                    continue
                if isinstance(item, Artifact) and item.file_path is not None:
                    path = Path(item.file_path)
                    frame = read_peak_table(path)
                    feats = features_from_frame(frame, polarity=polarity, source_tool="elmaven", source_file=path.name)
                    out.append(self._auto_flush(feats))
        return out


__all__ = ["ElMaven"]
