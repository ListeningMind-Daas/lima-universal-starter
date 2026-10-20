#!/usr/bin/env python3
"""시드 검증 프로브 (범용) — 본 실측 전에 시드 오염을 걸러낸다.

사용:
  python3 seed_check.py --gl kr --anchor "전기자전거,전동자전거,자전거" "전기자전거" "전기자전거 추천" "전동자전거"
  python3 seed_check.py --gl kr --mode cs --anchor "○○마트" "○○마트 고객센터" "○○마트 환불"
  python3 seed_check.py --replay 99_Scratch/<분석>/probe      # 저장 코퍼스 0크레딧 재채점
  python3 seed_check.py --gl kr --json "시드"                  # seed-check/v1 계약 (CEP Finder 훅)

근거·임계: references/seed-verification.md — 노이즈 <20% · 적합률(앵커 기준) >=60% · 브랜드 히트 >=10
비용: 시드당 약 100~230크레딧 (intent_finder/keyword_list 30 + 반환어 2/개 — 반환 수 비례)
사전: dictionary/E0_사전.csv (Noise 등재 시드는 0크레딧 차단 · Brand/SubBrand는 히트 계산 · Channel/Reviewer는 브랜드 아님)
노이즈 어휘: adapter.yaml A2(common + gl + gl_regex) — 품목 문맥이 바뀌면 사전을 고치지 스크립트를 고치지 않는다.
기록: dictionary/seed_registry.csv (append-only, --no-registry로 끔)
stdlib 전용. lima-agents/api/client.py가 있으면 그것을 쓰고, 없으면 내장 urllib 클라이언트로 동작한다.
"""
from __future__ import annotations

import argparse, csv, datetime, json, os, re, sys, time, urllib.error, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SKILLS_ROOT = SKILL.parent
DICT = SKILL / "dictionary/E0_사전.csv"
REGISTRY = SKILL / "dictionary/seed_registry.csv"
ADAPTER = SKILL / "adapter.yaml"

THRESH = {"noise": 0.20, "fit": 0.60, "brand_hits": 10, "cs": 0.25}
MIN_N = 20   # 이보다 적은 표본은 비율 판정이 무의미 → pool

# CS·VOC 의도 (--mode cs 양성 신호) — 2026-08-14 리테일 CS 저니 실측 어휘
CS_RE = re.compile(
    r"고객센터|고객\s*센터|전화번호|상담원?|문의|접수|불만|voc|환불|반품|교환|취소|규정|영수증|배송\s*(지연|문의|시간|지역)|"
    r"주문\s*(불가|취소)|재고\s*(확인|조회|문의)|재입고|품절|오류|안됨|안\s*됨|장애|먹통|결제\s*(오류|취소)|픽업|"
    r"customer service|support|refund|return|cancel|complaint|not working|error", re.I)


# ───────────────────────── 클라이언트 (lima-agents 우선, 없으면 내장)
def _workspace_root() -> Path | None:
    for d in [Path.cwd(), *HERE.parents]:
        if (d / "00_Context").is_dir() or (d / ".agents/skills").is_dir():
            return d
    return None


def _resolve_base() -> str:
    env = os.environ.get("LM_API_BASE", "").strip()
    if env:
        return env.rstrip("/")
    for d in [Path.cwd(), *HERE.parents]:
        f = d / "00_Context/.lm-api-base"
        if f.is_file() and f.read_text(encoding="utf8").strip():
            return f.read_text(encoding="utf8").strip().rstrip("/")
    return "https://listeningmind-data-api.ascentlab.io"


class _MiniClient:
    """urllib 전용 최소 클라이언트 — 429/5xx 재시도."""
    def __init__(self, api_key: str):
        if not api_key:
            raise SystemExit("API 키가 비어 있음 — 00_Context/.lm-api-key 또는 --key")
        self.api_key, self.base = api_key, _resolve_base()

    def post(self, endpoint: str, body: dict, retries: int = 2) -> dict:
        url = f"{self.base}/{endpoint.lstrip('/')}"
        data = json.dumps(body, ensure_ascii=False).encode("utf8")
        hdr = {"Content-Type": "application/json", "LM-API-KEY": self.api_key}
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(url, data=data, headers=hdr)
                with urllib.request.urlopen(req, timeout=180) as r:
                    return json.loads(r.read().decode("utf8"))
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                    time.sleep(2 ** attempt); continue
                raise
        raise RuntimeError("retry loop exit")


def make_client(key_path: str):
    key = Path(key_path).read_text(encoding="utf8").strip() if Path(key_path).is_file() else ""
    la = SKILLS_ROOT / "lima-agents"
    if (la / "api/client.py").is_file():
        sys.path.insert(0, str(la))
        try:
            from api.client import DaasClient            # noqa: PLC0415
            return DaasClient(key), "lima-agents/api"
        except Exception:                                  # noqa: BLE001
            pass
    return _MiniClient(key), "builtin"


# ───────────────────────── 사전·노이즈
def load_dict(extra: list[str] | None = None):
    """스킬 E0 사전 + 분석별 추가 사전(--dict, 여러 개) 병합."""
    brands, noise_seeds, flagged, replacements = {}, set(), set(), {}
    files = ([DICT] if DICT.exists() else []) + [Path(x) for x in (extra or []) if Path(x).is_file()]
    rows = [r for f in files for r in csv.DictReader(f.open(encoding="utf8"))]
    for r in rows:
        forms = [r["label"]] + [a.strip() for a in (r.get("aliases") or "").split("|") if a.strip()]
        cls = (r.get("class") or "").strip()
        if cls in ("Brand", "SubBrand"):
            for f in forms:
                if len(f) >= 2:
                    brands[f.lower()] = r["label"]
        elif cls == "Noise":
            noise_seeds |= {f.lower() for f in forms}
            m = re.search(r"(?:대체|keep_only)\s*:\s*([^·(]+)", r.get("note") or "")
            if m:
                replacements[r["label"].lower()] = [x.strip() for x in re.split(r"[,·]", m.group(1)) if x.strip()]
        if "동음이의" in (r.get("note") or "") or "충돌" in (r.get("note") or ""):
            flagged |= {f.lower() for f in forms}
    return brands, noise_seeds, flagged, replacements


def _adapter_patterns(gl: str):
    """adapter.yaml A2.patterns.{common,gl,gl_regex} — 내장 YAML 파서(lib/vertical.py) 우선, 없으면 정규식 추출."""
    if not ADAPTER.exists():
        return [], []
    la = SKILLS_ROOT / "lima-agents"
    if (la / "lib/vertical.py").is_file():
        sys.path.insert(0, str(la))
        try:
            from lib.vertical import load_adapter          # noqa: PLC0415
            ad = load_adapter(SKILL.name, SKILLS_ROOT)
            p = ad.get("A2_noise_lexicon", "patterns") or {}
            return list(p.get("common") or []) + list(p.get(gl) or []), list(p.get(gl + "_regex") or [])
        except Exception:                                  # noqa: BLE001
            pass
    txt = ADAPTER.read_text(encoding="utf8")
    out = []
    for key in ("common", gl):
        m = re.search(rf"^\s+{key}:\s*\[(.*?)\]", txt, re.S | re.M)
        if m:
            out += [x.strip().strip('"\'') for x in m.group(1).replace("\n", " ").split(",") if x.strip()]
    return out, []


def load_noise_re(gl: str):
    pats, rawre = _adapter_patterns(gl)
    parts = [re.escape(x) for x in pats if x] + list(rawre)
    if not parts:
        parts = [re.escape(x) for x in ("영어로", "위키", "wiki", "채용", "주가", "로그인", "드라마", "가사", "youtube", "streaming")]
        return re.compile("|".join(parts), re.I), "builtin"
    return re.compile("|".join(parts), re.I), "adapter:A2"


# ───────────────────────── 판정
def check(seed, gl, queries, brands, anchor_tokens, noise_re, mode="buy", role="category", brand_gate=True):
    noise = [q for q in queries if noise_re.search(q.lower())]
    clean = [q for q in queries if q not in noise]
    toks = [t for t in (anchor_tokens or []) if t]
    if toks:
        fit = [q for q in clean if any(t in q.lower() for t in toks)]
        basis = "anchor"
    else:
        auto = [t for t in re.split(r"\s+", seed.lower()) if len(t) >= 2] or [seed.lower()]
        fit = [q for q in clean if any(t in q.lower() for t in auto)]
        basis = "self(자기충족 — --anchor 지정 권장)"
    hits = sum(1 for q in clean if any(
        re.search(r"(?<![a-z가-힣])" + re.escape(a) + r"(?![a-z])", q.lower()) for a in brands))
    cs = [q for q in clean if CS_RE.search(q)]
    n = len(queries) or 1
    m = {"seed": seed, "gl": gl, "role": role, "mode": mode, "n": len(queries),
         "noise_rate": round(len(noise) / n, 3),
         "fit_rate": round(len(fit) / (len(clean) or 1), 3), "fit_basis": basis,
         "brand_hits": hits, "cs_rate": round(len(cs) / (len(clean) or 1), 3),
         "noise_samples": noise[:5]}
    # 판정 — 역할별 게이트 (seed-verification.md §2)
    if len(queries) < MIN_N and role == "category":
        m["verdict"] = "시드 통합"; m["reason"] = f"표본 {len(queries)}<{MIN_N}"
    elif m["noise_rate"] >= THRESH["noise"]:
        m["verdict"] = "시드 교체"; m["reason"] = "노이즈율"
    elif role == "situation":
        m["verdict"] = "통과"; m["reason"] = "상황 앵커 — 도달률은 측정값"
    elif role == "product":
        m["verdict"] = "통과"; m["reason"] = "제품 앵커 — 적합률 면제·연관어 수는 특성값"
    elif mode == "cs":
        m["verdict"] = "통과" if m["cs_rate"] >= THRESH["cs"] else "시드 교체"
        m["reason"] = "CS 의도율"
    elif m["fit_rate"] < THRESH["fit"]:
        m["verdict"] = "시드 교체"; m["reason"] = "적합률"
    elif brand_gate and m["brand_hits"] < THRESH["brand_hits"]:
        m["verdict"] = "시드 통합"; m["reason"] = "브랜드 히트 부족(사전 공백이면 brand-map 보강 · 비브랜드 카테고리면 --skip-brand-gate)"
    else:
        m["verdict"] = "통과"; m["reason"] = ""
    return m


VMAP = {"통과": "pass", "시드 교체": "replace", "시드 통합": "pool", "폐기(사전 등재)": "discard"}


def _append_registry(rows, a):
    if a.no_registry:
        return
    new = not REGISTRY.exists()
    with REGISTRY.open("a", encoding="utf8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["ts", "gl", "seed", "role", "anchor", "mode", "n", "noise_rate", "fit_rate",
                        "brand_hits", "cs_rate", "verdict", "cost", "note"])
        ts = datetime.date.today().isoformat()
        for m in rows:
            w.writerow([ts, m["gl"], m["seed"], m.get("role", ""), a.anchor, m.get("mode", ""), m["n"],
                        m["noise_rate"], m["fit_rate"], m["brand_hits"], m.get("cs_rate", ""),
                        m["verdict"], m.get("cost", 0), m.get("reason", "")])


def _emit(rows, a, cost, noise_src, client_src):
    if a.json:                                    # seed-check/v1 — 시드당 JSON 1행
        for m in rows:
            v = m["verdict"].split(" · ")[0]
            print(json.dumps({"seed": m["seed"], "gl": m["gl"], "verdict": VMAP.get(v, "replace"),
                              "noise_rate": m["noise_rate"], "fit_rate": m["fit_rate"],
                              "brand_hits": m["brand_hits"], "alt_seeds": m.get("alt_seeds", []),
                              "cost": m.get("cost", 0)}, ensure_ascii=False))
        return
    basis = rows[0].get("fit_basis", "?") if rows else "?"
    print(f"노이즈 사전: {noise_src} · 적합 기준: {basis} · 클라이언트: {client_src} · 모드: {a.mode} · 역할: {a.role}")
    print(f"{'시드':24} {'n':>4} {'노이즈':>7} {'적합':>7} {'브랜드':>6} {'CS':>6}  판정")
    print("-" * 84)
    for m in rows:
        extra = f"  ← {m['reason']}" if m.get("reason") else ""
        alt = f"  대체: {', '.join(m['alt_seeds'])}" if m.get("alt_seeds") else ""
        print(f"{m['seed']:24} {m['n']:>4} {m['noise_rate']:>7.1%} {m['fit_rate']:>7.1%} "
              f"{m['brand_hits']:>6} {m.get('cs_rate', 0):>6.1%}  {m['verdict']}{extra}{alt}")
        if m.get("noise_samples") and m["noise_rate"] >= 0.1:
            print(f"{'':24} 노이즈 예: {' · '.join(m['noise_samples'])}")
    print(f"\n크레딧 {cost} (이번 프로브 소진 · total_cost 합산)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("seeds", nargs="*")
    ap.add_argument("--gl", default="kr", choices=["kr", "us", "jp"])
    ap.add_argument("--anchor", default="", help="앵커 카테고리 어휘 쉼표구분 — fit_rate 기준(권장)")
    ap.add_argument("--mode", default="buy", choices=["buy", "cs"], help="cs: 구매의도 대신 CS 의도율로 판정")
    ap.add_argument("--role", default="category", choices=["category", "situation", "product"])
    ap.add_argument("--replay", default="", help="저장 코퍼스 디렉터리를 API 없이 재채점(0크레딧)")
    ap.add_argument("--dump", default="", help="원본 연관어를 이 디렉터리에 저장(리플레이·코퍼스 확보)")
    ap.add_argument("--key", default="", help="API 키 파일 (기본: 워크스페이스 00_Context/.lm-api-key)")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--json", action="store_true", help="seed-check/v1 계약 출력")
    ap.add_argument("--no-registry", action="store_true", help="seed_registry.csv 기록 생략")
    ap.add_argument("--dict", action="append", default=[], help="분석별 추가 E0 사전(csv) — 여러 번 지정 가능")
    ap.add_argument("--skip-brand-gate", action="store_true",
                    help="비브랜드 카테고리(신선식품·서비스 등) — 브랜드 히트 게이트 생략 (히트는 참고값으로만)")
    a = ap.parse_args()

    brands, noise_seeds, flagged, replacements = load_dict(a.dict)
    anchor = [t.strip().lower() for t in a.anchor.split(",") if t.strip()]
    noise_re, noise_src = load_noise_re(a.gl)
    rows, cost = [], 0

    if a.replay:
        for fp in sorted(Path(a.replay).glob("*.json")):
            o = json.loads(fp.read_text(encoding="utf8"))
            qs = o.get("queries") if "queries" in o else o.get("data", [])
            m = check(o.get("seed", fp.stem), o.get("gl", a.gl), qs or [], brands, anchor, noise_re, a.mode, a.role, not a.skip_brand_gate)
            m["cost"] = 0
            rows.append(m)
        _emit(rows, a, 0, noise_src, "replay")
        return rows

    if not a.seeds:
        ap.error("시드를 하나 이상 주거나 --replay DIR을 지정")
    key_path = a.key or str(((_workspace_root() or SKILL) / "00_Context/.lm-api-key"))
    client, client_src = make_client(key_path)
    for s in a.seeds:
        if s.lower() in noise_seeds:                       # STEP 1 — 0크레딧 차단
            rows.append({"seed": s, "gl": a.gl, "role": a.role, "mode": a.mode, "n": 0, "noise_rate": 1.0,
                         "fit_rate": 0.0, "brand_hits": 0, "cs_rate": 0.0, "verdict": "폐기(사전 등재)",
                         "reason": "E0 Noise", "alt_seeds": replacements.get(s.lower(), []), "cost": 0})
            continue
        r = client.post("intent_finder/keyword_list", {"keywords": [s], "gl": a.gl, "limit": a.limit})
        c1 = (r.get("cost_detail") or {}).get("total_cost", 0)
        cost += c1
        queries = r.get("data", []) or []
        m = check(s, a.gl, queries, brands, anchor, noise_re, a.mode, a.role, not a.skip_brand_gate)
        m["cost"] = c1
        if s.lower() in flagged:
            m["verdict"] += " · 동음이의어 플래그"
        if m["verdict"].startswith("시드 교체"):
            m["alt_seeds"] = replacements.get(s.lower(), [])
        if a.dump:
            d = Path(a.dump); d.mkdir(parents=True, exist_ok=True)
            (d / (re.sub(r"[^0-9A-Za-z가-힣]+", "_", s) + ".json")).write_text(
                json.dumps({"seed": s, "gl": a.gl, "queries": queries, "metrics": m, "cost_detail": r.get("cost_detail"),
                            "request_at": r.get("request_at")}, ensure_ascii=False, indent=1), encoding="utf8")
        rows.append(m)
    _append_registry(rows, a)
    _emit(rows, a, cost, noise_src, client_src)
    return rows


if __name__ == "__main__":
    main()
