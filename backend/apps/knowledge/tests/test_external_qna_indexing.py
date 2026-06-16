from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.knowledge.indexing import ExternalQnaIndexer, chunk_external_qna
from apps.knowledge.management.commands.index_external_qna import Command as IndexCommand
from apps.knowledge.models import (
    ExternalQnaRecord,
    IndexJob,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSource,
)
from apps.rag.embeddings import DeterministicEmbeddingAdapter


@pytest.fixture
def external_qna_record() -> ExternalQnaRecord:
    return ExternalQnaRecord.objects.create(
        source="hidoc",
        external_id="hidoc:C0001:A0001",
        content_hash="hash-1",
        department="소아청소년과",
        source_department_code="PD000",
        source_question_id="C0001",
        source_answer_id="A0001",
        source_url="https://www.hidoc.co.kr/healthqna/view/C0001",
        list_page=1,
        question_title="아기 고환에 물집이 생겨요",
        question_body="아기띠 후 고환에 물집처럼 보이는 증상이 생겼다가 사라집니다.",
        answer_body="압박으로 인한 일시 변화일 수 있으나 소아청소년과 진료를 권합니다.",
        answerer_name="김경남",
        answerer_title="전문의",
        answerer_external_id="U0001",
        answerer_organization="가톨릭대학교 성빈센트병원",
        tags=["영유아", "소아청소년과"],
        raw_metadata={"agree_count": 1},
        collected_at=timezone.now(),
    )


@pytest.mark.django_db
def test_chunk_external_qna_contains_citation_metadata(external_qna_record):
    chunks = chunk_external_qna(external_qna_record, max_chars=160)

    assert chunks
    assert chunks[0].chunk_index == 0
    assert "질문:" in chunks[0].text
    assert "답변:" in chunks[0].text
    assert chunks[0].citation_metadata == {
        "source": "hidoc",
        "source_url": "https://www.hidoc.co.kr/healthqna/view/C0001",
        "external_question_id": "C0001",
        "external_answer_id": "A0001",
        "title": "아기 고환에 물집이 생겨요",
        "department": "소아청소년과",
        "department_code": "PD000",
        "chunk_index": 0,
        "source_record_id": external_qna_record.id,
    }


@pytest.mark.django_db
def test_indexer_creates_source_document_chunks_and_job(external_qna_record):
    adapter = DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding")
    result = ExternalQnaIndexer(embedding_adapter=adapter, chunk_chars=240).index_records(
        ExternalQnaRecord.objects.filter(pk=external_qna_record.pk)
    )

    assert result.processed_records == 1
    assert result.indexed_chunks == 1
    assert KnowledgeSource.objects.get(key="hidoc").display_name == "HiDoc"
    document = KnowledgeDocument.objects.get(source_external_id="hidoc:C0001:A0001")
    assert document.external_qna_record == external_qna_record
    assert document.department == "소아청소년과"
    chunk = KnowledgeChunk.objects.get(document=document)
    assert chunk.embedding_dimensions == 8
    assert chunk.embedding_model == "test-embedding"
    assert len(chunk.embedding) == 8
    assert chunk.embedding_vector.startswith("[")
    assert chunk.citation_metadata["external_question_id"] == "C0001"
    assert IndexJob.objects.latest("created_at").status == IndexJob.Status.SUCCEEDED


@pytest.mark.django_db
def test_indexer_is_idempotent_and_does_not_duplicate_chunks(external_qna_record):
    adapter = DeterministicEmbeddingAdapter(dimensions=8, model_name="test-embedding")
    indexer = ExternalQnaIndexer(embedding_adapter=adapter, chunk_chars=240)

    first = indexer.index_records(ExternalQnaRecord.objects.filter(pk=external_qna_record.pk))
    second = indexer.index_records(ExternalQnaRecord.objects.filter(pk=external_qna_record.pk))

    assert first.indexed_chunks == 1
    assert second.indexed_chunks == 1
    assert KnowledgeDocument.objects.count() == 1
    assert KnowledgeChunk.objects.count() == 1


def test_index_external_qna_command_arguments_parse():
    parser = IndexCommand().create_parser("manage.py", "index_external_qna")

    options = parser.parse_args(["--source", "hidoc", "--department-code", "PD000", "--limit", "100"])

    assert options.source == "hidoc"
    assert options.department_code == "PD000"
    assert options.limit == 100


@pytest.mark.django_db
def test_index_external_qna_management_command_indexes_records(external_qna_record):
    output = StringIO()

    call_command(
        "index_external_qna",
        source="hidoc",
        department_code="PD000",
        limit=100,
        embedding_provider="deterministic",
        dimensions=8,
        stdout=output,
    )

    assert "processed=1" in output.getvalue()
    assert KnowledgeDocument.objects.count() == 1
    assert KnowledgeChunk.objects.count() == 1
