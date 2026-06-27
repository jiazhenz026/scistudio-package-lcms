# Changelog

All notable changes to this package are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- Raised the core dependency floor from `scistudio>=0.2.1a0` to
  `scistudio>=0.3.0a0`. Core 0.3.0 formalizes the ADR-051 Addendum 1
  interaction-memory contract (the inheritable `InteractiveMixin` surface +
  `execution_mode = interactive` schema-driven UI) that the upcoming LCMS
  interactive blocks will inherit. CI already resolves core from
  `SCISTUDIO_CORE_REF=main`, so this only updates the declared floor.
  (#5)

## [0.1.0]

- Initial example package generated from `scistudio-package-lcms`:
  one example type (`ExampleSeries`), one passthrough block (`ExampleBlock`),
  and an empty previewers stub.
