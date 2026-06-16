from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.ingestion.hidoc import (
    DEFAULT_USER_AGENT,
    Department,
    HidocClient,
    HidocIngestionRunner,
    discover_departments,
    resolve_department,
)


class Command(BaseCommand):
    help = "Collect HiDoc Q&A records and upsert them into the configured database."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--mode",
            choices=("sample", "full"),
            default="sample",
            help="Ingestion mode shown in progress logs.",
        )
        parser.add_argument(
            "--department",
            action="append",
            default=[],
            help="Department label or alias, for example '소아과'. Can be repeated.",
        )
        parser.add_argument(
            "--department-code",
            action="append",
            default=[],
            help="HiDoc department code, for example PD000. Can be repeated.",
        )
        parser.add_argument(
            "--all",
            dest="all_departments",
            action="store_true",
            help="Discover and collect all HiDoc department codes under 진료과별 상담.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum answer-level records to upsert. Defaults to 100 in sample mode.",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=int(os.environ.get("INGESTION_WORKERS", "5")),
            help="Number of parallel page workers.",
        )
        parser.add_argument(
            "--request-delay",
            type=float,
            default=float(os.environ.get("HIDOC_REQUEST_DELAY", "0.5")),
            help="Minimum delay in seconds between source-site HTTP requests.",
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=float(os.environ.get("HIDOC_TIMEOUT", "15")),
            help="HTTP request timeout in seconds.",
        )
        parser.add_argument(
            "--retries",
            type=int,
            default=int(os.environ.get("HIDOC_RETRIES", "3")),
            help="Retry count for source fetches and database upserts.",
        )
        parser.add_argument(
            "--log-file",
            default=os.environ.get(
                "INGESTION_LOG_FILE",
                str(Path(settings.BASE_DIR).parent / "ingestion.log"),
            ),
            help="Append-only progress log path.",
        )
        parser.add_argument(
            "--max-pages",
            type=int,
            default=None,
            help="Optional page cap for dry runs or constrained verification.",
        )
        parser.add_argument(
            "--skip-total-discovery",
            action="store_true",
            help="Skip total page discovery. Requires --max-pages.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch and parse records but do not write to the database.",
        )
        parser.add_argument(
            "--no-robots-check",
            action="store_true",
            help="Disable robots.txt check. Use only for local parser tests.",
        )
        parser.add_argument(
            "--user-agent",
            default=os.environ.get("HIDOC_USER_AGENT", DEFAULT_USER_AGENT),
            help="HTTP User-Agent for source requests.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        if options["mode"] == "sample" and limit is None:
            limit = 100
        if limit is not None and limit <= 0:
            raise CommandError("--limit must be greater than 0")
        if options["workers"] <= 0:
            raise CommandError("--workers must be greater than 0")
        if options["skip_total_discovery"] and options["max_pages"] is None:
            raise CommandError("--skip-total-discovery requires --max-pages")

        client = HidocClient(
            user_agent=options["user_agent"],
            timeout=options["timeout"],
            request_delay=options["request_delay"],
            retries=options["retries"],
        )
        departments = self._build_departments(options, client)

        if options["mode"] == "sample" and not options["all_departments"] and not departments:
            departments = [resolve_department("소아과")]

        if not departments:
            raise CommandError("No departments selected. Use --department, --department-code, or --all.")

        runner = HidocIngestionRunner(
            mode=options["mode"],
            departments=departments,
            limit=limit,
            workers=options["workers"],
            log_path=options["log_file"],
            dry_run=options["dry_run"],
            max_pages=options["max_pages"],
            discover_total_pages=not options["skip_total_discovery"],
            check_robots=not options["no_robots_check"],
            client=client,
            upsert_retries=options["retries"],
        )
        stats = runner.run()

        self.stdout.write(
            self.style.SUCCESS(
                "HiDoc ingestion complete: "
                f"processed={stats.processed_records} "
                f"inserted={stats.inserted_records} "
                f"updated={stats.updated_records} "
                f"failed_pages={stats.failed_pages} "
                f"log={options['log_file']}"
            )
        )

    def _build_departments(self, options, client: HidocClient) -> list[Department]:
        departments: list[Department] = []

        if options["all_departments"]:
            departments.extend(discover_departments(client))

        departments.extend(resolve_department(value) for value in options["department"])
        departments.extend(resolve_department(value) for value in options["department_code"])

        deduped: dict[str, Department] = {}
        for department in departments:
            deduped[department.code] = department
        return list(deduped.values())
