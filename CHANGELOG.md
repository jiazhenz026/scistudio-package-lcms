# Changelog

All notable changes to this package are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

- Multi-file IO + table naming:
  - `LoadPeakTable` now loads **one or several** files (a `path` list) into a
    `Collection[LCMSFeatureTable]` — one table per file — and records each file
    on `LCMSFeatureTable.Meta.source_file` plus the file stem as the table's
    display name.
  - `SavePeakTable` (new) writes feature table(s) to CSV: a single table to a
    `.csv` path, or one CSV per table (named by `display_name`, de-duplicated)
    into a folder when given a collection. (Note: a single saver call still
    writes one file each; multi-file means one file per collection item.)
  - `LCMSFeatureTable.Meta` gains `source_file`, and
    `LCMSFeatureTable.from_wide(…, source=<input table>)` carries the source's
    provenance (`source_file`) and user-facing name to the derived table — so
    core's display-name resolver (#1812) names the whole pipeline from the
    origin file with no per-block stamping. Blocks that emit a *specifically
    named* product (the corrector matrices, MID / enrichment, statistics,
    consumption/release) compose `"<source file> · <product>"` (e.g.
    `scan1_negative · Corrected`) so several inputs' products stay distinct.
- `IsotopeCorrection` fix — El-MAVEN ≥ 0.4 can report one compound as several
  peak groups (same `compound`, different `metaGroupId`), which AccuCor /
  AccuCor2 reject ("Multiple peak groups detected … use metaGroupId column").
  The embedded R now folds the peak-group id into the compound name where a
  compound spans more than one group (e.g. `Glucose` → `Glucose [g1]`,
  `Glucose [g2]`), so each group is corrected independently. Validated against
  real AccuCor; a regression test runs when R + accucor are present.
  Each of the four output tables is now named after its corrector matrix
  (`display_name` / `sheet_name` = "Original" / "Corrected" / "Normalized" /
  "Pool size") so the previewer shows the matrix's identity instead of an
  unnamed table (#1812).
- Distribution renamed `scistudio-package-lcms` → `scistudio-blocks-lcms` and the
  import module `scistudio_package_lcms` → `scistudio_blocks_lcms`, so the
  desktop Package Manager installs it (it discovers `scistudio_blocks_*` modules)
  and the palette groups it as a plugin package rather than under SciStudio Core.
- Downstream-analysis blocks (#10) — the reusable, general steps of the three
  core LCMS analyses (consumption/release, untargeted, isotope tracing),
  abstracted out of the lab-specific flux pipeline. Data type is unchanged
  (`LCMSFeatureTable`); result tables are the core `DataFrame`; visualization is
  left to the user's plot card and pathway enrichment to external tools:
  - `Normalization` — interactive internal-standard normalization: divides each
    sample column by a reference. Modes: a single reference feature (e.g.
    HEPES), a per-metabolite isotope internal standard (located via
    `isotopeLabel`, e.g. glucose ÷ ¹³C-glucose), or total / median. The
    reference / internal-standard pairing is picked in a panel; reference rows
    are dropped after use. Ships `panels/normalization.js`.
  - `Log2MeanCenter` — a small standalone transform: `log2` + per-feature
    mean-centering (relative log2FC), the untargeted heatmap/stats input.
    Orthogonal to `Normalization` (across samples vs within a sample).
  - `GroupStatistics` — interactive group assignment, then a per-feature Welch
    t-test / one-way ANOVA / linear trend with Benjamini-Hochberg (or
    Bonferroni) correction; emits a tidy statistics `DataFrame` (group means,
    statistic, p-value, p_adj, significant). Ships `panels/group_statistics.js`.
    Adds a `scipy>=1.10` dependency (BH is implemented locally).
  - `ConsumptionRelease` — interactive reference-group pick; per feature, each
    sample minus the reference-group mean (consumed −, released +). An optional
    `metadata` input of per-sample cell numbers plus a Δt config turns the
    difference into a per-cell-per-time rate. Ships
    `panels/consumption_release.js`.
  - `CalculateMID` — the mass isotopologue distribution (M+0/M+1/… fractions per
    compound per sample) and the derived ¹³C enrichment (`Σ i·MID_i / (n−1)`).
    Two ports — `mid` (isotopologue-row fractions) and `enrichment` (one row per
    compound) — since the two have different granularity.
  - `MetaboliteExport` — joins a user-supplied `compound→ID` map (e.g. HMDB)
    onto a statistics or feature table for external enrichment tools
    (MetaboAnalyst / Metaboverse), dropping unmapped compounds by default.
- `ElMaven` — an `AppBlock` that runs El-MAVEN's headless `peakdetector` over raw
  `.mzML` / `.mzXML` files and outputs a standard `LCMSFeatureTable`. It uses the
  core `AppBlock` `prepare_launch` hook (ADR-052 §7, core 0.3.2) to generate the
  peakdetector XML config — one `<samples>` entry per input file, so the whole
  input collection is injected — and reconstructs the resulting peaks CSV into a
  feature table (reusing `LoadPeakTable`). Exposes the executable path
  (`app_command`) plus the key detection parameters (polarity, ppm, intensity,
  quality, mass/RT range, alignment). Needs `peakdetector` on the host.
- `BackgroundSubtraction` — an interactive block (ADR-051) that opens a panel
  (one tab per input table) to assign each sample column a role and a
  background, then subtracts each sample's aggregated (mean/median) background
  and drops the background columns. The panel is pre-filled by a name-based
  heuristic that classifies messy column names (blank/bg/background, qc,
  wash/ignore, the replicate-0 convention) and matches samples to their group's
  background; run headless it applies that suggestion. Negatives are not clamped
  (matches the reference pipeline). Ships a dependency-free ES-module panel
  (`panels/background_subtraction.js`, served per ADR-051) with tabs per table,
  per-column role/background editing, wildcard bulk rules, and a live summary.
- `LCMSFeatureTable.from_wide(frame, *, sample_columns, …)` — the standard
  reconstruction of a feature table from a derived wide frame plus its sample
  columns (annotation inferred). Used by blocks that produce a derived table
  (corrected, normalized, background-subtracted); upstream annotation a step
  drops is allowed to be absent.
- `IsotopeCorrection` — a natural-isotope-abundance correction block that ships
  an embedded R script (`_r/isotope_correction.R`) and runs it with `Rscript`.
  `corrector="accucor"` runs AccuCor (single-isotope); `corrector="accucor2"`
  runs AccuCor2 (dual-isotope, e.g. ¹³C+²H), following the reference flux
  pipeline. Emits all four corrector matrices on four output ports —
  `original`, `corrected`, `normalized`, `pool`. Exposes `resolution`,
  `resolution_defined_at`, `c13_purity`, `h2n15_purity`, `label`, `charge`, and
  `rscript_path`. The feature table crosses the Python↔R boundary as CSV.
  Requires R + the corrector packages on the host.
- `LoadPeakTable` — an IO loader block (`SimpleLoader`) that reads an El-MAVEN
  peaks export (`.csv` / `.tab` / `.tsv`) into an `LCMSFeatureTable` via
  `from_elmaven`. Exposes a `polarity` config (auto/positive/negative); `auto`
  infers polarity from the file name. Registers a load `FormatCapability` for
  `LCMSFeatureTable`.
- `LCMSFeatureTable` — the package's primary data type: a wide LCMS feature
  table (subclasses core `DataFrame`) of per-feature annotation columns plus one
  intensity column per sample. Its MUST-shape domain constructor
  `from_elmaven(frame, *, polarity=None, sample_columns=None)` packs an El-MAVEN
  peaks export, recording the annotation/sample split, polarity, source
  software, and isotope-label flag on `LCMSFeatureTable.Meta`.
- ADR-052 §13 developer-facing contract, self-enforcing (#1826): the package
  scaffolds the public reuse surface as MUST skeletons that raise
  `NotImplementedError` (the type's `from_<domain>` constructor and the
  `describe_public_api` discovery hook) plus a SHOULD `helpers.py` placeholder,
  so a copied package
  fails loudly until its contract is filled in. Every public symbol carries an
  ADR-052 §5 stability marker (`@stable` / `@provisional`) with a `Since`
  against this package's version line, and `scripts/validate_contract.py` now
  checks the §13.1 reuse surface (public type, no `to_pandas`/`to_numpy`
  shadowing, no underscore-named author-facing helpers, decorator coverage).
- Anti-drift freeze + generated reference (#1826, ADR-052 §7/§15): a committed
  golden snapshot of the public surface
  (`tests/api/public_surface.snapshot.json`) produced by
  `scripts/snapshot_api.py`, plus a freeze test that fails CI on any accidental
  add/remove/re-tier of a public symbol. `.github/CODEOWNERS` makes
  `tests/api/**` owner-reviewed. A minimal mkdocs + mkdocstrings/griffe build
  (`mkdocs.yml`, `.[docs]`) renders the developer-facing reference from
  docstrings + the stability decorators.
- Core floor raised to `scistudio>=0.3.2a0`: `ElMaven` relies on the core
  `AppBlock.prepare_launch` hook (ADR-052 §7), first shipped on the 0.3.2 line
  (the package also uses `scistudio.stability` from 0.3.1).
  `[tool.scistudio.ota].min_core_base` bumped to `0.3.2` to match.
- OTA hot-update support (#1784): the package self-declares its update source
  via `PackageInfo.ota` (mirrored in `[tool.scistudio.ota]`), and
  `scripts/ota_publish.py` publishes `manifest.json` + a source snapshot to the
  package's own public `ota-<channel>` GitHub pre-release. The in-app SciStudio
  Package Manager checks this source and offers updates.

## [0.1.0]

- Initial package scaffolded from `scistudio-package-template`: the
  self-enforcing ADR-052 §13 contract surface, a placeholder passthrough block
  (`ExampleBlock`), and an empty previewers stub, ready for the LCMS types and
  blocks to be filled in.
