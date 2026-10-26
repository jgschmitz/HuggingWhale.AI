from datetime import timedelta

import pytest

from whale_core.config import Identity
from whale_core.service import fuse, now
from whale_core.storage import scoped_id


def ingest(svc, who, data=b"Chicago support hours", **kwargs):
    job = svc.submit(who, "handbook", "handbook.md", data, kwargs.get("allowed", ["tenant"]))
    assert svc.work_one()
    return job


def test_ingestion_dedup_and_source_version(service, identity):
    job = ingest(service, identity)
    assert service.atlas.jobs.find_one({"_id": job["job_id"]})["state"] == "succeeded"
    assert service.objects.client.calls[0]["VersionId"] == "v1"
    same = service.submit(identity, "handbook", "handbook.md", b"Chicago support hours", ["tenant"])
    assert same["status"] == "unchanged"
    assert service.voyage.document_calls == 1
    assert service.atlas.chunks.count_documents({}) == 1


def test_new_revision_only_and_tenant_scope(service, identity):
    ingest(service, identity)
    old = list(service.atlas.chunks.find())
    ingest(service, identity, b"New hours")
    service.atlas.chunks.insert_many(old)  # Simulate stale search index hits.
    result = service.search(identity, "hours", answer=True)
    assert [h["text"] for h in result["sources"]] == ["New hours"]
    assert service.search(Identity("other", "jeffery"), "hours")["sources"] == []
    assert service.search(Identity("demo", "someone"), "hours")["sources"]


def test_acl_revocation_before_external_reranking(service, identity):
    ingest(service, identity)
    key = scoped_id("demo", "handbook")
    service.atlas.documents.update_one({"_id": key}, {"$set": {"allowed_principals": ["private-reader"]}})
    response = service.search(identity, "hours", answer=True)
    assert response["sources"] == []
    assert service.voyage.rerank_calls[-1] == []
    assert not service.generator.calls


def test_delete_stale_index_and_inflight_worker(service, identity):
    service.submit(identity, "handbook", "handbook.md", b"Old hours", ["tenant"])
    service.voyage.hook = lambda: service.delete(identity, "handbook")
    assert service.work_one()
    assert service.atlas.jobs.find_one()["state"] == "superseded"
    assert service.atlas.chunks.count_documents({}) == 0
    assert service.search(identity, "hours")["sources"] == []
    assert service.objects.client.objects  # Retention is a separate S3 policy.


def test_new_request_supersedes_older_queued_job(service, identity):
    first = service.submit(identity, "handbook", "handbook.md", b"Old", ["tenant"])
    second = service.submit(identity, "handbook", "handbook.md", b"New", ["tenant"])
    service.work_one()
    service.work_one()
    assert service.atlas.jobs.find_one({"_id": first["job_id"]})["state"] == "superseded"
    assert service.atlas.jobs.find_one({"_id": second["job_id"]})["state"] == "succeeded"
    assert service.search(identity, "hours")["sources"][0]["text"] == "New"


def test_revert_to_active_content_cancels_pending_version(service, identity):
    ingest(service, identity, b"A")
    service.submit(identity, "handbook", "handbook.md", b"B", ["tenant"])
    revert = service.submit(identity, "handbook", "handbook.md", b"A", ["tenant"])
    assert revert["status"] == "queued"
    while service.work_one():
        pass
    assert service.search(identity, "hours")["sources"][0]["text"] == "A"


def test_retry_does_not_destroy_current_revision(service, identity):
    ingest(service, identity, b"A")
    job = service.submit(identity, "handbook", "handbook.md", b"B", ["tenant"])
    def fail():
        raise RuntimeError("temporary provider error")
    service.voyage.hook = fail
    service.work_one()
    assert service.atlas.jobs.find_one({"_id": job["job_id"]})["state"] == "queued"
    assert service.search(identity, "hours")["sources"][0]["text"] == "A"
    service.voyage.hook = None
    service.atlas.jobs.update_one({"_id": job["job_id"]}, {"$set": {"available_at": now()}})
    service.work_one()
    assert service.search(identity, "hours")["sources"][0]["text"] == "B"


def test_exhausted_worker_lease_is_not_stuck_running(service, identity):
    job = service.submit(identity, "handbook", "handbook.md", b"A", ["tenant"])
    service.atlas.jobs.update_one({"_id": job["job_id"]}, {"$set": {
        "state": "running", "attempts": 3, "lease_until": now() - timedelta(seconds=1)}})
    assert not service.work_one()
    assert service.atlas.jobs.find_one()["state"] == "failed"


def test_revocation_during_generation_discards_answer(service, identity):
    ingest(service, identity)
    service.generator.hook = lambda: service.delete(identity, "handbook")
    result = service.search(identity, "hours", answer=True)
    assert result["sources"] == []
    assert "Sources changed" in result["answer"]


def test_telemetry_does_not_save_question_or_source_text(service, identity):
    ingest(service, identity)
    service.search(identity, "sensitive question", answer=True)
    event = service.atlas.events.find_one()
    assert "sensitive" not in str(event)
    assert "Chicago" not in str(event)
    assert event["usage"]["llm"]["total_tokens"] == 20


def test_fusion_deduplicates_and_combines_rankings():
    a, b = {"_id": "a"}, {"_id": "b"}
    results = fuse([a, b], [b])
    assert [x["_id"] for x in results] == ["b", "a"]


def test_non_admin_cannot_ingest_or_delete(service):
    who = Identity("demo", "reader")
    with pytest.raises(PermissionError):
        service.submit(who, "id", "x.txt", b"hi", ["tenant"])
    with pytest.raises(PermissionError):
        service.delete(who, "id")


def test_worker_reclaims_expired_lease(service, identity):
    job = service.submit(identity, "handbook", "handbook.md", b"A", ["tenant"])
    service.atlas.jobs.update_one({"_id": job["job_id"]}, {"$set": {
        "state": "running", "attempts": 1, "owner": "dead-worker",
        "lease_until": now() - timedelta(seconds=1)}})
    assert service.work_one()
    result = service.atlas.jobs.find_one()
    assert result["state"] == "succeeded"
    assert result["attempts"] == 2


def test_corrupt_source_never_replaces_active_content(service, identity):
    ingest(service, identity, b"A")
    job = service.submit(identity, "handbook", "handbook.md", b"B", ["tenant"])
    row = service.atlas.jobs.find_one({"_id": job["job_id"]})
    service.objects.client.objects[row["source"]["key"]] = b"tampered"
    service.work_one()
    assert service.atlas.jobs.find_one({"_id": job["job_id"]})["state"] == "failed"
    assert service.search(identity, "hours")["sources"][0]["text"] == "A"
