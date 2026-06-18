from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings

from apps.rag.retrieval import KnowledgeSearchResult


SOURCE_GROUNDED_PROMPT_VERSION = "source_grounded_answer_v1"
DEFAULT_CHAT_LLM_MODEL = "llama3.1:8b"


class LLMError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model_name: str


class ChatLLMAdapter(Protocol):
    model_name: str

    def generate_answer(self, payload: dict[str, Any]) -> LLMResponse:
        ...


def build_source_grounded_prompt_payload(
    *,
    query: str,
    results: list[KnowledgeSearchResult],
) -> dict[str, Any]:
    return {
        "prompt_version": SOURCE_GROUNDED_PROMPT_VERSION,
        "instructions": (
            "Answer only from the provided retrieved contexts. If the contexts are insufficient, "
            "say that the indexed context is insufficient. Include compact citation IDs from the "
            "provided citation metadata. Do not use outside knowledge."
        ),
        "query": query,
        "contexts": [
            {
                "chunk_id": result.chunk_id,
                "document_id": result.document_id,
                "score": result.score,
                "text": result.text or result.text_preview,
                "citation": result.citation,
            }
            for result in results
        ],
    }


def render_source_grounded_prompt(payload: dict[str, Any]) -> str:
    contexts = []
    for index, context in enumerate(payload["contexts"], start=1):
        citation = context.get("citation") or {}
        citation_id = _citation_id(citation, fallback=str(index))
        contexts.append(
            "\n".join(
                [
                    f"[{index}] citation_id={citation_id}",
                    f"score={context.get('score')}",
                    f"text={context.get('text', '')}",
                    f"citation={json.dumps(citation, ensure_ascii=False)}",
                ]
            )
        )
    return "\n\n".join(
        [
            f"Prompt version: {payload['prompt_version']}",
            f"Instructions: {payload['instructions']}",
            f"User query: {payload['query']}",
            "Retrieved contexts:",
            "\n\n".join(contexts),
            "Answer:",
        ]
    )


@dataclass
class DeterministicChatLLMAdapter:
    model_name: str = "deterministic-chat-llm"

    def generate_answer(self, payload: dict[str, Any]) -> LLMResponse:
        if not payload["contexts"]:
            return LLMResponse(
                text="Indexed context is insufficient for this query.",
                model_name=self.model_name,
            )
        citation_ids = [
            _citation_id(context.get("citation") or {}, fallback=str(index))
            for index, context in enumerate(payload["contexts"], start=1)
        ]
        return LLMResponse(
            text=(
                "Indexed context summary: "
                f"{payload['contexts'][0]['text']} "
                f"Citations: {', '.join(citation_ids)}"
            ),
            model_name=self.model_name,
        )


@dataclass
class OllamaChatLLMAdapter:
    base_url: str
    model_name: str
    timeout: float = 30.0

    def generate_answer(self, payload: dict[str, Any]) -> LLMResponse:
        request_payload = build_ollama_generate_payload(payload=payload, model_name=self.model_name)
        request = Request(
            self.base_url.rstrip("/") + "/api/generate",
            data=json.dumps(request_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (OSError, URLError, json.JSONDecodeError) as exc:
            raise LLMError(f"ollama generation request failed: {exc}") from exc

        generated = body.get("response")
        if not isinstance(generated, str) or not generated.strip():
            raise LLMError("ollama response did not include generated text")
        return LLMResponse(text=generated.strip(), model_name=str(body.get("model") or self.model_name))


def build_ollama_generate_payload(*, payload: dict[str, Any], model_name: str) -> dict[str, Any]:
    return {
        "model": model_name,
        "prompt": render_source_grounded_prompt(payload),
        "stream": False,
    }


def get_chat_llm_adapter(
    *,
    provider: str | None = None,
    model_name: str | None = None,
) -> ChatLLMAdapter:
    resolved_provider = provider or getattr(settings, "CHAT_LLM_PROVIDER", "deterministic")
    resolved_model = model_name or getattr(settings, "CHAT_LLM_MODEL", DEFAULT_CHAT_LLM_MODEL)
    if resolved_provider == "ollama":
        return OllamaChatLLMAdapter(
            base_url=getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434"),
            model_name=resolved_model,
            timeout=float(getattr(settings, "CHAT_LLM_TIMEOUT", 30.0)),
        )
    if resolved_provider == "deterministic":
        return DeterministicChatLLMAdapter(model_name=resolved_model)
    raise LLMError(f"unsupported chat LLM provider: {resolved_provider}")


def _citation_id(citation: dict[str, Any], *, fallback: str) -> str:
    question_id = citation.get("external_question_id")
    answer_id = citation.get("external_answer_id")
    if question_id and answer_id:
        return f"{question_id}:{answer_id}"
    if question_id:
        return str(question_id)
    return fallback
