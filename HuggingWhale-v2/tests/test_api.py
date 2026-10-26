from fastapi.testclient import TestClient

from whale_core.api import create_app


ADMIN = {"Authorization": "Bearer admin-token-for-tests-only"}
READER = {"Authorization": "Bearer reader-token-for-tests-only"}


def test_authentication_and_admin_boundaries(service):
    with TestClient(create_app(service)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/documents").status_code == 401
        assert client.post("/search", json={"question": "test"}).status_code == 401
        assert client.delete("/documents/id", headers=READER).status_code == 403
        assert client.get("/jobs/id", headers=READER).status_code == 403
        assert client.get("/identity", headers=READER).json()["tenant"] == "other"


def test_upload_worker_search_source_and_feedback(service):
    with TestClient(create_app(service)) as client:
        result = client.post("/documents", headers=ADMIN, data={"document_id": "handbook"},
                             files={"file": ("handbook.md", b"Chicago support hours")})
        assert result.status_code == 202
        job_id = result.json()["job_id"]
        service.work_one()
        assert client.get("/jobs/" + job_id, headers=ADMIN).json()["state"] == "succeeded"
        response = client.post("/search", headers=ADMIN, json={"question": "hours", "answer": True})
        assert response.status_code == 200
        assert response.json()["sources"][0]["filename"] == "handbook.md"
        assert client.get("/documents/handbook/source", headers=ADMIN).content == b"Chicago support hours"
        assert client.get("/documents/handbook/source", headers=READER).status_code == 404
        trace = response.json()["trace_id"]
        assert client.post("/feedback/" + trace, headers=READER, json={"helpful": True}).status_code == 404
        assert client.post("/feedback/" + trace, headers=ADMIN, json={"helpful": True}).status_code == 200


def test_api_validation_and_safe_dependency_failure(service):
    with TestClient(create_app(service)) as client:
        assert client.post("/search", headers=ADMIN, json={"question": "x", "top_k": 100}).status_code == 422
        assert client.post("/search", headers=ADMIN, json={"question": "   "}).status_code == 400
        def fail(*args):
            raise RuntimeError("mongodb://SECRET")
        service.voyage.query = fail
        result = client.post("/search", headers=ADMIN, json={"question": "x"})
        assert result.status_code == 503
        assert "SECRET" not in result.text
