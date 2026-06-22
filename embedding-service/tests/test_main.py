from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import EmbedRequest, RerankDocument, RerankRequest, embed, rerank


def test_embed_endpoint_returns_configured_dimensions_and_metadata(monkeypatch):
    monkeypatch.setenv("EMBEDDING_BACKEND", "deterministic")
    monkeypatch.setenv("EMBEDDING_MODEL", "test-semantic-model")

    response = embed(EmbedRequest(texts=["아기 고환 물집"], dimensions=12))

    body = response.model_dump()
    assert body["provider"] == "deterministic"
    assert body["model"] == "test-semantic-model"
    assert body["dimensions"] == 12
    assert len(body["embeddings"]) == 1
    assert len(body["embeddings"][0]) == 12


def test_rerank_endpoint_returns_contract_without_requiring_model(monkeypatch):
    monkeypatch.setenv("RERANKER_BACKEND", "deterministic")
    monkeypatch.setenv("RERANKER_MODEL", "test-reranker")

    response = rerank(
        RerankRequest(
            query="아기 고환 물집",
            documents=[
                RerankDocument(id="a", text="고환 물집 관련 문서"),
                RerankDocument(id="b", text="감기 관련 문서"),
            ],
        )
    )

    body = response.model_dump()
    assert body["provider"] == "deterministic"
    assert body["model"] == "test-reranker"
    assert [item["id"] for item in body["results"]] == ["a", "b"]
    assert body["results"][0]["score"] >= body["results"][1]["score"]
