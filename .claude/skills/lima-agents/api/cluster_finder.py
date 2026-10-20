"""cluster_finder API wrapper.

Endpoint · POST /cluster_finder
"""
from __future__ import annotations

from .client import DaasClient


def fetch(
    client: DaasClient,
    keyword: str,
    gl: str = "kr",
    limit: int = 5000,
    hop: int = 2,
    orientation: str = "UNDIRECTED",
    time_point: str = "curr",
    data_type: str = "all",
) -> dict:
    """단일 시드로 관계 그래프 조회.

    Returns · 원본 API 응답 dict · {"result", "data": {rels, communities, nodes}, "cost_detail", ...}
    """
    body = {
        "keyword": keyword,
        "gl": gl,
        "time_point": time_point,
        "limit": limit,
        "hop": hop,
        "orientation": orientation,
        "data_type": data_type,
    }
    return client.post("cluster_finder", body)


def fetch_keyword_list(
    client: DaasClient,
    keyword: str,
    gl: str = "kr",
    limit: int = 500,
    hop: int = 2,
    orientation: str = "UNDIRECTED",
    time_point: str = "curr",
) -> dict:
    """관계 그래프의 키워드 리스트만 조회 (POST /cluster_finder/keyword_list).

    그래프 구조(rels·communities)가 불필요하고 키워드 우주만 필요할 때의 경량 대안.
    Returns · 원본 API 응답 dict
    """
    body = {
        "keyword": keyword,
        "gl": gl,
        "time_point": time_point,
        "limit": limit,
        "hop": hop,
        "orientation": orientation,
    }
    return client.post("cluster_finder/keyword_list", body)


def unique_keywords(response: dict) -> list[str]:
    """cluster_finder 응답의 모든 유니크 키워드 리스트 추출.

    소스 우선순위 · nodes > communities > rels
    - nodes 필드가 있으면 (신 버전) 그거 사용
    - 아니면 communities 딕셔너리 값들의 union
    - 마지막 폴백 · rels 관계 쌍에서
    """
    data = response.get("data", {})
    seen = set()
    result = []
    # 1) nodes (있으면)
    for n in data.get("nodes", []) or []:
        kw = n.get("keyword") if isinstance(n, dict) else str(n)
        if kw and kw not in seen:
            seen.add(kw)
            result.append(kw)
    # 2) communities (딕셔너리 {cid: [kw, kw, ...]})
    for cid, kws in (data.get("communities", {}) or {}).items():
        for kw in kws or []:
            if kw not in seen:
                seen.add(kw)
                result.append(kw)
    # 3) rels 폴백
    for pair in data.get("rels", []) or []:
        if not isinstance(pair, (list, tuple)):
            continue
        for kw in pair:
            if kw and kw not in seen:
                seen.add(kw)
                result.append(kw)
    return result


def build_kw2community(response: dict) -> dict[str, str]:
    """communities 딕셔너리에서 · keyword → community_id 매핑."""
    data = response.get("data", {})
    out = {}
    for cid, kws in (data.get("communities", {}) or {}).items():
        for kw in kws or []:
            out[kw] = str(cid)
    # nodes 필드 있으면 · community도 함께
    for n in data.get("nodes", []) or []:
        if isinstance(n, dict) and n.get("keyword") and n.get("community") is not None:
            out.setdefault(n["keyword"], str(n["community"]))
    return out


# 하위 호환 · 기존 이름 유지
unique_keywords_from_nodes = unique_keywords
