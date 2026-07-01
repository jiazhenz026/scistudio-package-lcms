"""Open raw LC-MS files in El-MAVEN and collect the exported peak table (an AppBlock).

This block is an interactive launcher rather than a headless driver: it hands the
input ``.mzML`` / ``.mzXML`` files to the El-MAVEN application, opens it, and waits
for the user to export a peak table. El-MAVEN's GUI ``main()`` loads every positional
command-line argument through its file loader, so this block overrides the ADR-052 §7
``prepare_launch`` hook (core ``AppBlock``) to return the sample files' on-disk paths —
El-MAVEN then auto-loads them on launch. The user tunes detection parameters and
exports the peak table *inside* El-MAVEN; those knobs live in the application, not in
this block's config.

The user exports the peaks CSV into the configured *Save Outputs At* directory; ``run``
watches that directory and reconstructs the CSV into the package's standard
:class:`LCMSFeatureTable` (reusing :class:`LoadPeakTable`), so the block's output is the
same type the rest of the LCMS blocks consume.

Runtime requirement: the host must have the El-MAVEN application; its path is the
block's ``app_command`` config (*Executable Path*, a file browser in the UI).
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, ClassVar

from scistudio.blocks.app import AppBlock
from scistudio.blocks.base import BlockConfig, InputPort, OutputPort
from scistudio.core.types import Artifact, Collection
from scistudio.stability import stable

from scistudio_blocks_lcms.blocks.load_peak_table import LoadPeakTable
from scistudio_blocks_lcms.types import LCMSFeatureTable

_MS_EXTENSIONS = (".mzml", ".mzxml")


@stable(since="0.1.0")
class ElMaven(AppBlock):
    """Open raw LC-MS files in El-MAVEN; collect the exported peak table as a feature table."""

    name: ClassVar[str] = "El-MAVEN Peak Detection"
    description: ClassVar[str] = "Open raw mzML/mzXML files in El-MAVEN; collect the exported peak table."

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
                "title": "Executable Path",
                "description": "Path to the El-MAVEN application.",
                "ui_widget": "file_browser",
                "ui_priority": 0,
            },
            "output_dir": {
                "type": ["string", "null"],
                "default": None,
                "title": "Save Outputs At",
                "description": (
                    "Directory you export El-MAVEN's peak table into; the block reads it back as a feature table."
                ),
                "ui_widget": "directory_browser",
                "ui_priority": 1,
            },
        },
        "required": ["app_command"],
    }

    def prepare_launch(self, exchange_dir: Path, output_dir: Path, config: BlockConfig) -> list[str]:
        """Return the input sample files as positional arguments for El-MAVEN.

        El-MAVEN's GUI loads every positional command-line argument through its file
        loader, so passing the sample paths opens the application with the data already
        loaded. The block points it at the input Artifacts' own on-disk files (captured
        in :meth:`run`): copying large raw LC-MS files would be wasteful, and the user
        drives detection and export inside the application. The output directory is not
        passed on the command line — the user exports there manually. The fallback glob
        covers a direct ``prepare_launch`` call.
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
        return sample_files

    def run(self, inputs: dict[str, Collection], config: BlockConfig) -> dict[str, Collection]:
        """Open El-MAVEN on the input samples and reconstruct the exported CSV into a feature table."""
        # TODO(#8): hand El-MAVEN the input paths directly instead of staging.
        #   Core AppBlock cannot stage a multi-item Collection of files (it unpacks
        #   to a bare list the bridge serialises as object reprs), so the block
        #   references the input Artifacts' original file_path and passes those paths
        #   as El-MAVEN's positional arguments. When core gains multi-file staging
        #   this can move to staged inputs. Out of scope per owner decision
        #   (package-only work).
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

        self._sample_paths = sample_paths

        # The user exports El-MAVEN's peak table into the configured output dir. When
        # none is set, use an owned temp dir: core AppBlock deletes a *temp* exchange
        # dir in its ``finally`` (taking ``exchange_dir/outputs`` with it) before this
        # override can reconstruct the CSV. A user-set output dir is persistent, so we
        # honour it untouched.
        owned_dir: Path | None = None
        if config.get("output_dir"):
            run_config = config
        else:
            owned_dir = Path(tempfile.mkdtemp(prefix="scistudio_elmaven_out_"))
            run_config = config.model_copy(update={"params": {**config.params, "output_dir": str(owned_dir)}})
        try:
            raw_outputs = super().run(inputs, run_config)

            loader = LoadPeakTable()
            load_config = {"polarity": "auto"}
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
                raise RuntimeError(
                    "ElMaven: no peak table was exported. Export groups as CSV into the "
                    "output directory before closing El-MAVEN."
                )
            return {"peaks": Collection(tables, item_type=LCMSFeatureTable)}
        finally:
            self._sample_paths = None
            if owned_dir is not None:
                shutil.rmtree(owned_dir, ignore_errors=True)


__all__ = ["ElMaven"]
