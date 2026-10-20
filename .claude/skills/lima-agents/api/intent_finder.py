"""intent_finder API wrapper.

Endpoint · POST /intent_finder/keyword_list

비용 주의 · 호출당 크레딧이 keyword_info보다 큼 — 반드시 필요한 분석
(인텐트 유형별 키워드 확장)에만 호출하고, 실소비는 응답 cost_detail로 확인.
keyword_info 응답의 intents(i/n/c/t) 벡터로 충분한 분석에는 호출하지 않는다.
"""
from __future__ import annotations

from .client import DaasClient

SORT_FIELDS = ("volume_avg", "volume_total", "volume_trend", "cpc", "competition_index")


def fetch(
    client: DaasClient,
    keywords: list[str],
    gl: str = "kr",
    volume_threshold: int = 100,
    limit: int = 100,
    sort: str = "volume_avg",
    order: str = "desc",
) -> dict:
    """시드 키워드들의 인텐트 유형별 연관 키워드 리스트 조회.

    - volume_threshold · 검색량 임계값 (기본 100)
    - limit · 반환 키워드 수 제한 (기본 100 — 비용 비례하므로 보수적으로)
    - sort · volume_avg(기본) / volume_total / volume_trend / cpc / competition_index

    Returns · 원본 API 응답 dict · {"result", "data", "cost_detail", ...}
    """
    if sort not in SORT_FIELDS:
        raise ValueError(f"sort must be one of {SORT_FIELDS}")
    body = {
        "keywords": keywords,
        "gl": gl,
        "volume_threshold": volume_threshold,
        "limit": limit,
        "sort": sort,
        "order": order,
    }
    return client.post("intent_finder/keyword_list", body)
