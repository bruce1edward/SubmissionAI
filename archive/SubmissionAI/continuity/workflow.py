from copy import deepcopy
from pathlib import Path
import sqlite3
import time
from typing import TypedDict
from uuid import uuid4

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.mongodb import MongoDBSaver

from .memory import recall_memory
from .reviewer import Reviewer
from .schemas import CHECKS, CHECK_TITLES
from .storage import digest, now

HARNESS_VERSION = "continuity-1.0"


class ReviewState(TypedDict, total=False):
    run_id: str
    package: dict
    baseline_id: str | None
    baseline_results: dict
    memories: list
    stale_memory_count: int
    force_full: bool
    results: dict
    events: list
    completed_nodes: list
    metrics: dict
    objective_status: str
    changed_documents: list


def fingerprint(check_id, package, memories, settings):
    if check_id == "endpoint_alignment":
        dependencies = sorted((d["id"], d["hash"]) for d in package["documents"] if d["kind"] in {"protocol", "sap"})
    else:
        # Coverage depends on the checklist content and full inventory, not SAP prose.
        dependencies = {
            "checklists": sorted((d["id"], d["hash"]) for d in package["documents"] if d["kind"] == "checklist"),
            "inventory": sorted(d["id"] for d in package["documents"]),
        }
    return digest({"check": check_id, "dependencies": dependencies,
                   "memory": sorted(m["id"] for m in memories if check_id in m["check_ids"]),
                   "harness": HARNESS_VERSION, "mode": settings.review_mode,
                   "model": settings.llm_model, "provider": settings.llm_base_url,
                   "retrieval": "atlas" if settings.vector_enabled else "lexical",
                   "embedding_model": settings.voyage_model if settings.vector_enabled else None})


def transition(previous, current):
    if not previous:
        return "new" if current == "open" else ("unresolved" if current == "unresolved" else "clear")
    old = previous["status"]
    if current == "unresolved":
        return "unresolved"
    if old == "open" and current == "clear":
        return "resolved"
    if old == "clear" and current == "open":
        return "reopened"
    if old == "unresolved":
        return "new" if current == "open" else "clear"
    return "unchanged"


class ReviewEngine:
    def __init__(self, store, settings, retriever, client=None):
        self.store, self.settings = store, settings
        self.reviewer = Reviewer(settings, retriever, client)
        self.checkpoint_connection = None
        if store.backend == "mongodb":
            self.saver = MongoDBSaver(store.client, db_name=settings.mongodb_database)
        else:
            self.checkpoint_connection = sqlite3.connect(str(settings.data_dir / "checkpoints.sqlite3"), check_same_thread=False)
            self.saver = SqliteSaver(self.checkpoint_connection)
        graph = StateGraph(ReviewState)
        graph.add_node("prepare", self.prepare)
        graph.add_node("endpoint_alignment", lambda s: self.check(s, "endpoint_alignment"))
        graph.add_node("referenced_documents", lambda s: self.check(s, "referenced_documents"))
        graph.add_node("finalize", self.finalize)
        graph.add_edge(START, "prepare")
        graph.add_edge("prepare", "endpoint_alignment")
        graph.add_edge("endpoint_alignment", "referenced_documents")
        graph.add_edge("referenced_documents", "finalize")
        graph.add_edge("finalize", END)
        self.graph = graph.compile(checkpointer=self.saver)

    @staticmethod
    def config(run_id):
        return {"configurable": {"thread_id": run_id}, "recursion_limit": 12}

    def create(self, package, force_full=False):
        previous_runs = self.store.list("runs", {"study_id": package["study_id"], "status": "completed"})
        baseline = previous_runs[0] if previous_runs else None
        baseline_state = self.snapshot(baseline["id"])["state"] if baseline else {}
        active, stale = recall_memory(self.store, package)
        prior_docs = {d["id"]: d["hash"] for d in baseline_state.get("package", {}).get("documents", [])}
        next_docs = {d["id"]: d["hash"] for d in package["documents"]}
        run_id = uuid4().hex
        initial = {
            "run_id": run_id, "package": package, "force_full": force_full,
            "baseline_id": baseline["id"] if baseline else None,
            "baseline_results": deepcopy(baseline_state.get("results", {})),
            "memories": active, "stale_memory_count": len(stale),
            "changed_documents": sorted(k for k in set(prior_docs) | set(next_docs) if prior_docs.get(k) != next_docs.get(k)),
            "results": {}, "events": [], "completed_nodes": [], "objective_status": "pending",
            "metrics": {"model_calls": 0, "retrieval_calls": 0, "tokens": 0, "checks_executed": 0, "checks_reused": 0, "active_ms": 0},
        }
        record = {"id": run_id, "study_id": package["study_id"], "package_id": package["id"],
                  "version": package["version"], "status": "ready", "created_at": now(),
                  "review_mode": self.settings.review_mode, "storage": self.store.backend,
                  "initial_state": initial, "error": None}
        self.store.put("runs", record)
        return self.snapshot(run_id)

    def snapshot(self, run_id):
        record = self.store.get("runs", run_id)
        if not record:
            raise KeyError("Review not found")
        checkpoint = self.graph.get_state(self.config(run_id))
        state = dict(checkpoint.values) if checkpoint.values else record["initial_state"]
        next_nodes = list(checkpoint.next) if checkpoint.values else ["prepare"]
        status = record["status"]
        if state.get("objective_status") in {"review_complete", "needs_input"} and not next_nodes:
            status = "completed"
        return {**{k: v for k, v in record.items() if k != "initial_state"}, "status": status,
                "state": state, "next_nodes": next_nodes, "checkpoint_id":
                checkpoint.config.get("configurable", {}).get("checkpoint_id") if checkpoint.config else None}

    def execute(self, run_id, mode="continue"):
        with self.store.lease("run:" + run_id):
            record = self.store.get("runs", run_id)
            if not record:
                raise KeyError("Review not found")
            snap = self.snapshot(run_id)
            if snap["status"] == "completed":
                record.update(status="completed", error=None)
                self.store.put("runs", record)
                return snap
            record.update(status="running", error=None)
            self.store.put("runs", record)
            try:
                checkpoint = self.graph.get_state(self.config(run_id))
                self.graph.invoke(
                    None if checkpoint.values else record["initial_state"], self.config(run_id),
                    interrupt_after=["prepare", *CHECKS, "finalize"] if mode == "step" else [],
                )
                after = self.graph.get_state(self.config(run_id))
                record["status"] = "paused" if after.next else "completed"
            except Exception:
                # Provider/validation failures are represented as unresolved findings.
                # Unexpected infrastructure failures retain the last committed checkpoint.
                record.update(status="failed", error="Workflow interrupted by an infrastructure error. The last completed checkpoint is retained; inspect server logs and resume.")
                raise
            finally:
                self.store.put("runs", record)
            return self.snapshot(run_id)

    def event(self, state, node, detail, **extra):
        return {"id": f"{state['run_id']}:{node}:{len(state['events'])}", "at": now(), "node": node, "detail": detail, **extra}

    def prepare(self, state):
        event = self.event(state, "prepare", f"Loaded {len(state['memories'])} applicable reviewer memories; excluded {state['stale_memory_count']} stale memories. Selected checks using document and memory fingerprints.")
        return {"events": [*state["events"], event], "completed_nodes": [*state["completed_nodes"], "prepare"]}

    def check(self, state, check_id):
        start = time.perf_counter()
        package = state["package"]
        memories = [m for m in state["memories"] if check_id in m["check_ids"]]
        check_hash = fingerprint(check_id, package, memories, self.settings)
        previous = state["baseline_results"].get(check_id)
        metrics = dict(state["metrics"])
        cached = bool(previous and previous["fingerprint"] == check_hash and previous["status"] != "unresolved" and not state["force_full"])
        if cached:
            result = deepcopy(previous)
            result.update(reused=True, reused_from=state["baseline_id"], transition="unchanged")
            # Source IDs/hashes are stable; rebind links to this version's immutable package.
            result["package_id"] = package["id"]
            trace = [{"tool": "reuse_checkpoint_result", "detail": "All input fingerprints match. Reused the verified result without a model call."}]
            metrics["checks_reused"] += 1
        else:
            decision, usage, trace = self.reviewer.run(check_id, package, memories)
            for key, val in usage.items():
                metrics[key] += val
            metrics["checks_executed"] += 1
            result = {**decision, "id": digest([package["study_id"], check_id])[:24],
                      "check_id": check_id, "title": CHECK_TITLES[check_id], "fingerprint": check_hash,
                      "package_id": package["id"], "reused": False, "reused_from": None,
                      "transition": transition(previous, decision["status"])}
        result["memory_ids"] = [m["id"] for m in memories]
        metrics["active_ms"] += round((time.perf_counter() - start) * 1000, 2)
        event = self.event(state, check_id, f"{CHECK_TITLES[check_id]}: {result['status']} ({result['transition']}).", trace=trace, reused=cached)
        return {"results": {**state["results"], check_id: result}, "metrics": metrics,
                "events": [*state["events"], event], "completed_nodes": [*state["completed_nodes"], check_id]}

    def finalize(self, state):
        unresolved_count = sum(r["status"] == "unresolved" for r in state["results"].values())
        status = "needs_input" if unresolved_count else "review_complete"
        event = self.event(state, "finalize", "Review finished with unresolved checks requiring human input." if unresolved_count else "All configured checks completed with verified evidence. This is not a regulatory approval assessment.")
        return {"objective_status": status, "events": [*state["events"], event], "completed_nodes": [*state["completed_nodes"], "finalize"]}

    def close(self):
        if self.checkpoint_connection:
            self.checkpoint_connection.close()
