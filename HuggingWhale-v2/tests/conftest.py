from io import BytesIO

import mongomock
import pytest

from whale_core.config import Identity, Settings
from whale_core.service import Knowledge
from whale_core.storage import Atlas, Objects


class S3:
    def __init__(self):
        self.objects = {}
        self.calls = []

    def put_object(self, **kwargs):
        self.objects[kwargs["Key"]] = kwargs["Body"]
        return {"ETag": '"hash"', "VersionId": "v1"}

    def get_object(self, **kwargs):
        self.calls.append(kwargs)
        return {"Body": BytesIO(self.objects[kwargs["Key"]])}


class Voyage:
    def __init__(self):
        self.document_calls = 0
        self.rerank_calls = []
        self.hook = None

    def document(self, text):
        self.document_calls += 1
        if self.hook:
            self.hook()
        return [{"text": text, "embedding": [1.0] * 256}], {"total_tokens": 10}

    def query(self, text):
        return [1.0] * 256, {"total_tokens": 2}

    def rerank(self, query, hits, top_k):
        self.rerank_calls.append(hits)
        return [{**h, "rerank_score": 0.9} for h in hits[:top_k]], {"total_tokens": 12}


class Generator:
    def __init__(self):
        self.calls = []
        self.hook = None

    def answer(self, question, hits):
        self.calls.append(hits)
        if self.hook:
            self.hook()
        return "Answer [1]", {"total_tokens": 20}


@pytest.fixture
def identity():
    return Identity("demo", "jeffery", True)


@pytest.fixture
def service():
    cfg = Settings(mongo_uri="mongodb://localhost", s3_bucket="test", voyage_api_key="test",
                   dimensions=256, api_tokens=[
                       {"token": "admin-token-for-tests-only", "tenant": "demo", "principal": "jeffery", "admin": True},
                       {"token": "reader-token-for-tests-only", "tenant": "other", "principal": "reader"}])
    atlas = Atlas(cfg, mongomock.MongoClient().test)
    atlas.setup()
    # Mongomock does not implement Atlas Search. Return raw candidates deliberately;
    # tests exercise the live manifest authorization even if an index is stale.
    atlas.candidates = lambda *args, **kwargs: (list(atlas.chunks.find()), list(atlas.chunks.find()))
    return Knowledge(cfg, atlas, Objects(cfg, S3()), Voyage(), Generator())
