# Repository provenance and development timeline

The application at the root of this consolidated repository is the Continuity document-review harness. It is based on the later `Submission-AI` source tree. Two other repositories are retained as complete file-tree snapshots under `archive/`, and their original Git commits are reachable through non-squashed merge parents. The archived source is historical context, not a runtime dependency of the active application.

| Original repository | Earliest recorded commit | Tip at consolidation | Commits | Preserved files |
|---|---|---|---:|---|
| `bruce1edward/SubmissionAI` | `c4f4969cf728a2bf9eb290e2c1a75c7a6aac91eb`, June 6, 2026, 15:02:50 EDT | `335c7d0d52cba2d8178b3f2bc447d6fb9ebbe200` | 9 | `archive/SubmissionAI/` |
| `bruce1edward/Submission-AI` | `e26eca8143e9d810ff7854122dc936c71e5e7ee0`, September 26, 2026, 14:40:02 EDT | `02a35f771eedef7f9de90f1066b7bc596ea98f9d` | 3 | Active root tree before consolidation |
| `bruce1edward/SubmissonAI` | `eb7fc87ce3b2bc115d8b51b26dfeaea2a9ae7992`, June 6, 2026, 15:18:18 EDT | `3d1a8b7a655e8b77d3c632b87299b09d86a1f9af` | 2 | `archive/SubmissonAI/` |

The June repositories contain the earlier Streamlit/ChromaDB regulatory RAG implementation and supporting knowledge-base material. The original `SubmissionAI` repository later added the first Continuity harness in commit `335c7d0d52cba2d8178b3f2bc447d6fb9ebbe200`, recorded at 08:34:54 EDT on September 26. That commit moved the earlier Streamlit `app.py` to `legacy_streamlit_app.py` without changing its file content and replaced the root app with the new review harness. The `Submission-AI` repository subsequently published the more developed Continuity implementation, tests, Atlas/model/vector verification records, and rehearsal evidence. The active root reflects that later tree; see [development history](DEVELOPMENT_HISTORY.md) and the [event eligibility timeline](EVENT_ELIGIBILITY.md).

The original commit objects, author and committer metadata, and source trees were not rewritten. To verify preservation after cloning this consolidated repository:

```text
git merge-base --is-ancestor 02a35f771eedef7f9de90f1066b7bc596ea98f9d main
git merge-base --is-ancestor 335c7d0d52cba2d8178b3f2bc447d6fb9ebbe200 main
git merge-base --is-ancestor 3d1a8b7a655e8b77d3c632b87299b09d86a1f9af main
git rev-parse main:archive/SubmissionAI
git rev-parse 335c7d0d52cba2d8178b3f2bc447d6fb9ebbe200^{tree}
git rev-parse main:archive/SubmissonAI
git rev-parse 3d1a8b7a655e8b77d3c632b87299b09d86a1f9af^{tree}
```

The two `archive/SubmissionAI` tree hashes should both be `4b02a2bff6ee044d5ba14228f37a9e63fb28d747`; the two `archive/SubmissonAI` tree hashes should both be `15d59a358512f84d880c9e70f17e63bfea905ad1`.

These dates are recorded Git metadata and do not independently prove the first development date, authorship, or hackathon eligibility. In particular, the first Continuity snapshot predates the 10:30 EDT hacking start listed in the supplied participant guide. A later repository publication or consolidation must not be presented as the start of that work. The original GitHub repository URLs identify the sources; if those repositories are deleted, their separate GitHub settings and pages will no longer be available. Complete local Git bundles were made before consolidation as an additional backup.
