#!/usr/bin/env python3
"""Build the package-local documentation bundle consumed by SciStudio core."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIRNAME = "_scistudio_docs"
ENTRY_POINT_GROUPS = (
    "scistudio.blocks",
    "scistudio.types",
    "scistudio.previewers",
)


def _read_pyproject(root: Path) -> dict[str, Any]:
    return tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))


def _top_module(pyproject: dict[str, Any]) -> str:
    entry_points = pyproject.get("project", {}).get("entry-points", {})
    for group in ENTRY_POINT_GROUPS:
        for ref in entry_points.get(group, {}).values():
            module = str(ref).partition(":")[0].split(".")[0]
            if module:
                return module
    raise ValueError("could not derive the top-level package module from SciStudio entry points")


def _package_dir(root: Path, pyproject: dict[str, Any], top_module: str) -> Path:
    wheel_config = pyproject.get("tool", {}).get("hatch", {}).get("build", {}).get("targets", {}).get("wheel", {})
    for package in wheel_config.get("packages", []):
        path = root / str(package)
        if path.name == top_module:
            return path

    fallback = root / "src" / top_module
    if fallback.is_dir():
        return fallback
    raise ValueError(f"could not find source package directory for {top_module!r}")


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("._-")
    return (cleaned or "package").lower()


def _copy_file(src: Path, dest: Path) -> None:
    if not src.is_file():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _surface_rows(snapshot_path: Path) -> list[dict[str, Any]]:
    if not snapshot_path.is_file():
        return []
    try:
        raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    rows = raw.get("surface", [])
    return rows if isinstance(rows, list) else []


def _md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _render_api_index(*, name: str, version: str, description: str, surface_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# API Reference",
        "",
        f"Package: `{name}`",
        f"Version: `{version}`" if version else "Version: unknown",
    ]
    if description:
        lines.extend(["", description])
    lines.extend(
        [
            "",
            "This wheel-bundled reference is generated at package build time so SciStudio",
            "can inject installed package docs into projects without reading package source.",
            "",
            "## Public Surface",
            "",
        ]
    )
    if not surface_rows:
        lines.append("No committed public surface snapshot was found.")
    else:
        lines.extend(
            [
                "| Symbol | Kind | Stability | Since |",
                "| --- | --- | --- | --- |",
            ]
        )
        for row in sorted(surface_rows, key=lambda item: str(item.get("symbol", ""))):
            lines.append(
                "| "
                f"`{_md(row.get('symbol'))}` | "
                f"{_md(row.get('kind'))} | "
                f"{_md(row.get('tier'))} | "
                f"{_md(row.get('since'))} |"
            )
    lines.extend(
        [
            "",
            "## Source Material",
            "",
            "- `mkdocs-reference.md` is the package's MkDocs/mkdocstrings reference source.",
            "- `public_surface.snapshot.json` is the frozen ADR-052 public surface used by CI.",
            "- `package-overview.md` is the human-facing package catalog.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_agent_reference(*, name: str, version: str, description: str) -> str:
    lines = [
        f"# {name} Agent Reference",
        "",
        f"Version: `{version}`" if version else "Version: unknown",
    ]
    if description:
        lines.extend(["", description])
    lines.extend(
        [
            "",
            "Use this bundled reference when writing custom SciStudio blocks against",
            "types, constructors, helpers, blocks, or previewers exported by this installed package.",
            "",
            "## Start Here",
            "",
            "- `api-reference/index.md` lists the public reuse surface and stability tiers.",
            "- The project user guide also receives this package's overview under",
            "  `user-guide/package-reference/<package-slug>/`.",
            "",
            "Do not rely on package internals that are absent from the public surface.",
            "",
        ]
    )
    return "\n".join(lines)


def build_package_docs(root: Path = ROOT) -> Path:
    """Create ``src/<module>/_scistudio_docs`` and return its path."""
    root = root.resolve()
    pyproject = _read_pyproject(root)
    project = pyproject.get("project", {})
    name = str(project.get("name", "package"))
    version = str(project.get("version", ""))
    description = str(project.get("description", ""))
    top_module = _top_module(pyproject)
    package_dir = _package_dir(root, pyproject, top_module)
    docs_root = package_dir / DOCS_DIRNAME

    if docs_root.exists():
        shutil.rmtree(docs_root)
    (docs_root / "api-reference").mkdir(parents=True)
    (docs_root / "agent-reference").mkdir(parents=True)
    (docs_root / "user-guide").mkdir(parents=True)

    manifest = {
        "schema_version": 1,
        "package_name": name,
        "name": name,
        "title": name,
        "version": version,
        "slug": _slug(name),
        "description": description,
        "generated_by": "scripts/build_package_docs.py",
    }
    (docs_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    snapshot = root / "tests" / "api" / "public_surface.snapshot.json"
    api_index = _render_api_index(
        name=name,
        version=version,
        description=description,
        surface_rows=_surface_rows(snapshot),
    )
    (docs_root / "api-reference" / "index.md").write_text(api_index, encoding="utf-8")
    _copy_file(root / "docs" / "reference.md", docs_root / "api-reference" / "mkdocs-reference.md")
    _copy_file(root / "docs" / "package-overview.md", docs_root / "api-reference" / "package-overview.md")
    _copy_file(snapshot, docs_root / "api-reference" / "public_surface.snapshot.json")

    agent_reference = _render_agent_reference(name=name, version=version, description=description)
    (docs_root / "agent-reference" / "README.md").write_text(agent_reference, encoding="utf-8")

    _copy_file(root / "README.md", docs_root / "user-guide" / "README.md")
    _copy_file(root / "docs" / "package-overview.md", docs_root / "user-guide" / "package-overview.md")
    _copy_file(root / "docs" / "ui-style-guide.md", docs_root / "user-guide" / "ui-style-guide.md")
    _copy_file(root / "docs" / "DOCUMENTATION-STANDARD.md", docs_root / "user-guide" / "DOCUMENTATION-STANDARD.md")
    return docs_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root to build from")
    args = parser.parse_args(argv)

    docs_root = build_package_docs(args.root)
    print(docs_root.relative_to(args.root.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
