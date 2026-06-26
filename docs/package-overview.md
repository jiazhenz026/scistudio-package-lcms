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

- Requires `scistudio>=<floor>`.
- Python `>=3.11`.
