---
manifest_version: 1
branch: 5-harden-docker-flask-production
issue: 5
issue_url: https://github.com/andrea-dm/ai-enterprise-workflow-capstone/issues/5
host: github
repository: andrea-dm/ai-enterprise-workflow-capstone
scope: docker-flask-production-hardening
lock: "@ProjectDeveloper/2026-05-15T00:00:00Z"
mr: null
mr_url: null
status: in-progress
---

# Harden Docker image and Flask service for production readiness

## Current state

- **Dockerfile** (`python:3.12-slim`): builds and runs correctly but
  runs as `root`, has no `.dockerignore`, no health check, uses Flask's
  Werkzeug development server via `CMD ["python", "run.py"]`, and does
  not `pip install .` — the package is only importable because Python
  adds CWD to `sys.path`, which Gunicorn's WSGI import path does not.
- **`start.sh`**: correctly builds and runs the container with `-it
  --rm`, but does not mount host directories for mutable state
  (`data/`, `models/`, `logs/`). Every container restart loses logs
  and trained models.
- **`api.py`** (L10–L11): hardcodes `app.config["DEBUG"] = True`,
  leaking tracebacks in production. No liveness probe endpoint exists.
- **`run.py`**: local dev entry-point using Flask's built-in server.
  Already guarded with `if __name__ == "__main__"`. No changes needed.
- **`requirements.txt`**: Docker-only dependency list; does not include
  a WSGI server.
- **`.dockerignore`**: does not exist. `COPY . .` bakes `.git/`,
  `tests/`, `nb/`, `manifests/`, `__pycache__/` into the image —
  inflating size and leaking source.

## Specification

Implement 7 enhancements (all independently testable) to bring the
containerized service closer to production-grade:

1. Create a `.dockerignore` to exclude dev artefacts from the image.
2. Add `gunicorn>=23.0` to `requirements.txt` (Docker-only).
3. Add `RUN pip install --no-cache-dir .` to Dockerfile so the package
   is importable by Gunicorn.
4. Add defensive `mkdir + chown` for data dirs inside the container.
5. Add a non-root `appuser` in the Dockerfile.
6. Add a `HEALTHCHECK` instruction using Python `urllib` (no curl in
   slim image).
7. Replace `CMD` with Gunicorn (2 workers, overridable via
   `WEB_CONCURRENCY`).
8. Add a `GET /healthz` endpoint in `api.py` for liveness probes.
9. Drive `DEBUG` from the `FLASK_DEBUG` env var instead of hardcoding
   `True`.
10. Add a test for `/healthz`.
11. Add volume bind-mounts for `data/`, `models/`, `logs/` in
    `start.sh`.

## Implementation plan

Six file-scoped phases, executed sequentially. Infrastructure files
first (minimal risk), then application code, then tests, then
Dockerfile (highest blast radius), then `start.sh`.

1. Phase 1: `.dockerignore` (new file)
2. Phase 2: `requirements.txt` (add gunicorn)
3. Phase 3: `api.py` (import os, DEBUG env var, /healthz endpoint)
4. Phase 4: `test_api.py` (add healthz test)
5. Phase 5: `Dockerfile` (pip install ., mkdir+chown, useradd,
   HEALTHCHECK, gunicorn CMD)
6. Phase 6: `start.sh` (volume mounts)

## Risks

- **R1** — Without `pip install .`, Gunicorn cannot import
  `ai_enterprise_workflow.service:app`. The current `CMD ["python",
  "run.py"]` works only because Python auto-adds CWD to `sys.path`.
  Mitigated by adding `RUN pip install --no-cache-dir .` after
  `COPY . .` (Phase 5).
- **R2** — Non-root `appuser` may lack write permission to `/app/data`,
  `/app/models`, `/app/logs` if volumes are not mounted. Mitigated by
  `mkdir -p` + `chown` before `USER appuser` (Phase 5).
- **R3** — `python:3.12-slim` does not ship `curl`. HEALTHCHECK uses
  Python `urllib.request` instead (Phase 5).
- **R4** — Gunicorn does not run on Windows. Acceptable: Docker is the
  deployment target; local dev uses `run.py` (Flask dev server).
- **R5** — Gunicorn `>=23.0` may not yet be published on PyPI. Verify
  during implementation; fall back to `>=22.0` if needed.

## Execution context

- **Working directory:** repo root
  (`/home/azureuser/cloudfiles/code/Users/andrea.del_monaco/capstone`).
- **Active branch:** `5-harden-docker-flask-production`.
- **Base branch:** `develop`.
- **Python version:** 3.12 (`pyproject.toml` `requires-python = ">=3.12"`).
- **Validation commands** (priority order):
  1. `uv run ruff check src/ai_enterprise_workflow/service/api.py`
  2. `uv run ruff format --check src/ai_enterprise_workflow/service/api.py`
  3. `uv run pyright src/ai_enterprise_workflow/service/api.py`
  4. `uv run ruff check tests/service/test_api.py`
  5. `uv run pyright tests/service/test_api.py`
  6. `uv run pytest tests/service/test_api.py -p no:tach -p no:cov -v`
     → 9 passed (8 existing + 1 new).
  7. `docker build -t capstone .` → exits 0 (optional; depends on
     Docker daemon availability).
- **Tooling preconditions:**
  - `uv` installed and synced (`uv sync --group dev`).
  - Docker daemon running (for Phase 5 build validation only — optional
    if CI handles it).
- **Files in scope:**
  - `.dockerignore` (new)
  - `Dockerfile`
  - `requirements.txt`
  - `src/ai_enterprise_workflow/service/api.py`
  - `tests/service/test_api.py`
  - `start.sh`
- **Files explicitly out of scope:**
  - `run.py` — no changes needed; already correct.
  - `pyproject.toml` — gunicorn is Docker-only (Decision D1).
  - `src/ai_enterprise_workflow/service/__init__.py` — already exports
    `app`; no changes needed.
  - `manifests/` — only this file.

## Decisions log

### D1 — Gunicorn scope: Docker-only dependency

- **Chosen:** Add `gunicorn>=23.0` to `requirements.txt` only. Do not
  add to `pyproject.toml` `[project].dependencies`.
  Reflected in: Phase 2 diff (P2).
- **Rejected:**
  - Add to both `requirements.txt` and `pyproject.toml` — user decided
    against; gunicorn is a deployment concern.
- **Rationale:** Keeps `pyproject.toml` minimal; local dev uses
  `run.py` which does not import gunicorn.
- **Locked:** yes.

### D2 — Gunicorn worker count

- **Chosen:** 2 workers (`-w 2`), overridable via `WEB_CONCURRENCY`
  env var. Reflected in: Phase 5 diff (P5), CMD line.
- **Rejected:**
  - 1 worker — too low for concurrent requests.
  - 4 workers — overkill for a capstone demo.
- **Rationale:** User selected 2. Gunicorn reads `WEB_CONCURRENCY`
  natively.
- **Locked:** yes.

### D3 — HEALTHCHECK transport: Python urllib, not curl

- **Chosen:** `HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:80/healthz')"`.
  Reflected in: Phase 5 diff (P5), HEALTHCHECK line.
- **Rejected:**
  - `curl -fsS` — `python:3.12-slim` does not ship `curl`.
  - `wget` — also absent from slim images.
- **Rationale:** Python is guaranteed present; `urllib` is stdlib.
- **Locked:** yes.

### D4 — Non-root user name

- **Chosen:** `appuser` with `--no-create-home --shell /bin/false`.
  Reflected in: Phase 5 diff (P5), useradd + USER lines.
- **Rejected:**
  - `nobody` — UID 65534; volume-mount permission collisions.
- **Rationale:** Explicit dedicated user is Docker best practice.
- **Locked:** yes.

### D5 — `/healthz` endpoint: method and response shape

- **Chosen:** `GET /healthz` returning `{"status": "ok"}` with HTTP 200.
  Reflected in: Phase 3 diff (P3), healthz function.
- **Rejected:**
  - `GET /health` — less conventional for Kubernetes probes.
  - Model-readiness check — readiness probe, not liveness; out of scope.
- **Rationale:** Liveness probes must be cheap and side-effect-free.
- **Locked:** yes.

### D6 — DEBUG flag default

- **Chosen:** `app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "0") == "1"`.
  Reflected in: Phase 3 diff (P3), line replacing hardcoded True.
- **Rejected:**
  - Keep `True` default — leaks tracebacks.
  - Use `FLASK_ENV` — deprecated since Flask 2.3.
- **Rationale:** `FLASK_DEBUG` is the canonical Flask env var.
- **Locked:** yes.

### D7 — Volume mount paths in `start.sh`

- **Chosen:** Bind-mount `$PWD/data`, `$PWD/models`, `$PWD/logs` to
  `/app/data`, `/app/models`, `/app/logs`.
  Reflected in: Phase 6 diff (P6).
- **Rejected:**
  - Named Docker volumes — less transparent for a capstone demo.
- **Rationale:** Bind mounts let the user inspect files on the host.
- **Locked:** yes.

### D8 — Package installation for Gunicorn import

- **Chosen:** Add `RUN pip install --no-cache-dir .` after `COPY . .`
  and before `useradd`. Reflected in: Phase 5 diff (P5).
- **Rejected:**
  - Rely on `PYTHONPATH=/app/src` — fragile; breaks if package layout
    changes; Gunicorn docs recommend proper installation.
  - `pip install -e .` — editable installs are a dev pattern, not for
    production images.
- **Rationale:** `@Planner` Stage 1 identified that `gunicorn
  ai_enterprise_workflow.service:app` cannot resolve the module without
  a proper install. `python run.py` worked only because Python
  auto-adds CWD to `sys.path`.
- **Locked:** yes.

### D9 — Defensive directory creation for non-root user

- **Chosen:** `RUN useradd ... && mkdir -p /app/data /app/models /app/logs && chown -R appuser:appuser /app/data /app/models /app/logs`
  before `USER appuser`. Reflected in: Phase 5 diff (P5).
- **Rejected:**
  - Skip mkdir/chown; rely solely on volume mounts — container fails to
    write if volumes are not mounted (e.g., quick `docker run` without
    `start.sh`).
- **Rationale:** Defensive measure ensuring the container is
  self-contained even without explicit volume mounts.
- **Locked:** yes.

### D10 — healthz endpoint placement in api.py

- **Chosen:** Place `/healthz` route **between** the module-level setup
  block and the existing `/predict` route. This groups the lightweight
  probe before the heavier business endpoints.
- **Rejected:**
  - Append at end of file — works but scatters the simplest route after
    complex business logic.
- **Rationale:** Convention: infrastructure/health routes first, domain
  routes after.
- **Locked:** yes.

### D11 — healthz test name and assertions

- **Chosen:** `test_healthz_returns_ok` with three assertions:
  `status_code == 200`, `get_json() == {"status": "ok"}`.
  Reflected in: Phase 4 diff (P4).
- **Rejected:**
  - Single assertion on `"status" in response.get_json()` — too weak;
    doesn't verify the value.
- **Rationale:** The test should fully verify the contract (status code
  + exact JSON body).
- **Locked:** yes.

## Detailed action plan

### Phase 1 — Create `.dockerignore` `[effort: S]` `[mandatory: none; optional: none]`

**Goal:** Reduce Docker build context size and prevent dev artefacts
from leaking into the image.

**Evidence:** No `.dockerignore` exists in the repository (confirmed by
file search). `COPY . .` currently bakes `.git/`, `tests/`, `nb/`,
`manifests/`, `__pycache__/` into the image.

**Action:** Create new file `.dockerignore` at repo root.

#### Execution recipe

1. **Pre-checks.** `test -f .dockerignore && echo "EXISTS" || echo "OK"` → `OK`.
2. **Apply diffs.** Apply diff P1 — create `.dockerignore`.
3. **Post-edit commands.** None.
4. **Validation.** `test -f .dockerignore && echo "PASS" || echo "FAIL"` → `PASS`.
5. **Definition of Done.**
   - [ ] `.dockerignore` exists at repo root.
   - [ ] File contains entries for `.git/`, `.venv/`, `tests/`, `nb/`,
         `__pycache__/`, `manifests/`, `*.pyc`, `*.egg-info/`.
6. **Delegation directives.** None.
7. **Stop conditions.** None.

---

### Phase 2 — Add Gunicorn to `requirements.txt` `[effort: S]` `[mandatory: none; optional: none]`

**Goal:** Make Gunicorn available inside the Docker image as a
runtime dependency (D1: Docker-only).

**Evidence:** Current `requirements.txt` has 7 entries. Gunicorn is
absent. `pyproject.toml` `[project].dependencies` must remain
unchanged.

**Action:** Append `gunicorn>=23.0` to `requirements.txt`.

#### Execution recipe

1. **Pre-checks.** `grep gunicorn requirements.txt` → no match.
2. **Apply diffs.** Apply diff P2 — add gunicorn line.
3. **Post-edit commands.** None.
4. **Validation.** `grep -q 'gunicorn>=23.0' requirements.txt && echo "PASS"` → `PASS`.
5. **Definition of Done.**
   - [ ] `gunicorn>=23.0` is present in `requirements.txt`.
   - [ ] `pyproject.toml` is unchanged (no gunicorn).
6. **Delegation directives.** None.
7. **Stop conditions.** None.

---

### Phase 3 — Add `/healthz` endpoint and env-driven DEBUG in `api.py` `[effort: S]` `[mandatory: @LinterSpecialist; optional: @CodeReviewer]`

**Goal:** (a) Replace hardcoded `DEBUG = True` with env-var logic
(D6). (b) Add `GET /healthz` liveness probe (D5, D10).

**Evidence:** Current `api.py` L1–L11: no `import os`; L11 hardcodes
`app.config["DEBUG"] = True`. No `/healthz` route exists anywhere in
the file (L1–L78).

**Action:** Two edits in one pass:

1. Add `import os` as the first stdlib import (after the docstring,
   before `import pandas`).
2. Replace `app.config["DEBUG"] = True` with
   `app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "0") == "1"`.
3. Insert `GET /healthz` route between module-level setup and the
   existing `@app.route("/predict", ...)` block.

#### Execution recipe

1. **Pre-checks.**
   - `uv run ruff check src/ai_enterprise_workflow/service/api.py` → clean.
   - `uv run pyright src/ai_enterprise_workflow/service/api.py` → 0 errors.
2. **Apply diffs.** Apply diff P3 (`api.py`) — both edits in sequence.
3. **Post-edit commands.**
   - `uv run ruff format src/ai_enterprise_workflow/service/api.py`
4. **Validation.**
   - `uv run ruff check src/ai_enterprise_workflow/service/api.py` →
     "All checks passed!".
   - `uv run ruff format --check src/ai_enterprise_workflow/service/api.py`
     → "1 file already formatted".
   - `uv run pyright src/ai_enterprise_workflow/service/api.py` →
     "0 errors, 0 warnings".
   - `uv run pytest tests/service/test_api.py -p no:tach -p no:cov -v`
     → 8 passed (existing tests unaffected).
5. **Definition of Done.**
   - [ ] `import os` is present as the first stdlib import.
   - [ ] `app.config["DEBUG"]` reads from `FLASK_DEBUG` env var,
         defaulting to `False`.
   - [ ] `GET /healthz` route exists, returns `{"status": "ok"}`.
   - [ ] Ruff clean, pyright clean, 8 existing tests pass.
6. **Delegation directives.** Invoke `@LinterSpecialist` with:
   "Scan `src/ai_enterprise_workflow/service/api.py` for ruff + pyright
   compliance after adding `/healthz` endpoint and DEBUG env var."
7. **Stop conditions.** If pyright reports type errors on
   `os.environ.get`, ensure `import os` is at the top of the file.

---

### Phase 4 — Add test for `/healthz` endpoint `[effort: S]` `[mandatory: @TestDesigner; optional: none]`

**Goal:** Cover `GET /healthz` with a unit test, bringing the total
from 8 to 9.

**Evidence:** Current `tests/service/test_api.py` `TestUnit` class ends
with `test_logs_invalid_type_returns_error_string`. The new test
slots in after that method, still inside `class TestUnit`.

**Action:** Insert `test_healthz_returns_ok` method inside `TestUnit`,
after `test_logs_invalid_type_returns_error_string`.

#### Execution recipe

1. **Pre-checks.**
   - `uv run pytest tests/service/test_api.py -p no:tach -p no:cov -v`
     → 8 passed.
2. **Apply diffs.** Apply diff P4 (`test_api.py`).
3. **Post-edit commands.**
   - `uv run ruff format tests/service/test_api.py`
4. **Validation.**
   - `uv run ruff check tests/service/test_api.py` → clean.
   - `uv run pyright tests/service/test_api.py` → 0 errors.
   - `uv run pytest tests/service/test_api.py -p no:tach -p no:cov -v`
     → **9 passed** (8 existing + 1 new).
5. **Definition of Done.**
   - [ ] `test_healthz_returns_ok` exists inside `TestUnit`.
   - [ ] Test sends `GET /healthz` and asserts status code 200 and
         JSON body `{"status": "ok"}`.
   - [ ] 9 tests pass.
6. **Delegation directives.** Invoke `@TestDesigner` with:
   "Review the new `test_healthz_returns_ok` test in
   `tests/service/test_api.py` for completeness."
7. **Stop conditions.** None.

---

### Phase 5 — Rewrite Dockerfile `[effort: M]` `[mandatory: none; optional: @CodeReviewer]`

**Goal:** Apply D2, D3, D4, D8, D9 — Gunicorn CMD, HEALTHCHECK,
non-root user, `pip install .`, defensive dirs.

**Evidence:** Current `Dockerfile` is 14 lines. `CMD ["python",
"run.py"]` must be replaced. No user creation, no HEALTHCHECK, no
`pip install .` present.

**Action:** Replace the Dockerfile content to add: `pip install .`,
`useradd + mkdir + chown`, `USER appuser`, `HEALTHCHECK`, Gunicorn
`CMD`.

**Design rationale trace:**

| Line(s) | Decision |
|---------|----------|
| `RUN pip install --no-cache-dir .` | D8 — installs package for Gunicorn import |
| `useradd …` | D4 — non-root `appuser` |
| `mkdir -p … && chown` | D9 — defensive dirs |
| `USER appuser` | D4 — drop privileges |
| `HEALTHCHECK …` | D3 — pure-Python probe, no curl |
| `CMD ["gunicorn", …, "-w", "2", …]` | D2 — 2 workers |

#### Execution recipe

1. **Pre-checks.** `cat Dockerfile` — confirm current state (14 lines,
   `CMD ["python", "run.py"]`).
2. **Apply diffs.** Apply diff P5 (`Dockerfile`).
3. **Post-edit commands.** None.
4. **Validation.**
   - `grep -c 'gunicorn' Dockerfile` → `1`.
   - `grep -c 'appuser' Dockerfile` → `3` (useradd, chown, USER).
   - `grep -c 'HEALTHCHECK' Dockerfile` → `1`.
   - `grep -c 'pip install --no-cache-dir \.' Dockerfile` → `1`.
   - If Docker daemon available:
     `docker build -t capstone .` → exits 0.
5. **Definition of Done.**
   - [ ] `RUN pip install --no-cache-dir .` is present after `COPY . .`.
   - [ ] `USER appuser` is present.
   - [ ] `CMD` uses `gunicorn` with `--bind 0.0.0.0:80` and `-w 2`.
   - [ ] `HEALTHCHECK` probes `/healthz` using Python urllib.
   - [ ] `mkdir -p /app/data /app/models /app/logs` + `chown` present.
6. **Delegation directives.** None.
7. **Stop conditions.** If `docker build` fails on `useradd: command
   not found`, the base image may have changed to Alpine; fall back to
   `adduser --disabled-password --no-create-home appuser`. If Gunicorn
   version 23.0 is not found on PyPI, fall back to `>=22.0` in
   `requirements.txt`.

---

### Phase 6 — Add volume mounts to `start.sh` `[effort: S]` `[mandatory: none; optional: none]`

**Goal:** Bind-mount `data/`, `models/`, `logs/` so mutable state
persists across container restarts (D7).

**Evidence:** Current `start.sh` has no `-v` flags (lines 6–11).

**Action:** Add three `-v` flags to the `docker run` command.

#### Execution recipe

1. **Pre-checks.** `cat start.sh` — confirm current content (11 lines).
2. **Apply diffs.** Apply diff P6 (`start.sh`).
3. **Post-edit commands.** None.
4. **Validation.** `bash -n start.sh && echo "PASS" || echo "FAIL"` →
   `PASS`.
5. **Definition of Done.**
   - [ ] `start.sh` contains three `-v` flags for `data`, `models`,
         `logs`.
6. **Delegation directives.** None.
7. **Stop conditions.** None.

---

**Effort summary:** S×5, M×1 — total estimated complexity: Small.
No L or XL phases (decomposition not required).

## Proposed diffs

### P1 — `.dockerignore` (new file)

```diff
--- /dev/null
+++ b/.dockerignore
@@ -0,0 +1,8 @@
+.git/
+.venv/
+tests/
+nb/
+manifests/
+__pycache__/
+*.pyc
+*.egg-info/
```

### P2 — `requirements.txt`

```diff
--- a/requirements.txt
+++ b/requirements.txt
@@ -1,7 +1,8 @@
 flask>=3.0
+gunicorn>=23.0
 numpy>=2.2,<3
 pandas<3
 requests>=2.33.0
 scipy>=1.13
 statsmodels>=0.14
 tqdm>=4.66
```

### P3 — `src/ai_enterprise_workflow/service/api.py`

```diff
--- a/src/ai_enterprise_workflow/service/api.py
+++ b/src/ai_enterprise_workflow/service/api.py
@@ -1,11 +1,24 @@
 """Flask REST API exposing the forecasting and logging endpoints."""

+import os
+
 import pandas as pd
 from flask import Flask, jsonify, request
 from flask.typing import ResponseReturnValue

 from ai_enterprise_workflow.core.config import DIRECTORY_LOGS
 from ai_enterprise_workflow.forecasting.arima import model

 app = Flask(__name__)
-app.config["DEBUG"] = True
+app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "0") == "1"
+
+
+@app.route("/healthz", methods=["GET"])
+def healthz() -> ResponseReturnValue:
+    """Liveness probe endpoint.
+
+    Returns:
+        JSON ``{"status": "ok"}`` with HTTP 200.
+    """
+    return jsonify({"status": "ok"})


 @app.route("/predict", methods=["POST"])
```

### P4 — `tests/service/test_api.py`

Insert inside `class TestUnit`, after `test_logs_invalid_type_returns_error_string`:

```diff
--- a/tests/service/test_api.py
+++ b/tests/service/test_api.py
@@ -80,6 +80,14 @@
             assert "Error" in response.data.decode()
             assert response.get_json() is None

+        def test_healthz_returns_ok(
+            self, flask_client: FlaskClient
+        ) -> None:
+            """GET /healthz returns JSON with status ok."""
+            response = flask_client.get("/healthz")
+            assert response.status_code == 200
+            assert response.get_json() == {"status": "ok"}
+
     @pytest.mark.contract
     class TestContracts:
         """Property-based invariant tests via Hypothesis."""
```

### P5 — `Dockerfile`

```diff
--- a/Dockerfile
+++ b/Dockerfile
@@ -1,14 +1,25 @@
 FROM python:3.12-slim

 ENV PYTHONDONTWRITEBYTECODE=1 \
     PYTHONUNBUFFERED=1

 WORKDIR /app

 COPY requirements.txt .
 RUN pip install --no-cache-dir -r requirements.txt

 COPY . .
+RUN pip install --no-cache-dir .
+
+RUN useradd --no-create-home --shell /bin/false appuser \
+    && mkdir -p /app/data /app/models /app/logs \
+    && chown -R appuser:appuser /app/data /app/models /app/logs
+
+USER appuser

 EXPOSE 80
-CMD ["python", "run.py"]
+
+HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
+    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:80/healthz')"
+
+CMD ["gunicorn", "--bind", "0.0.0.0:80", "-w", "2", "ai_enterprise_workflow.service:app"]
```

### P6 — `start.sh`

```diff
--- a/start.sh
+++ b/start.sh
@@ -3,9 +3,12 @@

 app="capstone"
 docker build -t "${app}" .
 docker run \
     -it \
     --rm \
     -p 3000:80 \
+    -v "$PWD/data:/app/data" \
+    -v "$PWD/models:/app/models" \
+    -v "$PWD/logs:/app/logs" \
     --name "${app}" \
     "${app}"
```

## Failure playbook

| # | Symptom | Likely cause | Remediation | Escalate to |
|---|---------|--------------|-------------|-------------|
| 1 | `docker build` fails on `useradd: command not found` | Base image switched to Alpine | Replace `useradd` with `adduser --disabled-password --no-create-home appuser` | — |
| 2 | `HEALTHCHECK` always reports unhealthy | Gunicorn not ready within 10 s start period | Increase `--start-period` to 30 s | — |
| 3 | Gunicorn fails with `ModuleNotFoundError: ai_enterprise_workflow` | `RUN pip install --no-cache-dir .` missing or failed | Verify P5 diff applied; rebuild with `--no-cache` | — |
| 4 | Pyright `reportMissingImports` on `os` | `import os` not added or wrong position | Ensure `import os` is the first stdlib import, before `import pandas` | @LinterSpecialist |
| 5 | Ruff `I001` (import order) after adding `import os` | `os` must come before third-party imports | Run `uv run ruff check --fix` to auto-sort | @LinterSpecialist |
| 6 | Container cannot write to `/app/logs` at runtime | Volume not mounted AND chown missed | Verify Phase 5 includes `mkdir + chown`; ensure `start.sh` has `-v` flags | — |
| 7 | Existing tests fail after DEBUG change | A test relies on `DEBUG=True` behaviour | No existing test does; if one does, `app.config["TESTING"] = True` (set in fixture) overrides it | @TestDesigner |
| 8 | `pip install gunicorn>=23.0` fails — version not on PyPI | Version 23.0 not yet published | Change to `gunicorn>=22.0` in `requirements.txt` | — |
| 9 | New test `test_healthz_returns_ok` fails with 404 | `/healthz` route not registered | Verify P3 diff applied and route is before `/predict` | @TestDesigner |
| 10 | `tach check` fails on new `import os` in `api.py` | `os` is stdlib; tach should not flag it | tach is broken in current venv (missing `rich`); skip | — |

## Roadmap

| # | Phase | Owner | Status | Evidence / Notes |
|---|-------|-------|--------|------------------|
| 1 | Phase 1 — `.dockerignore` | @ProjectDeveloper | done | Created `.dockerignore` with 8 entries; `test -f` → PASS. |
| 2 | Phase 2 — Gunicorn in `requirements.txt` | @ProjectDeveloper | done | `gunicorn>=23.0` added after `flask>=3.0`; grep PASS. |
| 3 | Phase 3 — `/healthz` + DEBUG env var | @ProjectDeveloper → @LinterSpecialist | done | `import os`, env-driven DEBUG, `/healthz` route added; ruff+pyright 0 errors; 8 existing tests pass. |
| 4 | Phase 4 — `/healthz` test | @ProjectDeveloper → @TestDesigner | done | `test_healthz_returns_ok` added inside TestUnit; @TestDesigner SUFFICIENT verdict; ruff+pyright clean; 9/9 tests pass. |
| 5 | Phase 5 — Dockerfile hardening | @ProjectDeveloper → @CodeReviewer | done | pip install ., useradd+mkdir+chown, USER appuser, HEALTHCHECK, gunicorn CMD applied; structural grep: gunicorn×1, appuser×3, HEALTHCHECK×1, pip install .×1. |
| 6 | Phase 6 — Volume mounts in `start.sh` | @ProjectDeveloper | done | Three `-v` bind-mount flags added; `bash -n` syntax check PASS. |
| 7 | Documentation pass | @DocsReviewer | done | Targeted review: healthz() + flask_client + TestApi docstrings updated; Examples added to predict/logs/healthz; AAA comments in all 9 tests; ruff check+format clean. |
| 8 | Integration gate | @IntegrationChecker (`docs_mode=skip`) | done | First run: NO-GO (G2+G3 E501/format in tests/core/test_logging.py — new finding). @LinterSpecialist fixed. Re-run: GO — G0-G5 all PASS, 21/21 tests, 0 pyright errors. G6 skipped (tach broken, pre-existing). |
| 9 | MR preparation | @ProjectDeveloper | not-started | |

## Acceptance criteria (mirror)

Verbatim from GitHub issue #5:

- [x] `.dockerignore` exists and excludes `.git/`, `.venv/`, `tests/`, `nb/`, `__pycache__/`, `manifests/`
- [x] Dockerfile creates and switches to a non-root `appuser`
- [x] Dockerfile `CMD` uses Gunicorn with 2 workers (overridable via `WEB_CONCURRENCY`)
- [x] Dockerfile includes `RUN pip install --no-cache-dir .` so the package is importable by Gunicorn
- [x] Dockerfile includes `HEALTHCHECK` that probes `/healthz` using Python urllib
- [x] `api.py` exposes `GET /healthz` returning `{"status": "ok"}`
- [x] `api.py` reads `DEBUG` from `FLASK_DEBUG` env var, defaulting to `False`
- [x] `start.sh` bind-mounts `data/`, `models/`, `logs/` into the container
- [x] `gunicorn>=23.0` is in `requirements.txt` (not in `pyproject.toml`)
- [x] `run.py` remains unchanged as the local dev entry-point
- [x] All existing 8 tests pass; new `/healthz` test passes (total 9)
- [x] Ruff and pyright clean on all changed source files

## Manifest changelog

| Timestamp | Actor | Change |
|---|---|---|
| 2026-05-15T00:00:00Z | @ProjectArchitect | Created full-mode manifest: 6 phases, 7 enhancements, 11 decisions. Issue #5, branch 5-harden-docker-flask-production. |

## Handover

**Design phase complete.** The floor is handed over to
`@ProjectDeveloper`.

This manifest was authored by a reasoning-class model with the
explicit assumption that `@ProjectDeveloper` is an execution-class
model. All non-trivial design decisions are pre-resolved in
`## Decisions log`; all phase-level instructions are encoded as
`#### Execution recipe` sub-blocks; predictable failure modes are
covered in `## Failure playbook`. **Do not re-derive design choices.**

`@ProjectDeveloper` must:

1. Treat this manifest as the single source of truth. If a phrase
   in the manifest seems to require a design judgment, stop and
   ask the user; do not improvise.
2. Read `## Execution context` before starting and verify every
   precondition.
3. Execute phases sequentially. For each phase: flip the roadmap
   row to `in-progress`, run the `Execution recipe` literally,
   apply the referenced `Proposed diffs` exactly as drafted, run
   the listed validation commands, then flip the row to `done`
   with a one-line evidence note.
4. Any deviation from a `Proposed diff` must be recorded in the
   `Roadmap` `Evidence / Notes` column with justification, and the
   diff block patched in place.
5. On any predictable failure, consult `## Failure playbook` first
   before improvising or escalating.
6. After the last code phase, hand over to `@DocsReviewer`, then to
   `@IntegrationChecker` with `docs_mode=skip`.
7. Verify every box in `Acceptance criteria (mirror)` is checked
   before preparing the merge request.
8. Prepare the MR using the repository's pull request template
   (or default GitHub PR template).
9. When the user later confirms that the PR was merged and the linked
   issue is complete, re-invoke `@ProjectDeveloper` to record the
   merge/closure evidence and set the manifest frontmatter `status:`
   to `done`.

To start: `@ProjectDeveloper execute manifests/5-harden-docker-flask-production.md`.
To finalize after merge: `@ProjectDeveloper finalize manifests/5-harden-docker-flask-production.md`.
