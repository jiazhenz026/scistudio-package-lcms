# scistudio-package-lcms

LC-MS metabolomics and isotope-tracing blocks for
[SciStudio](https://github.com/jiazhenz026/SciStudio). This package covers the
**upstream** of an LC-MS workflow: get a peak table into SciStudio, define and
subtract background, and run natural-abundance isotope correction.

Conventions follow `scistudio-blocks-spectroscopy`, the reference package.

## Scope / non-goals

- **In scope (this release):** ingesting a peak-picker export, El-MAVEN
  integration, background selection + subtraction, and natural-abundance
  isotope correction (AccuCor / AccuCor2).
- **Out of scope:** raw-data processing (peak picking itself is done in the
  external tool), and all downstream analysis (normalization, drift correction,
  statistics, quantification, pathway enrichment) — those come later.
- Must not import sibling block packages (imaging, spectroscopy, srs); it
  depends only on `scistudio` core.

## Data types

| Type | Core base | Represents | Key metadata |
| --- | --- | --- | --- |
| `LCMSFeatures` | `DataFrame` | A peak/feature table exactly as a peak picker exported it (one row per feature or isotopologue, one column per sample) | `polarity`, `source_tool`, `source_file`, `labeled` |

`LCMSFeatures` keeps the exported columns verbatim — it does not impose a fixed
schema — so the same type serves both untargeted and isotope-tracing tables.

## Blocks

| Group | Block | Inputs → Outputs |
| --- | --- | --- |
| io | `LoadPeakTable` | file path → `LCMSFeatures` |
| interactive | `ElMaven` | `mzml: Artifact` → `peaks: LCMSFeatures` |
| preprocessing | `BackgroundSelector` | `features` → `samples` + `background` (1:1) |
| preprocessing | `BackgroundSubtraction` | `samples` + `background` → `result` |
| preprocessing | `IsotopeCorrection` | `features` → `corrected` + `mid` + `pool_size` |

A typical upstream graph: `ElMaven` (or `LoadPeakTable`) →
`BackgroundSelector` → `BackgroundSubtraction` → `IsotopeCorrection`.

## IO / format support

`LoadPeakTable` reads El-MAVEN / generic CSV-or-TSV exports verbatim (no
`FormatCapability` registration yet — it is a direct loader). `ElMaven` opens
mzML inputs in the external El-MAVEN app and parses the export back into
`LCMSFeatures`.

## Previewers

No previewers in this release.

## External requirements

- **`IsotopeCorrection`** wraps the published R packages and therefore needs
  **R** with `accucor` and `accucor2` installed. SciStudio core has no
  system-dependency mechanism, so this is checked at runtime and reported with a
  clear error when missing. Install once:

  ```r
  install.packages("devtools")
  devtools::install_github("XiaoyangSu/AccuCor")
  devtools::install_github("wangyujue23/AccuCor2")
  ```

- **`ElMaven`** needs the El-MAVEN desktop application installed; set its path
  via the block's `app_command` config when it is not on `PATH`.

## Install

```bash
# Core (private; installed from the repo until it is on PyPI)
pip install "scistudio @ git+https://github.com/jiazhenz026/SciStudio.git@main"
# This package, with dev tools
pip install -e ".[dev]"
scistudio blocks    # the LCMS blocks should appear
```

Compatibility floor: `scistudio>=0.2.1a0`, Python `>=3.11`.

## License

MIT.
