"""keyword_info API wrapper.

Endpoint · POST /keyword_info · POST /keyword_info/monthly_volume · POST /keyword_info/status
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


MONTH_SPAN_MAX = 48  # date_from~date_to 상한(4년) — 넘으면 422


def _check_month_range(date_from: str | None, date_to: str | None) -> None:
    """date_from·date_to(YYYY-MM · 해당 월 포함) 를 명세 규칙으로 미리 거른다 — 422 를 받기 전에."""
    import re

    months = {}
    for name, value in (("date_from", date_from), ("date_to", date_to)):
        if value is None:
            continue
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
            raise ValueError(f"{name} {value!r} — YYYY-MM")
        months[name] = int(value[:4]) * 12 + int(value[5:])
    if len(months) == 2:
        span = months["date_to"] - months["date_from"] + 1
        if span < 1:
            raise ValueError("date_to 가 date_from 보다 이르다")
        if span > MONTH_SPAN_MAX:
            raise ValueError(f"기간 {span}개월 — 최대 {MONTH_SPAN_MAX}개월")


def _monthly_volume_body(
    keywords: list[str], gl: str, date_from: str | None, date_to: str | None,
    user_query: str | None, response_format: str,
) -> dict:
    body: dict = {"keywords": keywords, "gl": gl, "response_format": response_format}
    if date_from:
        body["date_from"] = date_from
    if date_to:
        body["date_to"] = date_to
    if user_query:
        body["user_query"] = user_query
    return body


def _clean_keywords(keywords: str | list[str]) -> list[str]:
    if isinstance(keywords, str):
        keywords = [keywords]
    cleaned = [k for k in keywords if k and k.strip()]
    if not cleaned:
        raise ValueError("keywords required")
    return cleaned


def fetch_monthly_volume(
    client: DaasClient,
    keywords: str | list[str],
    gl: str = "kr",
    date_from: str | None = None,
    date_to: str | None = None,
    user_query: str | None = None,
    response_format: str = "json",
) -> dict:
    """키워드(최대 1000개)의 월별 검색량만 조회 · POST /keyword_info/monthly_volume.

    - 운영 명세 v1.0.20 (2026-11-13 확인) 부터 배치 — 본문은 keywords 배열(이전 판의 keyword 단건은 없어졌다) · DaaS 키 전용
      keywords 에 문자열 하나를 줘도 배열로 보낸다
    - date_from·date_to (YYYY-MM · 해당 월 포함 · 선택) — 둘 다 생략하면 제공 범위 전체(색인된 최신 월 기준 최근 4년).
      하나만 주면 다른 쪽은 제한 없음. 48개월 초과·순서 역전은 422 (여기서 미리 거른다).
      기간 선택은 이 엔드포인트에만 있다 — /keyword_info(ads_metrics·ads_info·all)에는 없다
    - 응답 data = [{keyword, monthly_volume: [{month, gg, nv, total}, ...]}] — 값은 /keyword_info 와 같다(명세 설명).
      색인에 없거나 (기간 내) 월별 검색량이 없는 키워드는 빠진다 · 모두 없으면 빈 리스트
    - 크레딧: 반환된 행 1개당 input 1 / output 0 (2026-11-13 실측 2건) — 데이터가 없는 키워드는 빠지고 과금되지 않는다(kr 3개 요청 → 2행 · 2).
      표기 변형 행도 과금된다(us refrigerator 1개 요청 → 3행 · 3) — 요청 키워드 수는 상한이 아니다. 행 순서는 요청 순서와 다를 수 있다
    """
    keywords = _clean_keywords(keywords)
    if len(keywords) > BATCH_SIZE:
        raise ValueError(f"keywords > {BATCH_SIZE} · use fetch_monthly_volume_all")
    if response_format not in ("json", "download_url"):
        raise ValueError(f"response_format {response_format!r} — json · download_url")
    _check_month_range(date_from, date_to)
    return client.post(
        "keyword_info/monthly_volume",
        _monthly_volume_body(keywords, gl, date_from, date_to, user_query, response_format),
    )


def fetch_monthly_volume_all(
    client: DaasClient,
    keywords: list[str],
    gl: str = "kr",
    date_from: str | None = None,
    date_to: str | None = None,
    user_query: str | None = None,
) -> tuple[list[dict], int]:
    """1000개를 넘는 키워드를 배치로 나눠 월별 검색량 조회 · 병합된 data 리스트 + 총 크레딧.

    Returns · (data_list, total_cost)
    """
    if not keywords:
        return [], 0
    keywords = _clean_keywords(keywords)
    _check_month_range(date_from, date_to)

    def make_body(chunk: list[str]) -> dict:
        return _monthly_volume_body(chunk, gl, date_from, date_to, user_query, "json")

    responses = client.batched_post(
        "keyword_info/monthly_volume", keywords, make_body, batch_size=BATCH_SIZE
    )
    all_data: list[dict] = []
    total_cost = 0
    for resp in responses:
        if resp.get("result") == "ERROR":
            continue
        all_data.extend(resp.get("data") or [])
        total_cost += (resp.get("cost_detail") or {}).get("total_cost", 0)
    return all_data, total_cost


def index_by_keyword(data_list: list[dict]) -> dict[str, dict]:
    """data 리스트를 keyword 기반 dict로 인덱싱 · 빠른 lookup용."""
    result = {}
    for item in data_list:
        kw = item.get("keyword")
        if kw:
            result[kw] = item
    return result


def fetch_status(client: DaasClient, user_query: str | None = None) -> dict:
    """검색량 데이터의 기준월(구글·네이버 각각의 최신 월)과 확인 시각 · POST /keyword_info/status.

    - 운영 명세 v1.0.29 (2026-11-27 확인)에서 생겼다 · 무료(cost_detail.total_cost 항상 0) · DaaS 키 전용 · 국가 구분 없음
    - 응답 data = {google_month, google_month_fetch_time, naver_month, naver_month_fetch_time} (월은 YYYY-MM, 시각은 UTC)
    - 기준월은 매시 확인된다 — 확인 시각이 1시간 넘게 지났으면 최근 확인이 실패한 것(명세 설명)
    - 쓰임: 월 갱신(새 달 데이터가 들어왔는지)을 크레딧 없이 확인한다. 실측 응답은 아직 없다(명세 예시만)
    """
    body: dict = {}
    if user_query:
        body["user_query"] = user_query
    return client.post("keyword_info/status", body)
