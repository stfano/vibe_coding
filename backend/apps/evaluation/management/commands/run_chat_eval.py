from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.evaluation.services import run_evaluation_dataset


class Command(BaseCommand):
    help = "Run a chat/RAG evaluation dataset through the existing chat graph."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--dataset", required=True, help="Evaluation dataset name.")
        parser.add_argument("--dataset-version", default="v1", help="Evaluation dataset version.")
        parser.add_argument(
            "--llm-provider",
            default="deterministic",
            choices=("deterministic", "ollama"),
            help="Chat LLM adapter provider.",
        )
        parser.add_argument("--model", default="", help="Optional model name override.")

    def handle(self, *args, **options):
        try:
            run = run_evaluation_dataset(
                dataset_name=options["dataset"],
                version=options["dataset_version"],
                llm_provider=options["llm_provider"],
                model_name=options["model"] or None,
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        result_ids = ",".join(str(result_id) for result_id in run.results.values_list("id", flat=True))
        self.stdout.write(
            " ".join(
                [
                    f"dataset={run.dataset.name}",
                    f"version={run.dataset.version}",
                    f"run_id={run.id}",
                    f"status={run.status}",
                    f"total={run.total_cases}",
                    f"passed={run.passed_cases}",
                    f"failed={run.failed_cases}",
                    f"skipped={run.skipped_cases}",
                    f"model={run.model_name}",
                    f"prompt_version={run.prompt_version}",
                    f"result_ids={result_ids}",
                ]
            )
        )
