---
manifest_version: 1
branch: 7-upgrade-core-foundation-typed-config-stdlib-logging-security
issue: 7
scope: "core config, log_events, ingestion, forecasting, service"
lock: null
mr: null
mr_url: https://github.com/andrea-dm/ai-enterprise-workflow-capstone/pull/new/7-upgrade-core-foundation-typed-config-stdlib-logging-security
status: in-review
---

# upgrade core foundation: typed config, stdlib logging, and security hardening

## Current state

The package currently uses:

- `core/config.py`: 9 module-level string/float constants; no env-var overrides; no `pathlib.Path`; no validation
- `core/logging.py`: custom CSV file writer that shadows stdlib `logging`; no log levels; no structured output
- `forecasting/arima.py`: `pickle.load()` for model deserialization (OWASP A08); `os.path` string concatenation
- `service/api.py`: plain-text error returns with implicit HTTP 200; no JSON error body
- All path operations use `os.path` string concatenation throughout

## Specification

Replace the above with:

- Pydantic v2 `AppSettings` (pydantic-settings) with env-overridable path fields and non-env schema constant fields
- `core/log_events.py` with stdlib logging, JSON formatter, JSONL log file, `get_logger` / `setup_logging`
- `pathlib.Path` operations throughout all callers
- Statsmodels-native model loading (no `pickle`)
- JSON error responses with correct HTTP status codes
- JSONL-backed `/logs` endpoint

## Implementation plan

- **Phase 0:** Add `pydantic-settings>=2.0` to `[project].dependencies` in `pyproject.toml`
- **Phase 1:** Rewrite `core/config.py` with `AppSettings` and `cfg` singleton
- **Phase 2:** Create `core/log_events.py`; delete `core/logging.py`
- **Phase 3a:** Migrate `ingestion/pipeline.py` (imports, pathlib, logging)
- **Phase 3b:** Migrate `forecasting/arima.py` (imports, pathlib, pickle→statsmodels)
- **Phase 3c:** Migrate `service/api.py` (imports, pathlib, error responses, /logs JSONL reader)
- **Phase 3d:** Update `run.py` with `setup_logging()` call
- **Phase 4:** Rewrite `tests/core/test_logging.py` → `test_log_events.py`; update `test_arima.py` and `test_api.py`

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| R1: Pydantic `Path` fields strip trailing slashes — callers must use `/` operator, never `str()` + `+` | Medium | Low | Enforce via code review; add note to PR description |
| R2: `cfg` singleton evaluated at import time — tests need `monkeypatch.setattr` on module-level `Path` aliases in callers | High | Medium | `@TestDesigner` documents fixture pattern in test plan |
| R3: statsmodels `ARIMAResults.load()` returns `Any` under Pyright strict — `# type: ignore[import-untyped]` required | High | Low | Pre-approved suppression per issue scope |
| R4: `test_logging.py` CSV assertions fully inverted — `@TestDesigner` owns redesign | High | Medium | Full test rewrite in Phase 4; existing tests expected to fail until then |
| R5: API error-case tests assert `get_json() is None` — must be updated in same commit | High | Medium | Update in Phase 4 alongside the implementation changes |
| R6: `/logs` endpoint switches from `pd.read_csv` to JSONL file reader — test mock target changes | Medium | Medium | Update mock targets in `test_api.py` during Phase 3c |

## Execution context

- **Working directory:** repo root (`/home/azureuser/cloudfiles/code/Users/andrea.del_monaco/capstone`)
- **Active branch:** `7-upgrade-core-foundation-typed-config-stdlib-logging-security`
- **Base branch:** `develop`
- **Python version:** 3.12 (pinned in `pyproject.toml`)
- **Validation commands (copy-pasteable, in priority order):**
  ```bash
  uv run ruff check src/ tests/
  uv run ruff format --check src/ tests/
  uv run pyright src/
  uv run tach check
  PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/ -q
  ```
  > **Repo memory note:** `.venv/` on cloudfiles is slow; use `/anaconda/envs/ai/bin/` tools directly. Run pytest from repo root with `PYTHONPATH=src`. For coverage: add `--cov-data-file=/tmp/.coverage`.

- **Tooling preconditions:**
  - Phase 0 (`uv sync`) must complete before any source file imports `core/config.py` — `pydantic-settings` must be importable.
  - No `.env` file required: all defaults work out of the box. Tests override paths via `monkeypatch.setattr`.

- **Files in scope (allow-list):**
  | File | Action |
  |---|---|
  | `pyproject.toml` | add dependency |
  | `src/ai_enterprise_workflow/core/config.py` | complete rewrite |
  | `src/ai_enterprise_workflow/core/log_events.py` | **create new** |
  | `src/ai_enterprise_workflow/core/logging.py` | **delete** (`git rm`) |
  | `src/ai_enterprise_workflow/core/__init__.py` | update docstring (1 line) |
  | `src/ai_enterprise_workflow/ingestion/pipeline.py` | imports + pathlib migration |
  | `src/ai_enterprise_workflow/forecasting/arima.py` | imports + pickle fix + pathlib |
  | `src/ai_enterprise_workflow/service/api.py` | imports + errors + `/logs` rewrite |
  | `run.py` | add `setup_logging()` call |
  | `tests/core/test_log_events.py` | **create new** |
  | `tests/core/test_logging.py` | **delete** (`git rm`) |
  | `tests/forecasting/test_arima.py` | fixture + assertions update |
  | `tests/service/test_api.py` | error tests + `/logs` mock target |

- **Files explicitly out of scope (do not touch):**
  - `src/ai_enterprise_workflow/monitoring/drift.py`
  - `src/ai_enterprise_workflow/cli.py`
  - `tach.toml` — layering unchanged
  - Any `__init__.py` except `core/__init__.py`
  - `Dockerfile`, `start.sh`, `nb/*.ipynb`

- **External fixtures required (already exist, no changes):**
  - `tests/resources/forecasting/3 revenue_country.csv`
  - `tests/resources/forecasting/4 revenue_total.csv`

---

## Decisions log

### D1 — Module rename: `core/logging.py` → `core/log_events.py`
- **Chosen:** `log_events.py` — reflected in Diff 3 (new file) and Diff 4 (delete old).
- **Rejected:**
  - Keep `logging.py`, use `import logging as _logging` inside — the shadow is systemic; doesn't eliminate the root cause.
  - `core/event_log.py` — noun-first name inconsistent with `log_ingest`/`log_train`/`log_predict` verb-prefixed public API.
- **Rationale:** `log_events.py` mirrors the `log_*` naming convention; unambiguously avoids the stdlib shadow. Cited in §2.3 of Planner output.
- **Locked:** yes.

### D2 — CSV removal (Q1 resolved by user)
- **Chosen:** Remove CSV writing entirely. The `log_*` functions emit via stdlib `logging` to a JSONL file (`events.jsonl`). The `/logs` endpoint reads JSONL — reflected in Diff 3 and Diff 7.
- **Rejected:** Keep CSV alongside stdlib logger — perpetuates the CSV debt.
- **Rationale:** User explicitly chose removal. JSONL is the modern structured-log format; eliminates the dual-write complexity and the pre-existing shadow.
- **Locked:** yes.

### D3 — Schema constants as `ClassVar` in `AppSettings` (Q2 resolved by user)
- **Chosen:** `KEYS`, `KEY_NAMES`, `KEY_TYPES` declared as `ClassVar` on `AppSettings` — reflected in Diff 2. Accessible as `cfg.KEYS` / `AppSettings.KEYS`.
- **Rejected:**
  - Module-level constants separate from `AppSettings` — user explicitly chose embedding.
  - Regular `Field(default=...)` — dict values containing Python type objects cannot be parsed from env vars; `ClassVar` sidesteps Pydantic validation entirely for these constants.
- **Rationale:** `ClassVar` is Pydantic's recommended pattern for class-level constants that must not participate in model validation or env-var binding. RFC: Pydantic v2 docs §Models/Class variables.
- **Locked:** yes.

### D4 — HTTP status codes (Q3 resolved by user)
- **Chosen:** `400` for missing required parameter; `422` for invalid type/value — reflected in Diff 7.
- **Rejected:** `400` for both — obscures the difference between absent and malformed params.
- **Rationale:** RFC 9110: 400 = "server cannot process request due to client error (missing)"; 422 = "request well-formed but contains semantic errors (invalid type)".
- **Locked:** yes.

### D5 — `pickle.load()` → `statsmodels.iolib.smpickle.load_pickle`
- **Chosen:** Use `load_pickle` from `statsmodels.iolib.smpickle` — reflected in Diff 6. Removes `import pickle` from application code.
- **Rejected:**
  - `ARIMAResults.load()` / `SARIMAXResults.load()` as class methods — these call `load_pickle` internally; importing the result-class types adds boilerplate with no benefit.
  - Keep `pickle.load()` with HMAC — adds complexity; statsmodels' own API is the idiomatic fix.
- **Rationale:** `load_pickle` is the direct statsmodels canonical deserializer matching `.save()` semantics. One import replaces four `pickle.load()` occurrences. OWASP A08 surface removed from application code.
- **Locked:** yes.

### D6 — Module-level `Path` aliases for test monkeypatching
- **Chosen:** Each caller module (`pipeline.py`, `arima.py`, `api.py`) defines `DIRECTORY_X: Path = cfg.directory_x` at module level — reflected in Diffs 5, 6, 7. Tests use `monkeypatch.setattr("module.DIRECTORY_OUTPUT", tmp_path)`.
- **Rejected:** Direct `cfg.directory_output` calls in every function body — makes callers depend on patching the Pydantic singleton, which is fragile with frozen models.
- **Rationale:** Module-level aliases are the pre-existing pattern in the test suite (test_arima.py L13-14 already patches `DIRECTORY_OUTPUT` and `DIRECTORY_MODELS` as module-level strings). This change preserves that pattern while upgrading the type from `str` to `Path`.
- **Locked:** yes.

### D7 — `pydantic-settings>=2.0` as new runtime dependency
- **Chosen:** `pydantic-settings>=2.0`, MIT license, maintained by pydantic-community — reflected in Diff 1.
- **Rejected:** `environs`/`dynaconf` — unfamiliar; add supply-chain risk; `pydantic-settings` is the natural extension of Pydantic already in the ecosystem.
- **Rationale:** Zero CVEs, MIT, one organisation (pydantic-community). Only allowed new dependency per scope agreement.
- **Locked:** yes.

### D8 — `_read_log_events` helper in `api.py` for testability
- **Chosen:** Extract JSONL file reading into a private `_read_log_events(log_dir: Path, event_type: str) -> list[dict[str, object]]` helper — reflected in Diff 7. Tests patch at `ai_enterprise_workflow.service.api._read_log_events`.
- **Rejected:** Inline JSONL reading in the `logs()` view function — untestable without real files or complex `mock_open` setup.
- **Rationale:** Thin helpers over I/O are the standard Flask testability pattern. Patch target changes from `pd.read_csv` to `_read_log_events` — equally simple in tests.
- **Locked:** yes.

---

## Detailed action plan

### Phase 0 — Add `pydantic-settings` dependency  `[effort: S]`  `[mandatory: @LinterSpecialist]`

Add `"pydantic-settings>=2.0"` to `[project].dependencies` in `pyproject.toml`. Regenerate lockfile.

**Dependency justification:** `pydantic-settings` 2.x, MIT License, maintained by pydantic-community; last release active; zero open CVEs (2026-05-16). No transitive deps beyond `pydantic` itself.

#### Execution recipe

1. **Pre-checks.** `git status` clean on branch `7-upgrade-core-foundation-typed-config-stdlib-logging-security`. `uv run python -c "import pydantic_settings"` fails (not yet installed) — expected.
2. **Apply diffs.** Apply **Diff 1 — `pyproject.toml`** from `## Proposed diffs`.
3. **Post-edit commands.**
   ```bash
   uv lock
   uv sync
   uv run python -c "import pydantic_settings; print(pydantic_settings.__version__)"
   ```
4. **Validation.**
   ```bash
   uv run ruff check pyproject.toml
   uv run deptry src/   # must exit 0; pydantic-settings is a used runtime dep
   ```
   Expected: `All checks passed.`
5. **Definition of Done.**
   - [ ] `pyproject.toml` contains `"pydantic-settings>=2.0"` in `[project].dependencies`
   - [ ] `uv.lock` regenerated (timestamp updated)
   - [ ] `python -c "import pydantic_settings"` exits 0
6. **Delegation directives.** `@LinterSpecialist`: *"Run `uv run deptry src/` after Phase 0. Confirm no new unused-dep or missing-dep issues. Attach output."*
7. **Stop conditions.** Stop if `uv lock` fails (dependency conflict). Report to user; do not proceed to Phase 1.

---

### Phase 1 — Rewrite `core/config.py`  `[effort: M]`  `[mandatory: @CodeReviewer, @LinterSpecialist]`

Replace the 9 bare module-level constants with `AppSettings(BaseSettings)` and a `cfg` singleton. Schema constants (`KEYS`, `KEY_NAMES`, `KEY_TYPES`) become `ClassVar` attributes (D3).

#### Execution recipe

1. **Pre-checks.** Phase 0 complete. `python -c "import pydantic_settings"` exits 0.
2. **Apply diffs.** Apply **Diff 2 — `src/ai_enterprise_workflow/core/config.py`** (complete file replacement).
3. **Post-edit commands.**
   ```bash
   uv run ruff format src/ai_enterprise_workflow/core/config.py
   ```
4. **Validation.**
   ```bash
   uv run ruff check src/ai_enterprise_workflow/core/config.py
   uv run pyright src/ai_enterprise_workflow/core/config.py
   uv run python -c "
   from ai_enterprise_workflow.core.config import cfg, AppSettings
   from pathlib import Path
   assert isinstance(cfg.directory_input, Path), 'directory_input must be Path'
   assert cfg.KEYS[0] == 'invoice_id', 'KEYS must start with invoice_id'
   print('Config OK:', cfg.directory_input, cfg.KEYS[:2])
   "
   ```
   Expected: prints `Config OK: data/input ('invoice_id', 'customer_id')`.
5. **Definition of Done.**
   - [ ] `from ai_enterprise_workflow.core.config import cfg` works in REPL
   - [ ] `cfg.directory_input` is a `pathlib.Path` equal to `Path("data/input")`
   - [ ] `cfg.KEYS` returns the 9-element tuple
   - [ ] Env override works: `DIRECTORY_INPUT=custom python -c "from ai_enterprise_workflow.core.config import cfg; assert str(cfg.directory_input)=='custom'"`
   - [ ] `pyright` exits 0 on `core/config.py`
   - [ ] **Note:** callers fail to import until Phases 2–3; do NOT run `pytest` until Phase 4.
6. **Delegation directives.** `@CodeReviewer`: *"Review `src/ai_enterprise_workflow/core/config.py` — ClassVar usage, env-var binding via `validation_alias`, singleton `cfg` pattern, tach boundary (only stdlib + pydantic-settings imported). Attach file."* `@LinterSpecialist`: *"Run `uv run pyright src/ai_enterprise_workflow/core/config.py` and `uv run ruff check src/ai_enterprise_workflow/core/config.py`. Report all errors."*
7. **Stop conditions.** Halt if `@CodeReviewer` objects to the `ClassVar` pattern. Surface to user before Phase 2.

---

### Phase 2 — Create `core/log_events.py`; delete `core/logging.py`  `[effort: M]`  `[mandatory: @CodeReviewer, @LinterSpecialist]`

Create the new stdlib-based logging module. Delete the old CSV shadow module. Do NOT update callers yet.

#### Execution recipe

1. **Pre-checks.** Phase 1 complete. `from ai_enterprise_workflow.core.config import cfg` works.
2. **Apply diffs.**
   - Apply **Diff 3 — `src/ai_enterprise_workflow/core/log_events.py`** (new file).
   - Apply **Diff 4 — `src/ai_enterprise_workflow/core/logging.py`** (delete): `git rm src/ai_enterprise_workflow/core/logging.py`
   - Apply **Diff 13 — `src/ai_enterprise_workflow/core/__init__.py`** (docstring update).
3. **Post-edit commands.**
   ```bash
   uv run ruff format src/ai_enterprise_workflow/core/log_events.py
   ```
4. **Validation.**
   ```bash
   uv run ruff check src/ai_enterprise_workflow/core/log_events.py
   uv run pyright src/ai_enterprise_workflow/core/log_events.py
   uv run tach check
   ```
   Expected: `tach check` exits 0. **Note:** `pytest tests/` WILL fail because `test_logging.py` imports from the deleted module. Do NOT run `pytest` until Phase 4.
5. **Definition of Done.**
   - [ ] `src/ai_enterprise_workflow/core/log_events.py` exists
   - [ ] `src/ai_enterprise_workflow/core/logging.py` deleted (`ls src/ai_enterprise_workflow/core/` confirms absence)
   - [ ] `from ai_enterprise_workflow.core.log_events import get_logger, setup_logging, log_ingest, log_train, log_predict` exits 0
   - [ ] `pyright` exits 0 on `log_events.py`
   - [ ] `tach check` exits 0
6. **Delegation directives.** `@CodeReviewer`: *"Review `src/ai_enterprise_workflow/core/log_events.py` — `_JsonlFormatter` correctness, `_STDLIB_LOG_KEYS` completeness, `log_*` extra-field choices, and tach boundary (only stdlib + core.config). Attach the file."*
7. **Stop conditions.** Halt if `tach check` fails after adding `log_events.py`. `core` must only import stdlib + pydantic-settings.

---

### Phase 3 — Caller migration  `[effort: M]`  `[mandatory: @LinterSpecialist; optional: @CodeReviewer]`

Migrate each caller in sequence (3a → 3b → 3c → 3d). Each sub-phase may be committed independently. Do NOT run the full `pytest` suite until Phase 4.

#### Phase 3a — `ingestion/pipeline.py`

1. **Pre-checks.** Phase 2 complete. `from ai_enterprise_workflow.core.log_events import log_ingest` exits 0.
2. **Apply diffs.** Apply **Diff 5 — `src/ai_enterprise_workflow/ingestion/pipeline.py`**.
3. **Post-edit.** `uv run ruff format src/ai_enterprise_workflow/ingestion/pipeline.py`
4. **Validation.**
   ```bash
   uv run ruff check src/ai_enterprise_workflow/ingestion/pipeline.py
   uv run pyright src/ai_enterprise_workflow/ingestion/pipeline.py
   uv run tach check
   ```
5. **Definition of Done.**
   - [ ] No `import os` in `pipeline.py`
   - [ ] All `directory_*` parameters typed as `Path`
   - [ ] `log_ingest` imported from `core.log_events`
   - [ ] `pyright` 0 errors; `tach check` 0 errors

#### Phase 3b — `forecasting/arima.py`

1. **Pre-checks.** Phase 3a complete.
2. **Apply diffs.** Apply **Diff 6 — `src/ai_enterprise_workflow/forecasting/arima.py`**.
3. **Post-edit.** `uv run ruff format src/ai_enterprise_workflow/forecasting/arima.py`
4. **Validation.**
   ```bash
   uv run ruff check src/ai_enterprise_workflow/forecasting/arima.py
   uv run pyright src/ai_enterprise_workflow/forecasting/arima.py
   uv run tach check
   ```
5. **Definition of Done.**
   - [ ] No `import pickle` in `arima.py`
   - [ ] No `import os` in `arima.py`
   - [ ] `load_pickle` imported from `statsmodels.iolib.smpickle`
   - [ ] `directory_models` parameter is `Path` in both train functions
   - [ ] `pyright` 0 errors; `tach check` 0 errors

#### Phase 3c — `service/api.py`

1. **Pre-checks.** Phase 3b complete.
2. **Apply diffs.** Apply **Diff 7 — `src/ai_enterprise_workflow/service/api.py`**.
3. **Post-edit.** `uv run ruff format src/ai_enterprise_workflow/service/api.py`
4. **Validation.**
   ```bash
   uv run ruff check src/ai_enterprise_workflow/service/api.py
   uv run pyright src/ai_enterprise_workflow/service/api.py
   uv run tach check
   ```
5. **Definition of Done.**
   - [ ] No `import pandas` in `api.py`
   - [ ] `_read_log_events` helper function present
   - [ ] All three error responses use `jsonify({"error": "…"})` with an HTTP status code
   - [ ] `pyright` 0 errors; `tach check` 0 errors

#### Phase 3d — `run.py`

1. **Pre-checks.** Phase 3c complete.
2. **Apply diffs.** Apply **Diff 8 — `run.py`**.
3. **Post-edit.** `uv run ruff format run.py`
4. **Validation.** `uv run ruff check run.py && uv run pyright run.py`
5. **Definition of Done.**
   - [ ] `setup_logging(log_dir=cfg.directory_logs)` called before `app.run()`
   - [ ] `pyright` 0 errors

#### Execution recipe (Phase 3 gate)

After all sub-phases complete:
```bash
uv run ruff check src/
uv run pyright src/
uv run tach check
```
All must exit 0. **Delegation directives.** `@LinterSpecialist`: *"Run `uv run pyright src/` and `uv run ruff check src/` after Phase 3d. Report any remaining errors. Attach the full pyright output."*
**Stop conditions.** Halt on any `tach check` failure. Halt if `pyright` reports errors in modules NOT touched by this phase.

---

### Phase 4 — Test rewrite  `[effort: L]`  `[mandatory: @TestDesigner, @LinterSpecialist]`

Delete `test_logging.py`, create `test_log_events.py`, update `test_arima.py` and `test_api.py`. Only after this phase is `pytest tests/` expected to pass fully.

#### Execution recipe

1. **Pre-checks.** All Phase 3 sub-phases complete. `uv run pyright src/` exits 0.
2. **Apply diffs.**
   - `git rm tests/core/test_logging.py`
   - Apply **Diff 9 — `tests/core/test_log_events.py`** (new file).
   - Apply **Diff 10 — `tests/forecasting/test_arima.py`** (hunks).
   - Apply **Diff 11 — `tests/service/test_api.py`** (hunks).
3. **Post-edit.** `uv run ruff format tests/`
4. **Validation.**
   ```bash
   uv run ruff check tests/
   PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/core/test_log_events.py -v
   PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/service/test_api.py -v
   PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/forecasting/test_arima.py -v -m "not slow"
   PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/ -q
   ```
   Expected: all tests pass. Slow integration tests may be skipped; run explicitly with `-m slow` for final gate.
5. **Definition of Done.**
   - [ ] `tests/core/test_logging.py` deleted
   - [ ] `tests/core/test_log_events.py` exists; all its tests pass
   - [ ] `pytest tests/service/test_api.py` exits 0 — error-case tests assert HTTP 400/422 + JSON body
   - [ ] `pytest tests/forecasting/test_arima.py -m "not slow"` exits 0
   - [ ] Full `pytest tests/ -q` exits 0
   - [ ] No `# type: ignore` added to test files without justification
6. **Delegation directives.** `@TestDesigner`: *"Review `tests/core/test_log_events.py`. Verify: (1) `caplog` captures records with `event` field; (2) `setup_logging` + file write test creates `events.jsonl` with valid JSON; (3) property-based tests clear `caplog` before each Hypothesis example via `caplog.clear()`. Attach file and `pytest -v` output."* `@LinterSpecialist`: *"Run `uv run ruff check tests/` and `uv run pyright src/`. Report all errors. Attach both outputs."*
7. **Stop conditions.** Halt if any test in `test_api.py` or `test_log_events.py` fails after the Phase 4 diff is applied — these must be 100% green before MR.

---

## Proposed diffs

> **Diff numbering:** 1=pyproject.toml, 2=config.py, 3=log_events.py (new), 4=logging.py (delete), 5=pipeline.py, 6=arima.py, 7=api.py, 8=run.py, 9=test_log_events.py (new), 10=test_logging.py (delete), 11=test_arima.py, 12=test_api.py (note: renumbered from 11 in plan — executor uses file paths, not diff numbers), 13=core/__init__.py.

---

### Diff 1 — `pyproject.toml`

*Phase 0. Rationale: add `pydantic-settings` as the only new runtime dependency (D7).*

```diff
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -7,6 +7,7 @@ dependencies = [
     "flask>=3.0",
     "numpy>=2.2,<3",
     "pandas<3",
+    "pydantic-settings>=2.0",
     "scipy>=1.13",
     "statsmodels>=0.14",
     "tqdm>=4.66",
```

---

### Diff 2 — `src/ai_enterprise_workflow/core/config.py`

*Phase 1. Rationale: complete rewrite — bare constants replaced by typed `AppSettings` with env-var binding and `ClassVar` schema constants (D3, D7).*

```diff
--- a/src/ai_enterprise_workflow/core/config.py
+++ b/src/ai_enterprise_workflow/core/config.py
@@ -1,49 +1,93 @@
-"""Configuration constants for the AI Enterprise Workflow service."""
-
-VERSION = 0.1
-DIRECTORY_INPUT = "./data/input/"
-DIRECTORY_OUTPUT = "./data/output/"
-DIRECTORY_MODELS = "./models/"
-DIRECTORY_LOGS = "./logs/"
-APP_BASE_URL = "http://127.0.0.1/"
-
-keys = (
-    "invoice_id",
-    "customer_id",
-    "stream_id",
-    "price",
-    "view_count",
-    "country",
-    "year",
-    "month",
-    "day",
-)
-
-key_names = {
-    "invoice": "invoice_id",
-    "customer_id": "customer_id",
-    "stream_id": "stream_id",
-    "price": "price",
-    "times_viewed": "view_count",
-    "country": "country",
-    "year": "year",
-    "month": "month",
-    "day": "day",
-    "total_price": "price",
-    "TimesViewed": "view_count",
-    "StreamID": "stream_id",
-}
-
-key_types = {
-    "invoice_id": int,
-    "customer_id": int,
-    "stream_id": int,
-    "price": float,
-    "view_count": int,
-    "country": str,
-    "year": int,
-    "month": int,
-    "day": int,
-}
+"""Typed configuration for the AI Enterprise Workflow service.
+
+All path fields default to relative paths suitable for running from the
+repository root. Override individual fields via environment variables or
+a ``.env`` file in the working directory.
+
+Attributes:
+    cfg: Process-level singleton. Import this in all application code.
+"""
+
+from __future__ import annotations
+
+from pathlib import Path
+from typing import ClassVar
+
+from pydantic import Field
+from pydantic_settings import BaseSettings, SettingsConfigDict
+
+
+class AppSettings(BaseSettings):
+    """Application settings loaded from environment variables or a ``.env`` file.
+
+    Attributes:
+        version: Package version number. Override via ``APP_VERSION``.
+        directory_input: Source JSON invoice files directory.
+            Override via ``DIRECTORY_INPUT``.
+        directory_output: Processed CSV output directory.
+            Override via ``DIRECTORY_OUTPUT``.
+        directory_models: Trained model artefacts directory.
+            Override via ``DIRECTORY_MODELS``.
+        directory_logs: JSONL event log directory.
+            Override via ``DIRECTORY_LOGS``.
+        app_base_url: Base URL for internal API references.
+            Override via ``APP_BASE_URL``.
+        KEYS: Ordered tuple of canonical invoice column names.
+            Not env-configurable (ClassVar).
+        KEY_NAMES: Source-to-canonical column name mapping.
+            Not env-configurable (ClassVar).
+        KEY_TYPES: Canonical column name to Python type mapping.
+            Not env-configurable (ClassVar).
+    """
+
+    model_config = SettingsConfigDict(
+        env_file=".env",
+        env_file_encoding="utf-8",
+        populate_by_name=True,
+        extra="ignore",
+    )
+
+    version: float = Field(default=0.1, validation_alias="APP_VERSION")
+    directory_input: Path = Field(
+        default=Path("data/input"), validation_alias="DIRECTORY_INPUT"
+    )
+    directory_output: Path = Field(
+        default=Path("data/output"), validation_alias="DIRECTORY_OUTPUT"
+    )
+    directory_models: Path = Field(
+        default=Path("models"), validation_alias="DIRECTORY_MODELS"
+    )
+    directory_logs: Path = Field(
+        default=Path("logs"), validation_alias="DIRECTORY_LOGS"
+    )
+    app_base_url: str = Field(
+        default="http://127.0.0.1/", validation_alias="APP_BASE_URL"
+    )
+
+    # ── Schema constants (ClassVar: excluded from Pydantic validation and env) ── #
+
+    KEYS: ClassVar[tuple[str, ...]] = (
+        "invoice_id",
+        "customer_id",
+        "stream_id",
+        "price",
+        "view_count",
+        "country",
+        "year",
+        "month",
+        "day",
+    )
+    KEY_NAMES: ClassVar[dict[str, str]] = {
+        "invoice": "invoice_id",
+        "customer_id": "customer_id",
+        "stream_id": "stream_id",
+        "price": "price",
+        "times_viewed": "view_count",
+        "country": "country",
+        "year": "year",
+        "month": "month",
+        "day": "day",
+        "total_price": "price",
+        "TimesViewed": "view_count",
+        "StreamID": "stream_id",
+    }
+    KEY_TYPES: ClassVar[dict[str, type[int] | type[float] | type[str]]] = {
+        "invoice_id": int,
+        "customer_id": int,
+        "stream_id": int,
+        "price": float,
+        "view_count": int,
+        "country": str,
+        "year": int,
+        "month": int,
+        "day": int,
+    }
+
+
+cfg: AppSettings = AppSettings()
```

---

### Diff 3 — `src/ai_enterprise_workflow/core/log_events.py` (new file)

*Phase 2. Rationale: stdlib-based logging replacing the CSV shadow module (D1, D2).*

```diff
--- /dev/null
+++ b/src/ai_enterprise_workflow/core/log_events.py
@@ -0,0 +1,148 @@
+"""Package-level event logging for the AI Enterprise Workflow service.
+
+This module replaces ``core/logging.py`` with a proper stdlib-based logging
+implementation that:
+
+- Provides :func:`get_logger` — returns child loggers of the package root.
+- Provides :func:`setup_logging` — attaches ``StreamHandler`` and optional
+  ``FileHandler`` (JSONL) to the package root logger.
+- Exposes :func:`log_ingest`, :func:`log_train`, :func:`log_predict` as
+  structured event emitters writing one JSON object per line to
+  ``<log_dir>/events.jsonl``.
+
+Notes:
+    This module avoids the name ``logging.py`` to prevent shadowing the
+    standard-library :mod:`logging` module (D1).
+"""
+
+from __future__ import annotations
+
+import json
+import logging
+import uuid
+from collections.abc import Mapping
+from datetime import datetime, timezone
+from logging import FileHandler, Formatter, Logger, StreamHandler, getLogger
+from pathlib import Path
+
+from ai_enterprise_workflow.core.config import cfg
+
+PACKAGE_LOGGER_NAME: str = "ai_enterprise_workflow"
+"""Namespace root for all package loggers."""
+
+_STDLIB_LOG_KEYS: frozenset[str] = frozenset(
+    {
+        "name",
+        "msg",
+        "args",
+        "levelname",
+        "levelno",
+        "pathname",
+        "filename",
+        "module",
+        "exc_info",
+        "exc_text",
+        "stack_info",
+        "lineno",
+        "funcName",
+        "created",
+        "msecs",
+        "relativeCreated",
+        "thread",
+        "threadName",
+        "processName",
+        "process",
+        "message",
+        "taskName",
+    }
+)
+"""Standard :class:`~logging.LogRecord` attribute names excluded from JSONL output."""
+
+_logger: Logger = getLogger(PACKAGE_LOGGER_NAME)
+
+
+class _JsonlFormatter(Formatter):
+    """Format :class:`~logging.LogRecord` instances as single-line JSON objects.
+
+    Each record serialises to a JSON object with keys ``timestamp``, ``level``,
+    ``logger``, ``message``, plus any extra fields injected via ``extra=`` on
+    the log call.
+    """
+
+    def format(self, record: logging.LogRecord) -> str:
+        """Return the log record serialised as a single JSON line.
+
+        Args:
+            record: The log record to format.
+
+        Returns:
+            A single-line JSON string without a trailing newline.
+        """
+        payload: dict[str, object] = {
+            "timestamp": datetime.fromtimestamp(
+                record.created, tz=timezone.utc
+            ).isoformat(),
+            "level": record.levelname,
+            "logger": record.name,
+            "message": record.getMessage(),
+        }
+        for key, value in record.__dict__.items():
+            if key not in _STDLIB_LOG_KEYS:
+                payload[key] = value
+        return json.dumps(payload)
+
+
+def get_logger(name: str) -> Logger:
+    """Return a child logger scoped under the package namespace.
+
+    Args:
+        name: Module name, typically ``__name__``. Automatically prefixed
+            with ``"ai_enterprise_workflow."`` unless already namespaced.
+
+    Returns:
+        A :class:`~logging.Logger` that inherits handlers from the package
+        root logger configured by :func:`setup_logging`.
+    """
+    if name.startswith(PACKAGE_LOGGER_NAME):
+        return getLogger(name)
+    return getLogger(f"{PACKAGE_LOGGER_NAME}.{name}")
+
+
+def setup_logging(
+    level: int = logging.INFO,
+    log_dir: Path | None = None,
+) -> None:
+    """Configure the package-level logger for this process.
+
+    Attaches a :class:`~logging.StreamHandler` (always) and, when *log_dir*
+    is provided, a :class:`~logging.FileHandler` writing JSONL records to
+    ``<log_dir>/events.jsonl``. Clears existing handlers first to prevent
+    duplicate output on repeated calls.
+
+    Args:
+        level: Numeric log level for the package logger and all handlers
+            (default: :data:`logging.INFO`).
+        log_dir: Directory for the ``events.jsonl`` file. Created if absent.
+            Pass ``None`` to disable file logging.
+    """
+    pkg_logger = getLogger(PACKAGE_LOGGER_NAME)
+    pkg_logger.setLevel(level)
+    pkg_logger.handlers.clear()
+    stream_handler = StreamHandler()
+    stream_handler.setLevel(level)
+    stream_handler.setFormatter(
+        Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")
+    )
+    pkg_logger.addHandler(stream_handler)
+    if log_dir is not None:
+        log_dir.mkdir(parents=True, exist_ok=True)
+        file_handler = FileHandler(log_dir / "events.jsonl", encoding="utf-8")
+        file_handler.setLevel(level)
+        file_handler.setFormatter(_JsonlFormatter())
+        pkg_logger.addHandler(file_handler)
+
+
+def log_ingest(shape: tuple[int, ...]) -> None:
+    """Emit a structured ingestion event to the package logger.
+
+    Args:
+        shape: Shape of the ingested dataset (e.g. ``(rows, cols)``).
+
+    Notes:
+        Emits an :data:`logging.INFO` record with
+        ``extra={"event": "ingest", "shape": list(shape), …}``.
+        Written to ``events.jsonl`` when :func:`setup_logging` has been
+        called with a *log_dir*.
+    """
+    _logger.info(
+        "ingest event",
+        extra={
+            "event": "ingest",
+            "id": str(uuid.uuid4())[:8],
+            "timestamp_event": datetime.now(tz=timezone.utc).isoformat(),
+            "shape": list(shape),
+        },
+    )
+
+
+def log_train(
+    model: str,
+    shape: tuple[int, ...],
+    performance: Mapping[str, object],
+    version: float = cfg.version,
+) -> None:
+    """Emit a structured training event to the package logger.
+
+    Args:
+        model: Model name or identifier (e.g. ``"arima"``).
+        shape: Shape of the training dataset.
+        performance: Performance metrics dictionary.
+        version: Package version recorded in the log entry.
+
+    Notes:
+        Emits an :data:`logging.INFO` record with
+        ``extra={"event": "train", "model": model, …}``.
+    """
+    _logger.info(
+        "train event",
+        extra={
+            "event": "train",
+            "id": str(uuid.uuid4())[:8],
+            "timestamp_event": datetime.now(tz=timezone.utc).isoformat(),
+            "version": version,
+            "model": model,
+            "shape": list(shape),
+            "performance": dict(performance),
+        },
+    )
+
+
+def log_predict(
+    model: str,
+    query: Mapping[str, object],
+    prediction: Mapping[str, object],
+    version: float = cfg.version,
+) -> None:
+    """Emit a structured prediction event to the package logger.
+
+    Args:
+        model: Model name or identifier.
+        query: Query parameters used for the prediction.
+        prediction: Prediction output mapping.
+        version: Package version recorded in the log entry.
+
+    Notes:
+        Emits an :data:`logging.INFO` record with
+        ``extra={"event": "predict", "model": model, …}``.
+    """
+    _logger.info(
+        "predict event",
+        extra={
+            "event": "predict",
+            "id": str(uuid.uuid4())[:8],
+            "timestamp_event": datetime.now(tz=timezone.utc).isoformat(),
+            "version": version,
+            "model": model,
+            "query": dict(query),
+            "prediction": dict(prediction),
+        },
+    )
```

---

### Diff 4 — `src/ai_enterprise_workflow/core/logging.py` (delete)

*Phase 2. Rationale: stdlib shadow removed (D1). Execute via `git rm`.*

```
git rm src/ai_enterprise_workflow/core/logging.py
```

No unified diff — file is deleted in its entirety. The executor must run `git rm`, not `rm`, to stage the deletion for the commit.

---

### Diff 5 — `src/ai_enterprise_workflow/ingestion/pipeline.py`

*Phase 3a. Rationale: migrate imports to cfg + log_events, pathlib everywhere (D6).*

```diff
--- a/src/ai_enterprise_workflow/ingestion/pipeline.py
+++ b/src/ai_enterprise_workflow/ingestion/pipeline.py
@@ -1,16 +1,16 @@
 """Data ingestion pipeline for loading and preprocessing invoice data."""

-import os
 import re
+from pathlib import Path

 import pandas as pd
 from tqdm import tqdm

-from ai_enterprise_workflow.core.config import (
-    DIRECTORY_INPUT,
-    DIRECTORY_OUTPUT,
-    key_names,
-    key_types,
-    keys,
-)
-from ai_enterprise_workflow.core.logging import log_ingest
+from ai_enterprise_workflow.core.config import cfg
+from ai_enterprise_workflow.core.log_events import log_ingest
+
+# Module-level aliases — patched in tests via monkeypatch.setattr
+DIRECTORY_INPUT: Path = cfg.directory_input
+DIRECTORY_OUTPUT: Path = cfg.directory_output

@@ -19,8 +19,8 @@ from ai_enterprise_workflow.core.logging import log_ingest
 def get_data(
     keys: tuple[str, ...],
     key_names: dict[str, str],
-    directory_data: str,
-    directory_output: str,
+    directory_data: Path,
+    directory_output: Path,
 ) -> pd.DataFrame:
@@ -38,9 +38,9 @@ def get_data(
     # Collect per-file DataFrames then concat once (avoids O(n²) copying)
     frames: list[pd.DataFrame] = []
-    for file_name in tqdm(os.listdir(directory_data)):
-        with open(directory_data + file_name) as file:
-            # Read JSON into pandas dataframe
+    for file_path in tqdm(sorted(directory_data.iterdir())):
+        with file_path.open() as file:
+            # Read JSON into pandas dataframe
             transactions = pd.read_json(file)
         # Rename column names using desired mappings
         transactions.rename(columns=key_names, inplace=True)
@@ -49,7 +49,7 @@ def get_data(
     data = pd.concat(frames, ignore_index=True)
     # Persist transactions in CSV file
-    data.to_csv(directory_output + "0 data.csv", index=False)
+    data.to_csv(directory_output / "0 data.csv", index=False)
     return data

@@ -66,7 +66,7 @@ def _to_digits(value: object) -> str:
 def clean_data(
     data: pd.DataFrame,
     keys: tuple[str, ...],
     key_types: dict[str, type[int] | type[float] | type[str]],
-    directory_output: str,
+    directory_output: Path,
 ) -> pd.DataFrame:
@@ -97,7 +97,7 @@ def clean_data(
     # Update data types to reduce memory consumption
     for key in keys:
         data[key] = data[key].astype(key_types[key])
     # Persist cleaned transactions in CSV file
-    data.to_csv(directory_output + "1 data_cleaned.csv", index=False)
+    data.to_csv(directory_output / "1 data_cleaned.csv", index=False)
     return data

@@ -103,7 +103,7 @@ def clean_data(
-def prepare_data(data: pd.DataFrame, directory_output: str) -> pd.DataFrame:
+def prepare_data(data: pd.DataFrame, directory_output: Path) -> pd.DataFrame:
@@ -123,7 +123,7 @@ def prepare_data(data: pd.DataFrame, directory_output: str) -> pd.DataFrame:
     # Remove negative price rows
     data = data[data["price"] > 0]
     # Persist prepared features in CSV file
-    data.to_csv(directory_output + "2 data_engineered.csv", index=False)
+    data.to_csv(directory_output / "2 data_engineered.csv", index=False)
     return data

@@ -133,7 +133,7 @@ def prepare_data(data: pd.DataFrame, directory_output: str) -> pd.DataFrame:
-def calculate_revenue_country(data: pd.DataFrame, directory_output: str) -> None:
+def calculate_revenue_country(data: pd.DataFrame, directory_output: Path) -> None:
@@ -144,7 +144,7 @@ def calculate_revenue_country(data: pd.DataFrame, directory_output: str) -> Non
     revenue = data.groupby(["country", "date"])["price"].sum().reset_index()
     revenue.rename(columns={"price": "revenue"}, inplace=True)
     # Persist calculated daily revenue by country in CSV file
-    revenue.to_csv(directory_output + "3 revenue_country.csv", index=False)
+    revenue.to_csv(directory_output / "3 revenue_country.csv", index=False)

@@ -153,7 +153,7 @@ def calculate_revenue_country(data: pd.DataFrame, directory_output: str) -> Non
-def calculate_revenue_total(data: pd.DataFrame, directory_output: str) -> None:
+def calculate_revenue_total(data: pd.DataFrame, directory_output: Path) -> None:
@@ -163,7 +163,7 @@ def calculate_revenue_total(data: pd.DataFrame, directory_output: str) -> None:
     revenue.set_index("date", inplace=True)
     revenue.rename(columns={"price": "revenue"}, inplace=True)
     # Persist calculated daily total revenue in CSV file
-    revenue.to_csv(directory_output + "4 revenue_total.csv")
+    revenue.to_csv(directory_output / "4 revenue_total.csv")

@@ -172,10 +172,10 @@ def calculate_revenue_total(data: pd.DataFrame, directory_output: str) -> None:
 def ingest(force: bool = False) -> None:
     ...
-    if not os.path.exists(DIRECTORY_OUTPUT):
-        os.makedirs(DIRECTORY_OUTPUT)
-    if force or not os.path.exists(DIRECTORY_OUTPUT + "4 revenue_total.csv"):
+    DIRECTORY_OUTPUT.mkdir(parents=True, exist_ok=True)
+    if force or not (DIRECTORY_OUTPUT / "4 revenue_total.csv").exists():
         print("Reading data...")
-        data = get_data(keys, key_names, DIRECTORY_INPUT, DIRECTORY_OUTPUT)
+        data = get_data(cfg.KEYS, cfg.KEY_NAMES, DIRECTORY_INPUT, DIRECTORY_OUTPUT)
         print("Cleaning data...")
-        data = clean_data(data, keys, key_types, DIRECTORY_OUTPUT)
+        data = clean_data(data, cfg.KEYS, cfg.KEY_TYPES, DIRECTORY_OUTPUT)
         print("Preparing features...")
```

---

### Diff 6 — `src/ai_enterprise_workflow/forecasting/arima.py`

*Phase 3b. Rationale: remove `pickle` (D5), replace with `load_pickle`; pathlib migration; cfg import (D6).*

```diff
--- a/src/ai_enterprise_workflow/forecasting/arima.py
+++ b/src/ai_enterprise_workflow/forecasting/arima.py
@@ -1,17 +1,17 @@
 """ARIMA and SARIMA forecasting models for revenue prediction."""

 from __future__ import annotations

-import os
-import pickle
+from pathlib import Path
 from typing import Any

 import pandas as pd
+from statsmodels.iolib.smpickle import load_pickle  # type: ignore[import-untyped]
 from statsmodels.tsa.api import SARIMAX  # type: ignore[import-untyped]
 from statsmodels.tsa.arima.model import ARIMA  # type: ignore[import-untyped]

-from ai_enterprise_workflow.core.config import (
-    DIRECTORY_MODELS,
-    DIRECTORY_OUTPUT,
-)
-from ai_enterprise_workflow.core.logging import log_predict, log_train
+from ai_enterprise_workflow.core.config import cfg
+from ai_enterprise_workflow.core.log_events import log_predict, log_train
 from ai_enterprise_workflow.ingestion.pipeline import ingest

+# Module-level aliases — patched in tests via monkeypatch.setattr
+DIRECTORY_OUTPUT: Path = cfg.directory_output
+DIRECTORY_MODELS: Path = cfg.directory_models
+
@@ -38,7 +38,7 @@ def get_revenue_country(revenue: pd.DataFrame, country: str) -> pd.DataFrame:
 def train_ARIMA_model(
     data: pd.Series[float],
     order: tuple[int, int, int],
-    directory_models: str,
+    directory_models: Path,
     country: str | None = None,
 ) -> Any:
@@ -54,9 +54,9 @@ def train_ARIMA_model(
     arima: Any = ARIMA(data, order=order)
     arima_model: Any = arima.fit()
     if country:
-        arima_model.save(directory_models + "arima_" + country + ".pickle")
+        arima_model.save(str(directory_models / f"arima_{country}.pickle"))
     else:
-        arima_model.save(directory_models + "arima.pickle")
+        arima_model.save(str(directory_models / "arima.pickle"))
     log_train("arima", data.shape, {})
     return arima_model

@@ -73,7 +73,7 @@ def train_ARIMA_model(
 def train_SARIMA_model(
     data: pd.Series[float],
     order: tuple[int, int, int],
     seasonal_order: tuple[int, int, int, int],
-    directory_models: str,
+    directory_models: Path,
     country: str | None = None,
 ) -> Any:
@@ -90,9 +90,9 @@ def train_SARIMA_model(
     sarima: Any = SARIMAX(data, order=order, seasonal_order=seasonal_order)
     sarima_model: Any = sarima.fit()
     if country:
-        sarima_model.save(directory_models + "sarima_" + country + ".pickle")  # type: ignore[union-attr]
+        sarima_model.save(str(directory_models / f"sarima_{country}.pickle"))  # type: ignore[union-attr]
     else:
-        sarima_model.save(directory_models + "sarima.pickle")  # type: ignore[union-attr]
+        sarima_model.save(str(directory_models / "sarima.pickle"))  # type: ignore[union-attr]
     log_train("sarima", data.shape, {})
     return sarima_model

@@ -138,10 +138,10 @@ def model(date: str, duration: int = 30, country: str | None = None) -> dict[st
     ...
-    if not os.path.exists(DIRECTORY_MODELS):
-        os.makedirs(DIRECTORY_MODELS)
-    if not os.path.exists(DIRECTORY_OUTPUT + "4 revenue_total.csv"):
+    DIRECTORY_MODELS.mkdir(parents=True, exist_ok=True)
+    if not (DIRECTORY_OUTPUT / "4 revenue_total.csv").exists():
         ingest()
-    revenue_countries = pd.read_csv(DIRECTORY_OUTPUT + "3 revenue_country.csv")
-    revenue_total = pd.read_csv(DIRECTORY_OUTPUT + "4 revenue_total.csv")
+    revenue_countries = pd.read_csv(DIRECTORY_OUTPUT / "3 revenue_country.csv")
+    revenue_total = pd.read_csv(DIRECTORY_OUTPUT / "4 revenue_total.csv")

@@ -156,20 +156,18 @@ def model(date: str, duration: int = 30, country: str | None = None) -> dict[st
     if country:
-        if os.path.exists(DIRECTORY_MODELS + "arima_" + country + ".pickle"):
-            with open(DIRECTORY_MODELS + "arima_" + country + ".pickle", "rb") as file:
-                arima_model = pickle.load(file)
+        arima_pickle = DIRECTORY_MODELS / f"arima_{country}.pickle"
+        if arima_pickle.exists():
+            arima_model = load_pickle(str(arima_pickle))
         else:
             arima_model = train_ARIMA_model(
                 revenue["revenue"], order, DIRECTORY_MODELS, country
             )
-        if os.path.exists(DIRECTORY_MODELS + "sarima_" + country + ".pickle"):
-            with open(DIRECTORY_MODELS + "sarima_" + country + ".pickle", "rb") as file:
-                sarima_model = pickle.load(file)
+        sarima_pickle = DIRECTORY_MODELS / f"sarima_{country}.pickle"
+        if sarima_pickle.exists():
+            sarima_model = load_pickle(str(sarima_pickle))
         else:
             sarima_model = train_SARIMA_model(
                 revenue["revenue"], order, seasonal_order, DIRECTORY_MODELS, country
             )
     else:
-        if os.path.exists(DIRECTORY_MODELS + "arima.pickle"):
-            with open(DIRECTORY_MODELS + "arima.pickle", "rb") as file:
-                arima_model = pickle.load(file)
+        arima_pickle = DIRECTORY_MODELS / "arima.pickle"
+        if arima_pickle.exists():
+            arima_model = load_pickle(str(arima_pickle))
         else:
             arima_model = train_ARIMA_model(revenue["revenue"], order, DIRECTORY_MODELS)
-        if os.path.exists(DIRECTORY_MODELS + "sarima.pickle"):
-            with open(DIRECTORY_MODELS + "sarima.pickle", "rb") as file:
-                sarima_model = pickle.load(file)
+        sarima_pickle = DIRECTORY_MODELS / "sarima.pickle"
+        if sarima_pickle.exists():
+            sarima_model = load_pickle(str(sarima_pickle))
         else:
             sarima_model = train_SARIMA_model(
                 revenue["revenue"], order, seasonal_order, DIRECTORY_MODELS
             )

@@ -217,7 +215,7 @@ def model(date: str, duration: int = 30, country: str | None = None) -> dict[st
     revenue["forecast_sarima"], sarima_result = predict(
         sarima_model, "sarima", start, end, actual_result
     )
-    revenue.to_csv(DIRECTORY_OUTPUT + "5 predictions" + file_suffix + ".csv")
+    revenue.to_csv(DIRECTORY_OUTPUT / f"5 predictions{file_suffix}.csv")
     return {"arima": arima_result, "sarima": sarima_result}
```

---

### Diff 7 — `src/ai_enterprise_workflow/service/api.py`

*Phase 3c. Rationale: remove pandas, add `_read_log_events` helper (D8), fix error responses (D4), pathlib (D6).*

```diff
--- a/src/ai_enterprise_workflow/service/api.py
+++ b/src/ai_enterprise_workflow/service/api.py
@@ -1,11 +1,14 @@
 """Flask REST API exposing the forecasting and logging endpoints."""

+import json
 import os
+from pathlib import Path

-import pandas as pd
 from flask import Flask, jsonify, request
 from flask.typing import ResponseReturnValue

-from ai_enterprise_workflow.core.config import DIRECTORY_LOGS
+from ai_enterprise_workflow.core.config import cfg
 from ai_enterprise_workflow.forecasting.arima import model

 app = Flask(__name__)
 app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "0") == "1"

+# Module-level alias — patched in tests via monkeypatch.setattr
+DIRECTORY_LOGS: Path = cfg.directory_logs
+
+
+def _read_log_events(
+    log_dir: Path, event_type: str
+) -> list[dict[str, object]]:
+    """Read log events of the given type from the JSONL event log.
+
+    Args:
+        log_dir: Directory containing the ``events.jsonl`` log file.
+        event_type: The ``event`` field value to filter on
+            (e.g. ``"ingest"``).
+
+    Returns:
+        List of deserialised JSON records whose ``event`` field matches
+        ``event_type``. Returns an empty list when the log file is absent
+        or contains no matching records. Malformed JSON lines are skipped.
+    """
+    log_file = log_dir / "events.jsonl"
+    if not log_file.exists():
+        return []
+    records: list[dict[str, object]] = []
+    with log_file.open(encoding="utf-8") as fh:
+        for line in fh:
+            line = line.strip()
+            if not line:
+                continue
+            try:
+                record: dict[str, object] = json.loads(line)
+                if record.get("event") == event_type:
+                    records.append(record)
+            except json.JSONDecodeError:
+                continue
+    return records

@@ -62,8 +95,8 @@ def predict() -> ResponseReturnValue:
     # Check date parameter in request
     if "date" in request.args:
         date = request.args["date"]
     else:
-        return "Error: No date parameter was provided."
+        return jsonify({"error": "No date parameter was provided."}), 400
     # Check country parameter in request
     country = request.args.get("country", None)
     # Check duration parameter in request
     if "duration" in request.args:
         duration = request.args["duration"]
-        duration = 30 if duration == "" else int(duration)
+        try:
+            duration = 30 if duration == "" else int(duration)
+        except ValueError:
+            return jsonify({"error": "duration must be an integer."}), 422
     else:
         duration = 30

@@ -98,14 +116,9 @@ def logs() -> ResponseReturnValue:
     if "type" in request.args:
         log_type = request.args["type"]
     else:
-        return "Error: No type parameter was provided."
-    if log_type == "ingest":
-        logs = pd.read_csv(DIRECTORY_LOGS + "ingest.csv").to_dict()
-    elif log_type == "train":
-        logs = pd.read_csv(DIRECTORY_LOGS + "train.csv").to_dict()
-    elif log_type == "predict":
-        logs = pd.read_csv(DIRECTORY_LOGS + "predict.csv").to_dict()
-    else:
-        return "Error: Invalid type parameter was provided."
-    return jsonify({"data": logs})
+        return jsonify({"error": "No type parameter was provided."}), 400
+    if log_type not in {"ingest", "train", "predict"}:
+        return jsonify({"error": "Invalid type parameter was provided."}), 422
+    result = _read_log_events(DIRECTORY_LOGS, log_type)
+    return jsonify({"data": result})
```

---

### Diff 8 — `run.py`

*Phase 3d. Rationale: call `setup_logging` at process startup so file handler is active for `app.run()`.*

```diff
--- a/run.py
+++ b/run.py
@@ -1,7 +1,11 @@
 """Entry-point: start the Flask development server."""

 import os

+from ai_enterprise_workflow.core.config import cfg
+from ai_enterprise_workflow.core.log_events import setup_logging
 from ai_enterprise_workflow.service import app

 if __name__ == "__main__":
+    setup_logging(log_dir=cfg.directory_logs)
     port = int(os.environ.get("PORT", "80"))
     app.run(host="0.0.0.0", port=port)
```

---

### Diff 9 — `tests/core/test_log_events.py` (new file)

*Phase 4. Rationale: replaces CSV-based `test_logging.py` with caplog-based and file-write tests (D2).*

```diff
--- /dev/null
+++ b/tests/core/test_log_events.py
@@ -0,0 +1,138 @@
+"""Tests for the stdlib-based event logger (core.log_events)."""
+
+import json
+import logging
+import string
+from pathlib import Path
+
+import pytest
+from hypothesis import HealthCheck, given
+from hypothesis import settings as hyp_settings
+from hypothesis import strategies as st
+
+from ai_enterprise_workflow.core.log_events import (
+    PACKAGE_LOGGER_NAME,
+    get_logger,
+    log_ingest,
+    log_predict,
+    log_train,
+    setup_logging,
+)
+
+
+class TestLogEvents:
+    """Test suite for core.log_events public functions."""
+
+    @pytest.mark.unit
+    class TestUnit:
+        """Happy-path and validation tests."""
+
+        def test_get_logger_returns_child_of_package_logger(self) -> None:
+            """get_logger returns a logger namespaced under the package root."""
+            logger = get_logger("some.module")
+            assert logger.name.startswith(PACKAGE_LOGGER_NAME)
+
+        def test_get_logger_already_namespaced_returns_same(self) -> None:
+            """get_logger with a fully-qualified name returns it unchanged."""
+            logger = get_logger("ai_enterprise_workflow.forecasting.arima")
+            assert logger.name == "ai_enterprise_workflow.forecasting.arima"
+
+        def test_log_ingest_emits_info_record(
+            self, caplog: pytest.LogCaptureFixture
+        ) -> None:
+            """log_ingest emits an INFO record with event='ingest'."""
+            with caplog.at_level(logging.INFO, logger=PACKAGE_LOGGER_NAME):
+                log_ingest((1000, 10))
+            assert any(
+                r.getMessage() == "ingest event"
+                and getattr(r, "event", None) == "ingest"
+                for r in caplog.records
+            )
+
+        def test_log_train_emits_info_record(
+            self, caplog: pytest.LogCaptureFixture
+        ) -> None:
+            """log_train emits an INFO record with event='train' and model field."""
+            with caplog.at_level(logging.INFO, logger=PACKAGE_LOGGER_NAME):
+                log_train("arima", (500, 1), {"mse": 0.05})
+            assert any(
+                getattr(r, "event", None) == "train"
+                and getattr(r, "model", None) == "arima"
+                for r in caplog.records
+            )
+
+        def test_log_predict_emits_info_record(
+            self, caplog: pytest.LogCaptureFixture
+        ) -> None:
+            """log_predict emits an INFO record with event='predict'."""
+            with caplog.at_level(logging.INFO, logger=PACKAGE_LOGGER_NAME):
+                log_predict("sarima", {"date": "2020-01-01"}, {"revenue": 1000.0})
+            assert any(
+                getattr(r, "event", None) == "predict"
+                and getattr(r, "model", None) == "sarima"
+                for r in caplog.records
+            )
+
+        def test_log_ingest_shape_stored_in_record(
+            self, caplog: pytest.LogCaptureFixture
+        ) -> None:
+            """log_ingest stores shape as a list in the record's extra fields."""
+            with caplog.at_level(logging.INFO, logger=PACKAGE_LOGGER_NAME):
+                log_ingest((42, 7))
+            record = next(
+                r for r in caplog.records if getattr(r, "event", None) == "ingest"
+            )
+            assert getattr(record, "shape", None) == [42, 7]
+
+        def test_setup_logging_writes_jsonl_file(self, tmp_path: Path) -> None:
+            """setup_logging + log_ingest creates events.jsonl with valid JSON."""
+            setup_logging(log_dir=tmp_path)
+            log_ingest((100, 5))
+            jsonl_file = tmp_path / "events.jsonl"
+            assert jsonl_file.exists()
+            with jsonl_file.open() as fh:
+                lines = [ln.strip() for ln in fh if ln.strip()]
+            assert len(lines) >= 1
+            record = json.loads(lines[-1])
+            assert record.get("event") == "ingest"
+            assert "timestamp" in record
+            # Reset handlers to avoid polluting subsequent tests
+            setup_logging()
+
+    @pytest.mark.contract
+    class TestContracts:
+        """Property-based invariant tests for core.log_events functions."""
+
+        @given(
+            n=st.integers(min_value=1, max_value=5),
+            shape=st.tuples(
+                st.integers(min_value=1, max_value=10_000),
+                st.integers(min_value=1, max_value=100),
+            ),
+        )
+        @hyp_settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
+        def test_log_ingest_record_count_invariant(
+            self, n: int, shape: tuple[int, int], caplog: pytest.LogCaptureFixture
+        ) -> None:
+            """For any n ≥ 1 calls, exactly n 'ingest' records are emitted."""
+            caplog.clear()
+            with caplog.at_level(logging.INFO, logger=PACKAGE_LOGGER_NAME):
+                for _ in range(n):
+                    log_ingest(shape)
+            ingest_records = [
+                r for r in caplog.records if getattr(r, "event", None) == "ingest"
+            ]
+            assert len(ingest_records) == n
+
+        @given(
+            model_name=st.text(
+                min_size=1,
+                max_size=50,
+                alphabet=string.ascii_letters + string.digits,
+            )
+        )
+        @hyp_settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
+        def test_log_train_any_model_name_emits_record(
+            self, model_name: str, caplog: pytest.LogCaptureFixture
+        ) -> None:
+            """log_train emits a record for any non-empty alphanumeric model name."""
+            caplog.clear()
+            with caplog.at_level(logging.INFO, logger=PACKAGE_LOGGER_NAME):
+                log_train(model_name, (1, 1), {})
+            assert any(
+                getattr(r, "event", None) == "train"
+                and getattr(r, "model", None) == model_name
+                for r in caplog.records
+            )
+
+        @given(
+            query=st.dictionaries(
+                st.text(min_size=1, max_size=10, alphabet=string.ascii_lowercase),
+                st.integers(),
+                max_size=3,
+            ),
+            prediction=st.dictionaries(
+                st.text(min_size=1, max_size=10, alphabet=string.ascii_lowercase),
+                st.floats(allow_nan=False, allow_infinity=False),
+                max_size=3,
+            ),
+        )
+        @hyp_settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
+        def test_log_predict_any_mapping_emits_record(
+            self,
+            query: dict[str, int],
+            prediction: dict[str, float],
+            caplog: pytest.LogCaptureFixture,
+        ) -> None:
+            """log_predict emits a record for any valid query and prediction mappings."""
+            caplog.clear()
+            with caplog.at_level(logging.INFO, logger=PACKAGE_LOGGER_NAME):
+                log_predict("model", query, prediction)
+            assert any(
+                getattr(r, "event", None) == "predict" for r in caplog.records
+            )
```

---

### Diff 10 — `tests/core/test_logging.py` (delete)

*Phase 4. Rationale: replaced by `test_log_events.py` (D2). Execute via `git rm`.*

```
git rm tests/core/test_logging.py
```

---

### Diff 11 — `tests/forecasting/test_arima.py`

*Phase 4. Rationale: patch targets now deliver `Path` values; remove `os` dependency.*

```diff
--- a/tests/forecasting/test_arima.py
+++ b/tests/forecasting/test_arima.py
@@ -1,7 +1,6 @@
 """Tests for the ARIMA/SARIMA forecasting model (forecasting.arima)."""

-import os
 import shutil
 from pathlib import Path
 from unittest.mock import patch
@@ -22,7 +21,7 @@ pytestmark = [
 ]


-@pytest.fixture(scope="class")
-def arima_dirs(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, str]:
+@pytest.fixture(scope="class")
+def arima_dirs(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
     """Create isolated output and model directories with fixture CSVs pre-copied.

     Args:
@@ -30,7 +29,7 @@ def arima_dirs(tmp_path_factory: pytest.TempPathFactory) -> tuple[str, str]:

     Returns:
-        A 2-tuple of ``(output_dir, model_dir)``, each ending with ``'/'``.
+        A 2-tuple of ``(output_dir, model_dir)`` as :class:`~pathlib.Path` objects.
     """
     output_dir = tmp_path_factory.mktemp("arima_output")
     model_dir = tmp_path_factory.mktemp("arima_models")
     for csv_file in ("3 revenue_country.csv", "4 revenue_total.csv"):
         shutil.copy(str(_FIXTURES / csv_file), str(output_dir / csv_file))
-    return str(output_dir) + "/", str(model_dir) + "/"
+    return output_dir, model_dir


 class TestArima:
@@ -44,14 +43,14 @@ class TestArima:

         def test_model_train_saves_arima_and_sarima_pickles(
-            self, arima_dirs: tuple[str, str]
+            self, arima_dirs: tuple[Path, Path]
         ) -> None:
             """model() persists both arima.pickle and sarima.pickle on first run."""
             output_dir, model_dir = arima_dirs
             with (
                 patch(_OUTPUT_TARGET, output_dir),
                 patch(_MODELS_TARGET, model_dir),
             ):
                 model("2018-11-20", 30, None)
-            assert os.path.exists(model_dir + "arima.pickle")
-            assert os.path.exists(model_dir + "sarima.pickle")
+            assert (model_dir / "arima.pickle").exists()
+            assert (model_dir / "sarima.pickle").exists()

         def test_model_predict_returns_arima_and_sarima_keys(
-            self, arima_dirs: tuple[str, str]
+            self, arima_dirs: tuple[Path, Path]
         ) -> None:
```

---

### Diff 12 — `tests/service/test_api.py`

*Phase 4. Rationale: update mock targets and error-case assertions (D4, D8).*

```diff
--- a/tests/service/test_api.py
+++ b/tests/service/test_api.py
@@ -1,16 +1,13 @@
 """Tests for the Flask REST API endpoints (service.api)."""

 from collections.abc import Generator
 from unittest.mock import patch

-import pandas as pd
 import pytest
 from flask.testing import FlaskClient
 from hypothesis import HealthCheck, given, settings
 from hypothesis import strategies as st

 from ai_enterprise_workflow.service.api import app

 _MODEL_TARGET = "ai_enterprise_workflow.service.api.model"
-_CSV_TARGET = "ai_enterprise_workflow.service.api.pd.read_csv"
+_READ_LOG_TARGET = "ai_enterprise_workflow.service.api._read_log_events"

@@ -59,8 +56,8 @@ class TestApi:
         def test_predict_missing_date_returns_error_string(
             self, flask_client: FlaskClient
         ) -> None:
-            """POST /predict without date returns a plain-text error response."""
+            """POST /predict without date returns HTTP 400 with JSON error body."""
             # Act
             response = flask_client.post("/predict")
             # Assert
-            assert "Error" in response.data.decode()
-            assert response.get_json() is None
+            assert response.status_code == 400
+            assert response.get_json() == {"error": "No date parameter was provided."}

         def test_logs_valid_type_returns_data_key(
             self, flask_client: FlaskClient
         ) -> None:
             """POST /logs with valid type returns JSON with 'data' key."""
             # Arrange
-            with patch(_CSV_TARGET, return_value=pd.DataFrame({"col": [1]})):
+            with patch(_READ_LOG_TARGET, return_value=[{"event": "predict"}]):
                 # Act
                 response = flask_client.post("/logs?type=predict")
             # Assert
             assert "data" in response.get_json()

         def test_logs_missing_type_returns_error_string(
             self, flask_client: FlaskClient
         ) -> None:
-            """POST /logs without type returns a plain-text error response."""
+            """POST /logs without type returns HTTP 400 with JSON error body."""
             # Act
             response = flask_client.post("/logs")
             # Assert
-            assert "Error" in response.data.decode()
-            assert response.get_json() is None
+            assert response.status_code == 400
+            assert response.get_json() == {"error": "No type parameter was provided."}

         def test_logs_invalid_type_returns_error_string(
             self, flask_client: FlaskClient
         ) -> None:
-            """POST /logs with unknown type returns a plain-text error response."""
+            """POST /logs with unknown type returns HTTP 422 with JSON error body."""
             # Act
             response = flask_client.post("/logs?type=unknown")
             # Assert
-            assert "Error" in response.data.decode()
-            assert response.get_json() is None
+            assert response.status_code == 422
+            assert response.get_json() == {"error": "Invalid type parameter was provided."}

@@ -118,7 +115,7 @@ class TestApi:
         @given(log_type=st.sampled_from(["ingest", "train", "predict"]))
         @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
         def test_logs_all_valid_types_return_data_key(
             self, flask_client: FlaskClient, log_type: str
         ) -> None:
             """POST /logs returns JSON with 'data' key for every registered log type."""
             # Arrange
-            with patch(_CSV_TARGET, return_value=pd.DataFrame({"col": [1]})):
+            with patch(_READ_LOG_TARGET, return_value=[]):
                 # Act
                 response = flask_client.post(f"/logs?type={log_type}")
             # Assert
             assert "data" in response.get_json()
```

---

### Diff 13 — `src/ai_enterprise_workflow/core/__init__.py`

*Phase 2. Rationale: update docstring to reflect the module rename (D1).*

```diff
--- a/src/ai_enterprise_workflow/core/__init__.py
+++ b/src/ai_enterprise_workflow/core/__init__.py
@@ -1 +1 @@
-"""Foundational primitives: configuration constants and event logging."""
+"""Foundational primitives: typed configuration and structured event logging."""
```

---

## Failure playbook

| # | Symptom | Likely cause | Remediation | Escalate to |
|---|---|---|---|---|
| 1 | `pyright` reports `reportMissingModuleSource` on `pydantic_settings` | `uv sync` not run after Phase 0 | Run `uv sync`; confirm `pydantic_settings` importable | @LinterSpecialist |
| 2 | `pyright` reports `reportAttributeAccessIssue` on `cfg.KEYS` | `ClassVar` not recognised through instance in older pyright | Upgrade `pyright` to latest; or access as `AppSettings.KEYS` in callers and update Diff 5/6 accordingly | @CodeReviewer |
| 3 | `tach check` fails after Phase 2 | `log_events.py` imports something outside `core` (e.g. forgot `from ai_enterprise_workflow.core.config import cfg` instead of a cross-layer import) | Verify imports in `log_events.py`: only `stdlib` + `core.config` are allowed | @LinterSpecialist |
| 4 | `pytest tests/core/test_log_events.py` fails on `caplog` not capturing | `PACKAGE_LOGGER_NAME` logger has `propagate=False` set elsewhere | Check `setup_logging` — ensure `pkg_logger.propagate` is left at default (`True`) | @TestDesigner |
| 5 | `pytest tests/service/test_api.py` fails on error-case status codes | Phase 3c diff not yet applied (or `api.py` not reloaded) | Re-apply Diff 7; verify `response.status_code` logic in `/predict` and `/logs` views | @LinterSpecialist |
| 6 | `pytest tests/forecasting/test_arima.py` fails — `AttributeError: 'Path' object has no attribute 'endswith'` | `arima.py` still passes `Path` to a statsmodels function that expects `str` | Ensure all `.save()` and `load_pickle()` calls use `str(path)` as in Diff 6 | @LinterSpecialist |
| 7 | `ruff` reports `A002` (argument `model` shadows builtin) | Pre-existing, not introduced by this change | Confirm in `ruff.toml` `per-file-ignores` or add `# noqa: A002`; do not suppress without confirming it was pre-existing | @LinterSpecialist |
| 8 | `ruff` reports `D1` (missing docstring) on new functions | `_read_log_events` or helpers lack docstrings | Add Google-style docstrings per `AGENTS.md`; all public and private functions in `api.py` and `log_events.py` must be documented | @DocsReviewer |
| 9 | `test_log_ingest_record_count_invariant` fails with count > n | `caplog.clear()` not called before each Hypothesis example | Verify `caplog.clear()` is the first line inside the `@given` test body (see Diff 9) | @TestDesigner |
| 10 | `uv lock` fails with dependency conflict | Another dependency pins `pydantic<2` | Check `pyproject.toml` for conflicting pins; open a user discussion before proceeding — do not force-resolve | user |

---

## Roadmap

| # | Phase | Owner | Status | Evidence / Notes |
|---|-------|-------|--------|------------------|
| 1 | Phase 0 — Add pydantic-settings dependency | @ProjectDeveloper → @LinterSpecialist | done | pydantic-settings 2.12.0 installed in /anaconda/envs/ai; uv.lock updated |
| 2 | Phase 1 — Rewrite core/config.py | @ProjectDeveloper → @CodeReviewer, @LinterSpecialist | done | AppSettings + cfg singleton; pyright 0 errors; KEY_TYPES union fixed to PYI055 |
| 3 | Phase 2 — Create log_events.py; delete logging.py | @ProjectDeveloper → @CodeReviewer, @LinterSpecialist | done | log_events.py created; logging.py git-rm'd; pyright 0 errors; tach clean |
| 4 | Phase 3a — Migrate ingestion/pipeline.py | @ProjectDeveloper → @LinterSpecialist | done | pathlib throughout; cfg.KEYS/KEY_NAMES/KEY_TYPES; ruff clean; pyright 0 errors |
| 5 | Phase 3b — Migrate forecasting/arima.py | @ProjectDeveloper → @LinterSpecialist | done | load_pickle replaces pickle.load; pathlib throughout; ruff clean; pyright 0 errors |
| 6 | Phase 3c — Migrate service/api.py | @ProjectDeveloper → @LinterSpecialist | done | _read_log_events; 400/422 JSON errors; ruff clean (PLW2901 fixed); pyright 0 errors |
| 7 | Phase 3d — Update run.py | @ProjectDeveloper | done | setup_logging(log_dir=cfg.directory_logs) added before app.run() |
| 8 | Phase 4 — Test rewrite | @ProjectDeveloper → @TestDesigner, @LinterSpecialist | done | test_log_events.py created; test_logging.py git-rm'd; test_arima.py + test_api.py updated; 19 non-slow tests pass |
| 9 | Documentation pass | @DocsReviewer | done | 7 docstring items applied; stale core.logging ref fixed; ruff 0 errors; pyright 0 errors |
| 10 | Integration gate | @IntegrationChecker (`docs_mode=skip`) | done | GO: G0–G6 all pass; pydantic>=2.0 added as direct dep (G1 fix); ruff format applied to 2 files (G3 fix); 19/19 non-slow tests pass |
| 11 | MR preparation | @ProjectDeveloper | done | 5 split commits pushed; branch pushed to origin; PR URL: https://github.com/andrea-dm/ai-enterprise-workflow-capstone/pull/new/7-upgrade-core-foundation-typed-config-stdlib-logging-security |

**Effort summary:** S×1, M×3 (Phases 1, 2, 3-combined), L×1 (Phase 4) — total estimated complexity: Medium. No XL phases.

---

## Acceptance criteria (mirror)

*No GitLab issue; criteria mirrored from the approved GitHub issue #7.*

- [ ] `cfg = AppSettings()` importable from `ai_enterprise_workflow.core.config`; each path field is a `pathlib.Path`; env-var `DIRECTORY_INPUT` overrides `cfg.directory_input`
- [ ] `KEYS`, `KEY_NAMES`, `KEY_TYPES` are non-env `ClassVar` attributes on `AppSettings` with the same values as the former module-level constants
- [ ] `core/logging.py` deleted; `core/log_events.py` exists with `get_logger`, `setup_logging`, `log_ingest`, `log_train`, `log_predict`
- [ ] `log_ingest` / `log_train` / `log_predict` write to a JSONL file under `cfg.directory_logs` via stdlib JSON formatter; no CSV files written
- [ ] `service/api.py` `/logs` endpoint reads the JSONL log file via `_read_log_events` and filters by `event` field; returns `{"data": [...]}` with HTTP 200
- [ ] No `pickle` import in `forecasting/arima.py`; model loading uses `load_pickle` from `statsmodels.iolib.smpickle`
- [ ] All error responses in `service/api.py` return `{"error": "…"}` JSON with HTTP 400 (missing param) or 422 (invalid type)
- [ ] `uv run ruff check src/ tests/` exits 0
- [ ] `uv run ruff format --check src/ tests/` exits 0
- [ ] `uv run pyright src/` exits 0 (strict mode)
- [ ] `uv run tach check` exits 0
- [ ] `PYTHONPATH=src pytest tests/ -q` exits 0 (all tests pass)
- [ ] No `TODO` or `NotImplementedError` introduced

---

## Handover

**Design phase complete.** The floor is handed over to `@ProjectDeveloper`.

This manifest was authored by a reasoning-class model with the explicit assumption that `@ProjectDeveloper` is an execution-class model. All non-trivial design decisions are pre-resolved in `## Decisions log`; all phase-level instructions are encoded as `#### Execution recipe` sub-blocks; predictable failure modes are covered in `## Failure playbook`. **Do not re-derive design choices.**

`@ProjectDeveloper` must:

1. Treat this manifest as the single source of truth. If a phrase in the manifest seems to require a design judgment, stop and ask the user; do not improvise.
2. Read `## Execution context` before starting and verify every precondition.
3. Execute phases sequentially. For each phase: flip the roadmap row to `in-progress`, run the `Execution recipe` literally, apply the referenced `Proposed diffs` exactly as drafted, run the listed validation commands, then flip the row to `done` with a one-line evidence note.
4. Any deviation from a `Proposed diff` must be recorded in the `Roadmap` `Evidence / Notes` column with justification, and the diff block patched in place.
5. On any predictable failure, consult `## Failure playbook` first before improvising or escalating.
6. After the last code phase, hand over to `@DocsReviewer`, then to `@IntegrationChecker` with `docs_mode=skip`.
7. Verify every box in `Acceptance criteria (mirror)` is checked before preparing the merge request.
8. Prepare the MR using `.github/PULL_REQUEST_TEMPLATE.md` (or the default template if absent).
9. When the user later confirms that the PR was merged and the linked issue is closed, re-invoke `@ProjectDeveloper` to record the merge/closure evidence, set the manifest frontmatter `status:` to `done`.

To start: `@ProjectDeveloper execute manifests/7-upgrade-core-foundation-typed-config-stdlib-logging-security.md`.
To finalize after merge: `@ProjectDeveloper finalize manifests/7-upgrade-core-foundation-typed-config-stdlib-logging-security.md`.

---

## Manifest changelog

| Timestamp | Actor | Change |
|---|---|---|
| 2026-05-16T00:00:00Z | @IssueTracker | Initial scaffold — issue #7, branch created, manifest bootstrapped |
| 2026-05-16T12:00:00Z | @ProjectArchitect | Added Execution context, Decisions log (D1–D8), Detailed action plan (Phases 0–4 with effort tags and Execution recipes), Proposed diffs (Diffs 1–13), Failure playbook (10 entries), Roadmap, Acceptance criteria mirror, Handover. Resolved Q1 (CSV removal), Q2 (ClassVar schema constants), Q3 (HTTP 400/422). |
| 2026-05-16T18:00:00Z | @ProjectDeveloper | Executed Phases 0–4; KEY_TYPES annotation deviation (PYI055: dict[str, type[int|float|str]]); pydantic declared as direct dep (G1 fix); ruff format applied post-DocsReviewer (G3 fix); 5 split commits pushed to origin; PR opened targeting develop; lock released. |
