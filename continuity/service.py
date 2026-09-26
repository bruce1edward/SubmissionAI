from .schemas import PackageInput
from .storage import digest, now


def ingest_package(store, retriever, payload: PackageInput):
    data = payload.model_dump()
    package_id = digest(data)[:32]
    with store.lease("ingest:" + data["study_id"]):
        existing = store.get("study_versions", package_id)
        if existing:
            return existing
        if store.list("study_versions", {"study_id": data["study_id"], "version": data["version"]}):
            raise ValueError("That version label already exists with different content. Choose a new version label.")
        package = {**data, "id": package_id, "created_at": now()}
        for doc in package["documents"]:
            doc["hash"] = digest({"text": doc["text"], "kind": doc["kind"]})
        retriever.index_package(package)
        return store.put("study_versions", package)
