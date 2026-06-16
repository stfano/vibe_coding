from __future__ import annotations

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from typing import Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings


TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]+")


class EmbeddingError(RuntimeError):
    pass


class EmbeddingAdapter(Protocol):
    model_name: str
    dimensions: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, query: str) -> list[float]:
        ...


def build_embedding_payload(texts: list[str], *, model: str, dimensions: int) -> dict[str, object]:
    return {
        "texts": texts,
        "model": model,
        "dimensions": dimensions,
    }


def normalize_vector(values: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in values))
    if length == 0:
        return values
    return [round(value / length, 8) for value in values]


def vector_to_pgvector(values: list[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in values) + "]"


@dataclass
class DeterministicEmbeddingAdapter:
    dimensions: int
    model_name: str = "deterministic-token-hash"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0 for _ in range(self.dimensions)]
        for token in TOKEN_PATTERN.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            vector[int(digest[:12], 16) % self.dimensions] += 1.0
        return normalize_vector(vector)


@dataclass
class HttpEmbeddingAdapter:
    service_url: str
    model_name: str
    dimensions: int
    timeout: float = 15.0

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        payload = build_embedding_payload(texts, model=self.model_name, dimensions=self.dimensions)
        request = Request(
            self.service_url.rstrip("/") + "/embed",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, json.JSONDecodeError) as exc:
            raise EmbeddingError(f"embedding service request failed: {exc}") from exc

        embeddings = body.get("embeddings")
        if not isinstance(embeddings, list):
            raise EmbeddingError("embedding service response missing embeddings")
        return embeddings

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]


def get_embedding_adapter(
    *,
    provider: str | None = None,
    dimensions: int | None = None,
    model_name: str | None = None,
) -> EmbeddingAdapter:
    resolved_provider = provider or os.environ.get("EMBEDDING_PROVIDER", "deterministic")
    resolved_dimensions = dimensions or int(getattr(settings, "VECTOR_DIMENSIONS", 1024))
    resolved_model = model_name or getattr(settings, "EMBEDDING_MODEL", "deterministic-token-hash")

    if resolved_provider == "http":
        return HttpEmbeddingAdapter(
            service_url=getattr(settings, "EMBEDDING_SERVICE_URL", "http://localhost:8080"),
            model_name=resolved_model,
            dimensions=resolved_dimensions,
            timeout=float(os.environ.get("EMBEDDING_TIMEOUT", "15")),
        )
    if resolved_provider == "deterministic":
        return DeterministicEmbeddingAdapter(dimensions=resolved_dimensions, model_name=resolved_model)
    raise EmbeddingError(f"unsupported embedding provider: {resolved_provider}")
