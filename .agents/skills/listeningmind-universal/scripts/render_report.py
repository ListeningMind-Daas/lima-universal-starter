#!/usr/bin/env python3
"""HTML 리포트 렌더러 — data.json → references/report-template.html → 단독 HTML.

사용:
  python3 render_report.py data.json                       # → 90_Output/<title>-<date>.html (워크스페이스 탐지)
  python3 render_report.py data.json -o out.html
  python3 render_report.py --schema                        # data.json 키 설명

규율 (_shared-core.md §7): LLM은 data.json의 서술만 쓰고, 차트·레이아웃·섹션 제거·번호는 이 스크립트가 결정론으로.
셸/sed/f-string으로 템플릿에 직접 주입하지 않는다 — 개행이 \\n 리터럴로 깨져 JS SyntaxError가 난다.
G4: adapter.yaml A5 mandatory 문구가 푸터 가드레일에 빠지면 경고(렌더는 계속).
stdlib 전용.
"""
from __future__ import annotations

import argparse, datetime, html, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
TEMPLATE = SKILL / "references/report-template.html"
ADAPTER = SKILL / "adapter.yaml"

SCHEMA = """data.json 키 (없는 섹션 키는 생략 → 섹션 제거)
title, eyebrow(예: "LAPTOP · US MARKET INTELLIGENCE"), scope_line, connectors_line, owner(실행 주체 · 필수),
lede_html, readiness{status, limits[]}, kpis[{label, value, desc, dir:"up|down|"}] (4장 권장)
trend{seed, months[], vals[], unit:"천 건", sub, note_html}           — 최근 24개월 권장
tam{sub, rows[{name, cat, value, share, yoy}], note_html}            — 카테고리 리포트
sov{hint, basis, rows[{name, cat, kind:"brand|channel|generic", share, trend}], aliases_html, note_html}
decision{hint, sub, cep[], nano[], kbf[], constraint[], avoidance[], rtb[], hold[]}  — 항목은 문자열(HTML 허용)
intent_mix{sub, rows[{name, share, query}], note_html}                — 카테고리 리포트
journey{n, sub, stages[{name, query, flow}], note_html}
backlog{hint, owner_suffix, now[], watch[], risk[]} — 항목 {title, scale:"L|M|S", evidence, action, veil}
footer{method_html, credits_total, credits_breakdown, used_credits, guardrails[], gaps_html}
provenance{calls[{id, step, at, tool, params, purpose, returned, cost, raw, status, reused_from}], estimate, monthly_used}
   — 생략하면 --run 분석 폴더의 ledger.json(수집 원장)과 plan.json(견적)에서 만든다.
     리포트 끝에 «호출 순서 · 호출 로그 · 비용 보고서»를 붙이고, HTML 옆에 <이름>.calls.csv · <이름>.cost.json 을 쓴다.
     footer.credits_total 이 원장 합계와 다르면 경고한다(원장이 정본).
"""

SECTION_ORDER = ["trend", "tam", "sov", "decision", "intent_mix", "journey", "backlog"]


def num(v) -> float:
    """'27.1%' · '79%*' · 48356 · '' → float (첫 숫자만) — 막대 폭 계산용."""
    m = re.search(r"-?\d+(?:\.\d+)?", str(v if v is not None else ""))
    return float(m.group(0)) if m else 0.0


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=False)


def li(items) -> str:
    return "".join(f"<li>{x}</li>" for x in (items or [])) or "<li>— 신호 없음(해당 층 비움)</li>"


# ───────────────────────── 조각 빌더
def kpi_cards(kpis):
    out = []
    for k in (kpis or [])[:4]:
        cls = " up" if k.get("dir") == "up" else (" down" if k.get("dir") == "down" else "")
        out.append(f'<div class="kpi"><div class="l">{esc(k.get("label"))}</div><div class="v{cls}">{esc(k.get("value"))}</div>'
                   f'<div class="d">{esc(k.get("desc"))}</div></div>')
    return "\n    ".join(out)


def trend_svg(t):
    months, vals = list(t.get("months") or []), list(t.get("vals") or [])
    n = len(vals)
    if n < 2:
        return '<p class="note">시계열 부족 — 차트 생략(표·문장으로 대체)</p>'
    if n > 24 and not t.get("allow_long"):
        months, vals = months[-24:], vals[-24:]; n = 24
    ymax = max(vals) or 1
    mag = 10 ** (len(str(int(ymax))) - 1)
    ymax_r = (int(ymax / mag) + 1) * mag
    xs = [50 + i * (800 / (n - 1)) for i in range(n)]
    ys = [240 - (v / ymax_r) * 220 for v in vals]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    area = f"M{xs[0]:.1f},240 " + " ".join(f"L{x:.1f},{y:.1f}" for x, y in zip(xs, ys)) + f" L{xs[-1]:.1f},240 Z"
    imax, imin = vals.index(max(vals)), vals.index(min(vals))
    ticks = "".join(f'<text x="44" y="{240 - f*220 + 4:.1f}" font-size="11" text-anchor="end" fill="var(--ink3)">{int(ymax_r*f):,}</text>'
                    f'<line x1="50" x2="850" y1="{240 - f*220:.1f}" y2="{240 - f*220:.1f}" stroke="var(--line)" stroke-width="1"/>'
                    for f in (0, 0.5, 1))
    xl = "".join(f'<text x="{xs[i]:.1f}" y="262" font-size="11" text-anchor="middle" fill="var(--ink3)">{esc(months[i])}</text>'
                 for i in range(n) if i % max(1, n // 6) == 0 or i == n - 1)
    mark = (f'<circle cx="{xs[imax]:.1f}" cy="{ys[imax]:.1f}" r="4" fill="var(--s-1)"/>'
            f'<text x="{xs[imax]:.1f}" y="{ys[imax]-9:.1f}" font-size="11" text-anchor="middle" fill="var(--ink)">피크 {esc(months[imax])} · {vals[imax]:,}</text>'
            f'<circle cx="{xs[imin]:.1f}" cy="{ys[imin]:.1f}" r="3.5" fill="var(--s-2)"/>')
    return (f'<svg id="trend" viewBox="0 0 880 290" width="100%" role="img" aria-label="월별 검색량 추이">'
            f'{ticks}<path d="{area}" fill="var(--accent-soft)" opacity=".7"/>'
            f'<polyline points="{pts}" fill="none" stroke="var(--s-1)" stroke-width="2.2" stroke-linejoin="round"/>'
            f'{mark}{xl}<line id="xh" x1="0" x2="0" y1="20" y2="240" stroke="var(--ink3)" stroke-dasharray="3 3" style="opacity:0"/>'
            f'<rect id="hover" x="50" y="20" width="800" height="220" fill="transparent"/></svg>')


def bar_rows(rows, kind_key="kind", value_key="share", trend_key="trend", cat_key="cat"):
    out = []
    shares = [num(r.get(value_key, 0)) for r in rows]
    mx = max(shares) if shares and max(shares) > 0 else 1
    for r, s in zip(rows, shares):
        kind = r.get(kind_key, "brand")
        fill = {"channel": " channel", "generic": " generic"}.get(kind, "")
        catcls = " channel" if kind == "channel" else ""
        tr = str(r.get(trend_key, "") or "")
        tcls = " up" if tr.startswith(("▲", "+")) else (" down" if tr.startswith(("▼", "-")) else "")
        share_txt = esc(r.get(value_key)) if kind != "channel" else "—"
        out.append(f'<div class="bar-row"><span class="name">{esc(r.get("name"))}<small class="cat{catcls}">{esc(r.get(cat_key, ""))}</small></span>'
                   f'<div class="bar-track"><div class="bar-fill{fill}" style="width:{s / mx * 100:.1f}%"></div></div>'
                   f'<span class="share">{share_txt}</span><span class="trend{tcls}">{esc(tr)}</span></div>')
    return "\n      ".join(out)


def tam_rows(rows):
    out = []
    vals = [num(r.get("value", 0)) for r in rows]
    mx = max(vals) if vals and max(vals) > 0 else 1
    for r, v in zip(rows, vals):
        y = str(r.get("yoy", "") or "")
        tcls = " up" if y.startswith(("▲", "+")) else (" down" if y.startswith(("▼", "-")) else "")
        out.append(f'<div class="bar-row"><span class="name">{esc(r.get("name"))}<small class="cat">{esc(r.get("cat", ""))}</small></span>'
                   f'<div class="bar-track"><div class="bar-fill" style="width:{v / mx * 100:.1f}%"></div></div>'
                   f'<span class="share">{esc(r.get("share"))}</span><span class="trend{tcls}">{esc(y)}</span></div>')
    return "\n      ".join(out)


def intent_rows(rows):
    out = []
    shares = [num(r.get("share", 0)) for r in rows]
    mx = max(shares) if shares and max(shares) > 0 else 1
    for r, s in zip(rows, shares):
        out.append(f'<div class="bar-row"><span class="name">{esc(r.get("name"))}</span>'
                   f'<div class="bar-track"><div class="bar-fill" style="width:{s / mx * 100:.1f}%"></div></div>'
                   f'<span class="share">{esc(r.get("share"))}</span><span class="trend"><code style="font-size:11px">{esc(r.get("query", ""))}</code></span></div>')
    return "\n      ".join(out)


def decision_cards(d):
    cards = [("CEP", "카테고리 진입 상황", d.get("cep")), ("Nano Intent", "원하는 해결 방식", d.get("nano")),
             ("KBF", "구매 결정 요인", d.get("kbf")), ("Constraint", "제약(선행 필터)", d.get("constraint")),
             ("Avoidance", "회피 요인", d.get("avoidance")), ("RTB", "신뢰 체계", d.get("rtb"))]
    out = [f'<div class="dcard"><h3>{esc(h)} <span>{esc(s)}</span></h3><ul>{li(items)}</ul></div>' for h, s, items in cards]
    if d.get("hold"):
        out.append(f'<div class="dcard noise"><span class="flag">해석 보류</span><h3>약한 연관 노드</h3><ul>{li(d["hold"])}</ul></div>')
    return "\n      ".join(out)


def journey_stages(stages):
    out = []
    for i, s in enumerate(stages or [], 1):
        q = f'<code>{esc(s.get("query"))}</code> → ' if s.get("query") else ""
        out.append(f'<div class="stage"><div class="n">STAGE {i}</div><div class="t">{esc(s.get("name"))}</div><div class="q">{q}{s.get("flow", "")}</div></div>')
    return "\n      ".join(out)


def backlog_rows(b):
    groups = [("g-now", "지금 대응할 변화", b.get("now")), ("g-watch", "계속 지켜볼 변화", b.get("watch")), ("g-risk", "위험 신호", b.get("risk"))]
    out = []
    for cls, title, items in groups:
        if not items:
            continue
        out.append(f'<tr class="group {cls}"><td colspan="3">{title}</td></tr>')
        for it in items:
            sc = (it.get("scale") or "").upper()
            badge = f'<span class="sc sc-{sc.lower()}">{sc}</span>' if sc in ("L", "M", "S") else ""
            veil = f'<span class="veil">{it["veil"]}</span>' if it.get("veil") else ""
            out.append(f'<tr><td>{esc(it.get("title"))}</td><td>{badge}{it.get("evidence", "")}</td><td>{it.get("action", "")}{veil}</td></tr>')
    return "\n        ".join(out)


# ───────────────────────── 템플릿 조립
def drop_section(tpl: str, sid: str) -> str:
    return re.sub(rf"\s*<!-- SECTION:{sid} -->.*?<!-- /SECTION:{sid} -->", "", tpl, flags=re.S)


def keep_section(tpl: str, sid: str) -> str:
    return tpl.replace(f"<!-- SECTION:{sid} -->", "").replace(f"<!-- /SECTION:{sid} -->", "")


def mandatory_texts():
    if not ADAPTER.exists():
        return []
    return re.findall(r'text:\s*"([^"]+)"', ADAPTER.read_text(encoding="utf8"))


# ───────────────────────── 호출 순서 · 호출 로그 · 비용 보고서 (산출물마다)
CALL_COLS = [("id", "ID"), ("step", "단계"), ("at", "시각"), ("tool", "도구"), ("params", "요청 조건(키워드·범위)"),
             ("returned", "받은 항목 수"), ("cost", "크레딧"), ("raw", "원본 파일"), ("status", "상태")]


def _params_text(p) -> str:
    if isinstance(p, dict):
        parts = []
        for k, v in p.items():
            if isinstance(v, list):
                v = ", ".join(map(str, v[:4])) + (f" 외 {len(v) - 4}" if len(v) > 4 else "")
            parts.append(f"{k}={v}")
        return " · ".join(parts)
    return "" if p is None else str(p)


def load_provenance(data: dict, run) -> tuple[dict, list[str]]:
    """data.provenance 가 있으면 그것을, 없으면 분석 폴더의 수집 원장(ledger.json)과 견적(plan.json)을 쓴다."""
    warns = []
    pv = dict(data.get("provenance") or {})
    rd = Path(run) if run else None
    if not pv.get("calls") and rd and (rd / "ledger.json").is_file():
        led = json.loads((rd / "ledger.json").read_text(encoding="utf8"))
        calls = []
        for i, e in enumerate(led, 1):
            live = e.get("source", "live") == "live"
            calls.append({"id": f"C{i}", "step": e.get("step"), "at": str(e.get("at", ""))[:16].replace("T", " "),
                          "tool": e.get("tool"), "params": _params_text(e.get("params")),
                          "returned": (e.get("params") or {}).get("n") if isinstance(e.get("params"), dict) else None,
                          "cost": (e.get("cost") or 0) if live else 0, "raw": e.get("raw") or "—",
                          "status": "새 요청" if live else "저장된 데이터 재사용",
                          "reused_from": None if live else f"저장본({e.get('source')})"})
        pv["calls"] = calls
        pv.setdefault("source", "ledger.json")
        plan = rd / "plan.json"
        if "estimate" not in pv and plan.is_file():
            est = (json.loads(plan.read_text(encoding="utf8")).get("estimate") or {}).get("total_range")
            if est:
                pv["estimate"] = est
    if "monthly_used" not in pv:
        mu = (data.get("footer") or {}).get("used_credits")
        if isinstance(mu, (int, float)) or (isinstance(mu, str) and re.fullmatch(r"[\d,]+", mu or "")):
            pv["monthly_used"] = int(str(mu).replace(",", ""))
    if not pv.get("calls"):
        warns.append("호출 기록 없음 — --run 으로 분석 폴더(ledger.json)를 주거나 data.provenance.calls 를 넣을 것. "
                     "리포트에 «호출 기록 없음»이 표시된다")
    total = sum(c.get("cost") or 0 for c in pv.get("calls") or [])
    ct = (data.get("footer") or {}).get("credits_total")
    if pv.get("calls") and ct not in (None, "", "—"):
        try:
            if int(str(ct).replace(",", "").split()[0]) != total:
                warns.append(f"footer.credits_total {ct} ≠ 호출 원장 합계 {total:,} — 비용 보고서는 원장을 따른다")
        except ValueError:
            pass
    return pv, warns


def cost_summary(pv: dict) -> dict:
    calls = pv.get("calls") or []
    by_tool, by_step = {}, {}
    for c in calls:
        for key, bucket in ((c.get("tool") or "—", by_tool), (c.get("step") or "—", by_step)):
            b = bucket.setdefault(key, {"calls": 0, "cost": 0})
            b["calls"] += 1
            b["cost"] += c.get("cost") or 0
    return {"total": sum(c.get("cost") or 0 for c in calls), "calls": len(calls),
            "reused": sum(1 for c in calls if c.get("reused_from")), "by_tool": by_tool, "by_step": by_step,
            "estimate": pv.get("estimate"), "monthly_used": pv.get("monthly_used"), "source": pv.get("source", "data.provenance")}


def _n(v):
    return "—" if v is None else (f"{v:,}" if isinstance(v, (int, float)) else esc(v))


def provenance_html(pv: dict) -> str:
    calls = pv.get("calls") or []
    head = '<div class="card" id="provenance"><div class="shead"><span class="no">부록</span><h2>데이터 출처와 크레딧 사용 내역</h2>'
    if not calls:
        return head + '<span class="badge b-derived">GAP</span></div><p class="sub">데이터 요청 기록이 없어, 이 리포트의 숫자가 어떤 요청에서 나왔는지 확인할 수 없다.</p></div>'
    cs = cost_summary(pv)
    # 도구 이름 · 호출 조건 · 단계 코드 · 파일 경로는 기계 식별자다 — <code> 로 감싸 어휘 검사 대상에서 뺀다
    seq = "".join(f'<li id="call-{esc(c.get("id"))}"><b>{esc(c.get("id"))}</b> · <code>{esc(c.get("step") or "—")}</code> · <code>{esc(c.get("tool"))}</code>'
                  f' — {esc(c.get("purpose")) if c.get("purpose") else "<code>" + esc(c.get("params")) + "</code>"} <span class="sub">→ {_n(c.get("cost"))} 크레딧'
                  f'{" · 저장된 데이터 재사용" if c.get("reused_from") else ""}</span></li>' for c in calls)
    th = "".join(f"<th>{lab}</th>" for _, lab in CALL_COLS)
    CODE = {"step", "tool", "params", "raw"}
    def cell(c, k):
        if k in ("returned", "cost"):
            return _n(c.get(k))
        v = esc(c.get(k) if c.get(k) is not None else "—")
        return f"<code>{v}</code>" if k in CODE else v
    rows = "".join("<tr>" + "".join(f"<td>{cell(c, k)}</td>" for k, _ in CALL_COLS) + "</tr>" for c in calls)
    est = cs["estimate"]
    est_txt = (f"{est[0]:,}~{est[1]:,}" if isinstance(est, list) and len(est) == 2 else _n(est)) if est is not None else "기록 없음"
    def bucket(title, d):
        tr = "".join(f"<tr><td><code>{esc(k)}</code></td><td>{v['calls']}</td><td>{v['cost']:,}</td>"
                     f"<td>{(v['cost'] / cs['total'] * 100 if cs['total'] else 0):.1f}%</td></tr>" for k, v in d.items())
        return f'<table><thead><tr><th>{title}</th><th>호출</th><th>비용(크레딧)</th><th>비중</th></tr></thead><tbody>{tr}</tbody></table>'
    return (head + f'<span class="badge b-measured">MEASURED</span><span class="hint">출처 · {esc(cs["source"])}</span></div>'
            f'<h3 id="calls-seq">데이터 요청 순서 (요청별 사용 크레딧)</h3><ol>{seq}</ol>'
            f'<h3 id="calls-log">데이터 요청별 상세 기록</h3><div style="overflow-x:auto"><table><thead><tr>{th}</tr></thead><tbody>{rows}</tbody></table></div>'
            f'<h3 id="cost">크레딧 사용 요약</h3><table><tbody>'
            f'<tr><th>이번 리포트에 쓴 크레딧</th><td><b>{cs["total"]:,} 크레딧</b> — 데이터 요청 {cs["calls"]}건의 합(응답 cost_detail 합산)</td></tr>'
            f'<tr><th>이전에 저장해 둔 데이터를 재사용한 요청 수</th><td>{cs["reused"]}건</td></tr>'
            f'<tr><th>견적</th><td>{est_txt}</td></tr>'
            f'<tr><th>이번 달 계정 누적 사용량(잔여 아님)</th><td>{_n(cs["monthly_used"])}</td></tr></tbody></table>'
            + bucket("도구", cs["by_tool"]) + bucket("단계", cs["by_step"]) + "</div>")


def write_sidecars(out: Path, pv: dict) -> list[Path]:
    import csv
    files = [out.with_suffix(".calls.csv"), out.with_suffix(".cost.json")]
    with files[0].open("w", encoding="utf-8-sig", newline="") as fp:
        w = csv.writer(fp)
        w.writerow([k for k, _ in CALL_COLS] + ["purpose", "reused_from"])
        for c in pv.get("calls") or []:
            w.writerow([c.get(k) for k, _ in CALL_COLS] + [c.get("purpose"), c.get("reused_from")])
    files[1].write_text(json.dumps(cost_summary(pv), ensure_ascii=False, indent=1), encoding="utf8")
    return files


def render(data: dict, provenance: dict | None = None) -> tuple[str, list[str]]:
    tpl = TEMPLATE.read_text(encoding="utf8")
    tpl = re.sub(r"^\s*<!--.*?-->\s*", "", tpl, count=1, flags=re.S)   # 상단 작성 가이드 주석은 산출물에서 제거
    warnings = []
    if not data.get("owner"):
        warnings.append("owner(실행 주체) 비어 있음 — 리포트 미완성. AskUserQuestion으로 확인 후 채울 것")
    present = [s for s in SECTION_ORDER if data.get(s)]
    for s in SECTION_ORDER:
        tpl = keep_section(tpl, s) if s in present else drop_section(tpl, s)
    tpl = keep_section(tpl, "trend_script") if "trend" in present else drop_section(tpl, "trend_script")
    # 섹션 번호 재부여
    nos = iter(f"{i:02d}" for i in range(1, len(present) + 1))
    tpl = re.sub(r"\{\{NO\}\}", lambda m: next(nos, "--"), tpl)

    rd, ft = data.get("readiness") or {}, data.get("footer") or {}
    limits = rd.get("limits") or []
    marks = "①②③④⑤⑥⑦⑧⑨"
    limits_html = " ".join(f"{marks[i] if i < 9 else i+1} {x}" for i, x in enumerate(limits)) + ("." if limits else "")
    guard = ft.get("guardrails") or []
    guard_html = " ".join(f"{marks[i] if i < 9 else i+1} {g}" for i, g in enumerate(guard))
    joined = " ".join(guard)
    for t in mandatory_texts():
        key = t[:6]
        if key not in joined:
            warnings.append(f"[G4] A5 mandatory 문구 누락 의심: 「{t}」 — footer.guardrails에 포함할 것")

    # 크레딧은 호출 원장이 정본이다 — 원장이 있으면 손으로 적은 합계 대신 원장 합계 · 도구별 내역을 쓴다
    pv = provenance if provenance is not None else (data.get("provenance") or {})
    if pv.get("calls"):
        cs = cost_summary(pv)
        credits_total = f'{cs["total"]:,}'
        credits_breakdown = " · ".join(f'{k} {v["cost"]:,}' for k, v in cs["by_tool"].items())
    else:
        credits_total, credits_breakdown = ft.get("credits_total", "—"), ft.get("credits_breakdown", "")
    t, s, d, j, b, im, tm = (data.get(k) or {} for k in ("trend", "sov", "decision", "journey", "backlog", "intent_mix", "tam"))
    rep = {
        "TITLE": esc(data.get("title")), "EYEBROW": esc(data.get("eyebrow", "MARKET INTELLIGENCE")),
        "SCOPE_LINE": esc(data.get("scope_line")), "CONNECTORS_LINE": esc(data.get("connectors_line")),
        "OWNER": esc(data.get("owner") or "미확정 — 실행 주체 확인 필요"), "LEDE_HTML": data.get("lede_html", ""),
        "READINESS_STATUS": esc(rd.get("status", "READY WITH LIMITS")), "READINESS_LIMITS_HTML": limits_html,
        "KPI_CARDS_HTML": kpi_cards(data.get("kpis")),
        "TREND_SUB": esc(t.get("sub", f"{t.get('seed', '')} 월별 검색량 · 최근 24개월 (단위: {t.get('unit', '건')})")),
        "TREND_SVG_HTML": trend_svg(t) if t else "", "TREND_NOTE_HTML": t.get("note_html", ""),
        "TAM_SUB": esc(tm.get("sub", "")), "TAM_ROWS_HTML": tam_rows(tm.get("rows") or []), "TAM_NOTE_HTML": tm.get("note_html", ""),
        "SOV_HINT": esc(s.get("hint", "cluster_finder(엔티티) + intent_finder(모델명) + keyword_info")),
        "SOV_BASIS": esc(s.get("basis", "브랜드+모델 그룹 합산")), "SOV_ROWS_HTML": bar_rows(s.get("rows") or []),
        "SOV_ALIASES_HTML": s.get("aliases_html", "(brand-map 참조)"), "SOV_NOTE_HTML": s.get("note_html", ""),
        "DECISION_HINT": esc(d.get("hint", "cluster_finder(군집) + keyword_info(볼륨 검증)")), "DECISION_SUB": esc(d.get("sub", "")),
        "DECISION_CARDS_HTML": decision_cards(d),
        "INTENT_SUB": esc(im.get("sub", "")), "INTENT_ROWS_HTML": intent_rows(im.get("rows") or []), "INTENT_NOTE_HTML": im.get("note_html", ""),
        "JOURNEY_N": esc(j.get("n", "")), "JOURNEY_SUB": esc(j.get("sub", "")), "JOURNEY_STAGES_HTML": journey_stages(j.get("stages")),
        "JOURNEY_NOTE_HTML": j.get("note_html", ""),
        "BACKLOG_OWNER_SUFFIX": esc(f" — {b['owner_suffix']}" if b.get("owner_suffix") else ""), "BACKLOG_HINT": esc(b.get("hint", "수행 잡")),
        "BACKLOG_ROWS_HTML": backlog_rows(b),
        "METHOD_HTML": ft.get("method_html", ""), "CREDITS_TOTAL": esc(credits_total),
        "CREDITS_BREAKDOWN": esc(credits_breakdown), "USED_CREDITS": esc(ft.get("used_credits", "—")),
        "GUARDRAILS_HTML": guard_html, "GAPS_HTML": ft.get("gaps_html", "—"),
        "PROVENANCE_HTML": provenance_html(pv),
    }
    tpl = re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: rep.get(m.group(1), m.group(0)), tpl)
    left = sorted(set(re.findall(r"\{\{([A-Z_]+)\}\}", tpl)))
    if left:
        warnings.append(f"미치환 플레이스홀더: {left}")
    # 차트 데이터는 json.dumps로만 주입 (개행·따옴표 안전)
    tpl = tpl.replace("/*MONTHS_JSON*/[]/*END*/", json.dumps(t.get("months") or [], ensure_ascii=False))
    tpl = tpl.replace("/*VALS_JSON*/[]/*END*/", json.dumps(t.get("vals") or []))
    tpl = tpl.replace('/*UNIT_JSON*/""/*END*/', json.dumps(t.get("unit", ""), ensure_ascii=False))
    return tpl, warnings


def default_out(data: dict) -> Path:
    root = next((d for d in [Path.cwd(), *HERE.parents] if (d / "90_Output").is_dir()), Path.cwd())
    slug = re.sub(r"[^0-9A-Za-z가-힣]+", "-", data.get("title", "report")).strip("-")[:40]
    return (root / "90_Output" if (root / "90_Output").is_dir() else root) / f"{slug}-{datetime.date.today().isoformat()}.html"


def _gate_banner(run, allow_ungated):
    """분석 건별 게이트(lima-agents lib/gates.py · run-gates/v1) — 렌더 전 게이트 미통과면 중단, 아니면 배너 HTML.
    lima-agents가 함께 설치돼 있지 않으면 확인을 건너뛰고 경고만 남긴다(단독 설치 호환)."""
    lima = Path(__file__).resolve().parents[2] / "lima-agents"
    if not (lima / "lib/gates.py").exists():
        print("⚠ 게이트 확인 생략 — lima-agents(lib/gates.py) 미설치", file=sys.stderr)
        return ""
    sys.path.insert(0, str(lima))
    from lib import gates
    return gates.require_for_render(Path(run) if run else None, allow_ungated)


def _number_check(data, run, allow_unverified):
    """작성 문구 숫자 대조(lima-agents lib/prose_check.py ) — data의 문장 속 숫자를 run 원자료·core 계산값·data의 수치 필드와 대조.
    --run이 없거나 lima-agents가 없으면 건너뛴다. 게이트 기록(gates.json)이 있는 run은 미통과 시 중단, 레거시 run은 배너만."""
    lima = Path(__file__).resolve().parents[2] / "lima-agents"
    if not run or not (lima / "lib/prose_check.py").exists():
        print("⚠ 숫자 대조 생략 — --run 없음 또는 lima-agents 미설치", file=sys.stderr)
        return ""
    sys.path.insert(0, str(lima))
    from lib import prose_check as pc
    nc = data.get("number_check") or {}
    texts = pc.config_texts(data, set(nc.get("skip") or []) | {"number_check", "eyebrow"})
    numeric = json.loads(json.dumps(data), object_hook=lambda d: {k: v for k, v in d.items() if not isinstance(v, str)})
    errs = pc.gate("리포트 데이터", texts, [numeric], run=[Path(run)], number_check=nc, brands=pc.brand_names(nc.get("vertical")),
                   ws=next((d for d in Path(run).resolve().parents if (d / "90_Output").is_dir()), None))
    if pc.enforce(Path(run), errs, allow_unverified):
        raise SystemExit(pc.abort_message("리포트 데이터", errs) + "\n  초안이 꼭 필요하면 --allow-unverified-numbers (산출물에 미통과 배너)")
    print(f"숫자 대조 {'미통과 ' + str(len(errs)) + '건 — 산출물에 배너' if errs else '통과'} — 문구 {len(texts)}건")
    return pc.banner_html(errs)


def _lexicon(page, data, allow_jargon):
    """어휘 검사(lima-agents lib/lexicon_check.py ) — 업무 사용자가 못 읽는 분석 작업 용어를 치환하고, 남으면 중단.
    lima-agents가 없으면(고객 전달 스타터) 건너뛴다."""
    lima = Path(__file__).resolve().parents[2] / "lima-agents"
    if not (lima / "lib/lexicon_check.py").exists():
        print("⚠ 어휘 검사 생략 — lima-agents 미설치", file=sys.stderr)
        return page
    sys.path.insert(0, str(lima))
    from lib import lexicon_check as lx
    return lx.finalize_html("리포트", page, (data or {}).get("lexicon_allow"), allow_jargon)


def _inject(page, banner):
    lima = Path(__file__).resolve().parents[2] / "lima-agents"
    if not banner:
        return page
    sys.path.insert(0, str(lima))
    from lib import gates
    return gates.inject(page, banner)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--schema", action="store_true")
    ap.add_argument("--run", help="분석 폴더(gates.json 위치) — 게이트 통과 확인")
    ap.add_argument("--allow-ungated", action="store_true", help="렌더 전 게이트 미통과여도 초안으로 렌더(배너 삽입)")
    ap.add_argument("--allow-unverified-numbers", action="store_true", help="문구 숫자 대조 미통과여도 초안으로 렌더(배너 삽입)")
    ap.add_argument("--allow-jargon", action="store_true", help="어휘 검사 미통과여도 초안으로 렌더")
    ap.add_argument("--allow-unreviewed", action="store_true", help="제목·문장 검토 기록부가 있는 설치에서만 쓰인다(스타터에는 없음)")
    a = ap.parse_args()
    if a.schema or not a.data:
        print(SCHEMA); return
    data = json.loads(Path(a.data).read_text(encoding="utf8"))
    banner = _gate_banner(a.run, a.allow_ungated)          # 미통과면 여기서 중단
    banner += _number_check(data, a.run, a.allow_unverified_numbers)
    pv, pv_warn = load_provenance(data, a.run)
    html_out, warnings = render(data, pv)
    warnings += pv_warn
    html_out = _inject(html_out, banner)
    html_out = _lexicon(html_out, data, a.allow_jargon)
    out = Path(a.out) if a.out else default_out(data)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_out, encoding="utf8")
    side = write_sidecars(out, pv)
    bad = html_out.count("\\n")
    cs = cost_summary(pv)
    print(f"렌더 완료 → {out} ({len(html_out):,} bytes) · 리터럴 \\n 개수 {bad}")
    print(f"호출 {cs['calls']}건 · 소진 {cs['total']:,} 크레딧 → {side[0].name} · {side[1].name}")
    for w in warnings:
        print("⚠", w)
    sys.exit(1 if any(w.startswith("미치환") for w in warnings) else 0)


if __name__ == "__main__":
    main()
