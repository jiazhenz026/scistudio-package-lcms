#!/usr/bin/env python3
"""Compute / freeze this package's public API surface (ADR-052 §7, §15).

The package's public surface is **every symbol in every public ``__all__``** plus
the decorated members of each exported class (``T.Meta``, ``T.from_<domain>``),
each with its ADR-052 §5 stability tier and ``Since`` — read through the single
``scistudio.stability.get_stability`` path the contract validator and the
generated reference also use, so the snapshot, the docs, and the contract can
never disagree (ADR-052 §15).

The surface is written to a committed golden snapshot
(``tests/api/public_surface.snapshot.json``). The freeze test recomputes the
live surface and diffs it against the snapshot:

* An accidental refactor that adds, removes, renames, or re-tiers a public
  symbol makes the diff non-empty → CI fails. You cannot drift the surface by
  editing code.
* An intentional change is a reviewable ``+added`` / ``-removed`` / tier-or-
  ``Since`` diff in the snapshot, owner-reviewed via CODEOWNERS on
  ``tests/api/**``.

Usage::

    python scripts/snapshot_api.py            # --check (default): diff, exit 1 on drift
    python scripts/snapshot_api.py --write     # regenerate the snapshot after an
                                               # intentional, documented change

Requires ``scistudio`` (core) installed — CI installs it from the private repo.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import pkgutil
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = ROOT / "tests" / "api" / "public_surface.snapshot.json"

BLOCKS_GROUP = "scistudio.blocks"
TYPES_GROUP = "scistudio.types"
PREVIEWERS_GROUP = "scistudio.previewers"


def _top_module() -> str:
    """The package's top-level import module, derived from its entry points."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    entry_points = pyproject.get("project", {}).get("entry-points", {})
    for group in (BLOCKS_GROUP, TYPES_GROUP, PREVIEWERS_GROUP):
        for ref in entry_points.get(group, {}).values():
            return ref.partition(":")[0].split(".")[0]
    raise SystemExit("no entry points to derive the package's top module from")


def _public_modules(top_name: str) -> list[Any]:
    """The top package plus every submodule with no underscore-prefixed component."""
    top = importlib.import_module(top_name)
    modules = [top]
    for info in pkgutil.walk_packages(getattr(top, "__path__", []), prefix=f"{top.__name__}."):
        tail = info.name[len(top.__name__) + 1 :]
        if any(part.startswith("_") for part in tail.split(".")):
            continue
        modules.append(importlib.import_module(info.name))
    return modules


def _entry(symbol_id: str, kind: str, info: Any) -> dict[str, Any]:
    return {
        "symbol": symbol_id,
        "kind": kind,
        "tier": getattr(info, "tier", None),
        "since": getattr(info, "since", None),
    }


def compute_surface(top_name: str) -> dict[str, Any]:
    """Return the package's public surface as a deterministic, JSON-able dict."""
    from scistudio.stability import get_stability

    top = importlib.import_module(top_name)
    version = getattr(top, "__version__", None)

    # Keyed by canonical symbol id so re-exports (a type exported at the top
    # level *and* from its defining module) collapse to one entry.
    surface: dict[str, dict[str, Any]] = {}

    def _record(obj: Any, export_module: str, export_name: str) -> None:
        target = getattr(obj, "__func__", obj)  # unwrap classmethod/staticmethod
        qualname = getattr(target, "__qualname__", None)
        if qualname is None:  # data constant — keyed by its export site
            symbol_id = f"{export_module}:{export_name}"
            kind = "data"
        else:
            module = getattr(target, "__module__", export_module)
            symbol_id = f"{module}:{qualname}"
            if inspect.isclass(obj):
                kind = "class"
            elif isinstance(obj, classmethod):
                kind = "classmethod"
            elif isinstance(obj, staticmethod):
                kind = "staticmethod"
            else:
                kind = "function"
        surface[symbol_id] = _entry(symbol_id, kind, get_stability(obj))

    for mod in _public_modules(top_name):
        for name in getattr(mod, "__all__", []):
            obj = getattr(mod, name)
            _record(obj, mod.__name__, name)
            # Descend one level into exported classes for their own decorated
            # members (the §13.1 contract members: T.Meta, T.from_<domain>).
            # Only own __dict__ members, so inherited core symbols never leak in.
            if inspect.isclass(obj):
                for member_name, member in vars(obj).items():
                    if member_name.startswith("_"):
                        continue
                    if get_stability(member) is not None:
                        _record(member, mod.__name__, member_name)

    return {
        "package": top_name,
        "version": version,
        "surface": sorted(surface.values(), key=lambda e: e["symbol"]),
    }


def _serialize(surface: dict[str, Any]) -> str:
    return json.dumps(surface, indent=2, sort_keys=True) + "\n"


def _diff(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    exp = {e["symbol"]: e for e in expected.get("surface", [])}
    act = {e["symbol"]: e for e in actual.get("surface", [])}
    lines: list[str] = []
    if expected.get("version") != actual.get("version"):
        lines.append(f"  version: {expected.get('version')!r} -> {actual.get('version')!r}")
    for symbol in sorted(set(exp) - set(act)):
        lines.append(f"  - removed: {symbol} ({exp[symbol]['tier']})")
    for symbol in sorted(set(act) - set(exp)):
        lines.append(f"  + added:   {symbol} ({act[symbol]['tier']})")
    for symbol in sorted(set(exp) & set(act)):
        if exp[symbol] != act[symbol]:
            lines.append(f"  ~ changed: {symbol}: {exp[symbol]} -> {act[symbol]}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute / freeze the public API surface.")
    parser.add_argument("--write", action="store_true", help="regenerate the snapshot")
    args = parser.parse_args(argv)

    actual = compute_surface(_top_module())

    if args.write:
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(_serialize(actual), encoding="utf-8")
        print(f"wrote {SNAPSHOT_PATH.relative_to(ROOT)} ({len(actual['surface'])} symbols)")
        return 0

    if not SNAPSHOT_PATH.exists():
        print(f"✗ no snapshot at {SNAPSHOT_PATH.relative_to(ROOT)}; run --write", file=sys.stderr)
        return 1
    expected = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    diff = _diff(expected, actual)
    if diff:
        print("✗ public API surface drifted from the committed snapshot:", file=sys.stderr)
        print("\n".join(diff), file=sys.stderr)
        print(
            "\nIf this change is intentional: re-run `python scripts/snapshot_api.py --write`, "
            "add a CHANGELOG entry, and keep the §5 deprecation policy (a removed `stable` "
            "symbol must be `deprecated` for ≥1 minor first; a new symbol carries a `Since`).",
            file=sys.stderr,
        )
        return 1
    print(f"✓ public API surface matches the snapshot ({len(actual['surface'])} symbols)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
