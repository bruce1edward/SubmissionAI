"""Agent 3 — SAP Validator.

Validates the Statistical Analysis Plan against seven regulatory domains using
a hybrid RAG knowledge base (ChromaDB dense retrieval + BM25Okapi sparse
retrieval + RRF fusion + cross-encoder re-ranking) and deterministic
pre-flight checks.

Domains
-------
pre_specification  ICH E9 §5.1 — SAP pre-specification before DB lock
estimand           ICH E9(R1) §3 — Estimand framework attributes
primary_endpoint   FDA Multiple Endpoints 2023
multiplicity       FDA Multiple Endpoints 2023 / ICH E9(R1)
subgroup           EMA Subgroup Analysis 2019
missing_data       EMA Missing Data 2010 / ICH E9(R1)
covariate          FDA Covariate Adjustment Guidance 2023
"""
from __future__ import annotations

from typing import Any

from openai import OpenAI

from ectd_agent import agent_validate_sap as _impl
from sap_validator_knowledge_base import (
    build_sap_rag_bundle,
    run_preflight_checks,
    get_sap_kb_metadata,
)


class SAPValidatorAgent:
    """Wraps :func:`ectd_agent.agent_validate_sap` with the SAP RAG system.

    The agent:

    1. Runs zero-LLM deterministic pre-flight checks (amendment timing,
       estimand completeness, stratification consistency).
    2. Retrieves domain-routed passages from the SAP Validator KB using
       hybrid retrieval (dense + BM25 + RRF + cross-encoder).
    3. Injects retrieved passages as prompt context for the LLM judge.
    4. Merges pre-flight findings into the LLM output.

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
        """Validate the SAP in *documents* against regulatory guidance.

        Parameters
        ----------
        extracted_data:
            Output of :class:`ContentExtractorAgent` (used to build
            ``trial_metadata`` for pre-flight checks).
        documents:
            Raw document texts; SAP and CSR are auto-detected by filename.

        Returns
        -------
        dict
            SAP validation result with ``findings``, ``endpoint_alignment``,
            ``missing_data_strategy``, ``multiplicity_control``,
            ``subgroup_analysis``, ``overall_score``, and ``sap_rag`` keys.
        """
        return _impl(extracted_data, documents, self.model, self.client)

    @staticmethod
    def preflight(
        sap_metadata: dict[str, Any],
        trial_timeline: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Run deterministic checks without any LLM call.

        Checks ICH E9 §5.1 (amendment after DB lock), ICH E9(R1) §3.1
        (estimand completeness), and FDA Covariate §III.A (stratification
        factor/covariate consistency).
        """
        return run_preflight_checks(sap_metadata, trial_timeline or {})

    @staticmethod
    def kb_metadata() -> dict[str, Any]:
        """Return SAP KB inventory (document count, chunk count, domains)."""
        return get_sap_kb_metadata()
