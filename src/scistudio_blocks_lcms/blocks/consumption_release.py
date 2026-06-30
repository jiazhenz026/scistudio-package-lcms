"""Metabolite consumption / release versus a reference group (interactive).

An interactive block (ADR-051): the user assigns sample columns to groups and
picks the *reference* group (fresh / unspent medium, or a ``t0`` sample); the
block then reports, per feature, each sample's difference from the reference
group mean — negative for consumed metabolites, positive for released ones.

An optional ``metadata`` input (a table of per-sample cell numbers) plus a Δt
config turn the raw difference into a per-cell-per-time *rate*
(``delta / (cell_number × Δt)``). Without them, the raw difference is returned.

Output is the core :class:`~scistudio.core.types.DataFrame` (a result table),
one per input feature table.
"""

from __future__ import annotations

from importlib.resources import files
from typing import Any, ClassVar

from scistudio.blocks.base import (
    INTERACTIVE_RESPONSE_KEY,
    BlockConfig,
    ExecutionMode,
    InputPort,
    InteractiveMixin,
    InteractivePrompt,
    OutputPort,
    PanelManifest,
)
from scistudio.blocks.process import ProcessBlock
from scistudio.core.types import Collection, DataFrame
from scistudio.stability import stable

from scistudio_blocks_lcms.blocks._consumption import compute_consumption, suggest_reference_group
from scistudio_blocks_lcms.blocks._group_stats import suggest_groups
from scistudio_blocks_lcms.blocks._naming import derived_name
from scistudio_blocks_lcms.blocks._results import dataframe_from_pandas
from scistudio_blocks_lcms.types import ELMAVEN_ANNOTATION_COLUMNS, LCMSFeatureTable

_PANEL_ID = "scistudio_blocks_lcms.interactive.consumption_release"
_PANEL_ASSET_ROOT = str(files("scistudio_blocks_lcms").joinpath("panels"))


def _sample_columns(item: LCMSFeatureTable, frame: Any) -> list[str]:
    meta = item.meta
    if meta is not None and meta.sample_columns:
        return [c for c in meta.sample_columns if c in frame.columns]
    return [str(c) for c in frame.columns if c not in ELMAVEN_ANNOTATION_COLUMNS]


def _annotation_columns(item: LCMSFeatureTable, frame: Any, samples: list[str]) -> list[str]:
    meta = item.meta
    if meta is not None and meta.annotation_columns:
        return [c for c in meta.annotation_columns if c in frame.columns]
    return [str(c) for c in frame.columns if c not in samples]


def _cell_numbers(metadata: Any, sample_column: str, value_column: str) -> dict[str, float]:
    """Build a ``sample -> cell number`` map from the optional metadata table."""
    if metadata is None:
        return {}
    obj = metadata[0] if isinstance(metadata, Collection) else metadata
    frame = obj.to_pandas()
    if sample_column not in frame.columns or value_column not in frame.columns:
        return {}
    import pandas as pd

    numbers: dict[str, float] = {}
    for _, row in frame.iterrows():
        value = pd.to_numeric(pd.Series([row[value_column]]), errors="coerce").iloc[0]
        if value == value:  # not NaN
            numbers[str(row[sample_column])] = float(value)
    return numbers


@stable(since="0.1.0")
class ConsumptionRelease(InteractiveMixin, ProcessBlock):
    """Per-feature consumption / release versus a reference group, optionally as a rate."""

    name: ClassVar[str] = "Consumption / Release"
    description: ClassVar[str] = "Compare each sample to a reference group; optional cell/time scaling gives a rate."
    version: ClassVar[str] = "0.1.0"
    algorithm: ClassVar[str] = "consumption_release"

    execution_mode: ClassVar[ExecutionMode] = ExecutionMode.INTERACTIVE
    interactive_panel: ClassVar[PanelManifest] = PanelManifest(
        panel_id=_PANEL_ID,
        module_url=f"/api/blocks/panels/{_PANEL_ID}/consumption_release.js",
        asset_root=_PANEL_ASSET_ROOT,
        version="0.1.0",
    )

    input_ports: ClassVar[list[InputPort]] = [
        InputPort(
            name="features",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            required=True,
            description="Feature table(s) of sample intensities.",
        ),
        InputPort(
            name="metadata",
            accepted_types=[DataFrame],
            is_collection=False,
            required=False,
            description="Optional per-sample cell numbers (for a per-cell-per-time rate).",
        ),
    ]
    output_ports: ClassVar[list[OutputPort]] = [
        OutputPort(
            name="rates",
            accepted_types=[DataFrame],
            is_collection=True,
            description="Per-feature consumption (−) / release (+) per sample, or a rate.",
        ),
    ]

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "dt": {"type": "number", "default": 1.0, "title": "Δt (time interval)"},
            "sample_column": {
                "type": "string",
                "default": "sample",
                "title": "Metadata: sample-name column",
            },
            "cell_number_column": {
                "type": "string",
                "default": "cell_number",
                "title": "Metadata: cell-number column",
            },
        },
    }

    def prepare_prompt(self, inputs: dict[str, Any], config: BlockConfig) -> InteractivePrompt:
        """Build one panel tab per table with suggested groups and reference group."""
        features = inputs["features"]
        tables: list[dict[str, Any]] = []
        for i, item in enumerate(features):
            frame = item.to_pandas()
            columns = _sample_columns(item, frame)
            group_map = suggest_groups(columns)
            group_names = list(dict.fromkeys(group_map.values()))
            tables.append(
                {
                    "index": i,
                    "label": f"Table {i + 1}",
                    "columns": columns,
                    "suggestion": {
                        "groups": group_map,
                        "reference_group": suggest_reference_group(group_names),
                    },
                }
            )
        return InteractivePrompt(panel_payload={"tables": tables})

    def run(self, inputs: dict[str, Collection], config: BlockConfig) -> dict[str, Collection]:
        """Compute consumption / release (or rate) for each table."""
        features = inputs["features"]
        cell_numbers = _cell_numbers(
            inputs.get("metadata"),
            str(config.get("sample_column", "sample")),
            str(config.get("cell_number_column", "cell_number")),
        )
        dt = float(config.get("dt", 1.0))

        response = config.get(INTERACTIVE_RESPONSE_KEY)
        response = response if isinstance(response, dict) else {}
        decisions = response.get("tables") if isinstance(response.get("tables"), list) else None

        outputs: list[Any] = []
        for i, item in enumerate(features):
            frame = item.to_pandas()
            samples = _sample_columns(item, frame)
            decision = decisions[i] if decisions and i < len(decisions) and isinstance(decisions[i], dict) else {}
            groups = decision.get("groups") or suggest_groups(samples)
            reference_group = decision.get("reference_group") or suggest_reference_group(
                list(dict.fromkeys(groups.values()))
            )
            if not reference_group:
                raise ValueError(
                    "ConsumptionRelease needs a reference group; none was chosen and none could be guessed "
                    "from the group names. Pick one in the panel."
                )
            out_frame = compute_consumption(
                frame,
                sample_columns=samples,
                groups=groups,
                reference_group=reference_group,
                annotation_columns=_annotation_columns(item, frame, samples),
                cell_numbers=cell_numbers,
                dt=dt,
            )
            rates_table = dataframe_from_pandas(out_frame)
            rates_table.user["display_name"] = derived_name(item, "consumption/release")
            outputs.append(self._auto_flush(rates_table))

        return {"rates": Collection(outputs) if outputs else Collection([], item_type=DataFrame)}


__all__ = ["ConsumptionRelease"]
