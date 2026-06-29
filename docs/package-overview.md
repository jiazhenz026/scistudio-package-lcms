# Package Overview — <package name>

> Fill this in for your package. This is the structured catalog required by
> `docs/DOCUMENTATION-STANDARD.md`. Keep it in sync with the code: the blocks
> listed here must match `get_blocks()` and the `README.md` block table.

## Purpose

<One paragraph: what scientific domain / task this package serves.>

## Scope and non-goals

- In scope: <...>
- Out of scope: <...> (and any sibling package this must not import)

## Data types

| Type | Core base | Represents | Key metadata |
| --- | --- | --- | --- |
| `ExampleSeries` | `Series` | A 1-D series of values | `unit`, `source_file` |

## Developer-facing API (ADR-052 §13.1)

The reuse surface a consumer (or the embedded agent) imports — types, their
constructors, and inherited accessors — standardized so every package reads the
same shape. Each public symbol carries an ADR-052 §5 tier + `Since` on **this
package's** version line. Transcribe this table for your own types (ADR-052
§13.2: each package carries its own §13.1 table).

| Member | Kind | Tier | Since | Notes |
| --- | --- | --- | --- | --- |
| `ExampleSeries` | type (subclasses `Series`) | stable | 0.1.0 | public at `from scistudio_package_lcms import ExampleSeries` — never a deep path |
| `ExampleSeries(data=…, meta=…)` | constructor | stable | 0.1.0 | canonical construction; inherited core idiom, signature not redefined |
| `ExampleSeries.Meta` | pydantic model | stable | 0.1.0 | typed, frozen metadata schema |
| `ExampleSeries.from_arrays(index, values, *, meta=None)` | classmethod | stable | 0.1.0 | domain-native packing constructor **on the type** (skeleton — implement) |
| `ExampleSeries.to_memory` / `to_pandas` / `to_numpy` / `sel` / `with_meta` | method | stable | core | inherited from core; **never** shadowed |
| `describe_public_api()` | function | provisional | 0.1.0 | discovery hook (ADR-052 §4.4) (skeleton — implement) |
| `helpers` | module | — | — | SHOULD placeholder for optional public cross-type helpers |

## Blocks

| Group | Block | Inputs → Outputs | Parameters | Notes |
| --- | --- | --- | --- | --- |
| example | `ExampleBlock` | `Collection[ExampleSeries]` → `Collection[ExampleSeries]` | — | Passthrough; replace with real logic |

## IO / format support (ADR-043)

<Only if the package has IO blocks. List advertised vs. deferred formats and
their `FormatCapability` records. Otherwise: "No IO blocks.">

## Previewers (ADR-048)

<Only if the package ships previewers. List each previewer, the type it
targets, and its capabilities. Otherwise: "No previewers.">

## Compatibility

- Requires `scistudio>=0.3.1a0` — the core 0.3.1 line ships
  `scistudio.stability` (ADR-052 §5), which every public symbol uses.
- Python `>=3.11`.

## OTA hot-update (#1784)

This package supports SciStudio's in-app Package Manager hot-update. The update
source is declared once in `[tool.scistudio.ota]` (publish-time source of truth)
and mirrored in `PackageInfo.ota`; `scripts/validate_contract.py` enforces they
match.

To publish a new version:

1. Bump `[project].version` in `pyproject.toml` (and `__version__`).
2. Run `python scripts/ota_publish.py --notes "<what changed>"` (needs `gh`
   authenticated with write access). Use `--dry-run` to build locally first.

This packs `src/` into a snapshot, hashes it, writes `manifest.json`, and
uploads both to the package's own public `ota-<channel>` rolling pre-release —
the exact URL declared in `[tool.scistudio.ota].manifest_url`. Clients running
core `>= min_core_base` then see the update in the Package Manager.
