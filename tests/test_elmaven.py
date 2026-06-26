"""Tests for the El-MAVEN AppBlock.

The external-launch lifecycle is inherited from core ``AppBlock`` and cannot run
without El-MAVEN installed, so these tests cover the parts this subclass owns:
port declarations and turning collected export files into ``LCMSFeatures``.
"""

from __future__ import annotations

from pathlib import Path

from scistudio.blocks.base.config import BlockConfig
from scistudio.blocks.base.state import ExecutionMode
from scistudio.core.types.artifact import Artifact
from scistudio.core.types.collection import Collection

from scistudio_package_lcms import _support
from scistudio_package_lcms.blocks.elmaven import ElMaven
from scistudio_package_lcms.types import LCMSFeatures

_CSV = (
    "medMz,medRt,isotopeLabel,compound,formula,A_1,A_2,BLANK1\n"
    "180.066,10.0,C12 PARENT,L-Tyrosine,C9H11NO3,1000,1100,5\n"
    "181.069,10.0,C13-label-1,L-Tyrosine,C9H11NO3,50,60,0\n"
)


def test_ports_and_mode() -> None:
    assert ElMaven.execution_mode is ExecutionMode.EXTERNAL
    assert ElMaven.input_ports[0].name == "mzml"
    assert Artifact in ElMaven.input_ports[0].accepted_types
    assert ElMaven.output_ports[0].name == "peaks"
    assert LCMSFeatures in ElMaven.output_ports[0].accepted_types


def test_features_from_outputs_parses_artifacts(tmp_path: Path) -> None:
    export = tmp_path / "scan1_negative.csv"
    export.write_text(_CSV, encoding="utf-8")
    raw = {"scan1_negative": Collection([Artifact(file_path=export)], item_type=Artifact)}

    block = ElMaven()
    features = block._features_from_outputs(raw, BlockConfig(params={"polarity": "negative"}))
    assert len(features) == 1
    feats = features[0]
    assert isinstance(feats, LCMSFeatures)
    assert feats.row_count == 2
    assert feats.meta is not None
    assert feats.meta.polarity == "negative"
    assert feats.meta.source_tool == "elmaven"
    assert feats.meta.labeled is True
    df = _support.features_pandas(feats)
    assert df["compound"].tolist() == ["L-Tyrosine", "L-Tyrosine"]


def test_features_from_outputs_passes_through_typed(tmp_path: Path) -> None:
    feats = _support.build_features({"compound": ["X"], "A_1": [1.0]}, meta=LCMSFeatures.Meta(source_tool="elmaven"))
    raw = {"peaks": Collection([feats], item_type=LCMSFeatures)}
    out = ElMaven()._features_from_outputs(raw, BlockConfig(params={}))
    assert out == [feats]
