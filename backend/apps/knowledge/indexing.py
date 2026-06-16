from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from django.db import connection
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.knowledge.models import (
    ExternalQnaRecord,
    IndexJob,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSource,
)
from apps.rag.embeddings import EmbeddingAdapter, get_embedding_adapter, vector_to_pgvector


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChunkCandidate:
    chunk_index: int
    text: str
    citation_metadata: dict[str, object]


@dataclass(frozen=True)
class IndexingResult:
    job_id: int
    processed_records: int
    indexed_chunks: int
    failed_records: int = 0


class IndexProgressLogger:
    def __init__(self, log_path: str | Path):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def info(self, event: str, **fields: Any) -> None:
        timestamp = timezone.now().isoformat()
        parts = [timestamp, "level=INFO", f"event={event}"]
        for key in (
            "job_id",
            "source",
            "department_code",
            "processed_records",
            "total_records",
            "indexed_chunks",
            "failed_records",
        ):
            value = fields.get(key)
            if value not in (None, ""):
                parts.append(f"{key}={value}")
        with self.log_path.open("a", encoding="utf-8", buffering=1) as file:
            file.write(" ".join(str(part) for part in parts) + "\n")


def chunk_external_qna(record: ExternalQnaRecord, *, max_chars: int = 1200) -> list[ChunkCandidate]:
    text = _build_external_qna_text(record)
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if not current:
            current = paragraph
            continue
        candidate = f"{current}\n\n{paragraph}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        chunks.extend(_split_long_text(current, max_chars=max_chars))
        current = paragraph

    if current:
        chunks.extend(_split_long_text(current, max_chars=max_chars))

    if not chunks:
        chunks = [_build_external_qna_text(record)]

    return [
        ChunkCandidate(
            chunk_index=index,
            text=chunk,
            citation_metadata=_build_citation_metadata(record, chunk_index=index),
        )
        for index, chunk in enumerate(chunks)
    ]


class ExternalQnaIndexer:
    def __init__(
        self,
        *,
        embedding_adapter: EmbeddingAdapter | None = None,
        chunk_chars: int | None = None,
        logger_: logging.Logger | None = None,
        progress_logger: IndexProgressLogger | None = None,
    ):
        self.embedding_adapter = embedding_adapter or get_embedding_adapter()
        self.chunk_chars = chunk_chars or int(os.environ.get("INDEXING_CHUNK_CHARS", "1200"))
        self.logger = logger_ or logger
        self.progress_logger = progress_logger

    def index_records(
        self,
        records: QuerySet[ExternalQnaRecord] | Iterable[ExternalQnaRecord],
        *,
        source_key: str = "hidoc",
        department_code: str = "",
    ) -> IndexingResult:
        materialized = list(records)
        job = IndexJob.objects.create(
            source_key=source_key,
            department_code=department_code,
            total_records=len(materialized),
            embedding_model=self.embedding_adapter.model_name,
            metadata={"chunk_chars": self.chunk_chars},
        )
        self._log_progress(
            "external_qna_index_started",
            job_id=job.id,
            source=source_key,
            department_code=department_code,
            processed_records=0,
            total_records=len(materialized),
            indexed_chunks=0,
            failed_records=0,
        )
        processed_records = 0
        indexed_chunks = 0
        failed_records = 0

        try:
            source = self._get_or_create_source(source_key)
            for record in materialized:
                try:
                    indexed_chunks += self._index_one_record(source, record)
                    processed_records += 1
                except Exception as exc:
                    failed_records += 1
                    self.logger.warning(
                        "external_qna_index_record_failed",
                        extra={
                            "source": source_key,
                            "department_code": record.source_department_code,
                            "external_id": record.external_id,
                        },
                    )
                    job.error_summary = _append_error(job.error_summary, record.external_id, str(exc))
                job.processed_records = processed_records
                job.indexed_chunks = indexed_chunks
                job.save(update_fields=["processed_records", "indexed_chunks", "error_summary", "updated_at"])
                self._log_progress(
                    "external_qna_index_progress",
                    job_id=job.id,
                    source=source_key,
                    department_code=department_code,
                    processed_records=processed_records,
                    total_records=len(materialized),
                    indexed_chunks=indexed_chunks,
                    failed_records=failed_records,
                )

            job.status = IndexJob.Status.SUCCEEDED if failed_records == 0 else IndexJob.Status.FAILED
            job.finished_at = timezone.now()
            job.metadata = {**job.metadata, "failed_records": failed_records}
            job.save(update_fields=["status", "finished_at", "metadata", "updated_at"])
            self._log_progress(
                "external_qna_index_finished",
                job_id=job.id,
                source=source_key,
                department_code=department_code,
                processed_records=processed_records,
                total_records=len(materialized),
                indexed_chunks=indexed_chunks,
                failed_records=failed_records,
            )
            return IndexingResult(
                job_id=job.id,
                processed_records=processed_records,
                indexed_chunks=indexed_chunks,
                failed_records=failed_records,
            )
        except Exception as exc:
            job.status = IndexJob.Status.FAILED
            job.error_summary = _append_error(job.error_summary, "job", str(exc))
            job.finished_at = timezone.now()
            job.metadata = {**job.metadata, "failed_records": failed_records}
            job.save(update_fields=["status", "error_summary", "finished_at", "metadata", "updated_at"])
            self._log_progress(
                "external_qna_index_failed",
                job_id=job.id,
                source=source_key,
                department_code=department_code,
                processed_records=processed_records,
                total_records=len(materialized),
                indexed_chunks=indexed_chunks,
                failed_records=failed_records,
            )
            raise

    def _get_or_create_source(self, source_key: str) -> KnowledgeSource:
        defaults = {
            "display_name": "HiDoc" if source_key == "hidoc" else source_key,
            "source_type": KnowledgeSource.SourceType.EXTERNAL_QNA,
            "base_url": "https://www.hidoc.co.kr" if source_key == "hidoc" else "",
            "license_status": "candidate_review",
            "metadata": {
                "usage_note": "Third-party public Q&A candidate content; not authoritative clinical guidance.",
            },
        }
        source, _ = KnowledgeSource.objects.update_or_create(key=source_key, defaults=defaults)
        return source

    @transaction.atomic
    def _index_one_record(self, source: KnowledgeSource, record: ExternalQnaRecord) -> int:
        existing_document = KnowledgeDocument.objects.filter(
            source=source,
            source_external_id=record.external_id,
        ).first()
        next_status = _next_document_status(existing_document, record.content_hash)
        document, _ = KnowledgeDocument.objects.update_or_create(
            source=source,
            source_external_id=record.external_id,
            defaults={
                "external_qna_record": record,
                "document_type": "external_qna_answer",
                "title": record.question_title,
                "department": record.department,
                "department_code": record.source_department_code,
                "source_url": record.source_url,
                "content_hash": record.content_hash,
                "status": next_status,
                "metadata": {
                    "source_question_id": record.source_question_id,
                    "source_answer_id": record.source_answer_id,
                    "answerer_name": record.answerer_name,
                    "answerer_title": record.answerer_title,
                    "tags": record.tags,
                    "clinical_authority": False,
                },
            },
        )
        candidates = chunk_external_qna(record, max_chars=self.chunk_chars)
        embeddings = self.embedding_adapter.embed_texts([candidate.text for candidate in candidates])

        document.chunks.all().delete()
        now = timezone.now()
        self._create_chunks(
            document=document,
            candidates=candidates,
            embeddings=embeddings,
            indexed_at=now,
        )
        return len(candidates)

    def _create_chunks(
        self,
        *,
        document: KnowledgeDocument,
        candidates: list[ChunkCandidate],
        embeddings: list[list[float]],
        indexed_at,
    ) -> None:
        if connection.vendor == "postgresql":
            self._create_chunks_postgres(
                document=document,
                candidates=candidates,
                embeddings=embeddings,
                indexed_at=indexed_at,
            )
            return

        KnowledgeChunk.objects.bulk_create(
            [
                KnowledgeChunk(
                    document=document,
                    chunk_index=candidate.chunk_index,
                    text=candidate.text,
                    text_hash=_sha256(candidate.text),
                    embedding=embedding,
                    embedding_vector=vector_to_pgvector(embedding),
                    embedding_model=self.embedding_adapter.model_name,
                    embedding_dimensions=self.embedding_adapter.dimensions,
                    citation_metadata=candidate.citation_metadata,
                    indexed_at=indexed_at,
                )
                for candidate, embedding in zip(candidates, embeddings, strict=True)
            ]
        )

    def _create_chunks_postgres(
        self,
        *,
        document: KnowledgeDocument,
        candidates: list[ChunkCandidate],
        embeddings: list[list[float]],
        indexed_at,
    ) -> None:
        sql = """
            INSERT INTO knowledge_knowledgechunk (
                created_at,
                updated_at,
                document_id,
                chunk_index,
                text,
                text_hash,
                embedding,
                embedding_vector,
                embedding_model,
                embedding_dimensions,
                citation_metadata,
                indexed_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s::jsonb,
                %s::vector,
                %s,
                %s,
                %s::jsonb,
                %s
            )
        """
        rows = [
            (
                indexed_at,
                indexed_at,
                document.id,
                candidate.chunk_index,
                candidate.text,
                _sha256(candidate.text),
                json.dumps(embedding),
                vector_to_pgvector(embedding),
                self.embedding_adapter.model_name,
                self.embedding_adapter.dimensions,
                json.dumps(candidate.citation_metadata, ensure_ascii=False),
                indexed_at,
            )
            for candidate, embedding in zip(candidates, embeddings, strict=True)
        ]
        with connection.cursor() as cursor:
            for row in rows:
                cursor.execute(sql, row)

    def _log_progress(self, event: str, **fields: Any) -> None:
        if self.progress_logger is None:
            return
        self.progress_logger.info(event, **fields)


def _build_external_qna_text(record: ExternalQnaRecord) -> str:
    return "\n\n".join(
        part
        for part in (
            f"제목: {record.question_title}",
            f"질문: {record.question_body}",
            f"답변: {record.answer_body}",
            "주의: 제3자 공개 Q&A 후보 자료이며 임상 판단 근거로 단독 사용하지 않습니다.",
        )
        if part.strip()
    )


def _build_citation_metadata(record: ExternalQnaRecord, *, chunk_index: int) -> dict[str, object]:
    return {
        "source": record.source,
        "source_url": record.source_url,
        "external_question_id": record.source_question_id,
        "external_answer_id": record.source_answer_id,
        "title": record.question_title,
        "department": record.department,
        "department_code": record.source_department_code,
        "chunk_index": chunk_index,
        "source_record_id": record.id,
    }


def _split_long_text(text: str, *, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    return [text[index : index + max_chars] for index in range(0, len(text), max_chars)]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _append_error(existing: str, identifier: str, message: str) -> str:
    entry = f"{identifier}: {message[:240]}"
    return "\n".join(part for part in (existing, entry) if part).strip()[:4000]


def _next_document_status(document: KnowledgeDocument | None, content_hash: str) -> str:
    if document is None:
        return KnowledgeDocument.Status.NEEDS_REVIEW
    if document.status == KnowledgeDocument.Status.DISABLED:
        return KnowledgeDocument.Status.DISABLED
    if document.content_hash != content_hash:
        return KnowledgeDocument.Status.NEEDS_REVIEW
    return document.status
