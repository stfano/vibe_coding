from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

from django.db import connection

from apps.knowledge.models import KnowledgeChunk
from apps.rag.embeddings import EmbeddingAdapter, get_embedding_adapter, vector_to_pgvector


@dataclass(frozen=True)
class KnowledgeSearchResult:
    chunk_id: int
    document_id: int
    document_status: str
    score: float
    text_preview: str
    citation: dict[str, Any]
    text: str = ""
    raw_score: float | None = None
    rerank_score: float | None = None


def search_knowledge(
    query: str,
    *,
    top_k: int = 5,
    embedding_adapter: EmbeddingAdapter | None = None,
    source: str | None = None,
    department_code: str | None = None,
    include_needs_review: bool = False,
) -> list[KnowledgeSearchResult]:
    if not query.strip() or top_k <= 0:
        return []
    adapter = embedding_adapter or get_embedding_adapter()
    query_embedding = adapter.embed_query(query)
    if connection.vendor == "postgresql":
        try:
            return _search_postgres(
                query_embedding,
                top_k=top_k,
                source=source,
                department_code=department_code,
                include_needs_review=include_needs_review,
            )
        except Exception:
            # Keep management smoke tests usable on early databases where pgvector
            # extension setup is still being validated.
            return _search_python(
                query_embedding,
                top_k=top_k,
                source=source,
                department_code=department_code,
                include_needs_review=include_needs_review,
            )
    return _search_python(
        query_embedding,
        top_k=top_k,
        source=source,
        department_code=department_code,
        include_needs_review=include_needs_review,
    )


def _search_python(
    query_embedding: list[float],
    *,
    top_k: int,
    source: str | None,
    department_code: str | None,
    include_needs_review: bool,
) -> list[KnowledgeSearchResult]:
    queryset = KnowledgeChunk.objects.select_related("document", "document__source")
    allowed_statuses = ["ready"]
    if include_needs_review:
        allowed_statuses.append("needs_review")
    queryset = queryset.filter(document__status__in=allowed_statuses, document__source__is_active=True)
    if source:
        queryset = queryset.filter(document__source__key=source)
    if department_code:
        queryset = queryset.filter(document__department_code=department_code)

    results = []
    for chunk in queryset:
        if not chunk.embedding:
            continue
        score = _cosine_similarity(query_embedding, [float(value) for value in chunk.embedding])
        results.append(_build_result(chunk, score=score))
    return sorted(results, key=lambda item: item.score, reverse=True)[:top_k]


def _search_postgres(
    query_embedding: list[float],
    *,
    top_k: int,
    source: str | None,
    department_code: str | None,
    include_needs_review: bool,
) -> list[KnowledgeSearchResult]:
    filters = ["c.embedding_vector IS NOT NULL", "s.is_active = true"]
    params: list[object] = [vector_to_pgvector(query_embedding)]
    if include_needs_review:
        filters.append("d.status IN ('ready', 'needs_review')")
    else:
        filters.append("d.status = 'ready'")
    if source:
        filters.append("s.key = %s")
        params.append(source)
    if department_code:
        filters.append("d.department_code = %s")
        params.append(department_code)
    params.append(top_k)

    sql = f"""
        SELECT
            c.id,
            d.id,
            d.status,
            GREATEST(0, 1 - (c.embedding_vector <=> %s::vector)) AS score,
            LEFT(c.text, 240) AS text_preview,
            c.citation_metadata,
            c.text
        FROM knowledge_knowledgechunk c
        JOIN knowledge_knowledgedocument d ON c.document_id = d.id
        JOIN knowledge_knowledgesource s ON d.source_id = s.id
        WHERE {' AND '.join(filters)}
        ORDER BY c.embedding_vector <=> %s::vector
        LIMIT %s
    """
    params.insert(len(params) - 1, params[0])

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()

    return [
        KnowledgeSearchResult(
            chunk_id=row[0],
            document_id=row[1],
            document_status=row[2],
            score=float(row[3]),
            text_preview=row[4],
            citation=_normalize_citation(row[5]),
            text=row[6],
            raw_score=float(row[3]),
            rerank_score=None,
        )
        for row in rows
    ]


def _build_result(chunk: KnowledgeChunk, *, score: float) -> KnowledgeSearchResult:
    return KnowledgeSearchResult(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        document_status=chunk.document.status,
        score=round(score, 6),
        text_preview=chunk.text[:240],
        citation=chunk.citation_metadata or {},
        text=chunk.text,
        raw_score=round(score, 6),
        rerank_score=None,
    )


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_length = math.sqrt(sum(a * a for a in left))
    right_length = math.sqrt(sum(b * b for b in right))
    if left_length == 0 or right_length == 0:
        return 0.0
    return numerator / (left_length * right_length)


def _normalize_citation(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}
