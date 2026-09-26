# Development history

SubmissionAI's Continuity harness is a separate implementation from the earlier SubmissionAI Streamlit application. This repository contains the FastAPI app, durable review workflow, browser console, synthetic fixtures, tests, and measured rehearsal records. Legacy agent modules, regulatory knowledge bases, and Streamlit assets are not included.

The first recorded harness snapshot was commit `335c7d0d52cba2d8178b3f2bc447d6fb9ebbe200` in the earlier `bruce1edward/SubmissionAI` repository, dated September 26, 2026 at 08:34:54 EDT. That snapshot already included checkpointing, reviewer memory, revision tracking, the console, and tests. This new repository imports the current implementation; its initial publication date is not the start of development.

Subsequent local work added live provider integration, Atlas Vector Search with Nebius embeddings, the final-configuration rehearsal and paired comparison, and presentation changes. The rehearsal reports describe observed functionality and measurements; they do not establish the development time of each feature.

The participant guide lists hacking as starting at 10:30 a.m. on September 26 and requires event-built work. Eligibility of the earlier harness snapshot has not been confirmed by organizers. Demo claims must follow their ruling and distinguish prior implementation from eligible event contributions.
