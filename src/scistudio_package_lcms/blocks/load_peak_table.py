"""Load an LC-MS peak table (El-MAVEN / generic CSV) as :class:`LCMSFeatures`.

A ``direction="input"`` :class:`IOBlock`: it reads a peak-picker export from
disk verbatim (every column the tool produced is kept) and tags it with
table-level provenance. This is the standalone file-ingest entry point; the
El-MAVEN AppBlock reuses the same parser through a format capability.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pandas as pd
from scistudio.blocks.base.config import BlockConfig
from scistudio.blocks.base.ports import OutputPort
from scistudio.blocks.io.io_block import IOBlock
from scistudio.core.types.base import DataObject
from scistudio.core.types.collection import Collection

from scistudio_package_lcms import _support
from scistudio_package_lcms.types import LCMSFeatures

#: Columns whose presence marks an isotope-tracing (labeled) table.
_LABELED_MARKERS = ("isotopeLabel", "C13", "13C#", "2H#", "H2")


def read_peak_table(path: Path, delimiter: str = "auto") -> pd.DataFrame:
    """Read a peak-table file into a pandas frame, verbatim.

    ``delimiter`` is ``"comma"`` / ``"tab"`` / ``"auto"``; ``"auto"`` infers
    tab for ``.tab`` / ``.tsv`` / ``.txt`` and comma otherwise.
    """
    sep = {"comma": ",", "tab": "\t"}.get(delimiter)
    if sep is None:
        sep = "\t" if path.suffix.lower() in {".tab", ".tsv", ".txt"} else ","
    return pd.read_csv(path, sep=sep)


def features_from_frame(
    frame: pd.DataFrame,
    *,
    polarity: str | None = None,
    source_tool: str | None = None,
    source_file: str | None = None,
) -> LCMSFeatures:
    """Wrap a raw peak-table frame in :class:`LCMSFeatures` with provenance Meta."""
    labeled = any(marker in frame.columns for marker in _LABELED_MARKERS)
    meta = LCMSFeatures.Meta(
        polarity=polarity,
        source_tool=source_tool,
        source_file=source_file,
        labeled=labeled,
    )
    return _support.build_features(frame, meta=meta)


class LoadPeakTable(IOBlock):
    """Load an LC-MS peak table (El-MAVEN / generic CSV) into ``LCMSFeatures``.

    The table is kept exactly as the peak picker exported it; only table-level
    provenance (polarity, source tool, source file) is attached as typed Meta.
    """

    type_name: ClassVar[str] = "lcms.load_peak_table"
    name: ClassVar[str] = "Load Peak Table"
    description: ClassVar[str] = "Load an LC-MS peak table (El-MAVEN / generic CSV) as LCMSFeatures."
    version: ClassVar[str] = "0.1.0"
    direction: ClassVar[str] = "input"

    output_ports: ClassVar[list[OutputPort]] = [
        OutputPort(name="features", accepted_types=[LCMSFeatures], description="Loaded peak table."),
    ]

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "ui_widget": "file_browser",
                "ui_priority": 0,
                "title": "Peak table file",
            },
            "source_tool": {
                "type": "string",
                "enum": ["elmaven", "mzmine", "generic"],
                "default": "elmaven",
                "title": "Source tool",
            },
            "polarity": {
                "type": "string",
                "enum": ["positive", "negative", "unknown"],
                "default": "unknown",
                "title": "Acquisition polarity",
            },
            "delimiter": {
                "type": "string",
                "enum": ["auto", "comma", "tab"],
                "default": "auto",
                "title": "Delimiter",
            },
        },
        "required": ["path"],
    }

    def load(self, config: BlockConfig, output_dir: str = "") -> DataObject | Collection:
        raw = config.get("path")
        if not raw:
            raise ValueError(f"{self.name}: 'path' is required")
        path = Path(str(raw))
        if not path.is_file():
            raise FileNotFoundError(f"{self.name}: peak table not found: {path}")

        frame = read_peak_table(path, str(config.get("delimiter", "auto")))
        polarity = str(config.get("polarity", "unknown"))
        return features_from_frame(
            frame,
            polarity=None if polarity == "unknown" else polarity,
            source_tool=str(config.get("source_tool", "elmaven")),
            source_file=path.name,
        )

    def save(self, obj: DataObject | Collection, config: BlockConfig) -> None:
        """Load-only block; saving is not supported."""
        raise NotImplementedError(f"{self.name} is a load-only block; it does not save.")


__all__ = ["LoadPeakTable", "features_from_frame", "read_peak_table"]
