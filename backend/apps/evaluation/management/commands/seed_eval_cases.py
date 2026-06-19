from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.evaluation.services import seed_hidoc_smoke_dataset


class Command(BaseCommand):
    help = "Seed a small idempotent chat/RAG evaluation dataset. Does not crawl external sources."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--dataset", required=True, help="Evaluation dataset name.")
        parser.add_argument("--dataset-version", default="v1", help="Evaluation dataset version.")
        parser.add_argument("--source", default="hidoc", help="Knowledge source key.")
        parser.add_argument("--department-code", default="PD000", help="Knowledge department code.")
        parser.add_argument(
            "--promote-one-ready-for-local-smoke",
            action="store_true",
            help="Promote one needs_review document to ready for a local-only smoke dataset.",
        )

    def handle(self, *args, **options):
        summary = seed_hidoc_smoke_dataset(
            dataset_name=options["dataset"],
            version=options["dataset_version"],
            source=options["source"],
            department_code=options["department_code"],
            promote_one_ready_for_local_smoke=options["promote_one_ready_for_local_smoke"],
        )
        self.stdout.write(
            " ".join(
                [
                    f"dataset={summary['dataset']}",
                    f"version={summary['version']}",
                    f"dataset_id={summary['dataset_id']}",
                    f"cases={summary['created_or_updated']}",
                    f"skipped_ready_cases={summary['skipped_ready_cases']}",
                    f"promoted_document_id={summary['promoted_document_id'] or ''}",
                ]
            )
        )
