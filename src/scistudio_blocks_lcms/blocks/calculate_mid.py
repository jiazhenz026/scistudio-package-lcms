"""Calculate the mass isotopologue distribution (MID) and ¹³C enrichment.

For a labelled feature table (one isotopologue row per compound), this block
emits two standard feature tables:

* ``mid`` — the input's isotopologue-row shape with each compound's per-sample
  intensities normalized to a fractional M+0 / M+1 / … distribution (the MID).
* ``enrichment`` — one row per compound, with the derived ¹³C enrichment
  (``Σ i·MID_i / (n−1)``) per sample.

MID is the primary product; enrichment is derived from it. They are separate
ports because they have different granularity (per isotopologue vs per
compound), so neither distorts the other's shape.
"""

from __future__ import annotations

from typing import Any, ClassVar

from scistudio.blocks.base import BlockConfig, InputPort, OutputPort
from scistudio.blocks.process import ProcessBlock
from scistudio.core.types import Collection
from scistudio.stability import stable

from scistudio_blocks_lcms.blocks._mid import compute_mid_and_enrichment
from scistudio_blocks_lcms.types import ELMAVEN_ANNOTATION_COLUMNS, LCMSFeatureTable


def _sample_columns(item: LCMSFeatureTable, frame: Any) -> list[str]:
    meta = item.meta
    if meta is not None and meta.sample_columns:
        return [c for c in meta.sample_columns if c in frame.columns]
    return [str(c) for c in frame.columns if c not in ELMAVEN_ANNOTATION_COLUMNS]


@stable(since="0.1.0")
class CalculateMID(ProcessBlock):
    """Compute the MID (fractional isotopologue distribution) and ¹³C enrichment."""

    name: ClassVar[str] = "Calculate MID"
    description: ClassVar[str] = "Normalize isotopologues to a fractional MID and derive ¹³C enrichment per compound."
    version: ClassVar[str] = "0.1.0"
    algorithm: ClassVar[str] = "calculate_mid"

    input_ports: ClassVar[list[InputPort]] = [
        InputPort(
            name="features",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            required=True,
            description="Labelled feature table(s): one isotopologue row per compound.",
        ),
    ]
    output_ports: ClassVar[list[OutputPort]] = [
        OutputPort(
            name="mid",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            description="MID fractions, in the input's isotopologue-row shape.",
        ),
        OutputPort(
            name="enrichment",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            description="¹³C enrichment per compound per sample.",
        ),
    ]

    def run(self, inputs: dict[str, Collection], config: BlockConfig) -> dict[str, Collection]:
        """Compute MID + enrichment for each labelled table."""
        features = inputs["features"]
        mids: list[LCMSFeatureTable] = []
        enrichments: list[LCMSFeatureTable] = []
        for item in features:
            frame = item.to_pandas()
            samples = _sample_columns(item, frame)
            mid_frame, enrichment_frame = compute_mid_and_enrichment(frame, sample_columns=samples)
            meta = item.meta
            mids.append(
                self._auto_flush(
                    LCMSFeatureTable.from_wide(
                        mid_frame,
                        sample_columns=samples,
                        polarity=meta.polarity if meta is not None else None,
                        software=meta.software if meta is not None else None,
                        labeled=True,
                    )
                )
            )
            enrichments.append(
                self._auto_flush(
                    LCMSFeatureTable.from_wide(
                        enrichment_frame,
                        sample_columns=samples,
                        polarity=meta.polarity if meta is not None else None,
                        software=meta.software if meta is not None else None,
                        labeled=False,
                    )
                )
            )

        return {
            "mid": Collection(mids) if mids else Collection([], item_type=LCMSFeatureTable),
            "enrichment": Collection(enrichments) if enrichments else Collection([], item_type=LCMSFeatureTable),
        }


__all__ = ["CalculateMID"]
