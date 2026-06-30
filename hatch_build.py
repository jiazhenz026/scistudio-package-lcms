"""Hatch build hook that stages SciStudio package docs before wheel creation."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from types import ModuleType

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_DOCS_ROOT_KEY = "scistudio_docs_root"


def _load_docs_builder(root: Path) -> ModuleType:
    script = root / "scripts" / "build_package_docs.py"
    spec = importlib.util.spec_from_file_location("_scistudio_build_package_docs", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CustomBuildHook(BuildHookInterface):
    """Generate ``_scistudio_docs`` and include it in wheel artifacts."""

    def initialize(self, version: str, build_data: dict) -> None:
        if self.target_name != "wheel":
            return

        root = Path(self.root)
        docs_root = _load_docs_builder(root).build_package_docs(root)
        artifact = f"{docs_root.relative_to(root).as_posix()}/**/*"
        build_data.setdefault("artifacts", [])
        if artifact not in build_data["artifacts"]:
            build_data["artifacts"].append(artifact)
        build_data[_DOCS_ROOT_KEY] = str(docs_root)

    def finalize(self, version: str, build_data: dict, artifact_path: str) -> None:
        if self.target_name != "wheel":
            return

        docs_root = build_data.get(_DOCS_ROOT_KEY)
        if isinstance(docs_root, str):
            shutil.rmtree(docs_root, ignore_errors=True)
