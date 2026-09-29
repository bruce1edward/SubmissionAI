"""Agent 1 — Content Extractor.

Reads all documents in an eCTD package and extracts structured Phase 2 and
Phase 3 trial facts via an LLM call.  The extracted data feeds every
downstream agent.
"""
from __future__ import annotations

from typing import Any, Callable

from openai import OpenAI


# Forward to the root-level implementation so logic lives in one place.
from ectd_agent import agent_extract_content as _impl, _fallback_extracted_data


class ContentExtractorAgent:
    """Wraps :func:`ectd_agent.agent_extract_content` as a stateful agent.

    Parameters
    ----------
    model:
        Nebius model ID (e.g. ``"meta-llama/Llama-3.3-70B-Instruct"``).
    client:
        Authenticated :class:`openai.OpenAI` client pointed at Nebius.
    """

    def __init__(self, model: str, client: OpenAI) -> None:
        self.model = model
        self.client = client

    def run(self, documents: dict[str, str]) -> dict[str, Any]:
        """Extract Phase 2 / Phase 3 facts from *documents*.

        Parameters
        ----------
        documents:
            Mapping of ``{file_path: text}`` from
            :func:`ectd_agent.read_ectd_package`.

        Returns
        -------
        dict
            ``{"phase2": {...}, "phase3": {...}}`` schema.  Falls back to
            sensible defaults if the LLM call fails or returns unparseable
            JSON.
        """
        return _impl(documents, self.model, self.client)

    @staticmethod
    def fallback() -> dict[str, Any]:
        """Return the hard-coded fallback data (no LLM required)."""
        return _fallback_extracted_data()
