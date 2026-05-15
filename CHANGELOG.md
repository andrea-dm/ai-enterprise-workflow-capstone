# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

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

## [5.0.0] — 2026-03-28

### Changed

- Replaced the critic-centric reflective architecture with the **Adaptive
  Mixed Reviewer + Challenger Topology** (interpreter → reviewer → challenger
  → verifier pipeline).
- Added `QuestionContract` facet decomposition for coverage-driven auditing.
- Introduced best-candidate memory across cycles.
