"""Save :class:`LCMSFeatureTable`(s) to CSV — one file, or many at once.

A :class:`~scistudio.blocks.io.simple_io.SimpleSaver` is single-object by design.
LCMS workflows routinely carry a *collection* of tables (per scan / polarity, or
the four corrector matrices), so this saver overrides :meth:`save` to accept a
multi-item collection and write one CSV per table. With several tables the
configured ``path`` is treated as a **directory** and each file is named after
the table's ``display_name`` (the #1812 convention the upstream blocks stamp);
a single table writes to ``path`` directly.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, ClassVar

from scistudio.blocks.base import BlockConfig, InputPort
from scistudio.blocks.io import SimpleSaver
from scistudio.core.types import Collection
from scistudio.core.types.base import DataObject
from scistudio.stability import stable

from scistudio_blocks_lcms.types import LCMSFeatureTable


def _safe_filename(name: str, *, fallback: str) -> str:
    """A filesystem-safe stem from a display name (``"scan1 · MID"`` → ``"scan1_MID"``)."""
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "_", str(name)).strip("._-")
    return cleaned or fallback


@stable(since="0.1.0")
class SavePeakTable(SimpleSaver):
    """Write one or several :class:`LCMSFeatureTable`s to CSV."""

    name: ClassVar[str] = "Save Peak Table"
    description: ClassVar[str] = "Write LCMS feature table(s) to CSV — one file, or one per table into a folder."

    input_type: ClassVar[type] = LCMSFeatureTable
    extensions: ClassVar[tuple[str, ...]] = (".csv",)
    format_id: ClassVar[str] = "lcms_feature_csv"

    input_ports: ClassVar[list[InputPort]] = [
        InputPort(
            name="data",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            required=True,
            description="Feature table(s) to write.",
        ),
    ]

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "ui_priority": 0,
                "ui_widget": "file_browser",
                "title": "Output file or folder",
                "description": "A .csv file for a single table, or a folder when saving several tables.",
            },
        },
        "required": ["path"],
    }

    def save(self, obj: DataObject | Collection, config: BlockConfig) -> None:
        """Write a single table to ``path``, or a collection one-CSV-per-table into a folder."""
        items = list(obj) if isinstance(obj, Collection) else [obj]
        tables = [item for item in items if isinstance(item, self.input_type)]
        if not tables:
            raise TypeError(f"{type(self).__name__} expected {self.input_type.__name__}(s) to save.")

        raw = config.get("path")
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            raise ValueError(f"{type(self).__name__} requires a non-empty 'path' in config.params.")
        target = Path(raw)
        params = dict(config.params)

        # Single table to an explicit .csv path: write it there.
        if len(tables) == 1 and target.suffix.lower() == ".csv":
            self.save_file(tables[0], target, params)
            return

        # Several tables (or a folder target): one CSV per table, named by
        # display_name, into the target directory.
        target.mkdir(parents=True, exist_ok=True)
        used: set[str] = set()
        for i, table in enumerate(tables):
            user = getattr(table, "user", None) or {}
            stem = _safe_filename(user.get("display_name") or f"table_{i + 1}", fallback=f"table_{i + 1}")
            unique = stem
            n = 1
            while unique in used:
                n += 1
                unique = f"{stem}_{n}"
            used.add(unique)
            self.save_file(table, target / f"{unique}.csv", params)

    def save_file(self, obj: DataObject, path: Path, config: dict[str, Any]) -> None:
        """Write one feature table to *path* as CSV."""
        if not isinstance(obj, LCMSFeatureTable):
            raise TypeError(f"SavePeakTable expected LCMSFeatureTable, got {type(obj).__name__}.")
        path.parent.mkdir(parents=True, exist_ok=True)
        obj.to_pandas().to_csv(path, index=False)


__all__ = ["SavePeakTable"]
