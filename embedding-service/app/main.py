import hashlib
import math
import os
import re
from functools import lru_cache
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field


TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]+")


class HealthResponse(BaseModel):
    status: str
    service: str
    embedding_model: str
    reranker_model: str
    embedding_backend: str
    reranker_backend: str


class EmbedRequest(BaseModel):
    texts: list[str]
    model: str | None = None
    dimensions: int | None = None


class EmbedResponse(BaseModel):
    provider: str
    model: str
    dimensions: int
    fallback_used: bool = False
    embeddings: list[list[float]]


class RerankDocument(BaseModel):
    id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RerankRequest(BaseModel):
    query: str
    documents: list[RerankDocument]
    model: str | None = None
    top_k: int | None = None


class RerankResult(BaseModel):
    id: str
    index: int
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class RerankResponse(BaseModel):
    provider: str
    model: str
    fallback_used: bool = False
    results: list[RerankResult]


app = FastAPI(title="Doctor Chat Embedding Service")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="doctor-chat-embedding-service",
        embedding_model=os.environ.get("EMBEDDING_MODEL", "not-configured"),
        reranker_model=os.environ.get("RERANKER_MODEL", "not-configured"),
        embedding_backend=os.environ.get("EMBEDDING_BACKEND", "sentence-transformers"),
        reranker_backend=os.environ.get("RERANKER_BACKEND", "deterministic"),
    )


@app.post("/embed", response_model=EmbedResponse)
def embed(request: EmbedRequest) -> EmbedResponse:
    model = request.model or os.environ.get("EMBEDDING_MODEL", "deterministic-token-hash")
    dimensions = request.dimensions or int(os.environ.get("VECTOR_DIMENSIONS", "1024"))
    backend = os.environ.get("EMBEDDING_BACKEND", "sentence-transformers")
    if backend == "sentence-transformers":
        try:
            return _embed_with_sentence_transformers(request.texts, model=model, dimensions=dimensions)
        except Exception:
            if not _fallback_enabled("EMBEDDING_SEMANTIC_FALLBACK"):
                raise

    return EmbedResponse(
        provider="deterministic",
        model=model,
        dimensions=dimensions,
        fallback_used=backend == "sentence-transformers",
        embeddings=[_embed_text(text, dimensions=dimensions) for text in request.texts],
    )


@app.post("/rerank", response_model=RerankResponse)
def rerank(request: RerankRequest) -> RerankResponse:
    model = request.model or os.environ.get("RERANKER_MODEL", "deterministic-token-overlap")
    backend = os.environ.get("RERANKER_BACKEND", "deterministic")
    if backend == "sentence-transformers":
        try:
            return _rerank_with_cross_encoder(request, model=model)
        except Exception:
            if not _fallback_enabled("RERANKER_SEMANTIC_FALLBACK"):
                raise
    return _rerank_deterministic(request, model=model, fallback_used=backend == "sentence-transformers")


def _embed_with_sentence_transformers(texts: list[str], *, model: str, dimensions: int) -> EmbedResponse:
    sentence_model = _sentence_transformer(model)
    embeddings = sentence_model.encode(texts, normalize_embeddings=True)
    vectors = [_coerce_dimensions([float(value) for value in embedding], dimensions=dimensions) for embedding in embeddings]
    return EmbedResponse(
        provider="sentence-transformers",
        model=model,
        dimensions=dimensions,
        fallback_used=False,
        embeddings=vectors,
    )


@lru_cache(maxsize=2)
def _sentence_transformer(model: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model)


def _rerank_with_cross_encoder(request: RerankRequest, *, model: str) -> RerankResponse:
    cross_encoder = _cross_encoder(model)
    pairs = [(request.query, document.text) for document in request.documents]
    scores = [float(score) for score in cross_encoder.predict(pairs)]
    return _serialize_rerank_results(request, scores=scores, provider="sentence-transformers", model=model)


@lru_cache(maxsize=2)
def _cross_encoder(model: str):
    from sentence_transformers import CrossEncoder

    return CrossEncoder(model)


def _rerank_deterministic(request: RerankRequest, *, model: str, fallback_used: bool) -> RerankResponse:
    query_tokens = set(TOKEN_PATTERN.findall(request.query.lower()))
    scores = []
    for document in request.documents:
        document_tokens = set(TOKEN_PATTERN.findall(document.text.lower()))
        if not query_tokens or not document_tokens:
            scores.append(0.0)
            continue
        overlap = len(query_tokens & document_tokens)
        denominator = math.sqrt(len(query_tokens) * len(document_tokens))
        scores.append(round(overlap / denominator, 8) if denominator else 0.0)
    return _serialize_rerank_results(
        request,
        scores=scores,
        provider="deterministic",
        model=model,
        fallback_used=fallback_used,
    )


def _serialize_rerank_results(
    request: RerankRequest,
    *,
    scores: list[float],
    provider: str,
    model: str,
    fallback_used: bool = False,
) -> RerankResponse:
    ranked = sorted(
        [
            RerankResult(
                id=document.id,
                index=index,
                score=round(scores[index], 8),
                metadata=document.metadata,
            )
            for index, document in enumerate(request.documents)
        ],
        key=lambda item: item.score,
        reverse=True,
    )
    if request.top_k is not None:
        ranked = ranked[: max(0, request.top_k)]
    return RerankResponse(provider=provider, model=model, fallback_used=fallback_used, results=ranked)


def _embed_text(text: str, *, dimensions: int) -> list[float]:
    vector = [0.0 for _ in range(dimensions)]
    for token in TOKEN_PATTERN.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        vector[int(digest[:12], 16) % dimensions] += 1.0
    length = math.sqrt(sum(value * value for value in vector))
    if length == 0:
        return vector
    return [round(value / length, 8) for value in vector]


def _coerce_dimensions(values: list[float], *, dimensions: int) -> list[float]:
    if len(values) == dimensions:
        return [round(value, 8) for value in values]
    if len(values) > dimensions:
        return normalize_vector(values[:dimensions])
    return normalize_vector(values + [0.0 for _ in range(dimensions - len(values))])


def normalize_vector(values: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in values))
    if length == 0:
        return values
    return [round(value / length, 8) for value in values]


def _fallback_enabled(name: str) -> bool:
    return os.environ.get(name, "true").lower() in {"1", "true", "yes", "on"}
