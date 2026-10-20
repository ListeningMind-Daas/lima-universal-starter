#!/usr/bin/env python3
"""예상 크레딧 산출 — 호출 계획을 운영 API 명세의 단가로 환산한다 (호출 전 고지·예산 확인용).

단가는 이 파일에 없다. lima-agents/api/spec.py 가 운영 OpenAPI(https://listeningmind-data-api.ascentlab.io/openapi.json)의
*Cost 스키마에서 읽는다(2026-10-13). 실제 청구는 응답 cost_detail.total_cost 가 최종 기준이다.
  LM_API_SPEC=pinned (기본 · 고정 사본) | live (운영 명세를 받는다) | auto (live, 실패 시 고정 사본 + 경고)
  CLI 는 --spec 으로 고른다 (기본 auto)

과금 공식 = 입력 단가 × 입력 수 + 출력 단가 × 출력 수 (도구별 입력·출력 단위는 아래 UNITS)
  cluster_finder · path_finder   입력 = 시드 1 · 출력 = 반환 고유 키워드 수 (cluster_finder 의 limit 은 관계 수 상한 →
                                 상한 견적은 unique_keywords = limit + 1 · 저장 응답 58건 모두 이하 · 2026-10-13)
  */keyword_list · intent_finder 입력 = 시드 1 · 출력 = 반환 키워드 수 (limit 100 이면 상한 100)
  keyword_info                   입력 = 키워드 수 · data_type 별 단가 (all · ads_info · ads_metrics)
  serp                           입력 = 키워드 수
  trend_finder                   입력 = 시드 1 · 출력 = 반환 이슈 수 (상한 limit)

사용:
  python3 credit_estimate.py --preset standard
  python3 credit_estimate.py --preset demand          # 수요 잡 파이프라인 (demand-lite · demand · demand-deep)
  python3 credit_estimate.py --intent 3 --kw-all 800 --cluster-kws 1200 --path 2 --path-kws 170 --budget 60000
  python3 credit_estimate.py --plan plan.json        # {"calls":[{"tool":"cluster_finder","unique_keywords":1000}, ...]}
"""
from __future__ import annotations

import argparse, importlib.util, json, os, sys
from pathlib import Path


def _load_spec_module():
    """옆 스킬 lima-agents/api/spec.py — 모든 배포본이 두 스킬을 함께 싣는다(starter·codex·gemini·플러그인)."""
    here = Path(__file__).resolve()
    for base in (here.parents[2], here.parents[3] / "skills"):
        f = base / "lima-agents" / "api" / "spec.py"
        if f.is_file():
            s = importlib.util.spec_from_file_location("lm_api_spec", f)
            m = importlib.util.module_from_spec(s)
            s.loader.exec_module(m)
            return m
    raise SystemExit("lima-agents/api/spec.py 를 찾지 못했다 — 단가는 운영 API 명세에서만 읽는다(lima-agents 스킬을 함께 설치)")


SPEC = _load_spec_module()

# 도구 → (명세 경로, 입력 수, 출력 수). 입력·출력 수는 호출 계획 필드에서 읽는다.
UNITS = {
    "cluster_finder":              ("/cluster_finder",              lambda k: 1, lambda k: k.get("unique_keywords", 0)),
    "cluster_finder/keyword_list": ("/cluster_finder/keyword_list", lambda k: 1, lambda k: k.get("returned", k.get("limit", 100))),
    "intent_finder":               ("/intent_finder/keyword_list",  lambda k: 1, lambda k: k.get("returned", k.get("limit", 100))),
    "intent_finder/keyword_list":  ("/intent_finder/keyword_list",  lambda k: 1, lambda k: k.get("returned", k.get("limit", 100))),
    "path_finder":                 ("/path_finder",                 lambda k: 1, lambda k: k.get("unique_keywords", 0)),
    "path_finder/keyword_list":    ("/path_finder/keyword_list",    lambda k: 1, lambda k: k.get("returned", k.get("limit", 100))),
    "keyword_info":                ("/keyword_info",                lambda k: k.get("keywords", 0), lambda k: 0),
    "serp":                        ("/serp",                        lambda k: k.get("keywords", 0), lambda k: 0),
    "trend_finder":                ("/trend_finder/issue_list",     lambda k: 1, lambda k: k.get("returned", k.get("limit", 50))),
}

PRESETS = {
    "quick":    dict(intent=1, intent_limit=100, kw_ads=200, kw_all=0, cluster_list=300, cluster_kws=0, path=0, path_kws=0, serp=0),
    "standard": dict(intent=2, intent_limit=100, kw_ads=0, kw_all=500, cluster_list=0, cluster_kws=1000, path=1, path_kws=170, serp=0),
    "deep":     dict(intent=3, intent_limit=100, kw_ads=0, kw_all=3000, cluster_list=0, cluster_kws=5000, path=4, path_kws=170, serp=0),
    # 수요 잡 파이프라인(collect_demand.py · references/demand-pipeline.md) — 프로브=시드 수 · kw_ads=시드 볼륨+유니크 ads_info
    # [가정] 유니크 = 시드당 신규 70 + 구조 탐색 시드당 120 · 실제 유니크 수가 나오면 collect 가 다시 낸다
    "demand-lite": dict(kw_ads_type="ads_info", intent=12, intent_limit=100, kw_ads=12 + 12 * 70, kw_all=0, cluster_list=0, cluster_kws=0, path=0, path_kws=170, serp=0),
    "demand":      dict(kw_ads_type="ads_info", intent=24, intent_limit=100, kw_ads=24 + 24 * 70 + 5 * 120, kw_all=0, cluster_list=150, cluster_list_calls=5,
                        cluster_kws=0, path=0, path_kws=170, serp=0),
    "demand-deep": dict(kw_ads_type="ads_info", intent=40, intent_limit=100, kw_ads=40 + 40 * 70 + 10 * 120, kw_all=0, cluster_list=150, cluster_list_calls=10,
                        cluster_kws=0, path=0, path_kws=170, serp=0),
}


def cost(tool: str, spec: dict | None = None, **k) -> int:
    """호출 1건의 예상 크레딧 — 단가는 운영 API 명세(spec 생략 시 LM_API_SPEC 기본 출처)."""
    if tool == "cluster_finder" and "nodes" in k:
        raise ValueError("cluster_finder 의 nodes 는 폐기 — unique_keywords(반환 고유 키워드 수)로 넘긴다")
    if tool not in UNITS:
        raise ValueError(f"unknown tool {tool}")
    path, n_in, n_out = UNITS[tool]
    data_type = k.get("data_type", "all") if tool == "keyword_info" else None
    rin, rout = SPEC.rate(spec or SPEC.default(), path, data_type)
    return rin * int(n_in(k)) + rout * int(n_out(k))


def from_flags(a) -> list[dict]:
    calls = []
    for _ in range(a.intent):
        calls.append({"tool": "intent_finder", "limit": a.intent_limit})
    if a.kw_ads:
        calls.append({"tool": "keyword_info", "data_type": getattr(a, "kw_ads_type", "ads_metrics"), "keywords": a.kw_ads})
    if a.kw_all:
        calls.append({"tool": "keyword_info", "data_type": "all", "keywords": a.kw_all})
    for _ in range(a.cluster_list_calls if a.cluster_list else 0):
        calls.append({"tool": "cluster_finder/keyword_list", "returned": a.cluster_list})
    if a.cluster_kws:
        calls.append({"tool": "cluster_finder", "unique_keywords": a.cluster_kws})
    for _ in range(a.path):
        calls.append({"tool": "path_finder", "unique_keywords": a.path_kws})
    if a.serp:
        calls.append({"tool": "serp", "keywords": a.serp})
    for _ in range(a.trend):
        calls.append({"tool": "trend_finder", "limit": a.trend_limit})
    return calls


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preset", choices=PRESETS)
    ap.add_argument("--plan", help="JSON 파일 {calls:[...]} (tool별 필드: keywords/data_type/limit/returned/unique_keywords — cluster_finder·path_finder 는 반환 고유 키워드 수)")
    ap.add_argument("--intent", type=int, default=0); ap.add_argument("--intent-limit", type=int, default=100)
    ap.add_argument("--kw-ads", type=int, default=0); ap.add_argument("--kw-all", type=int, default=0)
    ap.add_argument("--cluster-list", type=int, default=0, help="cluster_finder/keyword_list 호출당 반환 수")
    ap.add_argument("--cluster-list-calls", type=int, default=1); ap.add_argument("--cluster-kws", type=int, default=0, help="cluster_finder 반환 고유 키워드 수 (상한 견적은 limit+1)")
    ap.add_argument("--path", type=int, default=0); ap.add_argument("--path-kws", type=int, default=170)
    ap.add_argument("--serp", type=int, default=0)
    ap.add_argument("--trend", type=int, default=0, help="trend_finder 시드 수"); ap.add_argument("--trend-limit", type=int, default=50)
    ap.add_argument("--budget", type=int, default=0, help="사용자 상한 — 초과 시 exit 2")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--spec", choices=["auto", "live", "pinned"], default="auto",
                    help="단가 출처 — auto(운영 명세, 실패 시 고정 사본) · live · pinned")
    a = ap.parse_args()
    spec = SPEC.load(a.spec)

    if a.plan:
        calls = json.load(open(a.plan, encoding="utf8"))["calls"]
    elif a.preset:
        p = PRESETS[a.preset]
        for k, v in p.items():
            setattr(a, k, v)
        calls = from_flags(a)
    else:
        calls = from_flags(a)
    if not calls:
        ap.error("--preset, --plan 또는 호출 플래그 중 하나 필요")

    rows, total = [], 0
    for c in calls:
        k = {x: y for x, y in c.items() if x != "tool"}
        v = cost(c["tool"], spec=spec, **k)
        total += v
        rows.append({"tool": c["tool"], "params": k, "cost": v})
    out = {"calls": rows, "total": total, "budget": a.budget or None,
           "spec": {"version": spec["info"]["version"], "pinned_at": spec.get("pinned_at"), "source": spec.get("source")},
           "over_budget": bool(a.budget and total > a.budget)}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print(f"{'커넥터':30} {'파라미터':40} {'예상':>9}")
        print("-" * 82)
        for r in rows:
            print(f"{r['tool']:30} {json.dumps(r['params'], ensure_ascii=False):40} {r['cost']:>9,}")
        print("-" * 82)
        print(f"{'합계 (예상 · 실소비는 응답 cost_detail.total_cost)':71} {total:>9,}")
        print(f"단가 출처: 운영 API 명세 {spec['info']['version']} ({spec.get('pinned_at')})")
        if a.budget:
            print(f"예산 {a.budget:,} → {'초과 ⚠ 호출 전 범위 축소 필요' if out['over_budget'] else '이내'}")
    sys.exit(2 if out["over_budget"] else 0)


if __name__ == "__main__":
    main()
