from __future__ import annotations

from typing import Any

from apps.graph.state import (
    DEFAULT_LOW_CONFIDENCE_THRESHOLD,
    DEFAULT_TOP_K,
    GRAPH_ERROR_ANSWER,
    GRAPH_VERSION,
    LOW_CONFIDENCE_ANSWER,
    NO_SOURCE_ANSWER,
    RETRIEVED_CONTEXT_ANSWER,
    URGENT_ESCALATION_ANSWER,
    build_initial_state,
    serialize_state,
)
from apps.graph.workflow import run_langgraph_chat_workflow
from apps.rag.embeddings import EmbeddingAdapter
from apps.rag.llms import ChatLLMAdapter


def run_chat_safety_graph(
    *,
    message: str,
    top_k: int = DEFAULT_TOP_K,
    embedding_adapter: EmbeddingAdapter | None = None,
    llm_adapter: ChatLLMAdapter | None = None,
    source: str | None = None,
    department_code: str | None = None,
    low_confidence_threshold: float | None = None,
) -> dict[str, Any]:
    initial_state = build_initial_state(
        message=message,
        top_k=top_k,
        source=source,
        department_code=department_code,
        low_confidence_threshold=low_confidence_threshold,
    )
    final_state = run_langgraph_chat_workflow(
        initial_state=initial_state,
        embedding_adapter=embedding_adapter,
        llm_adapter=llm_adapter,
    )
    return serialize_state(final_state)


__all__ = [
    "DEFAULT_LOW_CONFIDENCE_THRESHOLD",
    "DEFAULT_TOP_K",
    "GRAPH_ERROR_ANSWER",
    "GRAPH_VERSION",
    "LOW_CONFIDENCE_ANSWER",
    "NO_SOURCE_ANSWER",
    "RETRIEVED_CONTEXT_ANSWER",
    "URGENT_ESCALATION_ANSWER",
    "run_chat_safety_graph",
]
