"""Versioned ingestion, durable jobs, hybrid retrieval, and grounded answers."""
import hashlib
import json
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pymongo import ReturnDocument

from whale_core.parsing import ALLOWED, extract
from whale_core.storage import scoped_id


def now():
    # Naive UTC matches PyMongo's default UTC BSON datetime decoding.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def fuse(*rankings, limit=50):
    """Reciprocal rank fusion: never compare vector and BM25 raw scores."""
    scores, records = {}, {}
    for ranking in rankings:
        seen = set()
        for rank, hit in enumerate(ranking, 1):
            key = hit["_id"]
            if key in seen:
                continue
            seen.add(key)
            scores[key] = scores.get(key, 0) + 1 / (60 + rank)
            records[key] = hit
    return [{**records[k], "fusion_score": scores[k]}
            for k in sorted(scores, key=lambda k: (-scores[k], str(k)))[:limit]]


class Knowledge:
    def __init__(self, cfg, atlas, objects, voyage, generator):
        self.cfg, self.atlas, self.objects = cfg, atlas, objects
        self.voyage, self.generator = voyage, generator
        # Changes to the embedding pipeline require re-ingestion, even with equal dimensions.
        self.pipeline = hashlib.sha256(json.dumps({
            "model": cfg.embedding_model, "dimensions": cfg.dimensions,
            "chunk_size": cfg.chunk_size, "overlap": 0, "parser": "v2.0"
        }, sort_keys=True).encode()).hexdigest()

    def submit(self, identity, document_id, filename, data, allowed):
        if not identity.admin:
            raise PermissionError("Admin token required")
        if not document_id.strip() or len(document_id) > 200 or "/" in document_id:
            raise ValueError("Document ID must be 1–200 characters without slashes")
        filename = Path(filename.replace("\\", "/")).name
        if Path(filename).suffix.lower() not in ALLOWED:
            raise ValueError("Unsupported document type")
        if not data or len(data) > self.cfg.max_upload_bytes:
            raise ValueError("Empty document or upload exceeds configured limit")
        allowed = sorted(set(p.strip() for p in allowed if p.strip()))
        if not allowed or len(allowed) > 100 or any(len(p) > 100 for p in allowed):
            raise ValueError("Provide 1–100 access principals; 'tenant' grants tenant-wide access")
        key = scoped_id(identity.tenant, document_id)
        digest = hashlib.sha256(data).hexdigest()
        fingerprint = hashlib.sha256(json.dumps([digest, filename, self.pipeline, allowed]).encode()).hexdigest()
        manifest = self.atlas.documents.find_one({"_id": key})
        if manifest and not manifest["deleted"]:
            if (manifest.get("fingerprint") == fingerprint
                    and manifest.get("pending_fingerprint") == fingerprint):
                return {"status": "unchanged", "document_id": document_id, "job_id": None}
            if manifest.get("pending_fingerprint") == fingerprint:
                job = self.atlas.jobs.find_one({"_id": manifest.get("requested_job"),
                                               "state": {"$in": ["queued", "running"]}})
                if job:
                    return {"status": job["state"], "document_id": document_id, "job_id": job["_id"]}
        source = self.objects.put(identity.tenant, document_id, digest, data)
        job_id = uuid.uuid4().hex
        self.atlas.documents.update_one({"_id": key}, {"$set": {
            "tenant": identity.tenant, "document_id": document_id, "deleted": False,
            "allowed_principals": allowed, "requested_job": job_id,
            "pending_fingerprint": fingerprint, "updated_at": now()
        }}, upsert=True)
        self.atlas.jobs.insert_one({
            "_id": job_id, "tenant": identity.tenant, "doc_key": key, "document_id": document_id,
            "filename": filename, "source": source, "content_hash": digest,
            "fingerprint": fingerprint, "pipeline": self.pipeline, "allowed_principals": allowed,
            "state": "queued", "attempts": 0, "available_at": now(), "lease_until": now(),
            "created_at": now()
        })
        return {"status": "queued", "document_id": document_id, "job_id": job_id}

    def work_one(self):
        owner = uuid.uuid4().hex
        job = self.atlas.jobs.find_one_and_update({
            "pipeline": self.pipeline, "attempts": {"$lt": self.cfg.max_attempts},
            "$or": [{"state": "queued", "available_at": {"$lte": now()}},
                     {"state": "running", "lease_until": {"$lte": now()}}]
        }, {"$set": {"state": "running", "owner": owner,
                     "lease_until": now() + timedelta(seconds=self.cfg.lease_seconds)},
            "$inc": {"attempts": 1}}, sort=[("created_at", 1)], return_document=ReturnDocument.AFTER)
        if not job:
            # A worker that died on its final attempt must not leave a job running forever.
            self.atlas.jobs.update_many({"state": "running", "lease_until": {"$lte": now()},
                                        "attempts": {"$gte": self.cfg.max_attempts}},
                                       {"$set": {"state": "failed", "error": "worker_lease_expired"}})
            return False
        revision = owner
        owned = {"_id": job["_id"], "state": "running", "owner": owner}
        stop, lost = threading.Event(), threading.Event()

        def heartbeat():
            while not stop.wait(max(1, self.cfg.lease_seconds // 3)):
                try:
                    result = self.atlas.jobs.update_one(owned, {"$set": {
                        "lease_until": now() + timedelta(seconds=self.cfg.lease_seconds)}})
                    if not result.matched_count:
                        lost.set()
                        return
                except Exception:
                    lost.set()
                    return

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        try:
            manifest_filter = {"_id": job["doc_key"], "requested_job": job["_id"], "deleted": False}
            if not self.atlas.documents.find_one(manifest_filter):
                self.atlas.jobs.update_one(owned, {"$set": {"state": "superseded"}})
                return True
            if job["pipeline"] != self.pipeline:
                raise ValueError("Worker configuration differs from queued ingestion")
            raw = self.objects.get(job["source"])
            if hashlib.sha256(raw).hexdigest() != job["content_hash"]:
                raise ValueError("Source checksum mismatch")
            text = extract(raw, job["filename"], self.cfg.max_document_chars)
            text_source = self.objects.put_text(job["source"], self.pipeline, text)
            rows, usage = self.voyage.document(text)
            chunks = [{"_id": f"{revision}:{i}", "tenant": job["tenant"], "doc_key": job["doc_key"],
                       "document_id": job["document_id"], "filename": job["filename"],
                       "revision": revision, "chunk_index": i, "text": row["text"],
                       "embedding": row["embedding"], "pipeline": self.pipeline,
                       "source": job["source"], "allowed_principals": job["allowed_principals"]}
                      for i, row in enumerate(rows)]
            if not chunks:
                raise ValueError("Provider returned no chunks")
            if lost.is_set():
                raise RuntimeError("Job lease lost")
            # Stage a unique attempt before switching the active manifest pointer.
            for offset in range(0, len(chunks), 100):
                self.atlas.chunks.insert_many(chunks[offset:offset + 100])
            if lost.is_set() or not self.atlas.jobs.find_one(owned):
                raise RuntimeError("Job lease lost")
            previous = self.atlas.documents.find_one_and_update(manifest_filter, {"$set": {
                "active_revision": revision, "fingerprint": job["fingerprint"],
                "active_source": job["source"], "filename": job["filename"],
                "active_text_source": text_source,
                "chunk_count": len(chunks), "pipeline": self.pipeline, "indexed_at": now()
            }}, return_document=ReturnDocument.BEFORE)
            state = "succeeded" if previous else "superseded"
            if previous and previous.get("active_revision"):
                self.atlas.chunks.delete_many({"revision": previous["active_revision"], "doc_key": job["doc_key"]})
            if state == "superseded":
                self.atlas.chunks.delete_many({"revision": revision})
            self.atlas.jobs.update_one(owned, {"$set": {"state": state, "finished_at": now(),
                                                       "chunk_count": len(chunks), "usage": usage}})
        except Exception as error:
            # Never remove a revision after it has become active, even if job bookkeeping failed.
            if not self.atlas.documents.find_one({"active_revision": revision}):
                self.atlas.chunks.delete_many({"revision": revision})
            retry = job["attempts"] < self.cfg.max_attempts and not isinstance(error, ValueError)
            self.atlas.jobs.update_one(owned, {"$set": {
                "state": "queued" if retry else "failed", "error": type(error).__name__,
                "available_at": now() + timedelta(seconds=2 ** job["attempts"])
            }})
        finally:
            stop.set()
            thread.join(timeout=1)
        return True

    def delete(self, identity, document_id):
        if not identity.admin:
            raise PermissionError("Admin token required")
        key = scoped_id(identity.tenant, document_id)
        result = self.atlas.documents.update_one({"_id": key, "tenant": identity.tenant},
            {"$set": {"deleted": True, "updated_at": now()},
             "$unset": {"active_revision": "", "requested_job": "", "fingerprint": ""}})
        if not result.matched_count:
            raise LookupError("Document not found")
        self.atlas.chunks.delete_many({"tenant": identity.tenant, "doc_key": key})
        return {"status": "deleted", "source_retained": True}

    def search(self, identity, question, top_k=6, rerank=True, answer=False):
        if not question.strip() or len(question) > 4000 or not 1 <= top_k <= 20:
            raise ValueError("Provide a question up to 4000 characters and top_k between 1 and 20")
        started = time.perf_counter()
        trace_id = uuid.uuid4().hex
        vector, query_usage = self.voyage.query(question)
        semantic, lexical = self.atlas.candidates(identity, question, vector, self.pipeline)
        hits = self.atlas.authorize(identity, fuse(semantic, lexical))
        rerank_usage, llm_usage = {}, {}
        if rerank:
            hits, rerank_usage = self.voyage.rerank(question, hits, top_k)
        else:
            hits = hits[:top_k]
        # Recheck after external reranking as well as before sending candidate text.
        hits = self.atlas.authorize(identity, hits)
        response = None
        if answer:
            if hits:
                response, llm_usage = self.generator.answer(question, hits)
            else:
                response = "No accessible indexed sources matched. I cannot answer from the available evidence."
        current = self.atlas.authorize(identity, hits)
        if len(current) != len(hits):
            response = "Sources changed during this request. Please search again." if answer else None
            hits = []
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        usage = {"embedding": query_usage, "rerank": rerank_usage, "llm": llm_usage}
        event = {"_id": trace_id, "tenant": identity.tenant, "principal": identity.principal,
                 "created_at": now(), "latency_ms": elapsed, "hit_count": len(hits),
                 "usage": usage, "pipeline": self.pipeline}
        self.atlas.events.insert_one(event)
        public = [{"citation": i, **{k: h[k] for k in (
            "document_id", "filename", "chunk_index", "text", "fusion_score")},
                   "rerank_score": h.get("rerank_score")}
                  for i, h in enumerate(hits, 1)]
        return {"trace_id": trace_id, "latency_ms": elapsed, "sources": public,
                "answer": response, "usage": usage}

