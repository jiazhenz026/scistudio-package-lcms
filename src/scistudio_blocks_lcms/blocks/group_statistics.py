"""Per-feature group statistics for LCMS feature tables (interactive).

An interactive block (ADR-051): it opens a panel where the user assigns each
sample column to an experimental group, picks a test (Welch t-test, one-way
ANOVA, or a linear trend over an ordered level), and a multiple-testing
correction. It then compares the per-group sample values of every feature and
returns a tidy statistics table — group means plus the test statistic, p-value,
BH-adjusted p-value, and a significance flag.

The group assignment is pre-filled by stripping a trailing replicate index from
the column name (:mod:`._group_stats`); the user corrects it in the panel.
Running headless applies the suggested groups and the configured test.

Output is the core :class:`~scistudio.core.types.DataFrame` (a result table),
one per input feature table — not a new package type.
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

from scistudio_blocks_lcms.blocks._group_stats import FDR_METHODS, TESTS, compute_stats, suggest_groups
from scistudio_blocks_lcms.blocks._results import dataframe_from_pandas
from scistudio_blocks_lcms.types import ELMAVEN_ANNOTATION_COLUMNS, LCMSFeatureTable

_PANEL_ID = "scistudio_blocks_lcms.interactive.group_statistics"
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


@stable(since="0.1.0")
class GroupStatistics(InteractiveMixin, ProcessBlock):
    """Compare feature intensities across sample groups (t-test / ANOVA / linear trend)."""

    name: ClassVar[str] = "Group Statistics"
    description: ClassVar[str] = (
        "Assign samples to groups, then compare each feature (t-test / ANOVA / trend) with FDR."
    )
    version: ClassVar[str] = "0.1.0"
    algorithm: ClassVar[str] = "group_statistics"

    execution_mode: ClassVar[ExecutionMode] = ExecutionMode.INTERACTIVE
    interactive_panel: ClassVar[PanelManifest] = PanelManifest(
        panel_id=_PANEL_ID,
        module_url=f"/api/blocks/panels/{_PANEL_ID}/group_statistics.js",
        asset_root=_PANEL_ASSET_ROOT,
        version="0.1.0",
    )

    input_ports: ClassVar[list[InputPort]] = [
        InputPort(
            name="features",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            required=True,
            description="Feature table(s) to compare across groups.",
        ),
    ]
    output_ports: ClassVar[list[OutputPort]] = [
        OutputPort(
            name="statistics",
            accepted_types=[DataFrame],
            is_collection=True,
            description="Per-feature statistics table(s): group means, statistic, p-value, p_adj, significant.",
        ),
    ]

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "test": {
                "type": "string",
                "enum": list(TESTS),
                "default": "ttest",
                "title": "Statistical Test",
            },
            "fdr": {
                "type": "string",
                "enum": list(FDR_METHODS),
                "default": "bh",
                "title": "Multiple-testing Correction",
            },
            "alpha": {"type": "number", "default": 0.05, "title": "Significance Threshold"},
        },
    }

    def prepare_prompt(self, inputs: dict[str, Any], config: BlockConfig) -> InteractivePrompt:
        """Build one panel tab per input table with its sample columns and suggested groups."""
        features = inputs["features"]
        tables: list[dict[str, Any]] = []
        for i, item in enumerate(features):
            frame = item.to_pandas()
            columns = _sample_columns(item, frame)
            tables.append(
                {
                    "index": i,
                    "label": f"Table {i + 1}",
                    "columns": columns,
                    "suggestion": {"groups": suggest_groups(columns)},
                }
            )
        return InteractivePrompt(
            panel_payload={
                "tables": tables,
                "tests": list(TESTS),
                "fdr_methods": list(FDR_METHODS),
                "test": str(config.get("test", "ttest")),
                "fdr": str(config.get("fdr", "bh")),
                "alpha": float(config.get("alpha", 0.05)),
            }
        )

    def run(self, inputs: dict[str, Collection], config: BlockConfig) -> dict[str, Collection]:
        """Compute per-feature group statistics for each table (panel decision or headless)."""
        features = inputs["features"]
        response = config.get(INTERACTIVE_RESPONSE_KEY)
        response = response if isinstance(response, dict) else {}
        test = str(response.get("test") or config.get("test", "ttest"))
        fdr = str(response.get("fdr") or config.get("fdr", "bh"))
        alpha = float(response.get("alpha", config.get("alpha", 0.05)))
        decisions = response.get("tables") if isinstance(response.get("tables"), list) else None

        outputs: list[Any] = []
        for i, item in enumerate(features):
            frame = item.to_pandas()
            samples = _sample_columns(item, frame)
            decision = decisions[i] if decisions and i < len(decisions) and isinstance(decisions[i], dict) else {}
            groups = decision.get("groups") or suggest_groups(samples)
            pair = decision.get("pair")
            stats_frame = compute_stats(
                frame,
                sample_columns=samples,
                groups=groups,
                annotation_columns=_annotation_columns(item, frame, samples),
                test=test,
                pair=tuple(pair) if isinstance(pair, (list, tuple)) and len(pair) == 2 else None,
                levels=decision.get("levels"),
                fdr=fdr,
                alpha=alpha,
            )
            outputs.append(self._auto_flush(dataframe_from_pandas(stats_frame)))

        return {"statistics": Collection(outputs) if outputs else Collection([], item_type=DataFrame)}


__all__ = ["GroupStatistics"]
