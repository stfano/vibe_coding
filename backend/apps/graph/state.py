from __future__ import annotations

from typing import Any, TypedDict

from django.conf import settings

from apps.rag.retrieval import KnowledgeSearchResult


GRAPH_VERSION = "chat_safety_router_v2"
GRAPH_RUNTIME = "langgraph_stategraph"
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
GRAPH_ERROR_ANSWER = (
    "Doctor Chat could not complete the source-grounded workflow safely. Please review the "
    "graph metadata and try again after the retrieval or model service is healthy."
)
ANSWER_GROUNDING_FAILED_ANSWER = (
    "Doctor Chat retrieved approved source context, but the generated answer failed grounding checks. "
    "Please review the cited source previews and graph metadata before using this response for clinical support."
)


class NodeSummary(TypedDict):
    name: str
    duration_ms: int
    summary: str


class ChatGraphState(TypedDict, total=False):
    message: str
    top_k: int
    low_confidence_threshold: float
    source: str | None
    department_code: str | None
    graph_path: list[str]
    node_summaries: list[NodeSummary]
    red_flag_terms: list[str]
    retrieved_results: list[KnowledgeSearchResult]
    source_status: str
    answer: str
    citations: list[dict[str, Any]]
    safety_flags: list[str]
    retrieved_source_ids: list[int]
    prompt_payload: dict[str, Any] | None
    prompt_version: str | None
    model_name: str | None
    llm_executed: bool
    error_summary: str | None
    answer_safety_status: str
    answer_safety_findings: list[str]
    answer_review_allowed_citation_ids: list[str]
    answer_review_detected_citation_ids: list[str]
    answer_review_unknown_citation_ids: list[str]


def build_initial_state(
    *,
    message: str,
    top_k: int = DEFAULT_TOP_K,
    source: str | None = None,
    department_code: str | None = None,
    low_confidence_threshold: float | None = None,
) -> ChatGraphState:
    return {
        "message": message,
        "top_k": top_k,
        "low_confidence_threshold": (
            low_confidence_threshold
            if low_confidence_threshold is not None
            else float(getattr(settings, "CHAT_RAG_LOW_CONFIDENCE_THRESHOLD", DEFAULT_LOW_CONFIDENCE_THRESHOLD))
        ),
        "source": source,
        "department_code": department_code,
        "graph_path": [],
        "node_summaries": [],
        "red_flag_terms": [],
        "retrieved_results": [],
        "source_status": "not_started",
        "answer": "",
        "citations": [],
        "safety_flags": [],
        "retrieved_source_ids": [],
        "prompt_payload": None,
        "prompt_version": None,
        "model_name": None,
        "llm_executed": False,
        "error_summary": None,
        "answer_safety_status": "skipped",
        "answer_safety_findings": [],
        "answer_review_allowed_citation_ids": [],
        "answer_review_detected_citation_ids": [],
        "answer_review_unknown_citation_ids": [],
    }


def serialize_state(state: ChatGraphState) -> dict[str, Any]:
    retrieved_results = state.get("retrieved_results") or []
    retrieved_source_ids = state.get("retrieved_source_ids") or []
    source_status = state.get("source_status") or "not_started"
    safety_flags = state.get("safety_flags") or []
    return {
        "answer": state.get("answer") or "",
        "source_status": source_status,
        "citations": state.get("citations") or [],
        "safety_flags": safety_flags,
        "red_flag_terms": state.get("red_flag_terms") or [],
        "retrieved_source_ids": retrieved_source_ids,
        "llm_executed": bool(state.get("llm_executed")),
        "retrieved_chunks": [
            {
                "chunk_id": result.chunk_id,
                "document_id": result.document_id,
                "document_status": result.document_status,
                "score": result.score,
                "preview": result.text_preview,
                "citation": result.citation,
            }
            for result in retrieved_results
        ],
        "graph": {
            "executed": True,
            "runtime": GRAPH_RUNTIME,
            "version": GRAPH_VERSION,
            "path": state.get("graph_path") or [],
            "node_summaries": state.get("node_summaries") or [],
            "retrieved_source_ids": retrieved_source_ids,
            "source_status": source_status,
            "safety_flags": safety_flags,
            "model_name": state.get("model_name"),
            "prompt_version": state.get("prompt_version"),
            "llm_executed": bool(state.get("llm_executed")),
            "error_summary": state.get("error_summary"),
            "answer_safety_status": state.get("answer_safety_status") or "skipped",
            "answer_safety_findings": state.get("answer_safety_findings") or [],
            "answer_review_allowed_citation_ids": state.get("answer_review_allowed_citation_ids") or [],
            "answer_review_detected_citation_ids": state.get("answer_review_detected_citation_ids") or [],
            "answer_review_unknown_citation_ids": state.get("answer_review_unknown_citation_ids") or [],
        },
    }
