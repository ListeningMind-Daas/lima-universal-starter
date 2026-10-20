"""path_finder API wrapper.

Endpoint · POST /path_finder · POST /path_finder/keyword_list

응답 형태 (2026-07-29 실측) · data = 검색 경로 배열, 각 경로는 키워드 시퀀스.
  {"result": "OK", "data": [["에어컨", "에어컨 설치", "벽걸이 에어컨 설치"], ...], "cost_detail": {...}}

비용 주의 · 반환 키워드 수에 비례 과금 (실측: 경로 5개·출력 10키워드 = 450 credits).
API 기본 limit=300이지만 본 래퍼는 150을 기본값으로 잡는다 — 여정 분석에 충분하며
비용을 절반 이하로 통제. 더 필요하면 limit을 명시적으로 올릴 것.
"""
from __future__ import annotations

from .client import DaasClient

TIME_POINTS = ("curr", "3m", "6m", "9m", "12m")


def fetch(
    client: DaasClient,
    keyword: str,
    gl: str = "kr",
    time_point: str = "curr",
    limit: int = 150,
) -> dict:
    """단일 키워드의 검색 경로(여정) 조회.

    Returns · 원본 API 응답 dict · {"result", "data": [[kw, ...], ...], "cost_detail", ...}
    """
    if time_point not in TIME_POINTS:
        raise ValueError(f"time_point must be one of {TIME_POINTS}")
    body = {"keyword": keyword, "gl": gl, "time_point": time_point, "limit": limit}
    return client.post("path_finder", body)


def fetch_keyword_list(
    client: DaasClient,
    keyword: str,
    gl: str = "kr",
    time_point: str = "curr",
    limit: int = 150,
) -> dict:
    """검색 경로에 등장하는 키워드 리스트만 조회 (경로 시퀀스 불필요 시 경량 대안)."""
    if time_point not in TIME_POINTS:
        raise ValueError(f"time_point must be one of {TIME_POINTS}")
    body = {"keyword": keyword, "gl": gl, "time_point": time_point, "limit": limit}
    return client.post("path_finder/keyword_list", body)


def paths(response: dict) -> list[list[str]]:
    """응답에서 검색 경로(키워드 시퀀스) 목록 추출 · 2개 미만 시퀀스는 제외.

    집계 행동 그래프이며 개인 추적이 아님.
    """
    raw = response.get("data", []) or []
    out: list[list[str]] = []
    for p in raw:
        if not isinstance(p, (list, tuple)):
            continue
        seq = [str(kw).strip() for kw in p if kw and str(kw).strip()]
        if len(seq) >= 2:
            out.append(seq)
    return out
