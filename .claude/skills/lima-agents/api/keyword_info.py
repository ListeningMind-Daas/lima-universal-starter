"""keyword_info API wrapper.

Endpoint · POST /keyword_info
"""
from __future__ import annotations

from .client import DaasClient

BATCH_SIZE = 1000  # API 상한


def fetch_batch(
    client: DaasClient,
    keywords: list[str],
    gl: str = "kr",
    data_type: str = "all",
) -> dict:
    """단일 배치 조회 (최대 1000개).

    data_type · ads_metrics · ads_info · all (기본)
    - 크레딧: all = 10/kw · ads_metrics/ads_info = 1/kw (2026-08-03 실측)
    - 분석은 all 권장 · 키 검증 등 저비용 확인은 ads_metrics
    """
    if len(keywords) > BATCH_SIZE:
        raise ValueError(f"keywords > {BATCH_SIZE} · use fetch_all")
    body = {"keywords": keywords, "gl": gl, "data_type": data_type}
    return client.post("keyword_info", body)


def fetch_all(
    client: DaasClient,
    keywords: list[str],
    gl: str = "kr",
    data_type: str = "all",
) -> tuple[list[dict], int]:
    """모든 키워드를 배치로 병렬 조회 · 병합된 data 리스트 + 총 크레딧.

    Returns · (data_list, total_cost)
    """
    if not keywords:
        return [], 0

    def make_body(chunk: list[str]) -> dict:
        return {"keywords": chunk, "gl": gl, "data_type": data_type}

    responses = client.batched_post(
        "keyword_info", keywords, make_body, batch_size=BATCH_SIZE
    )
    all_data: list[dict] = []
    total_cost = 0
    for resp in responses:
        if resp.get("result") == "ERROR":
            continue
        all_data.extend(resp.get("data", []))
        total_cost += resp.get("cost_detail", {}).get("total_cost", 0)
    return all_data, total_cost


def index_by_keyword(data_list: list[dict]) -> dict[str, dict]:
    """data 리스트를 keyword 기반 dict로 인덱싱 · 빠른 lookup용."""
    result = {}
    for item in data_list:
        kw = item.get("keyword")
        if kw:
            result[kw] = item
    return result
