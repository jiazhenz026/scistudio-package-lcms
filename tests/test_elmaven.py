"""Tests for the ElMaven AppBlock.

ElMaven is an interactive launcher: it hands the input sample files to El-MAVEN as
positional command-line arguments, opens the application, and waits for the user to
export a peaks CSV into the *Save Outputs At* directory. El-MAVEN is not available in
CI, so a fake stands in: it receives the sample paths as positional arguments and emits
an El-MAVEN-shaped peaks CSV into the output directory (modelling the user's manual
export). This exercises the real flow — input handling, the ``prepare_launch`` argv
generation, the launch, and reconstruction of the CSV into a standard
``LCMSFeatureTable``.
"""

from __future__ import annotations

import stat
from pathlib import Path

from scistudio.blocks.base import BlockConfig
from scistudio.core.types import Artifact, Collection

from scistudio_blocks_lcms.blocks import ElMaven
from scistudio_blocks_lcms.types import LCMSFeatureTable


def test_prepare_launch_returns_every_sample_path(tmp_path: Path) -> None:
    """Each staged mzML/mzXML file becomes its own positional argument."""
    exchange = tmp_path / "exchange"
    staged = exchange / "inputs" / "samples"
    staged.mkdir(parents=True)
    (staged / "item_0000.mzML").write_text("x")
    (staged / "item_0001.mzXML").write_text("x")
    output_dir = exchange / "outputs"
    output_dir.mkdir()

    argv = ElMaven().prepare_launch(exchange, output_dir, BlockConfig(params={}))

    assert len(argv) == 2
    assert sorted(Path(a).name for a in argv) == ["item_0000.mzML", "item_0001.mzXML"]


def _fake_elmaven(tmp_path: Path, output_dir: Path) -> Path:
    """Stand-in for El-MAVEN: read sample paths from argv, export a peaks CSV.

    Models the user's manual export into the *Save Outputs At* directory, which is
    baked into the script (El-MAVEN receives only the sample paths on the command line).
    """
    script = tmp_path / "fake_elmaven"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys, csv\n"
        f"outdir = {str(output_dir)!r}\n"
        "samples = sys.argv[1:]\n"
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

    output_dir = tmp_path / "saved_outputs"
    output_dir.mkdir()
    fake = _fake_elmaven(tmp_path, output_dir)
    config = BlockConfig(params={"app_command": str(fake), "output_dir": str(output_dir)})

    outputs = ElMaven().run({"samples": samples}, config)

    coll = outputs["peaks"]
    assert coll.length == 1
    table = coll[0]
    assert isinstance(table, LCMSFeatureTable)
    assert table.row_count == 1
    # Both samples handed to El-MAVEN became sample columns of the standard table.
    assert len(table.meta.sample_columns) == 2
    assert table.meta.software == "El-MAVEN"
