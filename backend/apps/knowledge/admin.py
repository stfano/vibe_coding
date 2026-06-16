from django.contrib import admin

from apps.knowledge.models import (
    ExternalQnaRecord,
    IndexJob,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSource,
)


@admin.register(ExternalQnaRecord)
class ExternalQnaRecordAdmin(admin.ModelAdmin):
    list_display = (
        "collected_at",
        "source",
        "department",
        "question_title",
        "answerer_name",
        "list_page",
    )
    list_filter = ("source", "department", "source_department_code", "collected_at")
    search_fields = (
        "external_id",
        "source_question_id",
        "source_answer_id",
        "question_title",
        "answerer_name",
    )
    readonly_fields = ("created_at", "updated_at", "collected_at")


@admin.register(KnowledgeSource)
class KnowledgeSourceAdmin(admin.ModelAdmin):
    list_display = ("key", "display_name", "source_type", "license_status", "is_active", "updated_at")
    list_filter = ("source_type", "license_status", "is_active")
    search_fields = ("key", "display_name", "base_url")
    readonly_fields = ("created_at", "updated_at")


class KnowledgeChunkInline(admin.TabularInline):
    model = KnowledgeChunk
    extra = 0
    fields = ("chunk_index", "embedding_model", "embedding_dimensions", "indexed_at")
    readonly_fields = ("indexed_at",)
    show_change_link = True


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "department", "department_code", "status", "updated_at")
    list_filter = ("source", "department", "department_code", "status", "created_at")
    search_fields = ("source_external_id", "title", "source_url")
    readonly_fields = ("created_at", "updated_at")
    inlines = (KnowledgeChunkInline,)
    actions = ("mark_ready", "mark_needs_review", "mark_disabled")

    @admin.action(description="Mark selected documents as ready")
    def mark_ready(self, request, queryset):
        queryset.update(status=KnowledgeDocument.Status.READY)

    @admin.action(description="Mark selected documents as needs review")
    def mark_needs_review(self, request, queryset):
        queryset.update(status=KnowledgeDocument.Status.NEEDS_REVIEW)

    @admin.action(description="Mark selected documents as disabled")
    def mark_disabled(self, request, queryset):
        queryset.update(status=KnowledgeDocument.Status.DISABLED)


@admin.register(KnowledgeChunk)
class KnowledgeChunkAdmin(admin.ModelAdmin):
    list_display = ("document", "chunk_index", "embedding_model", "embedding_dimensions", "indexed_at")
    list_filter = ("embedding_model", "embedding_dimensions", "indexed_at")
    search_fields = ("document__title", "text", "citation_metadata")
    readonly_fields = ("created_at", "updated_at", "indexed_at")


@admin.register(IndexJob)
class IndexJobAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "source_key",
        "department_code",
        "status",
        "processed_records",
        "indexed_chunks",
    )
    list_filter = ("source_key", "department_code", "status", "created_at")
    search_fields = ("source_key", "department_code", "error_summary")
    readonly_fields = ("created_at", "updated_at", "finished_at")
