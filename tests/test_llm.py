from dataclasses import replace
import json

import httpx
import pytest

from continuity.config import Settings
from continuity.reviewer import ChatClient, Reviewer, evaluate_explicit_check
from continuity.schemas import AgentDecision
from continuity.workflow import fingerprint
from conftest import ingest


def openai_settings(settings=None):
    return replace(settings or Settings(), review_mode="llm", llm_base_url="https://api.openai.com/v1",
                   llm_model="gpt-6-luna", llm_api_key="private-test-key", llm_api_style="responses",
                   llm_reasoning_effort="low")


def response_body(decision, **extra):
    return {"status": "completed", "usage": {"input_tokens": 80, "output_tokens": 20, "total_tokens": 100},
            "output": [{"type": "reasoning", "summary": []},
                       {"type": "message", "content": [{"type": "output_text", "text": decision.model_dump_json()}]}],
            **extra}


def install_transport(monkeypatch, handler):
    def post(url, *, headers, json, timeout):
        with httpx.Client(transport=httpx.MockTransport(handler), timeout=timeout) as client:
            return client.post(url, headers=headers, json=json)
    monkeypatch.setattr("continuity.reviewer.httpx.post", post)


def test_responses_request_uses_strict_schema_and_verifies_sources(system, monkeypatch):
    package = ingest(system)
    expected = evaluate_explicit_check("endpoint_alignment", package, [])

    def handler(request):
        assert str(request.url) == "https://api.openai.com/v1/responses"
        assert request.headers["authorization"] == "Bearer private-test-key"
        body = json.loads(request.content)
        assert body["store"] is False
        assert body["reasoning"] == {"effort": "low"}
        assert "temperature" not in body and "max_tokens" not in body
        assert body["max_output_tokens"] == 2400
        assert "missing_documents must always be an empty array" in body["input"][0]["content"]
        schema = body["text"]["format"]
        assert schema["strict"] is True
        assert set(schema["schema"]["required"]) == set(AgentDecision.model_fields)
        assert schema["schema"]["additionalProperties"] is False
        assert schema["schema"]["$defs"]["Citation"]["additionalProperties"] is False
        payload = json.loads(body["input"][1]["content"])
        assert payload["check_id"] == "endpoint_alignment"
        assert payload["document_inventory"] and payload["evidence"]
        return httpx.Response(200, json=response_body(expected))

    install_transport(monkeypatch, handler)
    result, metrics, trace = Reviewer(openai_settings(system[0]), system[2]).run("endpoint_alignment", package, [])
    assert result == expected.model_dump()
    assert metrics["model_calls"] == 1 and metrics["tokens"] == 100
    assert any(t["tool"] == "model" and "100 tokens" in t["detail"] for t in trace)


@pytest.mark.parametrize("variant", ["refusal", "incomplete", "empty", "invalid_json", "malformed_envelope"])
def test_unusable_response_keeps_usage_without_accepting_partial_findings(system, monkeypatch, variant):
    package = ingest(system)
    body = response_body(evaluate_explicit_check("endpoint_alignment", package, []))
    if variant == "refusal":
        body["output"][-1]["content"] = [{"type": "refusal", "refusal": "private provider message"}]
    elif variant == "incomplete":
        body["status"] = "incomplete"
        body["incomplete_details"] = {"reason": "max_output_tokens"}
    elif variant == "empty":
        body["output"] = []
    elif variant == "malformed_envelope":
        body["output"] = [None]
    else:
        body["output"][-1]["content"][0]["text"] = '{"status":'
    install_transport(monkeypatch, lambda request: httpx.Response(200, json=body))
    result, metrics, trace = Reviewer(openai_settings(system[0]), system[2]).run("endpoint_alignment", package, [])
    assert result["status"] == "unresolved" and result["citations"] == []
    assert metrics["tokens"] == 100 and metrics["model_calls"] == 1
    assert "private provider message" not in json.dumps([result, trace])


@pytest.mark.parametrize("status,code,expected", [
    (401, "invalid_api_key", "rejected the API key"),
    (403, "permission_denied", "does not have access"),
    (404, "model_not_found", "was not found"),
    (429, "insufficient_quota", "API quota"),
    (429, "credit_balance_exhausted", "API credits are exhausted"),
    (429, "project_spend_limit_exceeded", "project limit"),
    (429, "rate_limit_exceeded", "rate limit"),
    (400, "invalid_request_error", "request settings"),
    (503, "server_error", "temporarily unavailable"),
])
def test_provider_errors_are_actionable_and_do_not_echo_secrets(system, monkeypatch, status, code, expected):
    install_transport(monkeypatch, lambda request: httpx.Response(status, json={
        "error": {"code": code, "message": "private-test-key private document text"}}))
    result, metrics, trace = Reviewer(openai_settings(system[0]), system[2]).run("endpoint_alignment", ingest(system), [])
    assert result["status"] == "unresolved" and expected in result["explanation"]
    assert metrics["model_calls"] == 1 and metrics["tokens"] == 0
    assert "private-test-key" not in json.dumps([result, trace])
    assert "private document text" not in json.dumps([result, trace])


def test_responses_tool_loop_stops_after_one_extra_retrieval(system, monkeypatch):
    calls = []

    def handler(request):
        payload = json.loads(json.loads(request.content)["input"][1]["content"])
        calls.append(payload["retrieval_retry_available"])
        return httpx.Response(200, json=response_body(AgentDecision(action="retrieve", query="primary timing")))

    install_transport(monkeypatch, handler)
    result, metrics, _ = Reviewer(openai_settings(system[0]), system[2]).run("endpoint_alignment", ingest(system), [])
    assert calls == [True, False]
    assert result["status"] == "unresolved" and "budget" in result["explanation"]
    assert metrics == {"model_calls": 2, "retrieval_calls": 2, "tokens": 200}


def test_valid_structured_json_still_rejects_fabricated_evidence(system, monkeypatch):
    package = ingest(system)
    forged = evaluate_explicit_check("endpoint_alignment", package, []).model_copy(deep=True)
    forged.citations[0].quote = "This quotation was invented."
    install_transport(monkeypatch, lambda request: httpx.Response(200, json=response_body(forged)))
    result, _, _ = Reviewer(openai_settings(system[0]), system[2]).run("endpoint_alignment", package, [])
    assert result["status"] == "unresolved" and "rejected a citation" in result["explanation"]


def test_chat_compatible_provider_remains_supported(monkeypatch):
    decision = AgentDecision(action="conclude", status="unresolved", explanation="Missing evidence.")

    def handler(request):
        assert request.url.path == "/v1/chat/completions"
        assert "messages" in json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "content": decision.model_dump_json()}}], "usage": {"total_tokens": 12}})

    install_transport(monkeypatch, handler)
    result, usage = ChatClient(Settings(llm_api_key="test", llm_model="compatible-model")).decide({})
    assert result == decision and usage["total_tokens"] == 12


def test_changed_generation_settings_invalidate_cached_findings(system):
    package = ingest(system)
    settings = openai_settings(system[0])
    baseline = fingerprint("endpoint_alignment", package, [], settings)
    for changed in [replace(settings, llm_api_style="chat_completions"),
                    replace(settings, llm_reasoning_effort="medium"),
                    replace(settings, llm_max_output_tokens=4000)]:
        assert fingerprint("endpoint_alignment", package, [], changed) != baseline
