"""Tests for the :class:`LCMSFeatures` domain type and the ``_support`` plumbing."""

from __future__ import annotations

import pandas as pd
from scistudio.core.types.dataframe import DataFrame

from scistudio_package_lcms import _support
from scistudio_package_lcms.types import LCMSFeatures


def _sample_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "compound": ["L-Tyrosine", "L-Tyrosine"],
            "formula": ["C9H11NO3", "C9H11NO3"],
            "isotopeLabel": ["C12 PARENT", "C13-label-1"],
            "sample_A": [1000.0, 50.0],
            "sample_B": [1100.0, 60.0],
        }
    )


def test_lcmsfeatures_is_dataframe_subclass() -> None:
    # The type stays a core DataFrame so it flows through core IO/preview paths.
    assert issubclass(LCMSFeatures, DataFrame)


def test_meta_fields_exist() -> None:
    fields = set(LCMSFeatures.Meta.model_fields)
    assert {"polarity", "source_tool", "source_file", "labeled"}.issubset(fields)


def test_build_and_read_roundtrip_keeps_columns_verbatim() -> None:
    frame = _sample_frame()
    feats = _support.build_features(frame, meta=LCMSFeatures.Meta(polarity="negative", labeled=True))
    assert isinstance(feats, LCMSFeatures)
    assert feats.row_count == 2
    # Columns are preserved exactly as exported (no restructuring).
    assert feats.columns == list(frame.columns)
    out = _support.features_pandas(feats)
    assert list(out.columns) == list(frame.columns)
    assert out["sample_A"].tolist() == [1000.0, 50.0]
    assert feats.meta is not None and feats.meta.polarity == "negative"


def test_derive_preserves_lineage() -> None:
    src = _support.build_features(_sample_frame(), meta=LCMSFeatures.Meta(source_tool="elmaven"))
    derived = _support.derive_features(src, _sample_frame())
    assert isinstance(derived, LCMSFeatures)
    # Lineage recorded; metadata carried over when not overridden.
    assert derived.framework.derived_from == src.framework.object_id
    assert derived.meta is not None and derived.meta.source_tool == "elmaven"


def test_coerce_features_accepts_bare_and_collection() -> None:
    feats = _support.build_features(_sample_frame())
    assert _support.coerce_features(feats) is feats
    coll = _support.features_collection(feats)
    assert _support.coerce_features(coll) is feats
