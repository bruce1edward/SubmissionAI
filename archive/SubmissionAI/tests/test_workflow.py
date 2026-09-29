from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError

from continuity.config import Settings
from continuity.memory import approve_memory, recall_memory
from continuity.retrieval import Retriever
from continuity.reviewer import Reviewer, evaluate_explicit_check, verify
from continuity.schemas import AgentDecision, Citation, MemoryInput, PackageInput
from continuity.service import ingest_package
from continuity.storage import make_store, BusyRun
from continuity.workflow import ReviewEngine
from conftest import fixture_package, finish, ingest


def test_review_revision_reuse_and_reopening(system):
    engine = system[3]
    v1 = finish(engine, ingest(system, "v1"))
    assert [v["status"] for v in v1["state"]["results"].values()] == ["open", "open"]
    v2 = finish(engine, ingest(system, "v2"))
    assert v2["state"]["results"]["endpoint_alignment"]["transition"] == "resolved"
    assert v2["state"]["results"]["referenced_documents"]["status"] == "open"
    assert v2["state"]["results"]["referenced_documents"]["reused"] is True
    assert v2["state"]["metrics"]["checks_executed"] == 1
    assert v2["state"]["metrics"]["checks_reused"] == 1
    assert v2["state"]["changed_documents"] == ["sap.txt"]
    v3 = finish(engine, ingest(system, "v3"))
    assert v3["state"]["results"]["endpoint_alignment"]["transition"] == "reopened"
    assert len(v3["state"]["results"]) == 2
    assert engine.execute(v3["id"])["state"] == v3["state"]


def test_actual_process_exit_and_restart_preserves_completed_nodes(tmp_path):
    # Two separate interpreters prove the checkpoint is not just an in-memory cache.
    script = '''
import json,sys
from pathlib import Path
from continuity.config import Settings
from continuity.storage import make_store
from continuity.retrieval import Retriever
from continuity.workflow import ReviewEngine
from continuity.schemas import PackageInput
from continuity.service import ingest_package
s=Settings(data_dir=Path(sys.argv[1]));store=make_store(s);r=Retriever(store,s);e=ReviewEngine(store,s,r)
if sys.argv[2]=='start':
 p=ingest_package(store,r,PackageInput.model_validate_json(Path('demo/v1.json').read_text()))
 run=e.create(p);e.execute(run['id'],'step');result=e.execute(run['id'],'step')
else:
 result=e.execute(sys.argv[2])
print(json.dumps(result))
e.close();store.close()
'''
    first = json.loads(subprocess.check_output([sys.executable, "-c", script, str(tmp_path), "start"], text=True))
    assert first["status"] == "paused"
    assert first["state"]["completed_nodes"] == ["prepare", "endpoint_alignment"]
    second = json.loads(subprocess.check_output([sys.executable, "-c", script, str(tmp_path), first["id"]], text=True))
    assert second["status"] == "completed"
    assert second["state"]["metrics"]["checks_executed"] == 2
    assert second["state"]["results"]["endpoint_alignment"] == first["state"]["results"]["endpoint_alignment"]
    assert len(second["state"]["events"]) == 4


def test_memory_is_source_bound_and_invalidates_cache(system):
    settings, store, retriever, engine = system
    p = ingest(system)
    initial = finish(engine, p)
    memory = approve_memory(store, p, MemoryInput(
        package_id=p["id"], document_id="sap.txt", quote="Primary endpoint assessment: Week 12.",
        summary="This scheduled assessment conflicts with the protocol; verify it on every revision.", check_ids=["endpoint_alignment"],
    ))
    second = finish(engine, p)
    assert second["state"]["results"]["endpoint_alignment"]["reused"] is False
    assert second["state"]["results"]["endpoint_alignment"]["memory_ids"] == [memory["id"]]
    assert initial["state"]["memories"] == []
    v2 = ingest(system, "v2")
    active, stale = recall_memory(store, v2)
    assert active == [] and stale[0]["id"] == memory["id"]
    revised = finish(engine, v2)
    assert revised["state"]["stale_memory_count"] == 1
    assert revised["state"]["results"]["endpoint_alignment"]["status"] == "clear"


def test_scoped_memory_and_retrieval_do_not_cross_studies(system):
    _, store, retriever, engine = system
    a = ingest(system, study="STUDY-A")
    b = ingest(system, study="STUDY-B")
    approve_memory(store, a, MemoryInput(package_id=a["id"], document_id="protocol.txt", quote="Primary endpoint assessment: Week 8.", summary="Only STUDY-A may recall this note.", check_ids=["endpoint_alignment"]))
    result = finish(engine, b)
    assert result["state"]["memories"] == []
    assert all(p["study_id"] == "STUDY-B" and p["package_id"] == b["id"] for p in retriever.search(b, "Week") ["passages"])


def test_approved_alias_affects_coverage_and_goes_stale(system):
    _, store, retriever, engine = system
    data = fixture_package()
    data["documents"].append({"id":"safety_summary.txt", "title":"Safety summary", "kind":"supporting", "text":"This is the fictional safety appendix for SYN-014."})
    p = ingest_package(store, retriever, PackageInput.model_validate(data))
    assert finish(engine, p)["state"]["results"]["referenced_documents"]["status"] == "open"
    approve_memory(store, p, MemoryInput(package_id=p["id"], document_id="safety_summary.txt", quote="fictional safety appendix", summary="Verified that this source is the appendix referenced by the checklist.", check_ids=["referenced_documents"], kind="document_alias", alias="safety_appendix.txt"))
    current = finish(engine, p)
    assert current["state"]["results"]["referenced_documents"]["transition"] == "resolved"
    data["version"] = "2.0"
    data["documents"][-1]["text"] = "An unrelated supporting document has replaced the old content."
    changed = ingest_package(store, retriever, PackageInput.model_validate(data))
    assert finish(engine, changed)["state"]["results"]["referenced_documents"]["transition"] == "reopened"


def test_memory_rejects_fabricated_quote(system):
    p = ingest(system)
    with pytest.raises(ValueError, match="verbatim"):
        approve_memory(system[1], p, MemoryInput(package_id=p["id"], document_id="protocol.txt", quote="This is fabricated.", summary="Invalid review note", check_ids=["endpoint_alignment"]))


def test_same_version_is_immutable_and_ingest_is_idempotent(system):
    p = ingest(system)
    assert ingest(system)["id"] == p["id"]
    assert len(system[1].list("study_versions")) == 1
    data = fixture_package()
    data["documents"][0]["text"] += " Modified"
    with pytest.raises(ValueError, match="different content"):
        ingest_package(system[1], system[2], PackageInput.model_validate(data))


def test_invalid_llm_result_is_unresolved_not_sample_data(system):
    class InvalidClient:
        def decide(self, payload):
            return AgentDecision.model_validate({"status":"clear"}), {}
    settings = replace(system[0], review_mode="llm", llm_api_key="test-only", llm_model="test-model")
    reviewer = Reviewer(settings, system[2], InvalidClient())
    result, metrics, trace = reviewer.run("endpoint_alignment", ingest(system), [])
    assert result["status"] == "unresolved"
    assert result["citations"] == []
    assert "invalid structured response" in result["explanation"]
    assert metrics["model_calls"] == 1


def test_agent_requests_more_evidence_with_bounded_tool_budget(system):
    class RetrieverClient:
        def decide(self, payload):
            return AgentDecision(action="retrieve", query="Find the endpoint assessment"), {"total_tokens":7}
    settings = replace(system[0], review_mode="llm", llm_api_key="test-only", llm_model="test-model")
    result, metrics, _ = Reviewer(settings, system[2], RetrieverClient()).run("endpoint_alignment", ingest(system), [])
    assert result["status"] == "unresolved"
    assert metrics == {"model_calls":2,"retrieval_calls":2,"tokens":14}


def test_verifier_rejects_false_clear_and_invalid_citations(system):
    p = ingest(system)
    result = evaluate_explicit_check("endpoint_alignment", p, [])
    false_clear = result.model_copy(update={"status":"clear"})
    assert verify("endpoint_alignment", false_clear, p, []).status == "unresolved"
    fabricated = result.model_copy(update={"citations":[Citation(document_id="protocol.txt", quote="fabricated")]})
    assert verify("endpoint_alignment", fabricated, p, []).status == "unresolved"
    unrelated_advice = result.model_copy(update={"explanation":"Invented medical recommendations"})
    checked = verify("endpoint_alignment", unrelated_advice, p, [])
    assert checked.explanation == result.explanation


def test_unstructured_or_ambiguous_documents_do_not_get_clear(system):
    data = fixture_package()
    data["documents"][0]["text"] += "\nPrimary endpoint assessment: Week 4."
    p = ingest_package(system[1], system[2], PackageInput.model_validate(data))
    result = finish(system[3], p)
    assert result["state"]["results"]["endpoint_alignment"]["status"] == "unresolved"
    assert result["state"]["objective_status"] == "needs_input"


def test_force_full_does_not_reuse_cache(system):
    p = ingest(system)
    finish(system[3], p)
    reused = finish(system[3], p)
    assert reused["state"]["metrics"]["checks_reused"] == 2
    full = finish(system[3], p, force_full=True)
    assert full["state"]["metrics"]["checks_reused"] == 0
    assert full["state"]["metrics"]["checks_executed"] == 2


def test_concurrent_execution_lease_and_recovery(system):
    store = system[1]
    with store.lease("same-run"):
        with pytest.raises(BusyRun):
            with store.lease("same-run"):
                pytest.fail("Concurrent lease incorrectly granted")
    with store.lease("same-run"):
        pass


def test_expired_crashed_owner_does_not_block_resumption(system):
    store = system[1]
    with store.connection:
        store.connection.execute("INSERT INTO leases VALUES (?,?,?)", ("crashed-operation", "dead-owner", 0))
    with store.lease("crashed-operation"):
        with pytest.raises(BusyRun):
            with store.lease("crashed-operation"):
                pytest.fail("Duplicate execution must remain blocked after takeover")


def test_failure_preserves_successful_checkpoint(system, monkeypatch):
    p = ingest(system)
    engine = system[3]
    run = engine.create(p)
    engine.execute(run["id"], "step")
    original = engine.reviewer.run
    def fail(*args):
        raise RuntimeError("Injected infrastructure failure")
    monkeypatch.setattr(engine.reviewer, "run", fail)
    with pytest.raises(RuntimeError):
        engine.execute(run["id"])
    assert engine.snapshot(run["id"])["state"]["completed_nodes"] == ["prepare"]
    monkeypatch.setattr(engine.reviewer, "run", original)
    assert engine.execute(run["id"])["status"] == "completed"
