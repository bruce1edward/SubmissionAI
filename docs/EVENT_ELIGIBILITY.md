# SubmissionAI: eligibility clarification

Status: prepared for Bruce to send or discuss with organizers. Not sent. No eligibility ruling has been received.

## Ready-to-send message

Hi CV team — I need an eligibility ruling for my solo project, SubmissionAI:
https://github.com/bruce1edward/Submission-AI

It is a separate implementation from my earlier Streamlit project, but I started the new implementation before the scheduled hacking start. A baseline harness commit is timestamped September 26 at 8:34 a.m. EDT, before the guide's 10:30 a.m. start. That baseline already contained memory, checkpoints, revision tracking, a review UI, and initial model/vector integration code.

I subsequently extended the provider and retrieval integration and completed live Atlas Sandbox/model/vector-search testing and the v1–v3 rehearsal. The verification reports are timestamped between 12:31 p.m. and 2:20 p.m. EDT. Those timestamps establish when the recorded tests ran, not when all implementation began. The new repository is a publication of that work; it does not change the development timeline.

Does the event permit this pre-start baseline with disclosed later contributions? If so, which features may I demonstrate and have judged? If the entire entry is ineligible under the new-work rule, is there an approved way to participate with a separately scoped new component, or as a noncompetitive demo?

I can provide the baseline snapshot, current source, and verification reports. I will follow your ruling and accurately disclose the work that predates the hacking window.

## Evidence timeline

All times below are September 26, 2026, America/New_York (EDT, UTC−04:00). Git and report timestamps are recorded evidence, not independent attestations of authorship or event eligibility.

| Time | Evidence | What it establishes |
|---|---|---|
| 08:23:27 | `docs/benchmark.json`, `measured_at` | A recorded deterministic benchmark predates the hacking start. |
| 08:34:54 | Baseline commit `335c7d0d52cba2d8178b3f2bc447d6fb9ebbe200`; author and committer timestamps agree | Baseline source snapshot already contains the core harness and initial integrations. |
| 10:30 | Supplied participant guide, schedule | Listed hacking start. |
| 12:31:49 | `docs/live_llm_verification.json` | Recorded live model/review verification. |
| 12:49:56 | `docs/nebius_verification.json` | Recorded Nebius verification. |
| 13:04:49 | `docs/vector_verification.json` | Recorded Atlas vector retrieval verification. |
| 13:10:48 | `docs/vector_agent_verification.json` | Recorded agent review using vector retrieval. |
| 13:49:23 | `docs/rehearsal_v1.json` | Recorded final-configuration v1 rehearsal. |
| 14:09:33 | `docs/rehearsal_recovery.json` | Recorded recovery verification. |
| 14:14:56 | `docs/rehearsal_v2.json` | Recorded v2 rehearsal. |
| 14:20:11 | `docs/rehearsal_v3_comparison.json` | Recorded paired v3 incremental/full review comparison. |

## Contribution boundary

| Already in the baseline | Later additions or verification in the current snapshot |
|---|---|
| Durable review graph, checkpoint resume, source-bound memory, version/dependency tracking, resolution/reopening logic, synthetic fixtures, browser console | Live final-configuration rehearsal and paired measurement reports |
| Generic Chat Completions client and bounded retrieval loop | Responses API support, stronger provider response/error handling, additional live provider verification and tests |
| MongoDB storage/checkpoint support and Voyage-based Atlas vector retrieval code | Nebius Qwen embeddings, embedding-profile validation/filtering, additional vector validation, interactive evidence search and live verification |
| Original review UI | Mongdbtilimb rehearsal filtering and updated branding |

“Later” means different from or additional to the baseline. The available snapshots do not establish the exact coding time of every change. Do not label all later additions as event-built without adequate evidence and an organizer ruling.

## Next action after the ruling

- If organizers permit the baseline: record their exact scope and conditions, then revise the demo to distinguish that baseline from eligible additions.
- If organizers require entirely new work: do not submit this harness as wholly event-built. Confirm whether a genuinely separate, newly implemented component or noncompetitive demonstration is permitted before proceeding.
- Preserve the original timestamps and reports in either case. Repository creation time does not establish implementation time.
