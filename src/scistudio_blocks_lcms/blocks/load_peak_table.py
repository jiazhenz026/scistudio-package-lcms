"""Load an El-MAVEN peaks export into an :class:`LCMSFeatureTable`.

A :class:`~scistudio.blocks.io.simple_io.SimpleLoader`: the user points the
block at an El-MAVEN ``*_peaks_*.csv`` (or tab-delimited) export and it reads
the file into the package's :class:`LCMSFeatureTable` via the type's
:meth:`~scistudio_blocks_lcms.types.LCMSFeatureTable.from_elmaven` constructor.
The framework synthesizes the load
:class:`~scistudio.blocks.io.FormatCapability` from the class attributes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar, Literal

from scistudio.blocks.base import BlockConfig, OutputPort
from scistudio.blocks.io import SimpleLoader
from scistudio.core.types import Collection
from scistudio.stability import stable

from scistudio_blocks_lcms.types import LCMSFeatureTable


def _infer_polarity(name: str) -> Literal["positive", "negative"] | None:
    """Infer acquisition polarity from a file name.

    El-MAVEN does not record polarity in the export, but acquisition pipelines
    conventionally name files ``*_negative_*`` / ``*_positive_*`` (the reference
    flux pipeline does). Returns ``None`` when the name says nothing.
    """
    lowered = name.lower()
    has_neg = "negative" in lowered or "_neg" in lowered
    has_pos = "positive" in lowered or "_pos" in lowered
    if has_neg and not has_pos:
        return "negative"
    if has_pos and not has_neg:
        return "positive"
    return None


@stable(since="0.1.0")
class LoadPeakTable(SimpleLoader):
    """Read an El-MAVEN peaks export into an :class:`LCMSFeatureTable`."""

    name: ClassVar[str] = "Load Peak Table"
    description: ClassVar[str] = "Read an El-MAVEN peaks export (CSV/TAB) into an LCMS feature table."

    output_type: ClassVar[type] = LCMSFeatureTable
    extensions: ClassVar[tuple[str, ...]] = (".csv", ".tab", ".tsv")
    format_id: ClassVar[str] = "el_maven_peaks"

    output_ports: ClassVar[list[OutputPort]] = [
        OutputPort(
            name="data",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            description="Loaded LCMS feature table(s) — one per selected file.",
        ),
    ]

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "path": {
                "type": ["string", "array"],
                "items": {"type": "string"},
                "ui_priority": 0,
                "ui_widget": "file_browser",
            },
            "polarity": {
                "type": "string",
                "enum": ["auto", "positive", "negative"],
                "default": "auto",
                "title": "Acquisition Polarity",
                "description": "El-MAVEN exports do not record polarity. 'auto' infers it from the file name.",
                "ui_priority": 1,
            },
        },
        "required": ["path"],
    }

    def load(self, config: BlockConfig, output_dir: str = "") -> Collection:
        """Read one *or several* selected peaks files into a collection of tables.

        The base :class:`SimpleLoader` is single-file; El-MAVEN runs routinely
        export several files (per scan / polarity), so this override accepts a
        ``path`` that is a single string or a list and loads each into its own
        :class:`LCMSFeatureTable`. The result is always a :class:`Collection`
        (the loader's output port is a collection), so a one-file load is a
        one-item collection.
        """
        raw = config.get("path")
        entries = list(raw) if isinstance(raw, (list, tuple)) else [raw]
        params = dict(config.params)
        tables = [
            self.load_file(Path(entry), params)
            for entry in entries
            if entry is not None and not (isinstance(entry, str) and not entry.strip())
        ]
        if not tables:
            raise ValueError("LoadPeakTable requires at least one file path in config.params['path'].")
        return Collection(tables, item_type=LCMSFeatureTable)

    def load_file(self, path: Path, config: dict[str, Any]) -> LCMSFeatureTable:
        """Read the peaks file at *path* into an :class:`LCMSFeatureTable`."""
        import pandas as pd

        separator = "\t" if path.suffix.lower() in (".tab", ".tsv") else ","
        frame = pd.read_csv(path, sep=separator)

        choice = str(config.get("polarity") or "auto").lower()
        if choice == "positive":
            polarity: Literal["positive", "negative"] | None = "positive"
        elif choice == "negative":
            polarity = "negative"
        else:
            polarity = _infer_polarity(path.name)

        # Record the source file on Meta (provenance) and the file stem as the
        # display name. Core's resolver (#1812) names the table from these, and
        # LCMSFeatureTable.from_wide(source=…) carries them to derived tables, so
        # the whole pipeline keeps the file's identity without per-block naming.
        table = LCMSFeatureTable.from_elmaven(frame, polarity=polarity, source_file=path.name)
        table.user["sheet_name"] = path.stem
        table.user["display_name"] = path.stem
        return table


__all__ = ["LoadPeakTable"]
