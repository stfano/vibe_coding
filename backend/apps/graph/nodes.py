from __future__ import annotations

from django.db import connection

from apps.graph.state import (
    ANSWER_GROUNDING_FAILED_ANSWER,
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
from apps.rag.grounding import review_grounded_answer
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


def safety_review(state: ChatGraphState) -> tuple[dict, str]:
    if state.get("source_status") != "retrieved" or not state.get("llm_executed"):
        return {"answer_safety_status": "skipped"}, "answer review skipped"

    prompt_payload = state.get("prompt_payload") or {}
    contexts = prompt_payload.get("contexts") or []
    review = review_grounded_answer(answer=state.get("answer") or "", contexts=contexts)
    update = {
        "answer_safety_status": review.status,
        "answer_safety_findings": review.findings,
        "answer_review_allowed_citation_ids": review.allowed_citation_ids,
        "answer_review_detected_citation_ids": review.detected_citation_ids,
        "answer_review_unknown_citation_ids": review.unknown_citation_ids,
    }
    if review.status == "passed":
        return update, "answer grounding review passed"

    safety_flags = state.get("safety_flags") or []
    for finding in review.findings:
        safety_flags = _append_unique(safety_flags, _safety_flag_for_finding(finding))
    return {
        **update,
        "source_status": "answer_grounding_failed",
        "answer": ANSWER_GROUNDING_FAILED_ANSWER,
        "safety_flags": _append_unique(safety_flags, "answer_grounding_failed"),
    }, "answer grounding review failed"


def format_response(state: ChatGraphState) -> tuple[dict, str]:
    source_status = state.get("source_status")
    if source_status == "urgent_escalation":
        answer = URGENT_ESCALATION_ANSWER
    elif source_status == "low_confidence":
        answer = LOW_CONFIDENCE_ANSWER
    elif source_status == "answer_grounding_failed":
        answer = state.get("answer") or ANSWER_GROUNDING_FAILED_ANSWER
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
        "answer_safety_status": "skipped",
        "answer_safety_findings": [],
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


def _safety_flag_for_finding(finding: str) -> str:
    return {
        "missing_known_citation": "answer_missing_citation",
        "unknown_citation": "answer_unknown_citation",
        "definitive_diagnosis_language": "answer_definitive_diagnosis_language",
        "unsupported_medication_dose": "answer_unsupported_medication_dose",
        "unsupported_prescription_language": "answer_unsupported_prescription_language",
    }.get(finding, f"answer_{finding}")
