# SubmissionAI — Automate the last mile of drug development

A fresh document-review harness that remembers approved corrections, resumes from durable checkpoints, and updates findings when source documents change.

**Working locally:** FastAPI, a browser task console, LangGraph with SQLite checkpoints, immutable package versions, source-bound review memory, and deterministic consistency checks. No API keys are needed. Local mode does not claim to use a live model or Atlas.

**Atlas verified:** Application records, review memory, native LangGraph checkpoints, separate-process recovery, and incremental reviews have been verified with synthetic data in the hackathon-provided Atlas Sandbox. Each installation needs its own authorized credentials.

**Nebius verified:** `Qwen/Qwen3-235B-A22B-Instruct-2507` passed both synthetic evidence checks through the live app, including additional evidence retrieval and Atlas checkpoint read-back. [Measured results](docs/nebius_verification.json) record three model calls and 4,179 tokens for one review. This is the current local provider configuration, not a general accuracy evaluation.

**Atlas Vector Search verified:** Nebius Qwen embeddings and a 4,096-dimension Atlas index now power evidence search. The [retrieval smoke check](docs/vector_verification.json) verified semantic ranking and study/version isolation. A [full agent review](docs/vector_agent_verification.json) passed both evidence checks with three model calls, three vector retrievals, and 5,214 chat tokens; its Atlas checkpoint was read back successfully. Embedding usage is separate from the review's chat-token count.

**OpenAI verified:** The Responses API with `gpt-6-luna` passed synthetic end-to-end checks for evidence-backed findings, checkpoint recovery, memory recall, revision reuse, and reopening. The agent uses strict structured output, bounded evidence retrieval, token accounting, and independent citation verification. [Measured results](docs/live_llm_verification.json) record four model calls across three package versions; they are not a general accuracy evaluation. Other providers can use the Chat Completions interface. Voyage remains an optional, unverified embedding provider.

**Final configuration rehearsal passed:** The [rehearsal record](docs/REHEARSAL.md) covers reviewer memory, restart recovery, v2 resolution, v3 reopening, and a paired incremental/full review using Nebius and Atlas Vector Search. Both v3 runs produced the expected verified findings; the incremental run used one model call and 1,932 chat tokens versus three calls and 5,274 chat tokens for the full run. These are observations from one synthetic trial.

The active application at the repository root is the Continuity review harness. The earlier Streamlit implementation and its regulatory knowledge bases are preserved under `archive/SubmissionAI/`; an even earlier repository snapshot is preserved under `archive/SubmissonAI/`. The active application does not import either archive. See [repository provenance](docs/REPOSITORY_PROVENANCE.md) and [development history](docs/DEVELOPMENT_HISTORY.md) for the original commit histories and the distinction between recorded publication dates and actual development time.

Original software and authored documentation are available under the [MIT license](LICENSE). Historical regulatory source material and other third-party content retain their original rights; see [licensing scope](docs/LICENSING.md).

**Event eligibility: pending organizer clarification.** The [eligibility request and evidence timeline](docs/EVENT_ELIGIBILITY.md) identify the pre-start baseline and subsequent verification records. The request is prepared but has not been sent; no organizer ruling has been received.

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

The three fixture packages use the same synthetic study. Tests and the benchmark use temporary databases and do not alter your workspace history. Reviewer notes added in the interface persist in the configured SQLite or MongoDB database.

## Focus the rehearsal workspace

Set `DEMO_STUDY_ID=REHEARSAL-210a3222` and `DEMO_DRUG_NAME=Mongdbtilimb` in the private `.env`, then restart. The package and review lists show this study, and the sample loader keeps its versions in the same study. The drug name is a presentation label; immutable source text, memory references, and checkpoints remain intact. Clear these settings to restore all studies. This is a presentation filter, not authorization or deletion.

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

## Configure the Atlas Sandbox

1. Join the event-provided sandbox using the organizer's invitation. Get its connection URI and configure its authorized network access.
2. If `.env` does not exist yet, copy `.env.example` to `.env`. Fill values locally without overwriting existing credentials. Keep secrets out of chat, screenshots, and the repository.

```dotenv
STORAGE_BACKEND=mongodb
MONGODB_URI=<hackathon-sandbox-uri>
MONGODB_DATABASE=submissionai_continuity
VECTOR_SEARCH_ENABLED=false
REVIEW_MODE=deterministic
```

3. Restart the server and load a sample. Verify records in Atlas under the configured database. SQLite records are not automatically migrated.

## Enable Nebius model calls

The default template targets [Nebius Token Factory](https://docs.tokenfactory.nebius.com/quickstart). Use the hackathon-provided Nebius access or your own Token Factory project, and configure `.env`:

```dotenv
LLM_BASE_URL=https://api.tokenfactory.nebius.com/v1
LLM_API_STYLE=chat_completions
LLM_API_KEY=
NEBIUS_API_KEY=<your-real-Nebius-key-without-angle-brackets>
LLM_MODEL=Qwen/Qwen3-235B-A22B-Instruct-2507
LLM_REASONING_EFFORT=
LLM_MAX_OUTPUT_TOKENS=2400
```

Leave `LLM_API_KEY` empty when using `NEBIUS_API_KEY`; the generic key takes precedence. An OpenAI key cannot authenticate to Nebius. Model IDs are case-sensitive and can be obtained from the Token Factory catalog or its authenticated `/v1/models` endpoint.

Run `.venv/bin/python -m continuity check-llm`. Once both synthetic evidence checks pass, set `REVIEW_MODE=llm` and restart the app. Until then, `REVIEW_MODE=deterministic` keeps Atlas-backed reviews available without provider calls. Switching providers does not change your stored packages or historical reviews; new reviews use the selected provider and invalidate incompatible cached findings.

## Alternative: OpenAI model calls

Create a project API key in the [OpenAI dashboard](https://platform.openai.com/api-keys) and paste it into the local `.env` file. This application uses `LLM_API_KEY`. It calls the [Responses API with structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs); `store=false` is sent on each request, while the harness keeps its checkpoints in your own database.

```dotenv
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=<your-real-key-without-angle-brackets>
LLM_MODEL=gpt-6-luna
LLM_API_STYLE=responses
LLM_REASONING_EFFORT=low
LLM_MAX_OUTPUT_TOKENS=2400
```

The starting model is [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna), with low reasoning effort for the two focused checks. Model availability depends on your API project. You can change `LLM_MODEL` and its supported reasoning effort; omit the effort value for models without that parameter.

Run the credentialed smoke check before enabling live mode:

```sh
.venv/bin/python -m continuity check-llm
```

This makes up to four billable model calls on synthetic evidence in a temporary SQLite database. It succeeds only when both findings match independently verified source evidence. It prints statuses, citation counts, and actual token usage without printing the key. It does not test Atlas or enable live mode automatically.

After the check passes, set `REVIEW_MODE=llm`, restart Uvicorn, and start a **new review**. Existing completed deterministic reviews retain their original results. The execution journal shows model decisions and reported token use; the review metrics show total model calls and tokens. Changing the model, API style, reasoning effort, or output budget invalidates cached findings for new reviews.

Refusals, truncated or invalid output, missing credentials, unavailable models, rate limits, and API quota failures never become synthetic success results. Provider messages are translated to fixed troubleshooting messages rather than echoing potentially private content. Model calls have a 55-second request timeout and there are at most two per check; there are no hidden automatic retries.

For Nebius, Fireworks, or another compatible provider, set its base URL, key and model, and use `LLM_API_STYLE=chat_completions`. That path retains local schema and evidence validation; the strict Responses schema applies to `responses` mode.

## Enable Atlas Vector Search

Atlas stores and searches the vectors; Nebius generates them using `Qwen/Qwen3-Embedding-8B`. This uses the same `NEBIUS_API_KEY` as the configured chat model, with separate embedding requests. The [Qwen model card](https://huggingface.co/Qwen/Qwen3-Embedding-8B) describes its 4,096-dimensional embeddings and query instructions. The application adds a retrieval instruction only to queries, leaving source passages unchanged.

```dotenv
STORAGE_BACKEND=mongodb
MONGODB_VECTOR_INDEX=evidence_qwen3_4096
EMBEDDING_PROVIDER=nebius
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B
EMBEDDING_DIMENSIONS=4096
VECTOR_SEARCH_ENABLED=false
```

1. Run `.venv/bin/python -m continuity setup-atlas`. This creates the index in the configured sandbox's `evidence_chunks` collection. Run it again to check `status: READY` and `queryable: true`. It will reject an incompatible existing definition instead of changing that index.
2. Run `.venv/bin/python -m continuity check-vector --output docs/vector_verification.json`. This uses live embedding calls and creates three synthetic packages to check semantic ranking, source offsets, and isolation across studies and versions. It works before enabling vector mode in `.env`.
3. Set `VECTOR_SEARCH_ENABLED=true`, run `.venv/bin/python -m continuity reindex` to embed existing packages, and restart the server. Reindex requires vector mode to be enabled. New uploads are embedded automatically.
4. Open **Evidence library**, enter a question, and click **Search evidence**. Results show source passages and similarity scores; **Inspect passage** highlights the source. Scores indicate similarity, not confidence in a finding. Start a new review to exercise the agent's vector retrieval path.

The index uses cosine similarity and pre-filters on study, package, and embedding profile (provider/model/dimensions/query format). Reviews also include the embedding profile and index name in their cache fingerprint. Changing these settings requires reindexing; use a new index name when dimensions or the definition change. Nebius currently uses the embedding model's native output size and rejects mismatches rather than truncating vectors. Atlas indexing is asynchronous: a newly uploaded package can briefly return no evidence; wait and retry. Provider/search failures are explicit, with no silent keyword fallback.

The live synthetic check is recorded in [vector verification](docs/vector_verification.json). It is a smoke check, not a general relevance benchmark. [MongoDB's index documentation](https://www.mongodb.com/docs/vector-search/indexes/vector-search-type/) explains vector fields and pre-filters.

Voyage is still supported: set `EMBEDDING_PROVIDER=voyage`, `EMBEDDING_MODEL=voyage-3.5-lite`, `EMBEDDING_DIMENSIONS=1024`, `VOYAGE_API_KEY`, and a new index name. Legacy `VOYAGE_MODEL`/`VOYAGE_DIMENSIONS` values are used when the generic embedding settings are empty/zero. This provider needs its own live verification.

MongoDB collections: `study_versions`, `evidence_chunks`, `review_memory`, `runs`, `leases`, plus the integration's checkpoint collections. Findings and their histories are persisted within immutable run checkpoints and exposed by review history/export.

## Validation and measurements

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m continuity benchmark --output docs/benchmark.json
```

The tests cover separate-process restart, revision and reversion, idempotence, scoped retrieval, source-bound notes and aliases, the Responses HTTP contract, refusal/truncation handling, sanitized provider errors, token accounting, a bounded agent tool loop, citation rejection, API validation, embedding response validation, vector filters, incompatible index protection, and embedding profile cache invalidation. Automated tests use mocked provider responses; live MongoDB/model/embedding calls require separate credentialed integration runs.

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

For the hackathon: use the provided Atlas Sandbox, verify accessible repository links, record the required one-minute video, and submit by the organizer's deadline. Public deployment, the video, and event submission have not been performed by this build. Commit timestamps and event eligibility must reflect when work was actually done; do not present pre-event implementation as event work. The older Streamlit code and assets are present only as archived source snapshots and are not imported by the active Continuity application.

See `docs/DEMO_SCRIPT.md` for the demonstration and `HACKATHON_PLAN.md` for the researched event plan. No cloud account is required for the local build.
