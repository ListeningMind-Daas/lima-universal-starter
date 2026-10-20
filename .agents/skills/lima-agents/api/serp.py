"""serp API wrapper.

Endpoint · POST /serp

검색결과 화면(SERP) 자체를 블록 단위로 반환한다. keyword_info의 `features`가
"어떤 블록이 몇 개 있는지"만 알려주는 데 비해, 이 엔드포인트는 블록의 실제 내용
(제목·URL·스니펫·연관 질문·AI 개요 텍스트)을 준다.

응답 형태 (2026-08-19 실측 · gl=kr · num=10) · data = SERP 블록 배열.
  {"result": "OK", "data": [{"sequence": 1, "type": "ai_overview", ...},
                            {"sequence": 2, "type": "organic_results", "position": 1, ...}],
   "cost_detail": {"input_cost": 10, "output_cost": 0, "total_cost": 10}}

블록 type (실측 확인) · organic_results · ai_overview · knowledge_panel ·
people_also_ask_for · people_also_search_for · related_searches · video_results · images

비용 · 키워드당 **30크레딧** (입력 과금만 · 출력 과금 없음).
  2026-08-28 실측: input_cost 30 × 12시드 = 360. 이전 문서값 10은 2026-08-19 기준이며 그 사이 인상됐다.
  num=20으로 실측했고 num=10과의 차이는 미검증 — 견적 시 30/kw로 잡는다.

주의 · 반환 내용은 조회 시점의 검색결과 스냅샷이다. 시계열 비교에는 쓸 수 없고,
SERP 구조의 시점 비교가 필요하면 keyword_info(features)의 월 그레인을 쓴다.
"""
from __future__ import annotations

from .client import DaasClient

NUM_CHOICES = (10, 20)
QUERY_BLOCKS = ("related_searches", "people_also_search_for")


def fetch(
    client: DaasClient,
    keyword: str,
    gl: str = "kr",
    num: int = 20,
    device: str = "mobile",
    features: list[str] | None = None,
) -> dict:
    """단일 키워드의 SERP 조회.

    - num · 10 또는 20 (기본 20) · 과금은 num과 무관하게 키워드당 10
    - device · "mobile"(기본) / "desktop"
    - features · 특정 블록만 요청 (None이면 전체)

    Returns · 원본 API 응답 dict · {"result", "data": [블록, ...], "cost_detail", ...}
    """
    if num not in NUM_CHOICES:
        raise ValueError(f"num must be one of {NUM_CHOICES}")
    body: dict = {"keyword": keyword, "gl": gl, "num": num, "device": device}
    if features:
        body["features"] = features
    return client.post("serp", body)


def blocks(response: dict, block_type: str | None = None) -> list[dict]:
    """응답에서 SERP 블록 목록 추출 · block_type 지정 시 해당 타입만."""
    data = [b for b in (response.get("data") or []) if isinstance(b, dict)]
    if block_type:
        return [b for b in data if b.get("type") == block_type]
    return data


def block_counts(response: dict) -> dict[str, int]:
    """블록 type별 개수 · SERP 구조 요약용."""
    out: dict[str, int] = {}
    for b in blocks(response):
        t = b.get("type") or "unknown"
        out[t] = out.get(t, 0) + 1
    return out


def organic(response: dict) -> list[dict]:
    """자연 검색결과만 · position 순 정렬 · {position, site_name, title, url, snippet}."""
    out = [
        {k: b.get(k) for k in ("position", "site_name", "title", "url", "snippet")}
        for b in blocks(response, "organic_results")
    ]
    return sorted(out, key=lambda r: r.get("position") or 0)


def related_queries(response: dict) -> list[str]:
    """연관 검색어 · related_searches + people_also_search_for 통합 · 중복 제거."""
    seen: list[str] = []
    for t in QUERY_BLOCKS:
        for b in blocks(response, t):
            for item in b.get("items") or []:
                q = (item.get("query") or "").strip()
                if q and q not in seen:
                    seen.append(q)
    return seen


def questions(response: dict) -> list[dict]:
    """People Also Ask 질문 · {question, url, title}."""
    return [
        {"question": i.get("question"), "url": i.get("url"), "title": i.get("title")}
        for b in blocks(response, "people_also_ask_for")
        for i in (b.get("items") or [])
        if i.get("question")
    ]


def ai_overview_snippets(response: dict) -> list[str]:
    """AI 개요 본문 스니펫 · 없으면 빈 리스트 (AI Overview 미노출 키워드)."""
    out: list[str] = []
    for b in blocks(response, "ai_overview"):
        for tb in b.get("text_blocks") or []:
            for item in tb.get("list") or []:
                s = (item.get("snippet") or "").strip()
                if s:
                    out.append(s)
    return out
