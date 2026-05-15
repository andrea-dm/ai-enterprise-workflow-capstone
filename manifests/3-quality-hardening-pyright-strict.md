---
manifest_version: 1
branch: 3-quality-hardening-pyright-strict
issue: 3
issue_url: https://github.com/andrea-dm/ai-enterprise-workflow-capstone/issues/3
host: github
repository: andrea-dm/ai-enterprise-workflow-capstone
scope: slice-2-quality-hardening
lock: null
mr: null
mr_url: null
status: design
---

# Restore pyright strict-mode compliance and enable ModelTest in CI

## Current state

- `pyrightconfig.json` runs `typeCheckingMode: "standard"` — downgraded from `strict` during Slice 1 to unblock CI. The `[tool.pyright]` section in `pyproject.toml` still declares `strict` but is silently overridden by `pyrightconfig.json` (JSON file takes precedence per pyright config resolution rules).
- ~242 pyright strict-mode errors remain across all production modules, all caused by missing type annotations and unavailable `statsmodels` stubs. All errors are pre-existing (zero introduced by Slice 1).
- `tests/model_test.py` wraps `ModelTest` with `@unittest.skipIf(not _DATA_AVAILABLE, …)`, where `_DATA_AVAILABLE = os.path.exists("./data/input/")`. Because `data/*` is gitignored, both model tests are permanently skipped in CI.
- `ruff check` and `pytest` are currently green (post Slice 1 + CI-fix commits on `develop`).
- `scipy-stubs` is not yet installed; `pandas-stubs` is already in `[dependency-groups].dev`.

## Specification

### Goals

1. Restore `typeCheckingMode: "strict"` in `pyrightconfig.json`; achieve zero pyright errors across `src/` and `tests/`.
2. Add type annotations to all public (and relevant private) functions in `core/logging.py`, `ingestion/pipeline.py`, `forecasting/arima.py`, `monitoring/drift.py`, `service/api.py`.
3. Install `scipy-stubs` (dev group only); suppress `statsmodels` (no stubs exist) with exactly 2 `# type: ignore[import-untyped]` lines in `forecasting/arima.py`.
4. Replace the two `apply(lambda x: re.sub(…))` calls in `ingestion/pipeline.py` with a private `_to_digits(value: object) -> str` helper.
5. Add `ResponseReturnValue` return types to `service/api.py` Flask routes.
6. Annotate mock parameters in `tests/app_test.py` as `MagicMock` with `-> None` on all test methods.
7. Remove `[tool.pyright]` section from `pyproject.toml`.
8. Lift `reportUnknownMemberType: false` from `pyrightconfig.json` tests `executionEnvironments` entry.
9. Create fixture CSVs under `tests/fixtures/data/output/`; remove `@unittest.skipIf` guard from `model_test.py`; patch `DIRECTORY_OUTPUT` / `DIRECTORY_MODELS` in the test.

### Non-goals

- No business logic changes.
- No public symbol renames.
- No docstring content changes (only type annotation lines added/fixed).
- No changes to `tach.toml` or runtime `[project.dependencies]`.
- No changes to `data/input/` gitignore policy.

## Acceptance criteria

- [ ] `pyrightconfig.json` has `"typeCheckingMode": "strict"`; `pyright` reports 0 errors, 0 warnings.
- [ ] `[tool.pyright]` section is removed from `pyproject.toml`.
- [ ] All public functions in `core/logging.py`, `ingestion/pipeline.py`, `forecasting/arima.py`, `monitoring/drift.py`, `service/api.py` carry full type annotations (params + return type).
- [ ] `scipy-stubs>=1.13.0.0` is added to `[dependency-groups].dev` in `pyproject.toml`.
- [ ] `statsmodels` imports in `forecasting/arima.py` carry exactly `# type: ignore[import-untyped]`; no other `# type: ignore` suppressions added beyond those already present.
- [ ] `ingestion/pipeline.py` replaces the two `apply(lambda x: re.sub(…))` calls with a named `_to_digits(value: object) -> str` private helper.
- [ ] `service/api.py` route functions return `ResponseReturnValue` (from `flask.typing`).
- [ ] `tests/app_test.py` mock parameters typed as `MagicMock`; all test methods have `-> None`.
- [ ] `pyrightconfig.json` `executionEnvironments` entry for `tests/` no longer suppresses `reportUnknownMemberType`.
- [ ] `tests/fixtures/data/output/4 revenue_total.csv` committed; ≥ 180 rows synthetic daily revenue 2018-06-01 through 2018-11-30 with `date` and `revenue` columns.
- [ ] `tests/fixtures/data/output/3 revenue_country.csv` committed; `country`, `date`, `revenue` columns.
- [ ] `ModelTest::test_01_model_train` and `ModelTest::test_02_model_predict` pass in CI; `@unittest.skipIf` guard removed.
- [ ] `ruff check src/ tests/` and `ruff format --check src/ tests/` exit 0.
- [ ] `tach check` exits 0.
- [ ] `pytest tests/ -v` — all tests pass, no skips for model_test.
- [ ] `CHANGELOG.md` has a new entry documenting the quality hardening changes.

## Implementation plan

High-level phase outline (detailed action plan, proposed diffs, roadmap, and acceptance-criteria mirror will be appended by `@ProjectArchitect` in Stage 4):

- **Phase A — Config & stubs gate.** Restore `pyrightconfig.json` to `strict`; remove `[tool.pyright]` from `pyproject.toml`; add `scipy-stubs`; lift test env suppression.
- **Phase B — Annotate `core/logging.py`.** Add full annotations to 4 functions; remove `# noqa: ANN001`.
- **Phase C — Annotate `ingestion/pipeline.py`.** Add annotations to 5 helpers + `ingest`; introduce `_to_digits` private helper replacing inline lambdas.
- **Phase D — Annotate `monitoring/drift.py`.** Add annotations to `get_wasserstain_distance` (scipy-stubs now resolves `wasserstein_distance`).
- **Phase E — Annotate `forecasting/arima.py`.** Add `# type: ignore[import-untyped]` on statsmodels imports; annotate 5 functions with `Any` return types where statsmodels types are unavailable.
- **Phase F — Annotate `service/api.py`.** Add `ResponseReturnValue` return type to both Flask routes.
- **Phase G — Annotate test mock params in `app_test.py`.** Add `MagicMock` param types and `-> None` to 3 test methods.
- **Phase H — ModelTest fixture CSVs + unskip.** Generate and commit fixture CSVs; rewrite `model_test.py` with `patch` context managers; remove `@skipIf`.
- **Phase I — Final gate validation.** `ruff check`, `ruff format --check`, `pyright` (strict), `tach check`, `pytest tests/ -v`.

## Risks

- **R1:** Pandas-stubs type resolution for `pd.DataFrame` column operations in strict mode may produce 5–15 residual cascade errors in `ingestion/pipeline.py` after annotation (e.g., overloaded `DataFrame.__getitem__` returning `Unknown`). Mitigation: targeted `# type: ignore[unknown-member]` on specific `.apply()` chains only if pyright cannot resolve them with pandas-stubs.
- **R2:** `scipy-stubs` version conflict with installed `scipy`. Mitigation: pin `scipy-stubs` to `>=1.13.0.0`; version scheme mirrors scipy's (`{scipy_version}.{stubs_version}`).
- **R3:** SARIMA(2,1,2,30) fitting on 180-row synthetic data may exceed CI timeout or raise `LinAlgError`. Mitigation: use `numpy.random.seed` in fixture generation; measure fit time locally before merging; fall back to ARIMA-only assertion if > 30 s.
- **R4:** `Any` annotations on statsmodels return types may trigger new `reportUnknownArgumentType` cascade errors in callers. Mitigation: annotate intermediate `arima_model: Any` / `sarima_model: Any` variables explicitly at function boundaries.
- **R5:** Lifting `reportUnknownMemberType: false` from tests env may expose mock-related errors from `unittest.mock`. Mitigation: annotating mock params in Phase G should eliminate all such errors; if residual errors appear they will be fixed in Phase G before lifting the suppression.

## Execution context

- **Working directory:** repo root `/home/azureuser/cloudfiles/code/Users/andrea.del_monaco/capstone`
- **Active branch:** `3-quality-hardening-pyright-strict`
- **Base branch:** `develop`
- **Python version:** 3.12 (pinned in `pyproject.toml`)
- **pyrightconfig.json note:** already has `"typeCheckingMode": "strict"` and no `reportUnknownMemberType` suppression — confirmed by `git log pyrightconfig.json`. No change to that file is needed. Phase A only touches `pyproject.toml`.
- **Validation commands (run in this order after each phase):**
  1. `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/`
  2. `uv run pyright`
  3. `uv run tach check`
  4. `uv run pytest tests/ -v --tb=short`
- **Tooling preconditions:** `uv` installed; run `uv sync --group dev` before starting to install `scipy-stubs` after Phase A.
- **Files in scope (exhaustive allow-list):**
  - `pyproject.toml`
  - `src/ai_enterprise_workflow/core/logging.py`
  - `src/ai_enterprise_workflow/ingestion/pipeline.py`
  - `src/ai_enterprise_workflow/forecasting/arima.py`
  - `src/ai_enterprise_workflow/monitoring/drift.py`
  - `src/ai_enterprise_workflow/service/api.py`
  - `tests/app_test.py`
  - `tests/model_test.py`
  - `tests/fixtures/data/output/3 revenue_country.csv` (new)
  - `tests/fixtures/data/output/4 revenue_total.csv` (new)
  - `CHANGELOG.md`
- **Files explicitly out of scope:** `pyrightconfig.json` (already correct), `tach.toml`, `src/ai_enterprise_workflow/core/config.py`, `src/ai_enterprise_workflow/ingestion/__init__.py`, any `__init__.py`.
- **External dependencies:** none beyond repo-checked-in files.

## Decisions log

### D1 — `pyrightconfig.json` already in strict mode
- **Chosen:** No change to `pyrightconfig.json` — file already has `"typeCheckingMode": "strict"` and no test-environment `reportUnknownMemberType` suppression, confirmed at commit `b98ea70`.
- **Rejected:** Re-writing the file — unnecessary churn.
- **Rationale:** Session summary incorrectly recorded a downgrade; actual file was never changed from strict.
- **Locked:** yes.

### D2 — Remove `[tool.pyright]` from `pyproject.toml`
- **Chosen:** Delete the entire `[tool.pyright]` table — it silently conflicts with `pyrightconfig.json` (JSON file always wins per pyright config resolution). Reflected in Phase A diff.
- **Rejected:** Keep with a comment — comments don't prevent the silent override.
- **Rationale:** Two configs with divergent values mislead contributors; single source of truth is `pyrightconfig.json`.
- **Locked:** yes.

### D3 — `scipy-stubs>=1.13.0.0` in `[dependency-groups].dev` only
- **Chosen:** Dev-only dependency — no wheel impact, type-checking aid only. Reflected in Phase A diff.
- **Rejected:** Adding to runtime `[project.dependencies]` — stubs are never needed at runtime.
- **Locked:** yes.

### D4 — statsmodels: `# type: ignore[import-untyped]` per-import
- **Chosen:** Two suppression comments on the two statsmodels import lines in `forecasting/arima.py`; no global suppression flag. Reflected in Phase E diff.
- **Rejected:** `"reportMissingTypeStubs": false` globally — would hide future missing stubs for packages that do have stubs.
- **Locked:** yes.

### D5 — `_to_digits(value: object) -> str` private helper
- **Chosen:** Extract helper in `ingestion/pipeline.py`, placed between `get_data` and `clean_data`. Reflected in Phase C diff.
- **Rejected:** `# type: ignore[unknown-arg]` on lambda lines — suppression comment on production logic.
- **Rationale:** Helper is used in two call sites; extraction also removes duplication.
- **Locked:** yes.

### D6 — `setUpClass`/`tearDownClass` for ModelTest
- **Chosen:** Class-level fixture setup so ARIMA+SARIMA are fitted once per test class (not per test method). `test_01` fits models into `cls._modeldir`; `test_02` loads the same pickles. Reflected in Phase H diff.
- **Rejected:** Per-test `setUp` — SARIMA(2,1,2,30) fit takes 15–40 s; two fits per class run doubles CI time.
- **Rationale:** Tests remain independent assertions (train vs. predict) while sharing the expensive fit.
- **Locked:** yes.

### D7 — `pd.Series[Any]` for ARIMA/SARIMA data parameters
- **Chosen:** `pd.Series[Any]` — pandas-stubs returns `pd.Series[Any]` for column access `df["revenue"]`. Reflected in Phase E diff.
- **Rejected:** `pd.Series[float]` — would require a cast at the call site since column access is `Any`.
- **Locked:** yes.

### D8 — `npt.NDArray[np.floating[Any]]` for drift input
- **Chosen:** `import numpy.typing as npt` + `npt.NDArray[np.floating[Any]]` for the `data` parameter. Reflected in Phase D diff.
- **Rejected:** `np.ndarray[Any, np.dtype[Any]]` — less informative; `npt` spelling is the canonical numpy approach.
- **Locked:** yes.

## Detailed action plan

**Effort summary:** S×6, M×3 — total estimated complexity: Medium. No XL phases.

---

### Phase A — Config & stubs gate  `[effort: S]`  `[mandatory: @LinterSpecialist]`

**Goal:** Remove redundant `[tool.pyright]` from `pyproject.toml`; add `scipy-stubs` to dev group; re-sync deps.

**Files touched:** `pyproject.toml`

**Steps:**
1. In `pyproject.toml`, delete the entire `[tool.pyright]` section (11 lines including blank lines — see diff).
2. In `[dependency-groups].dev`, append `"scipy-stubs>=1.13.0.0"` as the last entry.
3. Run `uv sync --group dev` to install `scipy-stubs`.
4. Commit: `build(deps): remove redundant [tool.pyright] and add scipy-stubs`.

#### Execution recipe

1. **Pre-checks.** `git status` clean; `uv run pyright 2>&1 | tail -1` → `242 errors`.
2. **Apply diff.** Apply `pyproject.toml` diff from `## Proposed diffs § Phase A`.
3. **Post-edit.** `uv sync --group dev` (installs scipy-stubs).
4. **Validation.** `uv run pyright 2>&1 | tail -1` → still `242 errors` (stubs install alone fixes 18 drift.py errors — expect ~224 after this phase). `uv run ruff check src/ tests/` → clean. `uv run tach check` → clean.
5. **DoD.** `[tool.pyright]` no longer present in `pyproject.toml`; `scipy-stubs` in `uv.lock`; pyright error count reduced.
6. **Delegation.** After commit, post to `@LinterSpecialist`: "Phase A committed. Please verify `uv run pyright 2>&1 | tail -1` shows fewer errors than 242 and `ruff check src/ tests/` is clean."
7. **Stop conditions.** If `uv sync` fails due to scipy-stubs version conflict, pin `scipy-stubs==1.13.1.4` explicitly.

---

### Phase B — Annotate `core/logging.py`  `[effort: S]`  `[mandatory: @LinterSpecialist]`

**Goal:** Add full type annotations to all 4 functions; remove 4 `# noqa: ANN001` comments.

**Files touched:** `src/ai_enterprise_workflow/core/logging.py`

**Exact signature replacements (line → replacement):**

| Line | Old | New |
|---|---|---|
| 16 | `def log_common(log_file, log_data, headers, directory_logs):  # noqa: ANN001` | `def log_common(log_file: str, log_data: list[str], headers: list[str], directory_logs: str) -> None:` |
| 37 | `def log_ingest(shape):  # noqa: ANN001` | `def log_ingest(shape: tuple[int, ...]) -> None:` |
| 51 | `def log_train(model, shape, performance, version=VERSION):  # noqa: ANN001` | `def log_train(model: str, shape: tuple[int, ...], performance: dict[str, object], version: float = VERSION) -> None:` |
| 68 | `def log_predict(model, query, prediction, version=VERSION):  # noqa: ANN001` | `def log_predict(model: str, query: dict[str, object], prediction: dict[str, object], version: float = VERSION) -> None:` |

No new imports needed (`dict`, `list`, `tuple` are builtins in Python 3.12).

**Steps:**
1. Apply diff from `## Proposed diffs § Phase B`.
2. Commit: `feat(core): add type annotations to logging module`.

#### Execution recipe

1. **Pre-checks.** `uv run pyright src/ai_enterprise_workflow/core/logging.py 2>&1 | grep error | wc -l` → `34`.
2. **Apply diff.** `## Proposed diffs § Phase B`.
3. **Post-edit.** `uv run ruff format src/ai_enterprise_workflow/core/logging.py`.
4. **Validation.** `uv run pyright src/ai_enterprise_workflow/core/logging.py 2>&1 | tail -1` → `0 errors`. `uv run ruff check src/ai_enterprise_workflow/core/logging.py` → clean.
5. **DoD.** 0 pyright errors in file; 0 ruff errors; 4 `# noqa: ANN001` removed; `log_test.py` cascade errors also resolve (run `uv run pytest tests/log_test.py -v` → 3 passed).
6. **Delegation.** None required for this phase alone; combine with Phase C commit if preferred.
7. **Stop conditions.** If pyright reports `reportArgumentType` on any caller passing `data.shape` to `log_ingest`, confirm `pd.DataFrame.shape` type is `tuple[int, ...]` — it is per pandas-stubs.

---

### Phase C — Annotate `ingestion/pipeline.py`  `[effort: M]`  `[mandatory: @LinterSpecialist, @CodeReviewer]`

**Goal:** Add `_to_digits` private helper; replace 2 inline lambdas; add full annotations to all 6 functions.

**Files touched:** `src/ai_enterprise_workflow/ingestion/pipeline.py`

**Exact changes:**

1. **New private helper** — insert before `clean_data` (after line 32 `return data`):
   ```python
   def _to_digits(value: object) -> str:
       """Strip non-digit characters from the string representation of *value*."""
       return re.sub("[^0-9]", "", str(value))
   ```

2. **Lambda replacements** (inside `clean_data`):
   - `data["invoice_id"].apply(lambda x: re.sub("[^0-9]", "", x))` → `data["invoice_id"].apply(_to_digits)`
   - `data["stream_id"].apply(lambda x: re.sub("[^0-9]", "", x))` → `data["stream_id"].apply(_to_digits)`

3. **Signature annotations:**

| Function | New signature |
|---|---|
| `get_data` | `def get_data(keys: tuple[str, ...], key_names: dict[str, str], directory_data: str, directory_output: str) -> pd.DataFrame:` |
| `clean_data` | `def clean_data(data: pd.DataFrame, keys: tuple[str, ...], key_types: dict[str, type[int] \| type[float] \| type[str]], directory_output: str) -> pd.DataFrame:` |
| `prepare_data` | `def prepare_data(data: pd.DataFrame, directory_output: str) -> pd.DataFrame:` |
| `calculate_revenue_country` | `def calculate_revenue_country(data: pd.DataFrame, directory_output: str) -> None:` |
| `calculate_revenue_total` | `def calculate_revenue_total(data: pd.DataFrame, directory_output: str) -> None:` |
| `ingest` | `def ingest(force: bool = False) -> None:` |

No new imports needed.

**Steps:**
1. Apply diff from `## Proposed diffs § Phase C`.
2. Run `uv run pyright src/ai_enterprise_workflow/ingestion/pipeline.py` — if pandas-stubs cascade errors remain (R1), add targeted `# type: ignore[unknown-member]` only on the specific offending lines; do NOT add blanket suppression.
3. Commit: `feat(ingestion): add type annotations and _to_digits helper`.

#### Execution recipe

1. **Pre-checks.** `uv run pyright src/ai_enterprise_workflow/ingestion/pipeline.py 2>&1 | grep error | wc -l` → `77`.
2. **Apply diff.** `## Proposed diffs § Phase C`.
3. **Post-edit.** `uv run ruff format src/ai_enterprise_workflow/ingestion/pipeline.py`.
4. **Validation.** `uv run pyright src/ai_enterprise_workflow/ingestion/pipeline.py 2>&1 | tail -1` → `0 errors`. `uv run ruff check src/ai_enterprise_workflow/ingestion/pipeline.py` → clean.
5. **DoD.** 0 pyright errors; 0 ruff errors; `grep "lambda" src/ai_enterprise_workflow/ingestion/pipeline.py` → no matches; `_to_digits` function present.
6. **Delegation.** `@CodeReviewer`: "Please review the `_to_digits` extraction and type annotations in `ingestion/pipeline.py` — confirm the helper is correct and the `dict[str, type[int] | type[float] | type[str]]` annotation matches the `key_types` constant in `core/config.py`."
7. **Stop conditions.** If pandas-stubs cascade errors remain after applying the diff, add `# type: ignore[unknown-member]` on the specific offending line(s) only; document each suppression in the roadmap Notes column.

---

### Phase D — Annotate `monitoring/drift.py`  `[effort: S]`  `[mandatory: @LinterSpecialist]`

**Goal:** Add `from typing import Any` and `import numpy.typing as npt`; annotate `get_wasserstain_distance`. scipy-stubs (installed in Phase A) resolves `wasserstein_distance` typing.

**Files touched:** `src/ai_enterprise_workflow/monitoring/drift.py`

**Exact changes:**

1. **New imports** — add after `import numpy as np`:
   ```python
   import numpy.typing as npt
   from typing import Any
   ```
   (import ordering: stdlib `typing` before third-party `numpy.typing` per ruff I-rules — ruff will reorder automatically)

2. **Signature annotation:**
   ```python
   def get_wasserstain_distance(
       data: npt.NDArray[np.floating[Any]],
       batch_size: int = 1000,
       confidence: float = 0.05,
   ) -> np.floating[Any]:
   ```
   Remove `# noqa: ANN001`.

**Steps:**
1. Apply diff from `## Proposed diffs § Phase D`.
2. `uv run ruff format src/ai_enterprise_workflow/monitoring/drift.py` (ruff will sort imports).
3. Commit: `feat(monitoring): add type annotations to drift module`.

#### Execution recipe

1. **Pre-checks.** `uv run pyright src/ai_enterprise_workflow/monitoring/drift.py 2>&1 | grep error | wc -l` → `18`.
2. **Apply diff.** `## Proposed diffs § Phase D`.
3. **Post-edit.** `uv run ruff format src/ai_enterprise_workflow/monitoring/drift.py`.
4. **Validation.** `uv run pyright src/ai_enterprise_workflow/monitoring/drift.py 2>&1 | tail -1` → `0 errors`. `uv run ruff check src/ai_enterprise_workflow/monitoring/drift.py` → clean.
5. **DoD.** 0 pyright errors; `# noqa: ANN001` removed.
6. **Delegation.** None required.
7. **Stop conditions.** If `npt.NDArray[np.floating[Any]]` is not accepted by scipy-stubs `wasserstein_distance` signature (expects `ArrayLike`), change parameter to `npt.ArrayLike` — but `wasserstein_distance` accepts any array-like, so `NDArray` is a valid subtype.

---

### Phase E — Annotate `forecasting/arima.py`  `[effort: M]`  `[mandatory: @LinterSpecialist, @CodeReviewer]`

**Goal:** Suppress 2 statsmodels untyped imports; add `from typing import Any`; annotate all 5 functions; annotate intermediate `pickle.load` variables.

**Files touched:** `src/ai_enterprise_workflow/forecasting/arima.py`

**Exact changes:**

1. **New import** — add `from typing import Any` in the stdlib imports block (before `import os`):
   ```python
   from typing import Any
   ```

2. **Statsmodels suppressions** — change lines 7–8:
   ```python
   from statsmodels.tsa.api import SARIMAX  # type: ignore[import-untyped]
   from statsmodels.tsa.arima.model import ARIMA  # type: ignore[import-untyped]
   ```

3. **Signature annotations:**

| Function | New signature |
|---|---|
| `get_revenue_country` | `def get_revenue_country(revenue: pd.DataFrame, country: str) -> pd.DataFrame:` |
| `train_ARIMA_model` | `def train_ARIMA_model(data: pd.Series[Any], order: tuple[int, int, int], directory_models: str, country: str \| None = None) -> Any:` |
| `train_SARIMA_model` | `def train_SARIMA_model(data: pd.Series[Any], order: tuple[int, int, int], seasonal_order: tuple[int, int, int, int], directory_models: str, country: str \| None = None) -> Any:` |
| `predict` | `def predict(model: Any, name: str, start: int, end: int, actual: float \| None = None) -> tuple[Any, Any]:` |
| `model` | `def model(date: str, duration: int = 30, country: str \| None = None) -> dict[str, Any]:  # noqa: PLR0912` |

4. **Intermediate variable annotations** — inside `model()`, annotate every `pickle.load` assignment and the first assignment to `arima_model`/`sarima_model` in each branch:
   ```python
   arima_model: Any = pickle.load(file)   # in every with-open block
   sarima_model: Any = pickle.load(file)  # in every with-open block
   ```
   The `train_ARIMA_model`/`train_SARIMA_model` calls already return `Any`, so those assignments need no annotation.

**Steps:**
1. Apply diff from `## Proposed diffs § Phase E`.
2. `uv run ruff format src/ai_enterprise_workflow/forecasting/arima.py`.
3. Commit: `feat(forecasting): add type annotations to arima module`.

#### Execution recipe

1. **Pre-checks.** `uv run pyright src/ai_enterprise_workflow/forecasting/arima.py 2>&1 | grep error | wc -l` → `103`.
2. **Apply diff.** `## Proposed diffs § Phase E`.
3. **Post-edit.** `uv run ruff format src/ai_enterprise_workflow/forecasting/arima.py`.
4. **Validation.** `uv run pyright src/ai_enterprise_workflow/forecasting/arima.py 2>&1 | tail -1` → `0 errors`. `uv run ruff check src/ai_enterprise_workflow/forecasting/arima.py` → clean (existing `# type: ignore[union-attr]` and `# noqa: PLR0912` remain).
5. **DoD.** 0 pyright errors; exactly 2 `# type: ignore[import-untyped]` present; no other new `# type: ignore` added.
6. **Delegation.** `@CodeReviewer`: "Review Phase E — confirm `Any` return type on `train_ARIMA_model`/`train_SARIMA_model` and intermediate `pickle.load` annotations are the minimal correct annotations given statsmodels has no stubs."
7. **Stop conditions.** If `reportUnknownArgumentType` errors appear on statsmodels calls inside `train_*` functions after adding `Any` return type, add `cast(Any, arima.fit())` — but this should not be needed since `ARIMA` is already `Any` after the `# type: ignore[import-untyped]`.

---

### Phase F — Annotate `service/api.py`  `[effort: S]`  `[mandatory: @LinterSpecialist]`

**Goal:** Add `ResponseReturnValue` return types to both Flask route functions.

**Files touched:** `src/ai_enterprise_workflow/service/api.py`

**Exact changes:**

1. **New import** — add after `from flask import Flask, jsonify, request`:
   ```python
   from flask.typing import ResponseReturnValue
   ```

2. **Signature annotations:**
   - `def predict():` → `def predict() -> ResponseReturnValue:`
   - `def logs():` → `def logs() -> ResponseReturnValue:`

**Steps:**
1. Apply diff from `## Proposed diffs § Phase F`.
2. Commit: `feat(service): add ResponseReturnValue return types to Flask routes`.

#### Execution recipe

1. **Pre-checks.** `uv run pyright src/ai_enterprise_workflow/service/api.py 2>&1 | grep error | wc -l` → `3`.
2. **Apply diff.** `## Proposed diffs § Phase F`.
3. **Post-edit.** `uv run ruff format src/ai_enterprise_workflow/service/api.py`.
4. **Validation.** `uv run pyright src/ai_enterprise_workflow/service/api.py 2>&1 | tail -1` → `0 errors`.
5. **DoD.** 0 pyright errors; both route functions annotated; `flask.typing` import present.
6. **Delegation.** None.
7. **Stop conditions.** If `ResponseReturnValue` is not importable from `flask.typing` (Flask < 2.2), confirm `flask>=3.0` is pinned in `pyproject.toml` — it is.

---

### Phase G — Annotate test mock params in `tests/app_test.py`  `[effort: S]`  `[mandatory: @LinterSpecialist]`

**Goal:** Add `MagicMock` import; annotate `setUp` and 3 test methods; add `-> None` to all.

**Files touched:** `tests/app_test.py`

**Exact changes:**

1. **Import change** — replace `from unittest.mock import patch` with:
   ```python
   from unittest.mock import MagicMock, patch
   ```

2. **Method signature annotations:**
   - `def setUp(self):` → `def setUp(self) -> None:`
   - `def test_01_app_predict_country(self, mock_model):` → `def test_01_app_predict_country(self, mock_model: MagicMock) -> None:`
   - `def test_02_app_predict_total(self, mock_model):` → `def test_02_app_predict_total(self, mock_model: MagicMock) -> None:`
   - `def test_03_app_logs(self, mock_read_csv):` → `def test_03_app_logs(self, mock_read_csv: MagicMock) -> None:`

**Steps:**
1. Apply diff from `## Proposed diffs § Phase G`.
2. Commit: `test(service): annotate mock params and return types in AppTest`.

#### Execution recipe

1. **Pre-checks.** `uv run pyright tests/app_test.py 2>&1 | grep error | wc -l` → `7`.
2. **Apply diff.** `## Proposed diffs § Phase G`.
3. **Post-edit.** `uv run ruff format tests/app_test.py`.
4. **Validation.** `uv run pyright tests/app_test.py 2>&1 | tail -1` → `0 errors`. `uv run pytest tests/app_test.py -v` → 3 passed.
5. **DoD.** 0 pyright errors; all test methods annotated; existing tests still pass.
6. **Delegation.** None.
7. **Stop conditions.** None anticipated.

---

### Phase H — ModelTest fixture CSVs + unskip  `[effort: M]`  `[mandatory: @TestDesigner, @CodeReviewer]`

**Goal:** Generate and commit two fixture CSVs; rewrite `model_test.py` using `setUpClass` + `patch`; remove `@skipIf`.

**Files touched / created:**
- `tests/fixtures/data/output/3 revenue_country.csv` (new)
- `tests/fixtures/data/output/4 revenue_total.csv` (new)
- `tests/model_test.py` (rewrite)

**Fixture generation script** (run once; not committed):

```python
# Run from repo root: python3 scripts/gen_fixtures.py
import csv
import datetime
import numpy as np

rng = np.random.default_rng(42)
start_date = datetime.date(2018, 6, 1)
n_days = 183  # 2018-06-01 through 2018-11-30

t = np.arange(n_days, dtype=float)
revenues = (
    10_000
    + 50 * t
    + 2_000 * np.sin(2 * np.pi * t / 30)
    + 500 * rng.standard_normal(n_days)
)
revenues = np.maximum(revenues, 100.0)
dates = [start_date + datetime.timedelta(days=i) for i in range(n_days)]

import os
os.makedirs("tests/fixtures/data/output", exist_ok=True)

with open("tests/fixtures/data/output/4 revenue_total.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["date", "revenue"])
    for d, r in zip(dates, revenues):
        w.writerow([str(d), f"{r:.2f}"])

with open("tests/fixtures/data/output/3 revenue_country.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["country", "date", "revenue"])
    for d, r in zip(dates[:5], revenues[:5]):
        w.writerow(["Australia", str(d), f"{r:.2f}"])

print("Fixtures written.")
print(f"  4 revenue_total.csv: {n_days} rows")
print(f"  3 revenue_country.csv: 5 rows")
print(f"  Date of '2018-11-20' is row index {(datetime.date(2018, 11, 20) - start_date).days}")
```

**Exact `tests/model_test.py` replacement** (full file):

```python
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_enterprise_workflow.forecasting.arima import model

_FIXTURES = Path(__file__).parent / "fixtures" / "data" / "output"


class ModelTest(unittest.TestCase):
    _tmpdir: str
    _modeldir: str

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.mkdtemp()
        cls._modeldir = tempfile.mkdtemp()
        for csv_file in ("3 revenue_country.csv", "4 revenue_total.csv"):
            shutil.copy(str(_FIXTURES / csv_file), cls._tmpdir + "/" + csv_file)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._tmpdir, ignore_errors=True)
        shutil.rmtree(cls._modeldir, ignore_errors=True)

    def test_01_model_train(self) -> None:
        with (
            patch("ai_enterprise_workflow.forecasting.arima.DIRECTORY_OUTPUT", self._tmpdir + "/"),
            patch("ai_enterprise_workflow.forecasting.arima.DIRECTORY_MODELS", self._modeldir + "/"),
        ):
            model("2018-11-20", 30, None)
        assert os.path.exists(self._modeldir + "/arima.pickle")

    def test_02_model_predict(self) -> None:
        with (
            patch("ai_enterprise_workflow.forecasting.arima.DIRECTORY_OUTPUT", self._tmpdir + "/"),
            patch("ai_enterprise_workflow.forecasting.arima.DIRECTORY_MODELS", self._modeldir + "/"),
        ):
            result = model("2018-11-20", 30, None)
        assert "arima" in result
```

**Steps:**
1. Run the fixture generation script: `python3 -c "<script above>"` from repo root.
2. Verify: `wc -l "tests/fixtures/data/output/4 revenue_total.csv"` → `184` (183 data rows + header).
3. Verify: `head -2 "tests/fixtures/data/output/4 revenue_total.csv"` → header + first row with date `2018-06-01`.
4. Overwrite `tests/model_test.py` with the exact content above.
5. Run locally first: `cd ~ && PYTHONPATH=.../capstone/src python -m pytest .../capstone/tests/model_test.py -v --tb=short` — should show 2 passed (may take 20–60 s).
6. Commit: `test(forecasting): add fixture CSVs and rewrite ModelTest with patch`.

#### Execution recipe

1. **Pre-checks.** `python3 -c "import numpy, csv, datetime; print('ok')"` → `ok`.
2. **Apply changes.**
   a. Run fixture generation script.
   b. Apply `tests/model_test.py` diff from `## Proposed diffs § Phase H`.
3. **Post-edit.** `uv run ruff format tests/model_test.py`.
4. **Validation.**
   - `uv run pyright tests/model_test.py 2>&1 | tail -1` → `0 errors`.
   - `time uv run pytest tests/model_test.py -v --tb=short` → `2 passed`; note elapsed time. If > 60 s, see Stop conditions.
   - `uv run pytest tests/ -v --tb=short` → all 8 tests pass (0 skips).
5. **DoD.** Both model tests pass; `@unittest.skipIf` and `_DATA_AVAILABLE` removed; fixture CSVs committed; `wc -l tests/fixtures/data/output/4\ revenue_total.csv` = 184; `uv run pyright` → 0 errors total.
6. **Delegation.** `@TestDesigner`: "Review `model_test.py` rewrite — confirm `setUpClass` pattern is correct for shared fixture, that `patch` targets are the right module-level constants, and that the fixture CSV content (183 rows, seed=42) is stable across platforms." `@CodeReviewer`: "Confirm the `_to_digits` extraction and the fixture approach do not change any production behavior."
7. **Stop conditions.** If SARIMA fit takes > 60 s in CI, change `test_02_model_predict` to assert only `"arima" in result` (skip sarima assertion) and file a follow-up issue to add `pytest.mark.slow`.

---

### Phase I — Final gate validation  `[effort: S]`  `[mandatory: @IntegrationChecker]`

**Goal:** Confirm all quality gates pass end-to-end before opening the PR.

**Steps:**
1. `uv run ruff check src/ tests/ && uv run ruff format --check src/ tests/` → `All checks passed!`
2. `uv run pyright 2>&1 | tail -1` → `0 errors, 0 warnings, 0 informations`
3. `uv run tach check` → `All modules validated!`
4. `uv run pytest tests/ -v` → 8 passed, 0 skipped, 0 failed
5. Update `CHANGELOG.md` with a new `## [Unreleased]` entry documenting the quality hardening changes.
6. Open PR targeting `develop`; title (summary only): `restore pyright strict-mode compliance and enable ModelTest in CI`; body references issue `Closes #3`.

#### Execution recipe

1. **Pre-checks.** All Phase A–H rows show `done` in the Roadmap.
2. **Apply.** `CHANGELOG.md` update (new `## [Unreleased]` section with bullet list of changes).
3. **Validation.** Run all 4 commands above in order; all must exit 0.
4. **DoD.** Zero suppression comments beyond the 2 `# type: ignore[import-untyped]` on statsmodels imports (and existing `# type: ignore[union-attr]` on `sarima_model.save(...)` lines); 0 `# noqa: ANN001` anywhere in `src/`; `pytest tests/ -v` → 8 passed; CHANGELOG updated.
5. **Delegation.** `@IntegrationChecker` (`docs_mode=skip`): "All phases complete. Please run the full quality gate and confirm GO for PR."
6. **Stop conditions.** Any gate exit code ≠ 0 requires fixing before PR is opened.

## Proposed diffs

### Phase A — `pyproject.toml`

```diff
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -68,19 +68,6 @@ docstring-code-format = true
 
-[tool.pyright]
-pythonVersion = "3.12"
-typeCheckingMode = "strict"
-include = ["src", "tests"]
-# When overriding `exclude`, pyright drops its built-in defaults — re-add them
-# explicitly so __pycache__, dotfiles, and node_modules stay out of analysis.
-exclude = [
-    ".venv",
-    "./resources",
-    "**/__pycache__",
-    "**/node_modules",
-    "**/.*",
-]
-
-
-extraPaths = ["src"]
-
 [tool.deptry]
 known_first_party = ["ai_enterprise_workflow"]
```

```diff
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -100,6 +100,7 @@ test = [
 dev = [
     { include-group = "lint" },
     { include-group = "test" },
     "pandas-stubs>=3.0.0.260204",
+    "scipy-stubs>=1.13.0.0",
 ]
```

### Phase B — `src/ai_enterprise_workflow/core/logging.py`

```diff
--- a/src/ai_enterprise_workflow/core/logging.py
+++ b/src/ai_enterprise_workflow/core/logging.py
@@ -14,7 +14,7 @@ from ai_enterprise_workflow.core.config import DIRECTORY_LOGS, VERSION
 
-def log_common(log_file, log_data, headers, directory_logs):  # noqa: ANN001
+def log_common(log_file: str, log_data: list[str], headers: list[str], directory_logs: str) -> None:
     """Append a row to a CSV log file, writing the header row on first write.
 
     Args:
@@ -35,7 +35,7 @@ def log_common(log_file, log_data, headers, directory_logs):  # noqa: ANN001
         writer.writerow(log_data)
 
 
-def log_ingest(shape):  # noqa: ANN001
+def log_ingest(shape: tuple[int, ...]) -> None:
     """Write an ingestion event to the ingest log.
 
     Args:
@@ -49,7 +49,7 @@ def log_ingest(shape):  # noqa: ANN001
     log_common(log_file, log_data, headers, DIRECTORY_LOGS)
 
 
-def log_train(model, shape, performance, version=VERSION):  # noqa: ANN001
+def log_train(model: str, shape: tuple[int, ...], performance: dict[str, object], version: float = VERSION) -> None:
     """Write a training event to the train log.
 
     Args:
@@ -66,7 +66,7 @@ def log_train(model, shape, performance, version=VERSION):  # noqa: ANN001
     log_common(log_file, log_data, headers, DIRECTORY_LOGS)
 
 
-def log_predict(model, query, prediction, version=VERSION):  # noqa: ANN001
+def log_predict(model: str, query: dict[str, object], prediction: dict[str, object], version: float = VERSION) -> None:
     """Write a prediction event to the predict log.
 
     Args:
```

### Phase C — `src/ai_enterprise_workflow/ingestion/pipeline.py`

```diff
--- a/src/ai_enterprise_workflow/ingestion/pipeline.py
+++ b/src/ai_enterprise_workflow/ingestion/pipeline.py
@@ -18,7 +18,7 @@ from ai_enterprise_workflow.core.logging import log_ingest
 
-def get_data(keys, key_names, directory_data, directory_output):
+def get_data(keys: tuple[str, ...], key_names: dict[str, str], directory_data: str, directory_output: str) -> pd.DataFrame:
     """Read source data into a tabular data structure"""
     # Initialise dataframe with desired column names
     data = pd.DataFrame(columns=keys, dtype=int)
@@ -32,8 +32,15 @@ def get_data(keys, key_names, directory_data, directory_output):
     return data
 
 
-def clean_data(data, keys, key_types, directory_output):
+def _to_digits(value: object) -> str:
+    """Strip non-digit characters from the string representation of *value*."""
+    return re.sub("[^0-9]", "", str(value))
+
+
+def clean_data(data: pd.DataFrame, keys: tuple[str, ...], key_types: dict[str, type[int] | type[float] | type[str]], directory_output: str) -> pd.DataFrame:
     """Transform data into a cleaned dataframe"""
     data = data.copy()
     # Remove duplicate rows
@@ -41,8 +48,8 @@ def clean_data(data, keys, key_types, directory_output):
     # Replace null with -1
     data.fillna(value=-1, inplace=True)
     # Some features have non-numeric characters; remove those characters from string
-    data["invoice_id"] = data["invoice_id"].apply(lambda x: re.sub("[^0-9]", "", x))
-    data["stream_id"] = data["stream_id"].apply(lambda x: re.sub("[^0-9]", "", x))
+    data["invoice_id"] = data["invoice_id"].apply(_to_digits)
+    data["stream_id"] = data["stream_id"].apply(_to_digits)
     # Replace empty strings with -1
     data = data.replace(r"^\s*$", -1, regex=True)
@@ -58,21 +65,21 @@ def clean_data(data, keys, key_types, directory_output):
     return data
 
 
-def prepare_data(data, directory_output):
+def prepare_data(data: pd.DataFrame, directory_output: str) -> pd.DataFrame:
     """Perform feature transformations to prepare data for model"""
     data = data.copy()
@@ -79,13 +86,13 @@ def prepare_data(data, directory_output):
     return data
 
 
-def calculate_revenue_country(data, directory_output):
+def calculate_revenue_country(data: pd.DataFrame, directory_output: str) -> None:
     """Aggregate individual transactions into daily revenue by country"""
     revenue = data.groupby(["country", "date"])["price"].sum().reset_index()
     revenue.rename(columns={"price": "revenue"}, inplace=True)
     revenue.to_csv(directory_output + "3 revenue_country.csv", index=False)
 
 
-def calculate_revenue_total(data, directory_output):
+def calculate_revenue_total(data: pd.DataFrame, directory_output: str) -> None:
     """Aggregate individual transactions into daily total revenue"""
     revenue = data.groupby(["date"])["price"].sum().reset_index()
     revenue.set_index("date", inplace=True)
@@ -95,7 +102,7 @@ def calculate_revenue_total(data, directory_output):
 
 
-def ingest(force=False):
+def ingest(force: bool = False) -> None:
     """Run the full ingestion pipeline, writing processed CSVs to the output directory.
 
     Args:
```

### Phase D — `src/ai_enterprise_workflow/monitoring/drift.py`

```diff
--- a/src/ai_enterprise_workflow/monitoring/drift.py
+++ b/src/ai_enterprise_workflow/monitoring/drift.py
@@ -1,8 +1,12 @@
 """Wasserstein-distance drift detection utilities."""
 
+from typing import Any
+
 import numpy as np
+import numpy.typing as npt
 from scipy.stats import wasserstein_distance
 
 
-def get_wasserstain_distance(data, batch_size=1000, confidence=0.05):  # noqa: ANN001
+def get_wasserstain_distance(
+    data: npt.NDArray[np.floating[Any]],
+    batch_size: int = 1000,
+    confidence: float = 0.05,
+) -> np.floating[Any]:
```

### Phase E — `src/ai_enterprise_workflow/forecasting/arima.py`

```diff
--- a/src/ai_enterprise_workflow/forecasting/arima.py
+++ b/src/ai_enterprise_workflow/forecasting/arima.py
@@ -1,9 +1,11 @@
 """ARIMA and SARIMA forecasting models for revenue prediction."""
 
+from typing import Any
+
 import os
 import pickle
 
 import pandas as pd
-from statsmodels.tsa.api import SARIMAX
-from statsmodels.tsa.arima.model import ARIMA
+from statsmodels.tsa.api import SARIMAX  # type: ignore[import-untyped]
+from statsmodels.tsa.arima.model import ARIMA  # type: ignore[import-untyped]
 
 from ai_enterprise_workflow.core.config import (
@@ -17,19 +19,19 @@ from ai_enterprise_workflow.ingestion.pipeline import ingest
 
-def get_revenue_country(revenue, country):
+def get_revenue_country(revenue: pd.DataFrame, country: str) -> pd.DataFrame:
     """Get daily revenue data for given country"""
     return revenue[revenue["country"] == country].reset_index()[["date", "revenue"]]
 
 
-def train_ARIMA_model(data, order, directory_models, country=None):
+def train_ARIMA_model(data: pd.Series[Any], order: tuple[int, int, int], directory_models: str, country: str | None = None) -> Any:
     """Train an auto-regressive, integrating, moving-average (ARIMA) model"""
     arima = ARIMA(data, order=order)
     arima_model = arima.fit()
@@ -41,7 +43,7 @@ def train_ARIMA_model(data, order, directory_models, country=None):
     return arima_model
 
 
-def train_SARIMA_model(data, order, seasonal_order, directory_models, country=None):
+def train_SARIMA_model(data: pd.Series[Any], order: tuple[int, int, int], seasonal_order: tuple[int, int, int, int], directory_models: str, country: str | None = None) -> Any:
     """Train a seasonal auto-regressive, integrating, moving-average (SARIMA) model"""
     sarima = SARIMAX(data, order=order, seasonal_order=seasonal_order)
     sarima_model = sarima.fit()
@@ -54,7 +56,7 @@ def train_SARIMA_model(data, order, seasonal_order, directory_models, country=No
     return sarima_model
 
 
-def predict(model, name, start, end, actual=None):
+def predict(model: Any, name: str, start: int, end: int, actual: float | None = None) -> tuple[Any, Any]:
     """Generate forecasted predictions using trained model"""
     predictions = model.predict(start=start, end=end, dynamic=True)
     predictions_sum = predictions.sum()
@@ -65,7 +67,7 @@ def predict(model, name, start, end, actual=None):
     return predictions, predictions_sum
 
 
-def model(date, duration=30, country=None):  # noqa: PLR0912
+def model(date: str, duration: int = 30, country: str | None = None) -> dict[str, Any]:  # noqa: PLR0912
     """Run the full ARIMA/SARIMA forecast pipeline for the given date and duration.
 
@@ -86,14 +88,14 @@ def model(date, duration=30, country=None):  # noqa: PLR0912
         if os.path.exists(DIRECTORY_MODELS + "arima_" + country + ".pickle"):
             with open(DIRECTORY_MODELS + "arima_" + country + ".pickle", "rb") as file:
-                arima_model = pickle.load(file)
+                arima_model: Any = pickle.load(file)
         else:
             arima_model = train_ARIMA_model(
                 revenue["revenue"], order, DIRECTORY_MODELS, country
             )
         if os.path.exists(DIRECTORY_MODELS + "sarima_" + country + ".pickle"):
             with open(DIRECTORY_MODELS + "sarima_" + country + ".pickle", "rb") as file:
-                sarima_model = pickle.load(file)
+                sarima_model: Any = pickle.load(file)
         else:
             sarima_model = train_SARIMA_model(
@@ -102,10 +104,10 @@ def model(date, duration=30, country=None):  # noqa: PLR0912
     else:
         if os.path.exists(DIRECTORY_MODELS + "arima.pickle"):
             with open(DIRECTORY_MODELS + "arima.pickle", "rb") as file:
-                arima_model = pickle.load(file)
+                arima_model: Any = pickle.load(file)
         else:
             arima_model = train_ARIMA_model(revenue["revenue"], order, DIRECTORY_MODELS)
         if os.path.exists(DIRECTORY_MODELS + "sarima.pickle"):
             with open(DIRECTORY_MODELS + "sarima.pickle", "rb") as file:
-                sarima_model = pickle.load(file)
+                sarima_model: Any = pickle.load(file)
         else:
             sarima_model = train_SARIMA_model(
```

### Phase F — `src/ai_enterprise_workflow/service/api.py`

```diff
--- a/src/ai_enterprise_workflow/service/api.py
+++ b/src/ai_enterprise_workflow/service/api.py
@@ -2,6 +2,7 @@
 
 import pandas as pd
 from flask import Flask, jsonify, request
+from flask.typing import ResponseReturnValue
 
 from ai_enterprise_workflow.core.config import DIRECTORY_LOGS
 from ai_enterprise_workflow.forecasting.arima import model
@@ -13,7 +14,7 @@ app.config["DEBUG"] = True
 
 @app.route("/predict", methods=["POST"])
-def predict():
+def predict() -> ResponseReturnValue:
     """Run the ARIMA/SARIMA forecast for the given query parameters.
 
@@ -38,7 +39,7 @@ def predict():
 
 @app.route("/logs", methods=["POST"])
-def logs():
+def logs() -> ResponseReturnValue:
     """Return the requested log file as JSON.
```

### Phase G — `tests/app_test.py`

```diff
--- a/tests/app_test.py
+++ b/tests/app_test.py
@@ -1,6 +1,6 @@
 import unittest
-from unittest.mock import patch
+from unittest.mock import MagicMock, patch
 
 import pandas as pd
 
 from ai_enterprise_workflow.service.api import app
@@ -9,22 +9,22 @@ class AppTest(unittest.TestCase):
-    def setUp(self):
+    def setUp(self) -> None:
         app.config["TESTING"] = True
         self.client = app.test_client()
 
     @patch("ai_enterprise_workflow.service.api.model")
-    def test_01_app_predict_country(self, mock_model):
+    def test_01_app_predict_country(self, mock_model: MagicMock) -> None:
         mock_model.return_value = {"arima": 1000.0, "sarima": 1100.0}
         response = self.client.post(
             "/predict?date=2018-11-20&duration=30&country=Australia"
         )
         assert "data" in response.get_json()
 
     @patch("ai_enterprise_workflow.service.api.model")
-    def test_02_app_predict_total(self, mock_model):
+    def test_02_app_predict_total(self, mock_model: MagicMock) -> None:
         mock_model.return_value = {"arima": 1000.0, "sarima": 1100.0}
         response = self.client.post("/predict?date=2018-11-20&duration=30")
         assert "data" in response.get_json()
 
     @patch("ai_enterprise_workflow.service.api.pd.read_csv")
-    def test_03_app_logs(self, mock_read_csv):
+    def test_03_app_logs(self, mock_read_csv: MagicMock) -> None:
         mock_read_csv.return_value = pd.DataFrame({"type": ["predict"]})
         response = self.client.post("/logs?type=predict")
         assert "data" in response.get_json()
```

### Phase H — `tests/model_test.py`

<!-- pseudodiff: full file replacement -->

```diff
--- a/tests/model_test.py
+++ b/tests/model_test.py
@@ -1,27 +1,33 @@
-import os
-import unittest
-
-from ai_enterprise_workflow.core.config import DIRECTORY_MODELS
-from ai_enterprise_workflow.forecasting.arima import model
-
-_DATA_AVAILABLE = os.path.exists("./data/input/")
-
-
-@unittest.skipIf(not _DATA_AVAILABLE, "requires ./data/input/ — not present in CI")
-class ModelTest(unittest.TestCase):
-    def test_01_model_train(self):
-        model_file = DIRECTORY_MODELS + "arima.pickle"
-        date = "2018-11-20"
-        duration = 30
-        country = None
-        model(date, duration, country)
-        assert os.path.exists(model_file)
-
-    def test_02_model_predict(self):
-        key = "arima"
-        date = "2018-11-20"
-        duration = 30
-        country = None
-        result = model(date, duration, country)
-        assert key in result
+import os
+import shutil
+import tempfile
+import unittest
+from pathlib import Path
+from unittest.mock import patch
+
+from ai_enterprise_workflow.forecasting.arima import model
+
+_FIXTURES = Path(__file__).parent / "fixtures" / "data" / "output"
+
+
+class ModelTest(unittest.TestCase):
+    _tmpdir: str
+    _modeldir: str
+
+    @classmethod
+    def setUpClass(cls) -> None:
+        cls._tmpdir = tempfile.mkdtemp()
+        cls._modeldir = tempfile.mkdtemp()
+        for csv_file in ("3 revenue_country.csv", "4 revenue_total.csv"):
+            shutil.copy(str(_FIXTURES / csv_file), cls._tmpdir + "/" + csv_file)
+
+    @classmethod
+    def tearDownClass(cls) -> None:
+        shutil.rmtree(cls._tmpdir, ignore_errors=True)
+        shutil.rmtree(cls._modeldir, ignore_errors=True)
+
+    def test_01_model_train(self) -> None:
+        with (
+            patch("ai_enterprise_workflow.forecasting.arima.DIRECTORY_OUTPUT", self._tmpdir + "/"),
+            patch("ai_enterprise_workflow.forecasting.arima.DIRECTORY_MODELS", self._modeldir + "/"),
+        ):
+            model("2018-11-20", 30, None)
+        assert os.path.exists(self._modeldir + "/arima.pickle")
+
+    def test_02_model_predict(self) -> None:
+        with (
+            patch("ai_enterprise_workflow.forecasting.arima.DIRECTORY_OUTPUT", self._tmpdir + "/"),
+            patch("ai_enterprise_workflow.forecasting.arima.DIRECTORY_MODELS", self._modeldir + "/"),
+        ):
+            result = model("2018-11-20", 30, None)
+        assert "arima" in result
```

## Failure playbook

| # | Symptom | Likely cause | Remediation | Escalate to |
|---|---------|--------------|-------------|-------------|
| 1 | `uv sync` fails with `scipy-stubs` version conflict | Installed scipy version not covered by stubs version | Pin `scipy-stubs==1.13.1.4` (specific patch matching scipy 1.13.x) | @LinterSpecialist |
| 2 | pyright reports `reportUnknownMemberType` on `data["invoice_id"].apply(_to_digits)` after Phase C | pandas-stubs `.apply()` overload not resolving `_to_digits` return type | Add `# type: ignore[unknown-member]` on that line only; document in roadmap Notes | @LinterSpecialist |
| 3 | pyright reports `reportUnknownMemberType` on `data.groupby(...)["price"].sum()` in `ingestion/pipeline.py` | pandas-stubs groupby chain return type is `Unknown` | Add `# type: ignore[unknown-member]` on that line only | @LinterSpecialist |
| 4 | pyright reports `reportUnknownArgumentType` on statsmodels call inside `train_ARIMA_model` | `ARIMA` is `Any` but pyright cascades Unknown through the call | Wrap call: `cast(Any, ARIMA(data, order=order))` | @LinterSpecialist |
| 5 | `ruff check` fails with `TCH001` or `TCH002` on new `from typing import Any` | ruff wants `TYPE_CHECKING` guard for type-only imports | `Any` is used at runtime in annotations (PEP 563 not active); add `# noqa: TCH001` only if flagged — check ruff config first, `TCH` is not in extend-select | @LinterSpecialist |
| 6 | `ModelTest` SARIMA fit raises `LinAlgError` or `ConvergenceWarning` | Synthetic data with seed 42 converges, but CI environment may differ | Suppress warnings: add `import warnings; warnings.filterwarnings("ignore")` in `setUpClass`; if still fails, reduce SARIMA order to `(1,1,1,30)` via patch | @TestDesigner |
| 7 | `ModelTest` fit takes > 60 s in CI | SARIMA seasonal period 30 slow on CI hardware | Reduce fixture to 120 rows (covers 4 seasonal cycles) and reduce SARIMA seasonal order to `(1,1,1,7)` via a fixture-level patch; file follow-up issue | @TestDesigner |
| 8 | `tach check` fails after adding new import | Impossible given no new cross-layer imports are introduced | Verify no `from ai_enterprise_workflow.X import Y` was accidentally added to a module that violates DAG | @CodeReviewer |
| 9 | `uv run pyright` in strict mode reports errors in `tests/log_test.py` after Phase B | Cascade from annotated `log_*` functions exposing unknown call-site types | Annotate affected test methods with `-> None`; add `MagicMock` typing if mock is used | @LinterSpecialist |
| 10 | `arima_model: Any = pickle.load(file)` triggers `reportRedeclaration` (variable annotated twice in different branches) | pyright sees duplicate `: Any` annotation in if/else branches | Use a single `arima_model: Any` declaration before the if/else block (unbound), then assign without annotation inside each branch | @LinterSpecialist |

## Roadmap

| # | Phase | Owner | Status | Evidence / Notes |
|---|-------|-------|--------|------------------|
| 1 | Phase A — Config & stubs gate | @ProjectDeveloper → @LinterSpecialist | not-started | |
| 2 | Phase B — Annotate `core/logging.py` | @ProjectDeveloper → @LinterSpecialist | not-started | |
| 3 | Phase C — Annotate `ingestion/pipeline.py` | @ProjectDeveloper → @LinterSpecialist, @CodeReviewer | not-started | |
| 4 | Phase D — Annotate `monitoring/drift.py` | @ProjectDeveloper → @LinterSpecialist | not-started | |
| 5 | Phase E — Annotate `forecasting/arima.py` | @ProjectDeveloper → @LinterSpecialist, @CodeReviewer | not-started | |
| 6 | Phase F — Annotate `service/api.py` | @ProjectDeveloper → @LinterSpecialist | not-started | |
| 7 | Phase G — Annotate test mock params | @ProjectDeveloper → @LinterSpecialist | not-started | |
| 8 | Phase H — ModelTest fixture CSVs + unskip | @ProjectDeveloper → @TestDesigner, @CodeReviewer | not-started | |
| 9 | Phase I — Final gate validation | @ProjectDeveloper → @IntegrationChecker | not-started | |
| 10 | MR preparation | @ProjectDeveloper | not-started | |

## Acceptance criteria (mirror)

No GitLab issue supplied; criteria mirrored from GitHub issue #3 and the approved user request.

- [ ] `pyrightconfig.json` has `"typeCheckingMode": "strict"`; `pyright` reports 0 errors, 0 warnings.
- [ ] `[tool.pyright]` section is removed from `pyproject.toml`.
- [ ] All public functions in `core/logging.py`, `ingestion/pipeline.py`, `forecasting/arima.py`, `monitoring/drift.py`, `service/api.py` carry full type annotations (params + return type).
- [ ] `scipy-stubs>=1.13.0.0` is added to `[dependency-groups].dev` in `pyproject.toml`.
- [ ] `statsmodels` imports in `forecasting/arima.py` carry exactly `# type: ignore[import-untyped]`; no other `# type: ignore` suppressions added beyond those already present.
- [ ] `ingestion/pipeline.py` replaces the two `apply(lambda x: re.sub(…))` calls with a named `_to_digits(value: object) -> str` private helper.
- [ ] `service/api.py` route functions return `ResponseReturnValue` (from `flask.typing`).
- [ ] `tests/app_test.py` mock parameters typed as `MagicMock`; all test methods have `-> None`.
- [ ] `pyrightconfig.json` `executionEnvironments` entry for `tests/` no longer suppresses `reportUnknownMemberType`.
- [ ] `tests/fixtures/data/output/4 revenue_total.csv` committed; ≥ 180 rows synthetic daily revenue 2018-06-01 through 2018-11-30 with `date` and `revenue` columns.
- [ ] `tests/fixtures/data/output/3 revenue_country.csv` committed; `country`, `date`, `revenue` columns.
- [ ] `ModelTest::test_01_model_train` and `ModelTest::test_02_model_predict` pass in CI; `@unittest.skipIf` guard removed.
- [ ] `ruff check src/ tests/` and `ruff format --check src/ tests/` exit 0.
- [ ] `tach check` exits 0.
- [ ] `pytest tests/ -v` — all tests pass, no skips for model_test.
- [ ] `CHANGELOG.md` has a new entry documenting the quality hardening changes.

## Manifest changelog

| Timestamp | Actor | Change |
|---|---|---|
| 2026-05-15T12:45:00Z | @IssueTracker | Created GitHub issue #3 and branch `3-quality-hardening-pyright-strict`; initial manifest scaffold (current state, specification, implementation plan, risks). |
| 2026-05-15T13:30:00Z | @ProjectArchitect | Added execution context, decisions log (D1–D8), detailed action plan (phases A–I with execution recipes), proposed diffs (8 files), failure playbook (10 entries), roadmap (10 rows), acceptance criteria mirror, and handover. Effort: S×6, M×3. |

## Handover

**Design phase complete.** The floor is handed over to `@ProjectDeveloper`.

This manifest was authored by a reasoning-class model with the explicit assumption that `@ProjectDeveloper` is an execution-class model. All non-trivial design decisions are pre-resolved in `## Decisions log`; all phase-level instructions are encoded as `#### Execution recipe` sub-blocks; predictable failure modes are covered in `## Failure playbook`. **Do not re-derive design choices.**

`@ProjectDeveloper` must:

1. Treat this manifest as the single source of truth. If a phrase seems to require design judgment, stop and ask the user; do not improvise.
2. Read `## Execution context` before starting and verify every precondition.
3. Execute phases sequentially. For each phase: flip the roadmap row to `in-progress`, run the `Execution recipe` literally, apply the referenced `Proposed diffs` exactly as drafted, run the listed validation commands, then flip the row to `done` with a one-line evidence note.
4. Any deviation from a `Proposed diff` must be recorded in the `Roadmap` `Evidence / Notes` column with justification.
5. On any predictable failure, consult `## Failure playbook` first before improvising or escalating.
6. After the last code phase, hand over to `@DocsReviewer`, then to `@IntegrationChecker` with `docs_mode=skip`.
7. Verify every box in `Acceptance criteria (mirror)` is checked before preparing the merge request.
8. Prepare the MR targeting `develop`; title (summary only): `restore pyright strict-mode compliance and enable ModelTest in CI`; body: `Closes #3`.
9. When the user confirms the MR is merged, re-invoke `@ProjectDeveloper` to set `status: done` and close issue #3.

To start: `@ProjectDeveloper execute manifests/3-quality-hardening-pyright-strict.md`.
To finalize after merge: `@ProjectDeveloper finalize manifests/3-quality-hardening-pyright-strict.md`.
