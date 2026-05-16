---
manifest_version: 1
branch: 15-notebooks-rename-api-rewire
issue: 15
issue_url: https://github.com/andrea-dm/ai-enterprise-workflow-capstone/issues/15
status: design
scope: "notebooks, config"
affects:
  - notebooks/analysis.ipynb
  - notebooks/results.ipynb
  - tach.toml
  - .dockerignore
  - pyrightconfig.json
  - CHANGELOG.md
mr: null
mr_url: null
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
| `ingest` | `ai_enterprise_workflow.ingestion` | `ingest(force: bool = False) -> None` |
| `model` | `ai_enterprise_workflow.forecasting` | `model(date: str, duration: int, country: str \| None) -> dict[str, Any]` |
| `cfg` | `ai_enterprise_workflow.settings` | `Settings` dataclass — exposes `directory_output`, `drift_threshold`, etc. |

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

**Cell 1 — `sys.path` setup**

```python
import sys, pathlib
# Ensure repo root is on sys.path so `ai_enterprise_workflow` resolves
_root = pathlib.Path(__file__).resolve().parents[1] if "__file__" in dir() else pathlib.Path.cwd().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
```

**Cell 2 — CWD guard**

```python
import os, pathlib
# When kernel starts inside notebooks/, move up to repo root
if pathlib.Path.cwd().name == "notebooks":
    os.chdir(pathlib.Path.cwd().parent)
```

### `notebooks/analysis.ipynb` API contract

| Change | Detail |
|---|---|
| Import | `from ai_enterprise_workflow.ingestion import ingest` |
| Import | `from ai_enterprise_workflow.settings import cfg` |
| Data load trigger | `ingest(force=True)` replaces any manual CSV-download cell |
| Path resolution | All `pd.read_csv(...)` calls use `cfg.directory_output / "<filename>.csv"` |
| Remove | `def get_countries(...)` inline definition |
| Remove | `def decompose_data(...)` inline definition |
| Fix | Replace broken raw-text cell with a valid Markdown cell |

### `notebooks/results.ipynb` API contract

| Change | Detail |
|---|---|
| Import | `from ai_enterprise_workflow.forecasting import model` |
| Import | `from ai_enterprise_workflow.settings import cfg` |
| Forecast call | `result = model("2019-10-01", duration=30, country=None)` |
| Drift display | `print(f"Drift score: {result['drift_score']:.4f} (threshold: {cfg.drift_threshold})")` |
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

## Manifest changelog

| Date (UTC)           | Agent          | Change                           |
|----------------------|----------------|----------------------------------|
| 2026-05-16T00:00:00Z | @IssueTracker  | Manifest created from issue #15. |
