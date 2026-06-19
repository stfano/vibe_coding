from __future__ import annotations

import re
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.utils import timezone

from apps.knowledge.models import KnowledgeDocument


PREVIEW_CHARS = 72


class Command(BaseCommand):
    help = "Review and explicitly promote a small set of HiDoc sample documents for smoke evaluation."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--source", default="hidoc")
        parser.add_argument("--department-code", default="PD000")
        parser.add_argument("--limit", type=int, default=3)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--mark-ready", action="store_true")
        parser.add_argument("--mark-needs-review", action="store_true")
        parser.add_argument(
            "--document-id",
            action="append",
            default=[],
            help="Specific document ID to change. May be repeated or comma-separated.",
        )
        parser.add_argument("--confirm", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        source = options["source"]
        department_code = options["department_code"]
        limit = max(1, int(options["limit"]))
        dry_run = bool(options["dry_run"])
        mark_ready = bool(options["mark_ready"])
        mark_needs_review = bool(options["mark_needs_review"])
        confirm = bool(options["confirm"])
        document_ids = _parse_document_ids(options.get("document_id") or [])

        if mark_ready and mark_needs_review:
            raise CommandError("Use only one of --mark-ready or --mark-needs-review.")
        if mark_needs_review and not document_ids:
            raise CommandError("--mark-needs-review requires at least one --document-id.")
        if (mark_ready or mark_needs_review) and not dry_run and not confirm:
            raise CommandError("Changing document status requires --confirm.")

        if mark_ready:
            documents = list(
                _reviewable_queryset(source=source, department_code=department_code)
                .filter(id__in=document_ids)
                .order_by("id")
                if document_ids
                else _reviewable_queryset(source=source, department_code=department_code).order_by("id")[:limit]
            )
            self._write_header(
                mode="mark-ready",
                source=source,
                department_code=department_code,
                dry_run=dry_run,
                requested_ids=document_ids,
            )
            changed = self._change_documents(
                documents=documents,
                target_status=KnowledgeDocument.Status.READY,
                dry_run=dry_run,
                action_key="ready_smoke_review",
            )
            self.stdout.write(
                f"summary changed={changed if not dry_run else 0} "
                f"would_change={changed if dry_run else 0} skipped={len(document_ids) - len(documents) if document_ids else 0}"
            )
            return

        if mark_needs_review:
            documents = list(
                _base_queryset(source=source, department_code=department_code)
                .filter(id__in=document_ids, status=KnowledgeDocument.Status.READY)
                .order_by("id")
            )
            self._write_header(
                mode="mark-needs-review",
                source=source,
                department_code=department_code,
                dry_run=dry_run,
                requested_ids=document_ids,
            )
            changed = self._change_documents(
                documents=documents,
                target_status=KnowledgeDocument.Status.NEEDS_REVIEW,
                dry_run=dry_run,
                action_key="ready_smoke_review_revert",
            )
            self.stdout.write(
                f"summary changed={changed if not dry_run else 0} "
                f"would_change={changed if dry_run else 0} skipped={len(document_ids) - len(documents)}"
            )
            return

        documents = list(
            _reviewable_queryset(source=source, department_code=department_code).order_by("id")[:limit]
        )
        self._write_header(
            mode="dry-run" if dry_run else "review",
            source=source,
            department_code=department_code,
            dry_run=True,
            requested_ids=document_ids,
        )
        if not documents:
            self.stdout.write("no reviewable needs_review documents with chunks found")
            return
        for document in documents:
            self._write_document_summary(document)
        self.stdout.write(f"summary candidates={len(documents)} changed=0")

    def _write_header(
        self,
        *,
        mode: str,
        source: str,
        department_code: str,
        dry_run: bool,
        requested_ids: list[int],
    ) -> None:
        id_text = ",".join(str(document_id) for document_id in requested_ids) if requested_ids else "none"
        self.stdout.write(
            f"prepare_ready_smoke_docs mode={mode} source={source} department_code={department_code} "
            f"dry_run={str(dry_run).lower()} requested_document_ids={id_text}"
        )

    def _change_documents(
        self,
        *,
        documents: list[KnowledgeDocument],
        target_status: str,
        dry_run: bool,
        action_key: str,
    ) -> int:
        changed = 0
        for document in documents:
            self._write_document_summary(document)
            changed += 1
            if dry_run:
                continue
            document.status = target_status
            document.metadata = {
                **document.metadata,
                action_key: {
                    "status": target_status,
                    "updated_at": timezone.now().isoformat(),
                },
            }
            document.save(update_fields=["status", "metadata", "updated_at"])
        return changed

    def _write_document_summary(self, document: KnowledgeDocument) -> None:
        record = document.external_qna_record
        first_chunk = document.chunks.order_by("chunk_index").first()
        preview = _compact_preview(first_chunk.text if first_chunk else "")
        self.stdout.write(
            " ".join(
                [
                    f"document_id={document.id}",
                    f"status={document.status}",
                    f"title={_quote(document.title)}",
                    f"source_url={document.source_url}",
                    f"external_question_id={record.source_question_id if record else ''}",
                    f"external_answer_id={record.source_answer_id if record else ''}",
                    f"chunk_count={getattr(document, 'chunk_count', document.chunks.count())}",
                    f"preview={_quote(preview)}",
                ]
            )
        )


def _base_queryset(*, source: str, department_code: str):
    return (
        KnowledgeDocument.objects.select_related("source", "external_qna_record")
        .annotate(chunk_count=Count("chunks"))
        .filter(
            source__key=source,
            source__is_active=True,
            department_code=department_code,
            chunk_count__gt=0,
            chunks__citation_metadata__external_question_id__isnull=False,
            chunks__citation_metadata__external_answer_id__isnull=False,
        )
        .distinct()
    )


def _reviewable_queryset(*, source: str, department_code: str):
    return _base_queryset(source=source, department_code=department_code).filter(
        status=KnowledgeDocument.Status.NEEDS_REVIEW,
    )


def _parse_document_ids(raw_values: list[str] | tuple[str, ...] | str) -> list[int]:
    if isinstance(raw_values, str):
        values = [raw_values]
    else:
        values = list(raw_values)
    document_ids: list[int] = []
    for value in values:
        for part in str(value).split(","):
            part = part.strip()
            if not part:
                continue
            try:
                document_ids.append(int(part))
            except ValueError as exc:
                raise CommandError(f"Invalid --document-id value: {part}") from exc
    return list(dict.fromkeys(document_ids))


def _compact_preview(text: str) -> str:
    compacted = re.sub(r"\s+", " ", text).strip()
    if len(compacted) <= PREVIEW_CHARS:
        return compacted
    return compacted[:PREVIEW_CHARS].rstrip() + "..."


def _quote(value: str) -> str:
    escaped = value.replace('"', "'")
    return f'"{escaped}"'
