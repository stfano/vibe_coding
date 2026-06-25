from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GroundingReview:
    status: str
    findings: list[str]
    allowed_citation_ids: list[str]
    detected_citation_ids: list[str]
    unknown_citation_ids: list[str]


_BRACKET_CITATION_RE = re.compile(r"\[(\d+)\]")
_COMPOUND_CITATION_RE = re.compile(r"\b[A-Z][A-Z0-9_-]*:[A-Z0-9_-]*\d[A-Z0-9_-]*\b")
_DEFINITIVE_DIAGNOSIS_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bthe diagnosis is\b",
        r"\bthis confirms\b",
        r"\byou have\b",
        r"진단됩니다",
        r"확진입니다",
    )
]
_DOSE_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg/kg|mg|mcg|µg|g|ml|mL)\b", re.IGNORECASE)
_PRESCRIPTION_RE = re.compile(
    r"\b(?:prescribe|start|increase dose|bid|tid|qid)\b|처방|복용|시작하세요",
    re.IGNORECASE,
)


def review_grounded_answer(*, answer: str, contexts: list[dict[str, Any]]) -> GroundingReview:
    allowed_citation_ids = _allowed_citation_ids(contexts)
    detected_citation_ids = _detected_citation_ids(answer, allowed_citation_ids=allowed_citation_ids)
    allowed_set = set(allowed_citation_ids)
    known_detected = [citation_id for citation_id in detected_citation_ids if citation_id in allowed_set]
    unknown_citation_ids = [
        citation_id
        for citation_id in detected_citation_ids
        if citation_id not in allowed_set and _looks_like_unknown_citation_id(citation_id)
    ]

    findings = []
    if allowed_citation_ids and not known_detected:
        findings.append("missing_known_citation")
    if unknown_citation_ids:
        findings.append("unknown_citation")
    if _has_definitive_diagnosis_language(answer):
        findings.append("definitive_diagnosis_language")
    if _has_unsupported_answer_dose(answer=answer, contexts=contexts):
        findings.append("unsupported_medication_dose")
    if _has_unsupported_prescription_language(answer=answer, contexts=contexts):
        findings.append("unsupported_prescription_language")

    return GroundingReview(
        status="failed" if findings else "passed",
        findings=list(dict.fromkeys(findings)),
        allowed_citation_ids=allowed_citation_ids,
        detected_citation_ids=detected_citation_ids,
        unknown_citation_ids=list(dict.fromkeys(unknown_citation_ids)),
    )


def _allowed_citation_ids(contexts: list[dict[str, Any]]) -> list[str]:
    identifiers = []
    for index, context in enumerate(contexts, start=1):
        citation = context.get("citation") or {}
        question_id = citation.get("external_question_id")
        answer_id = citation.get("external_answer_id")
        if question_id and answer_id:
            identifiers.append(f"{question_id}:{answer_id}")
        if question_id:
            identifiers.append(str(question_id))
        identifiers.append(f"[{index}]")
    return list(dict.fromkeys(identifiers))


def _detected_citation_ids(answer: str, *, allowed_citation_ids: list[str]) -> list[str]:
    detected = [f"[{match.group(1)}]" for match in _BRACKET_CITATION_RE.finditer(answer)]
    detected.extend(match.group(0) for match in _COMPOUND_CITATION_RE.finditer(answer))
    for citation_id in allowed_citation_ids:
        if citation_id.startswith("[") or ":" in citation_id:
            continue
        if any(detected_id.startswith(f"{citation_id}:") for detected_id in detected):
            continue
        if re.search(rf"(?<![A-Z0-9_-]){re.escape(citation_id)}(?![A-Z0-9_-])", answer):
            detected.append(citation_id)
    return list(dict.fromkeys(detected))


def _looks_like_unknown_citation_id(value: str) -> bool:
    return bool(_BRACKET_CITATION_RE.fullmatch(value) or _COMPOUND_CITATION_RE.fullmatch(value))


def _has_definitive_diagnosis_language(answer: str) -> bool:
    return any(pattern.search(answer) for pattern in _DEFINITIVE_DIAGNOSIS_PATTERNS)


def _has_unsupported_answer_dose(*, answer: str, contexts: list[dict[str, Any]]) -> bool:
    context_text = _context_text(contexts)
    for match in _DOSE_RE.finditer(answer):
        if match.group(0).lower() not in context_text:
            return True
    return False


def _has_unsupported_prescription_language(*, answer: str, contexts: list[dict[str, Any]]) -> bool:
    if not _PRESCRIPTION_RE.search(answer):
        return False
    return _PRESCRIPTION_RE.search(_context_text(contexts)) is None


def _context_text(contexts: list[dict[str, Any]]) -> str:
    return "\n".join(str(context.get("text") or "") for context in contexts).lower()
