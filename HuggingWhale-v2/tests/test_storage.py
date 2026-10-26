from whale_core.config import Identity
from whale_core.storage import Atlas, Objects


def test_real_search_pipelines_scope_both_branches(service):
    calls = []
    class Collection:
        def aggregate(self, pipeline, **kwargs):
            calls.append(pipeline)
            return []
    atlas = Atlas(service.cfg, service.atlas.db)
    atlas.chunks = Collection()
    atlas.candidates(Identity("demo", "jeffery"), "support hours", [1.0] * 256, "pipeline")
    vector = calls[0][0]["$vectorSearch"]
    assert vector["filter"]["tenant"] == "demo"
    assert vector["filter"]["allowed_principals"] == {"$in": ["tenant", "jeffery"]}
    compound = calls[1][0]["$search"]["compound"]
    assert {"equals": {"path": "tenant", "value": "demo"}} in compound["filter"]
    assert {"equals": {"path": "pipeline", "value": "pipeline"}} in compound["filter"]
    assert calls[0][-1]["$project"]["embedding"] == 0


def test_search_index_fields_match_query_paths(service):
    defs = service.atlas.search_definitions()
    fields = defs["hw_vector"]["definition"]["fields"]
    assert fields[0]["numDimensions"] == service.cfg.dimensions
    assert {x["path"] for x in fields[1:]} == {"tenant", "allowed_principals", "pipeline"}
    mappings = defs["hw_keyword"]["definition"]["mappings"]
    assert mappings["dynamic"] is False
    assert mappings["fields"]["allowed_principals"]["type"] == "token"


def test_s3_fallback_read_uses_etag_precondition(service):
    class Client:
        def get_object(self, **kwargs):
            from io import BytesIO
            assert kwargs["IfMatch"] == '"etag"'
            assert "VersionId" not in kwargs
            return {"Body": BytesIO(b"text")}
    assert Objects(service.cfg, Client()).get({"key": "object", "etag": '"etag"'}) == b"text"
