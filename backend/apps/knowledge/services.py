from __future__ import annotations

from typing import Any

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404

from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument
from apps.knowledge.safety import detect_red_flag_query
from apps.rag.embeddings import DeterministicEmbeddingAdapter
from apps.rag.retrieval import search_knowledge


MAX_PAGE_SIZE = 50
DEFAULT_PAGE_SIZE = 20


def list_knowledge_documents(filters: dict[str, Any]) -> dict[str, Any]:
    page = max(1, int(filters.get("page") or 1))
    page_size = min(MAX_PAGE_SIZE, max(1, int(filters.get("page_size") or DEFAULT_PAGE_SIZE)))
    queryset = (
        KnowledgeDocument.objects.select_related("source", "external_qna_record")
        .annotate(chunk_count=Count("chunks"))
        .order_by("-updated_at", "id")
    )

    if source := filters.get("source"):
        queryset = queryset.filter(source__key=source)
    if department_code := filters.get("department_code"):
        queryset = queryset.filter(department_code=department_code)
    if status := filters.get("status"):
        queryset = queryset.filter(status=status)
    if q := filters.get("q"):
        queryset = queryset.filter(Q(title__icontains=q) | Q(source_external_id__icontains=q))

    count = queryset.count()
    offset = (page - 1) * page_size
    return {
        "count": count,
        "page": page,
        "page_size": page_size,
        "results": [_serialize_document_summary(document) for document in queryset[offset : offset + page_size]],
    }


def get_knowledge_document_detail(document_id: int) -> dict[str, Any]:
    document = get_object_or_404(
        KnowledgeDocument.objects.select_related("source", "external_qna_record"),
        id=document_id,
    )
    return {
        "document": _serialize_document_summary(document),
        "external_qna_record": _serialize_external_qna_record(document),
        "chunks": [
            {
                "id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "text_preview": chunk.text[:500],
                "embedding_model": chunk.embedding_model,
                "embedding_dimensions": chunk.embedding_dimensions,
                "citation_metadata": chunk.citation_metadata,
                "indexed_at": chunk.indexed_at.isoformat() if chunk.indexed_at else None,
            }
            for chunk in document.chunks.order_by("chunk_index")
        ],
    }


def update_knowledge_document_status(document_id: int, *, status: str) -> dict[str, Any]:
    document = get_object_or_404(KnowledgeDocument.objects.select_related("source"), id=document_id)
    document.status = status
    document.metadata = {
        **document.metadata,
        "review": {
            "status": status,
        },
    }
    document.save(update_fields=["status", "metadata", "updated_at"])
    document.chunk_count = document.chunks.count()
    return _serialize_document_summary(document)


def verify_knowledge_search(
    *,
    query: str,
    top_k: int,
    source: str | None = None,
    department_code: str | None = None,
    include_needs_review: bool = False,
) -> dict[str, Any]:
    red_flags = detect_red_flag_query(query)
    if red_flags:
        return {
            "query": query,
            "source_status": "retrieval_suppressed",
            "safety_flags": ["red_flag_query"],
            "red_flag_terms": red_flags,
            "llm_executed": False,
            "graph_executed": False,
            "results": [],
        }

    results = search_knowledge(
        query,
        top_k=top_k,
        source=source,
        department_code=department_code,
        include_needs_review=include_needs_review,
        embedding_adapter=_verification_embedding_adapter(source, department_code, include_needs_review),
    )
    source_status = "retrieved" if results else "no_matching_chunks"
    return {
        "query": query,
        "source_status": source_status,
        "safety_flags": [],
        "llm_executed": False,
        "graph_executed": False,
        "results": [
            {
                "rank": index,
                "chunk_id": result.chunk_id,
                "document_id": result.document_id,
                "document_status": result.document_status,
                "score": result.score,
                "preview": result.text_preview,
                "citation": result.citation,
            }
            for index, result in enumerate(results, start=1)
        ],
    }


def _serialize_document_summary(document: KnowledgeDocument) -> dict[str, Any]:
    chunk_count = getattr(document, "chunk_count", None)
    if chunk_count is None:
        chunk_count = document.chunks.count()
    return {
        "id": document.id,
        "source": document.source.key,
        "source_display_name": document.source.display_name,
        "source_license_status": document.source.license_status,
        "source_external_id": document.source_external_id,
        "title": document.title,
        "department": document.department,
        "department_code": document.department_code,
        "status": document.status,
        "source_url": document.source_url,
        "chunk_count": chunk_count,
        "updated_at": document.updated_at.isoformat(),
    }


def _serialize_external_qna_record(document: KnowledgeDocument) -> dict[str, Any] | None:
    record = document.external_qna_record
    if record is None:
        return None
    return {
        "id": record.id,
        "source": record.source,
        "external_id": record.external_id,
        "source_question_id": record.source_question_id,
        "source_answer_id": record.source_answer_id,
        "question_title": record.question_title,
        "question_body": record.question_body,
        "answer_body": record.answer_body,
        "answerer_name": record.answerer_name,
        "answerer_title": record.answerer_title,
        "source_url": record.source_url,
        "tags": record.tags,
        "collected_at": record.collected_at.isoformat(),
    }


def _verification_embedding_adapter(source: str | None, department_code: str | None, include_needs_review: bool):
    from django.db import connection

    if connection.vendor != "sqlite":
        return None

    queryset = KnowledgeChunk.objects.select_related("document", "document__source")
    allowed_statuses = [KnowledgeDocument.Status.READY]
    if include_needs_review:
        allowed_statuses.append(KnowledgeDocument.Status.NEEDS_REVIEW)
    queryset = queryset.filter(document__status__in=allowed_statuses, document__source__is_active=True)
    if source:
        queryset = queryset.filter(document__source__key=source)
    if department_code:
        queryset = queryset.filter(document__department_code=department_code)
    chunk = queryset.order_by("id").first()
    if chunk is None or not chunk.embedding_dimensions:
        return None
    return DeterministicEmbeddingAdapter(
        dimensions=chunk.embedding_dimensions,
        model_name=chunk.embedding_model or "deterministic-token-hash",
    )
