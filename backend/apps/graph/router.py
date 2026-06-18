from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from django.db import connection

from apps.knowledge.models import KnowledgeChunk, KnowledgeDocument
from apps.knowledge.safety import detect_red_flag_query
from apps.rag.embeddings import DeterministicEmbeddingAdapter, EmbeddingAdapter
from apps.rag.llms import (
    ChatLLMAdapter,
    build_source_grounded_prompt_payload,
    get_chat_llm_adapter,
)
from apps.rag.retrieval import KnowledgeSearchResult, search_knowledge


GRAPH_VERSION = "chat_safety_router_v1"
DEFAULT_TOP_K = 5
DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.05

NO_SOURCE_ANSWER = (
    "No approved medical knowledge documents are indexed yet, so I cannot provide a "
    "source-grounded clinical answer. Please index and review approved clinical content "
    "before using Doctor Chat for medical knowledge retrieval."
)
LOW_CONFIDENCE_ANSWER = (
    "I found approved knowledge content, but the retrieval confidence is too low to use it "
    "as source-grounded support. Please refine the query or review the indexed sources."
)
URGENT_ESCALATION_ANSWER = (
    "This query includes red-flag symptoms. Do not use candidate Q&A retrieval for this case. "
    "Follow urgent clinical escalation protocols and assess the patient immediately."
)
RETRIEVED_CONTEXT_ANSWER = (
    "I found approved indexed context for clinician review. No LLM answer was generated. "
    "Use the citation metadata and source previews to decide whether the evidence is relevant."
)


@dataclass
class NodeTrace:
    name: str
    duration_ms: int
    summary: str


@dataclass
class ChatGraphState:
    message: str
    top_k: int = DEFAULT_TOP_K
    low_confidence_threshold: float = DEFAULT_LOW_CONFIDENCE_THRESHOLD
    graph_path: list[str] = field(default_factory=list)
    node_summaries: list[NodeTrace] = field(default_factory=list)
    red_flag_terms: list[str] = field(default_factory=list)
    retrieved_results: list[KnowledgeSearchResult] = field(default_factory=list)
    source_status: str = "not_started"
    answer: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    safety_flags: list[str] = field(default_factory=list)
    retrieved_source_ids: list[int] = field(default_factory=list)
    prompt_payload: dict[str, Any] | None = None
    prompt_version: str | None = None
    model_name: str | None = None
    llm_executed: bool = False


def run_chat_safety_graph(
    *,
    message: str,
    top_k: int = DEFAULT_TOP_K,
    embedding_adapter: EmbeddingAdapter | None = None,
    llm_adapter: ChatLLMAdapter | None = None,
) -> dict[str, Any]:
    state = ChatGraphState(
        message=message,
        top_k=top_k,
        low_confidence_threshold=float(
            getattr(settings, "CHAT_RAG_LOW_CONFIDENCE_THRESHOLD", DEFAULT_LOW_CONFIDENCE_THRESHOLD)
        ),
    )
    _run_node(state, "validate_input", _validate_input)
    _run_node(state, "detect_red_flags", _detect_red_flags)

    if state.red_flag_terms:
        _run_node(state, "decide_source_status", _decide_source_status)
        _run_node(state, "format_response", _format_response)
        _run_node(state, "persist_metadata", _persist_metadata)
        return _serialize_state(state)

    _run_node(
        state,
        "retrieve_ready_documents",
        lambda current: _retrieve_ready_documents(current, embedding_adapter=embedding_adapter),
    )
    _run_node(state, "decide_source_status", _decide_source_status)
    if state.source_status == "retrieved":
        _run_node(state, "synthesize_answer", lambda current: _synthesize_answer(current, llm_adapter=llm_adapter))
    _run_node(state, "format_response", _format_response)
    _run_node(state, "persist_metadata", _persist_metadata)
    return _serialize_state(state)


def _run_node(state: ChatGraphState, name: str, node_func) -> None:
    started_at = time.perf_counter()
    summary = node_func(state)
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    state.graph_path.append(name)
    state.node_summaries.append(NodeTrace(name=name, duration_ms=duration_ms, summary=summary))


def _validate_input(state: ChatGraphState) -> str:
    state.message = state.message.strip()
    return "input accepted" if state.message else "empty input"


def _detect_red_flags(state: ChatGraphState) -> str:
    state.red_flag_terms = detect_red_flag_query(state.message)
    if state.red_flag_terms:
        state.safety_flags.append("red_flag_query")
        return f"red flags detected: {', '.join(state.red_flag_terms)}"
    return "no red flags detected"


def _retrieve_ready_documents(
    state: ChatGraphState,
    *,
    embedding_adapter: EmbeddingAdapter | None,
) -> str:
    adapter = embedding_adapter or _sqlite_test_embedding_adapter()
    state.retrieved_results = search_knowledge(
        state.message,
        top_k=state.top_k,
        embedding_adapter=adapter,
        include_needs_review=False,
    )
    state.citations = [result.citation for result in state.retrieved_results]
    state.retrieved_source_ids = list(dict.fromkeys(result.document_id for result in state.retrieved_results))
    return f"retrieved {len(state.retrieved_results)} ready chunks"


def _decide_source_status(state: ChatGraphState) -> str:
    if state.red_flag_terms:
        state.source_status = "urgent_escalation"
        return "retrieval suppressed for red-flag query"

    if not state.retrieved_results:
        state.source_status = "no_matching_ready_documents"
        state.safety_flags.append("no_ready_documents")
        return "no ready documents matched"

    top_score = max(result.score for result in state.retrieved_results)
    if top_score < state.low_confidence_threshold:
        state.source_status = "low_confidence"
        state.safety_flags.append("low_confidence_retrieval")
        return f"top score {top_score:.4f} below threshold"

    state.source_status = "retrieved"
    state.safety_flags.append("retrieved_context_available")
    return f"ready context available; top score {top_score:.4f}"


def _format_response(state: ChatGraphState) -> str:
    if state.source_status == "urgent_escalation":
        state.answer = URGENT_ESCALATION_ANSWER
    elif state.source_status == "low_confidence":
        state.answer = LOW_CONFIDENCE_ANSWER
    elif state.source_status == "retrieved":
        if not state.answer:
            state.answer = RETRIEVED_CONTEXT_ANSWER
    else:
        state.answer = NO_SOURCE_ANSWER
    return f"formatted {state.source_status} response"


def _synthesize_answer(state: ChatGraphState, *, llm_adapter: ChatLLMAdapter | None) -> str:
    adapter = llm_adapter or get_chat_llm_adapter()
    payload = build_source_grounded_prompt_payload(query=state.message, results=state.retrieved_results)
    response = adapter.generate_answer(payload)
    state.prompt_payload = payload
    state.prompt_version = payload["prompt_version"]
    state.model_name = response.model_name
    state.answer = response.text
    state.llm_executed = True
    return f"generated source-grounded answer with {adapter.model_name}"


def _persist_metadata(state: ChatGraphState) -> str:
    return "metadata prepared for chat persistence"


def _serialize_state(state: ChatGraphState) -> dict[str, Any]:
    return {
        "answer": state.answer,
        "source_status": state.source_status,
        "citations": state.citations,
        "safety_flags": state.safety_flags,
        "red_flag_terms": state.red_flag_terms,
        "retrieved_source_ids": state.retrieved_source_ids,
        "llm_executed": state.llm_executed,
        "retrieved_chunks": [
            {
                "chunk_id": result.chunk_id,
                "document_id": result.document_id,
                "document_status": result.document_status,
                "score": result.score,
                "preview": result.text_preview,
                "citation": result.citation,
            }
            for result in state.retrieved_results
        ],
        "graph": {
            "executed": True,
            "version": GRAPH_VERSION,
            "path": state.graph_path,
            "node_summaries": [
                {
                    "name": trace.name,
                    "duration_ms": trace.duration_ms,
                    "summary": trace.summary,
                }
                for trace in state.node_summaries
            ],
            "retrieved_source_ids": state.retrieved_source_ids,
            "source_status": state.source_status,
            "safety_flags": state.safety_flags,
            "model_name": state.model_name,
            "prompt_version": state.prompt_version,
            "llm_executed": state.llm_executed,
        },
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
