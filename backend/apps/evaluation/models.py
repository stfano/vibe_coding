from django.db import models

from apps.common.models import TimeStampedModel


class EvaluationDataset(TimeStampedModel):
    name = models.CharField(max_length=120)
    version = models.CharField(max_length=40, default="v1")
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name", "version"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "version"],
                name="evaluation_dataset_name_version_unique",
            )
        ]
        indexes = [models.Index(fields=["name", "version", "is_active"])]

    def __str__(self) -> str:
        return f"{self.name}:{self.version}"


class EvaluationCase(TimeStampedModel):
    dataset = models.ForeignKey(EvaluationDataset, on_delete=models.CASCADE, related_name="cases")
    case_key = models.CharField(max_length=120)
    query = models.TextField()
    source = models.CharField(max_length=80, blank=True)
    department_code = models.CharField(max_length=40, blank=True)
    expected_source_status = models.CharField(max_length=80)
    expected_llm_executed = models.BooleanField(default=False)
    expected_safety_flags = models.JSONField(default=list, blank=True)
    expected_citation_external_ids = models.JSONField(default=list, blank=True)
    expected_source_document_ids = models.JSONField(default=list, blank=True)
    min_top_score = models.FloatField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["dataset_id", "case_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["dataset", "case_key"],
                name="evaluation_case_dataset_key_unique",
            )
        ]
        indexes = [
            models.Index(fields=["expected_source_status", "is_active"]),
            models.Index(fields=["source", "department_code"]),
        ]

    def __str__(self) -> str:
        return f"{self.dataset}:{self.case_key}"


class EvaluationRun(TimeStampedModel):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    dataset = models.ForeignKey(EvaluationDataset, on_delete=models.CASCADE, related_name="runs")
    status = models.CharField(max_length=40, choices=Status.choices, default=Status.RUNNING)
    llm_provider = models.CharField(max_length=80, default="deterministic")
    model_name = models.CharField(max_length=180, blank=True)
    prompt_version = models.CharField(max_length=120, blank=True)
    total_cases = models.PositiveIntegerField(default=0)
    passed_cases = models.PositiveIntegerField(default=0)
    failed_cases = models.PositiveIntegerField(default=0)
    skipped_cases = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    error_summary = models.TextField(blank=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["dataset", "status", "created_at"]),
            models.Index(fields=["llm_provider", "model_name"]),
        ]

    def __str__(self) -> str:
        return f"{self.dataset}:{self.status}:{self.created_at:%Y%m%d%H%M%S}"


class EvaluationResult(TimeStampedModel):
    class Status(models.TextChoices):
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    run = models.ForeignKey(EvaluationRun, on_delete=models.CASCADE, related_name="results")
    case = models.ForeignKey(EvaluationCase, on_delete=models.CASCADE, related_name="results")
    status = models.CharField(max_length=40, choices=Status.choices)
    source_status = models.CharField(max_length=80, blank=True)
    llm_executed = models.BooleanField(default=False)
    model_name = models.CharField(max_length=180, blank=True)
    prompt_version = models.CharField(max_length=120, blank=True)
    safety_flags = models.JSONField(default=list, blank=True)
    citations = models.JSONField(default=list, blank=True)
    retrieved_source_ids = models.JSONField(default=list, blank=True)
    graph_path = models.JSONField(default=list, blank=True)
    graph_metadata = models.JSONField(default=dict, blank=True)
    checks = models.JSONField(default=dict, blank=True)
    answer_preview = models.TextField(blank=True)
    error_summary = models.TextField(blank=True)

    class Meta:
        ordering = ["run_id", "case_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "case"],
                name="evaluation_result_run_case_unique",
            )
        ]
        indexes = [
            models.Index(fields=["status", "source_status", "llm_executed"]),
            models.Index(fields=["created_at", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.run_id}:{self.case.case_key}:{self.status}"
