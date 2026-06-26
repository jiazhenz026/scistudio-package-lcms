# Package Overview — scistudio-package-lcms

The structured catalog required by `docs/DOCUMENTATION-STANDARD.md`. Kept in
sync with `get_blocks()` and the `README.md` block table.

## Purpose

LC-MS metabolomics and isotope-tracing **upstream** blocks: bring a peak-picker
export into SciStudio, define and subtract background, and run natural-abundance
isotope correction.

## Scope and non-goals

- In scope: peak-table ingestion, El-MAVEN integration, background
  selection/subtraction, natural-abundance isotope correction.
- Out of scope: raw-data peak picking (done in the external tool) and all
  downstream analysis (normalization, drift correction, statistics,
  quantification, KEGG enrichment). Must not import sibling block packages.

## Data types

| Type | Core base | Represents | Key metadata |
| --- | --- | --- | --- |
| `LCMSFeatures` | `DataFrame` | A peak/feature table verbatim from a peak picker (one row per feature/isotopologue, one column per sample) | `polarity`, `source_tool`, `source_file`, `labeled` |

## Blocks

| Group | Block | Inputs → Outputs | Parameters | Notes |
| --- | --- | --- | --- | --- |
| io | `LoadPeakTable` | path → `features: LCMSFeatures` | `path`, `source_tool`, `polarity`, `delimiter` | Reads El-MAVEN / generic CSV·TSV verbatim |
| interactive | `ElMaven` | `mzml: Collection[Artifact]` → `peaks: Collection[LCMSFeatures]` | `polarity`, `app_command` (core) | Opens mzML in El-MAVEN; parses the export |
| preprocessing | `BackgroundSelector` | `features: LCMSFeatures` → `samples: LCMSFeatures`, `background: LCMSFeatures` | `id_columns`, `background_patterns`, `sample_patterns`, `aggregation` | Splits one table into matched samples + 1:1 background |
| preprocessing | `BackgroundSubtraction` | `samples`, `background` → `result: LCMSFeatures` | `clip_negative` | Element-wise subtraction of a 1:1 background |
| preprocessing | `IsotopeCorrection` | `features: LCMSFeatures` → `corrected`, `mid`, `pool_size` (`LCMSFeatures`) | `mode` (single/dual), `tracer`, `resolution`, `resolution_defined_at`, `c13_purity`, `h2n15_purity` | Wraps R AccuCor / AccuCor2 |

## IO / format support (ADR-043)

`LoadPeakTable` is a direct `IOBlock` loader (reads CSV/TSV verbatim); it does
not yet register `FormatCapability` records. `ElMaven` collects the external
export files and parses them with the same reader.

## Previewers (ADR-048)

No previewers.

## External requirements

- `IsotopeCorrection` needs R with `accucor` + `accucor2` installed (checked at
  runtime). Single mode → `accucor::natural_abundance_correction`; dual mode →
  `accucor2::dual_correction`. The bundled, non-editable wrapper lives at
  `src/scistudio_package_lcms/r/accucor_run.R`.
- `ElMaven` needs the El-MAVEN desktop app.

## Compatibility

- Requires `scistudio>=0.2.1a0`.
- Python `>=3.11`.
