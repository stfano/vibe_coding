from __future__ import annotations

from django.db import connection

from apps.graph.state import (
    GRAPH_ERROR_ANSWER,
    LOW_CONFIDENCE_ANSWER,
    NO_SOURCE_ANSWER,
    RETRIEVED_CONTEXT_ANSWER,
    URGENT_ESCALATION_ANSWER,
    ChatGraphState,
)
from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument
from apps.knowledge.safety import detect_red_flag_query
from apps.rag.embeddings import DeterministicEmbeddingAdapter, EmbeddingAdapter
from apps.rag.llms import ChatLLMAdapter, build_source_grounded_prompt_payload, get_chat_llm_adapter
from apps.rag.retrieval import search_knowledge


def validate_input(state: ChatGraphState) -> tuple[dict, str]:
    message = state.get("message", "").strip()
    return {"message": message}, "input accepted" if message else "empty input"


def detect_red_flags(state: ChatGraphState) -> tuple[dict, str]:
    red_flag_terms = detect_red_flag_query(state.get("message", ""))
    if red_flag_terms:
        return {
            "red_flag_terms": red_flag_terms,
            "safety_flags": _append_unique(state.get("safety_flags") or [], "red_flag_query"),
        }, f"red flags detected: {', '.join(red_flag_terms)}"
    return {"red_flag_terms": []}, "no red flags detected"


def retrieve_ready_documents(
    state: ChatGraphState,
    *,
    embedding_adapter: EmbeddingAdapter | None,
) -> tuple[dict, str]:
    adapter = embedding_adapter or _sqlite_test_embedding_adapter()
    retrieved_results = search_knowledge(
        state.get("message", ""),
        top_k=state.get("top_k", 5),
        embedding_adapter=adapter,
        source=state.get("source"),
        department_code=state.get("department_code"),
        include_needs_review=False,
    )
    citations = [result.citation for result in retrieved_results]
    retrieved_source_ids = list(dict.fromkeys(result.document_id for result in retrieved_results))
    return {
        "retrieved_results": retrieved_results,
        "citations": citations,
        "retrieved_source_ids": retrieved_source_ids,
    }, f"retrieved {len(retrieved_results)} ready chunks"


def decide_source_status(state: ChatGraphState) -> tuple[dict, str]:
    if state.get("red_flag_terms"):
        return {"source_status": "urgent_escalation"}, "retrieval suppressed for red-flag query"

    retrieved_results = state.get("retrieved_results") or []
    if not retrieved_results:
        return {
            "source_status": "no_matching_ready_documents",
            "safety_flags": _append_unique(state.get("safety_flags") or [], "no_ready_documents"),
        }, "no ready documents matched"

    top_score = max(result.score for result in retrieved_results)
    if top_score < state.get("low_confidence_threshold", 0.05):
        return {
            "source_status": "low_confidence",
            "safety_flags": _append_unique(state.get("safety_flags") or [], "low_confidence_retrieval"),
        }, f"top score {top_score:.4f} below threshold"

    return {
        "source_status": "retrieved",
        "safety_flags": _append_unique(state.get("safety_flags") or [], "retrieved_context_available"),
    }, f"ready context available; top score {top_score:.4f}"


def synthesize_answer(
    state: ChatGraphState,
    *,
    llm_adapter: ChatLLMAdapter | None,
) -> tuple[dict, str]:
    adapter = llm_adapter or get_chat_llm_adapter()
    payload = build_source_grounded_prompt_payload(
        query=state.get("message", ""),
        results=state.get("retrieved_results") or [],
    )
    response = adapter.generate_answer(payload)
    return {
        "prompt_payload": payload,
        "prompt_version": payload["prompt_version"],
        "model_name": response.model_name,
        "answer": response.text,
        "llm_executed": True,
    }, f"generated source-grounded answer with {adapter.model_name}"


def format_response(state: ChatGraphState) -> tuple[dict, str]:
    source_status = state.get("source_status")
    if source_status == "urgent_escalation":
        answer = URGENT_ESCALATION_ANSWER
    elif source_status == "low_confidence":
        answer = LOW_CONFIDENCE_ANSWER
    elif source_status == "retrieved":
        answer = state.get("answer") or RETRIEVED_CONTEXT_ANSWER
    elif source_status == "graph_error":
        answer = GRAPH_ERROR_ANSWER
    else:
        answer = NO_SOURCE_ANSWER
    return {"answer": answer}, f"formatted {source_status} response"


def persist_metadata(state: ChatGraphState) -> tuple[dict, str]:
    return {}, "metadata prepared for chat persistence"


def safe_graph_error_update(state: ChatGraphState, *, node_name: str) -> dict:
    return {
        "source_status": "graph_error",
        "safety_flags": _append_unique(state.get("safety_flags") or [], "graph_error"),
        "error_summary": f"{node_name} failed",
        "llm_executed": False,
        "model_name": None,
        "prompt_version": None,
    }


def _sqlite_test_embedding_adapter() -> EmbeddingAdapter | None:
    if connection.vendor != "sqlite":
        return None

    chunk = (
        KnowledgeChunk.objects.select_related("document", "document__source")
        .filter(document__status=KnowledgeDocument.Status.READY, document__source__is_active=True)
        .order_by("id")
        .first()
    )
    if chunk is None or not chunk.embedding_dimensions:
        return None
    return DeterministicEmbeddingAdapter(
        dimensions=chunk.embedding_dimensions,
        model_name=chunk.embedding_model or "deterministic-token-hash",
    )


def _append_unique(values: list[str], value: str) -> list[str]:
    if value in values:
        return values
    return [*values, value]
