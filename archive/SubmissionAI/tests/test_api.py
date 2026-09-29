from fastapi.testclient import TestClient
from app import create_app
from continuity.config import Settings
from conftest import fixture_package


def test_api_review_and_export(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        status = client.get("/api/status").json()
        assert status["live_services_configured"] is False
        assert status["review_mode"] == "deterministic"
        assert client.get("/").status_code == 200
        assert client.get("/static/app.js").status_code == 200
        package = client.post("/api/demo/v1/load", json={}).json()
        run = client.post("/api/runs", json={"package_id":package["id"]}).json()
        step = client.post(f"/api/runs/{run['id']}/execute", json={"mode":"step"}).json()
        assert step["status"] == "paused"
        final = client.post(f"/api/runs/{run['id']}/execute", json={"mode":"continue"}).json()
        assert final["status"] == "completed"
        assert client.get(f"/api/runs/{run['id']}/export").json()["state"]["results"] == final["state"]["results"]
        assert len(client.get("/api/runs").json()) == 1
        assert client.get("/api/packages/does-not-exist").status_code == 404
        assert client.get("/api/runs/does-not-exist").status_code == 404


def test_api_validates_duplicate_documents_and_cross_origin(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        payload = fixture_package()
        payload["documents"].append(payload["documents"][0])
        assert client.post("/api/packages", json=payload).status_code == 422
        assert client.post("/api/demo/v1/load", json={}, headers={"Origin":"https://unrelated.example"}).status_code == 403
        assert client.post("/api/demo/v1/load", json={"study_id":"../bad"}).status_code == 422


def test_app_token_and_no_secret_in_status(tmp_path):
    token = "not-a-real-secret"
    with TestClient(create_app(Settings(data_dir=tmp_path, access_token=token))) as client:
        assert client.get("/api/status").status_code == 401
        response = client.get("/api/status", headers={"Authorization":f"Bearer {token}"})
        assert response.status_code == 200
        assert token not in response.text


def test_memory_api_verifies_source_and_retains_revoke_history(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        p = client.post("/api/demo/v1/load", json={}).json()
        payload = {"package_id":p["id"],"document_id":"protocol.txt","quote":"Primary endpoint assessment: Week 8.","summary":"Use the primary assessment field, not the follow-up visit.","check_ids":["endpoint_alignment"]}
        note = client.post("/api/memory", json=payload)
        assert note.status_code == 201
        assert len(client.get(f"/api/packages/{p['id']}/memory").json()["active"]) == 1
        assert client.post(f"/api/memory/{note.json()['id']}/revoke").json()["status"] == "revoked"
        assert client.get(f"/api/packages/{p['id']}/memory").json()["active"] == []
