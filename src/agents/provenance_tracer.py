"""Agent 2 — Provenance Tracer.

Maps Phase 2 efficacy, dose selection, and safety signals to their Phase 3
counterparts and scores alignment across three dimensions: efficacy
traceability, dose justification, and safety monitoring coverage.
"""
from __future__ import annotations

from typing import Any

from openai import OpenAI

from ectd_agent import agent_trace_provenance as _impl, _fallback_provenance


class ProvenanceTracerAgent:
    """Wraps :func:`ectd_agent.agent_trace_provenance` as a stateful agent.

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
        documents: dict[str, str],
    ) -> dict[str, Any]:
        """Trace Phase 2 → Phase 3 data provenance.

        Parameters
        ----------
        extracted_data:
            Output of :class:`ContentExtractorAgent`.
        documents:
            Raw document texts from the eCTD package.

        Returns
        -------
        dict
            Provenance report with ``efficacy_traceability``,
            ``dose_justification``, ``safety_traceability``, and
            ``overall_provenance_score`` keys.
        """
        return _impl(extracted_data, documents, self.model, self.client)

    @staticmethod
    def fallback(extracted_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return the hard-coded fallback provenance report."""
        return _fallback_provenance()
