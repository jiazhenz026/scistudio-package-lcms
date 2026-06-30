"""Internal-standard normalization for LCMS feature tables (interactive).

An interactive block (ADR-051): it opens a panel where the user picks the
normalization *reference* — a single reference feature, or a per-metabolite
isotope internal standard — then divides each sample column by that reference,
per sample. Total-ion and median normalization need no reference and run
without the panel.

The panel is pre-filled by a name heuristic (:mod:`._normalization`) that flags
likely spiked standards, which the user confirms or overrides. Running without a
panel decision (headless) applies the ``method`` configured on the block.

Normalization cancels *technical* variation between samples (extraction,
injection volume); it is distinct from :class:`~scistudio_blocks_lcms.blocks.log2_mean_center.Log2MeanCenter`,
which transforms each feature *across* samples for comparability.
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

from scistudio_blocks_lcms.blocks._normalization import METHODS, apply_normalization, suggest_reference
from scistudio_blocks_lcms.types import LCMSFeatureTable

_PANEL_ID = "scistudio_blocks_lcms.interactive.normalization"
#: Absolute on-disk dir the backend serves the panel asset from (ADR-051 §7).
_PANEL_ASSET_ROOT = str(files("scistudio_blocks_lcms").joinpath("panels"))

_COMPOUND_COLUMN = "compound"
_LABEL_COLUMN = "isotopeLabel"


def _sample_columns(item: LCMSFeatureTable, frame: Any) -> list[str]:
    """The intensity columns to normalize — sample columns only; annotation passes through."""
    meta = item.meta
    if meta is not None and meta.sample_columns:
        return [c for c in meta.sample_columns if c in frame.columns]
    from scistudio_blocks_lcms.types import ELMAVEN_ANNOTATION_COLUMNS

    return [str(c) for c in frame.columns if c not in ELMAVEN_ANNOTATION_COLUMNS]


def _compound_labels(frame: Any) -> list[dict[str, Any]]:
    """List each compound with its isotopologue labels (for the reference picker)."""
    if _COMPOUND_COLUMN not in frame.columns:
        return []
    compounds: list[dict[str, Any]] = []
    has_label = _LABEL_COLUMN in frame.columns
    for compound in frame[_COMPOUND_COLUMN].astype(str).drop_duplicates():
        if has_label:
            labels = [str(x) for x in frame.loc[frame[_COMPOUND_COLUMN].astype(str) == compound, _LABEL_COLUMN]]
            labels = list(dict.fromkeys(labels))  # unique, order-preserving
        else:
            labels = []
        compounds.append({"compound": compound, "labels": labels})
    return compounds


@stable(since="0.1.0")
class Normalization(InteractiveMixin, ProcessBlock):
    """Divide each sample column by a reference (internal standard / total / median)."""

    name: ClassVar[str] = "Normalization"
    description: ClassVar[str] = "Normalize sample columns to an internal standard, total, or median."
    version: ClassVar[str] = "0.1.0"
    algorithm: ClassVar[str] = "normalization"

    execution_mode: ClassVar[ExecutionMode] = ExecutionMode.INTERACTIVE
    interactive_panel: ClassVar[PanelManifest] = PanelManifest(
        panel_id=_PANEL_ID,
        module_url=f"/api/blocks/panels/{_PANEL_ID}/normalization.js",
        asset_root=_PANEL_ASSET_ROOT,
        version="0.1.0",
    )

    input_ports: ClassVar[list[InputPort]] = [
        InputPort(
            name="features",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            required=True,
            description="Feature table(s) to normalize.",
        ),
    ]
    output_ports: ClassVar[list[OutputPort]] = [
        OutputPort(
            name="features",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            description="Normalized feature table(s).",
        ),
    ]

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "method": {
                "type": "string",
                "enum": list(METHODS),
                "default": "total",
                "title": "Normalization Method",
                "description": "Headless default; the panel can override it.",
            },
            "drop_reference": {
                "type": "boolean",
                "default": True,
                "title": "Drop reference rows after normalizing",
            },
        },
    }

    def prepare_prompt(self, inputs: dict[str, Any], config: BlockConfig) -> InteractivePrompt:
        """Build one panel tab per input table with its compounds and a suggested reference."""
        features = inputs["features"]
        tables: list[dict[str, Any]] = []
        for i, item in enumerate(features):
            frame = item.to_pandas()
            compounds = _compound_labels(frame)
            tables.append(
                {
                    "index": i,
                    "label": f"Table {i + 1}",
                    "sample_columns": _sample_columns(item, frame),
                    "compounds": compounds,
                    "suggestion": {"single_reference": suggest_reference([c["compound"] for c in compounds])},
                }
            )
        return InteractivePrompt(
            panel_payload={
                "tables": tables,
                "methods": list(METHODS),
                "method": str(config.get("method", "total")),
                "drop_reference": bool(config.get("drop_reference", True)),
            }
        )

    def run(self, inputs: dict[str, Collection], config: BlockConfig) -> dict[str, Collection]:
        """Apply the panel's reference decision (or the configured method headless)."""
        features = inputs["features"]
        response = config.get(INTERACTIVE_RESPONSE_KEY)
        response = response if isinstance(response, dict) else {}
        method = str(response.get("method") or config.get("method", "total"))
        drop_reference = bool(response.get("drop_reference", config.get("drop_reference", True)))
        decisions = response.get("tables") if isinstance(response.get("tables"), list) else None

        outputs: list[LCMSFeatureTable] = []
        for i, item in enumerate(features):
            frame = item.to_pandas()
            decision = decisions[i] if decisions and i < len(decisions) and isinstance(decisions[i], dict) else {}
            out_frame = apply_normalization(
                frame,
                method=method,
                sample_columns=_sample_columns(item, frame),
                compound_column=_COMPOUND_COLUMN,
                label_column=_LABEL_COLUMN,
                reference=decision.get("reference"),
                pairs=decision.get("pairs"),
                drop_reference=drop_reference,
            )
            meta = item.meta
            outputs.append(
                self._auto_flush(
                    LCMSFeatureTable.from_wide(
                        out_frame,
                        sample_columns=list(meta.sample_columns) if meta is not None else [],
                        polarity=meta.polarity if meta is not None else None,
                        software=meta.software if meta is not None else None,
                        labeled=meta.labeled if meta is not None else False,
                    )
                )
            )

        return {"features": Collection(outputs) if outputs else Collection([], item_type=LCMSFeatureTable)}


__all__ = ["Normalization"]
