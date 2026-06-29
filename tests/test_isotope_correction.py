"""Tests for the IsotopeCorrection block's Python orchestration.

The real R correctors (accucor / accucor2) are not installable in CI, so these
tests exercise the Python glue — config marshalling, the CSV in / CSV out
boundary, the four output ports, and output-table construction — through a fake
``Rscript`` that reads the block's environment contract and writes the four
output CSVs. The embedded R is validated against real data on a host with R.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pandas as pd
import pytest
from scistudio.blocks.base import BlockConfig
from scistudio.core.types import Collection

from scistudio_package_lcms.blocks import IsotopeCorrection
from scistudio_package_lcms.blocks.isotope_correction import _OUTPUTS, _resolve_rscript
from scistudio_package_lcms.types import LCMSFeatureTable


def _persisted_table(tmp_path: Path, stem: str = "input") -> LCMSFeatureTable:
    """A storage-backed LCMSFeatureTable (as a downstream block would receive)."""
    frame = pd.DataFrame(
        {
            "isotopeLabel": ["C12 PARENT", "C13-label-1"],
            "compound": ["L-Tyrosine", "L-Tyrosine"],
            "formula": ["C9H11NO3", "C9H11NO3"],
            "medMz": [180.066, 181.070],
            "medRt": [10.07, 10.06],
            "Sample_A": [1608868.0, 161615.45],
            "Sample_B": [1743866.38, 163117.81],
        }
    )
    table = LCMSFeatureTable.from_elmaven(frame, polarity="negative")
    table.save(tmp_path / f"{stem}.parquet")
    return table


def _fake_rscript(tmp_path: Path) -> Path:
    """A stand-in for Rscript: writes the four output CSVs from the env contract.

    Each output keeps ``compound`` + the sample columns, mimicking a corrector
    that returns per-compound matrices for original/corrected/normalized/pool.
    """
    script = tmp_path / "fake_rscript"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import os, csv\n"
        "inp = os.environ['ACCUCOR_INPUT']\n"
        "outdir = os.environ['ACCUCOR_OUTPUT_DIR']\n"
        "samples = [s for s in os.environ['ACCUCOR_SAMPLE_COLUMNS'].split(',') if s]\n"
        "with open(inp, newline='') as f:\n"
        "    rows = list(csv.DictReader(f))\n"
        "cols = ['compound'] + samples\n"
        "for name in ('original', 'corrected', 'normalized', 'pool'):\n"
        "    with open(os.path.join(outdir, name + '.csv'), 'w', newline='') as f:\n"
        "        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')\n"
        "        w.writeheader()\n"
        "        for r in rows:\n"
        "            w.writerow({k: r.get(k, '') for k in cols})\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IRUSR)
    return script


def _run(block: IsotopeCorrection, table: LCMSFeatureTable, config: BlockConfig) -> dict[str, Collection]:
    return block.run({"features": Collection([table])}, config)


def test_ports_and_config() -> None:
    assert IsotopeCorrection.input_ports[0].accepted_types == [LCMSFeatureTable]
    out_names = [p.name for p in IsotopeCorrection.output_ports]
    assert out_names == ["original", "corrected", "normalized", "pool"]
    assert all(p.accepted_types == [LCMSFeatureTable] for p in IsotopeCorrection.output_ports)
    assert IsotopeCorrection.config_schema["properties"]["corrector"]["enum"] == ["accucor", "accucor2"]


def test_missing_rscript_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scistudio_package_lcms.blocks.isotope_correction.shutil.which",
        lambda _name: None,
    )
    with pytest.raises(RuntimeError, match="Rscript was not found"):
        _resolve_rscript(BlockConfig(params={}))


def test_emits_four_output_ports(tmp_path: Path) -> None:
    table = _persisted_table(tmp_path)
    fake = _fake_rscript(tmp_path)
    config = BlockConfig(params={"corrector": "accucor", "rscript_path": str(fake), "resolution": 100000})

    outputs = _run(IsotopeCorrection(), table, config)

    assert set(outputs) == set(_OUTPUTS)
    for name in _OUTPUTS:
        coll = outputs[name]
        assert coll.length == 1
        result = coll[0]
        assert isinstance(result, LCMSFeatureTable)
        assert result.columns == ["compound", "Sample_A", "Sample_B"]
        assert result.meta.sample_columns == ("Sample_A", "Sample_B")
        assert result.meta.annotation_columns == ("compound",)
        assert result.meta.polarity == "negative"


def test_collection_of_tables_wraps_per_port(tmp_path: Path) -> None:
    """A 3-table input collection yields a 3-table collection on every port."""
    tables = [_persisted_table(tmp_path, stem=f"in_{i}") for i in range(3)]
    fake = _fake_rscript(tmp_path)
    config = BlockConfig(params={"corrector": "accucor", "rscript_path": str(fake), "resolution": 100000})

    outputs = IsotopeCorrection().run({"features": Collection(tables)}, config)

    assert set(outputs) == set(_OUTPUTS)
    for name in _OUTPUTS:
        assert outputs[name].length == 3
        assert all(isinstance(t, LCMSFeatureTable) for t in outputs[name])


def test_failed_r_run_surfaces_stderr(tmp_path: Path) -> None:
    table = _persisted_table(tmp_path)
    failing = tmp_path / "boom"
    failing.write_text(
        "#!/usr/bin/env python3\nimport sys\nsys.stderr.write('kaboom')\nsys.exit(3)\n",
        encoding="utf-8",
    )
    failing.chmod(failing.stat().st_mode | stat.S_IEXEC | stat.S_IRUSR)
    config = BlockConfig(params={"corrector": "accucor", "rscript_path": str(failing)})

    with pytest.raises(RuntimeError, match="kaboom"):
        _run(IsotopeCorrection(), table, config)


def test_env_contract_passes_parameters(tmp_path: Path) -> None:
    """The block marshals its config into the embedded R script's env contract."""
    table = _persisted_table(tmp_path)
    capture = tmp_path / "env.json"
    script = tmp_path / "capture_rscript"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import os, json, csv\n"
        f"json.dump({{k: v for k, v in os.environ.items() if k.startswith('ACCUCOR_')}}, open({str(capture)!r}, 'w'))\n"
        "samples = os.environ['ACCUCOR_SAMPLE_COLUMNS'].split(',')\n"
        "outdir = os.environ['ACCUCOR_OUTPUT_DIR']\n"
        "for name in ('original', 'corrected', 'normalized', 'pool'):\n"
        "    with open(os.path.join(outdir, name + '.csv'), 'w', newline='') as f:\n"
        "        w = csv.writer(f); w.writerow(['compound'] + samples); w.writerow(['X'] + ['1'] * len(samples))\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IRUSR)
    config = BlockConfig(
        params={
            "corrector": "accucor2",
            "rscript_path": str(script),
            "resolution": 140000,
            "c13_purity": 1,
            "h2n15_purity": 1,
            "label": "CH",
            "charge": -1,
        }
    )

    _run(IsotopeCorrection(), table, config)

    import json

    env = json.loads(capture.read_text())
    assert env["ACCUCOR_MODE"] == "accucor2"
    assert env["ACCUCOR_RESOLUTION"] == "140000"
    assert env["ACCUCOR_LABEL"] == "CH"
    assert env["ACCUCOR_C13_PURITY"] == "1"
    assert env["ACCUCOR_SAMPLE_COLUMNS"] == "Sample_A,Sample_B"
