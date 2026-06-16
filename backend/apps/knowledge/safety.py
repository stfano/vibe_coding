from __future__ import annotations


RED_FLAG_TERMS = (
    "호흡곤란",
    "숨참",
    "숨 차",
    "숨이 차",
    "청색증",
    "의식 저하",
    "의식저하",
    "경련",
    "흉통",
    "가슴통증",
    "편측마비",
    "한쪽 마비",
    "말 어눌",
    "자살",
    "suicide",
    "chest pain",
    "shortness of breath",
    "cyanosis",
    "seizure",
    "stroke",
)


def detect_red_flag_query(query: str) -> list[str]:
    normalized = query.lower()
    return [term for term in RED_FLAG_TERMS if term.lower() in normalized]
