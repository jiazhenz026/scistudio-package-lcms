# Changelog

All notable changes to this package are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

- ADR-052 §13 developer-facing contract, self-enforcing (#1826): the template
  now scaffolds the public reuse surface as MUST skeletons that raise
  `NotImplementedError` (`ExampleSeries.from_arrays`, the `describe_public_api`
  discovery hook) plus a SHOULD `helpers.py` placeholder, so a copied package
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
- Core floor raised to `scistudio>=0.3.1a0` (#1826): the package imports
  `scistudio.stability` (ADR-052 §5), first shipped on the core 0.3.1 line.
  `[tool.scistudio.ota].min_core_base` bumped to `0.3.1` to match.
- OTA hot-update support (#1784): the package self-declares its update source
  via `PackageInfo.ota` (mirrored in `[tool.scistudio.ota]`), and
  `scripts/ota_publish.py` publishes `manifest.json` + a source snapshot to the
  package's own public `ota-<channel>` GitHub pre-release. The in-app SciStudio
  Package Manager checks this source and offers updates.

## [0.1.0]

- Initial example package generated from `scistudio-package-template`:
  one example type (`ExampleSeries`), one passthrough block (`ExampleBlock`),
  and an empty previewers stub.
