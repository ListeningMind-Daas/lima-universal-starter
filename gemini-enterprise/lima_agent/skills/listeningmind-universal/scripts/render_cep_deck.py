#!/usr/bin/env python3
"""CEP 카드 덱 리포트 렌더러 — deck.json → 단독 HTML (범용 템플릿 CSS·토큰 재사용). stdlib.

사용: python3 render_cep_deck.py deck.json -o out.html
deck.json 키: meta{title,eyebrow,scope_line,connectors_line,owner,lede_html,readiness{status,limits[]},kpis[{label,value,desc}]}
  cards[{n,title,type(상황형|전이형|시즌형|상태형),status,scale,who,why,what,ev[[k,v,t]],anchor[[k,v,t]],demo{m,a20,a30,a40,a50}|null,journey,imp,
         ni[],kbf[[text,실측|파생|없음]],cst}]  kbf_cols[]  matrix{n:[cell...]}  absent[[family,probe,verdict]]
  cross[{title,items[],hold:bool}]  footer{method_html,credits_total,credits_breakdown,used_credits,guardrails[],gaps_html}
규율: 차트 inline SVG · 수치마다 MEASURED/DERIVED · 셸 직접 주입 금지(이 스크립트만) · 가정·없음은 숨기지 않는다.
"""
import argparse, html, json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "references/report-template.html"
E = lambda s: html.escape("" if s is None else str(s), quote=False)
TY = {"상황형": "ty-s", "전이형": "ty-t", "시즌형": "ty-z", "상태형": "ty-u"}
EXTRA_CSS = '''
.pill{display:inline-block;font-size:11px;font-weight:700;padding:2px 9px;border-radius:20px;border:1px solid var(--line);color:var(--ink2);}
.ty-s{border-color:var(--s-1);color:var(--s-1);} .ty-t{border-color:var(--s-2);color:var(--s-2);} .ty-z{border-color:var(--s-3);color:var(--s-3);} .ty-u{border-color:var(--ink3);color:var(--ink2);}
.st-c{background:var(--accent-soft);color:var(--accent);border-color:transparent;} .st-k{background:var(--warn-bg);color:var(--ink2);border-color:var(--warn-bd);}
.slots{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px;font-size:13px;color:var(--ink2);}
.slots div{border:1px solid var(--line);border-radius:8px;padding:8px 10px;background:var(--paper);}
.slots b{display:block;font-size:10.5px;letter-spacing:.08em;color:var(--ink3);margin-bottom:2px;}
.two{display:grid;grid-template-columns:1.2fr 1fr;gap:20px;margin-top:12px;}
.bar-row.ev{grid-template-columns:170px 1fr 64px 96px;padding:4px 0;}
.bar-row.ev .name{font-size:12px;} .bar-row.ev .trend{font-size:11px;font-weight:600;}
.demo{margin-top:4px;} .demo .dl{display:block;font-size:11.5px;color:var(--ink3);margin:2px 0;}
.imp{font-size:13.5px;color:var(--ink);margin:10px 0 0;line-height:1.55;}
.nk{display:grid;grid-template-columns:1fr 1.2fr .9fr;gap:12px;margin-top:14px;border-top:1px dashed var(--line);padding-top:12px;}
.nkc h3{margin:0 0 6px;font-size:13px;} .nkc h3 span{color:var(--ink3);font-weight:500;font-size:11px;margin-left:6px;}
.nkc ul,.nkc ol{margin:0;padding-left:18px;font-size:13px;color:var(--ink2);} .nkc li{margin:3px 0;} .nkc ol{list-style:none;padding-left:0;}
.rk{display:inline-block;width:18px;height:18px;border-radius:50%;background:var(--accent-soft);color:var(--accent);font-size:11px;font-weight:800;text-align:center;line-height:18px;margin-right:6px;}
.lab{font-size:10px;font-weight:700;padding:1px 5px;border-radius:4px;margin-left:4px;vertical-align:1px;}
.l-m{background:var(--accent-soft);color:var(--accent);} .l-d{background:var(--line);color:var(--ink2);} .l-n{border:1px solid var(--warn-bd);color:var(--ink3);} .l-a{border:1px solid var(--s-2);color:var(--s-2);}
.nkc.cst p{font-size:12.5px;color:var(--ink2);margin:0;} .nkc.cst{background:var(--warn-bg);border:1px solid var(--warn-bd);border-radius:8px;padding:10px 12px;}
.mx td,.mx th{text-align:center;font-variant-numeric:tabular-nums;} .mx td:first-child,.mx th:first-child{text-align:left;}
.mx .r1{background:var(--accent-soft);color:var(--accent);font-weight:800;border-radius:4px;padding:1px 6px;}
.cross{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin-top:14px;}
@media (max-width:700px){.nk,.two,.slots{grid-template-columns:1fr;} .bar-row.ev{grid-template-columns:120px 1fr 56px 70px;}}
'''
LAB = {"실측": "l-m", "파생": "l-d", "없음": "l-n", "가정": "l-a"}

def fmt(v): return "—" if v is None else (f"{v:,}" if isinstance(v, (int, float)) else E(v))
def ev_rows(rows, mx):
    out = []
    for k, v, t in rows:
        w = 0 if not isinstance(v, (int, float)) or not v else max(2, v / mx * 100)
        t = t or ""
        tcls = " up" if t.startswith(("+", "▲")) else (" down" if t.startswith(("−", "-", "▼")) else "")
        out.append(f'<div class="bar-row ev"><span class="name">{E(k)}</span><div class="bar-track"><div class="bar-fill" style="width:{w:.1f}%"></div></div><span class="share">{fmt(v)}</span><span class="trend{tcls}">{E(t)}</span></div>')
    return "".join(out)
def demo_svg(d):
    if not d: return '<p class="note">성·연령 — 해당 없음 또는 미반환</p>'
    segs = [("20대", d.get("a20", 0)), ("30대", d.get("a30", 0)), ("40대", d.get("a40", 0)), ("50대+", d.get("a50", 0))]
    x, parts = 0, []
    for i, (l, p) in enumerate(segs):
        w = (p or 0) * 3.0
        parts.append(f'<rect x="{x:.1f}" y="0" width="{w:.1f}" height="14" fill="var(--s-1)" opacity="{.35 + i * .2:.2f}"/><text x="{x + w / 2:.1f}" y="26" font-size="9.5" text-anchor="middle" fill="var(--ink3)">{l} {p}%</text>')
        x += w
    m = d.get("m", 0)
    return f'<div class="demo"><span class="dl">남 {m}% · 여 {round(100 - m)}%</span><svg viewBox="0 0 300 30" width="100%" height="30" aria-label="연령 구성">{"".join(parts)}</svg><span class="dl">연령 구성 [실측 · 집계 비율]</span></div>'
def nikbf(c):
    if not c.get("ni") and not c.get("kbf"): return ""
    ni = "".join(f"<li>{E(x)}</li>" for x in c.get("ni") or [])
    kbf = "".join(f'<li><span class="rk">{i}</span>{E(k)} <span class="lab {LAB.get(t, "l-d")}">{E(t)}</span></li>' for i, (k, t) in enumerate(c.get("kbf") or [], 1))
    return f'''<div class="nk"><div class="nkc"><h3>Nano Intent <span>이 상황에서 원하는 결과·방식</span></h3><ul>{ni}</ul></div>
    <div class="nkc"><h3>KBF 서열 <span>이 상황에서의 비교 기준 — CEP마다 뒤집힘</span></h3><ol>{kbf}</ol></div>
    <div class="nkc cst"><h3>Constraint <span>선행 필터</span></h3><p>{E(c.get("cst", ""))}</p></div></div>'''
def card(c):
    vals = [v for _, v, _ in (c.get("ev") or []) + (c.get("anchor") or []) if isinstance(v, (int, float)) and v]
    mx = max(vals or [1])
    st = c.get("status", ""); stcls = "st-c" if st.startswith("confirmed") else "st-k"
    ty = c.get("type", "상황형"); scale = f'{c["scale"]:,}/월' if isinstance(c.get("scale"), (int, float)) else (c.get("scale") or "")
    anchor = f'<div class="sub" style="margin-top:10px">상위 앵커·여정 근거 <span class="badge b-measured">MEASURED</span></div><div class="bar-rows">{ev_rows(c["anchor"], mx)}</div>' if c.get("anchor") else ""
    return f'''<div class="card cep">
  <div class="shead"><span class="no">{c["n"]:02d}</span><h2>{E(c["title"])}</h2><span class="pill {TY.get(ty, "ty-s")}">{E(ty)}</span><span class="pill {stcls}">{E(st)}</span><span class="hint">{E(c.get("scale_label", "결합 쿼리 합"))} {E(scale)}</span></div>
  <div class="slots"><div><b>누가</b>{E(c.get("who"))}</div><div><b>왜</b>{E(c.get("why"))}</div><div><b>무엇을</b>{E(c.get("what"))}</div></div>
  <div class="two">
    <div><div class="sub">근거 쿼리 (월평균 검색량) <span class="badge b-measured">MEASURED</span></div><div class="bar-rows">{ev_rows(c.get("ev") or [], mx)}</div>{anchor}</div>
    <div>{demo_svg(c.get("demo"))}<p class="note"><b>여정</b> — {E(c.get("journey"))}</p><p class="imp"><b>함의</b> <span class="badge b-derived">DERIVED</span><br>{E(c.get("imp"))}</p></div>
  </div>
  {nikbf(c)}
</div>'''
def render(d):
    css = re.search(r"<style>(.*?)</style>", TEMPLATE.read_text(encoding="utf8"), re.S).group(1)
    m, cards, ft = d["meta"], d["cards"], d.get("footer") or {}
    marks = "①②③④⑤⑥⑦⑧⑨⑩"
    lim = " ".join(f"{marks[i] if i < 10 else i+1} {x}" for i, x in enumerate(m.get("readiness", {}).get("limits") or []))
    kpis = "".join(f'<div class="kpi"><div class="l">{E(k["label"])}</div><div class="v">{E(k["value"])}</div><div class="d">{E(k["desc"])}</div></div>' for k in m.get("kpis") or [])
    sumrows = "".join(f'<tr><td>{c["n"]}</td><td>{E(c["title"])}</td><td><span class="pill {TY.get(c.get("type"), "ty-s")}">{E(c.get("type"))}</span></td><td><span class="pill {"st-c" if c.get("status", "").startswith("confirmed") else "st-k"}">{E(c.get("status"))}</span></td><td style="text-align:right;font-variant-numeric:tabular-nums">{(f"{c[chr(115)+chr(99)+chr(97)+chr(108)+chr(101)]:,}" if isinstance(c.get("scale"), (int, float)) else E(c.get("scale") or "—"))}</td></tr>' for c in cards)
    cols = d.get("kbf_cols") or []; mx = d.get("matrix") or {}
    matrix = ""
    if cols and mx:
        rows = "".join("<tr><td>" + f'{c["n"]}. {E(c["title"])}' + "</td>" + "".join("<td>—</td>" if x == "—" else f'<td><span class="{"r1" if str(x)[0] == "1" else ""}">{E(x)}</span></td>' for x in mx.get(str(c["n"]), mx.get(c["n"], ["—"] * len(cols)))) + "</tr>" for c in cards)
        matrix = f'''<div class="card"><div class="shead"><span class="no">—</span><h2>CEP × KBF 매트릭스(KBF Ranking by CEP)</h2><span class="badge b-derived">DERIVED</span><span class="hint">숫자 = 서열 · ● 결합 쿼리/여정 측정 · ○ 카테고리 KBF 풀에서 파생 · □ 쿼리 있으나 볼륨 미반환 · △ 가정</span></div>
    <p class="sub">{E(d.get("matrix_sub", "같은 카테고리라도 진입 상황에 따라 1순위 기준이 다르다 — KBF를 전역 상수로 쓰면 틀린다"))}</p>
    <div class="chartbox"><table class="mx"><thead><tr><th>CEP</th>{"".join(f"<th>{E(k)}</th>" for k in cols)}</tr></thead><tbody>{rows}</tbody></table></div>
    <p class="note">{d.get("matrix_note_html", "")}</p></div>'''
    absent = "".join(f"<tr><td>{E(a)}</td><td>{E(b)}</td><td>{E(c)}</td></tr>" for a, b, c in d.get("absent") or [])
    absent_card = f'''<div class="card"><div class="shead"><span class="no">—</span><h2>{E(d.get("absent_title", "캔버스 완주 후 부재·비연결 판정"))}</h2><span class="badge b-measured">MEASURED</span><span class="hint">keyword_info ads_metrics · path_finder · [없음]=볼륨 미반환</span></div>
    <p class="sub">{E(d.get("absent_sub", "상황 패밀리별 결합 쿼리를 전수 프로브한 뒤의 부재 — “없다”를 측정값으로 말할 수 있는 근거"))}</p>
    <table><thead><tr><th>패밀리</th><th>프로브 결과</th><th>판정</th></tr></thead><tbody>{absent}</tbody></table><p class="note">{d.get("absent_note_html", "")}</p></div>''' if absent else ""
    cross = "".join(f'<div class="dcard{" noise" if x.get("hold") else ""}">{"<span class=\"flag\">다음 실측</span>" if x.get("hold") else ""}<h3>{E(x["title"])}</h3><ul>{"".join(f"<li>{i}</li>" for i in x["items"])}</ul></div>' for x in d.get("cross") or [])
    cross_card = f'<div class="card"><div class="shead"><span class="no">—</span><h2>크로스 패턴·다음 실측</h2><span class="badge b-derived">DERIVED</span><span class="hint">카드 {len(cards)}개 통합</span></div><div class="cross">{cross}</div></div>' if cross else ""
    guard = " ".join(f"{marks[i] if i < 10 else i+1} {g}" for i, g in enumerate(ft.get("guardrails") or []))
    page = f'''<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(m["title"])}</title>
<style>{css}{EXTRA_CSS}</style>
<div class="wrap">
  <div class="eyebrow">{E(m.get("eyebrow", "LISTENINGMIND · CEP DECK"))}</div>
  <h1>{E(m.get("h1", m["title"]))}</h1>
  <p class="sub">{E(m.get("scope_line"))}</p><p class="sub">{E(m.get("connectors_line"))}</p>
  <span class="owner">실행 주체 · {E(m.get("owner") or "미확정 — 확인 필요")}</span>
  <p class="lede">{m.get("lede_html", "")}</p>
  <div class="banner"><b>분석 준비도: {E(m.get("readiness", {}).get("status", "READY WITH LIMITS"))}</b> — {lim} 이 경계 안에서만 결론을 제시합니다.</div>
  <div class="kpis">{kpis}</div>
  <div class="card"><div class="shead"><span class="no">—</span><h2>카드 요약(CEP Index)</h2><span class="badge b-derived">DERIVED</span><span class="hint">{E(d.get("index_hint", "규모 = 결합 쿼리 월평균 합 · 순서는 규모·확증 강도"))}</span></div>
    <table class="sumtab"><thead><tr><th>#</th><th>CEP</th><th>유형</th><th>상태</th><th style="text-align:right">규모/월</th></tr></thead><tbody>{sumrows}</tbody></table>
    <p class="note">{d.get("index_note_html", "유형 — 상황형: 생활 맥락에서 진입 · 전이형: 인접 카테고리·관문 쿼리에서 진입 · 시즌형: 시점이 트리거 · 상태형: 사용 중 상태가 트리거. 상태 — confirmed는 결합 쿼리 볼륨 + (여정 또는 상위 앵커)로 교차 확증, candidate는 단일 신호.")}</p></div>
  {matrix}
  {"".join(card(c) for c in cards)}
  {absent_card}
  {cross_card}
  <div class="foot"><b>방법·한계</b> — {ft.get("method_html", "")} 크레딧 실측: 이번 분석 소진 <b>{E(ft.get("credits_total", "—"))}</b> ({E(ft.get("credits_breakdown", ""))}) · 월간 누적 {E(ft.get("used_credits", "—"))} (당월 누적 사용량 · 잔여 아님).<br><br>
    <b>가드레일</b> — {guard}<br><br><b>데이터 사양·공백</b> — {ft.get("gaps_html", "—")}</div>
</div>
'''
    return page

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
    """어휘 검사(lima-agents lib/lexicon_check.py ) — lima-agents가 없으면(고객 전달 스타터) 건너뛴다."""
    lima = Path(__file__).resolve().parents[2] / "lima-agents"
    if not (lima / "lib/lexicon_check.py").exists():
        print("⚠ 어휘 검사 생략 — lima-agents 미설치", file=sys.stderr)
        return page
    sys.path.insert(0, str(lima))
    from lib import lexicon_check as lx
    return lx.finalize_html("CEP 덱", page, (data or {}).get("lexicon_allow"), allow_jargon)


def _inject(page, banner):
    lima = Path(__file__).resolve().parents[2] / "lima-agents"
    if not banner:
        return page
    sys.path.insert(0, str(lima))
    from lib import gates
    return gates.inject(page, banner)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--run", help="분석 폴더(gates.json 위치) — 게이트 통과 확인")
    ap.add_argument("--allow-ungated", action="store_true", help="렌더 전 게이트 미통과여도 초안으로 렌더(배너 삽입)")
    ap.add_argument("--allow-unverified-numbers", action="store_true", help="문구 숫자 대조 미통과여도 초안으로 렌더(배너 삽입)")
    ap.add_argument("--allow-jargon", action="store_true", help="어휘 검사 미통과여도 초안으로 렌더")
    ap.add_argument("--allow-unreviewed", action="store_true", help="제목·문장 검토 기록부가 있는 설치에서만 쓰인다(스타터에는 없음)")
    a = ap.parse_args()
    banner = _gate_banner(a.run, a.allow_ungated)          # 미통과면 여기서 중단
    deck = json.loads(Path(a.deck).read_text(encoding="utf8"))
    banner += _number_check(deck, a.run, a.allow_unverified_numbers)
    page = _inject(render(deck), banner)
    page = _lexicon(page, deck, a.allow_jargon)
    Path(a.out).write_text(page, encoding="utf8")
    print(f"렌더 완료 → {a.out} ({len(page):,} bytes) · 리터럴 \\n {page.count(chr(92)+'n')}")
if __name__ == "__main__":
    main()
