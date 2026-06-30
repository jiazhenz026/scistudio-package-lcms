"""Run El-MAVEN peak detection on raw LC-MS files (an AppBlock).

El-MAVEN's headless ``peakdetector`` is a config-driven CLI: it reads an XML
config that lists each sample file by absolute path plus an output directory,
and is launched as ``peakdetector --xml config.xml`` rather than receiving a
directory. This block therefore overrides the ADR-052 §7 ``prepare_launch``
hook (core ``AppBlock``): after the engine stages the input ``.mzML`` / ``.mzXML``
files into the exchange directory, it writes the config — one ``<samples>`` entry
per staged file so **every file in the input collection is injected** — and
returns ``["--xml", <config>]``.

peakdetector writes a peaks CSV into the watched output directory; ``run`` then
reconstructs it into the package's standard :class:`LCMSFeatureTable` (reusing
:class:`LoadPeakTable`), so the block's output is the same type the rest of the
LCMS blocks consume.

Runtime requirement: the host must have El-MAVEN's ``peakdetector`` executable;
its path is the block's ``app_command`` config (a file browser in the UI).
"""

from __future__ import annotations

import shutil
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, ClassVar

from scistudio.blocks.app import AppBlock
from scistudio.blocks.base import BlockConfig, InputPort, OutputPort
from scistudio.core.types import Artifact, Collection
from scistudio.stability import stable

from scistudio_blocks_lcms.blocks.load_peak_table import LoadPeakTable
from scistudio_blocks_lcms.types import LCMSFeatureTable

_MS_EXTENSIONS = (".mzml", ".mzxml")
_IONIZATION_MODE = {"positive": "1", "negative": "-1", "neutral": "0"}


@stable(since="0.1.0")
class ElMaven(AppBlock):
    """Detect peaks across raw LC-MS files with El-MAVEN; output a feature table."""

    name: ClassVar[str] = "El-MAVEN Peak Detection"
    description: ClassVar[str] = "Run El-MAVEN peakdetector over raw mzML/mzXML files into a feature table."

    # AppBlock is variadic by default; pin our ports so the canvas shows the
    # right types and the output is the package's standard table type.
    variadic_inputs: ClassVar[bool] = False
    variadic_outputs: ClassVar[bool] = False
    output_patterns: ClassVar[list[str]] = ["*.csv"]

    # The input files' on-disk paths, captured in ``run`` for ``prepare_launch``.
    _sample_paths: list[str] | None = None

    input_ports: ClassVar[list[InputPort]] = [
        InputPort(
            name="samples",
            accepted_types=[Artifact],
            is_collection=True,
            required=True,
            description="Raw LC-MS sample files (.mzML / .mzXML).",
        ),
    ]
    output_ports: ClassVar[list[OutputPort]] = [
        OutputPort(
            name="peaks",
            accepted_types=[LCMSFeatureTable],
            is_collection=True,
            description="Detected peak table.",
        ),
    ]

    config_schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "app_command": {
                "type": "string",
                "title": "peakdetector Path",
                "description": "Path to El-MAVEN's peakdetector executable.",
                "ui_widget": "file_browser",
                "ui_priority": 0,
            },
            "polarity": {
                "type": "string",
                "enum": ["negative", "positive", "neutral"],
                "default": "negative",
                "title": "Ionization Mode",
                "ui_priority": 1,
            },
            "ppm": {
                "type": "number",
                "default": 20.0,
                "title": "Mass Tolerance (ppm)",
                "ui_priority": 2,
            },
            "min_intensity": {
                "type": "number",
                "default": 1000.0,
                "title": "Min Peak Intensity",
                "ui_priority": 3,
            },
            "min_quality": {
                "type": "number",
                "default": 0.5,
                "title": "Min Peak Quality (0–1)",
                "ui_priority": 4,
            },
            "min_good_group_count": {
                "type": "integer",
                "default": 1,
                "title": "Min Good Peak Count",
                "ui_priority": 5,
            },
            "min_signal_baseline_ratio": {
                "type": "number",
                "default": 2.0,
                "title": "Min Signal/Baseline Ratio",
                "ui_priority": 6,
            },
            "mz_min": {"type": "number", "default": 0.0, "title": "Min m/z", "ui_priority": 7},
            "mz_max": {"type": "number", "default": 100000.0, "title": "Max m/z", "ui_priority": 8},
            "rt_min": {"type": "number", "default": 0.0, "title": "Min RT (min)", "ui_priority": 9},
            "rt_max": {"type": "number", "default": 100000.0, "title": "Max RT (min)", "ui_priority": 10},
            "align_samples": {
                "type": "boolean",
                "default": False,
                "title": "Align Samples",
                "ui_priority": 11,
            },
        },
        "required": ["app_command"],
    }

    def prepare_launch(self, exchange_dir: Path, output_dir: Path, config: BlockConfig) -> list[str]:
        """Write the peakdetector XML config from the input files and config.

        peakdetector reads the sample files by absolute path, so the block points
        it at the input Artifacts' own on-disk files (captured in :meth:`run`):
        core ``AppBlock`` cannot stage a *multi-item* collection of files into the
        exchange directory, and copying large raw LC-MS files would be wasteful
        anyway. The fallback glob covers a direct ``prepare_launch`` call.
        """
        sample_files = list(getattr(self, "_sample_paths", None) or [])
        if not sample_files:
            sample_files = [
                str(p)
                for p in sorted((exchange_dir / "inputs").rglob("*"))
                if p.is_file() and p.suffix.lower() in _MS_EXTENSIONS
            ]
        if not sample_files:
            raise ValueError("ElMaven: no .mzML/.mzXML sample files were provided on the 'samples' input.")

        config_path = exchange_dir / "peakdetector_config.xml"
        self._write_config_xml(config_path, [Path(f) for f in sample_files], output_dir, config)
        return ["--xml", str(config_path)]

    @staticmethod
    def _write_config_xml(path: Path, sample_files: list[Path], output_dir: Path, config: BlockConfig) -> None:
        """Build the El-MAVEN peakdetector XML config (see ElMaven CLI docs)."""

        def _num(key: str, default: float) -> str:
            value = config.get(key)
            return str(value if value is not None else default)

        root = ET.Element("Arguments")

        options = ET.SubElement(root, "OptionsDialogArguments")
        ET.SubElement(options, "ionizationMode", value=_IONIZATION_MODE.get(str(config.get("polarity")), "-1"))
        ET.SubElement(options, "charge", value="1")
        ET.SubElement(options, "compoundPPMWindow", value=_num("ppm", 20.0))

        peaks = ET.SubElement(root, "PeaksDialogArguments")
        ET.SubElement(peaks, "processAllSlices", value="1")  # automated, database-free detection
        ET.SubElement(peaks, "pullIsotopes", value="0000")
        ET.SubElement(peaks, "ppmMerge", value=_num("ppm", 20.0))
        ET.SubElement(peaks, "minGroupIntensity", value=_num("min_intensity", 1000.0))
        ET.SubElement(peaks, "minQuality", value=_num("min_quality", 0.5))
        ET.SubElement(peaks, "minSignalBaseLineRatio", value=_num("min_signal_baseline_ratio", 2.0))
        ET.SubElement(peaks, "minGoodGroupCount", value=_num("min_good_group_count", 1))
        ET.SubElement(peaks, "minScanMz", value=_num("mz_min", 0.0))
        ET.SubElement(peaks, "maxScanMz", value=_num("mz_max", 100000.0))
        ET.SubElement(peaks, "minScanRt", value=_num("rt_min", 0.0))
        ET.SubElement(peaks, "maxScanRt", value=_num("rt_max", 100000.0))

        general = ET.SubElement(root, "GeneralArguments")
        for sample in sample_files:
            ET.SubElement(general, "samples", value=str(sample))
        ET.SubElement(general, "outputdir", value=str(output_dir))
        ET.SubElement(general, "savemzroll", value="0")
        ET.SubElement(general, "saveEicJson", value="0")
        ET.SubElement(general, "alignSamples", value="1" if config.get("align_samples") else "0")

        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)

    def run(self, inputs: dict[str, Collection], config: BlockConfig) -> dict[str, Collection]:
        """Run peakdetector (via AppBlock) and reconstruct its CSV into a feature table."""
        # TODO(#8): simplify once core AppBlock stages multi-item input collections.
        #   Core AppBlock currently cannot stage a multi-item Collection of files
        #   (it unpacks to a bare list the bridge serialises as object reprs), and
        #   deletes its temp exchange dir before this override reads outputs. So we
        #   reference the input Artifacts' original file_path and use an owned
        #   output_dir. Out of scope per owner decision (package-only work).
        #   Followup: https://github.com/jiazhenz026/scistudio-package-lcms/issues/8
        sample_paths: list[str] = []
        for artifact in inputs["samples"]:
            file_path = getattr(artifact, "file_path", None)
            if file_path is None:
                raise ValueError(
                    "ElMaven requires on-disk sample files (Artifact.file_path). Load the "
                    "mzML/mzXML files as file Artifacts before this block."
                )
            sample_paths.append(str(Path(file_path).resolve()))

        # Use an owned, persistent output dir: core AppBlock deletes its (temp)
        # exchange dir in its own ``finally``, which would take the peaks CSV with
        # it before this override can read it. Writing results outside the
        # exchange dir keeps them alive until reconstruction, then we clean up.
        self._sample_paths = sample_paths
        out_dir = Path(tempfile.mkdtemp(prefix="scistudio_elmaven_out_"))
        try:
            run_config = config.model_copy(update={"params": {**config.params, "output_dir": str(out_dir)}})
            raw_outputs = super().run(inputs, run_config)

            loader = LoadPeakTable()
            load_config = {"polarity": config.get("polarity", "auto")}
            tables: list[LCMSFeatureTable] = []
            for collection in raw_outputs.values():
                for artifact in collection:
                    file_path = getattr(artifact, "file_path", None)
                    if file_path is None:
                        continue
                    path = Path(file_path)
                    if path.suffix.lower() in (".csv", ".tab", ".tsv"):
                        tables.append(self._auto_flush(loader.load_file(path, load_config)))

            if not tables:
                raise RuntimeError("ElMaven: peakdetector produced no peaks CSV to load.")
            return {"peaks": Collection(tables, item_type=LCMSFeatureTable)}
        finally:
            self._sample_paths = None
            shutil.rmtree(out_dir, ignore_errors=True)


__all__ = ["ElMaven"]
