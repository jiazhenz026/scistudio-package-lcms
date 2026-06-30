"""Natural isotope abundance correction (AccuCor / AccuCor2).

A self-contained block that ships an embedded R script (``_r/isotope_correction.R``)
and runs it with ``Rscript`` to apply natural-isotope-abundance correction to an
:class:`LCMSFeatureTable`. ``corrector="accucor"`` runs AccuCor (single-isotope
tracing); ``corrector="accucor2"`` runs AccuCor2 (dual-isotope, e.g. ¹³C+²H),
following the reference flux pipeline.

Both correctors return four matrices — Original, Corrected, Normalized, and the
pool size — which this block emits on four output ports. The feature table
crosses the Python↔R boundary as CSV; any Excel the R packages need is written
inside R.

Runtime requirement: the host must have ``Rscript`` on ``PATH`` (or set via the
``rscript_path`` config) and the relevant R packages installed
(``accucor`` / ``accucor2`` and, for AccuCor2, ``dplyr`` / ``tidyr`` /
``stringr`` / ``openxlsx``). The block fails with a clear message otherwise.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any, ClassVar

from scistudio.blocks.base import BlockConfig, InputPort, OutputPort
from scistudio.blocks.process import ProcessBlock
from scistudio.core.types import Collection
from scistudio.stability import stable

from scistudio_blocks_lcms.types import ELMAVEN_ANNOTATION_COLUMNS, LCMSFeatureTable

_R_SCRIPT = "isotope_correction.R"

#: Output ports, in the order the correctors report their matrices. Each maps to
#: a ``<name>.csv`` the embedded R writes into the run's output directory.
_OUTPUTS = ("original", "corrected", "normalized", "pool")

#: Human-facing sheet names per output port — stamped as the table's
#: ``display_name`` (and ``sheet_name``) so the previewer / data router show the
#: corrector matrix's identity (#1812) instead of an unnamed table.
_SHEET_NAMES = {
    "original": "Original",
    "corrected": "Corrected",
    "normalized": "Normalized",
    "pool": "Pool size",
}


def _resolve_rscript(config: BlockConfig) -> str:
    """Return the Rscript executable path, or raise a clear error."""
    configured = config.get("rscript_path")
    if configured:
        return str(configured)
    found = shutil.which("Rscript")
    if not found:
        raise RuntimeError(
            "Rscript was not found on PATH. Install R and the accucor/accucor2 "
            "packages, or set the block's 'rscript_path' config."
        )
    return found


@stable(since="0.1.0")
class IsotopeCorrection(ProcessBlock):
    """Correct natural isotope abundance in an LCMS feature table via AccuCor/AccuCor2."""

    name: ClassVar[str] = "Isotope Correction"
    description: ClassVar[str] = "Natural isotope abundance correction (AccuCor / AccuCor2) for a feature table."
    version: ClassVar[str] = "0.1.0"
    algorithm: ClassVar[str] = "accucor"

    input_ports: ClassVar[list[InputPort]] = [
        InputPort(
            name="features",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            required=True,
            description="Feature table(s) to correct.",
        ),
    ]
    output_ports: ClassVar[list[OutputPort]] = [
        OutputPort(
            name="original",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            description="Original (uncorrected) abundances as parsed by the corrector.",
        ),
        OutputPort(
            name="corrected",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            description="Natural-abundance-corrected abundances.",
        ),
        OutputPort(
            name="normalized",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            description="Corrected abundances normalized to the labeled pool.",
        ),
        OutputPort(
            name="pool",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            description="Per-compound total pool size.",
        ),
    ]

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "corrector": {
                "type": "string",
                "enum": ["accucor", "accucor2"],
                "default": "accucor",
                "title": "Corrector",
                "description": "AccuCor (single-isotope) or AccuCor2 (dual-isotope, e.g. 13C+2H).",
                "ui_priority": 0,
            },
            "resolution": {
                "type": "number",
                "default": 100000,
                "title": "MS Resolution",
                "description": "Mass-spectrometer resolving power (e.g. 100000 for an Exactive).",
                "ui_priority": 1,
            },
            "resolution_defined_at": {
                "type": "number",
                "default": 200,
                "title": "Resolution Defined At (m/z)",
                "ui_priority": 2,
            },
            "c13_purity": {
                "type": ["number", "null"],
                "default": None,
                "title": "¹³C Tracer Purity",
                "description": "Isotopic purity of the 13C tracer (0–1). Blank uses the corrector default.",
                "ui_priority": 3,
            },
            "h2n15_purity": {
                "type": ["number", "null"],
                "default": None,
                "title": "²H/¹⁵N Tracer Purity (AccuCor2)",
                "ui_priority": 4,
            },
            "label": {
                "type": "string",
                "default": "CH",
                "title": "Label Elements (AccuCor2)",
                "description": "Dual-label elements, e.g. 'CH' (13C+2H) or 'CN' (13C+15N).",
                "ui_priority": 5,
            },
            "charge": {
                "type": "integer",
                "default": -1,
                "title": "Ion Charge (AccuCor2)",
                "ui_priority": 6,
            },
            "rscript_path": {
                "type": "string",
                "title": "Rscript Path",
                "description": "Override the Rscript executable. Blank resolves it from PATH.",
                "ui_widget": "file_browser",
                "ui_priority": 7,
            },
        },
    }

    def run(self, inputs: dict[str, Collection], config: BlockConfig) -> dict[str, Collection]:
        """Correct each input feature table and emit the four corrector matrices.

        Overrides :meth:`ProcessBlock.run` because the block has multiple output
        ports (ADR-027: a multi-port block owns its own iteration).
        """
        features = inputs["features"]
        rscript = _resolve_rscript(config)
        corrector = str(config.get("corrector") or "accucor")

        collected: dict[str, list[LCMSFeatureTable]] = {name: [] for name in _OUTPUTS}
        for item in features:
            for name, table in self._correct_one(item, config, rscript, corrector).items():
                collected[name].append(self._auto_flush(table))

        return {
            name: (Collection(tables) if tables else Collection([], item_type=LCMSFeatureTable))
            for name, tables in collected.items()
        }

    def _correct_one(
        self,
        item: Any,
        config: BlockConfig,
        rscript: str,
        corrector: str,
    ) -> dict[str, LCMSFeatureTable]:
        """Run the corrector on one feature table; return the four output tables."""
        import pandas as pd

        if not isinstance(item, LCMSFeatureTable):
            raise TypeError(f"IsotopeCorrection expects an LCMSFeatureTable, got {type(item).__name__}")

        frame = item.to_pandas()
        meta = item.meta
        if meta is not None and meta.sample_columns:
            sample_columns = list(meta.sample_columns)
        else:
            sample_columns = [c for c in frame.columns if c not in ELMAVEN_ANNOTATION_COLUMNS]

        with tempfile.TemporaryDirectory(prefix="scistudio_accucor_") as tmp:
            workdir = Path(tmp)
            input_csv = workdir / "input.csv"
            output_dir = workdir / "out"
            output_dir.mkdir()
            frame.to_csv(input_csv, index=False)

            env = self._build_env(config, corrector, input_csv, output_dir, workdir, sample_columns)
            with as_file(files("scistudio_blocks_lcms.blocks").joinpath("_r", _R_SCRIPT)) as script_path:
                proc = subprocess.run(
                    [rscript, str(script_path)],
                    env=env,
                    cwd=str(workdir),
                    capture_output=True,
                    text=True,
                )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"{corrector} isotope correction failed (exit {proc.returncode}).\nstderr:\n{proc.stderr.strip()}"
                )

            tables: dict[str, LCMSFeatureTable] = {}
            for name in _OUTPUTS:
                path = output_dir / f"{name}.csv"
                if not path.exists():
                    raise RuntimeError(f"{corrector} produced no '{name}' output.\nstderr:\n{proc.stderr.strip()}")
                try:
                    out_frame = pd.read_csv(path)
                except pd.errors.EmptyDataError:
                    out_frame = pd.DataFrame()
                table = LCMSFeatureTable.from_wide(
                    out_frame,
                    sample_columns=sample_columns,
                    polarity=meta.polarity if meta is not None else None,
                    software=meta.software if meta is not None else None,
                    labeled=meta.labeled if meta is not None else True,
                )
                # Name the table after its corrector matrix so the previewer /
                # data router show "Corrected" / "Normalized" / … instead of an
                # unnamed table (#1812). ``sheet_name`` is the structural identity
                # (save grouping); ``display_name`` is the presentation hook.
                sheet = _SHEET_NAMES[name]
                table.user["sheet_name"] = sheet
                table.user["display_name"] = sheet
                tables[name] = table
        return tables

    @staticmethod
    def _build_env(
        config: BlockConfig,
        corrector: str,
        input_csv: Path,
        output_dir: Path,
        workdir: Path,
        sample_columns: list[str],
    ) -> dict[str, str]:
        """Marshal the block config into the embedded R script's env contract."""
        import os

        env = dict(os.environ)
        env["ACCUCOR_MODE"] = corrector
        env["ACCUCOR_INPUT"] = str(input_csv)
        env["ACCUCOR_OUTPUT_DIR"] = str(output_dir)
        env["ACCUCOR_WORKDIR"] = str(workdir)
        env["ACCUCOR_SAMPLE_COLUMNS"] = ",".join(sample_columns)
        env["ACCUCOR_RESOLUTION"] = str(config.get("resolution") if config.get("resolution") is not None else 100000)
        env["ACCUCOR_RES_DEFINED_AT"] = str(
            config.get("resolution_defined_at") if config.get("resolution_defined_at") is not None else 200
        )
        c13 = config.get("c13_purity")
        if c13 is not None:
            env["ACCUCOR_C13_PURITY"] = str(c13)
        h2n15 = config.get("h2n15_purity")
        if h2n15 is not None:
            env["ACCUCOR_H2N15_PURITY"] = str(h2n15)
        env["ACCUCOR_LABEL"] = str(config.get("label") or "CH")
        env["ACCUCOR_CHARGE"] = str(config.get("charge") if config.get("charge") is not None else -1)
        return env


__all__ = ["IsotopeCorrection"]
