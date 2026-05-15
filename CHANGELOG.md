# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] — Vespa retrieval substrate

### Added

- **Sequential two-pass Thinking VLM mode with self-flagging deferral
  (default).** New
  :class:`carbon_pledges.core.models.ThinkingMode` enum
  (``SEQUENTIAL`` / ``CONCURRENT``) on
  ``IngestionAIModelConfig.thinking_mode`` (default ``SEQUENTIAL``,
  overridable via ``INGEST_THINKING_MODE``). The Instruct VLM now
  appends a ``DEFERRAL_CLAUSE`` to chart prompts, ``SAFETYNET_V2``,
  and ``FALLBACK_HEAVY``; pages it cannot transcribe with confidence
  emit the single sentinel line ``DEFER_TO_THINKING``. Detection is
  line-anchored and length-bounded (≤ 50 chars) to resist
  prompt-injection from source PDFs. Deferred pages are persisted to
  ``<artifacts>/<report_id>/.thinker/deferred.jsonl`` (JSONL queue)
  and ``.thinker/cache/`` (PNG cache). A new
  ``ThinkingOrchestrator`` (``carbon_pledges.ingestion.thinker``)
  runs once per PDF / bundle after every shard finishes Pass 1: it
  stops the Instruct vLLM server, starts the Thinking vLLM server
  (each at ``--gpu-memory-utilization=0.80``), drains the queue,
  strips ``<think>...</think>`` from each response, and persists
  ``<stem>_<page>.thinking.md`` sidecars. ``index_visuals`` then
  prefers ``.thinking.md`` over the matching ``.md``. Pass 2 is
  terminal: any failure (server crash, OpenAI error, sidecar I/O)
  is swallowed and the chunks manifest is emitted from Instruct
  outputs alone. After Pass 2 returns, the Instruct server is lazily
  re-spawned on the next ``_query_vlm`` call via a new
  ``IngestionResources.ensure_instruct_alive`` guard, so the next
  PDF transparently re-acquires VRAM. Issue #8.

- **Hybrid multi-GPU Thinking-VLM scheduling mode for 2× A100 hosts.**
  Auto-promoted on hosts with `n_visible_gpus >= 2` and
  `workers_per_job == 1`.  Replicates the Instruct VLM on both GPUs
  at steady state; the
  :class:`~carbon_pledges.ingestion._hybrid.HybridArbiter` daemon
  evicts one Instruct replica in favour of a Thinking VLM when the
  cross-PDF deferred queue crosses adaptive thresholds (queue depth
  >= ``hybrid_n_max`` OR EWMA(alpha, k) >= ``hybrid_ewma_tau``),
  with hysteresis (re-spawn Instruct at ``hybrid_n_min``) and
  dwell-time floors.  Operator-tunable via seven ``hybrid_*``
  config fields on
  :class:`~carbon_pledges.core.models.IngestionAIModelConfig`.
  Override: ``INGEST_THINKING_MODE=sequential``. Issue #10.

- **Cross-PDF audit JSONL** emitted at
  ``<artifacts>/.on_hold/deferred-<job_id>.jsonl`` in **both**
  SEQUENTIAL and HYBRID modes (cross-mode auditability, AC5).

### Changed

- **Default Thinking-VLM scheduling flipped to ``SEQUENTIAL``.**
  Operators must NOT pre-start the Thinking server in the default
  mode — the orchestrator owns its lifecycle. Concurrent (dual-server)
  scheduling remains available via ``thinking_mode: concurrent`` in
  the config or ``INGEST_THINKING_MODE=concurrent`` in the
  environment, paired with ``START_THINKING_VLM=1`` for
  ``launch_vllm_ingest.sh``. The launcher's header banner now
  documents the mode-selection contract.
- **Default Thinking-VLM scheduling on multi-GPU hosts promoted to
  ``HYBRID``.**  Single-GPU SEQUENTIAL behaviour preserved
  byte-identical (AC1). Concurrent mode (PR #7 legacy) remains
  opt-in and byte-identical.
- **``ThinkingOrchestrator`` gains a ``gpu_slot: int = 0``
  constructor knob**; ports and pidfiles are derived per-slot
  (``BASE_PORT + 10 * slot``). Defaults preserve pre-Phase-2
  behaviour.
- **Extractor Pass-1 routing predicate flipped from blacklist
  (``!= SEQUENTIAL``) to whitelist (``in {CONCURRENT}``).**
  HYBRID Pass 1 now correctly uses Instruct-only routing with
  sentinel-based deferral.
- **Per-report Vespa isolation contract.** All ingestion paths now
  pin ``report_id`` to the artifact directory name (the report's PDF
  stem for standalone files, the bundle name for bundle members),
  decoupling chunk identity from individual filenames inside a
  bundle. `ContentExtractor.__init__` accepts a keyword-only
  ``report_id`` (default: derived from ``file_name``); the ingestor
  passes ``pdf.stem`` and ``bundle_name`` explicitly. `source_pdf` is
  always populated and records the exact PDF filename.
- Hybrid YQL emitted by `VespaRetriever._build_query_body` is now
  fully parenthesized: the `(nearestNeighbor(...)) or
  (userInput(...))` clause is wrapped before appending the
  `report_id`/`modality` filter, so the filter applies to both the
  dense ANN branch and the lexical branch.
- `IngestionWorker._wipe_stale_artifacts` now deletes the matching
  Vespa documents (via `VespaWriter.delete_report`) before
  ``shutil.rmtree`` removes the on-disk artifact directory, keeping
  the Vespa side in lockstep with the local filesystem.
- **Retrieval substrate migrated from FAISS-on-disk to Vespa.**  All
  dense and lexical signals now live in a single Vespa container
  (`carbon_pledges_vespa`, image `vespaengine/vespa:8.469.30`) under
  the `chunk` schema, namespaced by `(report_id, modality)`.  The
  `hybrid` rank-profile combines BM25 with colBERT MaxSim over BGE-M3
  multi-vectors.
- `AuditorResources` now builds three `VespaRetriever` instances per
  report (body / tables / charts) and one shared regulation retriever,
  all subclassing `langchain_core.retrievers.BaseRetriever`.
- `ContentExtractor` and `ContextJob` write through `VespaWriter`;
  Vespa transport / schema errors now hard-fail instead of being
  silently swallowed.

### Added

- `carbon_pledges.resources._base.ReportNotIndexedError` — raised by
  the audit binder when a `report_id` has zero indexed chunks,
  surfacing the failure with an actionable message instead of
  silently returning an empty retriever.
- `_RetrievalSuite._report_has_chunks(report_id)` — count-only YQL
  probe (`select * from chunk where report_id contains "..." limit
  0`) executed before `_bind_report_retrievers` constructs any
  per-modality retriever.
- `VespaWriter.delete_report(report_id) -> int` — idempotent
  delete-by-query over the `chunk` schema. Per-document failures are
  swallowed so the operation is safe to retry.
- `VespaWriter.write_manifest(artifact_dir, *, report_id,
  source_pdfs, ingest_run_id)` — atomic per-report manifest writer
  (tempfile + ``os.replace``). Emits ``chunks/manifest.json`` with
  ``modality_counts``, ``total_chunks``, source filenames, and run
  timestamp.
- `VespaWriter.feed_chunks(..., artifact_dir=None)` — when an
  artifact directory is supplied, mirrors each fed record's text and
  metadata (no vectors) to ``chunks/chunks.jsonl.gz`` (gzip,
  append-mode), giving every report a self-contained chunk archive
  next to its raw markdown sidecars.
- `carbon_pledges.retrieval.embedder.BgeM3MultiVectorEmbedder` — dense
  + colBERT-style multi-vector encoder used by both writer and
  retriever.
- `carbon_pledges.retrieval.writer.VespaWriter` — batched
  `feed_iterable` ingestion with per-document encoding.
- `carbon_pledges.retrieval.retriever.VespaRetriever` —
  `BaseRetriever` wrapper around `pyvespa.Vespa.query` with the
  `hybrid` rank-profile.
- `vespa/app/` application package with the `chunk` schema and
  `hybrid` rank-profile, plus a deploy script.
- vLLM HTTP VLM client used during ingestion for chart/table
  classification and extraction.

### Removed

- `langchain_community.vectorstores.FAISS` integration in
  `AuditorResources`, `ContentExtractor`, and `ContextJob`.
- `RetrievalConfig.use_faiss_fallback` safety valve.
- Legacy `_load_report_faiss` and `_load_visual_retriever` methods
  on `AuditorResources`.
- Per-report `body/vectorstore/`, `tables/vectorstore/`,
  `charts/vectorstore/` directories and the regulation
  `index.faiss` / `index.pkl` files; only raw markdown sidecars
  remain on disk.
- `langchain_community*` and `langchain_huggingface` test stubs
  (no longer imported by the codebase).

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
