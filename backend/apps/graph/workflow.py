from __future__ import annotations

import time
from collections.abc import Callable
from typing import Literal

from langgraph.graph import END, START, StateGraph

from apps.graph import nodes
from apps.graph.state import ChatGraphState, NodeSummary
from apps.rag.embeddings import EmbeddingAdapter
from apps.rag.llms import ChatLLMAdapter

NodeResult = tuple[dict, str]
NodeFunc = Callable[[ChatGraphState], NodeResult]


def run_langgraph_chat_workflow(
    *,
    initial_state: ChatGraphState,
    embedding_adapter: EmbeddingAdapter | None = None,
    llm_adapter: ChatLLMAdapter | None = None,
) -> ChatGraphState:
    workflow = build_chat_workflow(embedding_adapter=embedding_adapter, llm_adapter=llm_adapter)
    return workflow.invoke(initial_state)


def build_chat_workflow(
    *,
    embedding_adapter: EmbeddingAdapter | None = None,
    llm_adapter: ChatLLMAdapter | None = None,
):
    builder = StateGraph(ChatGraphState)
    builder.add_node("validate_input", _instrumented("validate_input", nodes.validate_input))
    builder.add_node("detect_red_flags", _instrumented("detect_red_flags", nodes.detect_red_flags))
    builder.add_node("retrieve_ready_documents", _instrumented(
        "retrieve_ready_documents",
        lambda state: nodes.retrieve_ready_documents(state, embedding_adapter=embedding_adapter),
    ))
    builder.add_node("decide_source_status", _instrumented("decide_source_status", nodes.decide_source_status))
    builder.add_node("synthesize_answer", _instrumented(
        "synthesize_answer",
        lambda state: nodes.synthesize_answer(state, llm_adapter=llm_adapter),
    ))
    builder.add_node("safety_review", _instrumented("safety_review", nodes.safety_review))
    builder.add_node("format_response", _instrumented("format_response", nodes.format_response))
    builder.add_node("persist_metadata", _instrumented("persist_metadata", nodes.persist_metadata))

    builder.add_edge(START, "validate_input")
    builder.add_edge("validate_input", "detect_red_flags")
    builder.add_conditional_edges(
        "detect_red_flags",
        _route_after_red_flags,
        {
            "red_flag": "decide_source_status",
            "retrieve": "retrieve_ready_documents",
        },
    )
    builder.add_conditional_edges(
        "retrieve_ready_documents",
        _route_after_retrieval,
        {
            "decide": "decide_source_status",
            "format": "format_response",
        },
    )
    builder.add_conditional_edges(
        "decide_source_status",
        _route_after_source_status,
        {
            "synthesize": "synthesize_answer",
            "format": "format_response",
        },
    )
    builder.add_edge("synthesize_answer", "safety_review")
    builder.add_edge("safety_review", "format_response")
    builder.add_edge("format_response", "persist_metadata")
    builder.add_edge("persist_metadata", END)
    return builder.compile()


def _route_after_red_flags(state: ChatGraphState) -> Literal["red_flag", "retrieve"]:
    if state.get("red_flag_terms") or state.get("source_status") == "graph_error":
        return "red_flag"
    return "retrieve"


def _route_after_retrieval(state: ChatGraphState) -> Literal["decide", "format"]:
    if state.get("source_status") == "graph_error":
        return "format"
    return "decide"


def _route_after_source_status(state: ChatGraphState) -> Literal["synthesize", "format"]:
    if state.get("source_status") == "retrieved":
        return "synthesize"
    return "format"


def _instrumented(name: str, node_func: NodeFunc):
    def wrapped(state: ChatGraphState) -> dict:
        started_at = time.perf_counter()
        try:
            update, summary = node_func(state)
        except Exception:
            update = nodes.safe_graph_error_update(state, node_name=name)
            summary = update["error_summary"]
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        return {
            **update,
            "graph_path": [*(state.get("graph_path") or []), name],
            "node_summaries": [
                *(state.get("node_summaries") or []),
                NodeSummary(name=name, duration_ms=duration_ms, summary=summary),
            ],
        }

    return wrapped
