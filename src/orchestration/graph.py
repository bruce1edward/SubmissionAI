"""Sequential agent graph for eCTD readiness analysis.

The pipeline runs five agents in a fixed dependency order:

  ContentExtractor → ProvenanceTracer → SAPValidator
                                      ↘
                                        ConformanceChecker → ReportGenerator

All agents share the same LLM client and model.  Results from each step are
passed downstream as inputs.

The public entry points are:

- :func:`run_pipeline` — convenience wrapper around :func:`ectd_agent.run_ectd_analysis`
- :class:`AgentGraph` — object-oriented interface with per-step access
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from openai import OpenAI

# The canonical implementation lives in the root-level module so this graph
# module stays thin and avoids duplicating orchestration logic.
from ectd_agent import (
    run_ectd_analysis as _run,
    get_llm_client,
    read_ectd_package,
    assert_input_package_valid,
    DEFAULT_MODEL,
)
from src.agents.content_extractor import ContentExtractorAgent
from src.agents.provenance_tracer import ProvenanceTracerAgent
from src.agents.sap_validator import SAPValidatorAgent
from src.agents.conformance_checker import ConformanceCheckerAgent
from src.agents.report_generator import ReportGeneratorAgent


def run_pipeline(
    package_path: str | Path,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Run the full five-agent eCTD analysis pipeline.

    Parameters
    ----------
    package_path:
        Path to an eCTD ZIP file or directory containing submission documents.
    model:
        Nebius model ID (default: ``ectd_agent.DEFAULT_MODEL``).
    api_key:
        Nebius API key.  Falls back to the ``NEBIUS_API_KEY`` environment
        variable if *None*.
    progress_callback:
        Optional callable called with a status string before each step.

    Returns
    -------
    dict
        Full analysis result with keys: ``overall_score``,
        ``approval_probability``, ``status``, ``extracted_data``,
        ``provenance``, ``sap``, ``conformance``, ``report``,
        ``priority_items``, ``fda_questions``, ``timeline``.
    """
    return _run(
        package_path=package_path,
        model=model,
        api_key=api_key,
        progress_callback=progress_callback,
    )


class AgentGraph:
    """Object-oriented interface to the five-agent pipeline.

    Instantiate once, then call :meth:`run` or individual step methods to
    control execution.

    Parameters
    ----------
    model:
        Nebius model ID.
    api_key:
        Nebius API key (or set ``NEBIUS_API_KEY`` env var).

    Example
    -------
    >>> graph = AgentGraph(model="meta-llama/Llama-3.3-70B-Instruct", api_key="nbs-...")
    >>> result = graph.run("path/to/ectd_package.zip")
    >>> print(result["overall_score"])
    """

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None) -> None:
        self.model = model
        self.client: OpenAI = get_llm_client(api_key)

        self.content_extractor = ContentExtractorAgent(model, self.client)
        self.provenance_tracer = ProvenanceTracerAgent(model, self.client)
        self.sap_validator = SAPValidatorAgent(model, self.client)
        self.conformance_checker = ConformanceCheckerAgent(model, self.client)
        self.report_generator = ReportGeneratorAgent(model, self.client)

    def run(
        self,
        package_path: str | Path,
        progress_callback: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        """Execute the full pipeline on *package_path*."""
        return run_pipeline(
            package_path=package_path,
            model=self.model,
            api_key=None,  # client already authenticated
            progress_callback=progress_callback,
        )

    def run_step_by_step(
        self,
        package_path: str | Path,
    ) -> dict[str, Any]:
        """Run each agent individually and return intermediate outputs.

        Useful for debugging or partial re-runs.

        Returns
        -------
        dict
            ``{"documents": ..., "extracted": ..., "provenance": ...,
               "sap": ..., "conformance": ..., "report": ...}``
        """
        validation_report = assert_input_package_valid(package_path)
        documents = read_ectd_package(package_path)

        extracted = self.content_extractor.run(documents)
        provenance = self.provenance_tracer.run(extracted, documents)
        sap = self.sap_validator.run(extracted, documents)
        conformance = self.conformance_checker.run(
            extracted, provenance, sap, documents, validation_report
        )
        report = self.report_generator.run(extracted, provenance, sap, conformance)

        return {
            "documents": documents,
            "extracted": extracted,
            "provenance": provenance,
            "sap": sap,
            "conformance": conformance,
            "report": report,
        }
