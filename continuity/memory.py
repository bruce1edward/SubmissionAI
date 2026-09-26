from uuid import uuid4
from .storage import now


def approve_memory(store, package, payload):
    documents = {doc["id"]: doc for doc in package["documents"]}
    source = documents.get(payload.document_id)
    if not source or payload.quote not in source["text"]:
        raise ValueError("The quoted evidence must occur verbatim in the selected document")
    if payload.kind == "document_alias":
        if payload.alias in documents:
            raise ValueError("An alias cannot replace an existing document ID")
        if source["kind"] != "supporting":
            raise ValueError("Only supporting documents may supply a filename alias")
        existing, _ = recall_memory(store, package)
        if any(m["kind"] == "document_alias" and m["alias"] == payload.alias for m in existing):
            raise ValueError("An active alias already exists; revoke it before replacing it")
    record = {
        **payload.model_dump(), "id": uuid4().hex,
        "study_id": package["study_id"], "source_hash": source["hash"],
        "status": "approved", "created_at": now(),
    }
    return store.put("review_memory", record)


def recall_memory(store, package):
    hashes = {d["id"]: d["hash"] for d in package["documents"]}
    active, stale = [], []
    for item in store.list("review_memory", {"study_id": package["study_id"], "status": "approved"}):
        valid = hashes.get(item["document_id"]) == item["source_hash"]
        (active if valid else stale).append(item)
    return active, stale
