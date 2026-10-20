#!/usr/bin/env python3
"""CEP Finder 결정 리포트 렌더러 — run 폴더 → decision_report.html (정의서 v2.3 §12).

엔진(run_cep_finder.py)은 수치를 만들고 summary.md에서 멈춘다. 이 스크립트는 run 폴더의
core/hub_graph.json · out/run_manifest.json · raw/* 를 읽어 지표·차트를 산출하고, 판단이 개입하는
문장(허브 라벨·서사·슬롯 텍스트·결정구조·여정 서술·백로그)은 core/labels.json(schema.json 계약)에서
받아 template.html의 {{…}} 자리를 채운다. 라벨 파일이 없으면 수치만 채우고 서사 자리는
"[labels.json 미작성]"으로 남긴다 — 빈 칸을 지어내지 않는다.

사용:
  python3 render.py 90_Output/<run 폴더>                 # → out/decision_report.html
  python3 render.py <run_dir> --labels core/labels.json --copy-to 90_Output/x.html
재실행은 0크레딧(API 호출 없음). stdlib 전용.
"""
from __future__ import annotations

import argparse, json, re, statistics, collections
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS_ROOT = HERE.parents[2]          # lima_agent/skills
TEMPLATE = HERE / "template.html"

GRADE_CLS = {"measured": ("sl-m", "실측"), "derived": ("sl-d", "산출"),
             "assumption": ("sl-a", "가정"), "gap": ("sl-g", "공백")}
W_NAMES = {"W1": "이유(Why)", "W2": "시점(When)", "W3": "장소(Where)", "W4": "동반자(With whom)", "W5": "함께 쓰는 것(With what)", "W6": "병행 행동(While)", "W7": "감정(Feeling)"}
AGE_KEYS = [("20–24", "a20", "var(--age1)"), ("25–29", "a25", "var(--age2)"), ("30대", "a30", "var(--age3)"),
            ("40대", "a40", "var(--s-1)"), ("50+", "a50", "var(--age5)")]
DEFAULT_TAGS = {   # 여정 노드 태그 — 가전 기본 어휘 (labels.json tag_lexicon으로 덮어쓸 수 있음)
    "가격": r"가격|얼마|세일|할인|싸게|저렴|가성비|최저가",
    "추천·비교": r"추천|순위|비교|vs",
    "중고": r"중고",
    "효율·전기": r"1등급|에너지|효율|전기세|전기요금",
    "소음": r"소음|조용|무소음",
    "용량·크기": r"리터|\d+l\b|용량|사이즈|크기|소형|미니|중형|대형|초소형|인치|kg",
    "수리·고장": r"수리|고장|\bas\b|서비스센터|안시원|안됨|교체",
    "수명": r"수명",
    "설치": r"설치|이전설치|시공",
    "신제품": r"신제품|신상|2025|2026",
}
COMMUNITY = r"디시|dcinside|뽐뿌|클리앙|퀘이사존|블라인드"
CHANNEL = r"하이마트|쿠팡|중고나라|당근|다나와|11번가|지마켓|g마켓|전자랜드|홈쇼핑|네이버쇼핑|이마트|코스트코|costco|best buy|walmart|amazon"

GUARDRAILS_DEFAULT = ("① 모든 수치는 검색량·검색 경로 기준이며 판매량·시장 점유율·실사용 성능이 아님 "
    "② 브랜드 연결은 경로 수 기준 근사(SoV는 검색량 기준 근사) "
    "③ 효율등급·소비전력·용량·소음(dB) 수치는 제조사 공시·공식 출처만 인용, 회피 요인은 소비자 <i>우려 신호</i>이며 제품 성능 진술이 아님 "
    "④ 시즌·이벤트와 검색 상승의 인과는 단정하지 않고 동향으로만 서술 "
    "⑤ 성·연령은 집계 검색 데이터이며 개인 속성·민감 속성을 추정하지 않음 "
    "⑥ 부재를 반증으로 서술하지 않음 — 희박 패밀리는 캔버스 완주 후의 측정값.")


# ────────────────────────── 로드 ──────────────────────────
def jload(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf8"))
    except (OSError, json.JSONDecodeError):
        return default


def load_run(run: Path) -> dict:
    d = {"run": run,
         "hub_graph": jload(run / "core/hub_graph.json", {}),
         "manifest": jload(run / "out/run_manifest.json", {}),
         "head": jload(run / "raw/head_ads_info.json", {}),
         "topup": jload(run / "out/topup_manifest.json", {}),
         "paths": {}, "kwinfo": {}}
    for f in sorted(run.glob("raw/paths_*.json")):
        r = jload(f, {})
        d["paths"][f.stem.replace("paths_", "").replace("_", " ")] = r.get("data") or []
    for f in sorted(run.glob("raw/*kwinfo_all*.json")):
        for item in (jload(f, {}).get("data") or []):
            d["kwinfo"][item["keyword"]] = item
    return d


def load_brand_map(vertical: str, override: Path | None) -> dict:
    """brand-map.md(×/○ 표기 계약) → {brand: regex}. 파싱은 lib/canon.py 단일 파서에 위임한다(정본 소비 규칙).

    정본 브랜드 줄이 0건이면 브랜드 집계를 건너뛰되 **조용히 건너뛰지 않는다** —
    stderr와 BRAND_MAP_WARNINGS에 남긴다. 2026-09-17 확인: 표 형식으로만 쓴 brand-map은 0건으로 읽혀
    업권과 무관한 내장 브랜드로 SoV가 계산되고 있었다."""
    import sys as _sys
    _sys.path.insert(0, str(SKILLS_ROOT / "lima-agents"))
    from lib.canon import load_canon
    canon = load_canon(vertical, override, SKILLS_ROOT)
    rx = canon.regex_map()
    for d in canon.diagnostics:
        BRAND_MAP_WARNINGS.append(f"[정본 진단] {d}")
    if not rx:
        msg = (f"[정본 우회] {vertical}: brand-map 브랜드 줄 0건 → 브랜드 집계를 건너뛴다 — "
               "이 run의 브랜드 집계는 해당 업권 브랜드를 반영하지 않는다")
        BRAND_MAP_WARNINGS.append(msg)
        print(msg, file=_sys.stderr)
        brands = {}
        for b, al in brands.items():
            al = sorted(set(a.lower() for a in al), key=len, reverse=True)
            rx[b] = re.compile("|".join(r"\b" + re.escape(a) + r"\b" if re.match(r"^[a-z]", a) else re.escape(a) for a in al), re.I)
    return rx


BRAND_MAP_WARNINGS: list[str] = []


# ────────────────────────── 지표 ──────────────────────────
def monthly_series(item: dict) -> tuple[list[str], list[int]]:
    mv = sorted(item.get("monthly_volume") or [], key=lambda m: m["month"])
    return [m["month"] for m in mv], [m["total"] for m in mv]


def yoy(vals: list[int]):
    if len(vals) < 25:
        return None
    a, b = sum(vals[-13:-1]), sum(vals[-25:-13])     # 최신 미완월 제외
    return round(a / b - 1, 3) if b else None


def season_idx(months, vals) -> dict:
    by = collections.defaultdict(list)
    for m, v in zip(months, vals):
        by[int(m[5:7])].append(v)
    if len(by) < 12:
        return {}
    med = {k: statistics.median(v) for k, v in by.items()}
    base = statistics.mean(med.values()) or 1
    return {k: round(med[k] / base, 2) for k in sorted(med)}


def amplitude(idx: dict):
    return round(max(idx.values()) / max(min(idx.values()), 0.01), 2) if idx else None


def anomalies(months, vals, z=3.0):
    if len(vals) < 12:
        return []
    mu, sd = statistics.mean(vals), statistics.pstdev(vals) or 1
    return [(m, v, round((v - mu) / sd, 1)) for m, v in zip(months, vals) if (v - mu) / sd > z]


def journey_stats(anchor: str, paths: list, brand_rx: dict, tags: dict) -> dict:
    n = len(paths); tagc = collections.Counter(); brand_paths = 0; brands = collections.Counter()
    nxt = collections.Counter(); prev = collections.Counter(); end = collections.Counter(); uniq = set(); start = 0
    for p in paths:
        uniq.update(p); t = set(); bset = set()
        for node in p:
            if node == anchor:
                continue
            nl = node.lower()
            for b, rx in brand_rx.items():
                if rx.search(nl):
                    # 단독 기업명 쿼리 제외: 노드가 별칭 그 자체(+전자/electronics)면 도달로 세지 않음
                    if re.fullmatch(r"[a-z가-힣]+(전자)?", nl.replace(" ", "")) and len(nl) <= 6 and b.lower() in nl.replace("전자", ""):
                        continue
                    bset.add(b)
            for k, rx in tags.items():
                if re.search(rx, nl):
                    t.add(k)
            if re.search(COMMUNITY, nl): t.add("커뮤니티")
            if re.search(CHANNEL, nl): t.add("채널")
        for k in t: tagc[k] += 1
        for b in bset: brands[b] += 1
        if bset: brand_paths += 1
        end[p[-1]] += 1
        i = p.index(anchor) if anchor in p else -1
        if i == 0: start += 1
        if 0 <= i < len(p) - 1: nxt[p[i + 1]] += 1
        if i > 0: prev[p[i - 1]] += 1
    return {"anchor": anchor, "n": n, "uniq": len(uniq), "start": start, "brand_paths": brand_paths,
            "reach": (brand_paths / n) if n else None, "brands": brands.most_common(),
            "tags": tagc.most_common(), "next": nxt.most_common(8), "prev": prev.most_common(8), "end": end.most_common(8)}


# ────────────────────────── HTML 조각 ──────────────────────────
def esc(s): return str(s)   # labels.json은 신뢰된 내부 작성물 — 인라인 HTML 허용


def pct(x, d=1): return f"{x * 100:.{d}f}%" if x is not None else "—"


def yoy_cell(y):
    if y is None:
        return '<span class="trend">—</span>'
    cls = "up" if y > 0 else "down"
    return f'<span class="trend {cls}">{"▲" if y > 0 else "▼"}{abs(y) * 100:.0f}%</span>'


def hyp_label(h: dict, labels: dict) -> str:
    """가설 제목 — labels.json hypothesis_labels > 가설 label > 서사 첫 구절. 서사를 글자 수로 자르면 문장 중간에서 끊긴다(2026-09-17 제목·문장 검토)."""
    lab = (labels.get("hypothesis_labels") or {}).get(h.get("id")) or h.get("label")
    if lab:
        return lab
    narr = h.get("narrative") or ""
    return narr if len(narr) <= 48 else narr[:48].rsplit(" ", 1)[0] + "…"

def bar_rows(rows, head=("결합쿼리", "허브 내 비중", "월평균", "YoY")):
    tot = sum(r[1] for r in rows) or 1; mx = max(r[1] for r in rows) or 1
    out = [f'<div class="bar-row head"><span></span><span>{head[1]}</span><span style="text-align:right;">{head[2]}</span><span style="text-align:right;">{head[3]}</span></div>']
    for name, v, y in rows:
        out.append(f'<div class="bar-row"><span class="name">{name}</span><div class="bar-track"><div class="bar-fill" style="width:{v / mx * 100:.0f}%"></div></div>'
                   f'<span class="share">{v:,} <span>({v / tot * 100:.0f}%)</span></span>{yoy_cell(y)}</div>')
    return '<div class="bar-rows">' + "".join(out) + "</div>"


def agebar(ages: dict):
    seg = "".join(f'<span title="{l} {ages.get(k, 0):.0f}%" style="width:{ages.get(k, 0)}%;background:{c}"></span>' for l, k, c in AGE_KEYS)
    lab = " · ".join(f"{l} {ages.get(k, 0):.0f}%" for l, k, c in AGE_KEYS)
    return f'<div class="agebar">{seg}</div><div class="agelab">{lab}</div>'


def slot_html(w, spec):
    grade = (spec or {}).get("grade", "gap"); cls, gl = GRADE_CLS.get(grade, GRADE_CLS["gap"])
    text = (spec or {}).get("text") or "—"
    return f'<div class="slot {cls}"><div class="sw">{w} <span>{W_NAMES[w]}</span><em>{gl}</em></div><div class="sv">{esc(text)}</div></div>'


def trend_svg(months, vals, anomaly_months):
    m24, v24 = months[-24:], [round(x / 1000) for x in vals[-24:]]
    ymax = max(v24) * 1.08 or 1; n = len(v24); step = 800 / max(n - 1, 1)
    pts = [(50 + i * step, 240 - (v / ymax) * 220) for i, v in enumerate(v24)]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"M{pts[0][0]:.1f},240 " + " ".join(f"L{x:.1f},{y:.1f}" for x, y in pts) + f" L{pts[-1][0]:.1f},240 Z"
    marks = ""
    for am, av, az in anomaly_months:
        if am in m24:
            i = m24.index(am); x, y = pts[i]
            marks += (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="var(--paper)" stroke="var(--s-2)" stroke-width="2.2"/>'
                      f'<text x="{x - 8:.1f}" y="{y - 10:.1f}" font-size="11.5" fill="var(--s-2)" font-weight="700" text-anchor="end">{am} {round(av / 1000)}k · 이상치(z={az})</text>')
    ip = max(range(n), key=lambda i: v24[i] if m24[i] not in [a[0] for a in anomaly_months] else -1)
    px, py = pts[ip]
    marks += f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="var(--s-1)"/><text x="{px - 8:.1f}" y="{py - 9:.1f}" font-size="11" fill="var(--ink2)" text-anchor="end">{m24[ip]} {v24[ip]}k</text>'
    xt = "".join(f'<text x="{50 + i * step:.1f}" y="262" font-size="10.5" fill="var(--ink3)" text-anchor="middle">{m[2:4]}.{m[5:7]}</text>' for i, m in enumerate(m24) if i % 3 == 0)
    mid = round(ymax / 2); top = round(ymax)
    return (f'<svg id="trend" viewBox="0 0 880 290" width="100%" role="img" aria-label="월별 검색량 최근 24개월">'
            f'<line x1="50" y1="240" x2="850" y2="240" stroke="var(--line)"/><line x1="50" y1="130" x2="850" y2="130" stroke="var(--line)" stroke-dasharray="3 4"/><line x1="50" y1="20" x2="850" y2="20" stroke="var(--line)" stroke-dasharray="3 4"/>'
            f'<text x="44" y="244" font-size="10.5" fill="var(--ink3)" text-anchor="end">0</text><text x="44" y="134" font-size="10.5" fill="var(--ink3)" text-anchor="end">{mid}k</text><text x="44" y="24" font-size="10.5" fill="var(--ink3)" text-anchor="end">{top}k</text>'
            f'<path d="{area}" fill="var(--s-1)" opacity=".10"/><polyline points="{poly}" fill="none" stroke="var(--s-1)" stroke-width="2.2" stroke-linejoin="round"/>{marks}{xt}'
            f'<line id="xh" x1="0" y1="20" x2="0" y2="240" stroke="var(--ink3)" opacity="0"/><rect id="hover" x="50" y="20" width="800" height="220" fill="transparent"/></svg>'), m24, v24


def season_svg(series: list[tuple[str, dict, str]], shade_peak: dict):
    lo, hi = 0.4, max(1.6, max((max(idx.values()) for _, idx, _ in series if idx), default=1.6) + 0.1)
    def Y(v): return 200 - (v - lo) / (hi - lo) * 170
    def X(k): return 60 + (k - 1) * (780 / 11)
    parts = [f'<line x1="60" y1="{Y(1):.1f}" x2="840" y2="{Y(1):.1f}" stroke="var(--ink3)" stroke-dasharray="4 4"/><text x="846" y="{Y(1) + 4:.1f}" font-size="10.5" fill="var(--ink3)">1.0 평월</text>']
    if shade_peak:
        top3 = sorted(shade_peak, key=lambda k: -shade_peak[k])[:3]
        for k in top3:
            parts.append(f'<rect x="{X(k) - 780 / 22:.1f}" y="30" width="{780 / 11:.1f}" height="170" fill="var(--s-2)" opacity=".06"/>')
    colors = ["var(--s-1)", "var(--s-2)", "var(--s-3)"]; lx = 60
    for i, (label, idx, _) in enumerate(series[:3]):
        if not idx: continue
        c = colors[i]; p = [(X(k), Y(idx[k])) for k in range(1, 13)]
        parts.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in p)}" fill="none" stroke="{c}" stroke-width="2.2" stroke-linejoin="round"/>')
        parts += [f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{c}"/>' for x, y in p]
        parts.append(f'<text x="{lx}" y="22" font-size="11.5" fill="{c}" font-weight="700">— {label} (진폭 {amplitude(idx)})</text>'); lx += 260
    parts += [f'<text x="{X(k):.1f}" y="222" font-size="11" fill="var(--ink3)" text-anchor="middle">{k}월</text>' for k in range(1, 13)]
    return f'<svg viewBox="0 0 880 240" width="100%" role="img" aria-label="월별 시즌 지수">{"".join(parts)}</svg>'


def quadrant_svg(points: list[dict], legend: str | None = None):
    if not points:
        return '<p class="note">허브가 없어 4분면을 그리지 않음 — 상황형 진입 0은 측정값이며 기회 부재의 증명이 아님.</p>'
    xs = [p["x"] for p in points if p["x"] is not None] or [-0.1, 0.1]
    xlo, xhi = min(xs) - 0.07, max(xs) + 0.07; xmid = (xlo + xhi) / 2
    def qx(g): return 80 + (g - xlo) / (xhi - xlo) * 720
    def qy(r): return 230 - r * 190
    parts = [f'<rect x="80" y="40" width="720" height="190" fill="none" stroke="var(--line)"/>',
             f'<line x1="{qx(xmid):.1f}" y1="40" x2="{qx(xmid):.1f}" y2="230" stroke="var(--line)" stroke-dasharray="4 4"/><line x1="80" y1="{qy(0.5):.1f}" x2="800" y2="{qy(0.5):.1f}" stroke="var(--line)" stroke-dasharray="4 4"/>',
             '<text x="86" y="54" font-size="11" fill="var(--ink3)">브랜드 연결 높음 · 하락폭 큼 → 방어(연결 브랜드)/공략(경쟁 브랜드)</text>',
             '<text x="794" y="54" font-size="11" fill="var(--ink3)" text-anchor="end">연결 높음 · 상대 견조 → 방어</text>',
             '<text x="86" y="224" font-size="11" fill="var(--ink3)">연결 낮음 · 하락폭 큼 → 선점(시즌 창·저경쟁 시)</text>',
             '<text x="794" y="224" font-size="11" fill="var(--ink3)" text-anchor="end">연결 낮음 · 상대 견조 → 선점</text>']
    colors = ["var(--s-3)", "var(--s-2)", "var(--s-1)"]
    for i, p in enumerate(points):
        x = qx(p["x"] if p["x"] is not None else xmid); y = qy(p["y"] if p["y"] is not None else 0.5)
        r = 18 + 18 * (p.get("size_rank", 0.5))
        if p.get("grey"):
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.0f}" fill="none" stroke="var(--ink3)" stroke-width="2" stroke-dasharray="5 4"/>'
                         f'<text x="{x:.1f}" y="{y - r - 6:.1f}" font-size="12" font-weight="750" fill="var(--ink2)" text-anchor="middle">{p["label"]}</text>'
                         f'<text x="{x:.1f}" y="{y + r + 14:.1f}" font-size="10.5" fill="var(--ink3)" text-anchor="middle">{p["sub"]}</text>')
        else:
            c = colors[i % 3]
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.0f}" fill="{c}" opacity=".18" stroke="{c}" stroke-width="2"/>'
                         f'<text x="{x:.1f}" y="{y + 4:.1f}" font-size="12" font-weight="750" fill="var(--ink)" text-anchor="middle">{p["label"]}</text>'
                         f'<text x="{x:.1f}" y="{y + 18:.1f}" font-size="10.5" fill="var(--ink2)" text-anchor="middle">{p["sub"]}</text>')
    _legend = legend or 'x = 허브 결합쿼리 YoY(최신월 제외) ← 하락 · 견조 →  |  y = 여정 경로 중 브랜드 결합 노드 도달 비율 · 버블 = 허브 규모 · 점선 = 미측정'
    parts.append(f'<text x="440" y="258" font-size="11" fill="var(--ink3)" text-anchor="middle">{esc(_legend)}</text>')
    parts.append(f'<text x="{qx(xlo) + 2:.1f}" y="244" font-size="10" fill="var(--ink3)">{xlo * 100:+.0f}%</text><text x="{qx(xmid):.1f}" y="244" font-size="10" fill="var(--ink3)" text-anchor="middle">{xmid * 100:+.0f}%</text><text x="{qx(xhi) - 2:.1f}" y="244" font-size="10" fill="var(--ink3)" text-anchor="end">{xhi * 100:+.0f}%</text>')
    return f'<svg viewBox="0 0 880 270" width="100%" role="img" aria-label="기회 4분면">{"".join(parts)}</svg>'


def competition_extra(HG: dict, labels: dict) -> str:
    """v0.3 — 스위칭 방향성(B7) + Context×브랜드 매트릭스(B9) 블록. hub_graph에 없으면 빈 문자열."""
    out = []
    sw = HG.get("switching") or {}
    if sw.get("measured"):
        c = sw["counts"]; n = sw["n"]
        def bar(k, col):
            return f'<span style="display:inline-block;width:{c.get(k, 0) / n * 100:.0f}%;height:100%;background:{col}"></span>'
        out_trig = "".join(f"<li><code>{k}</code> {v}</li>" for k, v in (sw.get("switch_out_triggers") or [])[:6]) or "<li>없음</li>"
        in_trig = "".join(f"<li><code>{k}</code> {v}</li>" for k, v in (sw.get("switch_in_triggers") or [])[:6]) or "<li>없음</li>"
        to_s = " · ".join(f"{k} {v}" for k, v in sw.get("switch_out_to") or []); from_s = " · ".join(f"{k} {v}" for k, v in sw.get("switch_in_from") or [])
        note = esc(labels.get("switching_note") or "DERIVED — 방향 비대칭은 '자사 제품을 보던 세션이 경쟁 브랜드도 함께 검토한 비율'로 읽는다. 트리거 노드는 경쟁 검토 직전의 검색어이며 원인이 아니라 위치다.")
        out.append(
            '<div class="sl" style="margin-top:18px">브랜드 간 검색 이동 순서 <span class="badge b-measured">MEASURED</span></div>'
            f'<p class="sub">여정 {n}경로에서 자사·경쟁 브랜드 노드가 함께 나타난 순서 — <b>세션 인접 집계이며 개인의 이탈·전환이 아님</b>(인과 서술 금지)</p>'
            '<div style="height:14px;border-radius:3px;overflow:hidden;display:flex;border:1px solid var(--line);margin-top:8px">'
            + bar("own_only", "var(--s-1)") + bar("own_to_comp", "var(--s-2)") + bar("round_trip", "#b98a3c") + bar("comp_to_own", "var(--s-3)") + bar("comp_only", "var(--ink3)") + bar("none", "var(--line)") + '</div>'
            f'<div class="agelab">자사만 {c.get("own_only", 0)} · <b style="color:var(--s-2)">자사→경쟁 {c.get("own_to_comp", 0)} ({sw["switch_out_rate"]:.0%})</b> · 왕복 {c.get("round_trip", 0)} · <b style="color:var(--s-3)">경쟁→자사 {c.get("comp_to_own", 0)} ({sw["switch_in_rate"]:.0%})</b> · 경쟁만 {c.get("comp_only", 0)} · 무브랜드 {c.get("none", 0)}</div>'
            f'<div class="hgrid"><div><div class="sl">경쟁 브랜드 검색으로 넘어가기 직전 검색어 (→ {to_s or "해당 경로 없음"})</div><ul class="note" style="padding-left:18px;margin-top:4px">{out_trig}</ul></div>'
            f'<div><div class="sl">경쟁 브랜드 검색에서 넘어오기 직전 검색어 (← {from_s or "해당 경로 없음"})</div><ul class="note" style="padding-left:18px;margin-top:4px">{in_trig}</ul></div></div>'
            f'<p class="note">{note}</p>')
    cm = HG.get("context_matrix") or {}
    if cm.get("measured"):
        brands = [b["label"] for b in cm["brands"]]; side = {b["label"]: b["side"] for b in cm["brands"]}
        head = "".join(f'<th style="text-align:right">{b}<span class="veil">{"자사" if side[b] == "own" else "경쟁"}</span></th>' for b in brands)
        rows = []
        for r in cm["rows"]:
            cells = ""
            for b in brands:
                cc = r["cells"].get(b)
                if cc and cc.get("v"):
                    cells += f'<td style="text-align:right;font-variant-numeric:tabular-nums">{cc["v"]:,}</td>'
                else:
                    cells += f'<td style="text-align:right;color:var(--ink3)">{"[없음]" if cc and cc.get("measured") else "미측정"}</td>'
            g = (r["cells"].get("generic") or {}).get("v") or 0
            ov = r["overlap_index"]; ov_txt = f"{ov:.2f}" if ov is not None else "—"
            ov_col = "var(--s-2)" if (ov or 0) >= 0.6 else ("var(--accent)" if (ov or 0) >= 0.3 else "var(--ink3)")
            open_s = f'{r["open_share"]:.0%}' if r["open_share"] is not None else "—"; own_s = f'{r["own_share"]:.0%}' if r["own_share"] is not None else "—"
            rows.append(f'<tr><td>{r["context"]}</td><td style="text-align:right;color:var(--ink3)">{g:,}</td>{cells}<td style="text-align:right;font-weight:700;color:{ov_col}">{ov_txt}</td><td style="text-align:right">{open_s}</td><td style="text-align:right">{own_s}</td></tr>')
        note = esc(labels.get("context_matrix_note") or "DERIVED — 겹침 지수 = min(자사측, 경쟁측) ÷ max(자사측, 경쟁측): 1.0이면 같은 컨텍스트를 같은 규모로 나눠 갖는다. 무브랜드 여지 = 무브랜드 ÷ (무브랜드 + 브랜드합): 높을수록 어느 브랜드도 잡지 못한 컨텍스트. 자사 비중은 검색량 기준 근사이며 판매 점유율이 아님. 별칭은 대표 1형만 결합해 하한에 가깝다.")
        out.append(
            '<div class="sl" style="margin-top:18px">상황별 브랜드 검색량 점유 비교 <span class="badge b-measured">MEASURED</span></div>'
            f'<p class="sub">컨텍스트 × 브랜드 결합쿼리 월평균 검색량 · {cm["n_measured"]}/{cm["n_cells"]}셀 측정 · {esc(cm["denominator_basis"])}</p>'
            f'<div class="tbl"><table><thead><tr><th>컨텍스트</th><th style="text-align:right">무브랜드</th>{head}<th style="text-align:right">겹침 지수</th><th style="text-align:right">브랜드 없는 검색 비중</th><th style="text-align:right">자사 비중</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
            f'<p class="note">{note}</p>')
    return "".join(out)


LAYER_KO = {"situation": "상황(CEP 어휘)", "kbf_context": "KBF·컨텍스트", "feature_variant": "기능 변형", "own_line": "자사 라인", "brand_own": "자사 브랜드",
            "brand_comp": "경쟁 브랜드", "competing_feature": "경쟁 기능", "eval": "평가·이해", "purchase": "구매 근접", "model_code": "모델 코드(모델 선택)", "category_head": "품목 헤드", "category_other": "품목 기타", "other": "기타"}


def feature_block(HG: dict, labels: dict) -> str:
    """v0.4 B8 — 기능 변형·이해형 캔버스 + Feature Association(층별 경로 수·앞/뒤 위치·사슬 순서). 기능 앵커가 아니면 빈 문자열."""
    fe = HG.get("feature") or {}; fa = HG.get("association") or {}
    if not fe and not fa.get("measured"):
        return ""
    out = []
    if fe:
        terms = fe.get("understanding_terms") or []
        head = "".join(f'<th style="text-align:right">{t}</th>' for t in terms)
        rows = "".join(f'<tr><td>{r["term"]}</td><td style="text-align:right;font-weight:700">{(r["v"] or 0):,}</td>'
                       + "".join(f'<td style="text-align:right;{"color:var(--ink3)" if not r["understanding"].get(t) else ""}">{(r["understanding"].get(t) or "[없음]") if not r["understanding"].get(t) else f"{r["understanding"][t]:,}"}</td>' for t in terms)
                       + "</tr>" for r in fe.get("variants", []))
        pairs = " · ".join(f'<code>{p["q"]}</code> {p["v"]:,}' for p in fe.get("pairs", []) if p.get("v")) or "전량 [없음]"
        comps = " · ".join(f'{c.get("brand") or ""} <code>{c["feature"]}</code> {(f"{c["v"]:,}" if c.get("v") else "[없음]")}' for c in fe.get("competing_features", [])) or "미지정"
        out.append(
            '<div class="sl" style="margin-top:18px">기능명에 ‘뜻·단점·후기·차이’를 붙인 검색어의 검색량 <span class="badge b-measured">MEASURED</span></div>'
            '<p class="sub">변형별 월평균 검색량과 "뜻·기능·란·장단점·단점·후기·차이" 결합 — 기능을 이해·검증하는 층의 두께</p>'
            f'<div class="tbl"><table><thead><tr><th>변형</th><th style="text-align:right">월평균</th>{head}</tr></thead><tbody>{rows}</tbody></table></div>'
            f'<p class="note">변형 간 차이·vs: {pairs}<br>경쟁 기능 <span class="badge b-derived">가정</span>: {comps} — 기능 대응 관계는 검색 근거가 아닌 세계지식이며 온톨로지에 <code>competes_with(assumption)</code> 후보로만 적재</p>')
        ct = fe.get("consumer_terms") or []                                                     # v0.6 B14
        if ct:
            gp = fe.get("generic_vs_proper") or {}
            SENSE_KO = {"confirmed": "기능 의미 확인", "ambiguous": "뜻 섞임", "homonym": "동음이의", "unmeasured": "미측정"}
            terms_html = " · ".join(f'<code>{r["term"]}</code> {(f"{r["v"]:,}" if r.get("v") else "[없음]")}' + (f' <span class="veil" style="display:inline">[{SENSE_KO.get(r.get("sense"), r.get("sense"))} · 여정 기준 기능 {r["feature_share"]:.0%} → {r["v_adjusted"]:,}]</span>' if r.get("feature_share") is not None else "") for r in ct)
            ratio = f' (일반어/고유명 {gp["ratio"]}, 환산 후 {gp.get("ratio_adjusted")})' if gp.get("ratio") is not None else ""
            out.append(f'<p class="note"><b>소비자가 이 기능을 부르는 말</b> <span class="badge b-measured">MEASURED</span> — {terms_html} → 일반어 합 {gp.get("consumer_terms", 0):,}(동음이의 환산 {gp.get("consumer_terms_adjusted", 0):,}) vs 고유명 합 {gp.get("proper_variants", 0):,}{ratio}. 일반어의 뜻은 AI 요약이 아니라 검색 여정(path_finder)으로 검증했다(S0b). '
                       '소비자 어휘와 고유명이 다르면 검색어 축이 둘로 갈린다(동의어 중복 가능 · 합은 상한)</p>')
    be = HG.get("benefit") or {}                                                                # v0.6 B13
    if be.get("measured"):
        DIM_KO = {"who": "누가", "when": "언제", "what": "무엇을", "while": "무엇 하면서", "where": "어디서"}
        ROLE_CLS = {"search_target": "b-measured", "weak_signal": "b-derived", "language_only": "b-derived", "narrative_only": "b-derived", "benefit_narrative": "b-derived", "no_evidence": "", "unmeasured": ""}
        rows = []; last_tier = None
        for c in be.get("cells") or []:
            if c.get("tier") and c["tier"] != last_tier:
                last_tier = c["tier"]
                rows.append(f'<tr><td colspan="10" style="background:var(--paper);font-weight:700;color:var(--ink2)">{esc(c["tier"])} · {esc(c.get("tier_label") or "")}</td></tr>')
            top = " · ".join(f'<code>{x["q"]}</code> {x["v"]:,}' for x in (c.get("top") or [])[:3]) or "—"
            rows.append(f'<tr><td><span class="veil" style="display:inline">{c.get("rank", "")}.</span> {esc(c["label"])}<span class="veil">{DIM_KO.get(c["dim"], c["dim"])} · {c["w"]}</span></td><td>{"<br>".join(f"<code>{esc(x['seed'])}</code> <span class='veil' style='display:inline'>{x['n'] if x['n'] is not None else '미수집'}</span>" for x in (c.get("seed_results") or [{"seed": c.get("seed"), "n": c.get("harvested")}]))}</td>'
                        f'<td style="text-align:right">{c["harvested"] if c.get("harvested") is not None else "—"}</td><td style="text-align:right">{c.get("with_volume", 0)}</td>'
                        f'<td style="text-align:right;font-weight:700">{(c.get("volume_sum") or 0):,}</td><td style="text-align:right">{c.get("language_only", 0)}</td><td style="text-align:right;color:var(--ink3)">{c.get("off_feature_n", 0)}</td><td style="text-align:right">{c.get("feature_linked_n", 0)}{(" <span class=veil style=display:inline>" + esc(" · ".join(c.get("linked_examples") or [])[:60]) + "</span>") if c.get("linked_examples") else ""}</td>'
                        f'<td>{top}</td><td>{_serp_cell(c)}</td><td><span class="badge {ROLE_CLS.get(c["verdict"], "")}">{esc(c["role"])}</span></td></tr>')
        vc = be.get("verdict_counts") or {}
        out.append('<div class="sl" style="margin-top:18px">기능 편익을 누가·언제·어디서로 나눈 세부 상황 <span class="badge b-derived">DERIVED</span></div>'
                   f'<p class="sub">편익 "{esc(be.get("benefit") or "")}"를 누가·언제·무엇을·무엇 하면서·어디서로 나눈 {len(be.get("cells") or [])}개 세부 상황 — 셀별 시드 자동 생성·수확(intent_finder vt=0) · '
                   f'검색 타겟 {vc.get("search_target", 0)} · 약한 신호 {vc.get("weak_signal", 0)} · 표현만 {vc.get("language_only", 0)} · <b>기사·AI 요약에만 존재(대두 맥락) {vc.get("narrative_only", 0)}</b> · 편익 어휘만 일치 {vc.get("benefit_narrative", 0)} · 근거 없음 {vc.get("no_evidence", 0)} · 미수집 {vc.get("unmeasured", 0)}<br>정렬: {esc(be.get("sort_rule") or "")}</p>'
                   '<div class="tbl"><table><thead><tr><th>세부 상황</th><th>시드 · 연관어 수</th><th style="text-align:right">수집 연관어(중복 제외)</th><th style="text-align:right">검색량 있는 검색어 수</th><th style="text-align:right">볼륨합</th><th style="text-align:right">표현만</th><th style="text-align:right">기능 무관 검색어 수</th><th style="text-align:right">기능 연결 검색어 수</th><th>상위 검색어</th><th>기사·AI 요약</th><th>캠페인 역할</th></tr></thead>'
                   f'<tbody>{"".join(rows)}</tbody></table></div>'
                   f'<p class="note">{esc(labels.get("benefit_note") or be.get("note") or "")}</p>')
    if fa.get("measured"):
        n = fa["n"]; layers = fa["layers"]
        order = [L for L, _ in fa.get("chain_order", [])]
        chain = " → ".join(f'<b>{LAYER_KO.get(L, L)}</b><span class="veil" style="display:inline">({r:+.2f})</span>' for L, r in fa.get("chain_order", []))
        rows = []
        for L, v in sorted(layers.items(), key=lambda x: -x[1]["paths"]):
            rp = v["mean_relpos"]; w = int(v["share"] * 100)
            pos_txt = "앞(선행)" if (rp or 0) < -0.05 else ("뒤(후행)" if (rp or 0) > 0.05 else "양쪽")
            nodes = " · ".join(f"<code>{nn}</code> {c}" for nn, c in v["top_nodes"][:5])
            rows.append(f'<tr><td>{LAYER_KO.get(L, L)}</td><td><div class="bar-track" style="height:12px"><div class="bar-fill" style="width:{w}%"></div></div></td>'
                        f'<td style="text-align:right;font-variant-numeric:tabular-nums">{v["paths"]} ({v["share"]:.0%})</td><td style="text-align:right">{v["before"]} / {v["after"]}</td>'
                        f'<td style="text-align:right;font-weight:700">{rp:+.2f} <span class="veil">{pos_txt}</span></td><td>{nodes}</td></tr>')
        out.append(
            '<div class="sl" style="margin-top:18px">기능명 검색 뒤 이어지는 검색 순서 — 기능 변형·모델·브랜드·평가 <span class="badge b-derived">DERIVED</span></div>'
            f'<p class="sub">{n}경로 · 앵커 위치 {fa["position"]}{" · <b>전방향 여정(앵커가 전부 시작점 — 선행 층 측정 불가)</b>" if fa.get("forward_only") else ""} · 노드를 어휘 규칙으로 층 분류(derived) · 상대 위치 &lt;0 = 앵커 앞, &gt;0 = 뒤 · 세션 인접 집계</p>'
            f'<p class="narr" style="font-size:13.5px">측정된 사슬 순서: {chain}</p>'
            '<div class="tbl"><table><thead><tr><th>층</th><th style="width:18%">경로 비중</th><th style="text-align:right">경로 수</th><th style="text-align:right">기준 검색어 앞 / 뒤 경로 수</th><th style="text-align:right">평균 위치(앞 − / 뒤 +)</th><th>상위 검색어</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
            f'<p class="note">선행: {" · ".join(f"<code>{k}</code> {v}" for k, v in fa["prev"][:6]) or "—"} / 후행: {" · ".join(f"<code>{k}</code> {v}" for k, v in fa["next"][:6]) or "—"}<br>'
            f'{esc(labels.get("feature_note") or "DERIVED — 제안된 사슬(Need → Feature → Product → Brand → Compare → Evaluate → Purchase)은 여기서 측정된 순서로만 인정한다. 층 어휘 규칙은 sense.layer_lexicon으로 덮어쓸 수 있고, 순서는 집계 순서이지 개인의 단계가 아니다.")}</p>')
    return "".join(out)


def _vol_cell(m: dict) -> str:
    if m.get("v"):
        return f'{m["v"]:,}'
    return '0 <span class="veil" style="display:inline">언어</span>'


def _flags(m: dict) -> str:
    f = []
    if m.get("space_context"): f.append("공간")
    if m.get("noise"): f.append("노이즈")
    return " · ".join(f)


def evidence_block(HG: dict, labels: dict) -> str:
    """v0.5 — S2 증거(AIO·PAA) 요약 + S3 롱테일 코퍼스 통계. 없으면 빈 문자열."""
    ev = HG.get("evidence") or {}; lt = HG.get("longtail") or {}; out = []
    if ev.get("measured"):
        a, n = ev.get("aio_exposure") or (0, 0)
        paa = "".join(f'<li><code>{q["q"]}</code> <span class="veil" style="display:inline">[{q["seed"]}]</span></li>' for q in (ev.get("paa") or [])[:12]) or "<li>없음</li>"
        rel = " · ".join(f'<code>{x["q"]}</code>' for x in (ev.get("related") or [])[:16]) or "없음"
        out.append('<div class="sl" style="margin-top:18px">검색결과 화면·AI 검색 요약에서 발췌한 근거 <span class="badge b-derived">EXTRACTED</span></div>')
        out.append(f'<p class="sub">serp {ev.get("n_seeds", 0)}시드(30크레딧/시드) · AI Overview 노출 <b>{a}/{n}</b> · PAA {len(ev.get("paa") or [])} · 연관검색 {len(ev.get("related") or [])} · 증거 {ev.get("items_n", 0)}건 — 조회 시점 스냅샷, 가설의 원천이지 소비자 발화가 아님</p>')
        out.append(f'<div class="hgrid"><div><div class="sl">PAA(사람들이 함께 묻는 질문)</div><ul class="note" style="padding-left:18px;margin-top:4px">{paa}</ul></div><div><div class="sl">연관검색</div><p class="note" style="margin-top:4px">{rel}</p></div></div>')
    if lt.get("measured"):
        rows = lt.get("rows") or []; top = [r for r in rows if r["v"]][:14]; lang = [r for r in rows if r.get("language_only")][:14]
        nz = lt.get("noise") or {}
        tr = "".join(f'<tr><td>{r["q"]}</td><td style="text-align:right;font-variant-numeric:tabular-nums">{r["v"]:,}</td><td>{r["seed"]}</td><td>{_flags(r)}</td></tr>' for r in top)
        lang_txt = " · ".join(f'<code>{r["q"]}</code>' for r in lang) or "없음"
        note = esc(labels.get("longtail_note") or "DERIVED — 0볼륨 쿼리는 구글 보고 임계 미만의 실제 검색어로, 상황 언어의 존재 근거다. 허브 규모(HUB_FLOOR)에는 합산하지 않고 가설 확증의 언어 근거로만 쓴다. 노이즈는 버리지 않고 플래그한다(개수·볼륨 양 기준).")
        out.append('<div class="sl" style="margin-top:18px">이번에 수집한 세부 검색어 <span class="badge b-measured">MEASURED</span></div>')
        out.append(f'<p class="sub">intent_finder(vt=0) {len(lt.get("seeds") or [])}시드 → {lt["n"]}쿼리 · 볼륨 있음 {lt["with_volume"]} · <b>언어층(0볼륨) {lt["language_only"]}</b> · 미측정 {lt["unmeasured"]} · 노이즈 {nz.get("n", 0)}(개수 {(nz.get("share_n") or 0):.0%} / 볼륨 {(nz.get("share_v") or 0):.0%}) · 공간 맥락 {lt["space_context_n"]} · 볼륨합 {lt["volume_sum"]:,}</p>')
        out.append(f'<div class="hgrid"><div><div class="tbl"><table><thead><tr><th>상위 쿼리(볼륨)</th><th style="text-align:right">월평균</th><th>시드</th><th>플래그</th></tr></thead><tbody>{tr}</tbody></table></div></div>'
                   f'<div><div class="sl">검색량은 집계되지 않지만 실제로 쓰이는 검색 표현 예시 (규모 합계에서 제외)</div><p class="note" style="margin-top:4px">{lang_txt}</p><p class="note">{note}</p></div></div>')
    return "".join(out)


def slot_html_simple(w, text):
    grade = "assumption" if text else "gap"; cls, gl = GRADE_CLS[grade]
    return f'<div class="slot {cls}"><div class="sw">{w} <span>{W_NAMES[w]}</span><em>{gl}</em></div><div class="sv">{esc(text or "—")}</div></div>'


def hypothesis_block(HG: dict, labels: dict, only_candidates: bool = False) -> str:
    """v0.5 — S5 가설 카드: 서사(assumption)·슬롯·매칭 키워드(언어층 표기)·근거 강도·성립 요건·승격 판정. only_candidates=본문용(후보·승격만)."""
    hy = HG.get("hypotheses") or {}
    promoted = labels.get("promoted") or {}
    if hy.get("status") == "awaiting_llm":
        return '<div class="sl" style="margin-top:18px">S5 · 가설 선행 <span class="badge b-derived">대기</span></div><p class="note">core/hypothesis_tasks.json 발주 상태 — 가설 작성 후 <code>--hypotheses</code>로 확증 재실행(0크레딧).</p>'
    if hy.get("status") != "confirmed":
        return ""
    cards = []
    for h in hy.get("hypotheses") or []:
        st = h["status"]; v = h["hub_verdict"]
        pr = promoted.get(h["id"])
        if only_candidates and not (v == "candidate" or pr): continue
        badge = (f'<span class="st st-c">confirmed · {pr["id"]}</span>' if pr else ('<span class="st st-c">candidate</span>' if v == "candidate" else f'<span class="st st-r">{v}</span>'))
        sbadge = f'<span class="badge {"b-measured" if st == "supported" else "b-derived"}">{st} · {h["strength"]}</span>'
        slots = h.get("slots") or {}
        slot_html = "".join(slot_html_simple(w, (slots.get(w) or {}).get("text")) for w in ("W1", "W2", "W3", "W4", "W5", "W6", "W7"))
        mk = h.get("matched") or []
        kws = "".join(f'<tr><td>{m["q"]}</td><td style="text-align:right;font-variant-numeric:tabular-nums">{_vol_cell(m)}</td><td>{_flags(m)}</td></tr>' for m in mk[:12])
        if not kws:
            kws = f'<tr><td colspan="3" style="color:var(--ink3)">매칭 키워드 없음 — unsupported 보존 · {esc(h.get("unsupported_reason") or "")}</td></tr>'
        req = h.get("requirements") or {}; req_txt = " · ".join(f'{k} {"✓" if ok else "✗"}' for k, ok in req.items())
        ni = "".join(f"<li>{x}</li>" for x in (h.get("nano_intents") or [])); kb = "".join(f"<li>{x}</li>" for x in (h.get("kbf") or []))
        side = ""
        if ni: side += '<div class="sl">원하는 해결 방식</div><ul class="note" style="padding-left:18px;margin-top:4px">' + ni + "</ul>"
        if kb: side += '<div class="sl">KBF(근거 키워드 병기 의무)</div><ul class="note" style="padding-left:18px;margin-top:4px">' + kb + "</ul>"
        b = h["backing"]; deferred = " (HUB_FLOOR 미달 — 보류·보존)" if v == "deferred" else ""
        cards.append(
            f'<div class="hub{"" if (v == "candidate" or pr) else " grey"}">'
            f'<div class="hhead"><span class="hid">{h.get("id", "")}</span><h3>{esc(hyp_label(h, labels))}</h3>{badge}{sbadge}<span class="badge b-derived">서사 · 가정</span></div>'
            f'<p class="narr">{esc(h.get("narrative", ""))}</p>'
            f'<div class="hgrid"><div><div class="tbl"><table><thead><tr><th>관련 검색어 (이번에 수집한 검색어 중 일치)</th><th style="text-align:right">월평균</th><th>플래그</th></tr></thead><tbody>{kws}</tbody></table></div>'
            f'<p class="note">근거 강도 — 매칭 <b>{b["matched_n"]}</b>(예측 {b.get("predicted_n", b["matched_n"])} · <b style="color:var(--s-2)">post-hoc 태깅 {b.get("tagged_n", 0)}</b> · 언어층 {b["language_only_n"]}) · 볼륨합 <b>{b["volume_sum"]:,}</b> · co_path {b["co_path"]} · {esc(b["denominator_basis"])}<br>성립 요건 — {req_txt} · 슬롯 {h.get("slot_coverage", 0)}/7 · 판정 <b>{v}</b>{deferred}{(" → 강등 대상: " + esc(h["demoted_to"])) if h.get("demoted_to") else ""}</p></div>'
            f'<div>{side}</div></div><div class="slots">{slot_html}</div></div>')
    if only_candidates:
        head = (f'<div class="sl" style="margin-top:18px">가설을 세워 검색 데이터로 확인한 진입점 — 후보 {len(cards)}건 <span class="badge b-derived">DERIVED</span></div>'
                f'<p class="sub">{"블라인드 작성" if hy.get("blind") else "코퍼스 노출 작성"} · match={hy.get("match")} · 전체 {hy["n"]}건의 판정표는 부록 A2 — 서사는 가정, 매칭 키워드는 측정, 승격은 성립 요건 + strong</p>')
        return head + "".join(cards)
    head = (f'<div class="sl" style="margin-top:18px">S5 · 가설 선행 — 상황 가설과 키워드 확증 <span class="badge b-derived">DERIVED</span></div>'
            f'<p class="sub">가설 {hy["n"]}건(prompt {hy.get("prompt_version") or "?"}) · supported {hy["supported"]} · unsupported {hy["unsupported"]} · 기각률 <b>{(hy.get("rejection_rate") or 0):.0%}</b>(예측 키워드만 {(hy.get("rejection_rate_predicted_only") or 0):.0%} · post-hoc 태깅 {hy.get("post_hoc_n", 0)}건){" — 0%는 편향 신호" if hy.get("rejection_rate") == 0 else ""} · 허브 후보 {len(hy.get("hypothesis_hubs") or [])}(승격률 {(hy.get("selection_rate") or 0):.0%}) · {"블라인드 작성" if hy.get("blind") else "코퍼스 노출 작성"} · match={hy.get("match")} — 서사는 가정, 매칭 키워드는 측정, 승격은 성립 요건 + strong(매칭 ≥3 · HUB_FLOOR)</p>')
    tail = f'<p class="note">{esc(labels.get("hypothesis_note") or "가설은 AIO·PAA·롱테일에서 세워졌고(assumption) 코퍼스 밖 키워드는 근거로 쓰지 않았다. unsupported·deferred는 삭제하지 않고 다음 run에서 재판정한다.")}</p>'
    return head + "".join(cards) + tail


def merge_block(HG: dict, labels: dict) -> str:
    """v0.5 S6 — 허브 구별성·병합 판정 매트릭스(자카드·포함도)와 통합 제안. merge 없으면 빈 문자열."""
    mg = HG.get("merge") or {}
    if not mg.get("pairs"):
        return ""
    units = mg.get("units") or []; ids = [u["id"] for u in units]; lab = {u["id"]: (u.get("label") or u["id"]) for u in units}
    P = {}
    for p in mg["pairs"]:
        P[(p["a"], p["b"])] = p; P[(p["b"], p["a"])] = p
    def cell(a, b):
        if a == b: return '<td style="background:var(--line);text-align:center">—</td>'
        p = P.get((a, b))
        if not p: return "<td></td>"
        j = p["jaccard"]; v = p["verdict"]
        col = "var(--s-2)" if v == "병합 제안" else ("#b98a3c" if v in ("사람 판단",) or v.startswith("흡수") else ("var(--accent)" if v.startswith("연관") else "var(--ink3)"))
        return f'<td style="text-align:center;font-variant-numeric:tabular-nums;color:{col};font-weight:{"700" if j >= 0.3 or v.startswith("흡수") else "400"}" title="{v} · 포함 {p["containment"]:.2f} · 공유 {", ".join(p["shared_tokens"][:5])}">{j:.2f}</td>'
    hub_short = {h.get("id"): h.get("short") for h in labels.get("hubs") or [] if h.get("short")}
    short = lambda i: esc(hub_short.get(i) or (lab.get(i) or i.replace("CEP-", "")).split(" — ")[0])   # 내부 id·엔진 패밀리명(전이형) 대신 진입점 짧은 이름 — 2026-09-17 제목·문장 검토
    head = "".join(f'<th style="text-align:center;font-size:10.5px">{short(i)}</th>' for i in ids)
    rows = "".join(f'<tr><td style="font-size:12px">{short(i)}</td>' + "".join(cell(i, k) for k in ids) + "</tr>" for i in ids)
    notable = [p for p in mg["pairs"] if p["verdict"] != "유지"][:10]
    nl = "".join(f'<li><b>{p["a"]} × {p["b"]}</b> J={p["jaccard"]:.2f}(렉심 {p["jaccard_lexeme"]:.2f} · 토큰 {p["jaccard_token"]:.2f} · 포함 {p["containment"]:.2f}) · 공유 {" · ".join(f"<code>{t}</code>" for t in p["shared_tokens"][:6]) or "—"} → <b>{p["verdict"]}</b></li>' for p in notable) or "<li>임계 이상 쌍 없음 — 전 허브 유지</li>"
    cons = " · ".join(("<b>" + " ⊕ ".join(c["members"]) + "</b>") if c["proposed"] else c["members"][0] for c in mg.get("consolidated") or [])
    th = mg.get("thresholds") or {}
    note = esc(labels.get("merge_note") or f"DERIVED — 자카드는 렉심 집합(키워드에서 품목 제거 · 긴 슬롯 서술 제외) 기준이며 토큰 자카드·포함도(overlap/min)를 병기. 임계: 병합 ≥{th.get('merge')} · 사람 판단 ≥{th.get('human')} · 흡수 = 포함도 ≥{th.get('absorb_containment')} & J≥{th.get('related')}. 최종 병합·분리는 승인 세션의 판단.")
    return ('<div class="sl" style="margin-top:18px">진입점끼리 얼마나 겹치는지 — 겹침 정도 비교표 <span class="badge b-derived">DERIVED</span></div>'
            f'<p class="sub">허브 {len(ids)}(패밀리 세분 + 가설 후보) · 쌍 {len(mg["pairs"])} · 셀 = 자카드(호버: 판정·포함도·공유 토큰)</p>'
            f'<div class="tbl"><table><thead><tr><th></th>{head}</tr></thead><tbody>{rows}</tbody></table></div>'
            f'<div class="sl">많이 겹치는 진입점 쌍</div><ul class="note" style="padding-left:18px;margin-top:4px">{nl}</ul>'
            f'<p class="note">통합 제안: {cons}<br>{note}</p>')


VERDICT_ORDER = {"confirmed": 0, "candidate": 1, "grey": 2, "deferred": 3, "demoted(요건 미달)": 4, "unsupported": 5}


def registry_table(HG: dict, labels: dict, hubs: list) -> str:
    """01 진입점 지도 — 패밀리/상속 허브(labels) + 가설 허브(전 판정)를 한 표로. 상태·규모·근거·최근접 자카드."""
    promoted = labels.get("promoted") or {}
    mg = HG.get("merge") or {}; near = {}
    for p in mg.get("pairs") or []:
        for a, b in ((p["a"], p["b"]), (p["b"], p["a"])):
            if p["jaccard"] > near.get(a, (0, None))[0]: near[a] = (p["jaccard"], b)
    rows = []
    for h in hubs:
        hs = h["spec"]; st = hs.get("status", "candidate")
        rows.append({"id": hs.get("id", ""), "label": hs.get("label", ""), "kind": "상속" if h.get("inherited") else "패밀리 허브", "status": st,
                     "vol": h["sum"], "co": (h["journey"] or {}).get("n") if h.get("journey") else None, "evid": "결합쿼리 실측" + (" + 여정" if h.get("journey") else ""), "near": near.get(hs.get("id", "").split(" ")[0])})
    for y in (HG.get("hypotheses") or {}).get("hypotheses") or []:
        v = y.get("hub_verdict", ""); pr = promoted.get(y["id"])
        st = "confirmed" if pr else ("candidate" if v == "candidate" else v)
        b = y.get("backing") or {}
        rows.append({"id": (pr or {}).get("id") or y["id"], "label": y.get("label", ""), "kind": "가설(블라인드)" if (HG.get("hypotheses") or {}).get("blind") else "가설",
                     "status": st, "vol": b.get("volume_sum", 0), "co": b.get("co_path"), "evid": f'예측 {b.get("predicted_n", 0)}' + (f' · 태깅 {b.get("tagged_n")}' if b.get("tagged_n") else "") + (f' · 언어 {b.get("language_only_n")}' if b.get("language_only_n") else ""), "near": near.get(y["id"]),
                     "demoted": y.get("demoted_to")})
    rows.sort(key=lambda r: (VERDICT_ORDER.get(r["status"], 9), -(r["vol"] or 0)))
    hidden = [r for r in rows if r["status"] in ("demoted(요건 미달)", "unsupported")]
    if labels.get("registry_hide_rejected", True):
        rows = [r for r in rows if r["status"] not in ("demoted(요건 미달)", "unsupported")]
    mx = max((r["vol"] or 0) for r in rows) or 1
    def stcell(r):
        s = r["status"]; cls = "st-c" if s == "confirmed" else "st-r"
        txt = {"confirmed": "confirmed", "candidate": "candidate", "grey": "회색(근거 보강)", "deferred": "보류", "demoted(요건 미달)": "강등", "unsupported": "기각"}.get(s, s)
        return f'<span class="st {cls}">{txt}</span>' + (f'<span class="veil">→ {esc(r["demoted"])}</span>' if r.get("demoted") else "")
    tr = "".join(
        f'<tr><td>{r["id"]}<span class="veil">{esc(r["label"] if len(r["label"]) <= 40 else r["label"][:40].rsplit(" ", 1)[0] + "…")}</span></td><td style="font-size:12px">{r["kind"]}</td><td>{stcell(r)}</td>'
        f'<td style="font-variant-numeric:tabular-nums"><span class="bar{" grey" if r["status"] in ("grey", "deferred", "demoted(요건 미달)", "unsupported") else (" hyp" if "가설" in r["kind"] else "")}" style="width:{(r["vol"] or 0) / mx * 90:.0f}px"></span>{(r["vol"] or 0):,}</td>'
        f'<td style="text-align:right">{r["co"] if r["co"] is not None else "—"}</td><td style="font-size:12px">{r["evid"]}</td>'
        f'<td style="font-size:12px">{(f"{r[chr(110)+chr(101)+chr(97)+chr(114)][1]} {r[chr(110)+chr(101)+chr(97)+chr(114)][0]:.2f}" if r.get("near") and r["near"][1] else "—")}</td></tr>' for r in rows)
    foot = (f'<p class="note">재분류·기각 {len(hidden)}건({", ".join(r["id"] for r in hidden)})은 본문에서 제외 — 부록 A2 가설 전수표 참조</p>' if hidden and labels.get("registry_hide_rejected", True) else "")
    return (f'<table class="reg"><thead><tr><th>진입점</th><th>유형</th><th>상태</th><th>규모(월 · 상황+품목 검색어 합)</th><th style="text-align:right">함께 나온 검색 경로 수</th><th>근거</th><th>가장 비슷한 진입점과 겹침 정도</th></tr></thead><tbody>{tr}</tbody></table>' + foot)


def _chain_html(h: dict) -> str:
    """v0.6 — 가설별 증거 사슬 행: ① serp 발췌(시드·수집시각·원본) ② 검색어(수확 시드·실측·사후) ③ 여정 동반 경로 ④ 관계망 사용 여부."""
    ch = h.get("evidence_chain") or {}
    if not ch: return ""
    serp = "".join(
        f'<li>{"✓" if c.get("resolved") else "✗ 원문 미확인"}{" (시드 일치·원문 근사)" if c.get("loose") else ""} <b>{(c.get("kind") or "").upper()}</b> [{esc(c.get("seed") or "")}] {esc((c.get("text") or c.get("claim") or "")[:170])}'
        + (f' <span class="veil" style="display:inline">{esc(c.get("collected_at") or "")} · {esc(c.get("raw_file") or "")}</span>' if c.get("raw_file") else "") + "</li>"
        for c in ch.get("serp") or []) or "<li>원천 인용 없음 — 가설 작성자가 source_evidence를 남기지 않음</li>"
    kws = " · ".join(f'<code>{esc(k["q"])}</code> {(f"{k["v"]:,}" if k.get("v") else ("0(표현만)" if k.get("language_only") else "미측정"))}<span class="veil" style="display:inline">[{esc(k.get("harvest_seed") or "")}{" · 사후" if k.get("post_hoc") else ""}]</span>'
                     for k in ch.get("keywords") or []) or "없음"
    pth = ch.get("paths") or {}
    paths = "".join(f'<li><code>{esc(" → ".join(p["path"]))}</code> <span class="veil" style="display:inline">{esc(p["raw_file"])}</span></li>' for p in pth.get("examples") or []) or "<li>동반 경로 없음</li>"
    return (f'<tr><td colspan="8" style="background:var(--paper);padding:10px 12px"><div class="hgrid">'
            f'<div><div class="sl">① 검색결과 화면 근거 (발췌 · 확인 안 된 항목 {ch.get("unresolved_claims", 0)}건)</div><ul class="note" style="padding-left:16px;margin-top:4px">{serp}</ul></div>'
            f'<div><div class="sl">② 검색어 근거 — 연관 검색어의 실측 검색량</div><p class="note" style="margin-top:4px">{kws}</p>'
            f'<div class="sl" style="margin-top:8px">③ 여정 근거 — 검색 여정 {pth.get("n", 0)}경로 중 함께 나타난 경로 {pth.get("co_path", 0)}</div><ul class="note" style="padding-left:16px;margin-top:4px">{paths}</ul>'
            f'<p class="note">④ 관계망(cluster_finder): {esc((ch.get("cluster") or {}).get("note") or "")}</p></div></div></td></tr>')


def _serp_cell(c: dict) -> str:
    n = c.get("serp_hits") or 0
    if not n and not (c.get("benefit_narrative_hits") or 0): return '<span class="veil" style="display:inline">없음</span>'
    ex = (c.get("serp_examples") or [{}])[0]
    nsr = c.get("narrative_seed_results") or []
    ns_txt = (" · 서사 시드 " + " / ".join(f"‘{esc(x['seed'])}’ {x['relevant'] if x['relevant'] is not None else '미수집'}+{x.get('benefit_only') or 0}/{x['items'] if x['items'] is not None else '-'}" for x in nsr)) if nsr else ""
    bn = c.get("benefit_narrative_hits") or 0
    if not n and bn:
        bx = (c.get("benefit_examples") or [{}])[0]
        return f'<b>0</b> · 편익 어휘만 <b>{bn}</b>{ns_txt} <span class="veil" style="display:inline">{esc((bx.get("kind") or "").upper())}[{esc(bx.get("seed") or "")}] “{esc((bx.get("text") or "")[:70])}…”</span>'
    return f'<b>{n}</b>{(" · 편익 어휘만 " + str(bn)) if bn else ""}{ns_txt} <span class="veil" style="display:inline">{esc((ex.get("kind") or "").upper())}[{esc(ex.get("seed") or "")}] “{esc((ex.get("text") or "")[:70])}…”</span>'


def credit_ledger_block(workdir) -> str:
    """크레딧 원장 — raw/ 원본의 cost_detail.total_cost 전수 합산(재현 원본과 1:1).
    manifest의 calls 기록과 달리 라이브·보강·재수확을 구분 없이 실제 응답 기준으로 집계한다.
    _archive* 하위는 '아카이브(현행 재현에 미사용)'로 분리 표기."""
    import glob as _glob
    def _tool(o):
        rd = o.get("request_detail") or {}
        if "hop" in rd: return "cluster_finder"
        if "num" in rd or "device" in rd: return "serp"
        if "volume_threshold" in rd: return "intent_finder"
        if "data_type" in rd or "keywords" in rd: return "keyword_info"
        if "keyword" in rd: return "path_finder"
        return "기타"
    def _walk(o, acc):
        if isinstance(o, dict):
            cd = o.get("cost_detail")
            if isinstance(cd, dict) and "total_cost" in cd:
                acc.append((_tool(o), cd["total_cost"]))
            for v in o.values(): _walk(v, acc)
        elif isinstance(o, list):
            for v in o: _walk(v, acc)
    per, calls, arch = {}, {}, 0
    for fp in _glob.glob(str(workdir / "raw" / "**" / "*.json"), recursive=True):
        try:
            with open(fp, encoding="utf-8") as f: o = json.load(f)
        except Exception:
            continue
        acc = []; _walk(o, acc)
        for tool, c in acc:
            if "_archive" in fp: arch += c; continue
            per[tool] = per.get(tool, 0) + c; calls[tool] = calls.get(tool, 0) + 1
    total = sum(per.values())
    if not total: return ""
    rows = []
    for tool, c in sorted(per.items(), key=lambda x: -x[1]):
        share = c / total * 100
        rows.append(f'<tr><td>{tool}</td><td style="text-align:right">{calls[tool]:,}</td>'
                    f'<td style="text-align:right"><b>{c:,}</b></td><td style="text-align:right">{share:.0f}%</td></tr>')
    arch_note = f' · v0.1 아카이브(현행 재현 미사용) 별도 {arch:,}크레딧' if arch else ""
    return (
        '<div class="sl" style="margin-top:18px">데이터 조회 비용(크레딧) 내역 — 원자료 기준 <span class="badge b-measured">MEASURED</span></div>'
        '<div class="tbl"><table><tr><th>커넥터</th><th style="text-align:right">응답 수</th>'
        '<th style="text-align:right">크레딧</th><th style="text-align:right">비중</th></tr>'
        + "".join(rows) +
        f'<tr><td><b>합계</b></td><td style="text-align:right">{sum(calls.values()):,}</td>'
        f'<td style="text-align:right"><b>{total:,}</b></td><td style="text-align:right">100%</td></tr></table></div>'
        f'<p class="note">raw/ 응답의 cost_detail.total_cost 전수 합산 — 이 원장과 저장된 원자료가 1:1이므로 재계산할 때의 비용 기준이다. '
        f'manifest calls 기록과 차이가 나면 원장이 우선한다{arch_note}. used_credits는 당월 누적 사용량이며 잔여량이 아니다.</p>')


def provenance_block(HG: dict, labels: dict) -> str:
    """v0.6 — 지표 산출 근거표: 리포트의 모든 수치가 어느 커넥터의 어느 필드에서 어떤 계산으로 나왔는지."""
    hg_hy = HG.get("hypotheses") or {}; be = HG.get("benefit") or {}
    rows = [
        ("월평균 검색량", "keyword_info · ads_metrics.volume_avg", "네이버+구글 월평균 검색 횟수(최근 기간) · 검색어 묶음은 단순 합(동의어 중복 가능 → 상한)", "raw/*ads_metrics*.json · raw/*ads_info*.json · raw/*kwinfo_all*.json"),
        ("추세(전년 대비)", "keyword_info · ads_metrics.volume_trend", "기간 대비 증감률(-1~∞) · +30% 이상 급성장, -50% 이하 급락 기준", "동일"),
        ("월별 시즌 지수", "keyword_info · monthly_volume (24~48개월)", "달력월별 중앙값 ÷ 12개월 평균 (1.0 = 평월) · 묶음은 검색량 가중 평균 · 인과 단정 없음", "raw/*kwinfo_all*.json · raw/*ads_info*.json"),
        ("성·연령", "keyword_info(all) · demography.f_gender_ratio · a20~a50_ratio", "검색량 가중 평균 · 집계 검색 데이터(개인 추정 없음) · gl=kr 전용", "raw/*kwinfo_all*.json"),
        ("광고비·경쟁", "keyword_info · ads_metrics.cpc(USD) · competition", "구글 광고 추정가 · 시점 변동", "동일"),
        ("검색어 의도 구분", "keyword_info(all) · intents{i,n,c,t}", "정보형/내비게이션/비교형/구매형 플래그 → '어떤 사람 → 무엇으로'", "raw/*kwinfo_all*.json"),
        ("세부 검색어(롱테일)·표현 근거", "intent_finder(volume_threshold=0) → keyword_info ads_info", "시드별 연관 검색어 수확 후 1크레딧/건 실측 · 0볼륨은 표현 근거(규모 합산 금지)", "raw/longtail_*.json · raw/longtail_ads_info*.json · raw/benefit_ads_info*.json"),
        ("검색결과 화면 근거(AI 요약·연관 질문·자연결과)", "serp · ai_overview · people_also_ask · organic", "조회 시점 스냅샷(발췌) · 가설의 원천이지 소비자 발화 아님", "raw/serp_*.json (request_at 보존)"),
        ("여정·동반 경로(co_path)", "path_finder", "앵커 검색어 전후 세션 인접 경로 · 가설 어휘 포함 경로 수 · 집계 행동(개인 여정 아님)", "raw/paths_*.json"),
        ("가설 판정(근거 있음/기각/재분류)", "엔진 S5", "예측 검색어가 수집 검색어와 일치(엄격=완전·접두/접미, 느슨=부분) · 요건: 구매 전·Why 필수·When|Where·3요소·검색어 ≥1 · 후보 = 매칭 ≥3 & 볼륨합 ≥500" + (f" · 이 run 기각률 {(hg_hy.get('rejection_rate') or 0):.0%}" if hg_hy.get("status") == "confirmed" else ""), "core/hub_graph.json › hypotheses"),
        ("볼륨합(근거 강도)", "엔진 S5", "매칭 검색어 volume_avg 합 · 표현 근거(0)·기능 외(off_feature) 제외 · 규모가 아니라 근거 강도", "동일"),
        ("중복도(자카드)", "엔진 S6", "핵심 어휘 집합 교집합/합집합 · ≥0.7 병합 · 0.6~0.7 사람 판단", "core/hub_graph.json › merge"),
    ]
    if be.get("measured"):
        fl = be.get("floor") or {}
        rows.append(("편익 세부 상황 판정(검색 타겟/약한 신호/표현만/근거 없음)", "엔진 S3c(B13)", f"셀 시드 → intent_finder(vt=0) 수확 → ads_info 실측 · 검색 타겟 = 볼륨 있는 검색어 ≥{fl.get('min_queries', 3)} & 합 ≥{fl.get('hub_floor', 500):,} · 노이즈·기능 외 제외", "core/hub_graph.json › benefit · raw/longtail_*.json"))
    if HG.get("feature"):
        rows.append(("소비자 일반어 vs 고유명", "keyword_info · ads_metrics(B14 기능 사전)", "일반어 볼륨 합 ÷ 고유명 변형 볼륨 합", "raw/consumer_terms_ads_metrics.json · raw/feature_variants_ads_metrics.json"))
    if HG.get("context_matrix", {}).get("measured") if isinstance(HG.get("context_matrix"), dict) else False:
        rows.append(("상황별 브랜드 점유(겹침·무브랜드 여지)", "keyword_info · ads_metrics", "브랜드×컨텍스트 결합 검색어 볼륨 매트릭스 · 검색량 기준 근사", "raw/context_matrix*.json"))
    tr = "".join(f"<tr><td>{esc(a)}</td><td><code>{esc(b)}</code></td><td>{esc(c)}</td><td><span class='veil' style='display:inline'>{esc(d)}</span></td></tr>" for a, b, c, d in rows)
    return ('<div class="sl" style="margin-top:14px">지표 산출 근거 — 모든 수치의 원천·계산</div>'
            f'<div class="tbl"><table class="cmp"><thead><tr><th>지표</th><th>데이터 출처 · 항목</th><th>계산·해석 규칙</th><th>원본 파일</th></tr></thead><tbody>{tr}</tbody></table></div>'
            f'<p class="note">{esc(labels.get("provenance_note") or "raw/ 원본은 API 응답 그대로(요청 파라미터·cost_detail 포함) 보존되며 원자료로 0크레딧 재계산할 수 있다. 여기 없는 수치는 이 리포트에 쓰지 않았다.")}</p>')


def hypothesis_table(HG: dict, labels: dict) -> str:
    hy = HG.get("hypotheses") or {}
    if hy.get("status") != "confirmed":
        return '<p class="note">가설 확증 없음(발주 대기 또는 미실행)</p>'
    promoted = labels.get("promoted") or {}
    tr = "".join(
        f'<tr><td>{h["id"]}{(" → " + promoted[h["id"]]["id"]) if h["id"] in promoted else ""}</td><td>{esc(h.get("label") or "")}</td><td>{h["status"]}/{h["strength"]}</td>'
        f'<td style="text-align:right">{h["backing"]["predicted_n"]}/{h["backing"].get("tagged_n", 0)}/{h["backing"]["language_only_n"]}</td><td style="text-align:right;font-variant-numeric:tabular-nums">{h["backing"]["volume_sum"]:,}</td>'
        f'<td style="text-align:right">{h["backing"]["co_path"]}</td><td>{" ".join(("✓" if ok else "✗") for ok in (h.get("requirements") or {}).values())}</td><td>{h["hub_verdict"]}{(" → " + esc(h["demoted_to"])) if h.get("demoted_to") else ""}</td></tr>' + _chain_html(h) for h in hy["hypotheses"])
    return (f'<p class="sub">가설 {hy["n"]}건 · {"블라인드" if hy.get("blind") else "코퍼스 노출"} · match={hy.get("match")} · supported {hy["supported"]} · unsupported {hy["unsupported"]} · 기각률 {(hy.get("rejection_rate") or 0):.0%}(예측만 {(hy.get("rejection_rate_predicted_only") or 0):.0%}) · 후보 {hy.get("candidates", 0)}(승격률 {(hy.get("selection_rate") or 0):.0%})</p>'
            f'<div class="tbl"><table class="cmp"><thead><tr><th>ID</th><th>가설</th><th>근거 강도</th><th style="text-align:right">근거 건수(예측/태깅/언어)</th><th style="text-align:right">볼륨합</th><th style="text-align:right">함께 나온 검색 경로 수</th><th>성립 요건(구매 전·이유·시점/장소·상황 요소 3개·검색어)</th><th>판정</th></tr></thead><tbody>{tr}</tbody></table></div>')


def key_messages_block(labels: dict, auto: list) -> str:
    kms = labels.get("key_messages") or auto
    return "".join(f'<div class="k"><div class="h">{esc(k["headline"])}</div><div class="e">{esc(k.get("evidence", ""))}</div>' + (f'<div class="i">→ {esc(k["implication"])}</div>' if k.get("implication") else "") + "</div>" for k in kms)



# ────────────────────────── 비즈니스 사용자 어휘 사전 (2026-08-22) ──────────────────────────
# 최종 HTML의 텍스트 노드에만 적용한다(태그 속성·<script> 제외). 순서가 중요 — 긴 구절을 먼저.
GLOSSARY = [
    ("EXECUTIVE SUMMARY", "핵심 요약 (EXECUTIVE SUMMARY)"), ("APPENDIX A · 데이터 · 방법 · 게이트", "부록 A · 데이터 · 방법 · 품질 점검"),
    ("Feature Association", "기능 연관 구조"), ("Context × 브랜드 겹침 매트릭스", "상황별 브랜드 점유 비교"), ("Context×브랜드 매트릭스", "상황별 브랜드 점유 비교"), ("Context×브랜드", "상황별 브랜드 점유"),
    ("Nano Intent", "세부 의도"), ("Constraint", "제약"), ("Avoidance", "회피 요인"), ("Opportunity Backlog", "실행 과제"),
    ("상황형 진입", "상황 기반 진입"), ("상황형", "상황 기반"), ("전이형 진입", "브랜드 경유 진입"), ("전이형", "브랜드 경유형"),
    ("스위칭 방향성", "브랜드 전환 흐름"), ("스위칭", "브랜드 전환"), ("이탈 트리거", "전환 직전 검색어(이탈)"), ("유입 트리거", "전환 직전 검색어(유입)"),
    ("허브 레지스트리", "진입점 목록"), ("가설 허브", "가설 기반 진입점"), ("상속 허브", "상위 품목 분석에서 가져온 진입점"), ("패밀리 허브", "사전 기반 진입점"), ("회색 허브", "근거 보강 필요 진입점"), ("허브", "진입점"),
    ("패밀리", "상황군"), ("7W 슬롯", "7가지 상황 요소(7W)"), ("슬롯 커버리지", "상황 요소 충족"), ("빈 슬롯", "빈 요소"), ("슬롯", "상황 요소"),
    ("결합쿼리", "상황+품목 검색어"), ("결합형", "조합 검색어"), ("브리지", "연결 검색어"), ("헤드텀", "대표 검색어"), ("롱테일 코퍼스", "세부 검색어 집합"), ("롱테일", "세부 검색어"), ("코퍼스 봉인", "수집 검색어 범위 내 매칭"), ("코퍼스", "수집 검색어"),
    ("언어층(0볼륨)", "표현 근거(검색량 미보고)"), ("언어층", "표현 근거"), ("렉심", "핵심 어휘"), ("자카드", "중복도"), ("포함도", "부분 중복도"),
    ("co_path", "동반 경로"), ("캔버싱", "전수 조회"), ("캔버스", "전수 조회"), ("AI Overview", "AI 검색 요약"), ("AIO", "AI 검색 요약"), ("PAA", "연관 질문"),
    ("블라인드 작성", "데이터 미열람 작성"), ("블라인드", "데이터 미열람"), ("post-hoc 태깅", "사후 연결"), ("post-hoc", "사후"), ("리플레이", "재계산"),
    ("match=strict", "일치 기준=엄격"), ("match=loose", "일치 기준=느슨"), ("strict 매칭", "엄격 일치"), ("strict", "엄격 일치"),
    ("HUB_FLOOR", "최소 규모 기준(500)"), ("BRIDGE_FLOOR", "최소 검색량 기준(100)"), ("YoY", "전년 대비"), ("분면", "영역"),
    ("supported/strong", "근거 충분"), ("supported/weak", "근거 약함"), ("unsupported/none", "기각"), ("demoted(요건 미달)", "재분류(요건 미달)"),
    ("· strong", "· 근거 충분"), ("· weak", "· 근거 약함"), ("unsupported", "기각"), ("supported", "근거 있음"), ("candidate", "후보"), ("confirmed로", "확정으로"), ("confirmed", "확정"), ("deferred", "보류"),  # 치환 순서 주의: 부분 문자열(supported⊂unsupported)·조사 결합(confirmed로)은 긴 패턴 먼저 (2026-08-29 정오)
    ("MEASURED", "실측"), ("DERIVED", "산출"), ("EXTRACTED", "발췌"),
    ("서사 시드", "서사 기준 검색어"), ("공간 시드", "공간 기준 검색어"), ("시드 역할", "기준 검색어 역할"), ("시드당", "기준 검색어당"), ("시드로", "기준 검색어로"), ("시드 목록", "기준 검색어 목록"), ("시드 재수확", "기준 검색어 재수확"), ("시드", "기준 검색어"),
    ("기능 앵커", "기능 기준 축"), ("제품 앵커", "제품 기준 축"), ("품목 앵커", "품목 기준 축"), ("상황 앵커", "상황 기준 축"), ("앵커 레벨", "기준 축 레벨"), ("앵커 위치", "기준 검색어 위치"), ("앵커가", "기준 검색어가"), ("앵커 앞", "기준 검색어 앞"), ("앵커 뒤", "기준 검색어 뒤"), ("앵커", "기준 축"),
    ("off_feature", "기능 외 수요"), ("vt=0", "검색량 0 포함"),
    ("path_finder", "검색 여정 데이터"), ("keyword_info", "검색량 데이터"), ("intent_finder", "연관 검색어 데이터"), ("cluster_finder", "검색 관계망 데이터"), ("serp", "검색결과 화면"),
    ("KBF 층", "구매 결정 요인 층"), ("KBF로 강등", "구매 결정 요인으로 재분류"), ("KBF로", "구매 결정 요인으로"), ("KBF 이관", "구매 결정 요인 이관"), ("KBF(근거 키워드 병기 의무)", "구매 결정 요인(근거 검색어 병기)"),
    ("RTB 원천", "신뢰 근거 원천"), ("RTB 공백", "신뢰 근거 공백"), ("RTB 전달", "신뢰 근거 전달"),
    ("키워드", "검색어"),
    # 치환 후 조사 보정
    ("진입점는", "진입점은"), ("진입점를", "진입점을"), ("진입점로", "진입점으로"), ("진입점가 ", "진입점이 "), ("진입점와", "진입점과"),
    ("상황군는", "상황군은"), ("상황군를", "상황군을"), ("상황군로", "상황군으로"), ("상황군가 ", "상황군이 "), ("상황군와", "상황군과"),
    ("검색어은", "검색어는"), ("검색어을", "검색어를"), ("검색어으로", "검색어로"), ("검색어이 ", "검색어가 "),
    ("요소은", "요소는"), ("요소을", "요소를"), ("요소으로", "요소로"), ("요소이 ", "요소가 "),
    ("기준 축는", "기준 축은"), ("기준 축를", "기준 축을"), ("기준 축로", "기준 축으로"), ("기준 축가 ", "기준 축이 "), ("기준 축와", "기준 축과"), ("기준 축라", "기준 축이라"), ("기준 축다", "기준 축이다"),
]


def friendly(html: str) -> str:
    """태그·script 밖 텍스트에만 용어 사전 적용."""
    parts = re.split(r"(<script.*?</script>|<[^>]+>)", html, flags=re.S)
    out = []
    for seg in parts:
        if seg.startswith("<"):
            out.append(seg); continue
        for a, b in GLOSSARY:
            seg = seg.replace(a, b)
        out.append(seg)
    res = "".join(out)
    # 받침 유무가 바뀐 치환어와 조사 사이에 닫는 태그가 끼는 경우의 후처리 (2026-08-30)
    res = re.sub(r"(요소|검색어)(</b>|</span>)으로", r"\1\2로", res)
    res = re.sub(r"(기준 축|진입점|상황군)(</b>|</span>)로", r"\1\2으로", res)
    res = re.sub(r"(요소|검색어)(</b>|</span>)은", r"\1\2는", res)
    res = re.sub(r"(요소|검색어)(</b>|</span>)을", r"\1\2를", res)
    res = re.sub(r"(기준 축|진입점|상황군)(</b>|</span>)([를는])", lambda m: m.group(1)+m.group(2)+{"를":"을","는":"은"}[m.group(3)], res)
    return res


# ────────────────────────── 조립 ──────────────────────────
def build(run: Path, labels: dict, brand_map_path: Path | None) -> tuple[str, list]:
    D = load_run(run); HG, MF = D["hub_graph"], D["manifest"]
    category = HG.get("category") or MF.get("run_id", "").split("-")[0]; gl = HG.get("gl", "kr")
    vertical = (MF.get("adapter") or {}).get("vertical", "listeningmind-universal")
    brand_rx = load_brand_map(vertical, brand_map_path)
    tags = labels.get("tag_lexicon") or DEFAULT_TAGS
    warn = []
    NA = lambda k: f"[labels.json 미작성: {k}]"

    # 헤드텀 시계열
    head_item = ((D["head"].get("data") or [{}])[0]) if D["head"] else (D["kwinfo"].get(category) or {})
    months, vals = monthly_series(head_item)
    head_avg = (head_item.get("ads_metrics") or {}).get("volume_avg")
    h_yoy = yoy(vals); anom = anomalies(months, vals)
    vals_adj = list(vals)
    for am, av, az in anom:
        i = months.index(am); nb = [vals[j] for j in (i - 1, i + 1) if 0 <= j < len(vals)]
        vals_adj[i] = statistics.median(nb) if nb else av
    h_yoy_adj = yoy(vals_adj)
    nv = [m.get("nv", 0) for m in sorted(head_item.get("monthly_volume") or [], key=lambda m: m["month"])]
    h_yoy_nv = yoy(nv) if any(nv) else None
    h_season = season_idx(months, vals)

    # 캔버스 · 브리지
    bridges = HG.get("bridges") or []; bvol = {b["combo"]: b.get("v") for b in bridges}
    fams = collections.OrderedDict()
    for b in bridges:
        fams.setdefault(b["family"], []).append(b)
    facets = set(labels.get("facets") or []) | {b["combo"] for b in bridges if b.get("segment_facet")}
    sparse = {s["family"]: s for s in HG.get("sparse_families") or []}
    engine_hubs = {h["family"]: h for h in HG.get("hubs") or [] if h.get("family")}   # 가설 허브(S5)는 family 없음 — 가설 블록에서 표시
    thr = MF.get("thresholds") or {}
    fam_text = labels.get("canvas_families") or {}
    cards = []
    for fam, bs in fams.items():
        qualified = [b for b in bs if b.get("qualified") and b["combo"] not in facets]
        tot = sum(b["v"] or 0 for b in qualified)
        facet_in = [b for b in bs if b["combo"] in facets]
        if fam in engine_hubs and fam not in sparse and tot >= (thr.get("hub_floor") or 500) and not (facet_in and tot - sum(b["v"] or 0 for b in facet_in) < (thr.get("hub_floor") or 500)):
            cls, val = "", f"{tot:,}"
        elif facet_in:
            cls, val = "facet", f"{tot:,}"
        else:
            cls, val = "sparse", f"{max((b['v'] or 0) for b in bs):,}"
        desc = fam_text.get(fam) or f"{len(qualified)}/{len(bs)} 결합형 성립" + (f" · 패싯 분리: {', '.join(b['combo'] for b in facet_in)}" if facet_in else "")
        cards.append(({"": 0, "facet": 1, "sparse": 2}[cls], f'<div class="fam {cls}"><div class="fn">{fam.upper() if fam.isascii() else fam}</div><div class="fv">{val}</div><div class="fd">{desc}</div></div>'))
    for g, o in (HG.get("alias_groups") or {}).items():          # B2 — 별칭군 카드
        al = " · ".join(f'{r["alias"]} {r["v"] or "[없음]"}' + (f'({r["yoy"] * 100:+.0f}%)' if r.get("yoy") is not None else "") for r in o["aliases"])
        ev = " · ".join(f'{k.split(" ", 1)[-1]} {v or "[없음]"}' for k, v in (o.get("eval") or {}).items())
        cards.append((0, f'<div class="fam facet"><div class="fn">별칭군 · {g}</div><div class="fv">{o["volume_sum"]:,}</div><div class="fd">{al}<br>평가형: {ev}<br><span class="veil">동의어 중복 가능 — 합계는 상한 · 상황 허브 아님(라인·기능)</span></div></div>'))
    season_amp = amplitude(h_season)
    if "season" not in fams and h_season:
        cards.append((2, f'<div class="fam sparse"><div class="fn">SEASON · 시즌</div><div class="fv">{season_amp}</div><div class="fd">{fam_text.get("season") or f"헤드텀 진폭 {season_amp} (임계 {thr.get("season_amp", 2.0)})"}</div></div>'))

    # 허브 (labels.hubs 우선, 없으면 엔진 패밀리 허브 그대로)
    product_mode = HG.get("anchor_level") in ("product", "feature")
    hub_specs = labels.get("hubs") or [
        {"id": h["id"], "label": h["family"], "status": "candidate", "status_text": "candidate · 승인 대기",
         "bridges": [b["combo"] for b in h.get("bridges", []) if b["combo"] not in facets]} for h in HG.get("hubs") or [] if h.get("bridges") and h.get("source") != "hypothesis-first(S5)"]
    if product_mode and not labels.get("hubs"):
        for ih in HG.get("inherited_hubs") or []:
            hub_specs.append({"id": f'{ih["id"]} (상속)', "label": f'{ih["label"]} → {ih["verdict"]}', "short": ih["label"], "status": "grey",
                              "status_text": f'품목 run {ih.get("status", "")} · 제품 연결 {ih["verdict"]}', "bridges": [], "inherited": True,
                              "volume": ih.get("volume_sum"), "source": ih.get("source"),
                              "own_bridges": " · ".join(f"{l} × 제품명" for l in ih.get("lexemes", [])[:4]) + " [없음]",
                              "stats_extra": f'제품 여정 co_path {ih["product_journey_co_path"]}/{ih["product_journey_n"]} · 품목 여정({ih.get("parent_journey_anchor") or "-"}) 제품 별칭 도달 {ih["parent_journey_product_reach"] if ih.get("parent_journey_product_reach") is not None else "미측정"}/{ih.get("parent_journey_n") or "-"} · 자사 타라인 {ih.get("parent_journey_own_line_reach") if ih.get("parent_journey_own_line_reach") is not None else "-"}',
                              "narrative": "[labels.json 미작성: narrative]", "slots": {}})
    hubs = []
    for i, hs in enumerate(hub_specs):
        if hs.get("inherited"):          # 타 run(품목 레벨) 허브 상속 — 수치는 labels가 준다(출처 명기)
            hubs.append({"spec": hs, "rows": [], "sum": hs.get("volume") or 0, "yoy": hs.get("yoy"), "season": {},
                         "comp": None, "aio": None, "f": None, "ages": None, "intents": None, "journey": None, "inherited": True})
            continue
        combos = [c for c in hs.get("bridges", []) if c in bvol]
        rows = []; series_sum = None; mon = None; kw_items = []
        for c in combos:
            it = D["kwinfo"].get(c); y = None
            if it:
                mo, vv = monthly_series(it); y = yoy(vv); kw_items.append(it)
                if vv:
                    if series_sum is None: series_sum, mon = list(vv), mo
                    elif len(vv) == len(series_sum): series_sum = [a + b for a, b in zip(series_sum, vv)]
            rows.append((c, bvol[c] or 0, y))
        rows.sort(key=lambda r: -r[1]); tot = sum(r[1] for r in rows)
        h = {"spec": hs, "rows": rows, "sum": tot, "yoy": yoy(series_sum) if series_sum else None,
             "season": season_idx(mon, series_sum) if series_sum else {}, "comp": None, "aio": None, "f": None, "ages": None, "intents": None}
        if kw_items and tot:
            w = lambda f: sum((it["ads_metrics"]["volume_avg"] or 0) * f(it) for it in kw_items) / tot
            h["comp"] = round(w(lambda it: it["ads_metrics"].get("competition_index") or 0))
            h["aio"] = f'{sum(1 for it in kw_items if (it.get("features") or {}).get("f_ai_overview"))}/{len(kw_items)}'
            if all(it.get("demography") for it in kw_items):
                h["f"] = round(w(lambda it: it["demography"].get("f_gender_ratio") or 0), 1)
                h["ages"] = {k: round(w(lambda it, k=k: it["demography"].get(k + "_ratio") or 0), 1) for _, k, _ in AGE_KEYS}
            h["intents"] = " · ".join(f'{it["keyword"]} {"/".join(k.upper() for k in "inct" if (it.get("intents") or {}).get(k))}' for it in kw_items)
        # 여정
        anchor = hs.get("journey_anchor") or next((a for a in D["paths"] if a in combos), None)
        h["journey"] = journey_stats(anchor, D["paths"][anchor], brand_rx, tags) if anchor and anchor in D["paths"] else None
        hubs.append(h)

    # 허브 카드 HTML
    inh_verdict = {ih["id"]: ih.get("verdict", "") for ih in HG.get("inherited_hubs") or []}
    mode = labels.get("inherited_cards", "linked_only")
    collapsed = []
    if mode == "linked_only":
        keep = []
        for h in hubs:
            if h.get("inherited"):
                base = h["spec"].get("id", "").split(" ")[0]
                v = inh_verdict.get(base, "")
                if not v.startswith("연결 단서"):
                    collapsed.append((h["spec"].get("id", ""), h["spec"].get("label", ""), v or "미측정", h["sum"])); continue
            keep.append(h)
        hubs_for_cards = keep
    else:
        hubs_for_cards = hubs
    hub_html = []
    if collapsed:
        hub_html.append('<div class="sl">상위 품목 분석의 진입점 — 이 제품과의 연결 근거 없음(상세 생략 · 01 목록 참조)</div><ul class="note" style="padding-left:18px;margin-top:4px">'
                        + "".join(f"<li><b>{i}</b> {esc(l)} — {esc(v)} · 상위 규모 {n:,}</li>" for i, l, v, n in collapsed) + "</ul>")
    if not hubs:
        hub_html.append(f'<p class="note">{esc(labels.get("hubs_note") or "상황형 허브 0 — 캔버스 완주 후의 측정값(부재 ≠ 반증)")}</p>')
    for h in hubs_for_cards:
        hs = h["spec"]; st = hs.get("status", "candidate"); grey = st == "grey" or (h["journey"] is None and st != "confirmed")
        stcls = "st-c" if st == "confirmed" else "st-r"
        badge = '<span class="badge b-derived">근거 보강 필요</span>' if grey else '<span class="badge b-measured">MEASURED</span>'
        slots = hs.get("slots") or {}
        cov = sum(1 for w in W_NAMES if (slots.get(w) or {}).get("grade") in ("measured", "derived", "assumption"))
        demo = ""
        if h["ages"]:
            demo = (f'<div class="sl">상황 검색어 기준 검색자 성·연령 ({"국내" if gl == "kr" else gl}) <span class="badge b-measured">MEASURED</span></div>'
                    f'<div class="demo">여성 {h["f"]}% · 남성 {100 - h["f"]:.1f}%</div>{agebar(h["ages"])}'
                    f'<p class="note" style="margin-top:8px">{esc(hs.get("demo_note") or "")}</p>')
        else:
            demo = '<div class="sl">성·연령</div><p class="note">미측정 — keyword_info(all) 보강 실측 없음 또는 gl≠kr(데이터 사양)</p>'
        if h.get("inherited"):
            stats = f'<b>상속 허브</b> — 출처 {esc(hs.get("source") or "타 run")} · 허브 규모 {h["sum"]:,}/월 · YoY {pct(h["yoy"])} · 제품 앵커 자체 결합쿼리는 {esc(hs.get("own_bridges") or "[없음]")}'
        else:
            stats = (f'허브 규모 <b>{h["sum"]:,}/월</b>(결합쿼리 합, 48개월 평균) · YoY <b>{pct(h["yoy"])}</b>'
                 + (f' · 인텐트: {h["intents"]}' if h["intents"] else "") + (f' · AI Overview 노출 {h["aio"]}' if h["aio"] else "")
                 + (f' · 경쟁도 {h["comp"]}(가중)' if h["comp"] is not None else "") + (f' · {esc(hs["stats_extra"])}' if hs.get("stats_extra") else ""))
        bars = bar_rows(h["rows"]) if h["rows"] else f'<p class="note">{esc(hs.get("bridges_note") or "결합쿼리 없음")}</p>'
        jn = h["journey"]
        jline = (f'여정 {jn["n"]}경로 · 브랜드 도달 {pct(jn["reach"], 0)}' if jn else "여정 미실측")
        hub_html.append(f'''<div class="hub{" grey" if grey else ""}">
  <div class="hhead"><span class="hid">{hs.get("id", "")}</span><h3>{esc(hs.get("label", ""))}</h3><span class="st {stcls}">{esc(hs.get("status_text", st))}</span>{badge}</div>
  <p class="narr">{esc(hs.get("narrative") or NA("narrative"))} <span class="veil">{esc(hs.get("narrative_note") or "서사는 결합쿼리 문자열만으로 조립(코퍼스 봉인) · 라벨은 가정 등급")}</span></p>
  <div class="hgrid"><div>{bars}<p class="note">{stats}</p></div><div>{demo}</div></div>
  <div class="slots">{"".join(slot_html(w, slots.get(w)) for w in W_NAMES)}</div>
  <p class="note">슬롯 커버리지 <b>{cov}/7</b> · {jline} · {esc(hs.get("coverage_note") or "")}</p>
</div>''')
        if not slots: warn.append(f'허브 {hs.get("id")} 슬롯 미작성')

    # KPI
    situ_sum = sum(h["sum"] for h in hubs if not h.get("inherited"))
    n_conf = sum(1 for h in hubs if h["spec"].get("status") == "confirmed")
    max_hub_amp = max((amplitude(h["season"]) or 0) for h in hubs) if hubs else None
    kpis = labels.get("kpis") or [
        {"label": f'헤드텀 "{category}" 월평균', "value": f"{head_avg:,}" if head_avg else "—", "desc": f"{len(months)}개월 평균 (측정)"},
        {"label": "상황형 진입 합계", "value": f"{situ_sum:,}", "desc": f"허브 {len(hubs)}종 결합쿼리 합 · 헤드텀 대비 {situ_sum / head_avg * 100:.1f}% (분모: 헤드텀 단독 · 파생)" if head_avg else "허브 결합쿼리 합 (파생)"},
        {"label": "확인된 진입점 수", "value": f'{len(hubs)} <small>/ 희박 {len(sparse)} · 패싯 {len(facets)}</small>', "desc": f"confirmed {n_conf} · 후보 {len(hubs) - n_conf} (측정)"},
        {"label": "성수기·비수기 검색량 배율 (대표 검색어 vs 가장 큰 진입점)", "value": f'{season_amp or "—"} <small>vs</small> {max_hub_amp or "—"}', "desc": "월 중앙값 지수 최대/최소 (파생)"}]
    kpi_html = "".join(f'<div class="kpi"><div class="l">{k["label"]}</div><div class="v">{k["value"]}</div><div class="d">{k["desc"]}</div></div>' for k in kpis)

    # 차트
    tsvg, m24, v24 = trend_svg(months, vals, anom) if vals else ("<p class='note'>헤드텀 시계열 없음</p>", [], [])
    ssvg = season_svg([(f'헤드텀 "{category}"', h_season, "")] + [(h["spec"].get("label", ""), h["season"], "") for h in sorted(hubs, key=lambda h: -(amplitude(h["season"]) or 0))[:2]], h_season)
    trend_note = labels.get("trend_note") or (f"읽기 — YoY(최신 미완월 제외) <b>{pct(h_yoy)}</b>" + (f" · 이상치 보정 <b>{pct(h_yoy_adj)}</b> ({', '.join(f'{a[0]} z={a[2]}' for a in anom)})" if anom else "") + (f" · 네이버 단독 {pct(h_yoy_nv)}" if h_yoy_nv is not None else "") + ". 검색량 기준이며 판매량이 아님.")
    season_note = labels.get("season_note") or f"DERIVED — 헤드텀 진폭 {season_amp} · 허브별 진폭은 범례 참조. 시즌과 검색 상승의 인과는 단정하지 않음."

    # 결정구조
    dec = labels.get("decision") or {}
    def ul(items): return "".join(f"<li>{esc(x)}</li>" for x in items) if items else f"<li>{NA('decision')}</li>"
    dec_default_cep = [f'<b>{h["spec"].get("label")}</b> {h["sum"]:,}' for h in hubs] + [f'희박(측정): {", ".join(f"{k} {v["max_v"]}" for k, v in sparse.items())}' if sparse else ""]
    dcards = [("진입 상황", "CEP", dec.get("CEP") or [x for x in dec_default_cep if x]), ("세부 의도", "— 원하는 해결 방식", dec.get("NI")),
              ("구매 결정 요인", "KBF", dec.get("KBF")), ("제약 요인", "", dec.get("CST")), ("회피 요인", "", dec.get("AVD")), ("신뢰 근거", "RTB", dec.get("RTB"))]
    dec_html = "".join(f'<div class="dcard"><h3>{t} <span>{s}</span></h3><ul>{ul(items)}</ul></div>' for t, s, items in dcards)
    if dec.get("HOLD"):
        dec_html += f'<div class="dcard noise"><span class="flag">해석 보류</span><h3>신호가 약하거나 다른 품목이 섞인 검색어</h3><ul>{ul(dec["HOLD"])}</ul></div>'

    # 여정 블록
    jblocks = []; all_j = {}
    for a, paths in D["paths"].items():
        all_j[a] = journey_stats(a, paths, brand_rx, tags)
    jl = {j["anchor"]: j for j in labels.get("journeys") or []}
    for a, js in all_j.items():
        spec = jl.get(a, {})
        if spec.get("stages"):
            stages = "".join(f'<div class="stage"><div class="n">{s["n"]}</div><div class="t">{esc(s["t"])}</div><div class="q">{esc(s["q"])}</div></div>' for s in spec["stages"])
        else:
            fmt = lambda lst: " · ".join(f"<code>{k}</code> {v}" for k, v in lst[:5]) or "—"
            stages = (f'<div class="stage"><div class="n">PREV</div><div class="t">앞서 검색한 검색어</div><div class="q">{fmt(js["prev"])}</div></div>'
                      f'<div class="stage"><div class="n">NEXT</div><div class="t">이어서 검색한 검색어</div><div class="q">{fmt(js["next"])}</div></div>'
                      f'<div class="stage"><div class="n">TAGS</div><div class="t">검색어 주제 분류</div><div class="q">{fmt(js["tags"])}</div></div>'
                      f'<div class="stage"><div class="n">END</div><div class="t">여정 마지막 검색어</div><div class="q">{fmt(js["end"])}</div></div>')
        title = spec.get("title") or f'"{a}" — {js["n"]}경로 · 고유 키워드 {js["uniq"]}'
        note = spec.get("note") or f'브랜드 도달 {js["brand_paths"]}/{js["n"]}({pct(js["reach"], 0)}) — ' + ", ".join(f"{b} {c}" for b, c in js["brands"][:4])
        jblocks.append(f'<div class="sl" style="margin-top:18px">{esc(title)}</div><div class="flow">{stages}</div><p class="note">{esc(note)}</p>')
    if not jblocks: jblocks.append("<p class='note'>여정 미실측 — raw/paths_*.json 없음</p>")

    # 매트릭스
    agg = collections.Counter()
    for js in all_j.values():
        for b, c in js["brands"]: agg[b] += c
    top2 = [b for b, _ in agg.most_common(2)] or ["—", "—"]
    while len(top2) < 2: top2.append("—")
    mx = [f'<div class="mh"></div><div class="mh">{top2[0]}</div><div class="mh">{top2[1]}</div><div class="mh">기타 브랜드</div><div class="mh">무브랜드 경로</div>']
    hub_by_anchor = {h["journey"]["anchor"]: h for h in hubs if h["journey"]}
    for a, js in all_j.items():
        bd = dict(js["brands"]); others = ", ".join(f"{b} {c}" for b, c in js["brands"] if b not in top2) or "—"
        lab = (hub_by_anchor[a]["spec"].get("label") if a in hub_by_anchor else ("패싯 · " if a in facets else "")) or ""
        gen = js["n"] - js["brand_paths"]
        mx.append(f'<div class="mr">{lab} {a} ({js["n"]})</div><div class="c1">{bd.get(top2[0], 0)}</div><div class="c1">{bd.get(top2[1], 0)}</div><div class="c0">{others}</div><div class="c0">{gen} ({gen / js["n"] * 100:.0f}%)</div>')
    tr = HG.get("transition") or {}
    if product_mode and tr.get("measured"):
        comp = " · ".join(f"{b} {c}" for b, c in tr.get("competitor_cooccurrence") or []) or "없음"
        own = " · ".join(f"{b} {c}" for b, c in tr.get("own_line_branch") or []) or "없음"
        mx.append(f'<div class="mr">전이형 · {category} ({tr["n"]})</div><div class="c1" style="grid-column:span 2">경쟁 동반: {comp}</div><div class="c1">자사 라인 분기: {own}</div><div class="c0">상황 렉심 도달 {tr.get("situation_reach")}</div>')
    for h in hubs:
        if not h["journey"] and not h.get("inherited"):
            mx.append(f'<div class="mr">{h["spec"].get("label")}</div><div class="c0">미측정</div><div class="c0">미측정</div><div class="c0">미측정</div><div class="c0">여정 미실측</div>')

    # 4분면
    sizes = sorted(h["sum"] for h in hubs) or [1]
    pts = [{"label": h["spec"].get("short") or h["spec"].get("label", ""), "x": h["yoy"], "y": h["journey"]["reach"] if h["journey"] else None,
            "grey": h["journey"] is None or h["spec"].get("status") == "grey",
            "size_rank": sizes.index(h["sum"]) / max(len(sizes) - 1, 1),
            "sub": f'{h["sum"]:,} · 도달 {pct(h["journey"]["reach"], 0) if h["journey"] else "미측정"} · 경쟁 {h["comp"] if h["comp"] is not None else "—"}'} for h in hubs]
    qsvg = quadrant_svg(pts, labels.get("quadrant_legend"))  # 상속 배치 run은 labels로 범례를 정밀화(2026-08-30)

    # 백로그
    bl = labels.get("backlog") or {}
    rows = []
    for key, title, cls in (("now", "지금 대응할 변화", "g-now"), ("watch", "계속 지켜볼 변화", "g-watch"), ("risk", "위험 신호", "g-risk")):
        items = bl.get(key) or []
        if not items: continue
        rows.append(f'<tr class="group {cls}"><td colspan="3">{title}</td></tr>')
        for r in items:
            sc = f'<span class="sc sc-{r["scale"].lower()}">{r["scale"].upper()}</span>' if r.get("scale") else ""
            veil = f'<span class="veil">{esc(r["veil"])}</span>' if r.get("veil") else ""
            rows.append(f'<tr><td>{esc(r["title"])}</td><td>{sc}{esc(r["evidence"])}</td><td>{esc(r["action"])}{veil}</td></tr>')
    if not rows: rows.append(f'<tr><td colspan="3">{NA("backlog")}</td></tr>')

    # 크레딧·게이트
    calls = list((MF.get("credits") or {}).get("calls") or []); topup_calls = list((D["topup"] or {}).get("calls") or [])
    spent = (MF.get("credits") or {}).get("spent", 0); tspent = (D["topup"] or {}).get("spent", 0)
    def cl(calls): return " · ".join(f'{c["tool"]} {c["cost"]:,}' + (f'({c["params"].get("kw")})' if c.get("params", {}).get("kw") else f'(n={c["params"].get("n")})' if c.get("params", {}).get("n") else "") for c in calls)
    credits = (f'ListeningMind DaaS keyword_info · path_finder, gl={gl}, 조회 {MF.get("run_id", "")[-13:]}. 엔진 run {spent:,} = {cl(calls)}'
               + (f' / 보강 실측 {tspent:,} = {cl(topup_calls)}' if topup_calls else "")
               + f'. <b>이번 분석 소진 합계 {spent + tspent:,}크레딧</b>' + (f'(예산 {MF["credits"]["budget"]:,})' if (MF.get("credits") or {}).get("budget") else "")
               + (f' · 월간 누적 {labels["used_credits"]:,}(당월 누적 사용량이며 잔여량 아님).' if labels.get("used_credits") else "."))
    gates = " · ".join(f'[{g["gate"]} {g["verdict"]}] {g["name"]} — {g["detail"]}' for g in MF.get("gates") or []) or "기록 없음"
    if facets: gates += f" · 패싯 분리 {len(facets)}건({', '.join(sorted(facets))})"
    if any(h["journey"] is None for h in hubs): gates += " · 여정 미실측 허브 회색 표기"
    for w in MF.get("warnings") or []: gates += f" · ⚠ {w}"
    gates += "."

    data = {
        "TITLE": labels.get("title") or f"{category} 카테고리 진입점(CEP) 결정 리포트",
        "VERTICAL_LABEL": labels.get("vertical_label") or vertical.replace("listeningmind-", "").upper(),
        "DATA_RANGE": f"{months[0]} ~ {months[-1]} ({len(months)}개월)" if months else "—", "QUERY_DATE": labels.get("query_date") or MF.get("run_id", "")[-13:-5],
        "GL": gl, "CATEGORY": category,
        "CONNECTORS_LINE": labels.get("connectors_line") or (f'keyword_info(캔버스 {len(bridges)}) · path_finder(' + " · ".join(f"{a} {len(p)}" for a, p in D["paths"].items()) + f' = {sum(len(p) for p in D["paths"].values())}경로)'),
        "OWNER": labels.get("owner") or NA("owner"), "RUN_ID": MF.get("run_id", "—"), "ENGINE": MF.get("engine", "—"), "SPEC": MF.get("spec", "—"),
        "ADAPTER": f'{vertical} v{(MF.get("adapter") or {}).get("version", "?")}',
        "LEDE": labels.get("lede") or NA("lede"),
        "READINESS_STATUS": (labels.get("readiness") or {}).get("status") or "READY WITH LIMITS",
        "READINESS_ITEMS": " ".join(f"{'①②③④⑤⑥⑦⑧⑨'[i] if i < 9 else i + 1} {x}" for i, x in enumerate((labels.get("readiness") or {}).get("items") or [NA("readiness")])) + ".",
        "KPI_CARDS": kpi_html, "CANVASS_N": len(bridges), "BRIDGE_FLOOR": thr.get("bridge_floor", 100), "HUB_FLOOR": thr.get("hub_floor", 500),
        "CANVAS_CARDS": "".join(c for _, c in sorted(cards, key=lambda x: x[0])), "CANVAS_NOTE": labels.get("canvas_note") or NA("canvas_note"),
        "MONTHS_N": len(months), "TREND_SVG": tsvg, "TREND_NOTE": trend_note, "SEASON_SVG": ssvg, "SEASON_NOTE": season_note,
        "HUB_HINT_EXTRA": f' + 보강 실측(keyword_info all {len(D["kwinfo"])})' if D["kwinfo"] else "", "HUB_CARDS": "".join(hub_html),
        "PATHS_N": sum(len(p) for p in D["paths"].values()), "DECISION_SUB": labels.get("decision_sub") or "근거: 여정 노드 태그 집계 + 결합쿼리 언어 · 검색 언어 기반 해석",
        "DECISION_CARDS": dec_html,
        "JOURNEY_HINT": " · ".join(f"{a} {len(p)}경로" for a, p in D["paths"].items()) or "미실측",
        "JOURNEY_SUB": labels.get("journey_sub") or ("앵커가 경로 시작점인 비율: " + " · ".join(f'{a} {j["start"]}/{j["n"]}' for a, j in all_j.items())),
        "JOURNEY_BLOCKS": "".join(jblocks), "MATRIX_CELLS": "".join(mx), "MATRIX_NOTE": labels.get("matrix_note") or "DERIVED — 브랜드 점유는 검색 경로 기준 근사이며 판매 점유율·시장 점유율이 아님.",
        "QUADRANT_SUB": labels.get("quadrant_sub") or f"허브가 {len(hubs)}개라 Opportunity Score의 순위 백분위는 거칠다 — 점수 대신 <b>분면·근거 품질·drivers</b>로 tier를 매긴다.",
        "QUADRANT_SVG": qsvg, "BACKLOG_ROWS": "".join(rows),
        "CREDITS_LINE": credits, "GATES_LINE": gates, "DATA_FILES_EXTRA": labels.get("data_files_extra") or "",
        "GAPS_LINE": labels.get("gaps_line") or "W6·W7 슬롯 · 전이형(헤드텀 여정) 미측정.",
        "GUARDRAILS_LINE": labels.get("guardrails_line") or GUARDRAILS_DEFAULT,
        "COMPETITION_EXTRA": competition_extra(HG, labels),
        "HYPOTHESIS_CARDS_MAIN": hypothesis_block(HG, labels, only_candidates=True),
        "HYPOTHESIS_TABLE": hypothesis_table(HG, labels),
        "REGISTRY_TABLE": registry_table(HG, labels, hubs),
        "REGISTRY_NOTE": labels.get("registry_note") or "DERIVED — 규모는 결합쿼리·매칭 키워드 월볼륨 합(언어층 0 제외, 동의어 미합산), 상태는 승인 세션 판정. 최근접 자카드는 렉심 집합 기준(부록 A2).",
        "EXEC_HEADLINE": labels.get("exec_headline") or f"{category}: 상황형 진입점 {len([h for h in hubs if not h.get('inherited')]) + len((HG.get('hypotheses') or {}).get('hypothesis_hubs') or [])}개가 수요의 입구를 설명한다",
        "KEY_MESSAGES": key_messages_block(labels, [
            {"headline": f"헤드텀 {category} 월평균 {head_avg:,} · 상황형 결합쿼리 합 {situ_sum:,}({(situ_sum / head_avg * 100) if head_avg else 0:.1f}%)", "evidence": "캔버스 전수 실측", "implication": "상황은 품목 헤드텀의 일부만 설명 — 나머지는 브랜드·스펙 직접 진입"},
            {"headline": f"허브 {len(hubs)}개 · 가설 후보 {(HG.get('hypotheses') or {}).get('candidates', 0)}개", "evidence": "labels.key_messages 미작성 — 자동 요약", "implication": ""}]),
        "RECOMMENDATIONS": ("<ol>" + "".join(f"<li>{esc(x)}</li>" for x in labels.get("recommendations") or []) + "</ol>") if labels.get("recommendations") else '<span class="veil">labels.recommendations 미작성</span>',
        "GATES_LIST": "".join(f'<li>[{g["gate"]} {g["verdict"]}] {esc(g["name"])} — {esc(g["detail"])}</li>' for g in MF.get("gates") or []) + "".join(f'<li>⚠ {esc(w)}</li>' for w in MF.get("warnings") or []),
        "FEATURE_BLOCK": feature_block(HG, labels),
        "PROVENANCE_BLOCK": provenance_block(HG, labels),
        "CREDIT_LEDGER_BLOCK": credit_ledger_block(run),
        "EVIDENCE_BLOCK": evidence_block(HG, labels),
        "HYPOTHESIS_BLOCK": hypothesis_block(HG, labels),
        "MERGE_BLOCK": merge_block(HG, labels),
        "EXTRA_SECTIONS": "".join(
            f'<div class="card"><div class="shead"><span class="no">{sec.get("no", f"{8 + i:02d}")}</span><h2>{esc(sec["title"])}</h2>'
            f'<span class="badge {"b-measured" if sec.get("grade") == "measured" else "b-derived"}">{"MEASURED" if sec.get("grade") == "measured" else "DERIVED"}</span>'
            f'<span class="hint">{esc(sec.get("hint", ""))}</span></div>{sec["html"]}</div>' for i, sec in enumerate(labels.get("extra_sections") or [])),
        "MONTHS_JSON": json.dumps(m24), "VALS_JSON": json.dumps(v24),
        **{f"T_{k.upper()}": (labels.get("section_titles") or {}).get(k) or d for k, d in {
            "registry": f"상황형 진입은 {len(hubs)}개 패밀리/상속 허브 + 가설 후보 {(HG.get('hypotheses') or {}).get('candidates', 0)}개로 정리된다 — 중복 여부는 자카드로 판정",
            "demand": f"헤드텀 YoY {pct(h_yoy)}(이상치 보정 {pct(h_yoy_adj)}) · 시즌 진폭 {season_amp} — 시즌은 독립 진입점이 아니라 허브의 W2 슬롯",
            "hubs": "허브마다 채워진 슬롯과 비어 있는 슬롯이 다르다 — 빈 슬롯은 채우지 않고 다음 측정 대상으로 남긴다",
            "decision": "6층은 허브에 매달린다 — CEP가 다르면 Nano Intent와 KBF 우선순위가 달라진다",
            "journey": "여정은 관문(선행)과 이탈(후행)을 드러낸다 — 세션 인접 집계이며 개인의 경로가 아니다",
            "backlog": "분면 → 근거 품질 → 점수 → 시즌 창 순으로 줄을 세운다 — 회색 허브는 공략 상위에 올리지 않는다"}.items()},
    }
    tpl = TEMPLATE.read_text(encoding="utf8")
    html = re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: str(data.get(m.group(1), m.group(0))), tpl)
    if labels.get("friendly", True):
        html = friendly(html)
    left = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", html)))
    if left: warn.append(f"미치환 자리: {left}")
    if not labels: warn.append("labels.json 없음 — 서사 자리는 [labels.json 미작성]으로 남김")
    return html, warn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir"); ap.add_argument("--labels"); ap.add_argument("--out"); ap.add_argument("--copy-to"); ap.add_argument("--brand-map")
    ap.add_argument("--allow-ungated", action="store_true", help="렌더 전 게이트 미통과여도 초안으로 렌더(미통과 배너 삽입)")
    ap.add_argument("--allow-unverified-numbers", action="store_true", help="라벨 숫자 대조 미통과여도 초안으로 렌더(배너 삽입)")
    ap.add_argument("--check", action="store_true", help="게이트·숫자 대조만 하고 쓰지 않는다")
    ap.add_argument("--allow-jargon", action="store_true", help="어휘 검사 미통과여도 초안으로 렌더")
    ap.add_argument("--allow-unreviewed", action="store_true", help="제목·문장 검토 기록부가 있는 설치에서만 쓰인다(스타터에는 없음)")
    a = ap.parse_args()
    run = Path(a.run_dir).resolve()
    import sys as _sys
    _sys.path.insert(0, str(SKILLS_ROOT / "lima-agents"))
    from lib import gates as _gates
    gate_banner = _gates.require_for_render(run, a.allow_ungated)      # 미통과면 여기서 중단
    lp = Path(a.labels) if a.labels else run / "core/labels.json"
    if not lp.is_absolute(): lp = (run / lp) if (run / lp).exists() else lp.resolve()
    labels = jload(lp, {}) or {}
    # ── 라벨 숫자 대조 — labels.json(LLM 작성)의 숫자가 run 원자료·core 계산값에 있어야 렌더한다
    from lib import prose_check as _pc
    _nc = labels.get("number_check") or {}
    _texts = _pc.config_texts(labels, set(_nc.get("skip") or []) | {"tag_lexicon", "number_check", "vertical_label"})
    _errs = _pc.gate("결정 리포트 라벨", _texts, [], run=[run], number_check=_nc,
                     brands=_pc.brand_names(labels.get("vertical") or "listeningmind-universal"), ws=SKILLS_ROOT.parents[1])
    if _pc.enforce(run, _errs, a.allow_unverified_numbers):         # 게이트 기록이 있는 run만 막는다 — 레거시는 배너
        raise SystemExit(_pc.abort_message(f"결정 리포트 {run.name}", _errs) + "\n  초안이 꼭 필요하면 --allow-unverified-numbers (산출물에 미통과 배너)")
    print(f"숫자 대조 {'미통과 ' + str(len(_errs)) + '건 — 산출물에 배너' if _errs else '통과'} — 라벨 문구 {len(_texts)}건")
    if a.check:
        raise SystemExit(1 if _errs else 0)
    html, warn = build(run, labels, Path(a.brand_map) if a.brand_map else None)
    html = _gates.inject(html, gate_banner + _pc.banner_html(_errs))
    out = Path(a.out) if a.out else run / "out/decision_report.html"
    # ── 어휘·표현 게이트 (references/lexicon-gate.md) — 경고만, 차단 아님
    _GATE = ["완패", "참패", "궤멸", "독주", "장악", "석권", "사실상 소유", "사실상 소멸",
             "압도적", "폭발적", "폭증", "입증됐", "확실시"]
    import re as _re
    _vis = _re.sub(r"<[^>]+>", " ", html)
    _hits = sorted({w for w in _GATE if w in _vis})
    if _hits:
        print(f"⚠ 어휘 게이트: {_hits} — 근거 병기·대체어 확인 (lexicon-gate.md)")
    if _re.search(r"TAM(?!\s*테이블|[^<]{0,40}(시장 금액 아님|검색량 기준))", _vis):
        print("⚠ 어휘 게이트: TAM 무주석 사용 — '검색량 기준·시장 금액 아님' 병기 필요")
    from lib import lexicon_check as _lx            # 어휘 검사 — GLOSSARY 치환 뒤에도 남은 작업 용어는 차단
    html = _lx.finalize_html(f"결정 리포트 {run.name}", html, labels.get("lexicon_allow"), a.allow_jargon)
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text(html, encoding="utf8")
    print(f"rendered → {out} ({len(html):,} bytes)")
    if a.copy_to:
        Path(a.copy_to).write_text(html, encoding="utf8"); print(f"copied  → {a.copy_to}")
    for w in warn: print("  ⚠", w)


if __name__ == "__main__":
    main()
