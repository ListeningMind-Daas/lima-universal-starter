#!/usr/bin/env python3
"""수요·트렌드 잡(잡 1) 수집 파이프라인 — 시드 레이어 설계 → 검증·확장 → 구조 탐색 → 정리 → 월별 수집 → 중복 제거 → 지표.

계약: references/demand-pipeline.md (D1~D8). 모든 단계는 분석 폴더에 입력·원본 응답·출력을 남기고,
--replay 면 저장본만 읽는다(0크레딧). 호출 전에는 예상 크레딧을 출력하고 --budget 을 넘으면 멈춘다.

  plan    D1  seed_layer_config.json 검사 — 층별 비율·총수 경고, 예상 크레딧        0크레딧
  expand  D2  시드 검증·연관어(seed_check --dump 재사용) · D3 시드 볼륨 · D4 구조 탐색 · D5 유니크 정리
  collect D6  유니크 전체 keyword_info(ads_info) — 월평균 + 48개월 월별(키워드당 1)
  build   D7  노이즈·브랜드·중복 제거(같은 월별 계열·구글 공유 변형) → D8 지표 core/demand_metrics.json   0크레딧
  report      core/demand_metrics.json → render_report.py 입력 뼈대(수치 필드만)            0크레딧
  rising  D9  키워드 단위 라이징(최근 3개월 vs 전년 동기) → core/rising.json                0크레딧
  explain D10 라이징 원인 — 구별 토큰 trend_finder + 품목 사후 필터 → core/rising_explained.json
  share       잡 4 브랜드·판매 채널·무브랜드 검색 점유 + 미등재 후보 → core/brand_share.json   0크레딧
  content     잡 5 목적별 검색어 묶음 · --serp-top N 구글 SERP(연관 질문·AI 개요·사이트) → core/content.json

예:
  python3 scripts/collect_demand.py plan    --run 99_Scratch/ebike-demand
  python3 scripts/collect_demand.py expand  --run 99_Scratch/ebike-demand --budget 8000
  python3 scripts/collect_demand.py collect --run 99_Scratch/ebike-demand --budget 5000
  python3 scripts/collect_demand.py build   --run 99_Scratch/ebike-demand
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SKILLS_ROOT = SKILL.parent
LIMA = SKILLS_ROOT / "lima-agents"
sys.path.insert(0, str(LIMA))
from lib import series_dedup as sd                       # noqa: E402

DICT = SKILL / "dictionary" / "E0_사전.csv"

# 층 정의 — 필수 4층(M1 문제 · M2 시장 · M3 브랜드 · M4 대체재) + 재화 유형별 동적 층
LAYERS = ("M1_problem", "M2_market", "M3_supply", "M4_substitute")
CONTEXT_LAYERS = ("M1_problem", "M4_substitute")      # 헤드라인 수요에서 빼고 맥락으로 보고하는 층
# 유니크 정리 소스 우선순위 — 먼저 들어온 소스를 남긴다 (seed 는 항상 최우선)
SOURCE_ORDER = ("seed", "intent:M2_market", "intent:M1_problem", "intent:M4_substitute", "intent:dynamic",
                "intent:M3_supply", "cluster")
RULES = {"M1_min": 0.20, "M2_min": 0.10, "M3_max": 0.40, "M4_min": 0.10, "total_min": 12, "total_rec": 20}
# 단가는 credit_estimate.py 한 곳에서만 읽는다(단가 변경 시 RATES/cost 만 고친다)
sys.path.insert(0, str(HERE))
from credit_estimate import cost as unit_cost              # noqa: E402

PROBE_MAX = unit_cost("intent_finder/keyword_list", returned=100)       # 시드당 상한(반환 100)
PROBE_MEASURED = 106                                                     # 시드당 실측 평균(반환이 100보다 적은 경우가 많다)
PRESETS = {
    "demand-lite": {"cluster_top": 0, "screen_threshold": 100},
    "demand": {"cluster_top": 5, "screen_threshold": 30},
    "demand-deep": {"cluster_top": 10, "screen_threshold": 10},
}


# ───────────────────────── 공통
def now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def slug(s: str) -> str:
    """seed_check --dump 파일명 규칙과 같게 — 다르면 저장본을 못 찾아 같은 프로브를 다시 산다."""
    return re.sub(r"[^0-9A-Za-z가-힣]+", "_", s)


def rjson(p: Path):
    return json.loads(p.read_text(encoding="utf8"))


def wjson(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf8")


def read_csv(p: Path, enc: str = "utf-8-sig") -> list[dict]:
    with p.open(encoding=enc, newline="") as f:
        return list(csv.DictReader(f))


def config(run: Path) -> dict:
    p = run / "seed_layer_config.json"
    if not p.exists():
        raise SystemExit(f"{p} 없음 — D1 시드 레이어 설계를 먼저 쓴다 (references/demand-pipeline.md §D1)")
    return rjson(p)


def seeds_by_layer(cfg: dict) -> list[tuple[str, str]]:
    """[(시드, 층)] — 동적 층은 'dynamic:<이름>'. 같은 시드가 여러 층이면 먼저 나온 층."""
    out, seen = [], set()
    layers = cfg.get("layers") or {}
    for name in LAYERS:
        for s in layers.get(name) or []:
            if s.strip() and sd.canon(s) not in seen:
                seen.add(sd.canon(s)); out.append((s.strip(), name))
    for dname, items in (layers.get("dynamic") or {}).items():
        for s in items or []:
            if s.strip() and sd.canon(s) not in seen:
                seen.add(sd.canon(s)); out.append((s.strip(), f"dynamic:{dname}"))
    return out


def layer_group(layer: str) -> str:
    return "dynamic" if layer.startswith("dynamic") else layer


def ledger_add(run: Path, step: str, tool: str, params: dict, cost, source: str = "live", raw=None) -> None:
    """호출 원장 — 리포트의 호출 순서 · 호출 로그 · 비용 보고서(render_report.py)가 여기서 만들어진다.
    raw 는 원본 응답 파일(분석 폴더 기준) — 호출 로그에서 숫자를 원본까지 따라가게 한다."""
    p = run / "ledger.json"
    led = rjson(p) if p.exists() else []
    rec = {"at": now(), "step": step, "tool": tool, "params": params, "cost": cost, "source": source}
    if raw:
        rec["raw"] = raw if isinstance(raw, str) else " · ".join(raw)
    led.append(rec)
    wjson(p, led)


def api_client():
    from api.client import DaasClient, MissingApiKey      # noqa: PLC0415
    try:
        return DaasClient()                               # 키: api.client.resolve_api_key()
    except MissingApiKey as e:
        raise SystemExit(str(e)) from None


def budget_check(est: int, budget, what: str) -> None:
    print(f"예상 크레딧 · {what} · 약 {est:,}")
    if budget is not None and est > budget:
        raise SystemExit(f"예산 초과 — 예상 {est:,} > --budget {budget:,}. 범위를 줄이거나 상한을 올린다(사용자 확인).")


def load_dict(extra: list[str]) -> tuple[dict, set]:
    """E0 사전 → (브랜드 별칭→라벨, 노이즈 표기 집합). 분석별 사전(--dict)을 덧붙인다."""
    brands, noise = {}, set()
    files = [DICT, *[Path(x) for x in extra or []]]
    for f in files:
        if not f.is_file():
            continue
        for r in read_csv(f, "utf8"):
            forms = [r.get("label") or ""] + [a.strip() for a in (r.get("aliases") or "").split("|")]
            cls = (r.get("class") or "").strip()
            if cls in ("Brand", "SubBrand") and "결합형만" in (r.get("note") or ""):
                forms = forms[1:]          # 라벨 단독은 매칭하지 않는다 — 단독이 다른 뜻(자동차 브랜드·인물)일 때
            forms = [x for x in forms if x.strip()]
            if cls in ("Brand", "SubBrand"):
                for x in forms:
                    if len(x) >= 2:
                        brands[x.lower()] = r["label"]
            elif cls == "Noise":
                noise |= {x.lower() for x in forms}
    return brands, noise


def load_channels(extra: list[str]) -> dict:
    """E0 Channel/Reviewer 행 → 별칭→"종류\t라벨"(channel=판매·중개 채널 · community=커뮤니티·리뷰어). 브랜드가 아니라 따로 센다."""
    out = {}
    for f in [DICT, *[Path(x) for x in extra or []]]:
        if not f.is_file():
            continue
        for r in read_csv(f, "utf8"):
            cls = (r.get("class") or "").strip()
            if cls in ("Channel", "Reviewer"):
                for x in [r.get("label") or ""] + [a.strip() for a in (r.get("aliases") or "").split("|")]:
                    if len(x.strip()) >= 2:
                        out[x.strip().lower()] = ("channel" if cls == "Channel" else "community") + "\t" + r["label"]
    return out


def noise_regex(gl: str):
    """seed_check 동결본의 노이즈 패턴(adapter A2 → 내장 기본)을 그대로 쓴다 — 판정 규칙을 한 곳에 둔다."""
    sys.path.insert(0, str(HERE))
    import _seed_check_legacy as legacy                   # noqa: PLC0415
    return legacy.load_noise_re(gl)[0]


def brand_of(kw: str, brands: dict) -> str:
    low = kw.lower()
    for a, label in sorted(brands.items(), key=lambda x: -len(x[0])):
        if re.search(r"(?<![a-z가-힣])" + re.escape(a) + r"(?![a-z])", low):
            return label
    return ""


def dict_extra(run: Path, a) -> list[str]:
    return list(a.dict or []) + [str(p) for p in sorted(run.glob("E0_*.csv"))]


# ───────────────────────── D1 plan
def cmd_plan(a) -> int:
    run = Path(a.run)
    cfg = config(run)
    pairs = seeds_by_layer(cfg)
    n = len(pairs) or 1
    cnt = {k: 0 for k in (*LAYERS, "dynamic")}
    for _, layer in pairs:
        cnt[layer_group(layer)] += 1
    warns = []
    if cnt["M1_problem"] / n < RULES["M1_min"]:
        warns.append(f"WARNING-SEED-M1: M1 문제 층 {cnt['M1_problem']}개({cnt['M1_problem']/n:.0%}) — 20% 이상 권장. 상위 수요(문제·욕구 표현)가 빠진다")
    if cnt["M2_market"] / n < RULES["M2_min"]:
        warns.append(f"WARNING-SEED-M2: M2 시장 층 {cnt['M2_market']}개 — 10% 이상 권장. 시장 경계 기준점이 약하다")
    if cnt["M3_supply"] / n > RULES["M3_max"]:
        warns.append(f"WARNING-SEED-M3-OVER: M3 브랜드 층 {cnt['M3_supply']/n:.0%} — 40% 이하 권장. 공급자 언어로 기운다")
    if cnt["M4_substitute"] / n < RULES["M4_min"]:
        warns.append(f"WARNING-SEED-M4: M4 대체재 층 {cnt['M4_substitute']}개 — 10% 이상 권장. 시장 경계가 좁게 그려진다")
    if len(pairs) < RULES["total_min"]:
        warns.append(f"WARNING-SEED-TOTAL: 시드 {len(pairs)}개 — 최소 {RULES['total_min']} · 권장 {RULES['total_rec']}~30")
    if not cfg.get("anchor"):
        warns.append("WARNING-ANCHOR: anchor 어휘가 없다 — 확장어의 카테고리 적합 판정이 시드 토큰에만 기댄다")
    preset = PRESETS[cfg.get("preset") or "demand"]
    probe_hi = len(pairs) * PROBE_MAX
    probe_lo = len(pairs) * PROBE_MEASURED
    cl = preset["cluster_top"] * unit_cost("cluster_finder/keyword_list", returned=int(cfg.get("cluster_limit") or 150))
    uniq_guess = int(len(pairs) * 70 + preset["cluster_top"] * 120)   # [가정] 시드당 신규 70 · 클러스터당 120
    est = {"D2_probe": [probe_lo, probe_hi], "D3_seed_volume": len(pairs), "D4_cluster_list_max": cl,
           "D6_ads_info_guess": uniq_guess,
           "total_range": [probe_lo + len(pairs) + cl // 2 + uniq_guess, probe_hi + len(pairs) + cl + uniq_guess],
           "basis": "[파생] 단가 표 × [가정] 반환 수 — D5 뒤 collect 가 실제 유니크 수로 다시 낸다"}
    plan = {"at": now(), "target": cfg.get("target"), "gl": cfg.get("gl", "kr"), "preset": cfg.get("preset") or "demand",
            "seeds": len(pairs), "by_layer": cnt, "warnings": warns, "estimate": est}
    wjson(run / "plan.json", plan)
    print(f"시드 {len(pairs)}개 · " + " · ".join(f"{k} {v}" for k, v in cnt.items()))
    for w in warns:
        print("⚠ " + w)
    print(f"예상 크레딧(범위) · {est['total_range'][0]:,} ~ {est['total_range'][1]:,}  {est['basis']}")
    return 0


# ───────────────────────── D2~D5 expand
def _probe(run: Path, cfg: dict, pairs, a) -> dict:
    """seed_check --dump 로 시드별 프로브 저장본을 만든다(없는 시드만). 판정·연관어는 저장본에서 읽는다."""
    pdir = run / "probe"
    pdir.mkdir(parents=True, exist_ok=True)
    missing = [s for s, _ in pairs if not (pdir / f"{slug(s)}.json").exists()]
    if missing and a.replay:
        print(f"⚠ replay — 프로브 저장본 없는 시드 {len(missing)}개는 건너뛴다: {', '.join(missing[:8])}")
    elif missing:
        budget_check(len(missing) * PROBE_MAX, a.budget, f"D2 프로브 {len(missing)}시드(상한)")
        cmd = [sys.executable, str(HERE / "seed_check.py"), "--gl", cfg.get("gl", "kr"), "--dump", str(pdir), "--json",
               "--skip-brand-gate", *(["--anchor", ",".join(cfg["anchor"])] if cfg.get("anchor") else []),
               *sum((["--dict", d] for d in dict_extra(run, a)), []), *missing]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 and not any((pdir / f"{slug(s)}.json").exists() for s in missing):
            raise SystemExit(f"seed_check 실패({r.returncode}): {r.stderr[-800:]}")
        cost = 0
        for s in missing:
            f = pdir / f"{slug(s)}.json"
            if f.exists():
                cost += ((rjson(f).get("cost_detail") or {}).get("total_cost") or 0)
        ledger_add(run, "D2", "intent_finder/keyword_list", {"seeds": missing, "via": "seed_check --dump"}, cost,
                   raw=[str((pdir / f"{slug(s)}.json").relative_to(run)) for s in missing if (pdir / f"{slug(s)}.json").exists()])
        print(f"D2 프로브 {len(missing)}시드 · {cost:,}크레딧")
    out = {}
    for s, layer in pairs:
        f = pdir / f"{slug(s)}.json"
        if f.exists():
            d = rjson(f)
            m = d.get("metrics") or {}
            v = m.get("verdict") or "통과"
            # 브랜드 층(M3)은 제품 앵커처럼 적합률을 면제한다 — 연관어가 모델명이라 카테고리 어휘가 거의 없다
            # (seed-verification.md §2 제품 앵커 규칙). 노이즈율 교체·사전 폐기는 그대로 둔다.
            if layer == "M3_supply" and v.startswith("시드 교체") and m.get("reason") == "적합률":
                v = f"통과(브랜드 층 — 적합률 {m.get('fit_rate')} 면제)"
            out[s] = {"layer": layer, "verdict": v, "queries": d.get("queries") or []}
    return out


def _kw_info(client, kws: list[str], gl: str, data_type: str) -> list[dict]:
    from api import keyword_info                          # noqa: PLC0415
    data, cost = keyword_info.fetch_all(client, kws, gl=gl, data_type=data_type)
    return data, cost


def _seed_volume(run: Path, cfg: dict, seeds: list[str], a) -> dict:
    """시드 월평균(ads_metrics) — 저장본에 없는 시드만 잰다(M3 를 나중에 채워도 새 시드만 과금)."""
    p = run / "api" / "seed_volume.json"
    d = rjson(p) if p.exists() else {"request": [], "data": [], "total_cost": 0}
    todo = [s for s in seeds if s not in set(d.get("request") or [])]
    if todo and a.replay:
        print(f"⚠ replay — 시드 볼륨 저장본에 없는 {len(todo)}개는 구조 탐색 대상에서 빠진다")
    elif todo:
        budget_check(unit_cost("keyword_info", data_type="ads_metrics", keywords=len(todo)), a.budget, f"D3 시드 볼륨 {len(todo)}개")
        data, cost = _kw_info(api_client(), todo, cfg.get("gl", "kr"), "ads_metrics")
        d = {"at": now(), "request": (d.get("request") or []) + todo, "data_type": "ads_metrics",
             "data": (d.get("data") or []) + data, "total_cost": (d.get("total_cost") or 0) + cost}
        wjson(p, d)
        ledger_add(run, "D3", "keyword_info", {"n": len(todo), "data_type": "ads_metrics"}, cost, raw="api/seed_volume.json")
    joined, _, _ = join_rows(d.get("data") or [], d.get("request") or [])
    return {k: float(((v.get("ads_metrics") or {}).get("volume_avg")) or 0) for k, v in joined.items() if k in seeds}


def _cluster(run: Path, cfg: dict, targets: list[str], a) -> dict:
    cdir = run / "cluster"
    limit = int(cfg.get("cluster_limit") or 150)
    todo = [s for s in targets if not (cdir / f"{slug(s)}.json").exists()]
    if todo and not a.replay:
        budget_check(len(todo) * unit_cost("cluster_finder/keyword_list", returned=limit), a.budget,
                     f"D4 구조 탐색 {len(todo)}시드 · hop 1 · limit {limit}(상한)")
        from api import cluster_finder                    # noqa: PLC0415
        client = api_client()
        for s in todo:
            r = cluster_finder.fetch_keyword_list(client, s, gl=cfg.get("gl", "kr"), limit=limit, hop=1)
            wjson(cdir / f"{slug(s)}.json", {"seed": s, "at": now(), "hop": 1, "limit": limit, **r})
            cost = (r.get("cost_detail") or {}).get("total_cost")
            ledger_add(run, "D4", "cluster_finder/keyword_list", {"seed": s, "hop": 1, "limit": limit}, cost,
                       raw=f"cluster/{slug(s)}.json")
            print(f"D4 {s} · {cost}크레딧")
    out = {}
    for s in targets:
        f = cdir / f"{slug(s)}.json"
        if f.exists():
            data = rjson(f).get("data") or []
            out[s] = [x if isinstance(x, str) else (x.get("keyword") or "") for x in data]
    return out


def cmd_expand(a) -> int:
    run = Path(a.run)
    cfg = config(run)
    gl = cfg.get("gl", "kr")
    pairs = seeds_by_layer(cfg)
    preset = PRESETS[cfg.get("preset") or "demand"]
    probes = _probe(run, cfg, pairs, a)
    passed = [s for s, _ in pairs if s in probes and not probes[s]["verdict"].startswith(("시드 교체", "폐기"))]
    for s in passed:
        if probes[s]["verdict"] != "통과":
            print(f"· {s}: {probes[s]['verdict']}")
    rejected = {s: (probes[s]["verdict"] if s in probes else "프로브 없음(사전 Noise 차단 또는 replay 누락)")
                for s, _ in pairs if s not in passed}
    vols = _seed_volume(run, cfg, passed, a) if passed else {}
    layer_of = dict(pairs)
    top_n = int(a.cluster_top if a.cluster_top is not None else preset["cluster_top"])
    cand = [s for s in passed if layer_group(layer_of[s]) in ("M2_market", "dynamic") and vols.get(s, 0) >= a.min_seed_volume]
    targets = sorted(cand, key=lambda s: -vols.get(s, 0))[:top_n]
    clusters = _cluster(run, cfg, targets, a) if targets else {}

    # D5 유니크 정리
    brands, noise_words = load_dict(dict_extra(run, a))
    nre = noise_regex(gl)
    anchor = [t.lower() for t in cfg.get("anchor") or [] if t]
    seen: dict[str, dict] = {}

    def add(kw: str, source: str, layer: str, origin: str):
        kw = (kw or "").strip()
        if not kw:
            return
        k = sd.canon(kw)
        if k in seen:
            return
        reason = ""
        if source != "seed":
            low = kw.lower()
            if low in noise_words:
                reason = "사전 Noise"
            elif nre.search(low):
                reason = "노이즈 패턴"
            else:
                # anchor 가 있으면 anchor 어휘·등록 브랜드만 적합으로 본다 — 출처 시드 토큰은 프로브 반환어 거의 전부에 있어
                # 걸러내지 못한다. 예외: 대체재 층(M4)은 다른 품목이라 출처 시드 토큰도 적합(맥락 층으로만 집계된다).
                seed_toks = {t for t in re.split(r"\s+", origin.lower()) if len(t) >= 2}
                toks = set(anchor) | (seed_toks if (not anchor or layer == "M4_substitute") else set())
                if toks and not any(t in low for t in toks) and not brand_of(kw, brands):
                    reason = "앵커 무관"
        seen[k] = {"keyword": kw, "key": k, "source": source, "layer": layer, "origin": origin,
                   "excluded_reason": reason}

    for s in passed:
        add(s, "seed", layer_of[s], s)
    order = {src: i for i, src in enumerate(SOURCE_ORDER)}
    probe_items = sorted(((s, probes[s]) for s in passed),
                         key=lambda x: order.get("intent:" + layer_group(x[1]["layer"]), 99))
    for s, p in probe_items:
        for q in p["queries"]:
            add(q, "intent:" + layer_group(p["layer"]), layer_of[s], s)
    for s in targets:
        for q in clusters.get(s, []):
            add(q, "cluster", layer_of[s], s)
    rows = list(seen.values())
    with (run / "unique_keywords.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["keyword", "key", "source", "layer", "origin", "excluded_reason"])
        w.writeheader(); w.writerows(rows)
    summary = {"at": now(), "seeds": len(pairs), "passed": len(passed), "rejected": rejected,
               "seed_volume": vols, "cluster_targets": targets, "unique": len(rows),
               "excluded": sum(1 for r in rows if r["excluded_reason"]),
               "by_source": {src: sum(1 for r in rows if r["source"] == src) for src in SOURCE_ORDER}}
    wjson(run / "expand.json", summary)
    print(f"통과 시드 {len(passed)}/{len(pairs)} · 구조 탐색 {len(targets)}시드 · 유니크 {len(rows):,} "
          f"(제외 표시 {summary['excluded']:,}) → unique_keywords.csv")
    if rejected:
        print("⚠ 교체·폐기 시드: " + ", ".join(f"{k}({v})" for k, v in rejected.items()))
    return 0


# ───────────────────────── D6 collect
def join_rows(data: list[dict], requested: list[str]) -> tuple[dict, list, list]:
    """응답 행을 요청어에 조인 — (요청어→행, 정규화로만 붙은 [(요청, 응답)], 미요청 행)."""
    by_key: dict[str, dict] = {}
    exact = {}
    for it in data or []:
        k = it.get("keyword")
        if k:
            exact.setdefault(k, it)
            by_key.setdefault(sd.canon(k), it)
    out, rematched, used = {}, [], set()
    for q in requested:
        it = exact.get(q)
        if it is None:
            it = by_key.get(sd.canon(q))
            if it is not None:
                rematched.append((q, it.get("keyword")))
        if it is not None:
            out[q] = it
            used.add(id(it))
    unrequested = [it.get("keyword") for it in data or [] if id(it) not in used]
    return out, rematched, unrequested


def cmd_collect(a) -> int:
    run = Path(a.run)
    cfg = config(run)
    gl = cfg.get("gl", "kr")
    uk = run / "unique_keywords.csv"
    if not uk.exists():
        raise SystemExit("unique_keywords.csv 없음 — expand 먼저")
    rows = read_csv(uk)
    targets = [r["keyword"] for r in rows if not r["excluded_reason"] or a.include_excluded]
    adir = run / "api"
    batches = sorted(adir.glob("kwinfo_ads_info_*.json"))
    done = set()
    for b in batches:
        done |= set(rjson(b).get("request") or [])
    todo = [k for k in targets if k not in done]
    if todo and a.replay:
        print(f"⚠ replay — 저장본에 없는 {len(todo):,}개는 미측정으로 둔다")
    elif todo:
        budget_check(unit_cost("keyword_info", data_type="ads_info", keywords=len(todo)), a.budget, f"D6 keyword_info(ads_info) {len(todo):,}개")
        from api import keyword_info                      # noqa: PLC0415
        client = api_client()
        start = len(batches)
        for i in range(0, len(todo), keyword_info.BATCH_SIZE):
            chunk = todo[i:i + keyword_info.BATCH_SIZE]
            r = keyword_info.fetch_batch(client, chunk, gl=gl, data_type="ads_info")
            cost = (r.get("cost_detail") or {}).get("total_cost")
            n = start + i // keyword_info.BATCH_SIZE + 1
            wjson(adir / f"kwinfo_ads_info_{n:03d}.json", {"at": now(), "request": chunk, "data_type": "ads_info", **r})
            ledger_add(run, "D6", "keyword_info", {"n": len(chunk), "data_type": "ads_info", "batch": n}, cost,
                       raw=f"api/kwinfo_ads_info_{n:03d}.json")
            print(f"D6 배치 {n} · {len(chunk):,}개 · {cost}크레딧")
    # 저장본 전체로 조인
    data, requested = [], []
    for b in sorted(adir.glob("kwinfo_ads_info_*.json")):
        d = rjson(b)
        data += d.get("data") or []
        requested += d.get("request") or []
    joined, rematched, unrequested = join_rows(data, requested)
    meta = {r["keyword"]: r for r in rows}
    months = sorted({m["month"] for it in joined.values() for m in it.get("monthly_volume") or [] if m.get("month")})
    out = []
    for q in targets:
        it = joined.get(q)
        am = (it or {}).get("ads_metrics") or {}
        mv = {m["month"]: m for m in (it or {}).get("monthly_volume") or []}
        r = {"keyword": q, "response_keyword": (it or {}).get("keyword") or "", "measured": bool(it),
             **{k: meta[q][k] for k in ("source", "layer", "origin", "excluded_reason")},
             "volume_avg": am.get("volume_avg"), "gg_volume_avg": am.get("gg_volume_avg"),
             "nv_volume_avg": am.get("nv_volume_avg"), "volume_trend": am.get("volume_trend")}
        for mo in months:
            m = mv.get(mo) or {}
            r[f"t_{mo}"], r[f"g_{mo}"], r[f"n_{mo}"] = m.get("total"), m.get("gg"), m.get("nv")
        out.append(r)
    fields = list(out[0].keys()) if out else ["keyword"]
    with (run / "keyword_info_all.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(out)
    wjson(run / "collect.json", {"at": now(), "requested": len(requested), "targets": len(targets),
                                 "measured": sum(1 for r in out if r["measured"]),
                                 "unmeasured": sum(1 for r in out if not r["measured"]),
                                 "rematched": rematched, "unrequested_rows": unrequested, "months": months})
    print(f"측정 {sum(1 for r in out if r['measured']):,}/{len(out):,} · 정규화 재매칭 {len(rematched)} · "
          f"미요청 변형 행 {len(unrequested)}(버림) · 월 {len(months)}개 → keyword_info_all.csv")
    return 0


# ───────────────────────── D7~D8 build
def _complete_months(months: list[str], as_of: str | None) -> list[str]:
    """최신 미완월 제외 — 분석 기준월(기본: 오늘이 속한 달) 이상은 빼고, 지정 시 그 달부터 뺀다."""
    cut = (as_of or datetime.date.today().strftime("%Y-%m"))[:7]
    return [m for m in months if m < cut]


def cmd_build(a) -> int:
    run = Path(a.run)
    cfg = config(run)
    ka = run / "keyword_info_all.csv"
    if not ka.exists():
        raise SystemExit("keyword_info_all.csv 없음 — collect 먼저")
    raw = read_csv(ka)
    months = sorted({c[2:] for c in (raw[0].keys() if raw else []) if c.startswith("t_")})
    brands, noise_words = load_dict(dict_extra(run, a))
    nre = noise_regex(cfg.get("gl", "kr"))
    thr = float(a.threshold if a.threshold is not None else PRESETS[cfg.get("preset") or "demand"]["screen_threshold"])

    num = lambda v: float(v) if v not in (None, "") else None   # noqa: E731
    rows = []
    for r in raw:
        low = r["keyword"].lower()
        monthly = [{"month": mo, "total": num(r.get(f"t_{mo}")), "gg": num(r.get(f"g_{mo}")), "nv": num(r.get(f"n_{mo}"))}
                   for mo in months if r.get(f"t_{mo}") not in (None, "")]
        rows.append({"keyword": r["keyword"], "source": r["source"], "layer": r["layer"], "origin": r["origin"],
                     "excluded_reason": r["excluded_reason"], "measured": r["measured"] == "True",
                     "volume_avg": num(r["volume_avg"]), "gg_volume_avg": num(r["gg_volume_avg"]),
                     "nv_volume_avg": num(r["nv_volume_avg"]), "is_seed": r["source"] == "seed",
                     "is_noise": bool(r["excluded_reason"]) or low in noise_words or bool(nre.search(low)),
                     "brand": brand_of(r["keyword"], brands), "monthly": monthly})
    measured = [r for r in rows if r["measured"]]
    dd = sd.mark_variants(measured)
    gg = sd.mark_gg_shared([r for r in measured if not r["is_noise"]])
    for r in rows:
        r.setdefault("canonical", r["keyword"]); r.setdefault("is_variant", False); r.setdefault("gg_shared_with", "")
        r["below_threshold"] = (r["volume_avg"] or 0) < thr and not r["is_seed"]
        r["counted"] = r["measured"] and not r["is_noise"] and not r["is_variant"] and not r["below_threshold"]

    comp = _complete_months(months, a.as_of)
    counted = [r for r in rows if r["counted"]]

    def contrib(r, m, drop_shared_gg=True):
        """한 행·한 달의 기여 — 구글을 공유하는 표기 변형은 네이버만, 채널 분리가 없으면 total."""
        if m["gg"] is None and m["nv"] is None:
            return m["total"] or 0
        gv = 0.0 if (drop_shared_gg and r["gg_shared_with"]) else (m["gg"] or 0)
        return gv + (m["nv"] or 0)

    def series(sel, drop_shared_gg=True):
        tot = {mo: 0.0 for mo in comp}
        g = {mo: 0.0 for mo in comp}
        n = {mo: 0.0 for mo in comp}
        for r in sel:
            for m in r["monthly"]:
                mo = m["month"]
                if mo not in tot:
                    continue
                gv = 0.0 if (drop_shared_gg and r["gg_shared_with"]) else (m["gg"] or 0)
                nv = m["nv"] or 0
                if m["gg"] is None and m["nv"] is None:
                    gv, nv = (m["total"] or 0), 0.0
                g[mo] += gv; n[mo] += nv; tot[mo] += gv + nv
        return tot, g, n

    # 헤드라인은 핵심 층(시장·브랜드·재화 유형 층)만 — 문제(M1)·대체재(M4) 층은 다른 수요라 맥락으로 따로 보고한다
    # 단, 맥락 층에서 확장된 검색어라도 anchor 어휘를 담으면 대상 품목 수요다('하이브리드 전기자전거') — 시드는 층을 유지한다
    anchor = [t.lower() for t in cfg.get("anchor") or [] if t]
    in_core = lambda r: (layer_group(r["layer"]) not in CONTEXT_LAYERS   # noqa: E731 
                         or (not r["is_seed"] and any(t in r["keyword"].lower() for t in anchor)))
    core = [r for r in counted if in_core(r)]
    for r in rows:
        r["core"] = bool(r["counted"] and in_core(r))
    # keywords_master.csv
    with (run / "keywords_master.csv").open("w", encoding="utf-8-sig", newline="") as f:
        cols = ["keyword", "canonical", "is_variant", "gg_shared_with", "is_noise", "excluded_reason", "below_threshold",
                "counted", "core", "brand", "source", "layer", "origin", "volume_avg", "gg_volume_avg", "nv_volume_avg"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)

    tot, g, n = series(core)
    naive, _, _ = series([r for r in measured if in_core(r) and not r["is_noise"]
                          and not ((r["volume_avg"] or 0) < thr and not r["is_seed"])], drop_shared_gg=False)
    all_tot, _, _ = series(counted)
    last12, prev12 = comp[-12:], comp[-24:-12]
    s12 = sum(tot[m] for m in last12)
    p12 = sum(tot[m] for m in prev12)
    yoy = (s12 / p12 - 1) if len(prev12) == 12 and p12 > 0 else None
    # 시즌 지수 — 최근 36개 완결월(없으면 가능한 만큼)의 달별 평균 / 전체 평균
    base = comp[-36:]
    by_moy: dict[str, list] = {}
    for mo in base:
        by_moy.setdefault(mo[5:], []).append(tot[mo])
    mean_all = (sum(tot[m] for m in base) / len(base)) if base else 0
    season = {k: round((sum(v) / len(v)) / mean_all, 3) for k, v in sorted(by_moy.items())} if mean_all else {}
    peaks = [k for k, v in season.items() if v >= 1.5]
    amp = (max(season.values()) / min(season.values())) if season and min(season.values()) > 0 else None

    def layer_share(field):
        agg: dict[str, float] = {}
        for r in counted:
            key = layer_group(r[field]) if field == "layer" else r[field]
            if field == "layer" and key in CONTEXT_LAYERS and in_core(r):
                key += "→core"                                  # 맥락 층 출신이지만 anchor 를 담아 헤드라인에 든 양
            agg[key] = agg.get(key, 0) + sum(contrib(r, m) for m in r["monthly"] if m["month"] in last12)
        return {k: round(v) for k, v in sorted(agg.items(), key=lambda x: -x[1])}

    all_vol = sum((r["volume_avg"] or 0) for r in measured if in_core(r) and not r["is_noise"] and not r["is_variant"])
    kept_vol = sum((r["volume_avg"] or 0) for r in core)
    by_layer = layer_share("layer")
    m14 = sum(v for k, v in by_layer.items() if k in CONTEXT_LAYERS)          # 헤드라인 밖 맥락 층만
    all12 = sum(all_tot[m] for m in last12)
    coll = rjson(run / "collect.json") if (run / "collect.json").exists() else {}
    uk = read_csv(run / "unique_keywords.csv") if (run / "unique_keywords.csv").exists() else []
    ex_d5: dict[str, int] = {}
    for r in uk:
        if r["excluded_reason"]:
            ex_d5[r["excluded_reason"]] = ex_d5.get(r["excluded_reason"], 0) + 1
    metrics = {
        "schema": "demand-metrics/v1", "at": now(), "target": cfg.get("target"), "gl": cfg.get("gl", "kr"),
        "months_complete": [comp[0], comp[-1]] if comp else [], "incomplete_excluded": [m for m in months if m not in comp],
        "keywords": {"unique": len(uk) or len(rows), "excluded_d5": sum(ex_d5.values()), "excluded_d5_by_reason": ex_d5,
                     "collected": len(rows), "measured": len(measured), "unmeasured": len(rows) - len(measured),
                     "noise_or_excluded": sum(1 for r in rows if r["is_noise"]), "variant_rows": dd["variant_rows"],
                     "variant_groups": dd["groups"], "gg_shared_rows": gg["gg_shared_rows"],
                     "below_threshold": sum(1 for r in rows if r["below_threshold"] and r["measured"]),
                     "counted": len(counted), "counted_core": len(core),
                     "unrequested_rows": len(coll.get("unrequested_rows") or [])},
        "scope": {"headline_layers": "M2_market · M3_supply · dynamic", "context_layers": list(CONTEXT_LAYERS),
                  "context_last12": {k: v for k, v in by_layer.items() if k in CONTEXT_LAYERS},
                  "all_layers_last12": round(all12)},
        "threshold": thr,
        "monthly_total": {m: round(tot[m]) for m in comp}, "monthly_gg": {m: round(g[m]) for m in comp},
        "monthly_nv": {m: round(n[m]) for m in comp},
        "last12_sum": round(s12), "last12_avg": round(s12 / len(last12)) if last12 else None,
        "prev12_sum": round(p12) if len(prev12) == 12 else None,
        "yoy": round(yoy, 4) if yoy is not None else None, "yoy_pct": round(yoy * 100, 1) if yoy is not None else None,
        "seasonality_index": season, "peak_months": peaks, "season_amplitude": round(amp, 2) if amp else None,
        "channel_share_last12": {"gg": round(sum(g[m] for m in last12) / s12, 4) if s12 else None,
                                 "nv": round(sum(n[m] for m in last12) / s12, 4) if s12 else None},
        "by_layer_last12": by_layer, "by_source_last12": layer_share("source"),
        "coverage": {"screen_volume_share": round(kept_vol / all_vol, 4) if all_vol else None,
                     "m1_m4_share_last12": round(m14 / all12, 4) if all12 else None,
                     "dedup_naive_last12": round(sum(naive[m] for m in last12)),
                     "dedup_removed_last12": round(sum(naive[m] for m in last12) - s12)},
        "top_counted": [{"keyword": r["keyword"], "volume_avg": r["volume_avg"], "layer": layer_group(r["layer"]),
                         "brand": r["brand"]} for r in sorted(core, key=lambda r: -(r["volume_avg"] or 0))[:30]],
        "labels": {"monthly_total": "[실측] 합산 [파생]", "yoy": "[파생]", "seasonality_index": "[파생]",
                   "variant_rows": "[추정] 규칙 기반 판정", "excluded": "[가정] 앵커·노이즈 규칙"},
    }
    wjson(run / "core" / "demand_metrics.json", metrics)
    k = metrics["keywords"]
    print(f"유니크 {k['unique']:,} · D5 제외 {k['excluded_d5']:,} · 집계 {k['counted']:,}개 · 핵심 층 {k['counted_core']:,}개(측정 {k['measured']:,} · 노이즈 {k['noise_or_excluded']:,} · 변형 {k['variant_rows']:,} · "
          f"임계 미만 {k['below_threshold']:,}) · 최근 12개월 {metrics['last12_sum']:,}건 · YoY "
          f"{'—' if yoy is None else f'{yoy:+.1%}'} · 피크 {','.join(peaks) or '없음'} → core/demand_metrics.json")
    return 0



# ───────────────────────── 2차 — 라이징 · 원인 · 브랜드 점유 · 콘텐츠 (build 산출물 재사용)
def load_master(run: Path):
    """keywords_master + keyword_info_all → 행 목록(월별 포함), 완결월, 지표. build 뒤에만 쓴다."""
    mp = run / "core" / "demand_metrics.json"
    if not mp.exists():
        raise SystemExit("core/demand_metrics.json 없음 — build 먼저")
    km = {r["keyword"]: r for r in read_csv(run / "keywords_master.csv")}
    raw = read_csv(run / "keyword_info_all.csv")
    months = sorted({c[2:] for c in (raw[0].keys() if raw else []) if c.startswith("t_")})
    m = rjson(mp)
    lo, hi = (m["months_complete"] + ["", ""])[:2]
    comp = [x for x in months if lo <= x <= hi]
    num = lambda v: float(v) if v not in (None, "") else None   # noqa: E731
    rows = []
    for r in raw:
        k = km.get(r["keyword"])
        if not k:
            continue
        rows.append({"keyword": r["keyword"], "counted": k["counted"] == "True", "core": k.get("core") == "True",
                     "brand": k.get("brand") or "", "gg_shared": bool(k.get("gg_shared_with")), "layer": k["layer"],
                     "source": k["source"], "volume_avg": num(r.get("volume_avg")),
                     "t": {mo: num(r.get(f"t_{mo}")) for mo in months}, "g": {mo: num(r.get(f"g_{mo}")) for mo in months},
                     "n": {mo: num(r.get(f"n_{mo}")) for mo in months}})
    return rows, comp, m


def month_contrib(r: dict, mo: str) -> float:
    """build 와 같은 기여 규칙 — 구글 공유 변형은 네이버만, 채널 분리가 없으면 total."""
    g, n, t = r["g"].get(mo), r["n"].get(mo), r["t"].get(mo)
    if g is None and n is None:
        return t or 0.0
    return (0.0 if r["gg_shared"] else (g or 0.0)) + (n or 0.0)


def prev_year(mo: str) -> str:
    return f"{int(mo[:4]) - 1}{mo[4:]}"


def cmd_rising(a) -> int:
    """D9 — 키워드 단위 라이징: 최근 N개 완결월 평균 vs 전년 같은 달 평균. 카테고리 합계가 조용해도 키워드는 뛴다."""
    run = Path(a.run)
    rows, comp, m = load_master(run)
    win = comp[-a.window:]
    base = [prev_year(x) for x in win]
    out = []
    for r in rows:
        if not r["core"] or any(b not in r["t"] for b in base):
            continue
        rec = sum(r["t"].get(x) or 0 for x in win) / len(win)
        pri = sum(r["t"].get(x) or 0 for x in base) / len(base)
        new = pri < a.new_floor
        if rec >= a.min_recent and (new or rec / pri >= a.ratio):
            out.append({"keyword": r["keyword"], "recent_avg": round(rec), "prior_avg": round(pri),
                        "ratio": None if pri == 0 else round(rec / pri, 2), "new": new, "delta": round(rec - pri),
                        "brand": r["brand"], "layer": layer_group(r["layer"])})
    out.sort(key=lambda x: -x["delta"])
    mt = m["monthly_total"]
    cat = {x: round(mt[x] / mt[prev_year(x)] - 1, 4) for x in comp[-12:] if mt.get(prev_year(x))}
    res = {"at": now(), "window": win, "baseline": base,
           "criteria": {"min_recent_avg": a.min_recent, "ratio": a.ratio, "new_if_prior_below": a.new_floor},
           "category_monthly_yoy": cat, "category_max_yoy": max(cat.values()) if cat else None,
           "rising": out, "labels": {"rising": "[실측 월별 · 파생 비교]"}}
    wjson(run / "core" / "rising.json", res)
    print(f"라이징 {len(out)}개 (최근 {len(win)}개월 평균 {a.min_recent:g}+ · {a.ratio:g}배+ 또는 신규) · 카테고리 월별 YoY 최대 "
          f"{'—' if res['category_max_yoy'] is None else f'{res['category_max_yoy']:+.0%}'} → core/rising.json")
    for x in out[:8]:
        print(f"  {x['keyword']}  {x['prior_avg']:,} → {x['recent_avg']:,}")
    return 0


def distinguishing_token(keyword: str, anchor: list[str], df: dict) -> str | None:
    """라이징 키워드에서 원인 조회용 구별 토큰 — anchor 어휘가 아니고 집계 키워드 전체에서 가장 드문 토큰."""
    anc = [sd.canon(x) for x in anchor]
    toks = keyword.lower().split()
    is_anchor = lambda ct: any(x in ct or ct in x for x in anc)   # noqa: E731
    cands = []
    for i, t in enumerate(toks):
        ct = sd.canon(t)
        if len(ct) < 2 or is_anchor(ct):
            continue
        cands.append((df.get(ct, 0), -len(ct), i))
    if not cands:
        return None
    i = sorted(cands)[0][2]
    # 두 글자 이하 조각('몬테 리아'의 '리아')은 이웃 비앵커 토큰과 붙인다 — 띄어 쓴 고유명의 한 조각은 다른 이슈를 끌어온다
    if len(sd.canon(toks[i])) <= 2:
        for j in (i - 1, i + 1):
            if 0 <= j < len(toks) and not is_anchor(sd.canon(toks[j])) and len(sd.canon(toks[j])) >= 1:
                return " ".join(toks[min(i, j):max(i, j) + 1])
    return toks[i]


def cmd_explain(a) -> int:
    """D10 — 라이징 원인: 구별 토큰으로 trend_finder(90일 → 비면 365일)를 부르고, 품목 어휘가 함께 나오는 이슈만 남긴다."""
    run = Path(a.run)
    cfg = config(run)
    gl = cfg.get("gl", "kr")
    rp = run / "core" / "rising.json"
    if not rp.exists():
        raise SystemExit("core/rising.json 없음 — rising 먼저")
    rising = rjson(rp)["rising"][: a.top]
    rows, _, _ = load_master(run)
    df: dict[str, int] = {}
    for r in rows:
        if r["counted"]:
            for t in {sd.canon(x) for x in r["keyword"].lower().split()}:
                df[t] = df.get(t, 0) + 1
    anchor = [t.lower() for t in cfg.get("anchor") or [] if t]
    plan = []
    for x in rising:
        tok = distinguishing_token(x["keyword"], anchor, df)
        plan.append((x, tok, run / "api" / f"trend_{slug(sd.canon(tok))}.json" if tok else None))
    todo = [p for p in plan if p[1] and not p[2].exists()]
    if todo and a.replay:
        print(f"⚠ replay — 이슈 저장본 없는 {len(todo)}개는 미수집으로 둔다")
    elif todo:
        budget_check(len(todo) * unit_cost("trend_finder", limit=a.limit), a.budget,
                     f"D10 trend_finder {len(todo)}토큰(상한 · 빈 결과는 과금 0)")
        from api import trend_finder                     # noqa: PLC0415
        client = api_client()
        for x, tok, f in todo:
            seed = sd.canon(tok)                          # 붙여 쓴 형태 — 띄어쓴 시드는 단어 하나만 맞아도 이슈를 가져온다
            tried = []
            for days in (a.period, 365):
                r = trend_finder.fetch(client, seed, gl=gl, period_days=days, limit=a.limit)
                cost = (r.get("cost_detail") or {}).get("total_cost") or 0
                tried.append({"period_days": days, "total": r.get("total"), "cost": cost})
                ledger_add(run, "D10", "trend_finder/issue_list", {"keyword": seed, "period_days": days, "limit": a.limit}, cost,
                           raw=str(Path(f).relative_to(run)) if Path(f).is_relative_to(run) else str(f))
                if (r.get("total") or 0) > 0 or days == 365:
                    break
            wjson(f, {"seed": seed, "for": x["keyword"], "tried": tried, "at": now(), **r})
            print(f"D10 {x['keyword']} → '{seed}' · 이슈 {r.get('total') or 0} · {sum(t['cost'] for t in tried)}크레딧")
    def relevant(d, x, tok):
        others = [sd.canon(t) for t in anchor] + [sd.canon(t) for t in x["keyword"].lower().split()
                                                  if sd.canon(t) not in sd.canon(tok)]
        kept = []
        for it in d.get("data") or []:
            text = sd.canon(" ".join([it.get("keyword") or ""] + list(it.get("summary") or []) + list(it.get("key_phrase") or [])))
            if sd.canon(tok) in text and any(o and o in text for o in others):
                kept.append({"keyword": it.get("keyword"), "issue_score": it.get("issue_score"),
                             "index_date": (it.get("index_date") or it.get("recorded_at") or "")[:10],
                             "summary": (it.get("summary") or [""])[0], "sources": (it.get("source_links") or [])[:2]})
        return kept

    # --retry-joined: 구별 토큰 결과가 무관 이슈뿐이면 키워드 전체를 붙여 쓴 형태로 한 번 더. 기본은 끈다 —
    # 2026-09-30 파일럿 3건에서 붙여쓴 전체 키워드도 1.9만~5.1만 건으로 넓게 매칭돼 상위 20건에 관련 이슈가 없었다.
    retry = []
    for x, tok, f in (plan if a.retry_joined else []):
        if tok and f.exists() and not relevant(rjson(f), x, tok):
            f2 = run / "api" / f"trend_{slug(sd.canon(x['keyword']))}.json"
            if f2 != f:
                retry.append((x, f2))
    todo2 = [(x, f2) for x, f2 in retry if not f2.exists()]
    if todo2 and not a.replay:
        budget_check(len(todo2) * unit_cost("trend_finder", limit=a.limit), a.budget, f"D10 재조회 {len(todo2)}개(키워드 붙여쓰기)")
        from api import trend_finder                     # noqa: PLC0415
        client = api_client()
        for x, f2 in todo2:
            seed = sd.canon(x["keyword"])
            r = trend_finder.fetch(client, seed, gl=gl, period_days=365, limit=a.limit)
            cost = (r.get("cost_detail") or {}).get("total_cost") or 0
            ledger_add(run, "D10", "trend_finder/issue_list", {"keyword": seed, "period_days": 365, "limit": a.limit}, cost,
                       raw=str(Path(f2).relative_to(run)) if Path(f2).is_relative_to(run) else str(f2))
            wjson(f2, {"seed": seed, "for": x["keyword"], "tried": [{"period_days": 365, "total": r.get("total"), "cost": cost}],
                       "at": now(), **r})
            print(f"D10 재조회 {x['keyword']} → '{seed}' · 이슈 {r.get('total') or 0} · {cost}크레딧")
    retry_file = dict((x["keyword"], f2) for x, f2 in retry)

    out = []
    for x, tok, f in plan:
        rec = {"keyword": x["keyword"], "token": tok, "recent_avg": x["recent_avg"], "prior_avg": x["prior_avg"]}
        if not tok:
            rec.update(verdict="구별 토큰 없음", issues=[]); out.append(rec); continue
        if not f.exists():
            rec.update(verdict="미수집", issues=[]); out.append(rec); continue
        d = rjson(f)
        kept = relevant(d, x, tok)
        used = tok
        f2 = retry_file.get(x["keyword"])
        if not kept and f2 is not None and f2.exists():
            d2 = rjson(f2)
            kept2 = relevant(d2, x, sd.canon(x["keyword"]))
            if kept2 or not (d.get("data") or []):
                d, kept, used = d2, kept2, sd.canon(x["keyword"])
        n = len(d.get("data") or [])
        total_m = d.get("total") or 0
        if kept:
            verdict = "원인 이슈 있음"
        elif not n:
            verdict = "이슈 없음"
        elif total_m > 1000:
            verdict = "매칭 과다 · 판정 보류"                 # 인덱스가 넓게 매칭해 상위가 무관 이슈로 찬다 — '없다'고 쓰지 않는다
        else:
            verdict = "무관 이슈만"
        rec.update(verdict=verdict, seed_used=used, returned=n, matched_total=total_m, tried=d.get("tried"), issues=kept)
        out.append(rec)
    wjson(run / "core" / "rising_explained.json", {"at": now(), "items": out,
          "note": "이슈 인덱스는 2025-05-26 이후·최대 365일 · summary 는 검색결과의 AI 요약(외부 요약) — 소비자 발화 아님",
          "labels": {"issues": "[외부 요약 · 수집 시점 스냅샷]"}})
    for r in out:
        print(f"  {r['keyword']} ← '{r['token']}' · {r['verdict']}" + (f" · {r['issues'][0]['summary'][:60]}" if r["issues"] else ""))
    return 0


GENERIC_PREFIX = {"가성비", "중고", "저렴한", "싼", "싸고", "국산", "국내", "수입", "여성", "남성", "여자", "남자", "아이", "어린이",
                  "미니", "소형", "대형", "추천", "인기", "최신", "신형", "좋은", "가벼운", "튼튼한", "고급", "입문", "입문용", "성인",
                  "노인", "학생", "초보", "새", "요즘", "최고", "베스트", "best", "top"}


def cmd_share(a) -> int:
    """잡 4 — 헤드라인 층 집계 키워드를 브랜드·판매 채널·무브랜드로 나눈 검색 점유. 미등재 브랜드 후보를 사람 검토용으로 낸다."""
    run = Path(a.run)
    cfg = config(run)
    rows, comp, _ = load_master(run)
    chans = load_channels(dict_extra(run, a))
    anchor = sorted([t.lower() for t in cfg.get("anchor") or [] if t], key=len, reverse=True)
    last12, prev12 = comp[-12:], comp[-24:-12]
    core = [r for r in rows if r["core"]]
    groups: dict[tuple, dict] = {}
    for r in core:
        if r["brand"]:
            key = ("brand", r["brand"])
        else:
            ch = brand_of(r["keyword"], chans)                 # "channel\t쿠팡" · "community\t디시"
            key = tuple(ch.split("\t", 1)) if ch else ("generic", "무브랜드")
        g = groups.setdefault(key, {"kind": key[0], "name": key[1], "last12": 0.0, "prev12": 0.0, "keywords": []})
        v12 = sum(month_contrib(r, x) for x in last12)
        g["last12"] += v12
        g["prev12"] += sum(month_contrib(r, x) for x in prev12)
        g["keywords"].append((r["keyword"], round(v12)))
    total = sum(g["last12"] for g in groups.values())
    branded = sum(g["last12"] for g in groups.values() if g["kind"] == "brand")
    out = []
    for g in sorted(groups.values(), key=lambda g: -g["last12"]):
        out.append({"kind": g["kind"], "name": g["name"], "last12": round(g["last12"]),
                    "share_of_branded": round(g["last12"] / branded, 4) if g["kind"] == "brand" and branded else None,
                    "share_of_headline": round(g["last12"] / total, 4) if total else None,
                    "yoy": round(g["last12"] / g["prev12"] - 1, 4) if len(prev12) == 12 and g["prev12"] else None,
                    "top_keywords": [k for k, _ in sorted(g["keywords"], key=lambda x: -x[1])[:5]],
                    "keyword_count": len(g["keywords"])})
    # 미등재 브랜드 후보 — 무브랜드 키워드의 품목 어휘 앞 토큰(자동 등록 금지 · 사람이 E0 에 넣고 재계산)
    cand: dict[str, dict] = {}
    seed_toks = {t for s_, lay in seeds_by_layer(cfg) if lay != "M3_supply" for t in s_.lower().split()}
    for r in core:
        if r["brand"] or brand_of(r["keyword"], chans):
            continue
        toks = r["keyword"].lower().split()
        ai = next((i for i, tk in enumerate(toks) if any(sd.canon(t) in sd.canon(tk) for t in anchor)), None)
        if not ai:                                    # 앵커를 담은 토큰 앞의 토큰들이 후보('벤츠 무선청소기' → '벤츠')
            continue
        pre = " ".join(toks[:ai])
        if (len(sd.canon(pre)) >= 2 and pre not in GENERIC_PREFIX and pre not in seed_toks and not pre.endswith("용")
                and not re.fullmatch(r"[\d\s.]+", pre)):
            c = cand.setdefault(pre, {"prefix": pre, "last12": 0.0, "examples": []})
            c["last12"] += sum(month_contrib(r, x) for x in last12)
            c["examples"].append(r["keyword"])
    cands = [{"prefix": c["prefix"], "last12": round(c["last12"]), "examples": c["examples"][:3]}
             for c in sorted(cand.values(), key=lambda c: -c["last12"])[: a.candidates]]
    res = {"at": now(), "months": [last12[0], last12[-1]] if last12 else [], "headline_last12": round(total),
           "branded_last12": round(branded), "branded_share": round(branded / total, 4) if total else None,
           "groups": out, "unregistered_brand_candidates": cands,
           "candidates_note": "브랜드만이 아니라 품목 유형어(세발·삼륜·pas)도 섞인다 — 사람이 브랜드만 골라 E0 Brand 로 넣고 build → share 재실행",
           "note": "검색량 기준 근사 — 판매 점유율이 아니다 · 한 키워드는 가장 긴 별칭의 한 브랜드에만 귀속 · 후보는 사람 검토 후 E0 에 넣는다",
           "labels": {"last12": "[실측 합산]", "share": "[파생]", "unregistered_brand_candidates": "[가정] 품목 어휘 앞 토큰 규칙"}}
    wjson(run / "core" / "brand_share.json", res)
    print(f"헤드라인 {round(total):,} · 브랜드 지명 {res['branded_share']:.0%} · 그룹 {len(out)} → core/brand_share.json")
    for g in [x for x in out if x["kind"] == "brand"][:8]:
        print(f"  {g['name']} {g['share_of_branded']:.1%} · YoY {'—' if g['yoy'] is None else f'{g['yoy']:+.0%}'}")
    if cands:
        print("  미등재 브랜드·유형 후보(사람 검토): " + ", ".join(f"{c['prefix']}({c['last12']:,})" for c in cands[:10]))
    return 0


PURPOSES = [  # (목적, 권장 형식, 어휘) — 먼저 맞는 것 하나로 분류
    ("문제해결", "문제 해결 가이드", ["고장", "수리", "교체", "안됨", "안 됨", "방전", "화재", "폭발", "에러", "오류", "소음", "불량", "해결", "as"]),
    ("구매", "가격·구매처 가이드", ["가격", "구매", "구입", "할인", "최저가", "싸게", "판매", "매장", "파는 곳", "파는곳", "렌탈", "대여",
                                "중고", "할부", "쿠폰", "비용", "견적", "매입"]),
    ("비교", "비교표·추천 목록", ["추천", "비교", "순위", "vs", "차이", "랭킹", "가성비", "best", "top"]),
    ("검증", "후기·장단점 정리", ["후기", "리뷰", "단점", "장점", "평가", "디시", "클리앙", "뽐뿌", "갤러리", "갤"]),
    ("정보", "FAQ·규정 안내", ["방법", "하는법", "하는 법", "뜻", "원리", "규정", "면허", "나이", "기준", "조건", "종류", "보조금", "지원금",
                           "보험", "등록", "법", "제한"]),
    ("사용", "사용 가이드", ["충전", "보관", "타는 법", "타는법", "관리", "세척", "설정", "속도", "주행거리", "용량"]),
]


def purpose_of(kw: str) -> tuple[str, str]:
    low = kw.lower()
    for name, fmt, words in PURPOSES:
        for w in words:
            hit = re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", low) if re.fullmatch(r"[a-z]+", w) else (w in low)
            if hit:
                return name, fmt
    return "탐색", "카테고리 랜딩"


def cmd_content(a) -> int:
    """잡 5 — 목적별 검색어 묶음 · 권장 형식. --serp-top N 이면 상위 검색어 SERP(연관 질문·AI 개요·자연결과 사이트)를 모은다."""
    run = Path(a.run)
    cfg = config(run)
    rows, comp, _ = load_master(run)
    last12 = comp[-12:]
    core = [r for r in rows if r["core"]]
    for r in core:
        r["v12"] = sum(month_contrib(r, x) for x in last12)
        r["purpose"], r["format"] = purpose_of(r["keyword"])
    total = sum(r["v12"] for r in core) or 1
    total_ns = sum(r["v12"] for r in core if r["source"] != "seed")     # 시드(헤드텀)를 뺀 롱테일 기준 — 헤드가 '탐색'을 채운다
    groups = []
    for name, fmt in [(p[0], p[1]) for p in PURPOSES] + [("탐색", "카테고리 랜딩")]:
        sel = sorted([r for r in core if r["purpose"] == name], key=lambda r: -r["v12"])
        if sel:
            nonseed = sum(r["v12"] for r in sel if r["source"] != "seed")
            groups.append({"purpose": name, "format": fmt, "keywords": len(sel), "last12": round(sum(r["v12"] for r in sel)),
                           "share": round(sum(r["v12"] for r in sel) / total, 4),
                           "share_excl_seeds": round(nonseed / total_ns, 4) if total_ns else None,
                           "top": [{"keyword": r["keyword"], "last12": round(r["v12"])} for r in sel[:10]]})
    res = {"at": now(), "months": [last12[0], last12[-1]] if last12 else [], "groups": groups,
           "labels": {"purpose": "[가정] 목적 어휘 규칙 분류", "last12": "[실측 합산]"}}
    if a.serp_top:
        top = sorted(core, key=lambda r: -r["v12"])[: a.serp_top]
        files = [(r, run / "api" / f"serp_{slug(r['keyword'])}.json") for r in top]
        todo = [(r, f) for r, f in files if not f.exists()]
        if todo and a.replay:
            print(f"⚠ replay — serp 저장본 없는 {len(todo)}개는 빠진다")
        elif todo:
            budget_check(unit_cost("serp", keywords=len(todo)), a.budget, f"serp {len(todo)}개")
            from api import serp                          # noqa: PLC0415
            client = api_client()
            for r, f in todo:
                resp = serp.fetch(client, r["keyword"], gl=cfg.get("gl", "kr"), num=20)
                wjson(f, {"keyword": r["keyword"], "at": now(), **resp})
                ledger_add(run, "content", "serp", {"keyword": r["keyword"], "num": 20},
                           (resp.get("cost_detail") or {}).get("total_cost"),
                           raw=str(Path(f).relative_to(run)) if Path(f).is_relative_to(run) else str(f))
        from api import serp as sp                        # noqa: PLC0415  (파싱 헬퍼만 — 호출 없음)
        got = [(r, rjson(f)) for r, f in files if f.exists()]
        sites: dict[str, int] = {}
        paa, per = [], []
        for r, d in got:
            org = [o for o in sp.organic(d) if (o.get("position") or 99) <= 10]
            from urllib.parse import urlparse             # noqa: PLC0415
            for o in org:
                o["site_name"] = o.get("site_name") or urlparse(o.get("url") or "").netloc or "?"
                sites[o["site_name"]] = sites.get(o["site_name"], 0) + 1
            qs = [q["question"] for q in sp.questions(d)]
            paa += [q for q in qs if q not in paa]
            per.append({"keyword": r["keyword"], "aio": bool(sp.ai_overview_snippets(d)), "paa": len(qs),
                        "top_sites": [o.get("site_name") for o in org[:5]], "collected_at": d.get("at")})
        gg = sum((r["g"].get(x) or 0) for r, _ in got for x in last12)
        nv = sum((r["n"].get(x) or 0) for r, _ in got for x in last12)
        res["serp"] = {"keywords": len(got), "google_share_of_these_keywords": round(gg / (gg + nv), 4) if gg + nv else None,
                       "aio_rate": round(sum(p["aio"] for p in per) / len(per), 4) if per else None,
                       "top10_site_counts": dict(sorted(sites.items(), key=lambda x: -x[1])[:15]),
                       "paa_questions": paa[:30], "per_keyword": per,
                       "caveat": "구글 검색결과 스냅샷(수집 시점) — 조회 검색어의 구글 비중이 낮으면 노출 지형을 단정하지 않는다 · 시계열 비교 불가"}
    wjson(run / "core" / "content.json", res)
    print("목적별(시드 제외): " + " · ".join(f"{g['purpose']} {g['share_excl_seeds'] or 0:.0%}" for g in groups) + " → core/content.json")
    if res.get("serp"):
        s_ = res["serp"]
        print(f"  serp {s_['keywords']}개 · 구글 비중 {s_['google_share_of_these_keywords']:.0%} · AI 개요 노출 {s_['aio_rate']:.0%} · "
              f"상위 사이트 {list(s_['top10_site_counts'])[:5]}")
    return 0

# ───────────────────────── report 뼈대
def cmd_report(a) -> int:
    run = Path(a.run)
    m = rjson(run / "core" / "demand_metrics.json")
    led = rjson(run / "ledger.json") if (run / "ledger.json").exists() else []
    spent = sum((x.get("cost") or 0) for x in led)
    by_tool: dict[str, int] = {}
    for x in led:
        by_tool[x["tool"]] = by_tool.get(x["tool"], 0) + (x.get("cost") or 0)
    months = list(m["monthly_total"].keys())[-24:]
    unit = 1000 if max(m["monthly_total"].values() or [0]) >= 10000 else 1
    k, c = m["keywords"], m["coverage"]
    peaks = [f"{int(p)}월" for p in m["peak_months"]]
    skel = {
        "title": f"{m['target']} 수요·트렌드 리포트", "eyebrow": "DEMAND · " + m["gl"].upper(),
        "scope_line": f"데이터 기간 {m['months_complete'][0]} ~ {m['months_complete'][1]} (완결월) · gl={m['gl']}",
        "connectors_line": f"keyword_info({k['measured']:,}개) · intent_finder · cluster_finder/keyword_list",
        "owner": "(작성)", "lede_html": "(작성)",
        "readiness": {"status": "(판정)", "limits": [
            f"집계 {k['counted']:,}개 — 유니크 {k['unique']:,}개 중 노이즈·앵커 무관 {k['excluded_d5'] + k['noise_or_excluded']:,}개, 표기 변형 {k['variant_rows']:,}개, 월평균 {m['threshold']:g} 미만 {k['below_threshold']:,}개 제외",
            f"선별 후 남은 볼륨 비중 {c['screen_volume_share']:.0%}" if c["screen_volume_share"] is not None else "선별 커버리지 산출 불가",
            f"헤드라인은 시장·브랜드·재화 유형 층만 합산 — 문제·대체재 층(전체의 {c['m1_m4_share_last12']:.0%})은 맥락으로 따로 표기" if c["m1_m4_share_last12"] is not None else "",
            "검색은 관심 신호이며 판매·점유율이 아님"]},
        "kpis": [
            {"label": "월평균 검색량 (중복 제거)", "value": f"{m['last12_avg']:,}", "desc": "최근 12개 완결월 (측정 합산)"},
            {"label": "YoY", "value": "—" if m["yoy_pct"] is None else f"{m['yoy_pct']:+.1f}%", "desc": "최근 12개월 vs 직전 12개월 (파생)",
             **({"dir": "up" if (m["yoy_pct"] or 0) >= 0 else "down"} if m["yoy_pct"] is not None else {})},
            {"label": "시즌 진폭", "value": "—" if not m["season_amplitude"] else f"{m['season_amplitude']}×",
             "desc": ("피크 " + "·".join(peaks)) if peaks else "월 평균 대비 1.5배 넘는 달 없음 (파생)"},
            {"label": "네이버 비중", "value": "—" if m["channel_share_last12"]["nv"] is None else f"{m['channel_share_last12']['nv']:.0%}",
             "desc": "최근 12개월 (측정)"}],
        "trend": {"seed": m["target"], "unit": "천 건" if unit == 1000 else "건", "months": months,
                  "values": [round(m["monthly_total"][x] / unit, 1) for x in months]},
        "footer": {"credits_total": f"{spent:,}", "credits_breakdown": " · ".join(f"{t} {v:,}" for t, v in by_tool.items())},
    }
    skel["readiness"]["limits"] = [x for x in skel["readiness"]["limits"] if x]
    out = Path(a.out) if a.out else run / "report-skeleton.json"
    wjson(out, skel)
    print(f"리포트 뼈대 → {out}  (서술 필드 '(작성)'을 채우고 필요 없는 섹션 키를 지운 뒤 render_report.py --run {run})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "expand", "collect", "build", "report", "rising", "explain", "share", "content"):
        p = sub.add_parser(name)
        p.add_argument("--run", required=True, help="분석 폴더 (seed_layer_config.json 위치)")
        p.add_argument("--replay", action="store_true", help="저장본만 읽는다(0크레딧)")
        p.add_argument("--budget", type=int, help="이 단계 예상 크레딧 상한 — 넘으면 멈춘다")
        p.add_argument("--dict", action="append", default=[], help="분석별 추가 E0 사전 csv (run 폴더의 E0_*.csv 는 자동)")
        if name == "expand":
            p.add_argument("--cluster-top", type=int, help="구조 탐색 시드 수 (기본: 프리셋)")
            p.add_argument("--min-seed-volume", type=float, default=1000, help="구조 탐색 대상 시드 최소 월평균")
        if name == "collect":
            p.add_argument("--include-excluded", action="store_true", help="제외 표시 키워드도 측정")
        if name == "build":
            p.add_argument("--threshold", type=float, help="집계 최소 월평균(기본: 프리셋)")
            p.add_argument("--as-of", help="분석 기준월 YYYY-MM — 이 달부터 미완월로 뺀다(기본: 오늘)")
        if name == "report":
            p.add_argument("--out")
        if name == "rising":
            p.add_argument("--window", type=int, default=3, help="최근 완결월 수")
            p.add_argument("--min-recent", type=float, default=1000, help="최근 월평균 하한")
            p.add_argument("--ratio", type=float, default=2.0, help="전년 동기 대비 배수")
            p.add_argument("--new-floor", type=float, default=100, help="전년 평균이 이보다 작으면 신규 등장으로 본다")
        if name == "explain":
            p.add_argument("--top", type=int, default=5, help="원인을 볼 라이징 키워드 수")
            p.add_argument("--period", type=int, default=90, help="첫 조회 기간(일) — 비면 365일로 한 번 넓힌다")
            p.add_argument("--limit", type=int, default=20, help="반환 이슈 수(출력 과금 2/건)")
            p.add_argument("--retry-joined", action="store_true", help="무관 이슈만이면 키워드 전체 붙여쓰기로 재조회(기본 끔)")
        if name == "share":
            p.add_argument("--candidates", type=int, default=20, help="미등재 브랜드 후보 수")
        if name == "content":
            p.add_argument("--serp-top", type=int, default=0, help="serp 로 볼 상위 검색어 수(키워드당 30)")
    a = ap.parse_args()
    return {"plan": cmd_plan, "expand": cmd_expand, "collect": cmd_collect, "build": cmd_build, "report": cmd_report,
            "rising": cmd_rising, "explain": cmd_explain, "share": cmd_share, "content": cmd_content}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
