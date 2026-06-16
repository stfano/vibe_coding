import hashlib
import math
import os
import re

from fastapi import FastAPI
from pydantic import BaseModel


TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]+")


class HealthResponse(BaseModel):
    status: str
    service: str
    embedding_model: str
    reranker_model: str


class EmbedRequest(BaseModel):
    texts: list[str]
    model: str | None = None
    dimensions: int | None = None


class EmbedResponse(BaseModel):
    model: str
    dimensions: int
    embeddings: list[list[float]]


app = FastAPI(title="Doctor Chat Embedding Service")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="doctor-chat-embedding-service",
        embedding_model=os.environ.get("EMBEDDING_MODEL", "not-configured"),
        reranker_model=os.environ.get("RERANKER_MODEL", "not-configured"),
    )


@app.post("/embed", response_model=EmbedResponse)
def embed(request: EmbedRequest) -> EmbedResponse:
    model = request.model or os.environ.get("EMBEDDING_MODEL", "deterministic-token-hash")
    dimensions = request.dimensions or int(os.environ.get("VECTOR_DIMENSIONS", "1024"))
    return EmbedResponse(
        model=model,
        dimensions=dimensions,
        embeddings=[_embed_text(text, dimensions=dimensions) for text in request.texts],
    )


def _embed_text(text: str, *, dimensions: int) -> list[float]:
    vector = [0.0 for _ in range(dimensions)]
    for token in TOKEN_PATTERN.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        vector[int(digest[:12], 16) % dimensions] += 1.0
    length = math.sqrt(sum(value * value for value in vector))
    if length == 0:
        return vector
    return [round(value / length, 8) for value in vector]
