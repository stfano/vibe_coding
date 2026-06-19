from django.contrib import admin

from apps.evaluation.models import EvaluationCase, EvaluationDataset, EvaluationResult, EvaluationRun


class EvaluationCaseInline(admin.TabularInline):
    model = EvaluationCase
    extra = 0
    fields = ("case_key", "expected_source_status", "expected_llm_executed", "is_active")
    show_change_link = True


@admin.register(EvaluationDataset)
class EvaluationDatasetAdmin(admin.ModelAdmin):
    list_display = ("name", "version", "is_active", "updated_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "version", "description")
    readonly_fields = ("created_at", "updated_at")
    inlines = (EvaluationCaseInline,)


@admin.register(EvaluationCase)
class EvaluationCaseAdmin(admin.ModelAdmin):
    list_display = ("case_key", "dataset", "expected_source_status", "expected_llm_executed", "is_active")
    list_filter = ("dataset", "expected_source_status", "expected_llm_executed", "is_active", "created_at")
    search_fields = ("case_key", "query", "source", "department_code")
    readonly_fields = ("created_at", "updated_at")


class EvaluationResultInline(admin.TabularInline):
    model = EvaluationResult
    extra = 0
    fields = ("case", "status", "source_status", "llm_executed", "model_name", "prompt_version")
    readonly_fields = fields
    show_change_link = True


@admin.register(EvaluationRun)
class EvaluationRunAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "dataset",
        "status",
        "llm_provider",
        "model_name",
        "passed_cases",
        "failed_cases",
        "skipped_cases",
    )
    list_filter = ("dataset", "status", "llm_provider", "model_name", "created_at")
    search_fields = ("dataset__name", "model_name", "prompt_version", "error_summary")
    readonly_fields = ("created_at", "updated_at", "finished_at")
    inlines = (EvaluationResultInline,)


@admin.register(EvaluationResult)
class EvaluationResultAdmin(admin.ModelAdmin):
    list_display = ("created_at", "run", "case", "status", "source_status", "llm_executed")
    list_filter = ("run__dataset", "status", "source_status", "llm_executed", "created_at")
    search_fields = ("case__case_key", "case__query", "model_name", "prompt_version", "error_summary")
    readonly_fields = ("created_at", "updated_at")
