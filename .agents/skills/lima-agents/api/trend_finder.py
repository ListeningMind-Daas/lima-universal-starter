"""trend_finder API wrapper.

Endpoint · POST /trend_finder/issue_list   (2026-09-23 래퍼 추가 · 단가는 운영 명세에서 읽는다 — api/spec.py)

시드 키워드 주변에서 **최근 급부상한 이슈 항목**을 반환한다. 구글 자동완성·검색결과(SERP) 기반의
일별 이슈 인덱스(2025-05-26부터 적재)에서 요약문·핵심 구문·출처 링크·토픽·이슈 점수를 준다.
keyword_info 가 "검색량이 어떻게 움직였나"라면, 이것은 "그 키워드 주변에서 지금 무슨 일이 있나"를
내용 근거(출처 링크)와 함께 준다.

**실시간 크롤이 아니다.** 빈 결과는 오류가 아니라 "그 기간 인덱스에 매칭된 이슈 없음"이라는 실측이다.
기간을 14 → 90 → 365 로 넓혀 한 번 더 보고 결론을 내린다(`widen()`). 이슈를 지어내지 않는다.

비용 · **50 (시드 키워드 1개) + 반환 이슈 항목 × 2**
  2026-09-23 실측 · 로봇청소기 · gl=kr · period_days=14 · limit=3 → cost_detail
  {"input_cost": 50, "input_count": 1, "output_cost": 2, "output_count": 3, "total_cost": 56} · total(매칭 전체) 7.
  출력 과금이 있으므로 `limit` 으로 통제한다 — API 기본 1,000(최대 10,000)이지만 래퍼 기본은 50.
  `total` 은 과금과 무관하게 매칭 전체 수를 알려 주므로, 먼저 작은 limit 으로 규모를 보고 늘린다.

응답 형태 (실측) · data = 이슈 항목 배열 (sort=score 기본 · 이슈 점수 내림차순)
  {"result": "OK", "total": 7,
   "data": [{"keyword": "드리미 x60", "issue_score": 5.5857, "content_type": "web", "topic": null,
             "category": null, "freshness": 0.0,
             "summary": ["드리미 X60 시리즈는 …", …], "key_phrase": ["드리미", "x60", …],
             "source_links": ["https://kr.dreametech.com/…", …],
             "recorded_at": "…", "index_date": "…"}],
   "cost_detail": {...}, "used_credits": 1234567}

주의 · 이슈 인덱스는 **구글** 기반이다. 네이버 비중이 큰 카테고리에서는 "국내 이슈 전체"로 단정하지 않는다.
"""
from __future__ import annotations

from . import spec as _spec
from .client import DaasClient

SORT_FIELDS = ("score", "date")
CONTENT_TYPES = ("news", "video", "web")
DEFAULT_LIMIT = 50
WIDEN_PERIODS = (14, 90, 365)


def estimate(limit: int, seeds: int = 1) -> int:
    """견적 · 시드당 입력 단가 + 최대 limit 건 × 출력 단가 (운영 명세 단가 · 상한 — 실제는 매칭 수만큼만 출력 과금)."""
    rin, rout = _spec.rate(_spec.default(), "/trend_finder/issue_list")
    return seeds * (rin + rout * int(limit))


def fetch(
    client: DaasClient,
    keyword: str,
    gl: str = "kr",
    period_days: int = 14,
    limit: int = DEFAULT_LIMIT,
    sort: str = "score",
    order: str = "desc",
    content_type: str | None = None,
    user_query: str | None = None,
) -> dict:
    """단일 시드 키워드의 최근 이슈 항목 조회.

    - period_days · 최신 N일의 이슈 인덱스 (기본 14 · 최대 365)
    - limit · 반환 이슈 항목 수 (기본 50 · 출력 과금 2/건이므로 보수적으로) · API 최대 10,000
    - sort · score(이슈 점수, 기본) / date(기록일)
    - content_type · news / video / web — 최상단 콘텐츠 유형 필터 (None 이면 전체)
    - user_query · 이 호출을 유발한 사용자 질의 원문 (선택 · 이력에 함께 적재)

    Returns · 원본 API 응답 dict · {"result", "total", "data": [이슈, ...], "cost_detail", ...}
    """
    if not keyword or not keyword.strip():
        raise ValueError("keyword required (단일 시드 문자열)")
    if sort not in SORT_FIELDS:
        raise ValueError(f"sort must be one of {SORT_FIELDS}")
    if content_type is not None and content_type not in CONTENT_TYPES:
        raise ValueError(f"content_type must be one of {CONTENT_TYPES} or None")
    if not 1 <= int(period_days) <= 365:
        raise ValueError("period_days must be 1..365")
    body: dict = {
        "keyword": keyword.strip(),
        "gl": gl,
        "period_days": int(period_days),
        "limit": int(limit),
        "sort": sort,
        "order": order,
    }
    if content_type:
        body["content_type"] = content_type
    if user_query:
        body["user_query"] = user_query
    return client.post("trend_finder/issue_list", body)


def widen(
    client: DaasClient,
    keyword: str,
    gl: str = "kr",
    periods: tuple[int, ...] = WIDEN_PERIODS,
    limit: int = DEFAULT_LIMIT,
    **kw,
) -> tuple[dict, list[int]]:
    """빈 결과면 기간을 넓혀 다시 본다 · (마지막 응답, 시도한 기간 목록).

    호출마다 시드 과금 50 이 다시 나간다 — 세 번 다 비면 150. 그래도 "이슈 없음"을 근거 있게 말하려면 필요하다.
    """
    tried: list[int] = []
    resp: dict = {}
    for p in periods:
        tried.append(p)
        resp = fetch(client, keyword, gl=gl, period_days=p, limit=limit, **kw)
        if items(resp):
            break
    return resp, tried


def items(response: dict) -> list[dict]:
    """이슈 항목 목록 · dict 만."""
    return [i for i in (response.get("data") or []) if isinstance(i, dict)]


def cost(response: dict) -> int:
    return int((response.get("cost_detail") or {}).get("total_cost") or 0)


def by_topic(response: dict) -> dict[str, list[dict]]:
    """topic 별 묶음 · topic 이 없는 항목은 "(없음)"."""
    out: dict[str, list[dict]] = {}
    for i in items(response):
        out.setdefault(i.get("topic") or "(없음)", []).append(i)
    return out


def sources(response: dict, max_per_item: int | None = None) -> list[tuple[str, str]]:
    """(이슈 키워드, 출처 URL) 평탄화 · 출처 인용용."""
    out: list[tuple[str, str]] = []
    for i in items(response):
        links = i.get("source_links") or []
        for u in (links[:max_per_item] if max_per_item else links):
            out.append((i.get("keyword") or "", u))
    return out


def brief(response: dict, n: int = 10) -> list[dict]:
    """리포트용 축약 · {keyword, issue_score, content_type, topic, summary(첫 문장), sources(첫 2개)}."""
    out = []
    for i in items(response)[:n]:
        out.append({
            "keyword": i.get("keyword"),
            "issue_score": i.get("issue_score"),
            "content_type": i.get("content_type"),
            "topic": i.get("topic"),
            "summary": (i.get("summary") or [""])[0],
            "sources": (i.get("source_links") or [])[:2],
            "index_date": i.get("index_date"),
        })
    return out
