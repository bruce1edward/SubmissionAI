import re
import httpx

from pymongo.operations import SearchIndexModel
from .storage import digest, now


class RetrievalError(Exception):
    pass


class Retriever:
    def __init__(self, store, settings):
        self.store, self.settings = store, settings

    def embed(self, texts, input_type):
        try:
            response = httpx.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.settings.voyage_api_key}"},
                json={"model": self.settings.voyage_model, "input": texts, "input_type": input_type,
                      "output_dimension": self.settings.voyage_dimensions}, timeout=40,
            )
            response.raise_for_status()
            data = sorted(response.json()["data"], key=lambda d: d["index"])
            vectors = [d["embedding"] for d in data]
            if len(vectors) != len(texts) or any(len(v) != self.settings.voyage_dimensions for v in vectors):
                raise ValueError("Embedding shape mismatch")
            return vectors
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise RetrievalError("Embedding request failed; check credentials, model, and dimensions") from exc

    def index_package(self, package):
        chunks = []
        for doc in package["documents"]:
            # Overlapping bounded passages; offsets always point into the original text.
            for start in range(0, len(doc["text"]), 1200):
                text = doc["text"][start:start + 1600]
                chunks.append({
                    "id": digest([package["id"], doc["id"], start]), "package_id": package["id"],
                    "study_id": package["study_id"], "document_id": doc["id"], "kind": doc["kind"],
                    "source_hash": doc["hash"], "start": start, "end": start + len(text),
                    "text": text, "created_at": package["created_at"],
                })
        if self.settings.vector_enabled:
            for i in range(0, len(chunks), 64):
                batch = chunks[i:i + 64]
                for chunk, vector in zip(batch, self.embed([c["text"] for c in batch], "document")):
                    chunk.update(embedding=vector, embedding_model=self.settings.voyage_model)
        for chunk in chunks:
            self.store.put("evidence_chunks", chunk)

    def search(self, package, query, limit=6):
        filters = {"study_id": package["study_id"], "package_id": package["id"]}
        if self.settings.vector_enabled:
            filters["embedding_model"] = self.settings.voyage_model
            vector = self.embed([query], "query")[0]
            try:
                records = list(self.store.db.evidence_chunks.aggregate([
                    {"$vectorSearch": {"index": self.settings.vector_index, "path": "embedding",
                                       "queryVector": vector, "numCandidates": max(limit * 20, 100),
                                       "limit": limit, "filter": filters}},
                    {"$project": {"_id": 0, "embedding": 0}},
                ]))
            except Exception as exc:
                raise RetrievalError("Atlas Vector Search failed; verify the configured index is READY") from exc
            if not records:
                raise RetrievalError("Atlas returned no evidence; the index may still be building or ingesting")
            mode = "atlas_vector"
        else:
            records = self.store.list("evidence_chunks", filters)
            terms = set(re.findall(r"[a-z0-9]+", query.lower()))
            records.sort(key=lambda row: len(terms & set(re.findall(r"[a-z0-9]+", row["text"].lower()))), reverse=True)
            records = records[:limit]
            mode = "lexical_local"
        return {"mode": mode, "query": query, "passages": records}

    def create_vector_index(self):
        if self.store.backend != "mongodb":
            raise ValueError("Atlas index creation requires STORAGE_BACKEND=mongodb")
        definition = {"fields": [
            {"type": "vector", "path": "embedding", "numDimensions": self.settings.voyage_dimensions, "similarity": "cosine"},
            *[{"type": "filter", "path": path} for path in ("study_id", "package_id", "embedding_model")],
        ]}
        indexes = list(self.store.db.evidence_chunks.list_search_indexes())
        existing = next((i for i in indexes if i["name"] == self.settings.vector_index), None)
        if existing:
            current_definition = existing.get("latestDefinition", existing.get("definition"))
            if current_definition and current_definition != definition:
                raise ValueError("The existing vector index has a different definition. Use a new MONGODB_VECTOR_INDEX name and reindex with the configured embedding model.")
            return {"name": existing["name"], "status": existing.get("status"), "created": False}
        name = self.store.db.evidence_chunks.create_search_index(SearchIndexModel(name=self.settings.vector_index, definition=definition, type="vectorSearch"))
        return {"name": name, "status": "BUILDING", "created": True}
