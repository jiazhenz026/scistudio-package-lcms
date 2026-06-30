"""Log2 + per-feature mean-centering transform for LCMS feature tables.

A small, standalone transform (the ``log2_mean_center`` step of the reference
untargeted pipeline): for each feature, take ``log2`` of its per-sample
intensities and subtract the feature's mean across samples, so every value
becomes that feature's log2 fold-change versus its own average. This puts high-
and low-abundance features on one comparable scale — the input a heatmap or a
group comparison wants.

It works *across* samples, per feature (row), and is therefore orthogonal to
:class:`~scistudio_package_lcms.blocks.normalization.Normalization`, which divides
*within* a sample by an internal standard. The two are typically run in order:
normalize first, then log2-mean-center.

Non-positive and missing intensities are floored to a small pseudocount — a
fraction of the smallest strictly-positive value — before the ``log2`` so the
transform is defined everywhere (matching the reference implementation).
"""

from __future__ import annotations

from typing import Any, ClassVar

from scistudio.blocks.base import BlockConfig, InputPort, OutputPort
from scistudio.blocks.process import ProcessBlock
from scistudio.core.types import Collection
from scistudio.stability import stable

from scistudio_package_lcms.types import ELMAVEN_ANNOTATION_COLUMNS, LCMSFeatureTable


def _sample_columns(item: LCMSFeatureTable, frame: Any) -> list[str]:
    meta = item.meta
    if meta is not None and meta.sample_columns:
        return [c for c in meta.sample_columns if c in frame.columns]
    return [str(c) for c in frame.columns if c not in ELMAVEN_ANNOTATION_COLUMNS]


def _log2_mean_center(frame: Any, sample_columns: list[str], pseudocount_fraction: float) -> Any:
    """Return *frame* with its sample columns log2-transformed and row-mean-centered."""
    import numpy as np

    result = frame.copy()
    cols = [c for c in sample_columns if c in result.columns]
    if not cols:
        return result
    num = result[cols].to_numpy(dtype=float)
    positive = num[num > 0]
    if positive.size == 0:
        return result  # nothing to log; leave untouched
    pseudo = float(positive.min()) * float(pseudocount_fraction)
    num = np.where((num <= 0) | np.isnan(num), pseudo, num)
    logged = np.log2(num)
    centered = logged - logged.mean(axis=1, keepdims=True)
    result[cols] = centered
    return result


@stable(since="0.1.0")
class Log2MeanCenter(ProcessBlock):
    """Log2-transform and per-feature mean-center the sample columns."""

    name: ClassVar[str] = "Log2 Mean Center"
    description: ClassVar[str] = "Log2-transform and mean-center each feature across samples (relative log2FC)."
    version: ClassVar[str] = "0.1.0"
    algorithm: ClassVar[str] = "log2_mean_center"

    input_ports: ClassVar[list[InputPort]] = [
        InputPort(
            name="features",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            required=True,
            description="Feature table(s) to transform.",
        ),
    ]
    output_ports: ClassVar[list[OutputPort]] = [
        OutputPort(
            name="features",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            description="Log2 mean-centered feature table(s).",
        ),
    ]

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "pseudocount_fraction": {
                "type": "number",
                "default": 0.1,
                "minimum": 0.0,
                "title": "Pseudocount Fraction",
                "description": "Floor for non-positive/missing values, as a fraction of the smallest positive value.",
            },
        },
    }

    def run(self, inputs: dict[str, Collection], config: BlockConfig) -> dict[str, Collection]:
        """Apply log2 + per-feature mean-centering to each input table's sample columns."""
        features = inputs["features"]
        fraction = float(config.get("pseudocount_fraction", 0.1))

        outputs: list[LCMSFeatureTable] = []
        for item in features:
            frame = item.to_pandas()
            out_frame = _log2_mean_center(frame, _sample_columns(item, frame), fraction)
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


__all__ = ["Log2MeanCenter"]
