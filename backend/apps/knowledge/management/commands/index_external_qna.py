from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.indexing import ExternalQnaIndexer, IndexProgressLogger
from apps.knowledge.models import ExternalQnaRecord
from apps.rag.embeddings import get_embedding_adapter


class Command(BaseCommand):
    help = "Convert external Q&A records into knowledge documents and embedded chunks."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--source", default="hidoc", help="External Q&A source key.")
        parser.add_argument("--department-code", default="", help="Optional source department code filter.")
        parser.add_argument("--limit", type=int, default=None, help="Maximum records to index.")
        parser.add_argument(
            "--embedding-provider",
            default=os.environ.get("EMBEDDING_PROVIDER", "deterministic"),
            choices=("deterministic", "http"),
            help="Embedding adapter provider.",
        )
        parser.add_argument(
            "--dimensions",
            type=int,
            default=None,
            help="Embedding dimensions. Defaults to VECTOR_DIMENSIONS.",
        )
        parser.add_argument(
            "--chunk-chars",
            type=int,
            default=int(os.environ.get("INDEXING_CHUNK_CHARS", "1200")),
            help="Maximum characters per chunk.",
        )
        parser.add_argument(
            "--log-file",
            default=os.environ.get("INDEXING_LOG_FILE", str(Path(settings.BASE_DIR).parent / "ingestion.log")),
            help="Append-only indexing progress log path.",
        )

    def handle(self, *args, **options):
        if options["limit"] is not None and options["limit"] <= 0:
            raise CommandError("--limit must be greater than 0")
        if options["chunk_chars"] <= 0:
            raise CommandError("--chunk-chars must be greater than 0")
        if options["dimensions"] is not None and options["dimensions"] <= 0:
            raise CommandError("--dimensions must be greater than 0")

        queryset = ExternalQnaRecord.objects.filter(source=options["source"]).order_by("id")
        if options["department_code"]:
            queryset = queryset.filter(source_department_code=options["department_code"])
        if options["limit"] is not None:
            queryset = queryset[: options["limit"]]

        adapter = get_embedding_adapter(
            provider=options["embedding_provider"],
            dimensions=options["dimensions"],
        )
        result = ExternalQnaIndexer(
            embedding_adapter=adapter,
            chunk_chars=options["chunk_chars"],
            progress_logger=IndexProgressLogger(options["log_file"]),
        ).index_records(
            queryset,
            source_key=options["source"],
            department_code=options["department_code"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                "External Q&A indexing complete: "
                f"job_id={result.job_id} "
                f"processed={result.processed_records} "
                f"chunks={result.indexed_chunks} "
                f"failed={result.failed_records} "
                f"log={options['log_file']}"
            )
        )
