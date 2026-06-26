# Changelog

All notable changes to this package are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0]

Initial LCMS upstream blocks (replaces the template scaffold).

- New type `LCMSFeatures` (subclasses core `DataFrame`): an LC-MS peak/feature
  table kept verbatim, with `polarity` / `source_tool` / `source_file` /
  `labeled` provenance metadata.
- New blocks:
  - `LoadPeakTable` — load an El-MAVEN / generic CSV·TSV peak table.
  - `ElMaven` — open mzML inputs in the external El-MAVEN app and parse the
    exported peak table into `LCMSFeatures`.
  - `BackgroundSelector` — split a table into matched `samples` + 1:1
    `background` tables (config-panel column picker).
  - `BackgroundSubtraction` — element-wise background subtraction.
  - `IsotopeCorrection` — natural-abundance correction via the R `accucor`
    (single) / `accucor2` (dual) packages; emits corrected intensities, the
    normalized isotopologue distribution (MID), and per-compound pool size.
- `IsotopeCorrection` adds a runtime requirement on R + `accucor` / `accucor2`
  (no bundled Python re-implementation, by design). Added `pandas` / `pyarrow`
  to the dependency floor for the table plumbing.
