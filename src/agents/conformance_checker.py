"""Agent 4 — Conformance Checker.

Verifies the eCTD package against FDA submission standards using the FDA
Conformance Checker hybrid RAG knowledge base (227 chunks across 13 FDA, ICH,
EMA, and CFR documents).

Checks include:
- eCTD v4.0 technical conformance (FDA eCTD TCG)
- ICH M4 CTD module completeness (M4E, M4Q, M4S)
- 21 CFR Part 312 IND requirements
- Study data technical specifications (FDA Study Data TCG)
- Electronic records compliance (21 CFR Part 11)
- ICH E3 CSR structure
- Adaptive design considerations (FDA 2019)
"""
from __future__ import annotations

from typing import Any

from openai import OpenAI

from ectd_agent import agent_check_conformance as _impl
from regulatory_knowledge_base import (
    build_conformance_rag_bundle,
    get_kb_metadata,
)


class ConformanceCheckerAgent:
    """Wraps :func:`ectd_agent.agent_check_conformance` with the FDA RAG system.

    Parameters
    ----------
    model:
        Nebius model ID.
    client:
        Authenticated :class:`openai.OpenAI` client.
    """

    def __init__(self, model: str, client: OpenAI) -> None:
        self.model = model
        self.client = client

    def run(
        self,
        extracted_data: dict[str, Any],
        provenance: dict[str, Any],
        sap: dict[str, Any],
        documents: dict[str, str],
        validation_report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Check eCTD package conformance against FDA/ICH standards.

        Parameters
        ----------
        extracted_data:
            Output of :class:`ContentExtractorAgent`.
        provenance:
            Output of :class:`ProvenanceTracerAgent`.
        sap:
            Output of :class:`SAPValidatorAgent`.
        documents:
            Raw document texts.
        validation_report:
            Optional output of :func:`ectd_agent.assert_input_package_valid`
            (package structure pre-flight).

        Returns
        -------
        dict
            Conformance report with per-domain findings, ``issues``, and
            ``overall_conformance_score``.
        """
        return _impl(
            extracted_data,
            provenance,
            sap,
            documents,
            self.model,
            self.client,
            validation_report,
        )

    @staticmethod
    def kb_metadata() -> dict[str, Any]:
        """Return FDA Conformance KB inventory (document count, chunk count)."""
        return get_kb_metadata()
