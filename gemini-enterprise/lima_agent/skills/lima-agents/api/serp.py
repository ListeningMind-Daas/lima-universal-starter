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
  num=10도 30이다(2026-11-02 40건). 스냅샷이 없는 키워드는 200 OK + data:[] + collected_at null + 0크레딧이다.

주의 · 실시간 크롤이 아니라 저장된 스냅샷을 돌려준다(OpenAPI). 시점은 요청 시각이 아니라 응답의 collected_at 이고,
처음 부른 키워드가 즉시 수집된 사례는 실측 표본(30건)에서 없었다. 시계열 비교에는 쓸 수 없고,
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
    features: str | list[str] | None = None,
) -> dict:
    """단일 키워드의 SERP 조회.

    - num · 10 또는 20 (기본 20) · 응답을 바꾸지 않았다(2026-11-02 kr 40쌍 동일) · 과금은 num과 무관하게 키워드당 30
    - device · "mobile"(기본) / "desktop"
    - features · 블록 유형 최대 1개 (문자열 또는 1개짜리 리스트 · None·빈 리스트면 전체 · 2개 이상은 API 가 422)

    Returns · 원본 API 응답 dict · {"result", "data": [블록, ...], "cost_detail", ...}
    """
    if num not in NUM_CHOICES:
        raise ValueError(f"num must be one of {NUM_CHOICES}")
    body: dict = {"keyword": keyword, "gl": gl, "num": num, "device": device}
    if features:
        features = [features] if isinstance(features, str) else features
        if len(features) > 1:
            raise ValueError("features · 블록 유형은 최대 1개")
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
    """ AI 개요 본문 스니펫(화면 순서) · 없으면 빈 리스트 (AI Overview 미노출 키워드).

    text_blocks 는 type 이 paragraph(자기 snippet)·list(list[] 안에 snippet, 다시 list[] 가 중첩될 수 있음)로 섞여 온다.
    2026-10-25 실측 2건: list 1단계만 읽으면 5/13(문단 5)·8/14(문단 3 + 중첩 목록 5)를 놓쳤다 — 문단만 있는 AI 개요는 '미노출'로 잘못 셀 수 있었다.
    """
    out: list[str] = []

    def walk(node: dict) -> None:
        s = (node.get("snippet") or "").strip()
        if s:
            out.append(s)
        for child in node.get("list") or []:
            if isinstance(child, dict):
                walk(child)

    for b in blocks(response, "ai_overview"):
        for tb in b.get("text_blocks") or []:
            walk(tb)
    return out


def ai_overview_references(response: dict) -> list[dict]:
    """AI 개요 블록 단위 인용 출처 `references[]`(title·url·source·origin_url). 문장 안 링크 조각 `snippet_links`(text·url)는
    블록이 아니라 text_blocks 안에 있고(08~09월 저장본 다수) 출처 목록이 아니라서 여기서 읽지 않는다."""
    out: list[dict] = []
    for b in blocks(response, "ai_overview"):
        out += list(b.get("references") or [])
    return out
