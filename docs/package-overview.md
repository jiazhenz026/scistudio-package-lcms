# Package Overview — scistudio-package-lcms

> The structured catalog required by `docs/DOCUMENTATION-STANDARD.md`. Keep it
> in sync with the code: the blocks listed here must match `get_blocks()` and
> the `README.md` block table.

## Purpose

LCMS analysis blocks and types for SciStudio: working with feature tables from
untargeted and isotope-tracing liquid chromatography–mass spectrometry runs
(El-MAVEN peaks exports), through background handling and isotope correction
into the three core downstream analyses — consumption / release, untargeted
group comparison, and isotope tracing (MID + enrichment). The blocks are the
reusable, general steps of those analyses; experiment-specific orchestration and
plotting stay in the user's own workflow / plot cards.

## Scope and non-goals

- In scope: LCMS feature tables (wide: feature annotation + per-sample
  intensity) and the blocks that load, clean, and quantify them.
- Out of scope: raw spectra / chromatogram processing and peak *picking* (that
  is the upstream tool's job, e.g. El-MAVEN); no import of sibling domain
  packages.

## Data types

| Type | Core base | Represents | Key metadata |
| --- | --- | --- | --- |
| `LCMSFeatureTable` | `DataFrame` | A wide feature table: annotation columns + one intensity column per sample | `polarity`, `software`, `source_file`, `labeled`, `annotation_columns`, `sample_columns` |

## Developer-facing API (ADR-052 §13.1)

The reuse surface a consumer (or the embedded agent) imports — types, their
constructors, and inherited accessors — standardized so every package reads the
same shape. Each public symbol carries an ADR-052 §5 tier + `Since` on **this
package's** version line. Transcribe this table for your own types (ADR-052
§13.2: each package carries its own §13.1 table).

| Member | Kind | Tier | Since | Notes |
| --- | --- | --- | --- | --- |
| `LCMSFeatureTable` | type (subclasses `DataFrame`) | stable | 0.1.0 | public at `from scistudio_blocks_lcms import LCMSFeatureTable` — never a deep path |
| `LCMSFeatureTable(columns=…, row_count=…, schema=…, data=…, meta=…)` | constructor | stable | 0.1.0 | canonical construction; inherited core `DataFrame` idiom, signature not redefined |
| `LCMSFeatureTable.Meta` | pydantic model | stable | 0.1.0 | typed, frozen metadata: `polarity`, `software`, `labeled`, `annotation_columns`, `sample_columns` |
| `LCMSFeatureTable.from_elmaven(frame, *, polarity=None, sample_columns=None)` | classmethod | stable | 0.1.0 | domain-native packing constructor **on the type**: packs an El-MAVEN peaks frame |
| `LCMSFeatureTable.from_wide(frame, *, sample_columns, source=None, polarity=None, software=None, labeled=False, source_file=None)` | classmethod | stable | 0.1.0 | standard reconstruction from a derived wide frame + its sample columns; annotation inferred, header loss allowed; pass `source=<input table>` to carry provenance (`source_file`) + display name forward |
| `LCMSFeatureTable.to_memory` / `to_pandas` / `to_numpy` / `with_meta` | method | stable | core | inherited from core; **never** shadowed |
| `ELMAVEN_ANNOTATION_COLUMNS` | data | — | 0.1.0 | the fixed El-MAVEN annotation-column names, in export order |
| `describe_public_api()` | function | provisional | 0.1.0 | discovery hook (ADR-052 §4.4) (skeleton — implement) |
| `helpers` | module | — | — | SHOULD placeholder for optional public cross-type helpers |

## Blocks

| Group | Block | Inputs → Outputs | Parameters | Notes |
| --- | --- | --- | --- | --- |
| app | `ElMaven` | `Collection[Artifact]` (mzML/mzXML) → `LCMSFeatureTable` (`peaks`) | `app_command` (peakdetector path), `polarity`, `ppm`, `min_intensity`, `min_quality`, `min_good_group_count`, `min_signal_baseline_ratio`, m/z & RT range, `align_samples` | Runs El-MAVEN `peakdetector` over the raw files via the `prepare_launch` hook (one `<samples>` per file), then loads the peaks CSV into a standard table. Needs `peakdetector` on the host |
| io | `LoadPeakTable` | file(s) (`.csv` / `.tab` / `.tsv`) → `Collection[LCMSFeatureTable]` | `path` (one file or several), `polarity` (auto/positive/negative) | Loads one or several El-MAVEN peaks exports (one table per file, named after the file); `auto` infers polarity from each file name |
| io | `SavePeakTable` | `Collection[LCMSFeatureTable]` → file(s) | `path` (a `.csv` file, or a folder for several tables) | Writes feature table(s) to CSV: a single table to the file, or one CSV per table (named by `display_name`) into the folder |
| process (interactive) | `BackgroundSubtraction` | `Collection[LCMSFeatureTable]` → `Collection[LCMSFeatureTable]` | interactive panel (one tab per table); roles + sample→background matching, replicate aggregation | Opens a panel pre-filled by a name heuristic; subtracts each sample's aggregated background and drops background columns (negatives kept). Headless: applies the suggestion |
| process | `IsotopeCorrection` | `Collection[LCMSFeatureTable]` → 4 ports: `original`, `corrected`, `normalized`, `pool` (each `Collection[LCMSFeatureTable]`) | `corrector` (accucor/accucor2), `resolution`, `resolution_defined_at`, `c13_purity`, `h2n15_purity`, `label`, `charge`, `rscript_path` | Natural isotope abundance correction via embedded AccuCor/AccuCor2 R; emits all four corrector matrices; needs R + the corrector packages on the host |
| process (interactive) | `Normalization` | `Collection[LCMSFeatureTable]` → `Collection[LCMSFeatureTable]` | interactive panel; `method` (single_reference / isotope_internal_standard / total / median), `drop_reference` | Internal-standard normalization: divides each sample column by a reference. Single reference feature (e.g. HEPES), per-metabolite isotope internal standard (located via `isotopeLabel`), or total / median. Reference picked in the panel |
| process | `Log2MeanCenter` | `Collection[LCMSFeatureTable]` → `Collection[LCMSFeatureTable]` | `pseudocount_fraction` | Log2-transforms and per-feature mean-centers the sample columns (relative log2FC) for heatmaps / group comparison. Orthogonal to `Normalization` |
| process (interactive) | `GroupStatistics` | `Collection[LCMSFeatureTable]` → `Collection[DataFrame]` (`statistics`) | interactive panel (group assignment); `test` (ttest / anova / linear_trend), `fdr` (bh / bonferroni / none), `alpha` | Assigns samples to groups, then compares each feature (Welch t-test / one-way ANOVA / linear trend) with FDR. Emits group means + statistic + p-value + p_adj + significant |
| process (interactive) | `ConsumptionRelease` | `Collection[LCMSFeatureTable]` (+ optional `metadata` `DataFrame`) → `Collection[DataFrame]` (`rates`) | interactive panel (group + reference pick); `dt`, `sample_column`, `cell_number_column` | Per feature, each sample minus the reference-group mean (consumed −, released +). With per-sample cell numbers + Δt, returns a per-cell-per-time rate |
| process | `CalculateMID` | `Collection[LCMSFeatureTable]` → 2 ports: `mid`, `enrichment` (each `Collection[LCMSFeatureTable]`) | — | Normalizes a compound's isotopologues to a fractional MID (M+0/M+1/…); derives ¹³C enrichment (`Σ i·MID_i / (n−1)`) per compound per sample. MID keeps the isotopologue-row shape; enrichment collapses to one row per compound |
| process | `MetaboliteExport` | `table` (`LCMSFeatureTable` / `DataFrame`) + `id_map` (`DataFrame`) → `DataFrame` (`exported`) | `compound_column`, `map_name_column`, `map_id_column`, `output_id_column`, `require_id` | Joins a user-supplied `compound→ID` map (e.g. HMDB) onto a table for external enrichment tools (MetaboAnalyst / Metaboverse); drops unmapped compounds by default. Enrichment itself is left to the external tool |
| example | `ExampleBlock` | `Collection[LCMSFeatureTable]` → `Collection[LCMSFeatureTable]` | — | Placeholder passthrough; replaced as the real LCMS blocks land |

## IO / format support (ADR-043)

- `LoadPeakTable` registers a **load** `FormatCapability` for `LCMSFeatureTable`
  over `.csv` / `.tab` / `.tsv` (format id `el_maven_peaks`), reading an
  El-MAVEN peaks export. No saver yet.

## Previewers (ADR-048)

No previewers.

## Compatibility

- Requires `scistudio>=0.3.2a0` — `ElMaven` relies on the core
  `AppBlock.prepare_launch` hook (ADR-052 §7), first shipped on the 0.3.2 line;
  the 0.3.1 line's `scistudio.stability` (ADR-052 §5) is also used everywhere.
- Python `>=3.11`.
- **`IsotopeCorrection` runtime dependency:** the host must have `R` (`Rscript`
  on `PATH`, or set per-node via `rscript_path`) and the corrector packages
  installed — `accucor` (`devtools::install_github("XiaoyangSu/AccuCor")`) for
  single-isotope, plus `accucor2` / `dplyr` / `tidyr` / `stringr` / `openxlsx`
  for dual-isotope. The block fails with a clear message when they are absent.

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
