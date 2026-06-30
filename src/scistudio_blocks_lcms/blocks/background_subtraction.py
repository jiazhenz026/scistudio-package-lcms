"""Interactive background subtraction for LCMS feature tables.

An interactive block (ADR-051): it pauses mid-workflow and opens a panel where
the user assigns each sample column a role and a background, then subtracts each
sample's aggregated background and drops the background columns. One panel tab
per input feature table.

The panel is pre-filled by a name-based heuristic (:mod:`._background_match`) so
the user only corrects the suggestion rather than matching ~100 columns from
scratch. Running without a panel decision (headless) applies the suggestion
directly. Subtraction never clamps negatives — the reference pipeline keeps them.
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
from scistudio.core.types import Collection
from scistudio.stability import stable

from scistudio_blocks_lcms.blocks._background_match import apply_subtraction, suggest
from scistudio_blocks_lcms.types import ELMAVEN_ANNOTATION_COLUMNS, LCMSFeatureTable

_PANEL_ID = "scistudio_blocks_lcms.interactive.background_subtraction"
#: Absolute on-disk dir the backend serves the panel asset from (ADR-051/§7).
#: Resolves to ``src/scistudio_blocks_lcms/panels`` (editable) or the installed
#: package's ``panels/`` dir (wheel).
_PANEL_ASSET_ROOT = str(files("scistudio_blocks_lcms").joinpath("panels"))


def _sample_columns(item: LCMSFeatureTable, frame: Any) -> list[str]:
    """The columns eligible for background matching — the sample (intensity)
    columns only. Annotation columns (m/z, RT, compound, …) are identity, never
    samples or backgrounds, so they are excluded and pass through untouched.
    """
    meta = item.meta
    if meta is not None and meta.sample_columns:
        return [c for c in meta.sample_columns if c in frame.columns]
    return [str(c) for c in frame.columns if c not in ELMAVEN_ANNOTATION_COLUMNS]


@stable(since="0.1.0")
class BackgroundSubtraction(InteractiveMixin, ProcessBlock):
    """Subtract background from sample columns, matching them interactively."""

    name: ClassVar[str] = "Background Subtraction"
    description: ClassVar[str] = "Match sample columns to backgrounds in a panel, then subtract."
    version: ClassVar[str] = "0.1.0"
    algorithm: ClassVar[str] = "background_subtraction"

    execution_mode: ClassVar[ExecutionMode] = ExecutionMode.INTERACTIVE
    interactive_panel: ClassVar[PanelManifest] = PanelManifest(
        panel_id=_PANEL_ID,
        module_url=f"/api/blocks/panels/{_PANEL_ID}/background_subtraction.js",
        asset_root=_PANEL_ASSET_ROOT,
        version="0.1.0",
    )

    input_ports: ClassVar[list[InputPort]] = [
        InputPort(
            name="features",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            required=True,
            description="Feature table(s) whose sample columns get background-subtracted.",
        ),
    ]
    output_ports: ClassVar[list[OutputPort]] = [
        OutputPort(
            name="features",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            description="Background-subtracted feature table(s).",
        ),
    ]

    def prepare_prompt(self, inputs: dict[str, Any], config: BlockConfig) -> InteractivePrompt:
        """Build one panel tab per input table, each with a suggested matching."""
        features = inputs["features"]
        tables: list[dict[str, Any]] = []
        for i, item in enumerate(features):
            frame = item.to_pandas()
            columns = _sample_columns(item, frame)
            numeric = frame[columns].select_dtypes("number")
            stats = {str(c): _safe_float(numeric[c].median()) for c in numeric.columns}
            tables.append(
                {
                    "index": i,
                    "label": f"Table {i + 1}",
                    "columns": columns,
                    "stats": stats,
                    "suggestion": suggest(columns),
                }
            )
        return InteractivePrompt(panel_payload={"tables": tables})

    def run(self, inputs: dict[str, Collection], config: BlockConfig) -> dict[str, Collection]:
        """Apply each table's matching (panel decision, or the suggestion headless)."""
        features = inputs["features"]
        response = config.get(INTERACTIVE_RESPONSE_KEY)
        decisions = response.get("tables") if isinstance(response, dict) else None

        outputs: list[LCMSFeatureTable] = []
        for i, item in enumerate(features):
            frame = item.to_pandas()
            if decisions and i < len(decisions) and isinstance(decisions[i], dict):
                decision = decisions[i]
            else:
                decision = suggest(_sample_columns(item, frame))
            out_frame = apply_subtraction(frame, decision)
            meta = item.meta
            out = LCMSFeatureTable.from_wide(
                out_frame,
                sample_columns=list(meta.sample_columns) if meta is not None else [],
                source=item,
                polarity=meta.polarity if meta is not None else None,
                software=meta.software if meta is not None else None,
                labeled=meta.labeled if meta is not None else False,
            )
            outputs.append(self._auto_flush(out))

        return {"features": Collection(outputs) if outputs else Collection([], item_type=LCMSFeatureTable)}


def _safe_float(value: Any) -> float | None:
    """A JSON-safe float, or None for NaN/non-finite (panel payloads must be JSON)."""
    import math

    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


__all__ = ["BackgroundSubtraction"]
