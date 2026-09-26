from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from app import create_app
from continuity.config import Settings
from continuity.retrieval import Retriever, RetrievalError
from continuity.workflow import fingerprint
from conftest import ingest


def embedding_settings(**kwargs):
    return Settings(storage_backend="mongodb", mongodb_uri="mongodb://example.invalid",
                    vector_enabled=True, embedding_provider="nebius", nebius_api_key="test-secret",
                    embedding_dimensions=3, **kwargs)


def mock_embeddings(monkeypatch, data):
    post = Mock(return_value=httpx.Response(200, json={"data": data},
                                           request=httpx.Request("POST", "https://example.invalid")))
    monkeypatch.setattr("continuity.retrieval.httpx.post", post)
    return post


def test_nebius_embedding_order_and_query_instruction(monkeypatch):
    post = mock_embeddings(monkeypatch, [{"index": 1, "embedding": [0, 1, 0]}, {"index": 0, "embedding": [1, 0, 0]}])
    retriever = Retriever(None, embedding_settings())
    assert retriever.embed(["one", "two"], "document") == [[1, 0, 0], [0, 1, 0]]
    assert post.call_args.kwargs["json"]["input"] == ["one", "two"]
    assert post.call_args.args[0] == "https://api.tokenfactory.nebius.com/v1/embeddings"
    mock_embeddings(monkeypatch, [{"index": 0, "embedding": [1, 0, 0]}])
    retriever.embed(["timing"], "query")
    # Documents remain unchanged; only Qwen retrieval queries receive instructions.
    from continuity.retrieval import httpx as client
    assert client.post.call_args.kwargs["json"]["input"][0].endswith("\nQuery: timing")


@pytest.mark.parametrize("data", [
    [], [{"index": 1, "embedding": [1, 0, 0]}],
    [{"index": 0, "embedding": [1, 0]}], [{"index": 0, "embedding": [0, 0, 0]}],
    [{"index": 0, "embedding": [1, "secret", 0]}],
    [{"index": 0, "embedding": [True, 1, 0]}],
    [{"index": 0, "embedding": [1, 0, 0]}, {"index": 0, "embedding": [1, 0, 0]}],
    None,
])
def test_invalid_embeddings_fail_closed(monkeypatch, data):
    mock_embeddings(monkeypatch, data)
    with pytest.raises(RetrievalError, match="Embedding request failed"):
        Retriever(None, embedding_settings()).embed(["document"], "document")


def test_nonfinite_embedding_rejected(monkeypatch):
    response = Mock()
    response.json.return_value = {"data": [{"index": 0, "embedding": [1, float("nan"), 0]}]}
    monkeypatch.setattr("continuity.retrieval.httpx.post", lambda *a, **k: response)
    with pytest.raises(RetrievalError):
        Retriever(None, embedding_settings()).embed(["document"], "document")


def test_voyage_legacy_settings_still_work(monkeypatch):
    post = mock_embeddings(monkeypatch, [{"index": 0, "embedding": [1, 0, 0]}])
    retriever = Retriever(None, Settings(voyage_api_key="voyage-test", voyage_dimensions=3))
    retriever.embed(["query"], "query")
    assert post.call_args.kwargs["json"] == {"model": "voyage-3.5-lite", "input": ["query"], "input_type": "query", "output_dimension": 3}


def test_vector_filter_and_no_lexical_fallback(monkeypatch):
    collection = Mock()
    collection.aggregate.return_value = [{"text": "source", "score": 0.9, "embedding": [1, 0, 0]}]
    settings = embedding_settings()
    retriever = Retriever(SimpleNamespace(db=SimpleNamespace(evidence_chunks=collection)), settings)
    monkeypatch.setattr(retriever, "embed", lambda *a: [[1, 0, 0]])
    package = {"study_id": "study-a", "id": "version-1"}
    result = retriever.search(package, "timing", limit=2)
    vector_query = collection.aggregate.call_args.args[0][0]["$vectorSearch"]
    assert vector_query["filter"] == {"study_id": "study-a", "package_id": "version-1", "embedding_profile": settings.embedding_profile}
    assert result["passages"] == [{"text": "source", "score": 0.9}]
    collection.aggregate.return_value = []
    with pytest.raises(RetrievalError, match="no evidence"):
        retriever.search(package, "timing")
    collection.aggregate.side_effect = RuntimeError("private provider details")
    with pytest.raises(RetrievalError, match="Atlas Vector Search failed"):
        retriever.search(package, "timing")


def test_embedding_profile_invalidates_review_cache(system):
    package = ingest(system)
    settings = embedding_settings()
    original = fingerprint("endpoint_alignment", package, [], settings)
    for change in [dict(embedding_dimensions=4), dict(embedding_provider="voyage"),
                   dict(embedding_model="another-model"), dict(vector_index="another-index")]:
        assert original != fingerprint("endpoint_alignment", package, [], replace(settings, **change))


def test_conflicting_existing_index_is_not_changed():
    collection = Mock()
    collection.list_search_indexes.return_value = [{"name": "evidence_vector", "latestDefinition": {"fields": []}}]
    store = SimpleNamespace(backend="mongodb", db=SimpleNamespace(evidence_chunks=collection))
    with pytest.raises(ValueError, match="different definition"):
        Retriever(store, embedding_settings()).create_vector_index()
    collection.create_search_index.assert_not_called()


def test_search_api_scopes_results_and_validates_queries(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        first = client.post("/api/demo/v1/load", json={"study_id": "FIRST"}).json()
        client.post("/api/demo/v2/load", json={"study_id": "FIRST"})
        client.post("/api/demo/v1/load", json={"study_id": "OTHER"})
        url = f"/api/packages/{first['id']}/search"
        response = client.post(url, json={"query": "endpoint", "limit": 2})
        assert response.status_code == 200
        assert len(response.json()["passages"]) == 2
        assert all(p["package_id"] == first["id"] and p["study_id"] == "FIRST" for p in response.json()["passages"])
        for invalid in [{"query": " "}, {"query": "x", "limit": 0}, {"query": "x" * 1201}]:
            assert client.post(url, json=invalid).status_code == 422
        assert client.post("/api/packages/missing/search", json={"query": "x"}).status_code == 404
