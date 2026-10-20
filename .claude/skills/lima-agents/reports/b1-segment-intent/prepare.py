"""B-1 · 연령별·성별 세그먼트 인텐트 데이터 준비.

Input · category · gl · api_key
Output · schema.json에 부합하는 dict
"""
from __future__ import annotations

import sys
import os
from datetime import datetime, timezone

# 스킬 루트를 sys.path에 추가 (api·lib 임포트용)
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SKILL_ROOT not in sys.path:
    sys.path.insert(0, SKILL_ROOT)

from api.client import DaasClient
from api import cluster_finder, keyword_info


# 세그먼트 정의 · demography 필드 기반
# flag_field · 사내 태깅 1/0 필드 (m_ prefix · 유의미 마커)
# ratio_field · 실제 비율 %
SEGMENTS = [
    {"key": "female", "label": "여성",  "kind": "gender", "flag": "m_f_gender_ratio", "ratio": "f_gender_ratio"},
    {"key": "male",   "label": "남성",  "kind": "gender", "flag": "m_m_gender_ratio", "ratio": "m_gender_ratio"},
    {"key": "a13",    "label": "10대",  "kind": "age",    "flag": "m_a13",            "ratio": "a13_ratio"},
    {"key": "a20",    "label": "20대",  "kind": "age",    "flag": "m_a20",            "ratio": "a20_ratio"},
    {"key": "a25",    "label": "25~",   "kind": "age",    "flag": "m_a25",            "ratio": "a25_ratio"},
    {"key": "a30",    "label": "30대",  "kind": "age",    "flag": "m_a30",            "ratio": "a30_ratio"},
    {"key": "a40",    "label": "40대",  "kind": "age",    "flag": "m_a40",            "ratio": "a40_ratio"},
    {"key": "a50",    "label": "50대+", "kind": "age",    "flag": "m_a50",            "ratio": "a50_ratio"},
]

# ratio 기반 폴백 임계값 · 사내 기준 (사내 태깅이 없거나 sparse할 때)
RATIO_FALLBACK_THRESHOLD = {
    "gender": 55.0,  # 성별 55%+ = 유의미
    "age": 25.0,     # 연령대 25%+ = 유의미 (전체 7개 연령대 균등 = 14%씩)
}


def belongs_to(seg: dict, demo: dict) -> bool:
    """이 노드가 이 세그먼트에 속하는가.

    우선순위 · 1) 사내 태깅 flag(1/0) 있으면 그거 사용 · 2) 없으면 ratio 임계값 폴백.
    """
    if not demo:
        return False
    # 1) flag 우선 (m_ prefix)
    flag_val = demo.get(seg["flag"])
    if flag_val is not None:
        try:
            if int(flag_val) > 0:
                return True
        except (TypeError, ValueError):
            pass
    # 2) ratio 폴백
    ratio_val = demo.get(seg["ratio"])
    if ratio_val is None:
        return False
    try:
        return float(ratio_val) >= RATIO_FALLBACK_THRESHOLD[seg["kind"]]
    except (TypeError, ValueError):
        return False


# KBF 후보 라벨 · CEP HOW_FEEL 서브그룹에 대응 · MVP는 키워드 기반 단순 매칭
KBF_PATTERNS = {
    "맛·식감": ["맛", "달콤", "쓴맛", "고소", "부드러", "꾸덕", "쫄깃"],
    "가격·가성비": ["가성비", "저렴", "싸", "할인", "가격", "코드", "특가"],
    "품질·평가": ["추천", "후기", "리뷰", "평점", "베스트", "순위", "인기"],
    "효능·기능": ["효능", "효과", "기능", "성분", "함량", "함유", "영양"],
    "안전·부작용": ["부작용", "안전", "우려", "위험", "안좋", "단점", "실패"],
    "다이어트·체중": ["다이어트", "감량", "살빼", "체중", "칼로리", "저칼로리"],
    "간편·편의": ["간편", "쉬운", "만들기", "간식", "밀박스", "먹는법"],
    "브랜드·정보": ["나무위키", "뜻", "종류", "차이", "비교"],
}


def classify_kbf(keyword: str) -> list[str]:
    """간이 KBF 분류 · 정규식 기반 · MVP용 · 나중에 LLM 분류로 대체 가능.

    매칭 안 되는 키워드는 · 빈 리스트 · KBF 분석에서 제외 (기타 없음).
    """
    labels = []
    for label, patterns in KBF_PATTERNS.items():
        if any(p in keyword for p in patterns):
            labels.append(label)
    return labels


def compute_insights(segments: list, kbf_by_seg: dict, cross: list) -> list[dict]:
    """조사원 자동 인사이트 3~5개 생성."""
    insights = []
    total_vol = sum(s["total_volume"] for s in segments) or 1

    # 1. 세그먼트 지배
    gender_segs = [s for s in segments if s["kind"] == "gender"]
    if gender_segs:
        top_gender = max(gender_segs, key=lambda s: s["total_volume"])
        share = top_gender["total_volume"] / (sum(g["total_volume"] for g in gender_segs) or 1) * 100
        insights.append({
            "kind": "segment_dominance",
            "title": f"성별 지배 · {top_gender['label']} {share:.0f}%",
            "body": f"{top_gender['label']} 검색이 성별 태그 노드 볼륨의 {share:.0f}%를 차지 · 크리에이티브·인플루언서 우선 타겟",
        })

    age_segs = [s for s in segments if s["kind"] == "age"]
    if age_segs:
        top_age = max(age_segs, key=lambda s: s["total_volume"])
        share_age = top_age["total_volume"] / (sum(a["total_volume"] for a in age_segs) or 1) * 100
        insights.append({
            "kind": "segment_dominance",
            "title": f"핵심 연령대 · {top_age['label']} {share_age:.0f}%",
            "body": f"{top_age['label']}이 연령 태그 노드 볼륨 상위 · 이 세그먼트 KBF·인텐트 딥다이브 우선",
        })

    # 2. 기회 공백 · 볼륨 극소 세그먼트
    small_segs = [s for s in age_segs if s["total_volume"] > 0 and s["total_volume"] < sum(a["total_volume"] for a in age_segs) * 0.05]
    if small_segs:
        s = min(small_segs, key=lambda x: x["total_volume"])
        insights.append({
            "kind": "opportunity",
            "title": f"미커버 세그먼트 · {s['label']}",
            "body": f"{s['label']} 볼륨이 전체 5% 미만 · 대형 브랜드 놓친 진입 기회 검토 대상",
        })

    # 3. KBF 격차
    if kbf_by_seg:
        # 최고 편익 요인 (전체 세그먼트 합)
        kbf_agg = {}
        for seg_kbfs in kbf_by_seg.values():
            for k in seg_kbfs:
                kbf_agg[k["label"]] = kbf_agg.get(k["label"], 0) + k["volume"]
        if kbf_agg:
            top_kbf = max(kbf_agg.items(), key=lambda x: x[1])
            insights.append({
                "kind": "kbf_gap",
                "title": f"KBF 지배 · {top_kbf[0]}",
                "body": f"'{top_kbf[0]}' 편익이 전체 KBF 볼륨 상위 · 크리에이티브 소구점으로 최우선",
            })

    return insights


def prepare(category: str, gl: str, api_key: str) -> dict:
    """B-1 데이터 준비 · schema.json 부합 dict 반환."""
    client = DaasClient(api_key)

    # 1. cluster_finder
    cf = cluster_finder.fetch(client, category, gl=gl, limit=5000, hop=2)
    if cf.get("result") != "OK":
        raise RuntimeError(f"cluster_finder 실패 · {cf.get('reason')}")

    all_kws = cluster_finder.unique_keywords(cf)
    cost_cf = cf.get("cost_detail", {}).get("total_cost", 0)

    # 2. keyword_info(all) · 볼륨·인구·인텐트 조회
    info_list, cost_ki = keyword_info.fetch_all(client, all_kws, gl=gl, data_type="all")
    info_by_kw = keyword_info.index_by_keyword(info_list)

    # volume은 keyword_info에서 · ads_metrics.volume_avg
    kw2vol = {}
    for kw in all_kws:
        info = info_by_kw.get(kw, {}) or {}
        ads = info.get("ads_metrics") or {}
        kw2vol[kw] = int(ads.get("volume_avg") or 0)

    # 3. 세그먼트별 노드·볼륨 집계
    segments_out = []
    for seg in SEGMENTS:
        seg_nodes = []
        for kw in all_kws:
            info = info_by_kw.get(kw)
            demo = (info or {}).get("demography")
            if belongs_to(seg, demo):
                seg_nodes.append(kw)
        total_vol = sum(kw2vol.get(k, 0) for k in seg_nodes)
        segments_out.append({
            "key": seg["key"],
            "label": seg["label"],
            "kind": seg["kind"],
            "keyword_count": len(seg_nodes),
            "total_volume": total_vol,
        })
        # for later use
        seg["_nodes"] = seg_nodes

    # share_pct · 같은 kind 내 합계 기준
    for kind in ("gender", "age"):
        kind_total = sum(s["total_volume"] for s in segments_out if s["kind"] == kind) or 1
        for s in segments_out:
            if s["kind"] == kind:
                s["share_pct"] = round(s["total_volume"] / kind_total * 100, 1)

    # 4. 세그먼트별 TOP 키워드
    top_by_seg = {}
    for seg in SEGMENTS:
        kws = seg.get("_nodes", [])
        sorted_kws = sorted(kws, key=lambda k: -kw2vol.get(k, 0))[:10]
        top_by_seg[seg["key"]] = [
            {
                "keyword": k,
                "volume": kw2vol.get(k, 0),
                "trend": (info_by_kw.get(k, {}) or {}).get("ads_metrics", {}).get("volume_trend", 0) or 0,
            }
            for k in sorted_kws
        ]

    # 5. 세그먼트별 KBF 집계
    kbf_by_seg = {}
    for seg in SEGMENTS:
        agg = {}
        for kw in seg.get("_nodes", []):
            vol = kw2vol.get(kw, 0)
            for label in classify_kbf(kw):
                if label not in agg:
                    agg[label] = {"volume": 0, "keyword_count": 0}
                agg[label]["volume"] += vol
                agg[label]["keyword_count"] += 1
        sorted_kbfs = sorted(
            [{"label": k, **v} for k, v in agg.items()],
            key=lambda x: -x["volume"],
        )
        kbf_by_seg[seg["key"]] = sorted_kbfs

    # 6. 성별 × 연령 매트릭스
    cross = []
    for g in ["female", "male"]:
        g_seg = next(s for s in SEGMENTS if s["key"] == g)
        g_set = set(g_seg.get("_nodes", []))
        for a in ["a13", "a20", "a25", "a30", "a40", "a50"]:
            a_seg = next(s for s in SEGMENTS if s["key"] == a)
            a_set = set(a_seg.get("_nodes", []))
            inter = list(g_set & a_set)
            inter_sorted = sorted(inter, key=lambda k: -kw2vol.get(k, 0))
            cross.append({
                "gender": g,
                "age": a,
                "volume": sum(kw2vol.get(k, 0) for k in inter),
                "keyword_count": len(inter),
                # 전체 키워드 · 볼륨 순 · 프론트에서 스크롤로 확인
                "top_keywords": [
                    {"keyword": k, "volume": kw2vol.get(k, 0)} for k in inter_sorted
                ],
            })

    # 7. 인사이트
    insights = compute_insights(segments_out, kbf_by_seg, cross)

    return {
        "meta": {
            "category": category,
            "gl": gl,
            "total_nodes": len(all_kws),
            "total_keywords_with_demo": sum(
                1 for kw in all_kws if (info_by_kw.get(kw, {}) or {}).get("demography")
            ),
            "total_credits": cost_cf + cost_ki,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "segments": segments_out,
        "top_keywords_by_segment": top_by_seg,
        "kbf_by_segment": kbf_by_seg,
        "cross_matrix": {"gender_x_age": cross},
        "insights": insights,
    }
