"""Cluster Explorer 데이터 준비.

기존 cluster-finder 스킬의 CLUSTER_DATA 구조를 그대로 조립.
- MVP · CEP 분류·엔티티 감지는 빈 값 (UI에 "데이터 없음" 표시)
- 나중에 Claude가 대화 안에서 추가로 분류·감지해 주입 가능
"""
from __future__ import annotations

import sys
import os
from datetime import datetime, timezone
from collections import Counter

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SKILL_ROOT not in sys.path:
    sys.path.insert(0, SKILL_ROOT)

from api.client import DaasClient
from api import cluster_finder, keyword_info
from lib import cep_regex_fallback, entity_detector
from lib.cep_classifier import assemble_cep_grouped


LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _compute_hubs(rels: list, communities: dict) -> list[str]:
    """degree 상위 · 각 클러스터 대표 노드."""
    degree = Counter()
    for a, b in rels:
        degree[a] += 1
        degree[b] += 1
    cluster_hubs = {}
    for cid, kws in (communities or {}).items():
        if kws:
            cluster_hubs[cid] = max(kws, key=lambda k: degree.get(k, 0))
    top_hubs = [kw for kw, _ in degree.most_common(10)]
    return sorted(set(cluster_hubs.values()) | set(top_hubs))


def _cluster_labels(communities: dict, kw2vol: dict) -> dict:
    """각 클러스터 · 검색량 합계 순 정렬 · A/B/C 알파벳 · 이름은 상위 키워드 자동."""
    if not communities:
        return {}
    # 총 볼륨 순 정렬
    sorted_cids = sorted(
        communities.items(),
        key=lambda x: -sum(kw2vol.get(k, 0) for k in x[1]),
    )
    out = {}
    for idx, (cid, kws) in enumerate(sorted_cids):
        letter = LETTERS[idx] if idx < len(LETTERS) else f"C{idx}"
        # 임시 · 상위 3 키워드 join · Claude가 필요하면 나중에 개선
        top_kws = sorted(kws, key=lambda k: -kw2vol.get(k, 0))[:3]
        name = " · ".join(top_kws) if top_kws else f"Cluster {cid}"
        total_vol = sum(kw2vol.get(k, 0) for k in kws)
        out[str(cid)] = {
            "letter": letter,
            "name": name,
            "total_volume": total_vol,
            "size": len(kws),
        }
    return out


def _nodes_with_community(all_kws: list[str], kw2comm: dict, kw2vol: dict) -> list[dict]:
    nodes = []
    for kw in all_kws:
        nodes.append({
            "keyword": kw,
            "volume": int(kw2vol.get(kw, 0) or 0),
            "community": str(kw2comm.get(kw, "")),
        })
    return nodes


def prepare(category: str, gl: str, api_key: str) -> dict:
    """Cluster Explorer CLUSTER_DATA 조립."""
    client = DaasClient(api_key)

    # 1. cluster_finder
    cf = cluster_finder.fetch(client, category, gl=gl, limit=5000, hop=2)
    if cf.get("result") != "OK":
        raise RuntimeError(f"cluster_finder 실패 · {cf.get('reason')}")

    data = cf["data"]
    all_kws = cluster_finder.unique_keywords(cf)
    rels = data.get("rels") or []
    communities = data.get("communities") or {}
    kw2comm = cluster_finder.build_kw2community(cf)
    cost_cf = cf.get("cost_detail", {}).get("total_cost", 0)

    # 2. keyword_info(all)
    info_list, cost_ki = keyword_info.fetch_all(client, all_kws, gl=gl, data_type="all")
    info_by_kw = keyword_info.index_by_keyword(info_list)

    # volume은 keyword_info에서
    kw2vol = {}
    for kw in all_kws:
        info = info_by_kw.get(kw, {}) or {}
        ads = info.get("ads_metrics") or {}
        kw2vol[kw] = int(ads.get("volume_avg") or 0)

    # 3. 파생 필드
    hub_keywords = _compute_hubs(rels, communities)
    cluster_labels = _cluster_labels(communities, kw2vol)
    nodes = _nodes_with_community(all_kws, kw2comm, kw2vol)

    # 4. keyword_info를 dict로 (템플릿 요구)
    kw_info_lite = {}
    for kw in all_kws:
        item = info_by_kw.get(kw)
        if not item:
            continue
        kw_info_lite[kw] = {
            "ads_metrics": item.get("ads_metrics"),
            "intents": item.get("intents"),
            "demography": item.get("demography"),
            "features": item.get("features"),
            "monthly_volume": item.get("monthly_volume"),
        }

    return {
        "seeds": [category],
        "communities": communities,
        "rels": rels,
        "nodes": nodes,
        "hub_keywords": hub_keywords,
        "bridge_kws": [],
        "cluster_labels": cluster_labels,
        # MVP · CEP·엔티티는 빈 값 (UI가 "데이터 없음" 표시)
        # 향후 · Claude가 대화 중 추가 조립해서 주입 가능
        "detected_entities": {"brands": [], "ingredients": [], "other": []},
        "cep_grouped": {},
        "keyword_info": kw_info_lite,
        "_meta": {
            "category": category,
            "gl": gl,
            "total_credits": cost_cf + cost_ki,
            "total_nodes": len(all_kws),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }
