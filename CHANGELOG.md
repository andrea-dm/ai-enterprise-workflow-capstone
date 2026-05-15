# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] — Slice 2: pyright strict-mode compliance

### Changed

- `pyrightconfig.json` upgraded to `"typeCheckingMode": "strict"`; removes
  `[tool.pyright]` from `pyproject.toml`.
- All public functions in `core/logging.py`, `ingestion/pipeline.py`,
  `forecasting/arima.py`, `monitoring/drift.py`, and `service/api.py`
  annotated with full parameter and return-type signatures.
- `ingestion/pipeline.py`: two anonymous `apply(lambda …)` calls replaced by
  the typed private helper `_to_digits(value: object) -> str`.
- `service/api.py` route functions return `flask.typing.ResponseReturnValue`.
- `tests/app_test.py` mock parameters typed as `MagicMock`; all test methods
  annotated `-> None`.
- `statsmodels` imports suppressed with `# type: ignore[import-untyped]`
  (no stubs available upstream); `scipy` resolved via `scipy-stubs`.
- `pandas-stubs` and `scipy-stubs` moved to the `lint` dependency group so
  CI's `--group lint` environment satisfies strict `reportMissingImports`.
- CI workflow `dependency-architecture-checks.yml` updated from
  `--only-group lint` to `--no-install-project --group lint` to include
  project runtime deps needed by pyright strict mode.

### Added

- `tests/fixtures/data/output/4 revenue_total.csv` — 183-row synthetic daily
  revenue fixture (2018-06-01 → 2018-11-30) enabling `ModelTest` to run
  without live data.
- `tests/fixtures/data/output/3 revenue_country.csv` — per-country revenue
  fixture seeded from the total fixture.
- `ModelTest::test_01_model_train` and `ModelTest::test_02_model_predict` now
  run in CI without skip guards.

## [Unreleased] — Slice 1: package restructure

### Added

- New src-layout package `ai_enterprise_workflow` (`core`, `ingestion`,
  `forecasting`, `monitoring`, `service` subpackages, plus `cli.py`
  placeholder for Slice 6).
- Hatchling wheel target wired via `[tool.hatch.build.targets.wheel]
  packages = ["src/ai_enterprise_workflow"]`.
- Re-exports: `from ai_enterprise_workflow.service import app`,
  `from ai_enterprise_workflow.ingestion import ingest`,
  `from ai_enterprise_workflow.forecasting import model`.

### Changed

- Project distribution name `carbon-pledges` → `ai-enterprise-workflow`;
  version reset to `0.1.0`.
- All internal imports rewritten from `src.*` to absolute
  `ai_enterprise_workflow.*` paths; every `from … import *` removed.
- Tooling configs (`pyproject.toml`, `tach.toml`, `pyrightconfig.json`,
  `sonar-project.properties`, `mkdocs.yml`) retargeted at the new package.
- Runtime + dev dependencies rationalized to capstone's actual stack
  (`flask`, `pandas`, `numpy`, `scipy`, `statsmodels`, `tqdm`, `matplotlib`).

### Notes

- Notebooks under `nb/` required no edits (verified zero `from src` refs).
- `monitoring/drift.py` retained verbatim; runtime wiring deferred to a later slice.
## [5.0.1] — 2026-03-29

### Fixed

- Moved `recursion_limit` from `StateGraph.compile()` to `invoke()` config
  to fix `TypeError` on LangGraph ≥ 1.0.
- Extracted adversarial model loading into dedicated
  `AuditorResources._load_adversarial_model()` method.
