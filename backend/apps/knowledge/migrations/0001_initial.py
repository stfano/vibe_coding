# Generated manually for the external Q&A ingestion slice.

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ExternalQnaRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("source", models.CharField(max_length=80)),
                ("external_id", models.CharField(max_length=180, unique=True)),
                ("content_hash", models.CharField(db_index=True, max_length=64)),
                ("department", models.CharField(max_length=120)),
                ("source_department_code", models.CharField(blank=True, max_length=40)),
                ("source_question_id", models.CharField(max_length=80)),
                ("source_answer_id", models.CharField(blank=True, max_length=80)),
                ("source_url", models.URLField(max_length=600)),
                ("list_page", models.PositiveIntegerField()),
                ("question_title", models.CharField(max_length=500)),
                ("question_body", models.TextField()),
                ("answer_body", models.TextField()),
                ("question_created_date", models.DateField(blank=True, null=True)),
                ("answer_created_date", models.DateField(blank=True, null=True)),
                ("answerer_name", models.CharField(blank=True, max_length=160)),
                ("answerer_title", models.CharField(blank=True, max_length=120)),
                ("answerer_external_id", models.CharField(blank=True, max_length=80)),
                ("answerer_organization", models.CharField(blank=True, max_length=240)),
                ("tags", models.JSONField(blank=True, default=list)),
                ("raw_metadata", models.JSONField(blank=True, default=dict)),
                ("collected_at", models.DateTimeField()),
            ],
            options={
                "ordering": ["-collected_at", "source_question_id", "source_answer_id"],
                "indexes": [
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
                ],
            },
        ),
    ]
