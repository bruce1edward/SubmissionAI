import re
import math
import httpx

from pymongo.operations import SearchIndexModel
from .storage import digest


class RetrievalError(Exception):
    pass


class Retriever:
    def __init__(self, store, settings):
        self.store, self.settings = store, settings

    def embed(self, texts, input_type):
        if not texts:
            return []
        if input_type not in {"document", "query"}:
            raise ValueError("Embedding input type must be document or query")
        settings = self.settings
        model = settings.effective_embedding_model
        dimensions = settings.effective_embedding_dimensions
        if settings.embedding_provider == "nebius":
            url, key = "https://api.tokenfactory.nebius.com/v1/embeddings", settings.nebius_api_key
            if input_type == "query" and model.startswith("Qwen/Qwen3-Embedding"):
                texts = [f"Instruct: Retrieve source passages relevant to the document review question.\nQuery: {text}" for text in texts]
            payload = {"model": model, "input": texts, "encoding_format": "float"}
            # Use the model's native dimensions; reject an incompatible response below.
        else:
            url, key = "https://api.voyageai.com/v1/embeddings", settings.voyage_api_key
            payload = {"model": model, "input": texts, "input_type": input_type, "output_dimension": dimensions}
        try:
            response = httpx.post(
                url, headers={"Authorization": f"Bearer {key}"}, json=payload, timeout=40,
            )
            response.raise_for_status()
            data = sorted(response.json()["data"], key=lambda d: d["index"])
            vectors = [d["embedding"] for d in data]
            if [d["index"] for d in data] != list(range(len(texts))):
                raise ValueError("Embedding index mismatch")
            if any(not isinstance(v, list) or len(v) != dimensions or
                   any(type(n) not in (int, float) or not math.isfinite(n) for n in v) or
                   not any(n != 0 for n in v) for v in vectors):
                raise ValueError("Embedding shape mismatch")
            return vectors
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
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
                    chunk.update(embedding=vector, embedding_model=self.settings.effective_embedding_model,
                                 embedding_profile=self.settings.embedding_profile)
        for chunk in chunks:
            self.store.put("evidence_chunks", chunk)

    def search(self, package, query, limit=6):
        if not query.strip() or len(query) > 1200 or not 1 <= limit <= 12:
            raise ValueError("Search needs a nonempty query of at most 1200 characters and a limit from 1 to 12")
        filters = {"study_id": package["study_id"], "package_id": package["id"]}
        if self.settings.vector_enabled:
            filters["embedding_profile"] = self.settings.embedding_profile
            vector = self.embed([query], "query")[0]
            try:
                records = list(self.store.db.evidence_chunks.aggregate([
                    {"$vectorSearch": {"index": self.settings.vector_index, "path": "embedding",
                                       "queryVector": vector, "numCandidates": max(limit * 20, 100),
                                       "limit": limit, "filter": filters}},
                    {"$set": {"score": {"$meta": "vectorSearchScore"}}},
                    {"$project": {"_id": 0, "embedding": 0}},
                ], maxTimeMS=15000))
            except Exception as exc:
                raise RetrievalError("Atlas Vector Search failed; verify the configured index is READY") from exc
            if not records:
                raise RetrievalError("Atlas returned no evidence; wait for indexing, or run reindex for existing packages")
            mode = "atlas_vector"
        else:
            records = self.store.list("evidence_chunks", filters)
            terms = set(re.findall(r"[a-z0-9]+", query.lower()))
            records.sort(key=lambda row: len(terms & set(re.findall(r"[a-z0-9]+", row["text"].lower()))), reverse=True)
            records = records[:limit]
            mode = "lexical_local"
        # Never return stored vectors, including when lexical mode is selected later.
        records = [{k: v for k, v in row.items() if k not in {"embedding", "_id"}} for row in records]
        return {"mode": mode, "query": query, "passages": records}

    def create_vector_index(self):
        if self.store.backend != "mongodb":
            raise ValueError("Atlas index creation requires STORAGE_BACKEND=mongodb")
        definition = {"fields": [
            {"type": "vector", "path": "embedding", "numDimensions": self.settings.effective_embedding_dimensions, "similarity": "cosine"},
            *[{"type": "filter", "path": path} for path in ("study_id", "package_id", "embedding_profile")],
        ]}
        indexes = list(self.store.db.evidence_chunks.list_search_indexes())
        existing = next((i for i in indexes if i["name"] == self.settings.vector_index), None)
        if existing:
            current_definition = existing.get("latestDefinition", existing.get("definition"))
            if current_definition and current_definition != definition:
                raise ValueError("The existing vector index has a different definition. Use a new MONGODB_VECTOR_INDEX name and reindex with the configured embedding model.")
            return {"name": existing["name"], "status": existing.get("status"), "queryable": existing.get("queryable", False), "created": False}
        name = self.store.db.evidence_chunks.create_search_index(SearchIndexModel(name=self.settings.vector_index, definition=definition, type="vectorSearch"))
        return {"name": name, "status": "BUILDING", "queryable": False, "created": True}
