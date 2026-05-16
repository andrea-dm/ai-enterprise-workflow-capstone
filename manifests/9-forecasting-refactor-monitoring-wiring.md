---
manifest_version: 1
branch: 9-forecasting-refactor-monitoring-wiring
issue: 9
issue_url: https://github.com/andrea-dm/ai-enterprise-workflow-capstone/issues/9
scope: "forecasting, monitoring, service, core"
tests: "tests/forecasting/test_arima.py, tests/service/test_api.py"
affects:
  - ai_enterprise_workflow.service.api
  - ai_enterprise_workflow.forecasting.arima
  - ai_enterprise_workflow.monitoring.drift
  - ai_enterprise_workflow.core.config
lock: null
mr: "#13"
mr_url: https://github.com/andrea-dm/ai-enterprise-workflow-capstone/pull/13
status: in-review
---

# decompose forecasting model and wire drift monitoring

## Current state

### `forecasting/arima.py`

| Symbol | Issue |
|---|---|
| `model()` | `# noqa: PLR0912` suppression — 12+ branches, monolithic body |
| `train_ARIMA_model` | PEP-8 violation (`ARIMA` not snake_case) |
| `train_SARIMA_model` | PEP-8 violation (`SARIMA` not snake_case) |

Public API surface (relevant symbols):

```python
def get_revenue_country(revenue: pd.DataFrame, country: str) -> pd.DataFrame: ...
def train_ARIMA_model(data, order, directory_models, country=None) -> Any: ...
def train_SARIMA_model(data, order, seasonal_order, directory_models, country=None) -> Any: ...
def predict(model, name, start, end, actual=None) -> tuple[Any, Any]: ...
def model(date: str, duration: int = 30, country: str | None = None) -> dict[str, Any]: ...  # noqa: PLR0912
```

Return dict of `model()` today: `{"arima": float, "sarima": float}` — no drift key.

### `monitoring/drift.py`

| Symbol | Issue |
|---|---|
| `get_wasserstain_distance` | Typo in public name (`wasserstain` → `wasserstein`) |
| _(no callers)_ | Module is an orphan — never imported by any other module |

### `core/config.py`

Plain module-level constants only; no `AppSettings` dataclass or `drift_threshold` field exists.

### `tach.toml`

`ai_enterprise_workflow.forecasting.depends_on` does **not** include `ai_enterprise_workflow.monitoring`; any import from `forecasting` → `monitoring` would currently fail `tach check`.

### `service/api.py`

`/predict` response today: `{"data": {"arima": float, "sarima": float}}` — no `drift_warning` key.

---

## Specification

### Renamed public symbols (`forecasting/arima.py`)

| Old name | New name | Signature change |
|---|---|---|
| `train_ARIMA_model` | `train_arima_model` | None — identical parameters and return type |
| `train_SARIMA_model` | `train_sarima_model` | None — identical parameters and return type |

All internal call-sites inside `arima.py` must be updated to the new names.

### New private helpers (`forecasting/arima.py`)

| Symbol | Responsibility |
|---|---|
| `_load_or_train(kind, revenue_series, order, seasonal_order, directory_models, country)` | Load a pickled model if the file exists; otherwise call `train_arima_model` or `train_sarima_model` and return the fitted instance. Eliminates the duplicated `if os.path.exists / else train_*` blocks for both country and global paths. |
| `_resolve_revenue(country, revenue_countries, revenue_total)` | Return `(revenue_df, file_suffix)` selecting the right DataFrame and file-suffix string based on whether `country` is `None`. |
| `_run_predictions(arima_model, sarima_model, revenue, date, duration, file_suffix)` | Execute `predict()` calls, reindex, write predictions CSV, return `(arima_result, sarima_result, revenue_array_for_drift)`. |

`model()` body after refactor becomes the orchestration entry-point only — no branches beyond calling the three helpers. The `# noqa: PLR0912` suppression is removed.

### `model()` return dict

```python
{
    "arima":  float,   # existing key
    "sarima": float,   # existing key
    "drift":  float,   # NEW — Wasserstein distance score
}
```

### `monitoring/drift.py`

Rename `get_wasserstain_distance` → `get_wasserstein_distance`. No behavioral change; only the symbol name changes.

### `core/config.py` — `AppSettings`

Add a typed `AppSettings` dataclass (or `pydantic.BaseModel` consistent with the pattern established in issue #7):

```python
@dataclass
class AppSettings:
    drift_threshold: float = 0.1
    # … other fields migrated from module constants as needed by this slice
```

Accessible as `cfg = AppSettings()` (or via the settings singleton if issue #7 introduced one). `cfg.drift_threshold` must be `float`.

### `tach.toml` — dependency update

```toml
[[modules]]
path = "ai_enterprise_workflow.forecasting"
depends_on = [
    "ai_enterprise_workflow.core",
    "ai_enterprise_workflow.ingestion",
    "ai_enterprise_workflow.monitoring",   # NEW
]
```

### `service/api.py` — `/predict` response

```python
result = model(date, duration, country)
drift_warning = result.get("drift", 0.0) > cfg.drift_threshold
return jsonify({"data": result, "drift_warning": drift_warning})
```

Response schema:

```json
{
  "data": {"arima": 1.23, "sarima": 1.45, "drift": 0.07},
  "drift_warning": false
}
```

---

## Implementation plan

### Phase E-1 — Rename `train_*` symbols

1. In `forecasting/arima.py`: rename `train_ARIMA_model` → `train_arima_model` and `train_SARIMA_model` → `train_sarima_model`.
2. Update all internal call-sites in `model()`.
3. Update mocks in `tests/forecasting/test_arima.py`.
4. Verify: `uv run ruff check src/` — no `N802` or similar naming violations.

### Phase E-2 — Extract private helpers

1. Introduce `_resolve_revenue`, `_load_or_train`, `_run_predictions` as module-private functions.
2. Rewrite `model()` to delegate to the three helpers; remove all internal `if/else` branches.
3. Remove the `# noqa: PLR0912` comment.
4. Verify: `uv run ruff check src/` passes; branch count in `model()` ≤ 3.

### Phase F-1 — Fix typo in `monitoring/drift.py`

1. Rename `get_wasserstain_distance` → `get_wasserstein_distance`.
2. Search entire codebase for any existing call-sites (notebooks, tests) and update them.
3. Verify: `uv run ruff check src/` passes; `uv run pyright src/` passes.

### Phase F-2 — Update `tach.toml`

1. Add `"ai_enterprise_workflow.monitoring"` to `forecasting`'s `depends_on` list.
2. Verify: `uv run tach check` exits 0.

### Phase F-3 — Add `drift_threshold` to `AppSettings` in `core/config.py`

1. Introduce (or extend) `AppSettings` with `drift_threshold: float = 0.1`.
2. Expose a module-level `settings` singleton if one was established in issue #7, otherwise create a local instance used by `model()` and `api.py`.
3. Verify: `uv run pyright src/` passes in strict mode.

### Phase F-4 — Wire drift into `arima.py`

1. Import `get_wasserstein_distance` from `monitoring.drift` and `AppSettings` from `core.config`.
2. Inside `_run_predictions` (or `model()`), call `get_wasserstein_distance` on the revenue array after predictions are computed.
3. Include `"drift": float(score)` in the returned dict.
4. Verify: `model()` return type annotation updated; `uv run pyright src/` passes.

### Phase F-5 — Surface `drift_warning` in `service/api.py`

1. Import settings and compute `drift_warning = result.get("drift", 0.0) > cfg.drift_threshold`.
2. Add `"drift_warning"` key to the `jsonify` response dict.
3. Verify: `tests/service/test_api.py` stubs updated to include `"drift"` key in mock return value; `"drift_warning"` present in response JSON assertions.

### Phase F-6 — Update test mocks

1. `tests/forecasting/test_arima.py`: update all patches/mocks from `train_ARIMA_model`/`train_SARIMA_model` to new snake_case names.
2. `tests/service/test_api.py`: update mock return value of `model` to include `"drift": 0.05`.
3. Assert `"drift_warning"` is present and is a `bool` in `/predict` response.
4. Verify: `PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/ -q` exits 0.

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Lambda / closure capture in `_load_or_train` — loop variable captured by reference if helpers are constructed in a loop | Low | Medium | Use explicit parameter defaults (`kind=kind`) in any lambda or default-arg closure; prefer a straightforward `if kind == "arima"` branch inside the helper |
| NumPy dtype casting — `get_wasserstein_distance` returns `np.floating[Any]`; storing in dict typed as `dict[str, float]` may fail Pyright strict | Medium | Low | Cast explicitly: `"drift": float(score)` at the call-site |
| Latency budget — `get_wasserstein_distance` runs 1 000 bootstrap iterations by default; calling it on every `/predict` request adds ~50–200 ms | Medium | Medium | Pass a smaller `batch_size` (e.g., 200) via `AppSettings.drift_batch_size`; or run detection async/post-hoc |
| External callers of `train_ARIMA_model` / `train_SARIMA_model` in notebooks (`nb/`) | Low | Low | `grep` the `nb/` directory before merging; update any notebook call-sites |
| `_resolve_revenue` indirectly calls `ingest()` (via the `model()` orchestration path) in integration tests — may hit filesystem | Low | Medium | Existing tests already mock `ingest`; verify all mock patches cover the new call path through `_run_predictions` |
| Slice A / issue #7 dependency ordering — `AppSettings` may already be partially defined in #7; merging out-of-order will create a conflict | Medium | Medium | Rebase this branch onto the merged `develop` after #7 lands; coordinate with `@ProjectDeveloper` before opening MR |

---

## Execution context

- **Working directory:** repo root (`/home/azureuser/cloudfiles/code/Users/andrea.del_monaco/capstone`)
- **Active branch:** `9-forecasting-refactor-monitoring-wiring`
- **Base branch:** `develop`
- **Python version:** 3.12
- **Validation commands:**
  ```bash
  uv run ruff check src/ tests/
  uv run ruff format --check src/ tests/
  uv run pyright src/
  uv run tach check
  PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/ -q
  PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/forecasting/ -v -m "not slow"
  ```
- **Tooling preconditions:**
  - Issue #7 (`7-upgrade-core-foundation-typed-config-stdlib-logging-security`) **must be merged** before any phase. This provides `cfg: AppSettings`, `load_pickle`, and `Path`-typed signatures in `arima.py`.
  - Run `git rebase origin/develop` after #7 merges, before starting Phase E-1.
  - Pre-check notebooks: `grep -r "train_ARIMA_model\|train_SARIMA_model\|get_wasserstain_distance" nb/` — update any call-sites before Phase E-1 / F-1.
  - `batch_size=200` is chosen for latency; this is configurable via `AppSettings.drift_batch_size` in future but hard-coded here per scope.

- **Files in scope (allow-list):**
  | File | Action |
  |---|---|
  | `src/ai_enterprise_workflow/forecasting/arima.py` | rename + helpers + drift (post-Slice-A state) |
  | `src/ai_enterprise_workflow/monitoring/drift.py` | typo fix only |
  | `tach.toml` | add `monitoring` to `forecasting` deps |
  | `src/ai_enterprise_workflow/core/config.py` | add `drift_threshold` field (post-Slice-A state) |
  | `src/ai_enterprise_workflow/service/api.py` | add `drift_warning` (post-Slice-B state) |
  | `tests/service/test_api.py` | update mock return values |
  | `tests/forecasting/test_arima.py` | no changes needed (integration tests test `model()` as black box; `"drift"` key does not break them) |

- **Files explicitly out of scope:**
  - `src/ai_enterprise_workflow/ingestion/` — no changes
  - `src/ai_enterprise_workflow/cli.py` — no changes
  - `Dockerfile`, `run.py`, `nb/` (only grep, no edits)

---

## Decisions log

### D1 — `_load_or_train` signature: generic `Callable[[], Any]` pattern
- **Chosen:** `_load_or_train(model_path: Path, train_fn: Callable[[], Any]) -> Any` — the caller passes a zero-arg lambda that captures training arguments — reflected in Diff 1.
- **Rejected:**
  - `_load_or_train(kind, revenue_series, order, seasonal_order, directory_models, country)` (IssueTracker scaffold) — ARIMA-specific params; not reusable and does not reduce complexity.
  - Duplicated `if path.exists() / else train()` inline — current state, exactly what PLR0912 is about.
- **Rationale:** Generic helper with a `Callable` eliminates 8 lines of duplicated code across 4 load-or-train call sites. Lambda captures training args via default-argument binding (see D2) to avoid closure bug.
- **Locked:** yes.

### D2 — Lambda closure capture: default-argument binding
- **Chosen:** Capture `country` via default argument: `lambda c=country: train_arima_model(..., c)` — reflected in Diff 1.
- **Rejected:** `lambda: train_arima_model(..., country)` — Python late-binding closure; if `country` is mutated between lambda definition and call, wrong value is captured. Although no mutation occurs in the current code, the explicit default binding is safer and passes strict Pyright.
- **Rationale:** Standard Python pattern for closure safety in lambda factory functions.
- **Locked:** yes.

### D3 — `_resolve_revenue` return type: `tuple[pd.DataFrame, str]`
- **Chosen:** `-> tuple[pd.DataFrame, str]` where the second element is the file suffix (`""` for totals, `"_<country>"` for country slice) — reflected in Diff 1.
- **Rejected:** `-> pd.DataFrame` only with suffix as a side-effect — forces `model()` to re-derive the suffix.
- **Rationale:** The suffix is determined by the same conditional that selects the DataFrame; returning both avoids the `if country` branch repeating in `_run_predictions`.
- **Locked:** yes.

### D4 — Revenue array for drift: capture before reindexing
- **Chosen:** Capture `revenue_array = revenue["revenue"].to_numpy().astype(np.float64).reshape(-1, 1)` **before** the `reindex` call inside `_run_predictions` — reflected in Diff 1.
- **Rejected:** Use post-reindex revenue (contains NaN in forecast window) — NaN values propagate into `wasserstein_distance` computation causing `nan` result.
- **Rationale:** Drift should measure the distribution of actual historical data, not the extended forecast window.
- **Locked:** yes.

### D5 — `drift_threshold` as new `AppSettings` field
- **Chosen:** Add `drift_threshold: float = Field(default=0.1, validation_alias="DRIFT_THRESHOLD")` to `AppSettings` in `core/config.py` (post-Slice-A) — reflected in Diff 4.
- **Rejected:** Module-level constant in `monitoring/drift.py` — drift threshold is service-level config, not a module constant; it belongs with other runtime-configurable fields in `AppSettings`.
- **Rationale:** Consistent with Slice A's pattern: all threshold/config values live in `AppSettings`.
- **Locked:** yes.

### D6 — Drift integration point: inside `_run_predictions`, returned in dict
- **Chosen:** Compute drift score inside `_run_predictions`, add `"drift": float(score)` to returned dict. `api.py` reads `result["drift"]` for `drift_warning` — reflected in Diffs 1 and 5.
- **Rejected:**
  - Compute drift in `api.py` — `api.py` does not have access to the revenue data; would require returning it from `model()` separately.
  - Async drift — out of scope; adds complexity (threading, asyncio).
- **Rationale:** `_run_predictions` has access to both the revenue array and the prediction results; it is the natural integration point.
- **Locked:** yes.

---

## Detailed action plan

### Phase E-1 — Rename `train_ARIMA_model` and `train_SARIMA_model`  `[effort: S]`  `[mandatory: @LinterSpecialist]`

Rename the two PEP-8-violating public functions and update all 4 internal call sites.

#### Execution recipe

1. **Pre-checks.** Issue #7 merged; `git rebase origin/develop`. `from ai_enterprise_workflow.forecasting.arima import model` exits 0. `grep -n "train_ARIMA_model\|train_SARIMA_model" src/ nb/ -r` — note all found locations.
2. **Apply diffs.** Apply hunk A of **Diff 1 — `src/ai_enterprise_workflow/forecasting/arima.py`** (rename only; no helper extraction yet).
3. **Post-edit.** `uv run ruff format src/ai_enterprise_workflow/forecasting/arima.py`
4. **Validation.**
   ```bash
   uv run ruff check src/ai_enterprise_workflow/forecasting/arima.py
   uv run pyright src/ai_enterprise_workflow/forecasting/arima.py
   PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/forecasting/ -q -m "not slow"
   ```
5. **Definition of Done.**
   - [ ] `train_ARIMA_model` absent from `arima.py`; `train_arima_model` present
   - [ ] `train_SARIMA_model` absent; `train_sarima_model` present
   - [ ] All 4 internal call sites in `model()` updated
   - [ ] `ruff check` 0 errors (no N802)
6. **Delegation directives.** `@LinterSpecialist`: *"Run `uv run ruff check src/ai_enterprise_workflow/forecasting/arima.py`. Confirm no `N802` violations remain. Attach output."*
7. **Stop conditions.** Stop if `forecasting/__init__.py` or any notebook re-exports the old names — update those first.

---

### Phase E-2 — Extract `_load_or_train`, `_resolve_revenue`, `_run_predictions`  `[effort: M]`  `[mandatory: @CodeReviewer, @LinterSpecialist]`

Decompose `model()` into three private helpers. Remove `# noqa: PLR0912`.

#### Execution recipe

1. **Pre-checks.** Phase E-1 complete. All non-slow tests pass.
2. **Apply diffs.** Apply hunk B of **Diff 1** (helper extraction + simplified `model()` body).
3. **Post-edit.** `uv run ruff format src/ai_enterprise_workflow/forecasting/arima.py`
4. **Validation.**
   ```bash
   uv run ruff check src/ai_enterprise_workflow/forecasting/arima.py
   uv run pyright src/ai_enterprise_workflow/forecasting/arima.py
   PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/forecasting/ -v
   ```
   Expected: both integration tests pass (including slow ones if time allows).
5. **Definition of Done.**
   - [ ] `_load_or_train`, `_resolve_revenue`, `_run_predictions` present in `arima.py`
   - [ ] `model()` body has no `# noqa: PLR0912`
   - [ ] `model()` has ≤3 branches (max complexity ≤ 10)
   - [ ] `pyright` 0 errors; `ruff check` 0 errors
   - [ ] Integration tests pass
6. **Delegation directives.** `@CodeReviewer`: *"Review `_load_or_train` — verify lambda closure uses default-arg binding (`lambda c=country: ...`). Review `_resolve_revenue` return type `tuple[pd.DataFrame, str]`. Review `_run_predictions` drift array capture (before reindex). Attach file."*
7. **Stop conditions.** Halt if `pyright` reports `reportUnknownVariableType` on lambda return. Use explicit `Callable[[], Any]` annotation.

---

### Phase F-1 — Fix `get_wasserstain_distance` typo  `[effort: S]`  `[mandatory: @LinterSpecialist]`

Single symbol rename in `monitoring/drift.py`.

#### Execution recipe

1. **Pre-checks.** `grep -rn "get_wasserstain_distance" src/ tests/ nb/` — note all locations.
2. **Apply diffs.** Apply **Diff 2 — `src/ai_enterprise_workflow/monitoring/drift.py`**.
3. **Post-edit.** `uv run ruff format src/ai_enterprise_workflow/monitoring/drift.py`
4. **Validation.**
   ```bash
   uv run ruff check src/ai_enterprise_workflow/monitoring/drift.py
   uv run pyright src/ai_enterprise_workflow/monitoring/drift.py
   grep -rn "get_wasserstain_distance" src/ tests/  # must return 0 results
   ```
5. **Definition of Done.**
   - [ ] `get_wasserstain_distance` absent; `get_wasserstein_distance` present
   - [ ] `pyright` 0 errors; `ruff check` 0 errors
6. **Delegation directives.** None required.
7. **Stop conditions.** None.

---

### Phase F-2 — Update `tach.toml`  `[effort: S]`  `[mandatory: @LinterSpecialist]`

Add `monitoring` to `forecasting`'s `depends_on`.

#### Execution recipe

1. **Pre-checks.** Phase F-1 complete.
2. **Apply diffs.** Apply **Diff 3 — `tach.toml`**.
3. **Validation.** `uv run tach check`
4. **Definition of Done.**
   - [ ] `tach check` exits 0
   - [ ] `ai_enterprise_workflow.monitoring` in `forecasting`'s `depends_on`
5. **Delegation directives.** `@LinterSpecialist`: *"Run `uv run tach check`. Confirm no new violations. Attach output."*
6. **Stop conditions.** Stop if tach reports a cycle. Escalate to @CodeReviewer.

---

### Phase F-3 — Add `drift_threshold` to `AppSettings`  `[effort: S]`  `[mandatory: @LinterSpecialist]`

**Dependency:** Issue #7 merged (provides `AppSettings(BaseSettings)` in `core/config.py`).

Add one new field to the existing `AppSettings` class.

#### Execution recipe

1. **Pre-checks.** `from ai_enterprise_workflow.core.config import cfg; print(cfg.drift_threshold)` — expected: `AttributeError` (field not yet added).
2. **Apply diffs.** Apply **Diff 4 — `src/ai_enterprise_workflow/core/config.py`** (one-field addition).
3. **Validation.**
   ```bash
   uv run pyright src/ai_enterprise_workflow/core/config.py
   PYTHONPATH=src /anaconda/envs/ai/bin/python -c "from ai_enterprise_workflow.core.config import cfg; assert cfg.drift_threshold == 0.1"
   ```
4. **Definition of Done.**
   - [ ] `cfg.drift_threshold == 0.1` (default)
   - [ ] `DRIFT_THRESHOLD=0.05 python -c "from ai_enterprise_workflow.core.config import cfg; assert cfg.drift_threshold == 0.05"` exits 0
   - [ ] `pyright` 0 errors
5. **Delegation directives.** None required.
6. **Stop conditions.** Stop if `AppSettings` is not yet present (issue #7 not merged).

---

### Phase F-4 — Wire drift into `arima.py`  `[effort: S]`  `[mandatory: @CodeReviewer]`

**Dependency:** Phase E-2 and Phase F-2 complete.

Import `get_wasserstein_distance` and integrate into `_run_predictions`.

#### Execution recipe

1. **Pre-checks.** `uv run tach check` exits 0 (F-2 complete). Phase E-2 complete.
2. **Apply diffs.** Apply hunk C of **Diff 1** (drift import + drift computation in `_run_predictions`).
3. **Post-edit.** `uv run ruff format src/ai_enterprise_workflow/forecasting/arima.py`
4. **Validation.**
   ```bash
   uv run ruff check src/ai_enterprise_workflow/forecasting/arima.py
   uv run pyright src/ai_enterprise_workflow/forecasting/arima.py
   PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/forecasting/ -q -m "not slow"
   ```
5. **Definition of Done.**
   - [ ] `"drift"` key present in `model()` return dict
   - [ ] `type(result["drift"]) == float` (not `np.floating`)
   - [ ] Integration tests: `"arima" in result` and `"sarima" in result` still pass
6. **Delegation directives.** `@CodeReviewer`: *"Review drift array construction: `revenue['revenue'].to_numpy().astype(np.float64).reshape(-1, 1)` before reindex. Verify `float()` cast on `np.floating` result. Confirm `batch_size=200` is correctly passed."*
7. **Stop conditions.** Stop if `pyright` reports `reportArgumentType` on the numpy array passed to `get_wasserstein_distance`. Add `npt.NDArray[np.floating[Any]]` cast.

---

### Phase F-5 — Surface `drift_warning` in `/predict` response  `[effort: S]`  `[mandatory: @LinterSpecialist]`

**Dependency:** Phase F-3 complete.

Add `drift_warning` to the `/predict` JSON response.

#### Execution recipe

1. **Pre-checks.** `cfg.drift_threshold` accessible.
2. **Apply diffs.** Apply **Diff 5 — `src/ai_enterprise_workflow/service/api.py`**.
3. **Post-edit.** `uv run ruff format src/ai_enterprise_workflow/service/api.py`
4. **Validation.** `uv run ruff check src/ai_enterprise_workflow/service/api.py && uv run pyright src/ai_enterprise_workflow/service/api.py`
5. **Definition of Done.**
   - [ ] `/predict` response JSON has top-level `"drift_warning"` boolean key
   - [ ] `pyright` 0 errors
6. **Delegation directives.** None required.
7. **Stop conditions.** Stop if `result["drift"]` raises `KeyError` — Phase F-4 not yet complete.

---

### Phase F-6 — Update test mocks  `[effort: S]`  `[mandatory: @TestDesigner]`

Update 4 mock call sites in `test_api.py` to include `"drift": 0.05`.

#### Execution recipe

1. **Pre-checks.** Phase F-5 complete.
2. **Apply diffs.** Apply **Diff 6 — `tests/service/test_api.py`**.
3. **Post-edit.** `uv run ruff format tests/service/test_api.py`
4. **Validation.**
   ```bash
   PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/service/ -v
   PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/ -q
   ```
5. **Definition of Done.**
   - [ ] All existing tests pass
   - [ ] `"drift_warning"` key present in `/predict` mock-response tests
   - [ ] Full `pytest tests/ -q` exits 0
6. **Delegation directives.** `@TestDesigner`: *"Review `tests/service/test_api.py` — confirm all 4 mock return values include `'drift': 0.05`; confirm Hypothesis test also updated. Attach `pytest -v` output."*
7. **Stop conditions.** Halt if `KeyError: 'drift'` appears in test output — Phase F-4 incomplete.

---

## Proposed diffs

### Diff 1 — `src/ai_enterprise_workflow/forecasting/arima.py`

*Phases E-1, E-2, F-4. Against **post-Slice-A** state (after manifest #7 is executed). The file uses `pathlib.Path`, `load_pickle`, and `cfg` at that point.*

> **Important:** apply against the `arima.py` resulting from manifest #7's Diff 6.

**Hunk A (Phase E-1) — rename `train_ARIMA_model` and `train_SARIMA_model`:**

```diff
--- a/src/ai_enterprise_workflow/forecasting/arima.py
+++ b/src/ai_enterprise_workflow/forecasting/arima.py
@@ -1,6 +1,8 @@
 """ARIMA and SARIMA forecasting models for revenue prediction."""

 from __future__ import annotations

 from pathlib import Path
 from typing import Any
+from collections.abc import Callable

 import pandas as pd
+import numpy as np
+import numpy.typing as npt
 from statsmodels.iolib.smpickle import load_pickle  # type: ignore[import-untyped]
@@ -38,7 +40,7 @@ def get_revenue_country(revenue: pd.DataFrame, country: str) -> pd.DataFrame:


-def train_ARIMA_model(
+def train_arima_model(
     data: pd.Series[float],
     order: tuple[int, int, int],
     directory_models: Path,
     country: str | None = None,
 ) -> Any:
@@ -65,7 +67,7 @@ def train_ARIMA_model(


-def train_SARIMA_model(
+def train_sarima_model(
     data: pd.Series[float],
     order: tuple[int, int, int],
     seasonal_order: tuple[int, int, int, int],
     directory_models: Path,
     country: str | None = None,
 ) -> Any:
```

**Hunk B (Phase E-2) — extract private helpers + simplify `model()`:**

```diff
--- a/src/ai_enterprise_workflow/forecasting/arima.py
+++ b/src/ai_enterprise_workflow/forecasting/arima.py
@@ -xx,0 +xx,90 @@ def predict(
     ...


+def _load_or_train(model_path: Path, train_fn: Callable[[], Any]) -> Any:
+    """Load a persisted model or train a fresh one if the file is absent.
+
+    Args:
+        model_path: Filesystem path to the pickled model file.
+        train_fn: Zero-argument callable that trains and persists the model,
+            returning the fitted model instance.
+
+    Returns:
+        Loaded or freshly trained model instance.
+    """
+    if model_path.exists():
+        return load_pickle(str(model_path))
+    return train_fn()
+
+
+def _resolve_revenue(
+    date: str,
+    country: str | None,
+    output_dir: Path,
+) -> tuple[pd.DataFrame, str]:
+    """Resolve the revenue DataFrame and filename suffix for a given country.
+
+    Args:
+        date: Forecast origin date string (unused here; kept for caller
+            symmetry).
+        country: Country name filter, or ``None`` for global totals.
+        output_dir: Directory containing the pipeline output CSVs.
+
+    Returns:
+        A 2-tuple of ``(revenue_df, file_suffix)`` where ``file_suffix``
+        is ``""`` for totals or ``"_<country>"`` for a country slice.
+    """
+    if not (output_dir / "4 revenue_total.csv").exists():
+        ingest()
+    revenue_countries = pd.read_csv(output_dir / "3 revenue_country.csv")
+    revenue_total = pd.read_csv(output_dir / "4 revenue_total.csv")
+    if country:
+        revenue = get_revenue_country(revenue_countries, country)
+        return revenue, f"_{country}"
+    return revenue_total, ""
+
+
+def _run_predictions(
+    revenue: pd.DataFrame,
+    date: str,
+    duration: int,
+    directory_models: Path,
+    file_suffix: str,
+) -> dict[str, Any]:
+    """Load or train ARIMA/SARIMA models and generate predictions.
+
+    Args:
+        revenue: Revenue DataFrame with ``date`` and ``revenue`` columns.
+        date: Forecast origin date string (YYYY-MM-DD).
+        duration: Number of forecast periods.
+        directory_models: Directory for persisting and loading model pickles.
+        file_suffix: Filename suffix (``""`` or ``"_<country>"``).
+
+    Returns:
+        Dictionary with ``"arima"``, ``"sarima"``, and ``"drift"`` keys.
+    """
+    from ai_enterprise_workflow.monitoring.drift import (  # noqa: PLC0415
+        get_wasserstein_distance,
+    )
+
+    order: tuple[int, int, int] = (2, 1, 2)
+    seasonal_order: tuple[int, int, int, int] = (2, 1, 2, 30)
+    country = file_suffix.lstrip("_") or None
+
+    arima_model = _load_or_train(
+        directory_models / f"arima{file_suffix}.pickle",
+        lambda c=country: train_arima_model(revenue["revenue"], order, directory_models, c),
+    )
+    sarima_model = _load_or_train(
+        directory_models / f"sarima{file_suffix}.pickle",
+        lambda c=country: train_sarima_model(
+            revenue["revenue"], order, seasonal_order, directory_models, c
+        ),
+    )
+
+    start: int = revenue.index[revenue["date"] == date][0] + 1
+    end: int = start + duration
+    # Capture historical revenue array BEFORE reindexing (avoids NaN in drift)
+    revenue_array: npt.NDArray[np.floating[Any]] = (
+        revenue["revenue"].to_numpy().astype(np.float64).reshape(-1, 1)
+    )
+    new_index = set(revenue.index) | set(range(start, end))
+    revenue = revenue.reindex(sorted(new_index))
+    actual = revenue["revenue"][start:end].sum()
+
+    revenue["forecast_arima"], arima_result = predict(arima_model, "arima", start, end, actual)
+    revenue["forecast_sarima"], sarima_result = predict(
+        sarima_model, "sarima", start, end, actual
+    )
+    revenue.to_csv(cfg.directory_output / f"5 predictions{file_suffix}.csv")
+
+    drift_score = get_wasserstein_distance(revenue_array, batch_size=200)
+    return {"arima": arima_result, "sarima": sarima_result, "drift": float(drift_score)}
+
+
-def model(date: str, duration: int = 30, country: str | None = None) -> dict[str, Any]:  # noqa: PLR0912
+def model(date: str, duration: int = 30, country: str | None = None) -> dict[str, Any]:
     """Run the full ARIMA/SARIMA forecast pipeline for the given date and duration.
     ...
     """
-    if not os.path.exists(DIRECTORY_MODELS):
-        os.makedirs(DIRECTORY_MODELS)
-    if not os.path.exists(DIRECTORY_OUTPUT + "4 revenue_total.csv"):
-        ingest()
-    ...  # (all 50+ lines of country/total branching and pickle loading)
+    DIRECTORY_MODELS.mkdir(parents=True, exist_ok=True)
+    revenue, file_suffix = _resolve_revenue(date, country, DIRECTORY_OUTPUT)
+    return _run_predictions(revenue, date, duration, DIRECTORY_MODELS, file_suffix)
```

---

### Diff 2 — `src/ai_enterprise_workflow/monitoring/drift.py`

*Phase F-1. Single symbol rename; no behavioral change.*

```diff
--- a/src/ai_enterprise_workflow/monitoring/drift.py
+++ b/src/ai_enterprise_workflow/monitoring/drift.py
@@ -9,7 +9,7 @@ from scipy.stats import wasserstein_distance  # type: ignore[import-untyped]


-def get_wasserstain_distance(
+def get_wasserstein_distance(
     data: npt.NDArray[np.floating[Any]],
     batch_size: int = 1000,
     confidence: float = 0.05,
 ) -> np.floating[Any]:
-    """Estimate the Wasserstein distance for drift detection via bootstrap sampling.
+    """Estimate the Wasserstein distance for drift detection via bootstrap sampling.
```

---

### Diff 3 — `tach.toml`

*Phase F-2.*

```diff
--- a/tach.toml
+++ b/tach.toml
@@ -44,7 +44,8 @@ depends_on = [
 [[modules]]
 path = "ai_enterprise_workflow.forecasting"
 depends_on = [
     "ai_enterprise_workflow.core",
     "ai_enterprise_workflow.ingestion",
+    "ai_enterprise_workflow.monitoring",
 ]
```

---

### Diff 4 — `src/ai_enterprise_workflow/core/config.py`

*Phase F-3. Against **post-Slice-A** state (after manifest #7 is executed). Adds one field to `AppSettings`.*

```diff
--- a/src/ai_enterprise_workflow/core/config.py
+++ b/src/ai_enterprise_workflow/core/config.py
@@ -xx,6 +xx,7 @@ class AppSettings(BaseSettings):
     app_base_url: str = Field(
         default="http://127.0.0.1/", validation_alias="APP_BASE_URL"
     )
+    drift_threshold: float = Field(default=0.1, validation_alias="DRIFT_THRESHOLD")

     # ── Schema constants (ClassVar: excluded from Pydantic validation and env) ── #
```

---

### Diff 5 — `src/ai_enterprise_workflow/service/api.py`

*Phase F-5. Against **post-Slice-B** state (after manifest #7 is executed). Adds `drift_warning` to `/predict` response.*

```diff
--- a/src/ai_enterprise_workflow/service/api.py
+++ b/src/ai_enterprise_workflow/service/api.py
@@ -xx,4 +xx,5 @@ def predict() -> ResponseReturnValue:
     ...
     result = model(date, duration, country)
-    return jsonify({"data": result})
+    return jsonify({"data": result, "drift_warning": result["drift"] > cfg.drift_threshold})
```

---

### Diff 6 — `tests/service/test_api.py`

*Phase F-6. Update 4 mock return values and add `drift_warning` assertion. Against post-Slice-B + post-Slice-D state (after manifests #7 and #8 are executed).*

```diff
--- a/tests/service/test_api.py
+++ b/tests/service/test_api.py
@@ -xx,3 +xx,3 @@ class TestApi:
         def test_predict_with_country_returns_data_key(
             self, flask_client: FlaskClient
         ) -> None:
-            with patch(_MODEL_TARGET, return_value={"arima": 1000.0, "sarima": 1100.0}):
+            with patch(_MODEL_TARGET, return_value={"arima": 1000.0, "sarima": 1100.0, "drift": 0.05}):
                 response = flask_client.post(
                     "/predict?date=2018-11-20&duration=30&country=Australia"
                 )
             assert "data" in response.get_json()
+            assert "drift_warning" in response.get_json()

         def test_predict_without_country_returns_data_key(
             self, flask_client: FlaskClient
         ) -> None:
-            with patch(_MODEL_TARGET, return_value={"arima": 1000.0, "sarima": 1100.0}):
+            with patch(_MODEL_TARGET, return_value={"arima": 1000.0, "sarima": 1100.0, "drift": 0.05}):
                 response = flask_client.post("/predict?date=2018-11-20&duration=30")
             assert "data" in response.get_json()

@@ -xx,3 +xx,3 @@ class TestApi:
         @given(duration=st.integers(min_value=1, max_value=365))
         @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
         def test_predict_any_valid_duration_returns_data_key(
             self, flask_client: FlaskClient, duration: int
         ) -> None:
-            with patch(_MODEL_TARGET, return_value={"arima": 1000.0, "sarima": 1100.0}):
+            with patch(_MODEL_TARGET, return_value={"arima": 1000.0, "sarima": 1100.0, "drift": 0.05}):
                 response = flask_client.post(
                     f"/predict?date=2018-11-20&duration={duration}"
                 )
             assert "data" in response.get_json()
```

---

## Failure playbook

| # | Symptom | Likely cause | Remediation | Escalate to |
|---|---------|--------------|-------------|-------------|
| 1 | `pyright` `reportUnknownVariableType` on lambda in `_load_or_train` | `Callable[[], Any]` not imported | Add `from collections.abc import Callable` to imports | @LinterSpecialist |
| 2 | `pyright` `reportArgumentType` on `revenue_array` passed to `get_wasserstein_distance` | `to_numpy()` returns `npt.NDArray[Any]` under pandas-stubs | Use `.astype(np.float64)` before reshape; type annotation present in Diff 1 | @LinterSpecialist |
| 3 | Integration tests fail: `AssertionError` on `"arima" in result` | `_run_predictions` raises before returning | Check drift score computation; if `revenue_array` is empty (all-NaN), `wasserstein_distance` may raise | @TestDesigner |
| 4 | `tach check` fails: `forecasting → monitoring` cycle | `monitoring` imports something from `forecasting` | Check `monitoring/drift.py` — it must only import `numpy`, `scipy`, and `core` symbols | @LinterSpecialist |
| 5 | `drift` key missing in `result` — `KeyError` in `api.py` | Phase F-4 not yet complete when F-5 is applied | Apply phases in order: F-4 before F-5 | @ProjectDeveloper |
| 6 | `cfg.drift_threshold` AttributeError | Issue #7 (`AppSettings`) not merged before Phase F-3 | Run `git rebase origin/develop`; confirm `AppSettings` has the field | @ProjectDeveloper |
| 7 | Integration tests slow (>60s) | `get_wasserstein_distance` with batch_size=200 in every test | Integration tests already marked `@pytest.mark.slow`; run with `-m "not slow"` during development | @TestDesigner |
| 8 | Ruff `N802` on `train_ARIMA_model` still present | Rename was not applied to both function definition and all call sites | `grep -n "train_ARIMA_model\|train_SARIMA_model" src/` must return 0 results | @LinterSpecialist |

---

## Roadmap

| # | Phase | Owner | Status | Evidence / Notes |
|---|-------|-------|--------|------------------|
| 1 | Phase E-1 — rename train_* | @ProjectDeveloper → @LinterSpecialist | done | Renamed in def + docstrings + 4 call sites; grep confirms 0 old names remain |
| 2 | Phase E-2 — extract helpers | @ProjectDeveloper → @CodeReviewer, @LinterSpecialist | done | `_load_or_train`, `_resolve_revenue`, `_run_predictions` extracted; `model()` simplified to 3 lines; `# noqa: PLR0912` removed; ruff+pyright 0 errors |
| 3 | Phase F-1 — fix typo in drift.py | @ProjectDeveloper → @LinterSpecialist | done | `get_wasserstein_distance` renamed; grep confirms 0 old names |
| 4 | Phase F-2 — tach.toml update | @ProjectDeveloper → @LinterSpecialist | done | `monitoring` added to `forecasting` depends_on; tach check ✅ |
| 5 | Phase F-3 — drift_threshold in AppSettings | @ProjectDeveloper | done | `drift_threshold: float = Field(default=0.1, validation_alias="DRIFT_THRESHOLD")` added; cfg.drift_threshold==0.1 verified |
| 6 | Phase F-4 — wire drift into arima.py | @ProjectDeveloper → @CodeReviewer | done | Lazy import of `get_wasserstein_distance` in `_run_predictions`; `revenue_array` captured before reindex; `"drift": float(drift_score)` in return dict |
| 7 | Phase F-5 — drift_warning in api.py | @ProjectDeveloper | done | `{"data": result, "drift_warning": result["drift"] > cfg.drift_threshold}` wired |
| 8 | Phase F-6 — update test mocks | @ProjectDeveloper → @TestDesigner | done | All 3 mock return values updated to include `"drift": 0.05`; `drift_warning` assertion added; 24 tests pass |
| 9 | Documentation pass | @DocsReviewer | done | config.py drift_threshold docstring, api.py predict() returns + example, drift.py examples added; ruff+pyright 0 errors |
| 10 | Integration gate | @IntegrationChecker (`docs_mode=skip`) | done | GO: G0/G2/G3/G4/G5/G6/lockfile all pass; 24 tests; 0 errors |
| 11 | MR preparation | @ProjectDeveloper | done | PR #13 opened: https://github.com/andrea-dm/ai-enterprise-workflow-capstone/pull/13 |

**Effort summary:** S×7, M×1 — total complexity: Small-Medium. No XL phases.

---

## Acceptance criteria (mirror)

*Mirrored verbatim from GitHub issue #9.*

- [ ] `train_ARIMA_model` and `train_SARIMA_model` are absent; `train_arima_model` and `train_sarima_model` are present with identical signatures.
- [ ] `model()` has no `# noqa: PLR0912`; `uv run ruff check src/` passes.
- [ ] `_load_or_train`, `_resolve_revenue`, `_run_predictions` present as private module functions.
- [ ] `get_wasserstein_distance` (correct spelling) is the only public symbol in `monitoring/drift.py`.
- [ ] `uv run tach check` passes with `monitoring` in `forecasting`'s `depends_on`.
- [ ] `cfg.drift_threshold` accessible as `float` with default `0.1`.
- [ ] `model()` return dict contains key `"drift"` with a `float` value.
- [ ] `POST /predict` JSON response contains `"drift_warning": bool`.
- [ ] All existing tests in `test_api.py` and `test_arima.py` pass (mocks updated).
- [ ] `uv run ruff check src/`, `uv run pyright src/`, `uv run tach check` all exit 0.
- [ ] `PYTHONPATH=src /anaconda/envs/ai/bin/python -m pytest tests/ -q` exits 0.

---

## Handover

**Design phase complete.** The floor is handed over to `@ProjectDeveloper`.

`@ProjectDeveloper` must:

1. Treat this manifest as the single source of truth.
2. **Issue #7 must be merged and rebased** before starting Phase E-1. Check `cfg`, `load_pickle`, and `Path` typing are available in the working state of `arima.py`.
3. Phases must be executed in order: E-1 → E-2 → F-1 → F-2 → F-3 → F-4 → F-5 → F-6.
4. Diffs 1, 4, 5 are against **post-Slice-A/B state** (manifests #7 executed). Apply only after rebasing.
5. On any predictable failure, consult `## Failure playbook` first.
6. After all phases, hand over to `@DocsReviewer`, then `@IntegrationChecker`.

To start: `@ProjectDeveloper execute manifests/9-forecasting-refactor-monitoring-wiring.md`.
To finalize after merge: `@ProjectDeveloper finalize manifests/9-forecasting-refactor-monitoring-wiring.md`.

---

## Manifest changelog

| Date (UTC) | Agent | Change |
|---|---|---|
| 2026-05-16T12:00:00Z | @IssueTracker | Initial scaffold — issue #9, branch created, manifest bootstrapped |
| 2026-05-16T12:30:00Z | @ProjectArchitect | Added Execution context, Decisions log (D1–D6), Detailed action plan (Phases E-1, E-2, F-1–F-6 with effort tags and Execution recipes), Proposed diffs (Diffs 1–6), Failure playbook, Roadmap, Acceptance criteria mirror, Handover. |
| 2026-05-16T00:00:00Z | @ProjectDeveloper | Executed phases E-1, E-2, F-1–F-6; @DocsReviewer docs pass; @IntegrationChecker GO (24 tests, 0 ruff/pyright/tach errors); 6 split commits; opened PR #13 targeting develop. |
