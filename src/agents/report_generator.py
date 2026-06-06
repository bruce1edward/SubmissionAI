"""Agent 5 — Report Generator.

Synthesises outputs from all four upstream agents into an executive
compliance report with an overall readiness score, prioritised remediation
items, and an estimated FDA review timeline.
"""
from __future__ import annotations

from typing import Any

from openai import OpenAI

from ectd_agent import agent_generate_report as _impl, _fallback_report


class ReportGeneratorAgent:
    """Wraps :func:`ectd_agent.agent_generate_report` as a stateful agent.

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
        conformance: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate the executive compliance report.

        Parameters
        ----------
        extracted_data:
            Output of :class:`ContentExtractorAgent`.
        provenance:
            Output of :class:`ProvenanceTracerAgent`.
        sap:
            Output of :class:`SAPValidatorAgent`.
        conformance:
            Output of :class:`ConformanceCheckerAgent`.

        Returns
        -------
        dict
            Report with ``overall_score``, ``approval_probability``,
            ``status``, ``priority_1_items``, ``priority_2_items``,
            ``fda_review_timeline``, and ``expected_fda_questions``.
        """
        return _impl(extracted_data, provenance, sap, conformance, self.model, self.client)

    @staticmethod
    def fallback(
        provenance: dict[str, Any],
        sap: dict[str, Any],
        conformance: dict[str, Any],
    ) -> dict[str, Any]:
        """Return the hard-coded fallback report (no LLM required)."""
        return _fallback_report(provenance, sap, conformance)
