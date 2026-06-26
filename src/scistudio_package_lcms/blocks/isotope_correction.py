"""Natural-abundance isotope correction via the R AccuCor / AccuCor2 packages.

This block wraps the published R packages rather than re-implementing the
correction (re-implementation would need its own validation paper). The Python
side prepares the inputs, invokes a bundled, non-editable R wrapper
(``r/accucor_run.R``) through ``Rscript``, and reads the three result tables
back as :class:`LCMSFeatures`:

- ``corrected``  — natural-abundance-corrected isotopologue intensities
- ``mid``        — normalised mass isotopologue distribution (fractional labeling)
- ``pool_size``  — total pool size per compound

One block, two modes:

- ``single`` → ``accucor::natural_abundance_correction`` (13C / 2H / 15N)
- ``dual``   → ``accucor2::dual_correction`` (13C + 2H)

Requires R with the ``accucor`` / ``accucor2`` packages installed; see the
package README. Core has no system-dependency declaration mechanism, so the
requirement is checked at runtime and reported with a clear error.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, ClassVar

import pandas as pd
from scistudio.blocks.base.config import BlockConfig
from scistudio.blocks.base.ports import InputPort, OutputPort
from scistudio.blocks.process.process_block import ProcessBlock
from scistudio.core.types.collection import Collection

from scistudio_package_lcms import _support
from scistudio_package_lcms.types import LCMSFeatures

#: Identifier / metadata column names that are never sample-intensity columns.
_META_COLUMNS = {
    "label",
    "metagroupid",
    "groupid",
    "goodpeakcount",
    "medmz",
    "medrt",
    "maxquality",
    "isotopelabel",
    "compound",
    "compoundid",
    "formula",
    "expectedrtdiff",
    "ppmdiff",
    "parent",
    "polarity",
    "c13",
    "h2",
    "13c#",
    "2h#",
    "expected?",
}

_TRAILING_INT = re.compile(r"(\d+)\s*$")
_PAIR_INT = re.compile(r"(\d+)-(\d+)\s*$")


def _r_script_path() -> Path:
    return Path(__file__).resolve().parent.parent / "r" / "accucor_run.R"


def sample_columns(frame: pd.DataFrame) -> list[str]:
    """Return numeric columns that are sample intensities (not identifiers)."""
    return [c for c in frame.columns if c.lower() not in _META_COLUMNS and pd.api.types.is_numeric_dtype(frame[c])]


def parse_isotope_label(label: str) -> tuple[int, int]:
    """Parse an El-MAVEN ``isotopeLabel`` into ``(c13_count, h2_count)``.

    Mirrors the lab's AccuCor2 prep: ``PARENT`` -> ``(0, 0)``; a deuterium label
    (``D2...``) contributes to the 2H count; a combined ``N-M`` tail splits into
    ``(13C, 2H)``; otherwise the trailing integer is the 13C count.
    """
    text = str(label)
    if "PARENT" in text.upper():
        return (0, 0)
    if text.startswith("D2"):
        m = _TRAILING_INT.search(text)
        return (0, int(m.group(1)) if m else 0)
    if "D2" in text:
        m = _PAIR_INT.search(text)
        if m:
            return (int(m.group(1)), int(m.group(2)))
    m = _TRAILING_INT.search(text)
    return (int(m.group(1)) if m else 0, 0)


def _require_columns(frame: pd.DataFrame, needed: list[str], *, mode: str) -> None:
    missing = [c for c in needed if c not in frame.columns]
    if missing:
        raise ValueError(
            f"Isotope Correction ({mode}): input is missing required column(s) {missing!r}. "
            f"Available columns: {list(frame.columns)[:12]}..."
        )


def prep_dual_inputs(frame: pd.DataFrame, polarity: str | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the AccuCor2 input table and formula list from a peak table."""
    _require_columns(frame, ["compound", "formula"], mode="dual")
    if polarity not in ("positive", "negative"):
        raise ValueError(
            "Isotope Correction (dual): table polarity is unknown; set it on Load Peak Table "
            "so the molecular charge can be inferred."
        )
    charge = -1 if polarity == "negative" else 1
    samples = sample_columns(frame)
    if not samples:
        raise ValueError("Isotope Correction (dual): no sample-intensity columns found.")

    # 13C# / 2H#: reuse existing count columns when present, else parse the label.
    if "13C#" in frame.columns and "2H#" in frame.columns:
        c13 = frame["13C#"].astype(int)
        h2 = frame["2H#"].astype(int)
    else:
        _require_columns(frame, ["isotopeLabel"], mode="dual")
        parsed = [parse_isotope_label(v) for v in frame["isotopeLabel"]]
        c13 = pd.Series([p[0] for p in parsed], index=frame.index)
        h2 = pd.Series([p[1] for p in parsed], index=frame.index)

    parent = frame["parent"] if "parent" in frame.columns else frame.get("medMz")
    if parent is None:
        raise ValueError("Isotope Correction (dual): input needs a 'parent' or 'medMz' column.")

    head = pd.DataFrame(
        {
            "Compound": frame["compound"].to_numpy(),
            "parent": parent.to_numpy(),
            "13C#": c13.to_numpy(),
            "2H#": h2.to_numpy(),
            "Expected?": 1,
        }
    )
    sample_df = frame[samples].reset_index(drop=True)
    input_df = pd.concat([head, sample_df], axis=1)

    formula_df = (
        frame[["compound", "formula"]]
        .drop_duplicates()
        .rename(columns={"compound": "compoundId"})
        .assign(charge=charge)
        .reset_index(drop=True)
    )
    return input_df, formula_df


class IsotopeCorrection(ProcessBlock):
    """Natural-abundance isotope correction via R AccuCor / AccuCor2.

    Emits corrected isotopologue intensities, the normalised mass isotopologue
    distribution (``mid``), and per-compound pool sizes.
    """

    type_name: ClassVar[str] = "lcms.isotope_correction"
    name: ClassVar[str] = "Isotope Correction"
    description: ClassVar[str] = "Natural-abundance correction (AccuCor / AccuCor2): corrected, MID, pool size."
    version: ClassVar[str] = "0.1.0"
    algorithm: ClassVar[str] = "natural_abundance_correction"
    subcategory: ClassVar[str] = "preprocessing"

    input_ports: ClassVar[list[InputPort]] = [
        InputPort(
            name="features",
            accepted_types=[LCMSFeatures],
            required=True,
            description="Labeled peak table (with isotopologue rows).",
        ),
    ]
    output_ports: ClassVar[list[OutputPort]] = [
        OutputPort(name="corrected", accepted_types=[LCMSFeatures], description="Corrected isotopologue intensities."),
        OutputPort(name="mid", accepted_types=[LCMSFeatures], description="Normalised isotopologue distribution."),
        OutputPort(name="pool_size", accepted_types=[LCMSFeatures], description="Per-compound pool size."),
    ]

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["single", "dual"],
                "default": "single",
                "title": "Correction mode (single = AccuCor, dual = AccuCor2)",
            },
            "tracer": {
                "type": "string",
                "enum": ["13C", "2H", "15N"],
                "default": "13C",
                "title": "Tracer isotope (single mode)",
            },
            "resolution": {"type": "number", "default": 140000, "minimum": 1, "title": "Resolution"},
            "resolution_defined_at": {
                "type": "number",
                "default": 200,
                "minimum": 1,
                "title": "Resolution defined at (m/z)",
            },
            "c13_purity": {"type": "number", "default": 1.0, "minimum": 0, "maximum": 1, "title": "13C tracer purity"},
            "h2n15_purity": {
                "type": "number",
                "default": 1.0,
                "minimum": 0,
                "maximum": 1,
                "title": "2H/15N tracer purity",
            },
        },
        "required": ["mode"],
    }

    def run(self, inputs: dict[str, Collection], config: BlockConfig) -> dict[str, Collection]:
        features = _support.coerce_features(inputs.get("features"), block=self.name, port="features")
        frame = _support.features_pandas(features)

        mode = str(config.get("mode", "single"))
        if mode not in ("single", "dual"):
            raise ValueError(f"{self.name}: unknown mode {mode!r}")
        resolution = float(config.get("resolution", 140000))
        res_def_at = float(config.get("resolution_defined_at", 200))
        c13_purity = float(config.get("c13_purity", 1.0))
        h2n15_purity = float(config.get("h2n15_purity", 1.0))
        tracer = str(config.get("tracer", "13C"))

        rscript = shutil.which("Rscript")
        if rscript is None:
            raise RuntimeError(
                f"{self.name} requires R (Rscript) with the AccuCor/AccuCor2 packages installed. "
                'Install R and run: Rscript -e \'devtools::install_github("XiaoyangSu/AccuCor"); '
                'devtools::install_github("wangyujue23/AccuCor2")\'.'
            )

        polarity = features.meta.polarity if features.meta is not None else None
        exchange = Path(tempfile.mkdtemp(prefix="scistudio_accucor_"))
        try:
            if mode == "dual":
                input_df, formula_df = prep_dual_inputs(frame, polarity)
                input_df.to_excel(exchange / "input.xlsx", sheet_name="Sheet 1", index=False)
                formula_df.to_csv(exchange / "formula.csv", index=False)
                single_purity = c13_purity
            else:
                # Single mode: AccuCor reads the El-MAVEN table verbatim.
                frame.to_excel(exchange / "input.xlsx", index=False)
                single_purity = c13_purity if tracer == "13C" else h2n15_purity

            proc = subprocess.run(
                [
                    rscript,
                    str(_r_script_path()),
                    str(exchange),
                    mode,
                    str(resolution),
                    str(res_def_at),
                    str(single_purity),
                    str(h2n15_purity),
                ],
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"{self.name}: AccuCor R correction failed (exit {proc.returncode}).\n{proc.stderr.strip()[-1500:]}"
                )

            corrected = pd.read_csv(exchange / "corrected.csv")
            mid = pd.read_csv(exchange / "mid.csv")
            pool_size = pd.read_csv(exchange / "pool_size.csv")
        finally:
            shutil.rmtree(exchange, ignore_errors=True)

        return {
            "corrected": _support.features_collection(self._auto_flush(_support.derive_features(features, corrected))),
            "mid": _support.features_collection(self._auto_flush(_support.derive_features(features, mid))),
            "pool_size": _support.features_collection(self._auto_flush(_support.derive_features(features, pool_size))),
        }


__all__ = ["IsotopeCorrection", "parse_isotope_label", "prep_dual_inputs", "sample_columns"]
