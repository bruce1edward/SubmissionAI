# Final configuration rehearsal

Demo drug name: **Mongdbtilimb**. Active study: `REHEARSAL-210a3222`. The demo lists show only this study’s v1, v2, and v3; older test studies remain stored but hidden. The display name does not rewrite source evidence or invalidate prior checkpoints. Keep subsequent notes and package revisions in this same study. The private `.data/rehearsal.json` file records the package and run IDs for continuing the rehearsal.

## Completed: v1 findings

Verified with Nebius chat calls, Nebius Qwen embeddings, and the hackathon MongoDB Atlas Vector Search index. Both checks were executed freshly, with no reused results.

| Check | Expected and observed result |
|---|---|
| Endpoint timing | Open: protocol specifies Week 8; SAP specifies Week 12 |
| Document coverage | Open: checklist requires `safety_appendix.txt`, which is absent |

All five citations matched the current documents. The completed checkpoint was read back from Atlas. The run used 3 model calls, 3 vector retrievals, and 5,084 chat tokens, with approximately 21 seconds for execution plus checkpoint read-back. Embedding token usage is separate.

[Machine-readable evidence](rehearsal_v1.json).

### Demo narration for this step

“This initial package has two consistency problems. The protocol schedules the primary assessment at Week 8, but the statistical analysis plan says Week 12. The checklist also requires a safety appendix that is missing. Each finding links to the exact source passage, and the review is saved in MongoDB Atlas.”

Open Review history and select this study's completed v1 review. Click the protocol and SAP citations to show the timing discrepancy, then the checklist citation to show the missing requirement. These are synthetic consistency checks, not clinical or regulatory advice.

## Completed: memory and restart recovery

The user saved the protocol-backed timing clarification, then created a fresh review with **Run one step**. The server was stopped and restarted. The same checkpoint and complete saved state were restored, including one reviewer note. The user resumed that review to completion: the timing check ran again, while the checklist result was reused. [Recovery evidence](rehearsal_recovery.json).

## Completed: v2 correction and reuse

Loaded version 2.0 under the same `REHEARSAL-210a3222` study. Only `sap.txt` changed: its primary assessment now matches the protocol at Week 8.

- **Endpoint timing: Resolved**, with exact Week 8 citations from both current documents.
- **Document coverage: Still open**, because `safety_appendix.txt` remains missing. The unchanged check was reused.
- **Reviewer memory: one note recalled**, because its protocol source is unchanged.
- **Measured work:** one check executed, one reused, one model call, one vector retrieval, and 1,901 chat tokens. Execution plus checkpoint read-back took about 12 seconds.
- The final checkpoint was read back from Atlas; all citations matched the v2 sources.

[Machine-readable v2 evidence](rehearsal_v2.json).

### Demo narration for v2

“I corrected the SAP to Week 8. Continuity detects that only this document changed, recalls my reviewer note, and reruns the timing check. That issue is now resolved. The missing appendix remains open, and its unchanged check is reused instead of spending another model call.”

## Completed: v3 reversion and paired comparison

Loaded v3 in the same study: SAP timing returns to Week 12 while the protocol stays at Week 8. The previously resolved timing finding **reopened**. The missing appendix remained open, and the incremental run reused its unchanged check. Both runs recalled the same reviewer note and preserved verified citations and Atlas checkpoints.

The incremental and full runs were created before either executed, freezing the same v2 baseline, v3 package, memory, and model settings.

| Measurement | Incremental v3 | Full v3 |
|---|---:|---:|
| Checks executed | 1 | 2 |
| Checks reused | 1 | 0 |
| Model calls | 1 | 3 |
| Vector retrievals | 1 | 3 |
| Chat tokens | 1,932 | 5,274 |
| Execution plus checkpoint read-back | 27.28 s | 29.80 s |
| Expected findings and source citations verified | Yes | Yes |

This single synthetic trial demonstrates fewer calls and chat tokens, not a general speedup or accuracy guarantee. Embedding requests are additional. Provider latency varied enough that the elapsed-time difference was small.

[Paired comparison evidence](rehearsal_v3_comparison.json).

### Demo narration for v3

“When the SAP reintroduces Week 12, Continuity reopens the timing issue instead of trusting the old resolution. It keeps the unchanged checklist result. In this measured example, that used one model call versus three for a full review, with the same verified findings.”

## Rehearsal outcome

The full planned sequence passed on the final Nebius + Atlas Vector Search configuration: initial findings, source-backed reviewer memory, restart recovery, v2 resolution, v3 reopening, and an incremental/full comparison. The tested restart was graceful; this does not establish weeks of reliability or recovery from every failure mode.

Next deliverables are publishing the current implementation and recording the one-minute submission video. Use Review history to open the existing rehearsal runs in order rather than creating duplicate runs for every take. Two v3 entries exist: the incremental entry reports one reused check; the full comparison reports zero.

With `DEMO_STUDY_ID=REHEARSAL-210a3222`, the sample-loading button targets this rehearsal study. `DEMO_DRUG_NAME=Mongdbtilimb` sets the display name. Clear both settings and restart to show the original full workspace. This presentation filter is not an access-control boundary.
