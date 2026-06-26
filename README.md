# scistudio-package-lcms

A GitHub **template repository** for building a new
[SciStudio](https://github.com/jiazhenz026/SciStudio) package. It ships a
minimal but complete example package plus the governance every package
should have: CI (lint, type, test, wheel build, contract check), an
`AGENTS.md` + PR checklist, and a documentation standard.

The conventions follow `scistudio-blocks-spectroscopy`, the reference package.

## Use this template

1. On GitHub, click **Use this template → Create a new repository**. Name it
   `scistudio-blocks-<domain>`.
2. Add the repository secret **`SCISTUDIO_CORE_TOKEN`** (Settings → Secrets and
   variables → Actions). It needs read access to the private `scistudio` core
   repo so CI can install it. Until core is on PyPI, every block repo needs
   this secret.
3. Rename the package to your domain:
   - `src/scistudio_package_lcms/` → `src/scistudio_blocks_<domain>/`
   - In `pyproject.toml`: `[project].name`, the three `[project.entry-points...]`
     references, `[tool.hatch.build.targets.wheel].packages`, and
     `known-first-party`.
   - Update `__init__.py` imports and `PackageInfo`.
4. Replace the example type/block/previewer with your own.
5. Fill in `README.md`, `docs/package-overview.md`, and `CHANGELOG.md` to
   `docs/DOCUMENTATION-STANDARD.md`.

## What's inside

```
.
├── AGENTS.md                       # contributor + AI-agent rules (lightweight)
├── CONTRIBUTING.md                 # dev setup, local checks, release
├── LICENSE                         # MIT
├── pyproject.toml                  # hatchling + ruff/mypy/pytest + entry points
├── .github/
│   ├── workflows/ci.yml            # lint · type · test · contract · wheel
│   └── pull_request_template.md    # the gate is this checklist
├── docs/
│   ├── DOCUMENTATION-STANDARD.md   # what every package's docs must contain
│   └── package-overview.md         # fill-in catalog template
├── scripts/validate_contract.py    # entry-point + registry contract check
├── src/scistudio_package_lcms/   # minimal example: 1 type, 1 block, previewers stub
└── tests/                          # packaging · contract · block tests
```

## Governance in one breath

- No gate ledger, no multi-step workflow. The gate is the PR checklist
  (`.github/pull_request_template.md`) enforced by CI.
- Every PR closes an issue, adds/updates tests for behavior changes, and keeps
  docs to the standard.
- `python scripts/validate_contract.py` + `scistudio blocks` prove the package
  still installs into core. CI runs both.

## Develop the example locally

```bash
pip install "scistudio @ git+https://github.com/jiazhenz026/SciStudio.git@main"
pip install -e ".[dev]"
pytest
scistudio blocks   # the example block should appear
```
