from django.urls import path

from apps.evaluation.views import (
    evaluation_dataset_list,
    evaluation_run_detail,
    evaluation_run_list,
)


urlpatterns = [
    path("datasets/", evaluation_dataset_list, name="evaluation-dataset-list"),
    path("runs/", evaluation_run_list, name="evaluation-run-list"),
    path("runs/<int:run_id>/", evaluation_run_detail, name="evaluation-run-detail"),
]
