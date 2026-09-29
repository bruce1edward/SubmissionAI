# Development history

SubmissionAI's Continuity harness is a separate implementation from the earlier SubmissionAI Streamlit application. The active root contains the FastAPI app, durable review workflow, browser console, synthetic fixtures, tests, and measured rehearsal records. The consolidated repository also preserves the older code in `archive/SubmissionAI/` and `archive/SubmissonAI/`; the active app does not import it. The [repository provenance record](REPOSITORY_PROVENANCE.md) identifies the source commits and archived trees.

The original SubmissionAI repository's first recorded commit, `c4f4969cf728a2bf9eb290e2c1a75c7a6aac91eb`, is dated June 6, 2026 at 15:02:50 EDT. It contains the earlier regulatory RAG and Streamlit work, which is distinct from Continuity. The first recorded Continuity snapshot was commit `335c7d0d52cba2d8178b3f2bc447d6fb9ebbe200` in that same repository, dated September 26, 2026 at 08:34:54 EDT. That snapshot already included checkpointing, reviewer memory, revision tracking, the console, and tests. The later `Submission-AI` publication and this consolidation do not change when that code was developed.

The baseline also contained initial Chat Completions and Voyage-based Atlas vector retrieval code. Subsequent local work extended provider support and retrieval with Nebius embeddings, added live verification and the final-configuration rehearsal and paired comparison, and updated the presentation. The rehearsal reports describe observed functionality and measurements; they do not establish the development time of each feature.

The participant guide lists hacking as starting at 10:30 a.m. on September 26 and requires event-built work. Eligibility of the earlier harness snapshot has not been confirmed by organizers. Demo claims must follow their ruling and distinguish prior implementation from eligible event contributions.

See the [organizer request, evidence timeline, and contribution boundary](EVENT_ELIGIBILITY.md) for the pending clarification. Later verification timestamps establish when recorded tests ran, not when every feature was implemented.
