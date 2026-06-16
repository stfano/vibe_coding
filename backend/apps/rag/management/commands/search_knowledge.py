from __future__ import annotations

import json
import os

from django.core.management.base import BaseCommand, CommandError

from apps.rag.embeddings import get_embedding_adapter
from apps.rag.retrieval import search_knowledge


class Command(BaseCommand):
    help = "Search embedded knowledge chunks and print citation metadata. Does not call an LLM."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--query", required=True, help="Search query.")
        parser.add_argument("--top-k", type=int, default=5, help="Number of chunks to return.")
        parser.add_argument("--source", default="", help="Optional source filter, for example hidoc.")
        parser.add_argument("--department-code", default="", help="Optional department code filter.")
        parser.add_argument(
            "--embedding-provider",
            default=os.environ.get("EMBEDDING_PROVIDER", "deterministic"),
            choices=("deterministic", "http"),
            help="Embedding adapter provider.",
        )
        parser.add_argument("--dimensions", type=int, default=None, help="Embedding dimensions.")

    def handle(self, *args, **options):
        if options["top_k"] <= 0:
            raise CommandError("--top-k must be greater than 0")
        if options["dimensions"] is not None and options["dimensions"] <= 0:
            raise CommandError("--dimensions must be greater than 0")

        adapter = get_embedding_adapter(
            provider=options["embedding_provider"],
            dimensions=options["dimensions"],
        )
        results = search_knowledge(
            options["query"],
            top_k=options["top_k"],
            embedding_adapter=adapter,
            source=options["source"] or None,
            department_code=options["department_code"] or None,
        )
        if not results:
            self.stdout.write("No knowledge chunks found.")
            return

        for index, result in enumerate(results, start=1):
            self.stdout.write(
                json.dumps(
                    {
                        "rank": index,
                        "score": result.score,
                        "chunk_id": result.chunk_id,
                        "preview": result.text_preview,
                        "citation": result.citation,
                    },
                    ensure_ascii=False,
                )
            )
