from __future__ import annotations

from apps.rag.llms import (
    DeterministicChatLLMAdapter,
    LLMResponse,
    build_ollama_generate_payload,
    build_source_grounded_prompt_payload,
)
from apps.rag.retrieval import KnowledgeSearchResult


def test_build_source_grounded_prompt_payload_shape():
    result = KnowledgeSearchResult(
        chunk_id=10,
        document_id=20,
        document_status="ready",
        score=0.91,
        text_preview="짧은 미리보기",
        text="아기띠 후 고환 물집처럼 보이는 증상에 관한 전체 ready chunk",
        citation={
            "source": "hidoc",
            "external_question_id": "C10",
            "external_answer_id": "A20",
        },
    )

    payload = build_source_grounded_prompt_payload(query="아기 고환 물집", results=[result])

    assert set(payload) == {"prompt_version", "instructions", "query", "contexts"}
    assert payload["query"] == "아기 고환 물집"
    assert payload["contexts"] == [
        {
            "chunk_id": 10,
            "document_id": 20,
            "score": 0.91,
            "text": "아기띠 후 고환 물집처럼 보이는 증상에 관한 전체 ready chunk",
            "citation": {
                "source": "hidoc",
                "external_question_id": "C10",
                "external_answer_id": "A20",
            },
        }
    ]


def test_deterministic_chat_llm_adapter_returns_cited_answer():
    adapter = DeterministicChatLLMAdapter(model_name="test-llm")
    payload = build_source_grounded_prompt_payload(
        query="아기 고환 물집",
        results=[
            KnowledgeSearchResult(
                chunk_id=1,
                document_id=2,
                document_status="ready",
                score=0.8,
                text_preview="압박으로 인한 일시 변화 가능성이 있습니다.",
                citation={"external_question_id": "C1", "external_answer_id": "A1"},
            )
        ],
    )

    response = adapter.generate_answer(payload)

    assert isinstance(response, LLMResponse)
    assert response.model_name == "test-llm"
    assert "C1:A1" in response.text


def test_build_ollama_generate_payload_uses_model_and_non_streaming_prompt():
    payload = build_source_grounded_prompt_payload(query="query", results=[])

    ollama_payload = build_ollama_generate_payload(payload=payload, model_name="llama3.1:8b")

    assert ollama_payload["model"] == "llama3.1:8b"
    assert ollama_payload["stream"] is False
    assert "User query: query" in ollama_payload["prompt"]
