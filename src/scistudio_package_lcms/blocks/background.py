"""Background handling blocks: select a 1:1 background, then subtract it.

Two blocks form a pair:

- :class:`BackgroundSelector` splits one peak table into matched ``samples`` /
  ``background`` tables (column-for-column), so the definition of "background"
  (which is lab-specific) lives in one configurable place.
- :class:`BackgroundSubtraction` subtracts the background table from the sample
  table element-wise.

The selector is the config-panel form of what will eventually be an interactive
column-picker once core grows a plugin-extensible interactive-block UI.

TODO(#interactive-blocks): replace BackgroundSelector's pattern-based config
panel with an interactive runtime column picker once core ships a
plugin-extensible interactive-block frontend (the DataRouter mechanism is
currently core-frontend-only). Tracked for the live-implementer follow-up.
"""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Any, ClassVar

import pandas as pd
from scistudio.blocks.base.config import BlockConfig
from scistudio.blocks.base.ports import InputPort, OutputPort
from scistudio.blocks.process.process_block import ProcessBlock
from scistudio.core.types.collection import Collection

from scistudio_package_lcms import _support
from scistudio_package_lcms.types import LCMSFeatures


def _matches_any(name: str, patterns: list[str]) -> bool:
    return any(fnmatch(name, pat) for pat in patterns)


def _numeric_columns(frame: pd.DataFrame) -> list[str]:
    return [c for c in frame.columns if pd.api.types.is_numeric_dtype(frame[c])]


class BackgroundSelector(ProcessBlock):
    """Split a peak table into matched ``samples`` and ``background`` tables.

    Identifier columns (non-numeric, plus any explicitly listed) are carried
    into both outputs unchanged. The background columns are aggregated into a
    per-row background profile and broadcast across the sample columns, so the
    emitted ``background`` table lines up 1:1 with ``samples`` and can feed
    :class:`BackgroundSubtraction` directly.
    """

    type_name: ClassVar[str] = "lcms.background_selector"
    name: ClassVar[str] = "Background Selector"
    description: ClassVar[str] = "Split a peak table into matched samples / background tables."
    version: ClassVar[str] = "0.1.0"
    algorithm: ClassVar[str] = "background_selection"
    subcategory: ClassVar[str] = "preprocessing"

    input_ports: ClassVar[list[InputPort]] = [
        InputPort(name="features", accepted_types=[LCMSFeatures], required=True, description="Peak table to split."),
    ]
    output_ports: ClassVar[list[OutputPort]] = [
        OutputPort(name="samples", accepted_types=[LCMSFeatures], description="Sample columns only."),
        OutputPort(name="background", accepted_types=[LCMSFeatures], description="1:1 background for each sample."),
    ]

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "id_columns": {
                "type": "array",
                "items": {"type": "string"},
                "default": [],
                "title": "Identifier columns (kept in both outputs)",
                "description": "Non-numeric columns are treated as identifiers automatically; list any extra here.",
            },
            "background_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "default": ["BLANK*"],
                "title": "Background column patterns (glob)",
            },
            "sample_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "default": ["*"],
                "title": "Sample column patterns (glob)",
            },
            "aggregation": {
                "type": "string",
                "enum": ["mean", "median"],
                "default": "mean",
                "title": "Background aggregation",
            },
        },
    }

    def run(self, inputs: dict[str, Collection], config: BlockConfig) -> dict[str, Collection]:
        features = _support.coerce_features(inputs.get("features"), block=self.name, port="features")
        frame = _support.features_pandas(features)

        id_explicit = list(config.get("id_columns", []) or [])
        background_patterns = list(config.get("background_patterns", ["BLANK*"]) or [])
        sample_patterns = list(config.get("sample_patterns", ["*"]) or [])
        aggregation = str(config.get("aggregation", "mean"))

        numeric = _numeric_columns(frame)
        non_numeric = [c for c in frame.columns if c not in numeric]
        # Identifiers: explicit list + every non-numeric column, in table order.
        id_cols = [c for c in frame.columns if c in set(id_explicit) | set(non_numeric)]

        background_cols = [c for c in numeric if c not in id_cols and _matches_any(c, background_patterns)]
        sample_cols = [
            c for c in numeric if c not in id_cols and c not in background_cols and _matches_any(c, sample_patterns)
        ]
        if not sample_cols:
            raise ValueError(f"{self.name}: no sample columns matched {sample_patterns!r}")
        if not background_cols:
            raise ValueError(f"{self.name}: no background columns matched {background_patterns!r}")

        profile = frame[background_cols].agg(aggregation, axis=1)

        samples_df = frame[id_cols + sample_cols].copy()
        background_df = frame[id_cols].copy()
        for col in sample_cols:
            background_df[col] = profile.to_numpy()

        samples_out = self._auto_flush(_support.derive_features(features, samples_df))
        background_out = self._auto_flush(_support.derive_features(features, background_df))
        return {
            "samples": _support.features_collection(samples_out),
            "background": _support.features_collection(background_out),
        }


class BackgroundSubtraction(ProcessBlock):
    """Subtract a 1:1 background table from a sample table, element-wise.

    The two inputs must share the same sample columns and row order (as
    produced by :class:`BackgroundSelector`). Identifier columns are taken from
    ``samples``; each shared numeric (sample) column has its background
    subtracted. Negative results are clipped to zero by default.
    """

    type_name: ClassVar[str] = "lcms.background_subtraction"
    name: ClassVar[str] = "Background Subtraction"
    description: ClassVar[str] = "Subtract a 1:1 background table from a sample table."
    version: ClassVar[str] = "0.1.0"
    algorithm: ClassVar[str] = "background_subtraction"
    subcategory: ClassVar[str] = "preprocessing"

    input_ports: ClassVar[list[InputPort]] = [
        InputPort(name="samples", accepted_types=[LCMSFeatures], required=True, description="Sample table."),
        InputPort(
            name="background",
            accepted_types=[LCMSFeatures],
            required=True,
            description="Background table, 1:1 with samples.",
        ),
    ]
    output_ports: ClassVar[list[OutputPort]] = [
        OutputPort(name="result", accepted_types=[LCMSFeatures], description="Background-subtracted table."),
    ]

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "clip_negative": {
                "type": "boolean",
                "default": True,
                "title": "Clip negative values to zero",
            },
        },
    }

    def run(self, inputs: dict[str, Collection], config: BlockConfig) -> dict[str, Collection]:
        samples = _support.coerce_features(inputs.get("samples"), block=self.name, port="samples")
        background = _support.coerce_features(inputs.get("background"), block=self.name, port="background")
        s_df = _support.features_pandas(samples)
        b_df = _support.features_pandas(background)

        if len(s_df) != len(b_df):
            raise ValueError(
                f"{self.name}: samples ({len(s_df)} rows) and background ({len(b_df)} rows) must align 1:1"
            )

        clip_negative = bool(config.get("clip_negative", True))
        shared = [c for c in _numeric_columns(s_df) if c in b_df.columns and pd.api.types.is_numeric_dtype(b_df[c])]
        if not shared:
            raise ValueError(f"{self.name}: samples and background share no numeric sample columns")

        result = s_df.copy()
        diff = s_df[shared].to_numpy() - b_df[shared].to_numpy()
        result[shared] = diff
        if clip_negative:
            result[shared] = result[shared].clip(lower=0)

        out = self._auto_flush(_support.derive_features(samples, result))
        return {"result": _support.features_collection(out)}


__all__ = ["BackgroundSelector", "BackgroundSubtraction"]
