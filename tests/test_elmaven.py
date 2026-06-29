"""Tests for the ElMaven AppBlock.

El-MAVEN's peakdetector is not available in CI, so a fake stands in: it reads the
XML config the block writes, and emits an El-MAVEN-shaped peaks CSV into the
output directory. This exercises the real flow — input staging, the
``prepare_launch`` config generation (one ``<samples>`` per file), the launch,
and reconstruction of the CSV into a standard ``LCMSFeatureTable``.
"""

from __future__ import annotations

import stat
import xml.etree.ElementTree as ET
from pathlib import Path

from scistudio.blocks.base import BlockConfig
from scistudio.core.types import Artifact, Collection

from scistudio_package_lcms.blocks import ElMaven
from scistudio_package_lcms.types import LCMSFeatureTable


def test_prepare_launch_injects_every_sample(tmp_path: Path) -> None:
    """Each staged mzML/mzXML file becomes its own <samples> entry."""
    exchange = tmp_path / "exchange"
    staged = exchange / "inputs" / "samples"
    staged.mkdir(parents=True)
    (staged / "item_0000.mzML").write_text("x")
    (staged / "item_0001.mzXML").write_text("x")
    output_dir = exchange / "outputs"
    output_dir.mkdir()

    argv = ElMaven().prepare_launch(exchange, output_dir, BlockConfig(params={"polarity": "negative", "ppm": 15}))

    assert argv[0] == "--xml"
    root = ET.parse(argv[1]).getroot()
    general = root.find("GeneralArguments")
    sample_values = sorted(s.get("value") for s in general.findall("samples"))
    assert len(sample_values) == 2
    assert sample_values[0].endswith("item_0000.mzML")
    assert sample_values[1].endswith("item_0001.mzXML")
    assert general.find("outputdir").get("value") == str(output_dir)
    assert root.find("OptionsDialogArguments").find("ionizationMode").get("value") == "-1"


def _fake_peakdetector(tmp_path: Path) -> Path:
    """Stand-in for peakdetector: read --xml config, write an El-MAVEN peaks CSV."""
    script = tmp_path / "fake_peakdetector"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys, csv, xml.etree.ElementTree as ET\n"
        "cfg = sys.argv[sys.argv.index('--xml') + 1]\n"
        "general = ET.parse(cfg).getroot().find('GeneralArguments')\n"
        "outdir = general.find('outputdir').get('value')\n"
        "samples = [s.get('value') for s in general.findall('samples')]\n"
        "ann = ['label','metaGroupId','groupId','goodPeakCount','medMz','medRt','maxQuality',\n"
        "       'isotopeLabel','compound','compoundId','formula','expectedRtDiff','ppmDiff','parent']\n"
        "cols = ann + [os.path.basename(s) for s in samples]\n"
        "row = ['',1,1,1,180.0,10.0,0.9,'C12 PARENT','X','X','C9H11NO3','0','0','180.0'] + [1000.0 for _ in samples]\n"
        "with open(os.path.join(outdir, 'peaks.csv'), 'w', newline='') as f:\n"
        "    w = csv.writer(f); w.writerow(cols); w.writerow(row)\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IRUSR)
    return script


def test_elmaven_end_to_end_outputs_feature_table(tmp_path: Path) -> None:
    s1 = tmp_path / "a_negative.mzML"
    s1.write_text("raw")
    s2 = tmp_path / "b_negative.mzXML"
    s2.write_text("raw")
    artifacts = [Artifact(file_path=s1, description="a"), Artifact(file_path=s2, description="b")]
    samples = Collection(artifacts, item_type=Artifact)
    fake = _fake_peakdetector(tmp_path)
    config = BlockConfig(params={"app_command": str(fake), "polarity": "negative", "ppm": 15})

    outputs = ElMaven().run({"samples": samples}, config)

    coll = outputs["peaks"]
    assert coll.length == 1
    table = coll[0]
    assert isinstance(table, LCMSFeatureTable)
    assert table.row_count == 1
    # Both injected samples became sample columns of the standard table.
    assert len(table.meta.sample_columns) == 2
    assert table.meta.software == "El-MAVEN"
