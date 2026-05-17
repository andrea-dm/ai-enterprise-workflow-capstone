# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.2.2] — 2026-05-17

### Changed

- `notebooks/results.ipynb`: add a lag-30 seasonal naive baseline to
  the predictions-vs-actuals comparison plot.

### Fixed

- `ai_enterprise_workflow.__version__`: align the package version marker
  with the release metadata.

## [0.2.1] — 2026-05-16

### Fixed

- `ingestion/pipeline.py` `clean_data`: replaced `fillna(value=-1, inplace=True)`
  with `pd.option_context("future.no_silent_downcasting", True)` +
  `fillna(value=-1).infer_objects(copy=False)` to eliminate the pandas
  `FutureWarning` on object-dtype downcasting.

### Changed

- `README.md` rewritten to reflect current package surface: `uv sync` install
  step, four CLI subcommands (`ingest`, `train`, `predict`, `serve`), corrected
  API port and response shape (includes `drift_warning`), full endpoint table
  (`/predict`, `/logs`, `/healthz`, `/readyz`), Docker `localhost:3000` note.

## [0.2.0] — 2026-05-16

### Added

- New src-layout package `ai_enterprise_workflow` (`core`, `ingestion`,
  `forecasting`, `monitoring`, `service` subpackages) with Hatchling wheel
  target; re-exports `app`, `ingest`, and `model` from sub-package roots.
- `notebooks/analysis.ipynb` and `notebooks/results.ipynb` rewired to call
  public API (`ingest()`, `model()`); directory renamed from `nb/` to
  `notebooks/`.
- **Slice A:** `AppSettings(BaseSettings)` typed configuration with
  env-override support via `pydantic-settings`; all directory/URL fields typed
  as `Path`/`str`; `drift_threshold: float = 0.1` added.
- **Slice B:** Structured JSONL logging via `core/log_events.py` replacing
  the CSV-based `core/logging.py`; `get_logger`, `setup_logging`,
  `log_ingest`, `log_train`, `log_predict` helpers.
- **Slice C:** Docker and Flask production hardening — non-root user,
  Gunicorn entrypoint, JSON error responses (400/422), `/readyz` health
  endpoint.
- **Slice D:** CLI fully wired via `argparse` (`ingest`, `train`, `predict`,
  `serve` subcommands); `[project.scripts]` entrypoint registered;
  `create_app` factory for test isolation.
- **Slice E:** `forecasting/arima.py` refactored — `train_ARIMA_model` and
  `train_SARIMA_model` renamed to snake_case; `model()` decomposed into
  `_load_or_train`, `_resolve_revenue`, `_run_predictions`; `# noqa: PLR0912`
  suppression removed.
- **Slice F:** Monitoring wired into forecasting — `get_wasserstein_distance`
  typo fixed; `forecasting → monitoring` tach dependency added; `model()`
  now returns `{"arima": float, "sarima": float, "drift": float}`;
  `/predict` response adds `drift_warning: bool`.
- **Slice G:** Test coverage expanded — `tests/ingestion/` (9 tests),
  `tests/monitoring/` (3 tests), `tests/cli/` (5 tests), shared
  `flask_client` fixture migrated to `tests/conftest.py`.
- **Slice H:** `py.typed` PEP 561 marker; `mkdocstrings` autodoc enabled
  (`members`, examples, signatures); `docs/api_reference.md` updated with
  `ai_enterprise_workflow.cli` directive (7 modules total).
- `tests/fixtures/data/output/4 revenue_total.csv` — 183-row synthetic daily
  revenue fixture (2018-06-01 → 2018-11-30) enabling `ModelTest` to run
  without live data.
- `tests/fixtures/data/output/3 revenue_country.csv` — per-country revenue
  fixture seeded from the total fixture.
- `ModelTest::test_01_model_train` and `ModelTest::test_02_model_predict` now
  run in CI without skip guards.

### Changed

- All internal imports rewritten from `src.*` to absolute
  `ai_enterprise_workflow.*` paths; every `from … import *` removed.
- Tooling configs (`pyproject.toml`, `tach.toml`, `pyrightconfig.json`,
  `sonar-project.properties`, `mkdocs.yml`) retargeted at the new package.
- Runtime + dev dependencies rationalized to capstone's actual stack
  (`flask`, `pandas`, `numpy`, `scipy`, `statsmodels`, `tqdm`, `matplotlib`).
- `pyrightconfig.json` upgraded to `"typeCheckingMode": "strict"`; removes
  `[tool.pyright]` from `pyproject.toml`.
- All public functions in `core/logging.py`, `ingestion/pipeline.py`,
  `forecasting/arima.py`, `monitoring/drift.py`, and `service/api.py`
  annotated with full parameter and return-type signatures.
- `ingestion/pipeline.py`: two anonymous `apply(lambda …)` calls replaced
  by the typed private helper `_to_digits(value: object) -> str`.
- `service/api.py` route functions return
  `flask.typing.ResponseReturnValue`.
- `tests/app_test.py` mock parameters typed as `MagicMock`; all test
  methods annotated `-> None`.
- `statsmodels` imports suppressed with `# type: ignore[import-untyped]`
  (no stubs available upstream); `scipy` resolved via `scipy-stubs`.
- `pandas-stubs` and `scipy-stubs` moved to the `lint` dependency group so
  CI's `--group lint` environment satisfies strict `reportMissingImports`.
- CI workflow `dependency-architecture-checks.yml` updated from
  `--only-group lint` to `--no-install-project --group lint` to include
  project runtime deps needed by pyright strict mode.
