---
manifest_version: 1
branch: 15-notebooks-rename-api-rewire
issue: 15
issue_url: https://github.com/andrea-dm/ai-enterprise-workflow-capstone/issues/15
status: done
scope: "notebooks, config"
affects:
  - notebooks/analysis.ipynb
  - notebooks/results.ipynb
  - tach.toml
  - .dockerignore
  - pyrightconfig.json
  - CHANGELOG.md
mr: "#16"
mr_url: https://github.com/andrea-dm/ai-enterprise-workflow-capstone/pull/16
lock: null
---

# rename `nb/` to `notebooks/` and rewire notebooks to use the public `src/` API

## Current state

### Directory

- `nb/` contains two notebooks: `analysis.ipynb` and `results.ipynb`.
- No other source under the repository root refers to `nb/` except the four config files below.

### Config references to `nb`

| File | Line | Current value |
|---|---|---|
| `tach.toml` | 21 | `"nb"` (exclude glob) |
| `.dockerignore` | 4 | `nb/` |
| `pyrightconfig.json` | 13 | `"nb"` (exclude entry) |
| `CHANGELOG.md` | 95 | prose: `Notebooks under \`nb/\` required no edits …` |

### Notebook public-API surface (as of develop HEAD)

| Symbol | Module | Signature |
|---|---|---|
| `ingest` | `ai_enterprise_workflow.ingestion` | `ingest(force: bool = False) -> None` — re-exported via `__all__` in `ingestion/__init__.py` |
| `model` | `ai_enterprise_workflow.forecasting` | `model(date: str, duration: int, country: str \| None) -> dict[str, Any]` — re-exported via `__all__` in `forecasting/__init__.py`; keys: `"arima"`, `"sarima"`, `"drift"` |
| `cfg` | `ai_enterprise_workflow.core.config` | `AppSettings(BaseSettings)` singleton — exposes `directory_output: Path`, `drift_threshold: float` |

### Current notebook defects

**`nb/analysis.ipynb`**
- Constructs raw paths (`'../data/output/'`) instead of using `cfg.directory_output`.
- Defines inline helpers (`def get_countries`, `def decompose_data`) that duplicate logic already in `src/`.
- Does not call `ingest()`; relies on pre-existing CSV files.
- Contains at least one broken raw-text cell.

**`nb/results.ipynb`**
- Does not call `model()`; loads model artifacts manually.
- Displays no drift score; no comparison against `cfg.drift_threshold`.
- Uses raw relative paths for CSV loading.

Neither notebook contains a `sys.path.insert` cell or a CWD guard.

## Specification

### Directory rename

```
git mv nb/ notebooks/
```

Git history (blame) is preserved for both `.ipynb` files.

### Config file changes

| File | Old value | New value |
|---|---|---|
| `tach.toml` L21 | `"nb"` | `"notebooks"` |
| `.dockerignore` L4 | `nb/` | `notebooks/` |
| `pyrightconfig.json` L13 | `"nb"` | `"notebooks"` |
| `CHANGELOG.md` L95 | `Notebooks under \`nb/\`` | `Notebooks under \`notebooks/\`` |

### Bootstrap cells (both notebooks)

**Cell A (first code cell) — CWD guard**

Must run before `sys.path.insert` because `cfg` paths are repo-root-relative.

```python
import os
import pathlib

# VS Code defaults kernel CWD to the notebook folder (notebooks/).
# Move up to repo root so cfg path defaults resolve correctly.
_cwd = pathlib.Path.cwd()
if _cwd.name == "notebooks":
    os.chdir(_cwd.parent)
```

**Cell B (second code cell) — `sys.path` setup**

Inserted AFTER the CWD guard so `pathlib.Path.cwd()` already points to the repo root.

```python
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path.cwd() / "src"))
```

### `notebooks/analysis.ipynb` API contract

| Change | Detail |
|---|---|
| Import | `from ai_enterprise_workflow.ingestion import ingest` |
| Import | `from ai_enterprise_workflow.core.config import cfg` |
| Data load trigger | `ingest(force=True)` replaces any manual CSV-download cell |
| Path resolution | All `pd.read_csv(...)` calls use `cfg.directory_output / "<filename>.csv"` |
| Remove | `def get_countries(...)` inline definition |
| Remove | `def decompose_data(...)` inline definition |
| Fix | Replace broken raw-text cell with a valid Markdown cell |

### `notebooks/results.ipynb` API contract

| Change | Detail |
|---|---|
| Import | `from ai_enterprise_workflow.forecasting import model` |
| Import | `from ai_enterprise_workflow.core.config import cfg` |
| Forecast call | `result = model("2019-10-01", duration=30, country=None)` |
| Drift display | `print(f"drift score: {result['drift']:.6f}  threshold: {cfg.drift_threshold}  warning: {result['drift'] > cfg.drift_threshold}")` |
| Path resolution | All `pd.read_csv(...)` calls use `cfg.directory_output / "<filename>.csv"` |

### Backward compatibility

No `src/` module is modified. The rename is purely filesystem + config. Any consumer that referenced `nb/` via a Git submodule or CI script should update its path, but no such consumer exists in this repository.

## Implementation plan

### Phase I-1 — Directory rename

1. `git mv nb/ notebooks/`
2. Verify `git status` shows both `.ipynb` files as renamed (not deleted+added).

### Phase I-2 — Config file updates

1. Edit `tach.toml` L21: `"nb"` → `"notebooks"`.
2. Edit `.dockerignore` L4: `nb/` → `notebooks/`.
3. Edit `pyrightconfig.json` L13: `"nb"` → `"notebooks"`.
4. Edit `CHANGELOG.md` L95: update prose mention.
5. Run `uv run tach check` — must pass.
6. Run `pyright src/` — must exit 0.

### Phase I-3 — Rewrite `notebooks/analysis.ipynb`

1. Insert bootstrap cells (Cell 1 `sys.path`, Cell 2 CWD guard) at the top.
2. Add imports for `ingest`, `cfg`.
3. Replace manual data-load with `ingest(force=True)`.
4. Replace raw path strings with `cfg.directory_output`-based paths.
5. Delete `def get_countries` and `def decompose_data` cells; replace callers with equivalent `cfg`/API calls.
6. Fix the broken raw-text cell (convert to Markdown cell).
7. Run all cells top-to-bottom; verify no exceptions.

### Phase I-4 — Rewrite `notebooks/results.ipynb`

1. Insert bootstrap cells (Cell 1 `sys.path`, Cell 2 CWD guard) at the top.
2. Add imports for `model`, `cfg`.
3. Replace manual model-loading with `result = model("2019-10-01", duration=30, country=None)`.
4. Add drift-score display cell.
5. Replace raw path strings with `cfg.directory_output`-based paths.
6. Run all cells top-to-bottom; verify no exceptions.

### Phase I-5 — Final validation

1. `ruff check src/ tests/` — must exit 0.
2. `uv run tach check` — must exit 0.
3. `pyright src/` — must exit 0.
4. Confirm `nb/` no longer exists in the working tree.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `git mv` treated as delete+add (history lost) | Low | Low | Verify with `git log --follow notebooks/analysis.ipynb` after move; if history is lost, use `git log --diff-filter=R --summary` to confirm rename detection |
| `ingest(force=True)` downloads data not present in CI | Medium | Medium | Notebooks are excluded from CI test runs; document that notebooks require the raw input JSON files under `data/input/` |
| `model()` signature changes in a future `src/` refactor | Low | Medium | Acceptance criteria pin the exact call signature; any future change to `model()` must update this notebook |
| Broken raw-text cell fix introduces notebook-kernel state dependency | Low | Low | Insert a fresh Markdown cell and delete the broken cell; verify kernel restart + run-all succeeds |
| Config line numbers shift after unrelated merges | Low | Low | Use grep/search rather than hard-coded line numbers during implementation |

---

## Execution context

- **Working directory:** `/home/azureuser/cloudfiles/code/Users/andrea.del_monaco/capstone` (repo root)
- **Active branch:** `15-notebooks-rename-api-rewire`
- **Base branch:** `develop`
- **Python version:** 3.12
- **Validation commands** (in priority order):
  ```bash
  /anaconda/envs/ai/bin/python -m ruff check src/ tests/
  /anaconda/envs/ai/bin/python -m pyright src/
  /anaconda/envs/ai/bin/python -m tach check
  /anaconda/envs/ai/bin/python -m pytest tests/ -q -p no:tach
  ```
- **Tooling preconditions:**
  - `nb/` must still exist on the working tree before Phase I-1 (the branch was created before the rename).
  - `data/input/` must contain the 26 invoice JSON files (required by `ingest(force=True)` when notebooks are executed interactively — not required for quality gates).
  - No uncommitted changes on the branch before starting.
- **Files in scope (allow-list):**

  | File | Action |
  |---|---|
  | `nb/` → `notebooks/` | `git mv` (rename) |
  | `notebooks/analysis.ipynb` | Full rewrite (14 cells) |
  | `notebooks/results.ipynb` | Full rewrite (10 cells) |
  | `tach.toml` | One-line edit: `"nb"` → `"notebooks"` |
  | `.dockerignore` | One-line edit: `nb/` → `notebooks/` |
  | `pyrightconfig.json` | One-line edit: `"nb"` → `"notebooks"` |
  | `CHANGELOG.md` | One-line prose update at line 95 |

- **Files explicitly out of scope:** all `src/` modules, `tests/`, `pyproject.toml`, `mkdocs.yml`, `manifests/` (historical prose).

---

## Decisions log

### D1 — CWD guard before `sys.path.insert`
- **Chosen:** Cell A = `os.chdir` guard; Cell B = `sys.path.insert(0, str(pathlib.Path.cwd() / "src"))` — order reflected in Diffs 5–6.
- **Rejected:** `sys.path.insert` first then CWD guard — would compute `pathlib.Path.cwd() / "src"` before CWD is normalised, resolving to `notebooks/src/` which does not exist.
- **Rationale:** `cfg` defaults use repo-root-relative paths; CWD must be repo root before any `from ai_enterprise_workflow...` import is attempted.
- **Locked:** yes.

### D2 — `ingest` import path
- **Chosen:** `from ai_enterprise_workflow.ingestion import ingest` — `ingestion/__init__.py` re-exports `ingest` in `__all__`.
- **Rejected:** `from ai_enterprise_workflow.ingestion.pipeline import ingest` — more fragile; bypasses the public package boundary.
- **Rationale:** `__init__.py` confirms `__all__ = ["ingest"]`; the short import is the intended public API.
- **Locked:** yes.

### D3 — `model` import path
- **Chosen:** `from ai_enterprise_workflow.forecasting import model` — `forecasting/__init__.py` re-exports `model` in `__all__`.
- **Rejected:** `from ai_enterprise_workflow.forecasting.arima import model` — bypasses public boundary.
- **Rationale:** Same pattern as D2; `__all__ = ["model"]` confirmed in source.
- **Locked:** yes.

### D4 — `cfg` import path
- **Chosen:** `from ai_enterprise_workflow.core.config import cfg` — the singleton defined in `core/config.py`.
- **Rejected:** `from ai_enterprise_workflow.settings import cfg` — this module does not exist; the `@IssueTracker` scaffold used the wrong path.
- **Rationale:** Source evidence: `cfg = AppSettings()` at bottom of `core/config.py`.
- **Locked:** yes.

### D5 — drift result key
- **Chosen:** `result["drift"]` — the `model()` return dict has keys `"arima"`, `"sarima"`, `"drift"` per `forecasting/arima.py` docstring and test mocks.
- **Rejected:** `result["drift_score"]` — the `@IssueTracker` scaffold used the wrong key; no such key exists in the dict.
- **Rationale:** Evidence from `tests/service/test_api.py` mock return values: `{"arima": 1.0, "sarima": 1.1, "drift": 0.05}`.
- **Locked:** yes.

### D6 — `ingest(force=True)` vs `force=False`
- **Chosen:** `force=True` — per user approval at Stage 0 intake.
- **Rejected:** `force=False` — idempotent but means the notebook silently skips ingestion if CSVs already exist, making it harder to use as a demonstration notebook.
- **Rationale:** User explicitly approved `force=True`; notebooks serve as authoritative end-to-end demonstrations.
- **Locked:** yes.

### D7 — forecast reference date and parameters
- **Chosen:** `model("2019-10-01", duration=30, country=None)` — per user approval at Stage 0 intake.
- **Rejected:** no alternatives considered; user confirmed this as correct.
- **Rationale:** Date leaves ~2 months of 2019 data as a holdout window within the 2017–2019 dataset range.
- **Locked:** yes.

### D8 — `get_countries` / `decompose_data` helpers
- **Chosen:** Delete both helper-function cells entirely.
- **Rejected:** Replace `get_countries` call with `revenue_total["country"].unique()` — `4 revenue_total.csv` has no `country` column (it is an aggregated total); the helper was vestigial.
- **Rationale:** `calculate_revenue_total` groups by `date` only; the country dimension is stripped. Retaining any reference to the deleted function would cause a `NameError`.
- **Locked:** yes.

---

## Detailed action plan

### Phase I-1 — `git mv nb/ notebooks/`  `[effort: S]`  `[mandatory: none; optional: none]`

Rename the notebook directory, preserving git history for both `.ipynb` files.

#### Execution recipe

1. **Pre-checks.**
   ```bash
   ls nb/        # must list analysis.ipynb and results.ipynb
   git status    # must be clean
   ```
2. **Apply diffs.** No diff file — execute directly:
   ```bash
   git mv nb notebooks
   ```
3. **Post-edit commands.** None.
4. **Validation.**
   ```bash
   git status    # → renamed: nb/analysis.ipynb -> notebooks/analysis.ipynb (etc.)
   ls notebooks/ # → analysis.ipynb  results.ipynb
   ```
   Expected: two `renamed:` lines in `git status`, no `deleted:`/`new file:` entries.
5. **Definition of Done.**
   - [x] `nb/` no longer exists.
   - [x] `notebooks/analysis.ipynb` and `notebooks/results.ipynb` exist.
   - [x] `git log --follow notebooks/analysis.ipynb` shows prior commits (history preserved).
6. **Delegation directives.** None — mechanical shell command.
7. **Stop conditions.** If `git status` shows `deleted:` + `new file:` instead of `renamed:`, git rename detection failed. Undo with `git mv notebooks nb` and retry with a `git add -A` approach.

---

### Phase I-2 — Config file updates  `[effort: S]`  `[mandatory: @LinterSpecialist; optional: none]`

Update four files that reference `nb` or `nb/` with the new `notebooks` path.

#### Execution recipe

1. **Pre-checks.** Phase I-1 complete. `nb/` no longer exists.
2. **Apply diffs.** Apply **Diff 1 — `tach.toml`**, **Diff 2 — `.dockerignore`**, **Diff 3 — `pyrightconfig.json`**, **Diff 4 — `CHANGELOG.md`** (all in `## Proposed diffs`).
3. **Post-edit commands.** None (no formatter applies to these files).
4. **Validation.**
   ```bash
   /anaconda/envs/ai/bin/python -m tach check
   # Expected: ✅ All modules validated!

   /anaconda/envs/ai/bin/python -m pyright src/
   # Expected: 0 errors, 0 warnings, 0 informations

   grep -r '"nb"' tach.toml pyrightconfig.json .dockerignore
   # Expected: no output (all references replaced)
   ```
5. **Definition of Done.**
   - [x] `tach check` exits 0.
   - [x] `pyright src/` exits 0.
   - [x] `grep -r '"nb"' tach.toml pyrightconfig.json .dockerignore` returns nothing.
   - [x] `CHANGELOG.md` line 95 contains `notebooks/` (not `nb/`).
6. **Delegation directives.** `@LinterSpecialist`: *"Run `tach check` and `pyright src/` after Diffs 1–4. Confirm both exit 0. Attach output."*
7. **Stop conditions.** Halt if `tach check` fails with a new violation — a config line number may have shifted; re-read `tach.toml` and re-apply.

---

### Phase I-3 — Rewrite `notebooks/analysis.ipynb`  `[effort: M]`  `[mandatory: @DocsReviewer; optional: @CodeReviewer]`

Replace all 16 original cells with 14 new cells that use the public `src/` API.

#### Execution recipe

1. **Pre-checks.** Phases I-1 and I-2 complete. `notebooks/analysis.ipynb` exists.
2. **Apply diffs.** Apply **Diff 5 — `notebooks/analysis.ipynb`** (pseudodiff; full cell content in `## Proposed diffs`). Use the notebook editor to replace cells.
3. **Post-edit commands.** None (notebooks are not ruff-formatted).
4. **Validation.** Execute the notebook top-to-bottom with the Jupyter kernel CWD at the repo root:
   ```bash
   cd /home/azureuser/cloudfiles/code/Users/andrea.del_monaco/capstone
   PYTHONPATH=src /anaconda/envs/ai/bin/jupyter nbconvert \
     --to notebook --execute \
     --ExecutePreprocessor.timeout=300 \
     notebooks/analysis.ipynb \
     --output /tmp/analysis_executed.ipynb 2>&1 | tail -5
   ```
   Expected: `[NbConvertApp] Writing ... notebook(s) to /tmp/analysis_executed.ipynb` with no `ERROR` lines.
5. **Definition of Done.**
   - [x] No cell contains a raw string path (`'../data/output/'` or `"../data/output/"`).
   - [x] No cell contains `def get_countries` or `def decompose_data`.
   - [x] Cell containing `ingest(force=True)` is present.
   - [x] All CSV paths use `cfg.directory_output / "..."`.
   - [x] `grep -n "def get_countries\|def decompose_data\|directory_output = " notebooks/analysis.ipynb` returns nothing.
   - [x] Notebook executes top-to-bottom without error.
6. **Delegation directives.** `@DocsReviewer`: *"Read `notebooks/analysis.ipynb`. Verify each Markdown cell heading is accurate. Confirm `ingest(force=True)` and `cfg.directory_output` are used. Flag any raw path strings. Attach review note."*
7. **Stop conditions.** Halt if `nbconvert --execute` exits non-zero — check whether `data/input/` is populated and `data/output/` is writable. If `ImportError: ai_enterprise_workflow`, confirm the CWD guard fired before `sys.path.insert`.

---

### Phase I-4 — Rewrite `notebooks/results.ipynb`  `[effort: M]`  `[mandatory: @DocsReviewer; optional: @CodeReviewer]`

Replace all 7 original cells with 10 new cells that call `model()` and display the drift score.

#### Execution recipe

1. **Pre-checks.** Phase I-3 complete (ensures `ingest()` has already written `data/output/` CSVs).
2. **Apply diffs.** Apply **Diff 6 — `notebooks/results.ipynb`** (pseudodiff; full cell content in `## Proposed diffs`).
3. **Post-edit commands.** None.
4. **Validation.**
   ```bash
   cd /home/azureuser/cloudfiles/code/Users/andrea.del_monaco/capstone
   PYTHONPATH=src /anaconda/envs/ai/bin/jupyter nbconvert \
     --to notebook --execute \
     --ExecutePreprocessor.timeout=900 \
     notebooks/results.ipynb \
     --output /tmp/results_executed.ipynb 2>&1 | tail -5
   ```
   Expected: execution completes (allow up to 15 min for first-run model training); no `ERROR` lines.
5. **Definition of Done.**
   - [x] Cell containing `result = model("2019-10-01", duration=30, country=None)` is present.
   - [x] Cell containing `result["drift"]` is present and prints the drift score.
   - [x] All CSV paths use `cfg.directory_output / "..."`.
   - [x] `grep -n "directory_output = " notebooks/results.ipynb` returns nothing.
   - [x] Notebook executes top-to-bottom without error.
6. **Delegation directives.** `@DocsReviewer`: *"Read `notebooks/results.ipynb`. Verify `model()` is called with the approved args. Confirm drift score display uses `result['drift']` (not `result['drift_score']`). Attach review note."*
7. **Stop conditions.** Halt if `model()` raises `FileNotFoundError` on revenue CSVs — run `ingest(force=True)` interactively first (Phase I-3 must have written `data/output/`). If model training hangs beyond 15 min, check available memory.

---

## Proposed diffs

### Diff 1 — `tach.toml`

*Phase I-2. Rename exclude entry.*

```diff
--- a/tach.toml
+++ b/tach.toml
@@ -18,7 +18,7 @@
 source_roots = ["src"]
 exclude = [
     "tests",
-    "nb",
+    "notebooks",
     "**/__pycache__",
 ]
```

---

### Diff 2 — `.dockerignore`

*Phase I-2. Rename exclude entry.*

```diff
--- a/.dockerignore
+++ b/.dockerignore
@@ -1,7 +1,7 @@
 .git/
 .venv/
 tests/
-nb/
+notebooks/
 manifests/
 __pycache__/
 *.pyc
```

---

### Diff 3 — `pyrightconfig.json`

*Phase I-2. Rename exclude entry.*

```diff
--- a/pyrightconfig.json
+++ b/pyrightconfig.json
@@ -8,7 +8,7 @@
   "exclude": [
     ".venv",
     "**/__pycache__",
     "**/node_modules",
     "**/.*",
-    "nb"
+    "notebooks"
   ],
```

---

### Diff 4 — `CHANGELOG.md`

*Phase I-2. Update prose mention.*

```diff
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -93,7 +93,7 @@
 - Runtime + dev dependencies rationalized to capstone's actual stack
   (`flask`, `pandas`, `numpy`, `scipy`, `statsmodels`, `tqdm`, `matplotlib`).

 ### Notes

-- Notebooks under `nb/` required no edits (verified zero `from src` refs).
+- Notebooks under `notebooks/` required no edits at the time of the slice-1 restructure (verified zero `from src` refs); rewired to use the public API in issue #15.
 - `monitoring/drift.py` retained verbatim; runtime wiring deferred to a later slice.
```

---

### Diff 5 — `notebooks/analysis.ipynb` (REWRITE)

*Phase I-3. Complete cell-by-cell replacement. Mark as pseudodiff.*

<!-- pseudodiff -->

**Target file:** `notebooks/analysis.ipynb`
**Final cell count:** 14 cells (6 Markdown + 8 Code)
**Constraint:** Do not add any `import` outside the designated import cells. Do not define any functions.

| # | Type | Exact content |
|---|---|---|
| 1 | Markdown | (see below) |
| 2 | Code | CWD guard (see below) |
| 3 | Code | `sys.path` + stdlib imports (see below) |
| 4 | Markdown | `## 1. Ingestion` note |
| 5 | Code | `ingest(force=True)` |
| 6 | Code | load `revenue_total` + `.head()` |
| 7 | Markdown | `## 2. Revenue over time` |
| 8 | Code | plot revenue |
| 9 | Markdown | `## 3. STL decomposition — trend and seasonal components (LOESS)` |
| 10 | Code | STL fit + plot |
| 11 | Markdown | `## 4. Stationarity — Augmented Dickey-Fuller test` |
| 12 | Code | `adfuller` + print result |
| 13 | Markdown | `## 5. Autocorrelation and partial autocorrelation` |
| 14 | Code | `plot_acf` + `plot_pacf` |

**Exact cell content:**

**Cell 1 (Markdown):**
```markdown
# Exploratory Data Analysis

End-to-end EDA notebook for the AI Enterprise Workflow capstone.
Drives the full ingestion pipeline via `ingest(force=True)`, then
analyses the aggregated daily revenue time series using STL
decomposition, an Augmented Dickey-Fuller stationarity test, and
autocorrelation / partial-autocorrelation plots.

**Prerequisites:** raw invoice JSON files must exist under `data/input/`.
```

**Cell 2 (Code — CWD guard):**
```python
import os
import pathlib

# Ensure the kernel runs from the repo root so cfg paths resolve correctly.
# VS Code defaults the kernel CWD to the notebook folder (notebooks/).
_cwd = pathlib.Path.cwd()
if _cwd.name == "notebooks":
    os.chdir(_cwd.parent)
```

**Cell 3 (Code — imports):**
```python
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path.cwd() / "src"))

import pandas as pd
from matplotlib import pyplot as plt
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.stattools import adfuller

from ai_enterprise_workflow.core.config import cfg
from ai_enterprise_workflow.ingestion import ingest

%matplotlib inline
```

**Cell 4 (Markdown):**
```markdown
## 1. Ingestion

Run the full ingestion pipeline. `force=True` always re-reads the raw
JSON files and overwrites any existing output CSVs.
```

**Cell 5 (Code):**
```python
ingest(force=True)
```

**Cell 6 (Code):**
```python
revenue_total = pd.read_csv(cfg.directory_output / "4 revenue_total.csv")
revenue_total.head()
```

**Cell 7 (Markdown):**
```markdown
## 2. Revenue over time
```

**Cell 8 (Code):**
```python
revenue_total.plot(x="date", y="revenue", legend=False)
plt.show()
```

**Cell 9 (Markdown):**
```markdown
## 3. STL decomposition — trend and seasonal components (LOESS)
```

**Cell 10 (Code):**
```python
stl = STL(revenue_total["revenue"], period=30)
stl.fit().plot()
plt.show()
```

**Cell 11 (Markdown):**
```markdown
## 4. Stationarity — Augmented Dickey-Fuller test

Tests whether the revenue time series has a unit root (non-stationary).
A *p*-value < 0.05 rejects the null hypothesis of a unit root.
```

**Cell 12 (Code):**
```python
adfuller_results = adfuller(revenue_total["revenue"])
if adfuller_results[1] < 0.05:
    print("Data is stationary (p =", round(adfuller_results[1], 6), ")")
else:
    print("Data is not stationary (p =", round(adfuller_results[1], 6), ")")
```

**Cell 13 (Markdown):**
```markdown
## 5. Autocorrelation and partial autocorrelation
```

**Cell 14 (Code):**
```python
plot_acf(revenue_total["revenue"])
plt.show()

plot_pacf(revenue_total["revenue"])
plt.show()
```

---

### Diff 6 — `notebooks/results.ipynb` (REWRITE)

*Phase I-4. Complete cell-by-cell replacement. Mark as pseudodiff.*

<!-- pseudodiff -->

**Target file:** `notebooks/results.ipynb`
**Final cell count:** 10 cells (4 Markdown + 6 Code)
**Constraint:** `result["drift"]` must be used (not `result["drift_score"]`). `model()` must be called with exactly `("2019-10-01", duration=30, country=None)`.

| # | Type | Exact content |
|---|---|---|
| 1 | Markdown | heading + training-time warning |
| 2 | Code | CWD guard |
| 3 | Code | `sys.path` + stdlib imports + package imports |
| 4 | Markdown | `## 1. Run forecast` |
| 5 | Code | `result = model(...)` |
| 6 | Markdown | `## 2. Drift score` |
| 7 | Code | print drift score + threshold |
| 8 | Code | load `5 predictions.csv` |
| 9 | Markdown | `## 3. Predictions vs actuals` |
| 10 | Code | plot |

**Exact cell content:**

**Cell 1 (Markdown):**
```markdown
# Forecast Results

Runs the ARIMA/SARIMA forecasting pipeline via `model()`, displays
the predicted revenue totals and Wasserstein drift score, and plots
the historical vs forecast series.

> **Note:** The first run trains ARIMA and SARIMA models on the full
> 2017–2019 dataset. This may take **2–10 minutes** on CPU.
> Subsequent runs load cached pickle files and complete in seconds.

**Prerequisites:** `data/input/` must contain the raw invoice JSON
files (or run `analysis.ipynb` first to populate `data/output/`).
```

**Cell 2 (Code — CWD guard):**
```python
import os
import pathlib

_cwd = pathlib.Path.cwd()
if _cwd.name == "notebooks":
    os.chdir(_cwd.parent)
```

**Cell 3 (Code — imports):**
```python
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path.cwd() / "src"))

import pandas as pd
from matplotlib import pyplot as plt

from ai_enterprise_workflow.core.config import cfg
from ai_enterprise_workflow.forecasting import model

%matplotlib inline
```

**Cell 4 (Markdown):**
```markdown
## 1. Run forecast

Calls `model()` with `date="2019-10-01"` and `duration=30`.
Returns a dict with keys `"arima"`, `"sarima"`, and `"drift"`.
```

**Cell 5 (Code):**
```python
# NOTE: first run may take several minutes while models are trained.
result = model("2019-10-01", duration=30, country=None)
print(result)
```

**Cell 6 (Markdown):**
```markdown
## 2. Drift score
```

**Cell 7 (Code):**
```python
drift_score = result["drift"]
print(f"drift score    : {drift_score:.6f}")
print(f"drift threshold: {cfg.drift_threshold}")
print(f"drift warning  : {drift_score > cfg.drift_threshold}")
```

**Cell 8 (Code):**
```python
revenue_predictions = pd.read_csv(cfg.directory_output / "5 predictions.csv")
revenue_predictions.head()
```

**Cell 9 (Markdown):**
```markdown
## 3. Predictions vs actuals
```

**Cell 10 (Code):**
```python
revenue_predictions[["revenue", "forecast_arima", "forecast_sarima"]].plot()
plt.show()
```

---

## Failure playbook

| # | Symptom | Likely cause | Remediation | Escalate to |
|---|---------|--------------|-------------|-------------|
| 1 | `git status` after `git mv` shows `deleted:` + `new file:` instead of `renamed:` | Git rename similarity threshold not met (unlikely for `.ipynb`) | Run `git add -A && git status` — git may still detect the rename during staging | @ProjectDeveloper |
| 2 | `tach check` fails after I-2 | `"notebooks"` string not written correctly in `tach.toml` | Re-read `tach.toml` and confirm exact string; re-apply Diff 1 | @LinterSpecialist |
| 3 | `pyright src/` regression after I-2 | Unrelated — `pyrightconfig.json` edit accidentally corrupted JSON | Validate JSON: `python3 -m json.tool pyrightconfig.json`; re-apply Diff 3 | @LinterSpecialist |
| 4 | `ImportError: No module named 'ai_enterprise_workflow'` in notebook | CWD guard did not fire before `sys.path.insert`, so `src/` path is wrong | Confirm Cell 2 (CWD guard) runs before Cell 3 (`sys.path.insert`); restart kernel and re-run top-to-bottom | @CodeReviewer |
| 5 | `FileNotFoundError: data/output/...` during `ingest()` | CWD is not repo root — `cfg.directory_output` resolves to wrong path | Add `print(pathlib.Path.cwd())` in Cell 2 to confirm CWD; re-check CWD guard | @CodeReviewer |
| 6 | `model()` raises `FileNotFoundError` on `4 revenue_total.csv` | `ingest()` was not run (or I-3 was skipped) | Run `ingest(force=True)` interactively; confirm `data/output/4 revenue_total.csv` exists | @ProjectDeveloper |
| 7 | `KeyError: 'drift'` in Cell 7 of `results.ipynb` | `model()` return dict does not contain `"drift"` key | Inspect `print(result.keys())`; if missing, check that issue #9 is in the base branch | @CodeReviewer |
| 8 | `nbconvert --execute` times out on `results.ipynb` | First-run ARIMA+SARIMA training exceeds 15 min (e.g., very slow CPU) | Increase `--ExecutePreprocessor.timeout=1800`; or run interactively in VS Code | @ProjectDeveloper |
| 9 | `grep` still finds `"nb"` in a config file after I-2 | One diff was not applied | Re-apply the missed diff; re-run `grep -r '"nb"' tach.toml pyrightconfig.json .dockerignore` | @LinterSpecialist |
| 10 | `plot_acf` / `plot_pacf` raises `ValueError: x is constant` | Revenue total column all zeros — `ingest()` wrote empty data | Check `data/input/` contains all 26 JSON files; re-run `ingest(force=True)` | @ProjectDeveloper |

---

## Roadmap

| # | Phase | Owner | Status | Evidence / Notes |
|---|-------|-------|--------|------------------|
| 1 | Phase I-1 — `git mv nb/ notebooks/` | @ProjectDeveloper | done | `renamed: nb/analysis.ipynb -> notebooks/analysis.ipynb`, `renamed: nb/results.ipynb -> notebooks/results.ipynb` — two renamed entries, no deleted/new-file entries |
| 2 | Phase I-2 — config file updates | @ProjectDeveloper → @LinterSpecialist | done | Diffs 1–4 applied; `tach check` ✅, `pyright src/` 0 errors; `grep '"nb"' tach.toml pyrightconfig.json .dockerignore` empty |
| 3 | Phase I-3 — rewrite `analysis.ipynb` | @ProjectDeveloper → @DocsReviewer | done | 14 cells written per Diff 5; no raw paths, no inline defs, `ingest(force=True)` present, `cfg.directory_output` used |
| 4 | Phase I-4 — rewrite `results.ipynb` | @ProjectDeveloper → @DocsReviewer | done | 10 cells written per Diff 6; no raw paths, `model("2019-10-01", 30, None)` call present, `result["drift"]` correct key used, `cfg.directory_output` used |
| 5 | Documentation pass | @DocsReviewer | done | PASS — both notebooks, all 5 checks (headings, no raw paths, API usage, CWD guard order, prerequisites note) |
| 6 | Integration gate | @IntegrationChecker (`docs_mode=skip`) | done | GO — G0–G6 all pass; 43 tests passed, 0 ruff/pyright/tach violations |
| 7 | MR preparation | @ProjectDeveloper | done | PR #16 merged 2026-05-16 by andrea-dm; issue #15 closed manually (PR targeted develop, not main) |

**Effort summary:** S×2, M×2 — total estimated complexity: Small-Medium. No XL phases.

---

## Acceptance criteria (mirror)

*Mirrored verbatim from GitHub issue #15.*

- [x] `nb/` directory no longer exists; `notebooks/` directory contains both `.ipynb` files.
- [x] `tach check` passes with `notebooks/` in the exclude list.
- [x] `pyright src/` exits 0 (no regressions).
- [x] `notebooks/analysis.ipynb` contains no raw string paths (`'../data/output/'`); all paths use `cfg.directory_output`.
- [x] `notebooks/analysis.ipynb` calls `ingest(force=True)` from `ai_enterprise_workflow.ingestion`.
- [x] `notebooks/analysis.ipynb` contains no inline function definitions (`def get_countries`, `def decompose_data`).
- [x] `notebooks/results.ipynb` calls `model("2019-10-01", duration=30, country=None)` from `ai_enterprise_workflow.forecasting`.
- [x] `notebooks/results.ipynb` displays the drift score from `model()` output and compares it to `cfg.drift_threshold`.
- [x] Both notebooks contain a `sys.path.insert` cell and a CWD guard cell (`os.chdir` to repo root when kernel starts in `notebooks/`).
- [x] `ruff check src/ tests/` exits 0 (no side effects from config changes).

---

## Handover

**Design phase complete.** The floor is handed over to `@ProjectDeveloper`.

This manifest was authored by a reasoning-class model with the explicit assumption that `@ProjectDeveloper` is an execution-class model. All non-trivial design decisions are pre-resolved in `## Decisions log`; all phase-level instructions are encoded as `#### Execution recipe` sub-blocks; predictable failure modes are covered in `## Failure playbook`. **Do not re-derive design choices.**

`@ProjectDeveloper` must:

1. Treat this manifest as the single source of truth. If a phrase in the manifest seems to require a design judgment, stop and ask the user; do not improvise.
2. Read `## Execution context` before starting and verify every precondition.
3. Execute phases **in order: I-1 → I-2 → I-3 → I-4**. For each phase: flip the roadmap row to `in-progress`, run the `Execution recipe` literally, apply the referenced `Proposed diffs` exactly as drafted, run the listed validation commands, then flip the row to `done` with a one-line evidence note.
4. Phases I-3 and I-4 use **pseudodiffs** — implement the exact cell content as specified in `## Proposed diffs` § Diffs 5–6. Do not add cells, rename headings, or change import paths.
5. On any predictable failure, consult `## Failure playbook` first before improvising or escalating.
6. After Phase I-4, hand over to `@DocsReviewer`, then to `@IntegrationChecker` with `docs_mode=skip`.
7. Verify every box in `Acceptance criteria (mirror)` is checked before preparing the MR.
8. Prepare the MR targeting `develop` with title matching `## Acceptance criteria` issue #15. Include `Closes #15` in the MR body.

To start: `@ProjectDeveloper execute manifests/15-notebooks-rename-api-rewire.md`.
To finalize after merge: `@ProjectDeveloper finalize manifests/15-notebooks-rename-api-rewire.md`.

---

## Manifest changelog

| Timestamp | Actor | Change |
|---|---|---|
| 2026-05-16T00:00:00Z | @IssueTracker | Initial scaffold — issue #15, branch created, manifest bootstrapped |
| 2026-05-16T18:30:00Z | @ProjectArchitect | Fixed scaffold errors (cfg module path D4, drift key D5, CWD/sys.path order D1); added Execution context, Decisions log (D1–D8), Detailed action plan (Phases I-1–I-4 with effort tags and Execution recipes), Proposed diffs (Diffs 1–6), Failure playbook (10 entries), Roadmap, Acceptance criteria mirror, Handover. |
| 2026-05-16T20:00:00Z | @ProjectDeveloper | Executed Phases I-1–I-4; smoke tests PASS; @DocsReviewer PASS; @IntegrationChecker GO (43 tests, 0 violations); 4 split commits; opened PR #16 targeting develop. Deviation: removed `notebooks/` from `.gitignore` (generic template entry was blocking git add on tracked files — recorded in repo lessons). |
| 2026-05-16T20:30:00Z | @ProjectDeveloper | Stage 7 finalization: PR #16 verified MERGED (2026-05-16T18:12:08Z, by andrea-dm); issue #15 closed manually (GitHub does not auto-close when PR targets develop); manifest status set to done. |
