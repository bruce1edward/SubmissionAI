# SubmissionAI Continuity

A fresh document-review harness that remembers approved corrections, resumes from durable checkpoints, and updates findings when source documents change.

**Working locally:** FastAPI, a browser task console, LangGraph with SQLite checkpoints, immutable package versions, source-bound review memory, and deterministic consistency checks. No API keys are needed. Local mode does not claim to use a live model or Atlas.

**Implemented, awaiting your credentials and live verification:** MongoDB Atlas application storage and LangGraph checkpointing, Atlas Vector Search with Voyage embeddings, and a bounded agent using an OpenAI-compatible chat endpoint. Use the hackathon-provided Atlas Sandbox for the event.

Continuity is the current root application. The previous Streamlit app is preserved as `legacy_streamlit_app.py`, with `requirements-legacy.txt` and its original [README](docs/LEGACY_README.md). Earlier agent modules, guidance documents, and repository history remain available as background; the Continuity application does not import the legacy implementation. To run the legacy app from a full repository checkout, install its separate requirements and run `streamlit run legacy_streamlit_app.py`.

## Run locally

Requires Python 3.12+. No Node build or Streamlit dependency.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8765
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). If your default Python is older than 3.12, use a newer Python executable for the venv step. A venv has already been created in the current workspace; starting Uvicorn is sufficient here.

The default environment is local and deterministic. Copy `.env.example` to `.env` only when you want to configure services. `.env`, `.venv`, and `.data` are excluded by `.gitignore`. Never commit credentials or review databases. `requirements.lock.txt` records the tested environment; use it instead of `requirements-dev.txt` to reproduce exact dependency versions.

## Try the complete flow

1. Choose **v1 · Initial package**, click **Load sample**, then **Run one step**. The review pauses after a saved checkpoint.
2. Reload the page, or stop and restart the server. Click **Resume review**. V1 contains a protocol/SAP timing mismatch and a missing referenced appendix.
3. Click a protocol citation. **Add a note from this source**, keep the exact quote, and save a source-backed reviewer note. New reviews recall it while that source remains unchanged.
4. Load **v2 · Timing corrected** and start a review. The timing finding resolves. Checklist coverage remains open and is reused because its dependencies did not change.
5. Load **v3 · Timing reverted**. The timing finding reopens.
6. Open **Review history**, inspect a prior checkpoint, or **Export review record**. **Run all checks again** disables result reuse for a comparison.

The three fixture packages use the same synthetic study. Tests and the benchmark use temporary databases and do not alter your workspace history. Reviewer notes added in the interface persist in `.data`.

## Supported input and limits

Import a JSON package; download an example from Evidence library or use `demo/v1.json`. A package contains a `study_id`, unique `version` label, and `documents` with `id`, `title`, `kind`, and `text`. Kinds: `protocol`, `sap`, `checklist`, `supporting`. Maximum 20 documents, 30,000 characters per document, and a 1 MB request limit. Each version is immutable; edits need a new version label.

This MVP verifies two explicit **synthetic document contracts**:

- Protocol and SAP each contain an unambiguous line such as `Primary endpoint assessment: Week 8.`
- The checklist names required files using lines such as `Required document: safety_appendix.txt`.

Unstructured, missing, or ambiguous fields become **unresolved**. This is not a full eCTD/PDF parser, clinical reviewer, regulatory compliance engine, or predictor of FDA approval. The fixture checklist is not FDA guidance.

## Agent and evidence architecture

```
Upload immutable version
  → recall applicable review memory
  → compare source hashes and check fingerprints
  → retrieve evidence and run selected checks
  → verify citations and explicit source fields
  → persist the review record
```

LangGraph checkpoints each node: `prepare`, `endpoint_alignment`, `referenced_documents`, `finalize`. SQLite is used locally; the MongoDB checkpointer is used in MongoDB mode. The workflow is the actual API execution path, not a logging layer added afterward.

In live-model mode, the agent can conclude or request **one additional evidence retrieval per check**. The output is validated against a strict schema. A missing document is established from the explicit checklist and complete inventory, not from a search miss. Citation existence and the two explicit checks are independently verified; only the verified explanation is shown. Unrelated medical claims are never promoted to findings. Invalid responses and provider failures become unresolved checks, never sample results.

Local mode evaluates those fields directly. It exercises the same persistence, evidence-verification, memory, and invalidation path but does not test model reasoning.

A result can be reused only if its dependency fingerprint matches: relevant source hashes or inventory, applicable memory IDs, harness/prompt version, review mode, provider/model, and retrieval configuration. The coverage check does not depend on SAP prose. Unresolved results are retried in fresh runs. A review freezes its package, memory, and baseline when it is created; add a new review to apply later memory changes.

Review memory is scoped to a study and exact source hash. Free-text notes provide context in live mode and remain visible in local mode; they do not override source checks. An approved **document alias** can affect coverage in both modes: map a required filename to a supporting document after verifying its source quote. Changing that source invalidates the alias. Revocation preserves historical runs.

Completed checkpoints survive process exit. An in-flight node can be repeated after a crash; writes use stable IDs/upserts. A crashed operation's concurrency lease expires within 30 seconds; if a resume says the operation is still running, wait for that lease to expire. This is a single-workspace prototype with no claim of distributed exactly-once execution.

## Configure the Atlas Sandbox later

1. Join the event-provided sandbox using the organizer's invitation. Get its connection URI and configure its authorized network access.
2. Copy `.env.example` to `.env` and fill values locally. Keep secrets out of chat, screenshots, and the repository.

```dotenv
STORAGE_BACKEND=mongodb
MONGODB_URI=<hackathon-sandbox-uri>
MONGODB_DATABASE=submissionai_continuity
MONGODB_VECTOR_INDEX=evidence_vector
VECTOR_SEARCH_ENABLED=true
VOYAGE_API_KEY=<your-key>
VOYAGE_MODEL=voyage-3.5-lite
VOYAGE_DIMENSIONS=1024
REVIEW_MODE=llm
LLM_BASE_URL=<provider-base-url-ending-in-v1>
LLM_API_KEY=<your-key>
LLM_MODEL=<model-id-available-in-your-account>
```

3. Run `.venv/bin/python -m continuity setup-atlas`. It creates the vector index on `evidence_chunks`, including study, package, and embedding-model filters. Run it again to check the status. Wait for `READY` before querying. This requires index-creation privileges in the sandbox.
4. Restart the server and load the samples. Documents are embedded during ingestion. The index may need a short time to ingest new records; no-result searches produce an explicit error rather than silently switching retrieval backends.
5. After changing the embedding model/dimensions or enabling vector search for already stored packages, choose a compatible index and run `.venv/bin/python -m continuity reindex`.
6. Run the demo with a real model and verify the source citations, checkpoint recovery, memory recall, and reversion. These live integrations have not been validated without your credentials.

Model and embedding choices can be changed to match event resources. The named Voyage model is configurable, not a requirement. SQLite data is not automatically copied into Atlas; reload synthetic packages or re-import your authorized packages after switching.

MongoDB collections: `study_versions`, `evidence_chunks`, `review_memory`, `runs`, `leases`, plus the integration's checkpoint collections. Findings and their histories are persisted within immutable run checkpoints and exposed by review history/export.

## Validation and measurements

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m continuity benchmark --output docs/benchmark.json
```

The tests cover separate-process restart, revision and reversion, idempotence, scoped retrieval, source-bound notes and aliases, malformed model output, a bounded agent tool loop, citation rejection, API validation, and infrastructure recovery. Live MongoDB/model/Voyage calls require a separate credentialed integration run.

The benchmark compares an incremental v2 review against a full v2 rerun and checks v3 reversion. It explicitly records the local deterministic mode and zero model calls. Timings include local checkpoint I/O and are not a production performance claim.

## Project map

| File | Responsibility |
|---|---|
| `app.py` | FastAPI endpoints, app lifecycle, static UI |
| `continuity/workflow.py` | Durable graph, dependency fingerprints, transitions |
| `continuity/reviewer.py` | Bounded live agent, deterministic checks, independent verifier |
| `continuity/retrieval.py` | Local lexical retrieval, Voyage, Atlas vector search/index |
| `continuity/storage.py` | SQLite/MongoDB records and operation leases |
| `continuity/memory.py` | Source-scoped human memory and aliases |
| `continuity/schemas.py` | Validated input/output contracts |
| `static/` | Responsive task console, evidence viewer, history, memory |
| `demo/` | Three synthetic package versions |
| `tests/` | Regression tests |

## Hosting and hackathon delivery

The local server binds only to `127.0.0.1`. A container definition is included for later hosting. Set `APP_ACCESS_TOKEN` to require a shared bearer token before exposing this single-workspace demo remotely; the UI stores it only in browser session storage. This is not multi-user authorization or production handling of clinical data. The interface and tests use synthetic documents.

For the hackathon: use the provided Atlas Sandbox, verify accessible repository links, record the required one-minute video, and submit by the organizer's deadline. Public deployment, the video, and event submission have not been performed by this build. Commit timestamps and event eligibility must reflect when work was actually done; do not present pre-event implementation as event work. The original SubmissionAI code was not copied into the Continuity implementation; legacy files are retained separately as background.

See `docs/DEMO_SCRIPT.md` for the demonstration and `HACKATHON_PLAN.md` for the researched event plan. No cloud account is required for the local build.
