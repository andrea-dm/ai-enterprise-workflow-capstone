---
manifest_version: 1
branch: 8-cli-wiring-service-hardening
issue: 8
issue_url: https://github.com/andrea-dm/ai-enterprise-workflow-capstone/issues/8
status: done
scope: "cli, service"
tests: tests/service/test_api.py
affects: []
mr: "!12"
mr_url: https://github.com/andrea-dm/ai-enterprise-workflow-capstone/pull/12
lock: null
---

# wire CLI subcommands and harden Flask service

## Current state

### `src/ai_enterprise_workflow/cli.py` (14 lines)

The module is a single-function placeholder that immediately raises
`NotImplementedError`. No argparse parser exists; no subcommands are wired.
No `[project.scripts]` entrypoint is declared in `pyproject.toml`.

```python
def main() -> int:
    raise NotImplementedError("CLI wiring deferred to Slice 6")
```

`tach.toml` declares `ai_enterprise_workflow.cli` as depending only on
`ai_enterprise_workflow.core` and `ai_enterprise_workflow.service`; the
`ingestion` and `forecasting` layers are not yet listed.

### `src/ai_enterprise_workflow/service/api.py` (current public surface)

| Symbol | Kind | Notes |
|---|---|---|
| `app` | `Flask` instance | Module-level global; no factory. |
| `healthz()` | `GET /healthz` | Liveness probe — returns `{"status": "ok"}` 200. |
| `predict()` | `POST /predict` | Accepts `date`, `duration`, `country` query params; no ISO-date validation; no 422 responses; duration empty-string guard present but integer validation absent. |
| `logs()` | `POST /logs` | Returns tail of log CSV. |

No `/readyz` readiness probe. No `create_app(config)` factory. Missing HTTP 422
validation for malformed `date` and non-positive `duration`.

---

## Specification

### Slice C — CLI wiring

#### `tach.toml` change

Extend `ai_enterprise_workflow.cli` `depends_on` to include:
- `ai_enterprise_workflow.ingestion`
- `ai_enterprise_workflow.forecasting`

#### `pyproject.toml` change

Add a `[project.scripts]` entry:

```toml
[project.scripts]
ai_enterprise_workflow = "ai_enterprise_workflow.cli:main"
```

#### `cli.py` public API

| Symbol | Signature | Behaviour |
|---|---|---|
| `setup_ingest(sub)` | `(sub: argparse._SubParsersAction) -> None` | Registers `ingest` subparser with `--force` flag. |
| `execute_ingest(args)` | `(args: argparse.Namespace) -> int` | Calls `pipeline.ingest(force=args.force)`; returns `0`. |
| `setup_train(sub)` | `(sub: argparse._SubParsersAction) -> None` | Registers `train` subparser with `--date` (required). |
| `execute_train(args)` | `(args: argparse.Namespace) -> int` | Calls `arima.model(args.date, 30, None)`; returns `0`. |
| `setup_predict(sub)` | `(sub: argparse._SubParsersAction) -> None` | Registers `predict` subparser with `--date` (required), `--duration` (default 30), `--country` (optional). |
| `execute_predict(args)` | `(args: argparse.Namespace) -> int` | Calls `arima.model(args.date, args.duration, args.country)`; returns `0`. |
| `setup_serve(sub)` | `(sub: argparse._SubParsersAction) -> None` | Registers `serve` subparser with `--host` (default `0.0.0.0`) and `--port` (default `8080`). |
| `execute_serve(args)` | `(args: argparse.Namespace) -> int` | Calls `create_app(cfg).run(host=args.host, port=args.port)`; returns `0`. |
| `main()` | `() -> int` | Builds root parser, attaches all four subparsers, dispatches via `args.func(args)`. Returns `1` if no subcommand given (prints usage). |

`sys.exit(main())` is called in the `if __name__ == "__main__"` guard.

---

### Slice D — Service hardening

#### `create_app(config)` factory

```python
def create_app(config: Settings | None = None) -> Flask:
    ...
```

- Accepts an optional `Settings` instance (from `ai_enterprise_workflow.core.config`).
- Registers all existing routes plus `/readyz`.
- Returns a fully configured `Flask` application.
- The module-level `app` global is replaced by `app = create_app()` so existing
  tests that import `app` directly continue to work without modification.

#### `GET /readyz`

| Condition | Response body | HTTP status |
|---|---|---|
| `cfg.directory_output / "4 revenue_total.csv"` exists | `{"status": "ready"}` | 200 |
| File absent | `{"status": "not ready", "reason": "data not ingested"}` | 503 |

#### Input validation for `POST /predict` (HTTP 422)

| Condition | Error response |
|---|---|
| `date` absent | `{"error": "date parameter is required"}` 422 |
| `date` not ISO format (`YYYY-MM-DD`) | `{"error": "date must be YYYY-MM-DD"}` 422 |
| `duration` non-integer string | `{"error": "duration must be a positive integer"}` 422 |
| `duration` ≤ 0 | `{"error": "duration must be a positive integer"}` 422 |
| `duration` empty string | treated as default `30` (existing behaviour preserved) |

Validation runs before calling `model(...)`.

---

## Implementation plan

### Phase C-1 — tach + pyproject wiring
1. Add `ai_enterprise_workflow.ingestion` and `ai_enterprise_workflow.forecasting`
   to the `depends_on` list of `ai_enterprise_workflow.cli` in `tach.toml`.
2. Add `[project.scripts]` block to `pyproject.toml`.
3. Verify: `uv run tach check` exits 0.

### Phase C-2 — `cli.py` rewrite
1. Replace the placeholder with `setup_X` / `execute_X` pairs and a `main()`
   dispatcher following the pattern above.
2. Add Google-style docstrings to every public function.
3. Verify: `uv run ruff check src/ai_enterprise_workflow/cli.py` and
   `uv run pyright src/` exit 0.

### Phase D-1 — App factory
1. Introduce `create_app(config: Settings | None = None) -> Flask`.
2. Move route registrations into the factory.
3. Keep `app = create_app()` at module scope.
4. Verify existing `test_api.py` tests pass.

### Phase D-2 — `/readyz` endpoint
1. Implement the readiness probe using `cfg.directory_output`.
2. Add unit tests covering both branches.

### Phase D-3 — 422 validation for `/predict`
1. Add ISO-date regex check and positive-integer coercion before calling `model`.
2. Return `jsonify({"error": "..."}), 422` on failure.
3. Preserve the empty-string → 30 default for `duration`.

### Phase D-4 — Test suite
1. Extend `tests/service/test_api.py` with cases for `/readyz` (both branches)
   and each 422 scenario.
2. Run full suite: `PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/ -q`.

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| tach expansion breaks existing import graph | Low | Medium | Run `uv run tach check` after each phase; revert if violations appear. |
| Slice B (#7) not yet merged into `develop` when this branch is cut | Medium | High | Rebase `8-cli-wiring-service-hardening` onto `develop` after #7 is merged before starting Phase C-1. |
| `create_app` refactor silently breaks tests that import module-level `app` | Low | Medium | Keep `app = create_app()` at module scope; run existing tests after Phase D-1 before proceeding. |
| Duration empty-string guard regression after 422 refactor | Low | Low | Explicitly test `POST /predict?date=2019-01-01&duration=` in Phase D-4 to verify default-30 path survives. |
| New 422 paths interfere with existing Hypothesis-style property tests | Low | Low | Audit `test_api.py` for property-based tests before Phase D-3; scope the validation guard narrowly. |

---

## Execution context

- **Working directory:** repo root (`/home/azureuser/cloudfiles/code/Users/andrea.del_monaco/capstone`)
- **Active branch:** `8-cli-wiring-service-hardening`
- **Base branch:** `develop`
- **Python version:** 3.12
- **Validation commands (copy-pasteable, in priority order):**
  ```bash
  uv run ruff check src/ tests/
  uv run ruff format --check src/ tests/
  uv run pyright src/
  uv run tach check
  PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/ -q
  ```
- **Tooling preconditions:**
  - Issue #7 (`7-upgrade-core-foundation-typed-config-stdlib-logging-security`) **must be merged into `develop` before starting Phase D-1**. Phase C phases (tach, pyproject, cli.py) can be executed immediately; they do not depend on issue #7.
  - Run `git rebase origin/develop` before Phase D-1 to pull in the `cfg`, `create_app`-ready `api.py`, and `log_events.py` state.
  - Executor must install the package in editable mode before testing the `[project.scripts]` entrypoint: `uv pip install -e .`

- **Files in scope (allow-list):**
  | File | Action |
  |---|---|
  | `tach.toml` | modify — add `ingestion` + `forecasting` to `cli` deps |
  | `pyproject.toml` | modify — add `[project.scripts]` |
  | `src/ai_enterprise_workflow/cli.py` | **full rewrite** |
  | `src/ai_enterprise_workflow/service/api.py` | modify — add `create_app`, `readyz`, date/duration validation |
  | `tests/service/test_api.py` | modify — add 5 new tests |

- **Files explicitly out of scope:**
  - `src/ai_enterprise_workflow/core/` — no changes
  - `src/ai_enterprise_workflow/forecasting/` — no changes
  - `src/ai_enterprise_workflow/ingestion/` — no changes
  - `Dockerfile`, `run.py`, `nb/`

---

## Decisions log

### D1 — `train` and `predict` as separate subcommands
- **Chosen:** `setup_train`/`execute_train` (fixed args: `--date` only, duration=30, country=None) and `setup_predict`/`execute_predict` (full args: `--date`, `--duration`, `--country`) as distinct dispatch pairs — reflected in Diff 3.
- **Rejected:** Single `execute_predict` handler shared by both `train` and `predict` (Planner's suggestion) — acceptance criteria explicitly require `train --date …` calls `model(date, 30, None)` while `predict --date … --duration … --country …` calls `model(date, duration, country)`. Different argument sets warrant separate parsers.
- **Rationale:** Keeping the subcommands separate makes `--help` output unambiguous to end users and is consistent with the carbon_pledges dispatch pattern.
- **Locked:** yes.

### D2 — App factory with `add_url_rule` (no `@app.route` decorators)
- **Chosen:** Remove all `@app.route` decorators; register view functions via `flask_app.add_url_rule(...)` inside `create_app`; expose `app = create_app()` module-level singleton — reflected in Diff 4.
- **Rejected:**
  - Keep `@app.route` decorators and have `create_app` return the same module-level `app` — does not support a fresh instance for testing; conftest.py (Slice G) requires `create_app({"TESTING": True})` to return a fresh instance with routes.
  - Use Flask Blueprints — cleaner long-term but requires importing `Blueprint` and restructuring all routes; out of scope for this slice.
- **Rationale:** `add_url_rule` inside the factory is the minimal change that enables per-test fresh app creation. Module-level `app = create_app()` preserves backward compatibility.
- **Locked:** yes.

### D3 — Date validation via `datetime.date.fromisoformat`
- **Chosen:** `datetime.date.fromisoformat(date)` in a `try/except ValueError` block — reflected in Diff 4.
- **Rejected:** Regex (`r"^\d{4}-\d{2}-\d{2}$"`) — accepts semantically invalid dates like `2019-13-32`; `fromisoformat` is stricter and stdlib-only.
- **Rationale:** stdlib `datetime` is already imported for validation; no new dependency. `fromisoformat` raises `ValueError` for any non-ISO-8601 date string in Python 3.7+.
- **Locked:** yes.

### D4 — `/readyz` checks `cfg.directory_output / "4 revenue_total.csv"`
- **Chosen:** Check existence of `cfg.directory_output / "4 revenue_total.csv"` — the same guard used in `arima.model()` (post-Slice-A) — reflected in Diff 4.
- **Rejected:** Check database connection or model directory — overkill for this service; the only resource that matters is whether the data pipeline has been run.
- **Rationale:** Mirrors the existing `model()` guard. Consistent sentinel file.
- **Locked:** yes.

### D5 — `execute_ingest/train/predict/serve` use lazy imports
- **Chosen:** Lazy imports inside each `execute_*` function body (e.g., `from ai_enterprise_workflow.ingestion.pipeline import ingest` inside `execute_ingest`) — reflected in Diff 3.
- **Rejected:** Module-level imports — slows `--help` startup by importing Flask, pandas, statsmodels; lazy imports are idiomatic for CLI entrypoints.
- **Rationale:** CLI `--help` must be fast. Heavy imports deferred to execution time.
- **Locked:** yes. Note: lazy imports affect mock target paths in tests — mock target is `"ai_enterprise_workflow.ingestion.pipeline.ingest"`, not `"ai_enterprise_workflow.cli.ingest"`.

---

## Detailed action plan

### Phase C-1 — tach + pyproject scaffolding  `[effort: S]`  `[mandatory: @LinterSpecialist]`

Update `tach.toml` and `pyproject.toml` to declare the CLI's runtime dependencies and the console entrypoint.

#### Execution recipe

1. **Pre-checks.** `git status` clean. `uv run tach check` passes on current branch.
2. **Apply diffs.** Apply **Diff 1 — `tach.toml`** and **Diff 2 — `pyproject.toml`** from `## Proposed diffs`.
3. **Post-edit.** `uv pip install -e .` to register the entrypoint.
4. **Validation.**
   ```bash
   uv run tach check
   uv run ai_enterprise_workflow --help  # must print usage, not raise ImportError
   ```
5. **Definition of Done.**
   - [ ] `tach.toml` `cli` `depends_on` includes `ingestion` and `forecasting`
   - [ ] `pyproject.toml` has `[project.scripts]` section
   - [ ] `uv run ai_enterprise_workflow --help` exits 0 (raises `NotImplementedError` is OK until Phase C-2)
   - [ ] `uv run tach check` exits 0
6. **Delegation directives.** `@LinterSpecialist`: *"Run `uv run tach check` after Phase C-1. Confirm `ai_enterprise_workflow.cli` deps now include `ingestion` and `forecasting`. Attach output."*
7. **Stop conditions.** Stop if `tach check` fails. Report to user.

---

### Phase C-2 — `cli.py` rewrite  `[effort: M]`  `[mandatory: @CodeReviewer, @LinterSpecialist]`

Replace the 14-line placeholder with the full `setup_X`/`execute_X` implementation.

#### Execution recipe

1. **Pre-checks.** Phase C-1 complete. `uv run tach check` exits 0.
2. **Apply diffs.** Apply **Diff 3 — `src/ai_enterprise_workflow/cli.py`** (full file replacement).
3. **Post-edit.** `uv run ruff format src/ai_enterprise_workflow/cli.py`
4. **Validation.**
   ```bash
   uv run ruff check src/ai_enterprise_workflow/cli.py
   uv run pyright src/ai_enterprise_workflow/cli.py
   uv run tach check
   uv run ai_enterprise_workflow --help
   uv run ai_enterprise_workflow ingest --help
   uv run ai_enterprise_workflow predict --help
   ```
   Expected: all exit 0; `--help` prints subcommand list.
5. **Definition of Done.**
   - [ ] `main()` returns `int`; no `NotImplementedError`
   - [ ] `setup_ingest`, `execute_ingest`, `setup_train`, `execute_train`, `setup_predict`, `execute_predict`, `setup_serve`, `execute_serve` all present with Google-style docstrings
   - [ ] `pyright` 0 errors on `cli.py`
   - [ ] `ruff check` 0 errors on `cli.py`
   - [ ] `uv run tach check` 0 errors
6. **Delegation directives.** `@CodeReviewer`: *"Review `src/ai_enterprise_workflow/cli.py` — lazy import pattern, exception handling policy (bare `except Exception`), `execute_serve` using module-level `app` singleton, `main()` return codes (0/1/2). Attach file."* `@LinterSpecialist`: *"Run `uv run pyright src/ai_enterprise_workflow/cli.py`. Report any `reportUnknownMemberType` on `argparse._SubParsersAction`. If flagged, add `# type: ignore[reportPrivateUsage]` per D1."*
7. **Stop conditions.** Halt if `@CodeReviewer` objects to the lazy import pattern. Surface to user.

---

### Phase D-1 — App factory  `[effort: S]`  `[mandatory: @CodeReviewer]`

**Dependency:** Issue #7 merged and branch rebased onto `develop`.

Add `create_app(config)` factory, remove `@app.route` decorators, register routes via `add_url_rule`, preserve module-level `app` singleton.

#### Execution recipe

1. **Pre-checks.** `git rebase origin/develop` complete. `from ai_enterprise_workflow.core.config import cfg` exits 0. Current `tests/service/test_api.py` passes: `PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/service/ -q`.
2. **Apply diffs.** Apply hunk A of **Diff 4 — `src/ai_enterprise_workflow/service/api.py`** (imports + remove global app + remove decorators + add `create_app` + `app = create_app()`).
3. **Post-edit.** `uv run ruff format src/ai_enterprise_workflow/service/api.py`
4. **Validation.**
   ```bash
   uv run ruff check src/ai_enterprise_workflow/service/api.py
   uv run pyright src/ai_enterprise_workflow/service/api.py
   PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/service/ -q
   ```
   Expected: existing tests still pass (module-level `app` preserved).
5. **Definition of Done.**
   - [ ] `create_app(config)` function present with Google-style docstring
   - [ ] `app = create_app()` at module level
   - [ ] No `@app.route` decorators remain
   - [ ] All existing tests pass
6. **Delegation directives.** `@CodeReviewer`: *"Review `create_app` factory — confirm `add_url_rule` correctly registers all 3 existing routes; verify `app = create_app()` at module level preserves import compatibility. Attach diff."*
7. **Stop conditions.** Halt if existing tests fail after D-1. Do not proceed to D-2.

---

### Phase D-2 — `/readyz` endpoint  `[effort: S]`  `[mandatory: @TestDesigner]`

Add the `readyz` view function and register it in `create_app`.

#### Execution recipe

1. **Pre-checks.** Phase D-1 complete and all existing tests pass.
2. **Apply diffs.** Apply hunk B of **Diff 4** (`readyz` function + `add_url_rule("/readyz", ...)` in `create_app`).
3. **Post-edit.** `uv run ruff format src/ai_enterprise_workflow/service/api.py`
4. **Validation.**
   ```bash
   uv run ruff check src/ai_enterprise_workflow/service/api.py
   uv run pyright src/ai_enterprise_workflow/service/api.py
   PYTHONPATH=src /anaconda/envs/ai/bin/python -c "
   from ai_enterprise_workflow.service.api import create_app
   app = create_app({'TESTING': True})
   c = app.test_client()
   r = c.get('/readyz')
   print(r.status_code, r.get_json())
   "
   ```
   Expected: `503 {'status': 'not ready', 'reason': 'data not ingested'}` (no CSV in default path).
5. **Definition of Done.**
   - [ ] `GET /readyz` returns `{"status": "ready"}` 200 when `cfg.directory_output / "4 revenue_total.csv"` exists
   - [ ] `GET /readyz` returns `{"status": "not ready", "reason": "data not ingested"}` 503 otherwise
   - [ ] `pyright` 0 errors
6. **Delegation directives.** `@TestDesigner`: *"Design fixture for `test_readyz_*` tests: use `monkeypatch.setattr(cfg, 'directory_output', tmp_path)` and `(tmp_path / '4 revenue_total.csv').touch()` for the ready-path test. Confirm `cfg` is not a frozen Pydantic model (check `model_config` in `core/config.py`)."*
7. **Stop conditions.** Stop if `cfg.directory_output` cannot be monkeypatched (frozen model). Escalate to @CodeReviewer.

---

### Phase D-3 — `/predict` 422 validation  `[effort: S]`  `[mandatory: @LinterSpecialist]`

Add ISO-date validation and positive-integer duration enforcement.

#### Execution recipe

1. **Pre-checks.** Phase D-2 complete.
2. **Apply diffs.** Apply hunk C of **Diff 4** (validation additions to `predict()` body).
3. **Post-edit.** `uv run ruff format src/ai_enterprise_workflow/service/api.py`
4. **Validation.**
   ```bash
   uv run ruff check src/ai_enterprise_workflow/service/api.py
   uv run pyright src/ai_enterprise_workflow/service/api.py
   PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/service/ -q
   ```
5. **Definition of Done.**
   - [ ] `POST /predict?date=not-a-date` returns `{"error": "Invalid date 'not-a-date'. Expected YYYY-MM-DD."}` 422
   - [ ] `POST /predict?date=2019-01-01&duration=-1` returns `{"error": "duration must be a positive integer."}` 422
   - [ ] `POST /predict?date=2019-01-01&duration=abc` returns `{"error": "duration must be a positive integer."}` 422
   - [ ] `POST /predict?date=2019-01-01&duration=` still treated as duration=30 (existing behaviour preserved)
   - [ ] All existing `test_api.py` tests pass
6. **Delegation directives.** `@LinterSpecialist`: *"Run `uv run ruff check src/ai_enterprise_workflow/service/api.py`. Confirm no `E501` (line length) on the f-string in the error message. Attach output."*
7. **Stop conditions.** Halt if existing Hypothesis test `test_predict_any_valid_duration_returns_data_key` fails — it uses `min_value=1`, so no ≤0 values should be generated; failure indicates a regression.

---

### Phase D-4 — New tests  `[effort: S]`  `[mandatory: @TestDesigner]`

Add 5 new test methods covering `/readyz` and 422 validation paths.

#### Execution recipe

1. **Pre-checks.** Phase D-3 complete. All existing tests pass.
2. **Apply diffs.** Apply **Diff 5 — `tests/service/test_api.py`** (append 5 new test methods).
3. **Post-edit.** `uv run ruff format tests/service/test_api.py`
4. **Validation.**
   ```bash
   uv run ruff check tests/service/test_api.py
   PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/service/test_api.py -v
   PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/ -q
   ```
   Expected: all pass, including 5 new tests.
5. **Definition of Done.**
   - [ ] `test_readyz_returns_ready_when_csv_exists` passes
   - [ ] `test_readyz_returns_503_when_csv_absent` passes
   - [ ] `test_predict_invalid_date_returns_422` passes
   - [ ] `test_predict_non_positive_duration_returns_422` passes
   - [ ] `test_predict_non_integer_duration_returns_422` passes
   - [ ] Full `pytest tests/ -q` exits 0
6. **Delegation directives.** `@TestDesigner`: *"Review `tests/service/test_api.py` — confirm all 5 new tests use `@pytest.mark.unit`, correct assert patterns (`response.status_code == 422`, `response.get_json() == {"error": "..."}`), and `monkeypatch` for readyz CSV fixture. Attach file and `pytest -v` output."*
7. **Stop conditions.** Halt if any new test fails. Fix before MR.

---

## Proposed diffs

### Diff 1 — `tach.toml`

*Phase C-1. Add `ingestion` + `forecasting` to `cli`'s `depends_on`.*

```diff
--- a/tach.toml
+++ b/tach.toml
@@ -26,8 +26,10 @@
 [[modules]]
 path = "ai_enterprise_workflow.cli"
 depends_on = [
     "ai_enterprise_workflow.core",
     "ai_enterprise_workflow.service",
+    "ai_enterprise_workflow.ingestion",
+    "ai_enterprise_workflow.forecasting",
 ]
```

---

### Diff 2 — `pyproject.toml`

*Phase C-1. Add `[project.scripts]` entrypoint.*

```diff
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -13,6 +13,9 @@ dependencies = [
     "tqdm>=4.66",
 ]

+[project.scripts]
+ai_enterprise_workflow = "ai_enterprise_workflow.cli:main"
+
 [build-system]
 requires = ["hatchling"]
 build-backend = "hatchling.build"
```

---

### Diff 3 — `src/ai_enterprise_workflow/cli.py` (full rewrite)

*Phase C-2. Replace the 14-line placeholder with the full dispatch implementation (D1, D5).*

```diff
--- a/src/ai_enterprise_workflow/cli.py
+++ b/src/ai_enterprise_workflow/cli.py
@@ -1,13 +1,170 @@
-"""Command-line entrypoint placeholder (wired in Slice 6)."""
-
-
-def main() -> int:
-    """Reserved CLI entrypoint.
-
-    Returns:
-        Process exit code.
-
-    Raises:
-        NotImplementedError: Always — the CLI body is deferred to Slice 6.
-    """
-    raise NotImplementedError("CLI wiring deferred to Slice 6")
+"""Command-line entrypoint for the AI Enterprise Workflow service."""
+
+from __future__ import annotations
+
+import argparse
+import json
+import sys
+from argparse import ArgumentParser, Namespace
+
+
+# ── ingest ────────────────────────────────────────────────────────────────────
+
+
+def setup_ingest(subparsers: argparse._SubParsersAction[ArgumentParser]) -> None:
+    """Register the 'ingest' subcommand parser.
+
+    Args:
+        subparsers: The subparser action group to add the 'ingest' command to.
+    """
+    parser = subparsers.add_parser("ingest", help="Run the data ingestion pipeline.")
+    parser.add_argument(
+        "--force",
+        action="store_true",
+        default=False,
+        help="Re-run the pipeline even if output files already exist.",
+    )
+    parser.set_defaults(func=execute_ingest)
+
+
+def execute_ingest(args: Namespace) -> int:
+    """Execute the ingest subcommand.
+
+    Args:
+        args: Parsed namespace with ``force: bool``.
+
+    Returns:
+        0 on success; 1 on unhandled exception.
+    """
+    from ai_enterprise_workflow.ingestion.pipeline import ingest  # noqa: PLC0415
+
+    try:
+        ingest(force=args.force)
+        return 0
+    except Exception as exc:
+        print(f"Error: {exc}", file=sys.stderr)
+        return 1
+
+
+# ── train ─────────────────────────────────────────────────────────────────────
+
+
+def setup_train(subparsers: argparse._SubParsersAction[ArgumentParser]) -> None:
+    """Register the 'train' subcommand parser.
+
+    Args:
+        subparsers: The subparser action group to add the 'train' command to.
+    """
+    parser = subparsers.add_parser(
+        "train", help="Train ARIMA/SARIMA models for a given reference date."
+    )
+    parser.add_argument(
+        "--date",
+        required=True,
+        help="Reference date (YYYY-MM-DD) for model training.",
+    )
+    parser.set_defaults(func=execute_train)
+
+
+def execute_train(args: Namespace) -> int:
+    """Execute the train subcommand.
+
+    Args:
+        args: Parsed namespace with ``date: str``.
+            Uses ``duration=30`` and ``country=None`` as fixed defaults.
+
+    Returns:
+        0 on success; 1 on unhandled exception.
+    """
+    from ai_enterprise_workflow.forecasting.arima import model  # noqa: PLC0415
+
+    try:
+        result = model(args.date, 30, None)
+        print(json.dumps(result, default=str))
+        return 0
+    except Exception as exc:
+        print(f"Error: {exc}", file=sys.stderr)
+        return 1
+
+
+# ── predict ───────────────────────────────────────────────────────────────────
+
+
+def setup_predict(subparsers: argparse._SubParsersAction[ArgumentParser]) -> None:
+    """Register the 'predict' subcommand parser.
+
+    Args:
+        subparsers: The subparser action group to add the 'predict' command to.
+    """
+    parser = subparsers.add_parser(
+        "predict", help="Generate ARIMA/SARIMA forecasts."
+    )
+    parser.add_argument(
+        "--date",
+        required=True,
+        help="Reference date (YYYY-MM-DD) for the forecast origin.",
+    )
+    parser.add_argument(
+        "--duration",
+        type=int,
+        default=30,
+        help="Number of days to forecast (default: 30).",
+    )
+    parser.add_argument(
+        "--country",
+        default=None,
+        help="Country name filter; omit for global totals.",
+    )
+    parser.set_defaults(func=execute_predict)
+
+
+def execute_predict(args: Namespace) -> int:
+    """Execute the predict subcommand.
+
+    Args:
+        args: Parsed namespace with ``date: str``, ``duration: int``,
+            ``country: str | None``.
+
+    Returns:
+        0 on success; 1 on unhandled exception.
+    """
+    from ai_enterprise_workflow.forecasting.arima import model  # noqa: PLC0415
+
+    try:
+        result = model(args.date, args.duration, args.country)
+        print(json.dumps(result, default=str))
+        return 0
+    except Exception as exc:
+        print(f"Error: {exc}", file=sys.stderr)
+        return 1
+
+
+# ── serve ─────────────────────────────────────────────────────────────────────
+
+
+def setup_serve(subparsers: argparse._SubParsersAction[ArgumentParser]) -> None:
+    """Register the 'serve' subcommand parser.
+
+    Args:
+        subparsers: The subparser action group to add the 'serve' command to.
+    """
+    parser = subparsers.add_parser("serve", help="Start the Flask development server.")
+    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0).")
+    parser.add_argument("--port", type=int, default=5000, help="Port number (default: 5000).")
+    parser.set_defaults(func=execute_serve)
+
+
+def execute_serve(args: Namespace) -> int:
+    """Execute the serve subcommand.
+
+    Args:
+        args: Parsed namespace with ``host: str`` and ``port: int``.
+
+    Returns:
+        0 on success; 1 on unhandled exception.
+    """
+    from ai_enterprise_workflow.service.api import app  # noqa: PLC0415
+
+    try:
+        app.run(host=args.host, port=args.port)
+        return 0
+    except Exception as exc:
+        print(f"Error: {exc}", file=sys.stderr)
+        return 1
+
+
+# ── entrypoint ────────────────────────────────────────────────────────────────
+
+
+def main() -> int:
+    """Parse arguments and dispatch to the appropriate subcommand executor.
+
+    Returns:
+        Process exit code: 0 = success, 1 = unhandled exception,
+        2 = argparse error (missing or invalid arguments).
+    """
+    parser = ArgumentParser(
+        prog="ai_enterprise_workflow",
+        description="AI Enterprise Workflow command-line interface.",
+    )
+    subparsers = parser.add_subparsers(title="subcommands", dest="subcommand")
+    setup_ingest(subparsers)
+    setup_train(subparsers)
+    setup_predict(subparsers)
+    setup_serve(subparsers)
+
+    args = parser.parse_args()
+    if args.subcommand is None:
+        parser.print_help()
+        return 2
+    return int(args.func(args))
+
+
+if __name__ == "__main__":
+    sys.exit(main())
```

---

### Diff 4 — `src/ai_enterprise_workflow/service/api.py`

*Phases D-1, D-2, D-3. Against **post-Slice-B** state (after manifest #7 is executed). Rationale: app factory (D2), readyz (D4), date/duration validation (D3).*

> **Important:** apply this diff to the `api.py` that results from applying manifest #7's Diff 7. The post-Slice-B file imports `cfg`, has `_read_log_events`, and returns JSON errors for 400/422.

```diff
--- a/src/ai_enterprise_workflow/service/api.py
+++ b/src/ai_enterprise_workflow/service/api.py
@@ -1,6 +1,7 @@
 """Flask REST API exposing the forecasting and logging endpoints."""

+import datetime
 import json
 import os
 from pathlib import Path
@@ -10,10 +11,7 @@ from flask.typing import ResponseReturnValue

 from ai_enterprise_workflow.core.config import cfg
 from ai_enterprise_workflow.forecasting.arima import model
-
-app = Flask(__name__)
-app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "0") == "1"

 # Module-level alias — patched in tests via monkeypatch.setattr
 DIRECTORY_LOGS: Path = cfg.directory_logs
@@ -xx,7 +xx,6 @@ def _read_log_events(
     ...


-@app.route("/healthz", methods=["GET"])
 def healthz() -> ResponseReturnValue:
     """Liveness probe endpoint.
@@ -xx,7 +xx,6 @@ def healthz() -> ResponseReturnValue:
     return jsonify({"status": "ok"})


-@app.route("/predict", methods=["POST"])
 def predict() -> ResponseReturnValue:
     """Run the ARIMA/SARIMA forecast for the given query parameters.
@@ -xx,6 +xx,13 @@ def predict() -> ResponseReturnValue:
     if "date" in request.args:
         date = request.args["date"]
     else:
         return jsonify({"error": "No date parameter was provided."}), 400
+    # ISO 8601 date validation
+    try:
+        datetime.date.fromisoformat(date)
+    except ValueError:
+        return jsonify({"error": f"Invalid date '{date}'. Expected YYYY-MM-DD."}), 422
     # Check country parameter in request
     country = request.args.get("country", None)
     # Check duration parameter in request
     if "duration" in request.args:
-        duration = request.args["duration"]
+        raw_duration = request.args["duration"]
         try:
-            duration = 30 if duration == "" else int(duration)
+            duration = 30 if raw_duration == "" else int(raw_duration)
         except ValueError:
-            return jsonify({"error": "duration must be an integer."}), 422
+            return jsonify({"error": "duration must be a positive integer."}), 422
+        if duration <= 0:
+            return jsonify({"error": "duration must be a positive integer."}), 422
     else:
         duration = 30
@@ -xx,7 +xx,6 @@ def predict() -> ResponseReturnValue:
     return jsonify({"data": result})


-@app.route("/logs", methods=["POST"])
 def logs() -> ResponseReturnValue:
     """Return the requested log events as JSON.
@@ -xx,3 +xx,47 @@ def logs() -> ResponseReturnValue:
     result = _read_log_events(DIRECTORY_LOGS, log_type)
     return jsonify({"data": result})
+
+
+def readyz() -> ResponseReturnValue:
+    """Readiness probe endpoint.
+
+    Returns:
+        JSON ``{"status": "ready"}`` with HTTP 200 when the ingested data
+        artefact is present; JSON ``{"status": "not ready",
+        "reason": "data not ingested"}`` with HTTP 503 otherwise.
+
+    Notes:
+        Checks for ``cfg.directory_output / "4 revenue_total.csv"`` — the
+        sentinel file written by the ingestion pipeline.
+    """
+    csv_path = cfg.directory_output / "4 revenue_total.csv"
+    if csv_path.exists():
+        return jsonify({"status": "ready"}), 200
+    return jsonify({"status": "not ready", "reason": "data not ingested"}), 503
+
+
+def create_app(config: dict[str, object] | None = None) -> Flask:
+    """Create and return a configured Flask application instance.
+
+    Args:
+        config: Optional mapping of Flask configuration overrides applied
+            after defaults (e.g. ``{"TESTING": True}``).
+
+    Returns:
+        Configured :class:`~flask.Flask` application with all routes
+        registered via :func:`~flask.Flask.add_url_rule`.
+    """
+    flask_app = Flask(__name__)
+    flask_app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "0") == "1"
+    if config:
+        flask_app.config.update(config)
+    flask_app.add_url_rule("/healthz", "healthz", healthz, methods=["GET"])
+    flask_app.add_url_rule("/predict", "predict", predict, methods=["POST"])
+    flask_app.add_url_rule("/logs", "logs", logs, methods=["POST"])
+    flask_app.add_url_rule("/readyz", "readyz", readyz, methods=["GET"])
+    return flask_app
+
+
+app: Flask = create_app()
```

---

### Diff 5 — `tests/service/test_api.py`

*Phase D-4. Add 5 new tests inside `TestUnit`. Against post-Slice-B state (after manifest #7 Diff 12 is applied).*

```diff
--- a/tests/service/test_api.py
+++ b/tests/service/test_api.py
@@ -1,6 +1,8 @@
 """Tests for the Flask REST API endpoints (service.api)."""

 from collections.abc import Generator
+from pathlib import Path
 from unittest.mock import patch

 import pytest
@@ -xx,6 +xx,7 @@ from hypothesis import strategies as st

 from ai_enterprise_workflow.service.api import app
+from ai_enterprise_workflow.core.config import cfg

 _MODEL_TARGET = "ai_enterprise_workflow.service.api.model"
 _READ_LOG_TARGET = "ai_enterprise_workflow.service.api._read_log_events"
@@ -xx,6 +xx,60 @@ class TestApi:

     @pytest.mark.unit
     class TestUnit:
+
+        def test_readyz_returns_ready_when_csv_exists(
+            self,
+            flask_client: FlaskClient,
+            tmp_path: Path,
+            monkeypatch: pytest.MonkeyPatch,
+        ) -> None:
+            """GET /readyz returns 200 when the sentinel CSV exists."""
+            (tmp_path / "4 revenue_total.csv").touch()
+            monkeypatch.setattr(cfg, "directory_output", tmp_path)
+            response = flask_client.get("/readyz")
+            assert response.status_code == 200
+            assert response.get_json() == {"status": "ready"}
+
+        def test_readyz_returns_503_when_csv_absent(
+            self,
+            flask_client: FlaskClient,
+            tmp_path: Path,
+            monkeypatch: pytest.MonkeyPatch,
+        ) -> None:
+            """GET /readyz returns 503 when the sentinel CSV is absent."""
+            monkeypatch.setattr(cfg, "directory_output", tmp_path)
+            response = flask_client.get("/readyz")
+            assert response.status_code == 503
+            assert response.get_json() == {
+                "status": "not ready",
+                "reason": "data not ingested",
+            }
+
+        def test_predict_invalid_date_returns_422(
+            self, flask_client: FlaskClient
+        ) -> None:
+            """POST /predict with non-ISO date returns HTTP 422."""
+            response = flask_client.post("/predict?date=not-a-date")
+            assert response.status_code == 422
+            assert "error" in response.get_json()
+
+        def test_predict_non_positive_duration_returns_422(
+            self, flask_client: FlaskClient
+        ) -> None:
+            """POST /predict with duration=0 returns HTTP 422."""
+            response = flask_client.post("/predict?date=2019-01-01&duration=0")
+            assert response.status_code == 422
+            assert response.get_json() == {"error": "duration must be a positive integer."}
+
+        def test_predict_non_integer_duration_returns_422(
+            self, flask_client: FlaskClient
+        ) -> None:
+            """POST /predict with non-integer duration returns HTTP 422."""
+            response = flask_client.post("/predict?date=2019-01-01&duration=abc")
+            assert response.status_code == 422
+            assert response.get_json() == {"error": "duration must be a positive integer."}
+
         def test_predict_with_country_returns_data_key(
```

---

## Failure playbook

| # | Symptom | Likely cause | Remediation | Escalate to |
|---|---------|--------------|-------------|-------------|
| 1 | `tach check` fails after Phase C-1 | Import added to `cli.py` that tach.toml doesn't declare | Verify `cli`'s `depends_on` was updated for both `ingestion` and `forecasting` | @LinterSpecialist |
| 2 | `pyright` reports `reportPrivateUsage` on `argparse._SubParsersAction` | Pyright strict flagging private argparse type | Add `# type: ignore[reportPrivateUsage]` on the function signature lines | @LinterSpecialist |
| 3 | `uv run ai_enterprise_workflow` fails after `uv pip install -e .` | `[project.scripts]` not picked up by editable install | Run `uv sync && uv pip install -e .` again; verify `which ai_enterprise_workflow` resolves | @LinterSpecialist |
| 4 | `POST /readyz` test fails — `AttributeError: can't set attribute` | `cfg` is a frozen Pydantic model | In `AppSettings`, set `model_config = ConfigDict(frozen=False)`; or patch the module-level alias: `monkeypatch.setattr("ai_enterprise_workflow.service.api.cfg", tmp_cfg)` | @CodeReviewer |
| 5 | Existing tests fail after Phase D-1 app factory change | `@app.route` decorator still present on one of the view functions (mixed state) | Verify all three `@app.route` decorators are removed; all routes registered via `add_url_rule` in `create_app` | @CodeReviewer |
| 6 | `test_predict_any_valid_duration_returns_data_key` fails after Phase D-3 | Duration `<= 0` guard inadvertently rejecting valid durations | Hypothesis uses `min_value=1`; failure indicates logic error in guard. Check `if duration <= 0` is after successful `int()` parse | @TestDesigner |
| 7 | `ruff` reports `PLC0415` on lazy imports in `cli.py` | Ruff enabled `PLC0415` (import not at top of file) | Rule is `PLC0415`. The `# noqa: PLC0415` comments in Diff 3 suppress this per-import; verify they are present | @LinterSpecialist |
| 8 | `execute_serve` causes test hang | `app.run()` is a blocking call | `execute_serve` must be mocked in tests; never call it without `mock.patch` | @TestDesigner |

---

## Roadmap

| # | Phase | Owner | Status | Evidence / Notes |
|---|-------|-------|--------|------------------|
| 1 | Phase C-1 — tach + pyproject | @ProjectDeveloper → @LinterSpecialist | done | tach ✅; entrypoint registered |
| 2 | Phase C-2 — cli.py rewrite | @ProjectDeveloper → @CodeReviewer, @LinterSpecialist | done | ruff ✅; pyright 0 errors; tach ✅; --help OK |
| 3 | Phase D-1 — App factory | @ProjectDeveloper → @CodeReviewer | done | create_app + app=create_app() ✅; 9 existing tests pass |
| 4 | Phase D-2 — /readyz endpoint | @ProjectDeveloper → @TestDesigner | done | readyz() registered; smoke test ✅ |
| 5 | Phase D-3 — /predict 422 validation | @ProjectDeveloper → @LinterSpecialist | done | date fromisoformat + duration≤0 guard ✅; pyright 0 errors |
| 6 | Phase D-4 — New tests | @ProjectDeveloper → @TestDesigner | done | 14/14 tests pass (5 new) |
| 7 | Documentation pass | @DocsReviewer | done | Examples+Notes added to 11 functions; ruff ✅ |
| 8 | Integration gate | @IntegrationChecker (`docs_mode=skip`) | done | G0-G6 all ✅; 26/26 tests |
| 9 | MR preparation | @ProjectDeveloper | done | PR #12 → develop; merged 2026-05-16T15:08:05Z |

**Effort summary:** S×4, M×1 — total complexity: Small-Medium. No XL phases.

---

## Acceptance criteria (mirror)

*Mirrored verbatim from GitHub issue #8.*

- [ ] `uv run ai_enterprise_workflow ingest --force` calls `pipeline.ingest(force=True)` and exits 0.
- [ ] `uv run ai_enterprise_workflow predict --date 2019-01-01 --duration 30 --country Australia` calls `arima.model("2019-01-01", 30, "Australia")` and exits 0.
- [ ] `uv run ai_enterprise_workflow train --date 2019-01-01` calls `arima.model("2019-01-01", 30, None)` and exits 0.
- [ ] `uv run ai_enterprise_workflow serve --host 127.0.0.1 --port 8080` calls `app.run(host="127.0.0.1", port=8080)`.
- [ ] Calling `main()` with no recognized subcommand returns non-zero exit code without raising.
- [ ] `GET /readyz` returns `{"status": "ready"} 200` when `cfg.directory_output / "4 revenue_total.csv"` exists.
- [ ] `GET /readyz` returns `{"status": "not ready", "reason": "data not ingested"} 503` otherwise.
- [ ] `POST /predict?date=not-a-date` returns `{"error": "..."}` HTTP 422.
- [ ] `POST /predict?date=2019-01-01&duration=-1` returns `{"error": "..."}` HTTP 422.
- [ ] `POST /predict?date=2019-01-01&duration=abc` returns `{"error": "..."}` HTTP 422.
- [ ] All existing `tests/service/test_api.py` tests pass unmodified.
- [ ] `uv run tach check`, `uv run pyright src/`, `uv run ruff check src/` all exit 0.
- [ ] `PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/ -q` exits 0.

---

## Handover

**Design phase complete.** The floor is handed over to `@ProjectDeveloper`.

This manifest was authored by a reasoning-class model with the explicit assumption that `@ProjectDeveloper` is an execution-class model. All non-trivial design decisions are pre-resolved in `## Decisions log`; all phase-level instructions are encoded as `#### Execution recipe` sub-blocks; predictable failure modes are covered in `## Failure playbook`. **Do not re-derive design choices.**

`@ProjectDeveloper` must:

1. Treat this manifest as the single source of truth.
2. Read `## Execution context` before starting and verify every precondition — especially that issue #7 is merged before Phase D-1.
3. Execute phases sequentially. For each phase: flip the roadmap row to `in-progress`, run the `Execution recipe` literally, apply the referenced `Proposed diffs` exactly as drafted, run the listed validation commands, then flip the row to `done`.
4. Diff 4 (api.py) is against **post-Slice-B** state. Do not apply it to the current file; apply it after issue #7 is merged.
5. On any predictable failure, consult `## Failure playbook` first.
6. After the last code phase, hand over to `@DocsReviewer`, then to `@IntegrationChecker` with `docs_mode=skip`.
7. Verify every box in `Acceptance criteria (mirror)` is checked before preparing the MR.

To start: `@ProjectDeveloper execute manifests/8-cli-wiring-service-hardening.md`.
To finalize after merge: `@ProjectDeveloper finalize manifests/8-cli-wiring-service-hardening.md`.

---

## Manifest changelog

| Date (UTC) | Agent | Change |
|---|---|---|
| 2026-05-16T12:00:00Z | @IssueTracker | Initial scaffold — issue #8, branch created, manifest bootstrapped |
| 2026-05-16T12:30:00Z | @ProjectArchitect | Added Execution context, Decisions log (D1–D5), Detailed action plan (Phases C-1, C-2, D-1–D-4 with effort tags and Execution recipes), Proposed diffs (Diffs 1–5), Failure playbook, Roadmap, Acceptance criteria mirror, Handover. |
| 2026-05-16 | @ProjectDeveloper | Executed phases C-1–D-4; DocsReviewer pass; IntegrationChecker GO (G0–G6); 5 split commits pushed; opened PR #12 targeting develop; lock released. |
| 2026-05-16 | @ProjectDeveloper | Stage 7 finalization: PR #12 merged at 2026-05-16T15:08:05Z (verified via gh CLI); status set to done; local branch deleted. |
