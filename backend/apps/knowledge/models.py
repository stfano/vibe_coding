from django.db import models

from apps.common.models import TimeStampedModel


class ExternalQnaRecord(TimeStampedModel):
    """Answer-level Q&A record collected from an external public source."""

    source = models.CharField(max_length=80)
    external_id = models.CharField(max_length=180, unique=True)
    content_hash = models.CharField(max_length=64, db_index=True)
    department = models.CharField(max_length=120)
    source_department_code = models.CharField(max_length=40, blank=True)
    source_question_id = models.CharField(max_length=80)
    source_answer_id = models.CharField(max_length=80, blank=True)
    source_url = models.URLField(max_length=600)
    list_page = models.PositiveIntegerField()
    question_title = models.CharField(max_length=500)
    question_body = models.TextField()
    answer_body = models.TextField()
    question_created_date = models.DateField(blank=True, null=True)
    answer_created_date = models.DateField(blank=True, null=True)
    answerer_name = models.CharField(max_length=160, blank=True)
    answerer_title = models.CharField(max_length=120, blank=True)
    answerer_external_id = models.CharField(max_length=80, blank=True)
    answerer_organization = models.CharField(max_length=240, blank=True)
    tags = models.JSONField(default=list, blank=True)
    raw_metadata = models.JSONField(default=dict, blank=True)
    collected_at = models.DateTimeField()

    class Meta:
        ordering = ["-collected_at", "source_question_id", "source_answer_id"]
        indexes = [
            models.Index(
                fields=["source", "department", "collected_at"],
                name="knowledge_e_source_bf1539_idx",
            ),
            models.Index(
                fields=["source_question_id", "source_answer_id"],
                name="knowledge_e_source_f5638d_idx",
            ),
            models.Index(
                fields=["source_department_code", "list_page"],
                name="knowledge_e_source_d60d24_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.source}:{self.source_question_id}:{self.source_answer_id or 'answer'}"


class KnowledgeSource(TimeStampedModel):
    class SourceType(models.TextChoices):
        EXTERNAL_QNA = "external_qna", "External Q&A"
        DOCUMENT = "document", "Document"

    key = models.CharField(max_length=80, unique=True)
    display_name = models.CharField(max_length=160)
    source_type = models.CharField(
        max_length=40,
        choices=SourceType.choices,
        default=SourceType.EXTERNAL_QNA,
    )
    base_url = models.URLField(max_length=600, blank=True)
    license_status = models.CharField(max_length=120, default="candidate_review")
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["key"]
        indexes = [models.Index(fields=["source_type", "is_active"])]

    def __str__(self) -> str:
        return self.display_name


class KnowledgeDocument(TimeStampedModel):
    class Status(models.TextChoices):
        READY = "ready", "Ready"
        NEEDS_REVIEW = "needs_review", "Needs Review"
        DISABLED = "disabled", "Disabled"

    source = models.ForeignKey(
        KnowledgeSource,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    external_qna_record = models.ForeignKey(
        ExternalQnaRecord,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="knowledge_documents",
    )
    source_external_id = models.CharField(max_length=180)
    document_type = models.CharField(max_length=60, default="external_qna_answer")
    title = models.CharField(max_length=500)
    department = models.CharField(max_length=120, blank=True)
    department_code = models.CharField(max_length=40, blank=True)
    source_url = models.URLField(max_length=600)
    content_hash = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=40, choices=Status.choices, default=Status.NEEDS_REVIEW)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["source_id", "source_external_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "source_external_id"],
                name="knowledge_document_source_external_unique",
            )
        ]
        indexes = [
            models.Index(fields=["department_code", "status"]),
            models.Index(fields=["content_hash"]),
        ]

    def __str__(self) -> str:
        return self.title


class KnowledgeChunk(TimeStampedModel):
    document = models.ForeignKey(
        KnowledgeDocument,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    chunk_index = models.PositiveIntegerField()
    text = models.TextField()
    text_hash = models.CharField(max_length=64, db_index=True)
    embedding = models.JSONField(default=list, blank=True)
    embedding_vector = models.TextField(blank=True)
    embedding_model = models.CharField(max_length=180, blank=True)
    embedding_dimensions = models.PositiveIntegerField(default=0)
    citation_metadata = models.JSONField(default=dict, blank=True)
    indexed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["document_id", "chunk_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "chunk_index"],
                name="knowledge_chunk_document_index_unique",
            )
        ]
        indexes = [
            models.Index(fields=["embedding_model", "embedding_dimensions"]),
            models.Index(fields=["text_hash"]),
        ]

    def __str__(self) -> str:
        return f"{self.document_id}:{self.chunk_index}"


class IndexJob(TimeStampedModel):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    source_key = models.CharField(max_length=80)
    department_code = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=40, choices=Status.choices, default=Status.RUNNING)
    total_records = models.PositiveIntegerField(default=0)
    processed_records = models.PositiveIntegerField(default=0)
    indexed_chunks = models.PositiveIntegerField(default=0)
    embedding_model = models.CharField(max_length=180, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    error_summary = models.TextField(blank=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["source_key", "department_code", "status"]),
            models.Index(fields=["created_at", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.source_key}:{self.department_code or 'all'}:{self.status}"
