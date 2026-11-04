"""keyword_info API wrapper.

Endpoint · POST /keyword_info · POST /keyword_info/monthly_volume
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


def fetch_monthly_volume(
    client: DaasClient,
    keyword: str,
    gl: str = "kr",
    user_query: str | None = None,
    response_format: str = "json",
) -> dict:
    """키워드 1개의 월별 검색량만 조회 · POST /keyword_info/monthly_volume.

    - 운영 명세 v1.0.15 부터 지원 · 분석 파이프라인은 배치(ads_info)를 쓴다 · DaaS 키 전용
    - 응답 data = [{keyword, monthly_volume: [{month, gg, nv, total}, ...]}] — 값은 /keyword_info 와 같다(스펙 설명).
      색인에 없거나 월별 검색량이 없으면 빈 리스트
    - 크레딧: input 1 / output 0 (2026-11-04 1건 실측 · total_cost 1) — 키워드가 여러 개면 keyword_info(ads_info) 배치가 같은 단가로 한 번에 받는다
    """
    if not keyword or not keyword.strip():
        raise ValueError("keyword required")
    if response_format not in ("json", "download_url"):
        raise ValueError(f"response_format {response_format!r} — json · download_url")
    body: dict = {"keyword": keyword, "gl": gl, "response_format": response_format}
    if user_query:
        body["user_query"] = user_query
    return client.post("keyword_info/monthly_volume", body)


def index_by_keyword(data_list: list[dict]) -> dict[str, dict]:
    """data 리스트를 keyword 기반 dict로 인덱싱 · 빠른 lookup용."""
    result = {}
    for item in data_list:
        kw = item.get("keyword")
        if kw:
            result[kw] = item
    return result
