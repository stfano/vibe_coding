from __future__ import annotations

import hashlib
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from django.db import close_old_connections
from django.utils import timezone


HIDOC_BASE_URL = "https://www.hidoc.co.kr"
HIDOC_ROBOTS_URL = "https://src.hidoc.co.kr/robots.txt"
DEFAULT_USER_AGENT = "DoctorChatQnaIngestion/0.1"


@dataclass(frozen=True)
class Department:
    code: str
    label: str


@dataclass(frozen=True)
class Pagination:
    max_page: int
    next_page: int | None


@dataclass(frozen=True)
class ListEntry:
    page_number: int
    department: str
    department_code: str
    question_id: str
    question_title: str
    detail_url: str
    answerer_name: str
    answerer_title: str
    answerer_external_id: str
    answerer_profile_url: str
    answerer_organization: str
    answer_created_date: date | None
    answer_preview: str
    list_order: int


@dataclass(frozen=True)
class DetailAnswer:
    answer_id: str
    answer_body: str
    answerer_name: str
    answerer_title: str
    answerer_external_id: str
    answerer_profile_url: str
    answerer_organization: str
    answer_created_date: date | None
    agree_count: int = 0
    recommend_count: int = 0
    asker_thanks: str = ""


@dataclass(frozen=True)
class DetailPage:
    question_id: str
    source_url: str
    question_title: str
    question_body: str
    question_created_date: date | None
    tags: list[str]
    answers: list[DetailAnswer]


@dataclass
class IngestionStats:
    processed_records: int = 0
    inserted_records: int = 0
    updated_records: int = 0
    skipped_records: int = 0
    failed_records: int = 0
    failed_pages: int = 0
    processed_pages: int = 0
    total_pages: int | None = None


@dataclass(frozen=True)
class PageResult:
    page_number: int
    records: list[dict[str, Any]] = field(default_factory=list)
    failed: bool = False
    error: str = ""


KNOWN_DEPARTMENTS: dict[str, Department] = {
    "PF000": Department("PF000", "가정의학과"),
    "PD000": Department("PD000", "소아청소년과"),
}

DEPARTMENT_ALIASES: dict[str, Department] = {
    "소아과": Department("PD000", "소아청소년과"),
    "소아청소년과": Department("PD000", "소아청소년과"),
    "pediatrics": Department("PD000", "소아청소년과"),
}


class HidocFetchError(RuntimeError):
    pass


class RobotsBlockedError(RuntimeError):
    pass


class ProgressLogger:
    def __init__(self, log_path: str | Path):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def info(self, event: str, **fields: Any) -> None:
        self._write("INFO", event, fields)

    def warning(self, event: str, **fields: Any) -> None:
        self._write("WARNING", event, fields)

    def error(self, event: str, **fields: Any) -> None:
        self._write("ERROR", event, fields)

    def _write(self, level: str, event: str, fields: dict[str, Any]) -> None:
        timestamp = timezone.now().isoformat()
        parts = [timestamp, f"level={level}", f"event={event}"]

        for key in ("mode", "department", "department_code", "worker_id"):
            value = fields.get(key)
            if value not in (None, ""):
                parts.append(f"{key}={value}")

        current_page = fields.get("current_page")
        total_pages = fields.get("total_pages")
        if current_page is not None:
            parts.append(f"page={current_page}/{total_pages or 'unknown'}")

        processed_records = fields.get("processed_records")
        target_records = fields.get("target_records")
        if processed_records is not None:
            parts.append(f"records_collected={processed_records}/{target_records or 'all'}")

        for key in (
            "inserted",
            "updated",
            "skipped",
            "failed_records",
            "failed_pages",
            "message",
            "error",
        ):
            value = fields.get(key)
            if value not in (None, ""):
                parts.append(f"{key}={value}")

        with self._lock:
            with self.log_path.open("a", encoding="utf-8", buffering=1) as file:
                file.write(" ".join(str(part) for part in parts) + "\n")


class HidocClient:
    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 15.0,
        request_delay: float = 0.5,
        retries: int = 3,
        backoff_seconds: float = 1.0,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.request_delay = max(0.0, request_delay)
        self.retries = max(1, retries)
        self.backoff_seconds = max(0.0, backoff_seconds)
        self._rate_lock = threading.Lock()
        self._last_request_at = 0.0

    def fetch_text(self, url: str) -> str:
        target_url = urljoin(HIDOC_BASE_URL, url)
        last_error: Exception | None = None

        for attempt in range(1, self.retries + 1):
            try:
                self._wait_for_rate_limit()
                request = Request(target_url, headers={"User-Agent": self.user_agent})
                with urlopen(request, timeout=self.timeout) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    return response.read().decode(charset, errors="replace")
            except (HTTPError, URLError, TimeoutError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(self.backoff_seconds * attempt)

        raise HidocFetchError(f"failed to fetch {target_url}: {last_error}") from last_error

    def _wait_for_rate_limit(self) -> None:
        if self.request_delay <= 0:
            return
        with self._rate_lock:
            elapsed = time.monotonic() - self._last_request_at
            wait_seconds = self.request_delay - elapsed
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            self._last_request_at = time.monotonic()


def ensure_robots_allowed(client: HidocClient, target_url: str) -> None:
    robots_text = client.fetch_text(HIDOC_ROBOTS_URL)
    parser = RobotFileParser()
    parser.parse(robots_text.splitlines())
    if not parser.can_fetch(client.user_agent, target_url):
        raise RobotsBlockedError(f"robots.txt disallows fetching {target_url}")


def resolve_department(value: str) -> Department:
    normalized = value.strip()
    if not normalized:
        raise ValueError("department must not be empty")
    if normalized in KNOWN_DEPARTMENTS:
        return KNOWN_DEPARTMENTS[normalized]
    alias = DEPARTMENT_ALIASES.get(normalized) or DEPARTMENT_ALIASES.get(normalized.lower())
    if alias:
        return alias
    return Department(normalized, normalized)


def build_list_url(department_code: str, page_number: int = 1) -> str:
    return f"{HIDOC_BASE_URL}/healthqna/part/list?code={department_code}&page={page_number}"


def build_detail_url(question_id: str) -> str:
    return f"{HIDOC_BASE_URL}/healthqna/view/{question_id}"


def parse_department_links(html: str) -> dict[str, Department]:
    soup = BeautifulSoup(html, "html.parser")
    departments: dict[str, Department] = {}
    for link in soup.select(".health_consult_clinic a[href*='code=']"):
        href = link.get("href", "")
        match = re.search(r"code=([A-Z0-9]+)", href)
        label_node = link.select_one(".txt_clinic")
        if not match or label_node is None:
            continue
        code = match.group(1)
        label = _clean_text(label_node.get_text(" ", strip=True))
        if code and label:
            departments[code] = Department(code, label)
    return departments


def parse_pagination(html: str) -> Pagination:
    soup = BeautifulSoup(html, "html.parser")
    page_numbers = [1]
    next_page: int | None = None

    for link in soup.select(".paging_type1 a[href*='page=']"):
        href = link.get("href", "")
        page = _extract_page_number(href)
        if page:
            page_numbers.append(page)
            classes = set(link.get("class", []))
            if "btn_next" in classes:
                next_page = page

    return Pagination(max_page=max(page_numbers), next_page=next_page)


def parse_list_page(
    html: str,
    *,
    page_number: int,
    department: str,
    department_code: str,
) -> list[ListEntry]:
    soup = BeautifulSoup(html, "html.parser")
    entries: list[ListEntry] = []

    for order, card in enumerate(soup.select(".qna_main"), start=1):
        title_link = card.select_one(".main_head a[href*='view/']")
        if title_link is None:
            continue

        detail_href = title_link.get("href", "")
        question_id = _extract_question_id(detail_href)
        if not question_id:
            continue

        doctor_link = card.select_one(".doctor_info a.link_doctor")
        answerer_name, answerer_title = _split_name_title(_node_text(doctor_link))
        profile_url = _absolute_url(doctor_link.get("href", "") if doctor_link else "")

        entries.append(
            ListEntry(
                page_number=page_number,
                department=department,
                department_code=department_code,
                question_id=question_id,
                question_title=_node_text(card.select_one(".tit_qna")),
                detail_url=build_detail_url(question_id),
                answerer_name=answerer_name,
                answerer_title=answerer_title,
                answerer_external_id=_extract_member_id(profile_url),
                answerer_profile_url=profile_url,
                answerer_organization=_node_text(card.select_one(".doctor_info .txt_clinic")),
                answer_created_date=parse_hidoc_date(_node_text(card.select_one(".txt_time"))),
                answer_preview=_node_text(card.select_one(".main_body .desc")),
                list_order=order,
            )
        )

    return entries


def parse_detail_page(html: str, *, question_id: str, source_url: str) -> DetailPage:
    soup = BeautifulSoup(html, "html.parser")
    question = soup.select_one(".view_question")
    title = _node_text(question.select_one(".tit") if question else None)
    question_body = _node_text(question.select_one(".desc") if question else None)
    question_date = parse_hidoc_date(_node_text(question.select_one(".user_info .txt_time") if question else None))
    tags = [_node_text(tag) for tag in soup.select(".view_question .txt_tag .tag_desc a")]

    answers: list[DetailAnswer] = []
    for answer in soup.select(".hidoc_answer"):
        doctor_link = answer.select_one(".doctor_clinic a.link_doctor")
        answerer_name, answerer_title = _split_name_title(_node_text(doctor_link))
        profile_url = _absolute_url(doctor_link.get("href", "") if doctor_link else "")
        hidden_uid = answer.select_one(".hiddenRegMemberUid")
        answer_id_node = answer.select_one("input.cid")
        body_node = answer.select_one(".answer_body .cont > .desc")

        answers.append(
            DetailAnswer(
                answer_id=(answer_id_node.get("value", "").strip() if answer_id_node else ""),
                answer_body=_node_text(body_node),
                answerer_name=answerer_name,
                answerer_title=answerer_title,
                answerer_external_id=(
                    hidden_uid.get("value", "").strip() if hidden_uid else _extract_member_id(profile_url)
                ),
                answerer_profile_url=profile_url,
                answerer_organization=_node_text(answer.select_one(".doctor_clinic .txt_clinic")),
                answer_created_date=parse_hidoc_date(_node_text(answer.select_one(".answer_head .txt_time"))),
                agree_count=_extract_recommendation_count(answer, "동의한 전문가"),
                recommend_count=_extract_recommendation_count(answer, "추천한 사용자"),
                asker_thanks=_node_text(answer.select_one(".message .desc")),
            )
        )

    return DetailPage(
        question_id=question_id,
        source_url=source_url,
        question_title=title,
        question_body=question_body,
        question_created_date=question_date,
        tags=[tag for tag in tags if tag],
        answers=answers,
    )


def build_record_payloads(
    entries: list[ListEntry],
    detail_pages: dict[str, DetailPage],
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for entry in entries:
        detail = detail_pages.get(entry.question_id)
        if detail is None:
            continue

        answer = _match_answer(entry, detail)
        answer_body = answer.answer_body if answer else entry.answer_preview
        source_answer_id = answer.answer_id if answer else ""
        fallback_suffix = hashlib.sha256(
            f"{entry.answerer_external_id}:{answer_body}".encode("utf-8")
        ).hexdigest()[:12]
        external_id = f"hidoc:{entry.question_id}:{source_answer_id or fallback_suffix}"
        content_hash = build_content_hash(
            "hidoc",
            entry.question_id,
            source_answer_id,
            detail.question_title or entry.question_title,
            detail.question_body,
            answer_body,
        )

        payloads.append(
            {
                "source": "hidoc",
                "external_id": external_id,
                "content_hash": content_hash,
                "department": entry.department,
                "source_department_code": entry.department_code,
                "source_question_id": entry.question_id,
                "source_answer_id": source_answer_id,
                "source_url": detail.source_url,
                "list_page": entry.page_number,
                "question_title": detail.question_title or entry.question_title,
                "question_body": detail.question_body,
                "answer_body": answer_body,
                "question_created_date": detail.question_created_date,
                "answer_created_date": (
                    entry.answer_created_date
                    or (answer.answer_created_date if answer else None)
                ),
                "answerer_name": answer.answerer_name if answer else entry.answerer_name,
                "answerer_title": answer.answerer_title if answer else entry.answerer_title,
                "answerer_external_id": (
                    answer.answerer_external_id if answer else entry.answerer_external_id
                ),
                "answerer_organization": (
                    answer.answerer_organization if answer else entry.answerer_organization
                ),
                "tags": detail.tags,
                "raw_metadata": {
                    "answerer_profile_url": (
                        answer.answerer_profile_url if answer else entry.answerer_profile_url
                    ),
                    "answer_preview": entry.answer_preview,
                    "agree_count": answer.agree_count if answer else 0,
                    "recommend_count": answer.recommend_count if answer else 0,
                    "asker_thanks": answer.asker_thanks if answer else "",
                    "list_order": entry.list_order,
                },
                "collected_at": timezone.now(),
            }
        )

    return payloads


def build_content_hash(
    source: str,
    question_id: str,
    answer_id: str,
    question_title: str,
    question_body: str,
    answer_body: str,
) -> str:
    normalized = "\n".join(
        _normalize_for_hash(value)
        for value in (
            source,
            question_id,
            answer_id,
            question_title,
            question_body,
            answer_body,
        )
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def upsert_qna_record(payload: dict[str, Any]) -> tuple[bool, Any]:
    from apps.knowledge.models import ExternalQnaRecord

    defaults = {key: value for key, value in payload.items() if key != "external_id"}
    record, created = ExternalQnaRecord.objects.update_or_create(
        external_id=payload["external_id"],
        defaults=defaults,
    )
    return created, record


class HidocIngestionRunner:
    def __init__(
        self,
        *,
        mode: str,
        departments: list[Department],
        limit: int | None,
        workers: int,
        log_path: str | Path,
        dry_run: bool = False,
        max_pages: int | None = None,
        discover_total_pages: bool = True,
        check_robots: bool = True,
        client: HidocClient | None = None,
        upsert_retries: int = 3,
    ):
        self.mode = mode
        self.departments = departments
        self.limit = limit
        self.workers = max(1, workers)
        self.logger = ProgressLogger(log_path)
        self.dry_run = dry_run
        self.max_pages = max_pages
        self.discover_total_pages = discover_total_pages
        self.check_robots = check_robots
        self.client = client or HidocClient()
        self.upsert_retries = max(1, upsert_retries)
        self.stats = IngestionStats()

    def run(self) -> IngestionStats:
        self.logger.info(
            "run_start",
            mode=self.mode,
            department=",".join(department.label for department in self.departments),
            target_records=self.limit,
            processed_records=0,
            inserted=0,
            updated=0,
            skipped=0,
            failed_records=0,
            failed_pages=0,
            message=f"workers={self.workers} dry_run={self.dry_run}",
        )

        if self.check_robots:
            ensure_robots_allowed(self.client, build_list_url("PD000", 1))

        for department in self.departments:
            self._run_department(department)
            if self._limit_reached():
                break

        self.logger.info(
            "run_complete",
            mode=self.mode,
            department=",".join(department.label for department in self.departments),
            total_pages=self.stats.total_pages,
            processed_records=self.stats.processed_records,
            target_records=self.limit,
            inserted=self.stats.inserted_records,
            updated=self.stats.updated_records,
            skipped=self.stats.skipped_records,
            failed_records=self.stats.failed_records,
            failed_pages=self.stats.failed_pages,
        )
        return self.stats

    def _run_department(self, department: Department) -> None:
        total_pages = self._get_total_pages(department)
        self.stats.total_pages = total_pages
        page_stop = total_pages
        if self.max_pages is not None:
            page_stop = min(page_stop, self.max_pages)

        self.logger.info(
            "department_start",
            mode=self.mode,
            department=department.label,
            department_code=department.code,
            total_pages=total_pages,
            processed_records=self.stats.processed_records,
            target_records=self.limit,
            inserted=self.stats.inserted_records,
            updated=self.stats.updated_records,
            failed_pages=self.stats.failed_pages,
        )

        for start_page in range(1, page_stop + 1, self.workers):
            if self._limit_reached():
                break
            end_page = min(start_page + self.workers - 1, page_stop)
            page_numbers = list(range(start_page, end_page + 1))
            results = self._collect_pages_parallel(department, page_numbers, total_pages)

            for result in sorted(results, key=lambda item: item.page_number):
                if result.failed:
                    self.stats.failed_pages += 1
                    self.logger.error(
                        "page_failed",
                        mode=self.mode,
                        department=department.label,
                        department_code=department.code,
                        current_page=result.page_number,
                        total_pages=total_pages,
                        processed_records=self.stats.processed_records,
                        target_records=self.limit,
                        inserted=self.stats.inserted_records,
                        updated=self.stats.updated_records,
                        failed_pages=self.stats.failed_pages,
                        error=result.error,
                    )
                    continue
                self._persist_page_records(department, result, total_pages)
                if self._limit_reached():
                    break

    def _get_total_pages(self, department: Department) -> int:
        if not self.discover_total_pages:
            if self.max_pages is None:
                raise ValueError("--max-pages is required when total discovery is disabled")
            return self.max_pages

        max_seen = 1
        current_page = 1
        visited: set[int] = set()

        while current_page not in visited:
            visited.add(current_page)
            html = self.client.fetch_text(build_list_url(department.code, current_page))
            pagination = parse_pagination(html)
            max_seen = max(max_seen, pagination.max_page)
            self.logger.info(
                "page_discovery",
                mode=self.mode,
                department=department.label,
                department_code=department.code,
                current_page=current_page,
                total_pages=max_seen,
                processed_records=self.stats.processed_records,
                target_records=self.limit,
                inserted=self.stats.inserted_records,
                updated=self.stats.updated_records,
                failed_pages=self.stats.failed_pages,
            )
            if self.max_pages is not None and max_seen >= self.max_pages:
                return self.max_pages
            if pagination.next_page is None:
                break
            current_page = pagination.next_page

        return max_seen

    def _collect_pages_parallel(
        self,
        department: Department,
        page_numbers: list[int],
        total_pages: int,
    ) -> list[PageResult]:
        results: list[PageResult] = []
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {}
            for index, page_number in enumerate(page_numbers, start=1):
                worker_id = f"worker-{index}"
                self.logger.info(
                    "page_start",
                    mode=self.mode,
                    department=department.label,
                    department_code=department.code,
                    worker_id=worker_id,
                    current_page=page_number,
                    total_pages=total_pages,
                    processed_records=self.stats.processed_records,
                    target_records=self.limit,
                    inserted=self.stats.inserted_records,
                    updated=self.stats.updated_records,
                    failed_pages=self.stats.failed_pages,
                )
                futures[
                    executor.submit(self._collect_page_records, department, page_number)
                ] = (page_number, worker_id)

            for future in as_completed(futures):
                page_number, worker_id = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001 - log and continue page failures.
                    result = PageResult(page_number=page_number, failed=True, error=str(exc))
                results.append(result)
                self.logger.info(
                    "page_fetched",
                    mode=self.mode,
                    department=department.label,
                    department_code=department.code,
                    worker_id=worker_id,
                    current_page=page_number,
                    total_pages=total_pages,
                    processed_records=self.stats.processed_records,
                    target_records=self.limit,
                    inserted=self.stats.inserted_records,
                    updated=self.stats.updated_records,
                    failed_pages=self.stats.failed_pages,
                    message=f"records={len(result.records)} failed={result.failed}",
                    error=result.error,
                )
        return results

    def _collect_page_records(self, department: Department, page_number: int) -> PageResult:
        list_html = self.client.fetch_text(build_list_url(department.code, page_number))
        entries = parse_list_page(
            list_html,
            page_number=page_number,
            department=department.label,
            department_code=department.code,
        )
        details: dict[str, DetailPage] = {}
        for question_id in sorted({entry.question_id for entry in entries}):
            url = build_detail_url(question_id)
            details[question_id] = parse_detail_page(
                self.client.fetch_text(url),
                question_id=question_id,
                source_url=url,
            )
        return PageResult(
            page_number=page_number,
            records=build_record_payloads(entries, details),
        )

    def _persist_page_records(
        self,
        department: Department,
        result: PageResult,
        total_pages: int,
    ) -> None:
        for index, payload in enumerate(result.records):
            if self._limit_reached():
                self.stats.skipped_records += len(result.records) - index
                break

            if self.dry_run:
                created = True
            else:
                created, _record = self._upsert_with_retry(payload)

            self.stats.processed_records += 1
            if created:
                self.stats.inserted_records += 1
            else:
                self.stats.updated_records += 1

        self.stats.processed_pages += 1
        self.logger.info(
            "page_complete",
            mode=self.mode,
            department=department.label,
            department_code=department.code,
            current_page=result.page_number,
            total_pages=total_pages,
            processed_records=self.stats.processed_records,
            target_records=self.limit,
            inserted=self.stats.inserted_records,
            updated=self.stats.updated_records,
            skipped=self.stats.skipped_records,
            failed_records=self.stats.failed_records,
            failed_pages=self.stats.failed_pages,
        )

    def _upsert_with_retry(self, payload: dict[str, Any]) -> tuple[bool, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self.upsert_retries + 1):
            try:
                close_old_connections()
                return upsert_qna_record(payload)
            except Exception as exc:  # noqa: BLE001 - transient DB errors are retried.
                last_error = exc
                close_old_connections()
                if attempt < self.upsert_retries:
                    time.sleep(attempt)
        self.stats.failed_records += 1
        raise RuntimeError(f"failed to upsert {payload.get('external_id')}: {last_error}") from last_error

    def _limit_reached(self) -> bool:
        return self.limit is not None and self.stats.processed_records >= self.limit


def discover_departments(client: HidocClient) -> list[Department]:
    html = client.fetch_text(f"{HIDOC_BASE_URL}/healthqna/part/list")
    departments = parse_department_links(html)
    return list(departments.values())


def _match_answer(entry: ListEntry, detail: DetailPage) -> DetailAnswer | None:
    if not detail.answers:
        return None
    for answer in detail.answers:
        if entry.answerer_external_id and answer.answerer_external_id == entry.answerer_external_id:
            return answer
    for answer in detail.answers:
        if entry.answerer_name and answer.answerer_name == entry.answerer_name:
            return answer
    index = max(entry.list_order - 1, 0)
    return detail.answers[index] if index < len(detail.answers) else detail.answers[0]


def parse_hidoc_date(value: str | None) -> date | None:
    if not value:
        return None
    match = re.search(r"(\d{4})[.](\d{1,2})[.](\d{1,2})", value)
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    return date(year, month, day)


def _extract_page_number(href: str) -> int | None:
    match = re.search(r"[?&]page=(\d+)", href)
    return int(match.group(1)) if match else None


def _extract_question_id(value: str) -> str:
    match = re.search(r"(C\d+)", value)
    return match.group(1) if match else ""


def _extract_member_id(value: str) -> str:
    match = re.search(r"(U\d+)", value)
    return match.group(1) if match else ""


def _extract_recommendation_count(answer: Any, label: str) -> int:
    for row in answer.select(".recomm_count dl"):
        if label in _node_text(row.select_one("dt")):
            match = re.search(r"\d+", _node_text(row.select_one("dd")))
            return int(match.group(0)) if match else 0
    return 0


def _split_name_title(value: str) -> tuple[str, str]:
    cleaned = value.replace("답변입니다.", "").strip()
    bracket_match = re.match(r"(.+?)\[(.+?)\]$", cleaned)
    if bracket_match:
        return _clean_text(bracket_match.group(1)), _clean_text(bracket_match.group(2))
    parts = cleaned.split()
    if len(parts) >= 2 and parts[-1] in {"전문의", "한의사", "의사", "약사", "영양사", "운동전문가"}:
        return _clean_text(" ".join(parts[:-1])), _clean_text(parts[-1])
    return _clean_text(cleaned), ""


def _node_text(node: Any) -> str:
    if node is None:
        return ""
    return _clean_text(node.get_text("\n", strip=True))


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _absolute_url(value: str) -> str:
    return urljoin(HIDOC_BASE_URL, value) if value else ""


def _normalize_for_hash(value: str) -> str:
    return _clean_text(value).lower()
