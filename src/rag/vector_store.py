"""Hybrid vector store for RAG retrieval.

Wraps the two knowledge bases used by SubmissionAI:

- **FDA Conformance KB** (``rag_knowledge_base/``) — 13 documents, 227 chunks.
  Used by :class:`ConformanceCheckerAgent`.
- **SAP Validator KB** (``sap_knowledge_base/``) — 12 documents, 182 chunks.
  Used by :class:`SAPValidatorAgent`.

Both KBs use the same hybrid retrieval pipeline:

1. **Dense** — ChromaDB + ``BAAI/bge-large-en-v1.5`` embeddings
2. **Sparse** — BM25Okapi with clinical term expansion (SAP, ITT, MMRM, …)
3. **RRF fusion** — Reciprocal Rank Fusion (k = 60)
4. **Cross-encoder re-ranking** — ``ms-marco-MiniLM-L-12-v2``

When the optional dependencies (``chromadb``, ``sentence-transformers``,
``rank-bm25``) are not installed the store falls back to a pure-Python BM25
index over built-in passage text, so the app always works.
"""
from __future__ import annotations

from typing import Any

from regulatory_knowledge_base import (
    build_conformance_rag_bundle as _build_conformance,
    build_no_prereq_rag_trace as _conformance_no_prereq,
    get_kb_metadata as _conformance_meta,
)
from sap_validator_knowledge_base import (
    build_sap_rag_bundle as _build_sap,
    get_sap_kb_metadata as _sap_meta,
)


class VectorStore:
    """Unified interface to both hybrid RAG knowledge bases.

    Instantiating this class has no side effects — KB indexes are built lazily
    on first retrieval and cached as module-level singletons in the underlying
    modules.

    Example
    -------
    >>> vs = VectorStore()
    >>> bundle = vs.retrieve_conformance(
    ...     queries=["eCTD module 5 completeness requirements"],
    ...     documents={"study_report.txt": "..."},
    ... )
    >>> print(bundle["retrieved_count"])
    """

    # ------------------------------------------------------------------ #
    # FDA Conformance KB                                                   #
    # ------------------------------------------------------------------ #

    def retrieve_conformance(
        self,
        queries: list[str],
        documents: dict[str, str] | None = None,
        validation_report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Retrieve passages from the FDA Conformance KB.

        Parameters
        ----------
        queries:
            List of retrieval queries (one per conformance domain).
        documents:
            Raw eCTD document texts (used to build a cross-document context
            section when ``chromadb`` is available).
        validation_report:
            Optional structural validation report from
            :func:`ectd_agent.assert_input_package_valid`.

        Returns
        -------
        dict
            ``{"prompt_context": str, "passages": list, "retrieved_count": int,
               "mode": "full_hybrid" | "no_prereq"}``
        """
        if documents is None:
            return _conformance_no_prereq(queries)
        return _build_conformance(
            queries=queries,
            documents=documents,
            validation_report=validation_report,
        )

    def conformance_metadata(self) -> dict[str, Any]:
        """Return FDA Conformance KB inventory (no side effects)."""
        return _conformance_meta()

    # ------------------------------------------------------------------ #
    # SAP Validator KB                                                     #
    # ------------------------------------------------------------------ #

    def retrieve_sap(
        self,
        sap_text: str,
        csr_text: str = "",
        trial_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Retrieve passages from the SAP Validator KB.

        Runs domain routing across seven SAP validation domains, then
        retrieves the most relevant passages from each domain's guideline
        subset.

        Parameters
        ----------
        sap_text:
            Full text of the Statistical Analysis Plan (truncated to 12 000
            characters internally if longer).
        csr_text:
            Full text of the Clinical Study Report (used for cross-document
            consistency checks).
        trial_metadata:
            Optional dict with keys ``database_lock_date``,
            ``primary_endpoint``, ``stratification_factors``,
            ``analysis_covariates`` (used by deterministic pre-flight checks).

        Returns
        -------
        dict
            ``{"prompt_context": str, "passages": list, "preflight_findings":
               list, "retrieved_count": int, "mode": str}``
        """
        return _build_sap(
            sap_text=sap_text,
            csr_text=csr_text,
            trial_metadata=trial_metadata or {},
        )

    def sap_metadata(self) -> dict[str, Any]:
        """Return SAP Validator KB inventory (no side effects)."""
        return _sap_meta()

    # ------------------------------------------------------------------ #
    # Combined                                                             #
    # ------------------------------------------------------------------ #

    def metadata(self) -> dict[str, Any]:
        """Return combined inventory for both KBs."""
        return {
            "conformance_kb": self.conformance_metadata(),
            "sap_kb": self.sap_metadata(),
        }
