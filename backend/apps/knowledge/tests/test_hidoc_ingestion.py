from __future__ import annotations

from pathlib import Path

import pytest

from apps.knowledge.ingestion.hidoc import (
    ProgressLogger,
    build_content_hash,
    build_record_payloads,
    parse_department_links,
    parse_detail_page,
    parse_list_page,
    parse_pagination,
    resolve_department,
    upsert_qna_record,
)
from apps.knowledge.models import ExternalQnaRecord
from apps.knowledge.management.commands.ingest_hidoc_qna import Command


LIST_HTML = """
<html>
  <body>
    <div class="health_consult_clinic">
      <a href="?code=PD000" class="ico_link">
        <strong class="part"><span class="txt_clinic">소아청소년과</span></strong>
      </a>
      <a href="?code=PF000" class="ico_link">
        <strong class="part"><span class="txt_clinic">가정의학과</span></strong>
      </a>
    </div>
    <div class="box_type1 qna_main">
      <div class="main_head">
        <a href="view/C0001048103">
          <strong class="tit_qna">아기고환에 물집이 생겨요</strong>
        </a>
      </div>
      <div class="main_body">
        <div class="doctor_info">
          <div class="info_desc">
            <p><a href="/find/doctor/default/U0000218209" class="link_doctor">김경남 전문의</a> 답변입니다.</p>
            <span class="txt_clinic">가톨릭대학교 성빈센트병원</span>
          </div>
          <span class="txt_time">2026.06.08</span>
        </div>
        <a href="view/C0001048103"><p class="desc">안녕하세요<br>아기띠 압박 관련 답변입니다.</p></a>
      </div>
    </div>
    <div class="box_type1 qna_main">
      <div class="main_head">
        <a href="view/C0001048103">
          <strong class="tit_qna">아기고환에 물집이 생겨요</strong>
        </a>
      </div>
      <div class="main_body">
        <div class="doctor_info">
          <div class="info_desc">
            <p><a href="/find/doctor/default/U0000257328" class="link_doctor">김지현 한의사</a> 답변입니다.</p>
            <span class="txt_clinic">마디마디튼튼한의원</span>
          </div>
          <span class="txt_time">2026.06.08</span>
        </div>
        <a href="view/C0001048103"><p class="desc">안녕하세요. 한방과 상담의 답변입니다.</p></a>
      </div>
    </div>
    <div class="paging_type1">
      <a href="/healthqna/part/list?code=PD000&page=2" class="num_page">2</a>
      <a href="/healthqna/part/list?code=PD000&page=3" class="num_page">3</a>
      <a href="/healthqna/part/list?code=PD000&page=11" class="ico_comm btn_next" title="다음">다음</a>
    </div>
  </body>
</html>
"""


DETAIL_HTML = """
<html>
  <body>
    <div class="box_type1 view_question">
      <strong class="tit">아기고환에 물집이 생겨요</strong>
      <div class="user_info"><span class="txt_time">2026.06.08</span></div>
      <div class="txt_tag">SMART TAG :<span class="tag_desc">
        <a href="/healthqna/list?code=HG002">남성생식기</a>,
        <a href="/healthqna/list?code=LBB00">영유아</a>,
        <a href="/healthqna/list?code=PD000">소아청소년과</a>
      </span></div>
      <div class="desc">
        <p>아기띠 하고 내려놓으면 고환에 물집이 생겼다가 잠시 후 사라집니다.<br>문제가 생겼을까요?</p>
      </div>
    </div>
    <div class="box_type1 clear_g answer_tit">
      <strong class="tit_answer">Re : 아기고환에 물집이 생겨요</strong>
    </div>
    <div class="box_type1 hidoc_answer">
      <div class="answer_head">
        <div class="doctor_clinic">
          <a href="/find/doctor/default/U0000218209" class="link_doctor">김경남[전문의]</a>
          <span class="txt_clinic">가톨릭대학교 성빈센트병원</span>
        </div>
        <div class="recomm_count">
          <dl><dt>이 답변에 동의한 전문가</dt><dd class="fc_green">1명</dd></dl>
          <dl><dt>이 답변을 추천한 사용자</dt><dd class="fc_green">2명</dd></dl>
        </div>
        <span class="txt_time"></span>
      </div>
      <div class="answer_body">
        <div class="message"><div class="message_inner"><p class="desc">정말감사드립니다</p></div></div>
        <div class="cont">
          <div class="desc">아기띠 압박으로 인한 일시적인 체액 정체일 가능성이 큽니다.<br>소아과 진료를 받아보세요.</div>
          <form method="post" class="answerForm">
            <input type="hidden" class="cid" value="C0001048127">
            <input type="hidden" class="hiddenRegMemberUid" value="U0000218209">
          </form>
        </div>
      </div>
    </div>
    <div class="box_type1 hidoc_answer">
      <div class="answer_head">
        <div class="doctor_clinic">
          <a href="/find/doctor/default/U0000257328" class="link_doctor">김지현[한의사]</a>
          <span class="txt_clinic">마디마디튼튼한의원</span>
        </div>
      </div>
      <div class="answer_body">
        <div class="cont">
          <div class="desc">음낭수종 또는 소아 탈장 가능성을 확인해야 합니다.</div>
          <form method="post" class="answerForm">
            <input type="hidden" class="cid" value="C0001048118">
          </form>
        </div>
      </div>
    </div>
  </body>
</html>
"""


def test_parse_list_page_extracts_answer_cards_and_pagination():
    entries = parse_list_page(
        LIST_HTML,
        page_number=1,
        department="소아청소년과",
        department_code="PD000",
    )
    pagination = parse_pagination(LIST_HTML)

    assert [entry.question_id for entry in entries] == ["C0001048103", "C0001048103"]
    assert entries[0].question_title == "아기고환에 물집이 생겨요"
    assert entries[0].answerer_name == "김경남"
    assert entries[0].answerer_title == "전문의"
    assert entries[0].answerer_external_id == "U0000218209"
    assert entries[0].answer_created_date.isoformat() == "2026-06-08"
    assert pagination.max_page == 11
    assert pagination.next_page == 11


def test_parse_detail_page_extracts_question_and_full_answers():
    detail = parse_detail_page(
        DETAIL_HTML,
        question_id="C0001048103",
        source_url="https://www.hidoc.co.kr/healthqna/view/C0001048103",
    )

    assert detail.question_title == "아기고환에 물집이 생겨요"
    assert "고환에 물집" in detail.question_body
    assert detail.question_created_date.isoformat() == "2026-06-08"
    assert detail.tags == ["남성생식기", "영유아", "소아청소년과"]
    assert len(detail.answers) == 2
    assert detail.answers[0].answer_id == "C0001048127"
    assert detail.answers[0].answerer_name == "김경남"
    assert detail.answers[0].answerer_title == "전문의"
    assert detail.answers[0].agree_count == 1
    assert detail.answers[0].recommend_count == 2
    assert "소아과 진료" in detail.answers[0].answer_body


def test_build_payloads_are_answer_level_and_include_stable_dedup_keys():
    entries = parse_list_page(
        LIST_HTML,
        page_number=1,
        department="소아청소년과",
        department_code="PD000",
    )
    detail = parse_detail_page(
        DETAIL_HTML,
        question_id="C0001048103",
        source_url="https://www.hidoc.co.kr/healthqna/view/C0001048103",
    )

    payloads = build_record_payloads(entries, {"C0001048103": detail})

    assert [payload["source_answer_id"] for payload in payloads] == [
        "C0001048127",
        "C0001048118",
    ]
    assert payloads[0]["external_id"] == "hidoc:C0001048103:C0001048127"
    assert payloads[0]["source_department_code"] == "PD000"
    assert payloads[0]["department"] == "소아청소년과"
    assert payloads[0]["source_url"].endswith("/healthqna/view/C0001048103")
    assert len(payloads[0]["content_hash"]) == 64
    assert payloads[0]["raw_metadata"]["answerer_profile_url"].endswith("U0000218209")


def test_content_hash_changes_when_answer_content_changes():
    first = build_content_hash("hidoc", "q1", "a1", "title", "question", "answer")
    second = build_content_hash("hidoc", "q1", "a1", "title", "question", "changed")

    assert first != second
    assert first == build_content_hash("hidoc", "q1", "a1", "title", "question", "answer")


def test_department_aliases_and_discovery():
    assert resolve_department("소아과").code == "PD000"
    assert resolve_department("소아청소년과").label == "소아청소년과"

    departments = parse_department_links(LIST_HTML)

    assert departments["PD000"].label == "소아청소년과"
    assert departments["PF000"].label == "가정의학과"


@pytest.mark.django_db
def test_upsert_qna_record_is_idempotent():
    entries = parse_list_page(
        LIST_HTML,
        page_number=1,
        department="소아청소년과",
        department_code="PD000",
    )
    detail = parse_detail_page(
        DETAIL_HTML,
        question_id="C0001048103",
        source_url="https://www.hidoc.co.kr/healthqna/view/C0001048103",
    )
    payload = build_record_payloads(entries, {"C0001048103": detail})[0]

    created, first_record = upsert_qna_record(payload)
    updated, second_record = upsert_qna_record({**payload, "answer_body": "updated answer"})

    assert created is True
    assert updated is False
    assert first_record.pk == second_record.pk
    assert ExternalQnaRecord.objects.count() == 1
    assert ExternalQnaRecord.objects.get().answer_body == "updated answer"


def test_progress_logger_writes_tail_friendly_progress_lines(tmp_path: Path):
    log_path = tmp_path / "ingestion.log"
    logger = ProgressLogger(log_path)

    logger.info(
        "page_complete",
        mode="sample",
        department="소아청소년과",
        worker_id="worker-1",
        current_page=12,
        total_pages=350,
        processed_records=87,
        target_records=100,
        inserted=80,
        updated=5,
        failed_pages=2,
    )

    line = log_path.read_text(encoding="utf-8").strip()

    assert "event=page_complete" in line
    assert "mode=sample" in line
    assert "department=소아청소년과" in line
    assert "worker_id=worker-1" in line
    assert "page=12/350" in line
    assert "records_collected=87/100" in line
    assert "inserted=80 updated=5 failed_pages=2" in line


def test_management_command_accepts_sample_and_full_modes():
    parser = Command().create_parser("manage.py", "ingest_hidoc_qna")

    sample = parser.parse_args(["--department", "소아과", "--limit", "100", "--workers", "5"])
    full = parser.parse_args(["--all", "--workers", "10", "--mode", "full"])

    assert sample.department == ["소아과"]
    assert sample.limit == 100
    assert sample.workers == 5
    assert full.all_departments is True
    assert full.mode == "full"
