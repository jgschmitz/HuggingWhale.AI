import httpx
import pytest

from whale_core.providers import Generator, ProviderError, Voyage


def test_context4_auto_chunking_rest_contract(service):
    requests = []
    def handler(req):
        import json
        body = json.loads(req.content)
        requests.append(body)
        chunk = {"embedding": [0.5] * 256, "index": 0}
        if body["input_type"] == "document":
            assert body["enable_auto_chunking"] is True
            assert body["inputs"] == ["complete document"]
            chunk["text"] = "backend chunk"
        else:
            assert body["inputs"] == [["question"]]
            assert "enable_auto_chunking" not in body
        return httpx.Response(200, json={"data": [{"index": 0, "data": [chunk]}]})
    vo = Voyage(service.cfg, httpx.Client(transport=httpx.MockTransport(handler)))
    rows, _ = vo.document("complete document")
    vec, _ = vo.query("question")
    assert rows[0]["text"] == "backend chunk"
    assert len(vec) == 256
    assert all(r["model"] == "voyage-context-4" for r in requests)


def test_missing_chunk_text_fails_without_fabricating_chunks(service):
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={
        "data": [{"index": 0, "data": [{"index": 0, "embedding": [0.5] * 256}]}]})))
    with pytest.raises(ProviderError, match="missing chunk text"):
        Voyage(service.cfg, client).document("document")


def test_provider_errors_redact_sensitive_response(service):
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(401, text="secret-key")))
    with pytest.raises(ProviderError) as err:
        Voyage(service.cfg, client).query("question")
    assert "secret-key" not in str(err.value)


def test_rerank_preserves_source_mapping(service):
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={
        "data": [{"index": 1, "relevance_score": .9}, {"index": 0, "relevance_score": .2}]})))
    hits, _ = Voyage(service.cfg, client).rerank("question", [{"text": "A"}, {"text": "B"}], 2)
    assert [h["text"] for h in hits] == ["B", "A"]


def test_llm_is_optional_and_cites_numbered_sources(service):
    with pytest.raises(ValueError, match="Configure"):
        Generator(service.cfg).answer("question", [])
    service.cfg.llm_api_key = "test"
    service.cfg.llm_model = "user-selected-model"
    def handler(req):
        import json
        body = json.loads(req.content)
        assert "[1] handbook.md" in body["messages"][1]["content"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "Answer [1]"}}]})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    answer, _ = Generator(service.cfg, client).answer("question", [{"filename": "handbook.md", "text": "A"}])
    assert answer == "Answer [1]"
