from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def configure_pgvector(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    dimensions = int(getattr(settings, "VECTOR_DIMENSIONS", 1024))
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cursor.execute(
            "ALTER TABLE knowledge_knowledgechunk "
            f"ALTER COLUMN embedding_vector TYPE vector({dimensions}) "
            "USING NULLIF(embedding_vector, '')::vector"
        )


def reverse_pgvector(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE knowledge_knowledgechunk "
            "ALTER COLUMN embedding_vector TYPE text "
            "USING embedding_vector::text"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("knowledge", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="IndexJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("source_key", models.CharField(max_length=80)),
                ("department_code", models.CharField(blank=True, max_length=40)),
                (
                    "status",
                    models.CharField(
                        choices=[("running", "Running"), ("succeeded", "Succeeded"), ("failed", "Failed")],
                        default="running",
                        max_length=40,
                    ),
                ),
                ("total_records", models.PositiveIntegerField(default=0)),
                ("processed_records", models.PositiveIntegerField(default=0)),
                ("indexed_chunks", models.PositiveIntegerField(default=0)),
                ("embedding_model", models.CharField(blank=True, max_length=180)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("error_summary", models.TextField(blank=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["source_key", "department_code", "status"], name="knowledge_i_source__ad2df0_idx"),
                    models.Index(fields=["created_at", "status"], name="knowledge_i_created_39c1f1_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="KnowledgeSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("key", models.CharField(max_length=80, unique=True)),
                ("display_name", models.CharField(max_length=160)),
                (
                    "source_type",
                    models.CharField(
                        choices=[("external_qna", "External Q&A"), ("document", "Document")],
                        default="external_qna",
                        max_length=40,
                    ),
                ),
                ("base_url", models.URLField(blank=True, max_length=600)),
                ("license_status", models.CharField(default="candidate_review", max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "ordering": ["key"],
                "indexes": [
                    models.Index(fields=["source_type", "is_active"], name="knowledge_k_source__db1b5b_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="KnowledgeDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("source_external_id", models.CharField(max_length=180)),
                ("document_type", models.CharField(default="external_qna_answer", max_length=60)),
                ("title", models.CharField(max_length=500)),
                ("department", models.CharField(blank=True, max_length=120)),
                ("department_code", models.CharField(blank=True, max_length=40)),
                ("source_url", models.URLField(max_length=600)),
                ("content_hash", models.CharField(db_index=True, max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[("ready", "Ready"), ("needs_review", "Needs Review"), ("disabled", "Disabled")],
                        default="needs_review",
                        max_length=40,
                    ),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                (
                    "external_qna_record",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="knowledge_documents",
                        to="knowledge.externalqnarecord",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="knowledge.knowledgesource",
                    ),
                ),
            ],
            options={
                "ordering": ["source_id", "source_external_id"],
                "indexes": [
                    models.Index(fields=["department_code", "status"], name="knowledge_k_departm_1f4b36_idx"),
                    models.Index(fields=["content_hash"], name="knowledge_k_content_ad5a56_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("source", "source_external_id"), name="knowledge_document_source_external_unique"),
                ],
            },
        ),
        migrations.CreateModel(
            name="KnowledgeChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("chunk_index", models.PositiveIntegerField()),
                ("text", models.TextField()),
                ("text_hash", models.CharField(db_index=True, max_length=64)),
                ("embedding", models.JSONField(blank=True, default=list)),
                ("embedding_vector", models.TextField(blank=True)),
                ("embedding_model", models.CharField(blank=True, max_length=180)),
                ("embedding_dimensions", models.PositiveIntegerField(default=0)),
                ("citation_metadata", models.JSONField(blank=True, default=dict)),
                ("indexed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chunks",
                        to="knowledge.knowledgedocument",
                    ),
                ),
            ],
            options={
                "ordering": ["document_id", "chunk_index"],
                "indexes": [
                    models.Index(fields=["embedding_model", "embedding_dimensions"], name="knowledge_k_embeddi_b2d0b7_idx"),
                    models.Index(fields=["text_hash"], name="knowledge_k_text_ha_2cc105_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("document", "chunk_index"), name="knowledge_chunk_document_index_unique"),
                ],
            },
        ),
        migrations.RunPython(configure_pgvector, reverse_pgvector),
    ]
