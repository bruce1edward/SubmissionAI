"""Local utilities: python -m continuity benchmark|setup-atlas|reindex."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from .config import Settings
from .schemas import PackageInput
from .service import ingest_package
from .storage import make_store, now
from .retrieval import Retriever
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["benchmark", "setup-atlas", "reindex"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "benchmark":
        result = benchmark()
    else:
        settings = Settings.from_env()
        store = make_store(settings)
        retriever = Retriever(store, settings)
        try:
            if args.command == "setup-atlas":
                result = retriever.create_vector_index()
            else:
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


if __name__ == "__main__":
    main()
