"""Utilities: python -m continuity benchmark|check-llm|check-vector|setup-atlas|reindex."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from uuid import uuid4

from .config import Settings
from .schemas import PackageInput
from .service import ingest_package
from .storage import make_store, now
from .retrieval import Retriever, RetrievalError
from .workflow import ReviewEngine

ROOT = Path(__file__).resolve().parents[1]


def benchmark():
    with TemporaryDirectory() as directory:
        settings = Settings(data_dir=Path(directory))
        store = make_store(settings)
        retriever = Retriever(store, settings)
        engine = ReviewEngine(store, settings, retriever)
        results = []
        for label, version, full in [("initial", "v1", False), ("incremental", "v2", False), ("full_comparison", "v2", True), ("reversion", "v3", False)]:
            package = ingest_package(store, retriever, PackageInput.model_validate_json((ROOT / "demo" / f"{version}.json").read_text()))
            started = time.perf_counter()
            run = engine.execute(engine.create(package, full)["id"])
            results.append({"scenario": label, "version": version, "wall_ms": round((time.perf_counter() - started) * 1000, 2),
                            "metrics": run["state"]["metrics"], "findings": {k: {"status": v["status"], "transition": v["transition"], "reused": v["reused"]} for k, v in run["state"]["results"].items()}})
        engine.close()
        store.close()
    return {"measured_at": now(), "mode": "deterministic", "storage": "sqlite", "retrieval": "lexical_local",
            "note": "Synthetic local harness benchmark. No LLM calls or Atlas measurements. Wall times include local checkpoint I/O and are not production performance claims.", "runs": results}


def check_llm():
    """Make up to four model requests against synthetic evidence, without Atlas writes."""
    with TemporaryDirectory() as directory:
        settings = replace(Settings.from_env(), storage_backend="sqlite", review_mode="llm",
                           vector_enabled=False, data_dir=Path(directory))
        settings.validate()
        store = make_store(settings)
        retriever = Retriever(store, settings)
        engine = ReviewEngine(store, settings, retriever)
        try:
            package = ingest_package(store, retriever, PackageInput.model_validate_json((ROOT / "demo" / "v1.json").read_text()))
            run = engine.execute(engine.create(package)["id"])
            findings = run["state"]["results"]
            return {"passed": all(f["status"] == "open" for f in findings.values()) and len(findings) == 2,
                    "model": settings.llm_model, "api_style": settings.llm_api_style,
                    "note": "Live model calls on synthetic evidence; temporary SQLite storage. Atlas persistence is tested separately.",
                    "metrics": run["state"]["metrics"],
                    "findings": {key: {"status": f["status"], "explanation": f["explanation"],
                                       "verified_citations": len(f["citations"])} for key, f in findings.items()}}
        finally:
            engine.close()
            store.close()


def check_vector():
    """Verify live embeddings, semantic retrieval, and version/study isolation."""
    settings = replace(Settings.from_env(), vector_enabled=True)
    settings.validate()
    store = make_store(settings)
    retriever = Retriever(store, settings)
    try:
        index = retriever.create_vector_index()
        if not index["queryable"]:
            return {"passed": False, "index": index, "note": "Wait for the index to become queryable, then run check-vector again."}
        study = "VECTOR-" + uuid4().hex[:8]
        packages = []
        for version, study_id in [("v1", study), ("v2", study), ("v1", study + "-OTHER")]:
            data = json.loads((ROOT / "demo" / f"{version}.json").read_text())
            data["study_id"] = study_id
            # More passages than the result limit demonstrate ranking as well as filtering.
            data["documents"].extend([
                {"id": f"distractor-{i}.txt", "title": "Unrelated synthetic memo", "kind": "supporting", "text": text}
                for i, text in enumerate([
                    "Cafeteria lunch includes soup, salad, and fresh fruit.",
                    "The office printer needs toner and recycled paper.",
                    "The courtyard garden has roses and lavender.",
                    "Train service stops at the airport and central station.",
                    "The conference room has blue chairs and a projector.",
                    "The annual picnic features music and games.",
                ])
            ])
            packages.append(ingest_package(store, retriever, PackageInput.model_validate(data)))
        query = "When is the main outcome measured?"
        results = []
        for package in packages:
            deadline = time.monotonic() + 45
            while True:
                try:
                    result = retriever.search(package, query, limit=2)
                    if len(result["passages"]) == 2:
                        break
                except RetrievalError:
                    if time.monotonic() >= deadline:
                        raise
                if time.monotonic() >= deadline:
                    raise RetrievalError("Vector search did not return two passages within the indexing wait")
                time.sleep(3)
            docs = {d["id"]: d for d in package["documents"]}
            passages = result["passages"]
            scoped = all(p["study_id"] == package["study_id"] and p["package_id"] == package["id"] for p in passages)
            faithful = all(p["source_hash"] == docs[p["document_id"]]["hash"] and
                           p["text"] == docs[p["document_id"]]["text"][p["start"]:p["end"]] for p in passages)
            relevant = passages[0]["document_id"] in {"protocol.txt", "sap.txt"}
            results.append({"version": package["version"], "other_study": package["study_id"] != study,
                            "scoped": scoped, "source_offsets_verified": faithful, "relevant_top_result": relevant,
                            "hits": [{"document_id": p["document_id"], "score": p["score"]} for p in passages]})
        return {"passed": all(r["scoped"] and r["source_offsets_verified"] and r["relevant_top_result"] for r in results),
                "verified_at": now(), "storage": "mongodb", "retrieval": "atlas_vector", "index": index,
                "embedding_provider": settings.embedding_provider, "embedding_model": settings.effective_embedding_model,
                "dimensions": settings.effective_embedding_dimensions, "query": query, "results": results,
                "note": "Live synthetic check of semantic ranking, source integrity, and study/version isolation; not a general retrieval benchmark. Creates three synthetic packages and makes embedding calls."}
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["benchmark", "check-llm", "check-vector", "setup-atlas", "reindex"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "benchmark":
        result = benchmark()
    elif args.command == "check-llm":
        result = check_llm()
    elif args.command == "check-vector":
        result = check_vector()
    else:
        settings = Settings.from_env()
        store = make_store(settings)
        retriever = Retriever(store, settings)
        try:
            if args.command == "setup-atlas":
                result = retriever.create_vector_index()
            else:
                if not settings.vector_enabled:
                    raise ValueError("Set VECTOR_SEARCH_ENABLED=true before reindexing for vector search")
                packages = store.list("study_versions")
                for package in packages:
                    retriever.index_package(package)
                result = {"reindexed_packages": len(packages), "vector_enabled": settings.vector_enabled}
        finally:
            store.close()
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")
    print(text)
    if args.command in {"check-llm", "check-vector"} and not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
