"""S3 canonical blobs and Atlas indexed representations are separate layers."""
from hashlib import sha256

import boto3
from botocore.config import Config
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel


def scoped_id(tenant, document_id):
    return sha256((tenant + "\0" + document_id).encode()).hexdigest()


class Objects:
    def __init__(self, cfg, client=None):
        self.cfg = cfg
        self.client = client or boto3.client("s3", region_name=cfg.s3_region,
                                            config=Config(retries={"max_attempts": 3},
                                                          connect_timeout=10, read_timeout=60))

    def put(self, tenant, doc_id, digest, data):
        # Content-addressed keys avoid overwriting a previous source revision.
        key = f"huggingwhale/{scoped_id(tenant, doc_id)}/{digest}/source"
        result = self.client.put_object(Bucket=self.cfg.s3_bucket, Key=key, Body=data,
                                        ContentType="application/octet-stream")
        return {"key": key, "version_id": result.get("VersionId"), "etag": result.get("ETag")}

    def get(self, source):
        args = dict(Bucket=self.cfg.s3_bucket, Key=source["key"])
        if source.get("version_id"):
            args["VersionId"] = source["version_id"]
        elif source.get("etag"):
            args["IfMatch"] = source["etag"]
        response = self.client.get_object(**args)
        body = response["Body"]
        try:
            data = body.read(self.cfg.max_upload_bytes + 1)
        finally:
            body.close()
        if len(data) > self.cfg.max_upload_bytes:
            raise ValueError("Source object exceeds upload limit")
        return data

    def put_text(self, source, pipeline, text):
        key = source["key"].removesuffix("source") + f"text/{pipeline}.txt"
        result = self.client.put_object(Bucket=self.cfg.s3_bucket, Key=key, Body=text.encode("utf-8"),
                                        ContentType="text/plain; charset=utf-8")
        return {"key": key, "version_id": result.get("VersionId"), "etag": result.get("ETag")}


class Atlas:
    def __init__(self, cfg, database=None):
        self.cfg = cfg
        self.client = None
        if database is None:
            self.client = MongoClient(cfg.mongo_uri, serverSelectionTimeoutMS=5000,
                                      connectTimeoutMS=5000, socketTimeoutMS=30000)
            database = self.client[cfg.database]
        self.db = database
        self.documents = database.documents
        self.chunks = database.chunks
        self.jobs = database.jobs
        self.events = database.events

    def setup(self):
        self.documents.create_index([("tenant", 1), ("document_id", 1)], unique=True)
        self.chunks.create_index([("tenant", 1), ("doc_key", 1), ("revision", 1)])
        self.jobs.create_index([("state", 1), ("available_at", 1), ("lease_until", 1)])
        self.events.create_index("created_at", expireAfterSeconds=30 * 86400)
        self.events.create_index([("tenant", 1), ("created_at", -1)])

    def search_definitions(self):
        return {
            "hw_vector": {"type": "vectorSearch", "definition": {"fields": [
                {"type": "vector", "path": "embedding", "numDimensions": self.cfg.dimensions,
                 "similarity": "cosine"},
                {"type": "filter", "path": "tenant"},
                {"type": "filter", "path": "allowed_principals"},
                {"type": "filter", "path": "pipeline"},
            ]}},
            "hw_keyword": {"type": "search", "definition": {"mappings": {"dynamic": False,
                "fields": {"text": {"type": "string"}, "tenant": {"type": "token"},
                           "allowed_principals": {"type": "token"}, "pipeline": {"type": "token"}}}}}
        }

    def ensure_search_indexes(self):
        existing = {i["name"]: i for i in self.chunks.list_search_indexes()}
        for name, spec in self.search_definitions().items():
            if name not in existing:
                self.chunks.create_search_index(SearchIndexModel(name=name, **spec))
            elif name == "hw_vector":
                definition = existing[name].get("latestDefinition", {})
                vectors = [f for f in definition.get("fields", []) if f.get("type") == "vector"]
                if vectors and vectors[0].get("numDimensions") != self.cfg.dimensions:
                    raise ValueError("Existing hw_vector dimensions differ; use a fresh database or rebuild that index")
        return list(self.chunks.list_search_indexes())

    def candidates(self, identity, query, vector, pipeline, limit=50):
        filters = {"tenant": identity.tenant, "allowed_principals": {"$in": identity.access},
                   "pipeline": pipeline}
        projection = {"embedding": 0}
        semantic = list(self.chunks.aggregate([
            {"$vectorSearch": {"index": "hw_vector", "path": "embedding", "queryVector": vector,
                               "filter": filters, "numCandidates": max(limit * 20, 100), "limit": limit}},
            {"$project": projection}], maxTimeMS=15000))
        lexical = list(self.chunks.aggregate([
            {"$search": {"index": "hw_keyword", "compound": {
                "must": [{"text": {"query": query, "path": "text"}}],
                "filter": [{"equals": {"path": "tenant", "value": identity.tenant}},
                           {"in": {"path": "allowed_principals", "value": identity.access}},
                           {"equals": {"path": "pipeline", "value": pipeline}}]}}},
            {"$limit": limit}, {"$project": projection}], maxTimeMS=15000))
        return semantic, lexical

    def authorize(self, identity, hits):
        """Recheck current manifests: search indexes can lag deletes and ACL changes."""
        if not hits:
            return []
        manifests = {v["_id"]: v for v in self.documents.find({
            "_id": {"$in": list({h["doc_key"] for h in hits})}, "tenant": identity.tenant,
            "deleted": False, "allowed_principals": {"$in": identity.access}})}
        return [h for h in hits if h.get("tenant") == identity.tenant
                and (m := manifests.get(h["doc_key"]))
                and h["revision"] == m.get("active_revision")]
