"""ADR-052 §15 surface freeze: the live public API matches the golden snapshot.

This recomputes the package's public surface (every ``__all__`` symbol + the
decorated members of each exported class, with tier + ``Since``) and diffs it
against ``tests/api/public_surface.snapshot.json``. A refactor that adds,
removes, renames, or re-tiers a public symbol fails this test — the surface
cannot drift by accident. An intentional change regenerates the snapshot
(``python scripts/snapshot_api.py --write``), which shows up as a reviewable
diff guarded by CODEOWNERS on ``tests/api/**``.

It loads the *same* ``scripts/snapshot_api.py`` the regenerate command and CI
use, so the test, the gate, and the snapshot cannot disagree.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType


def _load_snapshot_tool() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "snapshot_api.py"
    spec = importlib.util.spec_from_file_location("snapshot_api", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_public_surface_matches_snapshot() -> None:
    tool = _load_snapshot_tool()
    assert tool.SNAPSHOT_PATH.exists(), "run `python scripts/snapshot_api.py --write` to create the snapshot"
    expected = json.loads(tool.SNAPSHOT_PATH.read_text(encoding="utf-8"))
    actual = tool.compute_surface(tool._top_module())
    diff = tool._diff(expected, actual)
    assert not diff, (
        "public API surface drifted from tests/api/public_surface.snapshot.json:\n"
        + "\n".join(diff)
        + "\n\nIf intentional: run `python scripts/snapshot_api.py --write`, add a CHANGELOG "
        "entry, and follow the ADR-052 §5 deprecation policy."
    )
