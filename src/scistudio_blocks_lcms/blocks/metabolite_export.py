"""Annotate compounds with database IDs and emit an export-ready table.

External pathway-enrichment tools (MetaboAnalyst, Metaboverse) key on standard
metabolite IDs, not raw compound names. This block joins a user-supplied
``compound → ID`` map (e.g. an ``HMDB`` lookup) onto any compound-keyed table —
a statistics table from :class:`~scistudio_blocks_lcms.blocks.group_statistics.GroupStatistics`,
or a feature table — and returns the same table with the ID column added,
dropping unmapped compounds by default (those tools reject rows without an ID).

The enrichment itself is left to the external tool; this block produces the
export-ready table it consumes. Output is the core
:class:`~scistudio.core.types.DataFrame`.
"""

from __future__ import annotations

from typing import Any, ClassVar

from scistudio.blocks.base import BlockConfig, InputPort, OutputPort
from scistudio.blocks.process import ProcessBlock
from scistudio.core.types import Collection, DataFrame
from scistudio.stability import stable

from scistudio_blocks_lcms.blocks._results import dataframe_from_pandas
from scistudio_blocks_lcms.types import LCMSFeatureTable


def _to_frame(obj: Any) -> Any:
    """``to_pandas`` for either a single object or the first item of a Collection."""
    target = obj[0] if isinstance(obj, Collection) else obj
    return target.to_pandas()


def _annotate(
    table: Any,
    id_map: Any,
    *,
    compound_column: str,
    map_name_column: str,
    map_id_column: str,
    output_id_column: str,
    require_id: bool,
) -> Any:
    """Join ``compound -> id`` onto *table*, placing the ID column right after the compound."""
    result = table.copy()
    name_to_id = {str(name): value for name, value in zip(id_map[map_name_column], id_map[map_id_column], strict=False)}
    result[output_id_column] = result[compound_column].astype(str).map(name_to_id)
    if require_id:
        result = result[result[output_id_column].notna()].reset_index(drop=True)
    # Move the ID column to just after the compound column for a tidy export.
    cols = [c for c in result.columns if c != output_id_column]
    insert_at = cols.index(compound_column) + 1 if compound_column in cols else len(cols)
    ordered = cols[:insert_at] + [output_id_column] + cols[insert_at:]
    return result[ordered]


@stable(since="0.1.0")
class MetaboliteExport(ProcessBlock):
    """Annotate compounds with database IDs (e.g. HMDB) and emit an export-ready table."""

    name: ClassVar[str] = "Metabolite Export"
    description: ClassVar[str] = "Join a compound→ID map (e.g. HMDB) onto a table for MetaboAnalyst / Metaboverse."
    version: ClassVar[str] = "0.1.0"
    algorithm: ClassVar[str] = "metabolite_export"

    input_ports: ClassVar[list[InputPort]] = [
        InputPort(
            name="table",
            accepted_types=[LCMSFeatureTable, DataFrame],
            is_collection=False,
            required=True,
            description="A compound-keyed table (statistics or features) to annotate.",
        ),
        InputPort(
            name="id_map",
            accepted_types=[DataFrame, LCMSFeatureTable],
            is_collection=False,
            required=True,
            description="User-supplied compound→ID lookup (e.g. Name, HMDB).",
        ),
    ]
    output_ports: ClassVar[list[OutputPort]] = [
        OutputPort(
            name="exported",
            accepted_types=[DataFrame],
            is_collection=False,
            description="The input table with the database ID column added (unmapped rows dropped).",
        ),
    ]

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "compound_column": {"type": "string", "default": "compound", "title": "Table: compound column"},
            "map_name_column": {"type": "string", "default": "compound", "title": "ID map: name column"},
            "map_id_column": {"type": "string", "default": "HMDB", "title": "ID map: ID column"},
            "output_id_column": {"type": "string", "default": "HMDB", "title": "Output ID column name"},
            "require_id": {
                "type": "boolean",
                "default": True,
                "title": "Drop compounds with no ID",
            },
        },
    }

    def run(self, inputs: dict[str, Any], config: BlockConfig) -> dict[str, Any]:
        """Annotate the input table with database IDs from the supplied map."""
        table = _to_frame(inputs["table"])
        id_map = _to_frame(inputs["id_map"])

        compound_column = str(config.get("compound_column", "compound"))
        map_name_column = str(config.get("map_name_column", "compound"))
        map_id_column = str(config.get("map_id_column", "HMDB"))
        for column, where in ((compound_column, "table"), (map_name_column, "id_map"), (map_id_column, "id_map")):
            frame = table if where == "table" else id_map
            if column not in frame.columns:
                raise ValueError(f"{where} has no {column!r} column (columns: {list(frame.columns)})")

        annotated = _annotate(
            table,
            id_map,
            compound_column=compound_column,
            map_name_column=map_name_column,
            map_id_column=map_id_column,
            output_id_column=str(config.get("output_id_column", "HMDB")),
            require_id=bool(config.get("require_id", True)),
        )
        return {"exported": self._auto_flush(dataframe_from_pandas(annotated))}


__all__ = ["MetaboliteExport"]
