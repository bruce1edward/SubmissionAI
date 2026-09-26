from contextlib import asynccontextmanager
import hmac
import json
import logging
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from continuity.config import Settings
from continuity.memory import approve_memory, recall_memory
from continuity.retrieval import Retriever, RetrievalError
from continuity.schemas import PackageInput, RunInput, ExecuteInput, DemoInput, MemoryInput, SearchInput
from continuity.service import ingest_package
from continuity.storage import make_store, BusyRun, now
from continuity.workflow import ReviewEngine

ROOT = Path(__file__).resolve().parent
log = logging.getLogger("continuity")


def create_app(settings=None):
    settings = settings or Settings.from_env()
    settings.validate()

    @asynccontextmanager
    async def lifespan(app):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        store = make_store(settings)
        retriever = Retriever(store, settings)
        engine = ReviewEngine(store, settings, retriever)
        app.state.store, app.state.retriever, app.state.engine = store, retriever, engine
        yield
        engine.close()
        store.close()

    app = FastAPI(title="SubmissionAI Continuity", version="1.0.0", lifespan=lifespan)

    @app.middleware("http")
    async def boundaries(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            if origin and urlparse(origin).netloc != request.headers.get("host"):
                return JSONResponse({"detail": "Cross-origin API requests are not permitted"}, status_code=403)
            if settings.access_token:
                supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
                if not hmac.compare_digest(supplied, settings.access_token):
                    return JSONResponse({"detail": "Enter the configured app access token"}, status_code=401)
            size = request.headers.get("content-length", "0")
            if not size.isdigit() or int(size) > 1_000_000:
                return JSONResponse({"detail": "Package size limit is 1 MB"}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(BusyRun)
    async def busy_handler(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(RetrievalError)
    async def retrieval_handler(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=503)

    @app.exception_handler(ValueError)
    async def value_handler(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    def package_or_404(package_id):
        value = app.state.store.get("study_versions", package_id)
        if not value:
            raise HTTPException(404, "Package not found")
        return value

    def run_or_404(run_id):
        if not app.state.store.get("runs", run_id):
            raise HTTPException(404, "Review not found")
        return app.state.engine.snapshot(run_id)

    @app.get("/api/status")
    def status():
        return {"name": "SubmissionAI Continuity", "storage": settings.storage_backend,
                "review_mode": settings.review_mode,
                "demo_study_id": settings.demo_study_id,
                "demo_drug_name": settings.demo_drug_name,
                "retrieval": "atlas_vector" if settings.vector_enabled else "lexical_local",
                "embedding_model": settings.effective_embedding_model if settings.vector_enabled else None,
                "vector_index": settings.vector_index if settings.vector_enabled else None,
                "model": settings.llm_model if settings.review_mode == "llm" else None,
                "llm_api_style": settings.llm_api_style if settings.review_mode == "llm" else None,
                "atlas_connected": settings.storage_backend == "mongodb",
                "live_services_configured": settings.storage_backend == "mongodb" and settings.vector_enabled and settings.review_mode == "llm",
                "notice": "Local development: explicit document checks, SQLite checkpoints, and lexical retrieval." if settings.storage_backend == "sqlite" else "Connected to configured MongoDB. Verify this is the hackathon-provided sandbox."}

    @app.get("/api/packages")
    def packages():
        filters = {"study_id": settings.demo_study_id} if settings.demo_study_id else None
        return [{k: v for k, v in p.items() if k != "documents"} | {"document_count": len(p["documents"])} for p in app.state.store.list("study_versions", filters)]

    @app.post("/api/packages", status_code=201)
    def upload(payload: PackageInput):
        return ingest_package(app.state.store, app.state.retriever, payload)

    @app.get("/api/packages/{package_id}")
    def get_package(package_id: str):
        return package_or_404(package_id)

    @app.post("/api/packages/{package_id}/search")
    def search_evidence(package_id: str, payload: SearchInput):
        return app.state.retriever.search(package_or_404(package_id), payload.query, payload.limit)

    @app.get("/api/demo/{version}")
    def get_demo(version: str):
        if version not in {"v1", "v2", "v3"}:
            raise HTTPException(404, "Sample version not found")
        return json.loads((ROOT / "demo" / f"{version}.json").read_text())

    @app.post("/api/demo/{version}/load", status_code=201)
    def load_demo(version: str, payload: DemoInput):
        data = get_demo(version)
        data["study_id"] = payload.study_id
        return ingest_package(app.state.store, app.state.retriever, PackageInput.model_validate(data))

    @app.get("/api/runs")
    def runs():
        filters = {"study_id": settings.demo_study_id} if settings.demo_study_id else None
        records = app.state.store.list("runs", filters)
        output = []
        for record in records[:100]:
            snap = app.state.engine.snapshot(record["id"])
            output.append({k: v for k, v in snap.items() if k != "state"} | {"metrics": snap["state"]["metrics"], "results": snap["state"]["results"]})
        return output

    @app.post("/api/runs", status_code=201)
    def new_run(payload: RunInput):
        return app.state.engine.create(package_or_404(payload.package_id), payload.force_full)

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        return run_or_404(run_id)

    @app.post("/api/runs/{run_id}/execute")
    def execute(run_id: str, payload: ExecuteInput):
        run_or_404(run_id)
        try:
            return app.state.engine.execute(run_id, payload.mode)
        except BusyRun:
            raise
        except Exception:
            log.exception("Review execution failed")
            raise HTTPException(500, "Execution interrupted. The last completed checkpoint is retained. Review the server log and resume.") from None

    @app.get("/api/runs/{run_id}/export")
    def export_run(run_id: str):
        result = run_or_404(run_id)
        return JSONResponse(result, headers={"Content-Disposition": f'attachment; filename="review-{result["id"][:8]}.json"'})

    @app.get("/api/packages/{package_id}/memory")
    def memories(package_id: str):
        package = package_or_404(package_id)
        active, stale = recall_memory(app.state.store, package)
        return {"active": active, "stale": stale}

    @app.post("/api/memory", status_code=201)
    def add_memory(payload: MemoryInput):
        package = package_or_404(payload.package_id)
        with app.state.store.lease("memory:" + package["study_id"]):
            return approve_memory(app.state.store, package, payload)

    @app.post("/api/memory/{memory_id}/revoke")
    def revoke(memory_id: str):
        memory = app.state.store.get("review_memory", memory_id)
        if not memory:
            raise HTTPException(404, "Memory not found")
        memory.update(status="revoked", revoked_at=now())
        return app.state.store.put("review_memory", memory)

    @app.get("/")
    def home():
        return FileResponse(ROOT / "static" / "index.html")

    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    return app


app = create_app()
