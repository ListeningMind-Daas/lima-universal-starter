"""분석 건별 게이트 기록 (run-gates/v1) — 신규 분석이 파이프라인을 통과했는지 run 폴더에 남기고, 렌더·발행 때 확인한다.

2026-09-17 신설. 근거: 실행 파이프라인·체크리스트는 문서로만 있었고, 분석마다 어느 게이트를 통과했는지 남는 곳이
없었다. 렌더러도 확인하지 않고 산출물을 냈다(정본 공백 상태의 run이 산출물까지 나간 실측 사례가 있다).

두 단계
  render   렌더 전에 끝나야 하는 것 — 예산 승인 · 정본 해석 · 수집·엔진 게이트 · 준비도 · 회귀 테스트
  publish  외부로 내보내기 전에 끝나야 하는 것 — render 전부 + 출처 라벨 확인 · 규칙 회수
           (라벨 확인과 규칙 회수는 렌더 결과를 봐야 할 수 있으므로 렌더를 막지 않는다)

상태  pass · fail · waived(사유 필수 · 산출물에 공개) · pending · na(자동 판정만 — 해당 도구가 없는 환경)
      ask(결정 필요 — 사전 공백. 오류가 아니다) · filling(사용자가 채우기로 함) · skipped(사용자가 건너뛰기로 함)
기록  <run>/gates.json — 사람 기록(source=manual)은 자동 갱신이 덮어쓰지 않는다(채우기·건너뛰기 뒤 사전이 채워져 통과하면 통과로 갱신)

사전 공백은 실패·대기로 두지 않는다 (2026-09-17)
  품목 사전·정본이 이 품목을 덮지 않는 것은 오류가 아니라 사용자가 정할 문제다. 자동 판정은 'ask'로 두고,
  에이전트가 "품목 사전을 채울까요?"라고 묻는다 → 채우기: 사전 작성 후 check · 건너뛰기: decide --choice skip.
  건너뛰면 렌더는 막지 않고 "사전 생략(사용자 선택) — 브랜드 귀속·정본 판정은 잠정" 한 줄만 산출물에 남긴다.
  크레딧을 쓰는 CEP Finder 실측 run은 사전 공백이면 지출 전에 멈추고 이 질문을 먼저 받는다(--on-dictionary-gap).

렌더러 계약 (require_for_render)
  gates.json 없음        → 막지 않음 · '게이트 기록 없음' 배너 (2026-09-17 이전 run)
  render 단계 미통과     → 렌더 중단(SystemExit) · --allow-ungated면 렌더하되 미통과 배너
  통과                  → 면제(waived) 항목만 배너로 공개 · publish 미완은 한 줄 안내

표준 라이브러리만 쓴다. 정본 해석기(별도 오케스트레이션 스킬)·테스트 스위트가 없으면 해당 게이트는
수동 기록(attest/waive)을 요구하거나 na로 둔다 — 고객사 스타터에서도 같은 파일 형식으로 동작한다.
"""
from __future__ import annotations

import datetime
import html
import json
import re
import subprocess
import sys
from pathlib import Path

SCHEMA = "run-gates/v1"
SKILLS_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = SKILLS_ROOT.parents[1]

# (id, 이름, 단계, 파이프라인 단계)
GATES = [
    ("budget", "예산 승인", "render", "6"),
    ("canon", "정본 해석", "render", "6.5"),
    ("data", "수집·엔진 게이트", "render", "7~8"),
    ("readiness", "준비도", "render", "9"),
    ("tests", "회귀 테스트", "render", "—"),
    ("labels", "출처 라벨 확인", "publish", "10"),
    ("rules", "규칙 회수", "publish", "11"),
]
GATE_IDS = [g[0] for g in GATES]
NAMES = {g[0]: g[1] for g in GATES}
STAGE_OF = {g[0]: g[2] for g in GATES}
PASSING = {"pass", "waived", "na", "skipped"}
DICT_GATES = ("canon", "readiness")                            # 사전 공백 결정이 적용되는 게이트
DICT_QUESTION = "이 품목의 사전(브랜드·품목 어휘)이 비어 있거나 부족합니다. 사전을 채울까요, 건너뛰고 진행할까요?"
MANUAL_OK = {"pass", "waived"}


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def path_for(run: Path, override: Path | None = None) -> Path:
    return Path(override) if override else Path(run) / "gates.json"


def load(run: Path, override: Path | None = None) -> dict | None:
    p = path_for(run, override)
    if not p.exists():
        return None
    with p.open(encoding="utf8") as fh:
        return json.load(fh)


def save(run: Path, doc: dict, override: Path | None = None) -> Path:
    p = path_for(run, override)
    p.parent.mkdir(parents=True, exist_ok=True)
    doc["updated_at"] = _now()
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf8")
    return p


def init(run: Path, vertical: str | None, category: str | None, market: str = "kr",
         override: Path | None = None) -> dict:
    """없으면 만들고, 있으면 메타만 보충한다(기존 기록 보존)."""
    doc = load(run, override) or {"schema": SCHEMA, "run": str(Path(run)), "created_at": _now(),
                                   "gates": {g: {"status": "pending", "source": "auto", "evidence": ""} for g in GATE_IDS},
                                   "history": []}
    doc.setdefault("meta", {})
    for k, v in (("vertical", vertical), ("category", category), ("market", market)):
        if v and not doc["meta"].get(k):
            doc["meta"][k] = v
    for g in GATE_IDS:
        doc["gates"].setdefault(g, {"status": "pending", "source": "auto", "evidence": ""})
    return doc


def _set_auto(doc: dict, gate: str, status: str, evidence: str, **extra):
    cur = doc["gates"][gate]
    if cur.get("source") == "manual" and cur.get("status") in ("filling", "skipped") and status == "pass":
        cur = {}                               # 채우기·건너뛰기 뒤 사전이 실제로 채워졌으면 통과로 갱신
    elif cur.get("source") == "manual":        # 사람 기록은 자동 판정이 덮지 않는다
        cur.setdefault("auto_latest", {})
        cur["auto_latest"] = {"status": status, "evidence": evidence, "at": _now(), **extra}
        return
    doc["gates"][gate] = {"status": status, "source": "auto", "evidence": evidence, "at": _now(), **extra}


def _manifest(run: Path) -> dict | None:
    f = Path(run) / "out/run_manifest.json"
    if not f.exists():
        return None
    with f.open(encoding="utf8") as fh:
        return json.load(fh)


# ── 자동 판정 ──────────────────────────────────────────────────────────────
def auto_budget(doc: dict, mf: dict | None):
    if not mf:
        return
    c = mf.get("credits") or {}
    spent, cap = c.get("spent") or 0, c.get("budget")
    if spent == 0:
        _set_auto(doc, "budget", "pass", "신규 지출 0크레딧(replay·저장본)")
    elif cap:
        st = "pass" if spent <= cap else "fail"
        _set_auto(doc, "budget", st, f"실행 전 상한 {cap:,} · 소진 {spent:,}크레딧")
    else:
        _set_auto(doc, "budget", "pending", f"소진 {spent:,}크레딧 · 상한(--budget) 없이 실행 — 사전 승인 기록 필요(attest)")


def auto_data(doc: dict, mf: dict | None):
    if not mf:
        return
    gates = mf.get("gates") or []
    bad = [g for g in gates if str(g.get("verdict")) in ("실패", "차단", "fail", "FAIL")]
    warn = [g for g in gates if str(g.get("verdict")) in ("경고", "warn")]
    ev = f"엔진 게이트 {len(gates)}건 · 실패 {len(bad)} · 경고 {len(warn)}"
    if warn:
        ev += " — 경고: " + " / ".join(f"{g.get('gate')} {g.get('name')}" for g in warn[:4])
    _set_auto(doc, "data", "fail" if bad else "pass", ev)


def auto_readiness(doc: dict, mf: dict | None):
    if not mf:
        return
    v = ((mf.get("adapter") or {}).get("validation")) or {}
    slots = v.get("slots") or {}
    uncovered = [f"{sid}: {i}" for sid, s in slots.items() for i in (s.get("issues") or []) if "미등재" in str(i)]
    errors = v.get("errors") or []
    if errors:
        _set_auto(doc, "readiness", "fail", " · ".join((errors + uncovered)[:4]))
    elif uncovered:                                            # 사전 공백 — 오류가 아니라 사용자 결정
        _set_auto(doc, "readiness", "ask", " · ".join(uncovered[:4]), question=DICT_QUESTION)
    else:
        partial = [sid for sid, s in slots.items() if s.get("effective_status") != "ready"]
        _set_auto(doc, "readiness", "pass", "어댑터 커버리지 통과" + (f" · 선언상 부분 {', '.join(partial)}" if partial else ""))


def auto_canon(doc: dict, run: Path):
    meta = doc.get("meta") or {}
    resolver = None   # 이 패키지에는 정본 해석기가 없다
    if resolver is None:
        _set_auto(doc, "canon", "ask", "정본 해석기가 없는 설치 — 버티컬 정본이 이 품목을 덮는지 사용자에게 확인",
                  question=DICT_QUESTION)
        return
    if not meta.get("vertical") or not meta.get("category"):
        _set_auto(doc, "canon", "pending", "vertical·category 메타 없음 — run_gate.py init으로 지정")
        return
    data_dir = Path(run)                                       # R3 원자료 — replay run은 원본 raw를 가리킨다
    if not any((data_dir / "raw").glob("serp_*.json")):
        mf = _manifest(run) or {}
        if mf.get("replay") and Path(mf["replay"]).exists():
            data_dir = Path(mf["replay"])
    sys.path.insert(0, str(resolver.parent))
    try:
        import canon_resolve                                   # noqa: E402
        res = canon_resolve.resolve(meta["vertical"], meta["category"], meta.get("market", "kr"), data_dir)
    except Exception as e:                                     # noqa: BLE001
        _set_auto(doc, "canon", "pending", f"정본 해석 실행 실패: {e}")
        return
    st = res["state"]
    r3 = res["checks"].get("R3") or {}
    ev = f"{st} · R1 {res['checks']['R1']['status']} · R2 {res['checks']['R2']['status']} · R3 {r3.get('status')}"
    if r3.get("disagreements"):
        ev += " · 불일치 " + ", ".join(d["name"] for d in r3["disagreements"][:6])
    if st == "COVERED":
        _set_auto(doc, "canon", "pass", ev, state=st)
    else:                                                      # 정본 공백·외부 열거 미실행 — 사용자 결정
        q = ("SERP 외부 열거(약 60크레딧)로 정본을 확인할까요, 건너뛸까요?" if st == "UNRESOLVED"
             else "정본(사전)이 이 품목을 덮지 않습니다. 정본 작업으로 채울까요, 건너뛰고 진행할까요?")
        _set_auto(doc, "canon", "ask", ev, state=st, next=res.get("next"), question=q)


def auto_tests(doc: dict):
    tests = WORKSPACE / "tests"
    if not tests.is_dir():
        _set_auto(doc, "tests", "na", "이 설치에는 회귀 테스트 스위트가 없다")
        return
    p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
                       cwd=WORKSPACE, capture_output=True, text=True, timeout=900)
    ran = re.search(r"Ran (\d+) tests?", p.stderr or "")
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=WORKSPACE, capture_output=True, text=True).stdout.strip()
    ev = f"{ran.group(0) if ran else '실행 결과 파싱 실패'} · {'OK' if p.returncode == 0 else 'FAILED'} · HEAD {sha or '—'}"
    _set_auto(doc, "tests", "pass" if p.returncode == 0 else "fail", ev)


def refresh(run: Path, override: Path | None = None, run_tests: bool = True, canon: bool = True) -> dict:
    doc = init(run, None, None, override=override)
    mf = _manifest(run)
    if mf:
        doc["meta"].setdefault("vertical", (mf.get("adapter") or {}).get("vertical"))
        doc["meta"].setdefault("run_id", mf.get("run_id"))
    auto_budget(doc, mf)
    auto_data(doc, mf)
    auto_readiness(doc, mf)
    if canon:
        auto_canon(doc, run)
    if run_tests:
        auto_tests(doc)
    elif not (WORKSPACE / "tests").is_dir():                   # 스위트 자체가 없는 설치(고객사 스타터 등)는 실행과 무관하게 n/a
        _set_auto(doc, "tests", "na", "이 설치에는 회귀 테스트 스위트가 없다")
    doc["history"].append({"at": _now(), "action": "refresh"})
    save(run, doc, override)
    return doc


# ── 사람 기록 ──────────────────────────────────────────────────────────────
def attest(run: Path, gate: str, status: str, by: str, note: str, override: Path | None = None) -> dict:
    if gate not in GATE_IDS:
        raise ValueError(f"알 수 없는 게이트: {gate}")
    if gate == "rules":
        raise ValueError("규칙 회수는 record_rules로 기록한다(등록부 ID 검증)")
    if gate == "tests" and status == "pass":
        raise ValueError("회귀 테스트는 사람이 통과로 기록할 수 없다 — run_gate.py check로 실행하거나 사유와 함께 waive")
    if status not in MANUAL_OK:
        raise ValueError("사람 기록 상태는 pass | waived")
    if not by or not note.strip():
        raise ValueError("기록자(--by)와 근거·사유(--note)는 필수")
    doc = load(run, override)
    if doc is None:
        raise ValueError("gates.json 없음 — 먼저 run_gate.py init")
    prev = doc["gates"][gate]
    doc["gates"][gate] = {"status": status, "source": "manual", "by": by, "evidence": note, "at": _now(),
                          "auto_latest": {k: prev.get(k) for k in ("status", "evidence") if prev.get("source") == "auto"} or prev.get("auto_latest")}
    doc["history"].append({"at": _now(), "action": status, "gate": gate, "by": by})
    save(run, doc, override)
    return doc


def decide(run: Path, choice: str, by: str, note: str = "", gates: list[str] | None = None,
           override: Path | None = None) -> dict:
    """사전 공백 결정 — 'ask' 상태 게이트에 사용자 선택을 기록한다. gates를 안 주면 사전 게이트 전체(정본·준비도)."""
    if choice not in ("fill", "skip"):
        raise ValueError("choice는 fill | skip")
    if not by:
        raise ValueError("기록자(--by) 필수 — 결정한 사람")
    doc = load(run, override)
    if doc is None:
        raise ValueError("gates.json 없음 — 먼저 run_gate.py init")
    targets = gates or [g for g in DICT_GATES if doc["gates"][g]["status"] in ("ask", "filling", "skipped")]
    if not targets:
        raise ValueError("결정할 게이트가 없다 — 사전 공백('결정 필요') 상태가 아니다")
    for g in targets:
        if g not in DICT_GATES:
            raise ValueError(f"사전 결정은 {', '.join(DICT_GATES)} 게이트에만 적용된다")
        prev = doc["gates"][g]
        auto = {k: prev.get(k) for k in ("status", "evidence") if prev.get("source") == "auto"} or prev.get("auto_latest")
        if choice == "skip":
            ev = "사용자 선택: 사전을 채우지 않고 진행 — 브랜드 귀속·정본 판정은 잠정" + (f" · {note}" if note else "")
            doc["gates"][g] = {"status": "skipped", "source": "manual", "by": by, "evidence": ev, "at": _now(), "auto_latest": auto}
        else:
            ev = "사용자 선택: 사전 채우기 — 사전을 채운 뒤 run_gate.py check" + (f" · {note}" if note else "")
            doc["gates"][g] = {"status": "filling", "source": "manual", "by": by, "evidence": ev, "at": _now(), "auto_latest": auto}
    doc["history"].append({"at": _now(), "action": f"decide:{choice}", "gates": targets, "by": by})
    save(run, doc, override)
    return doc


def registry_ids() -> set | None:
    return None   # 규칙 등록부는 이 패키지에 없다 — 규칙 ID 검증을 건너뛴다


def record_rules(run: Path, by: str, new: list[str] | None = None, reconfirmed: list[str] | None = None,
                 none_reason: str | None = None, note: str = "", override: Path | None = None) -> dict:
    """분석 종료 시 규칙 회수 (파이프라인 11). 새 규칙은 등록부에 먼저 올린 뒤 그 ID로 기록한다."""
    new, reconfirmed = list(new or []), list(reconfirmed or [])
    if not (new or reconfirmed or (none_reason and none_reason.strip())):
        raise ValueError("새 규칙(--new)·재확인(--reconfirm) ID 또는 새 규칙이 없는 사유(--none) 중 하나는 필수")
    if not by:
        raise ValueError("기록자(--by) 필수")
    ids = registry_ids()
    if ids is not None:
        unknown = [i for i in new + reconfirmed if i not in ids]
        if unknown:
            raise ValueError(f"등록부에 없는 ID: {unknown} — 규칙 등록부에 먼저 올린다")
    doc = load(run, override)
    if doc is None:
        raise ValueError("gates.json 없음 — 먼저 run_gate.py init")
    ev = " · ".join(x for x in (f"새 규칙 {', '.join(new)}" if new else "", f"재확인 {', '.join(reconfirmed)}" if reconfirmed else "",
                                f"새 규칙 없음 — {none_reason}" if none_reason else "", note) if x)
    doc["gates"]["rules"] = {"status": "pass", "source": "manual", "by": by, "evidence": ev, "at": _now(),
                             "new": new, "reconfirmed": reconfirmed, "none_reason": none_reason,
                             "registry_checked": ids is not None}
    doc["history"].append({"at": _now(), "action": "rules", "by": by})
    save(run, doc, override)
    return doc


# ── 판정·배너 ──────────────────────────────────────────────────────────────
def evaluate(doc: dict | None, stage: str = "render") -> dict:
    if doc is None:
        return {"recorded": False, "complete": False, "blocking": [], "ask": [], "waived": [], "skipped": [], "pending_publish": []}
    need = [g for g in GATE_IDS if stage == "publish" or STAGE_OF[g] == "render"]
    blocking = [(g, doc["gates"][g]) for g in need if doc["gates"][g]["status"] not in PASSING]
    waived = [(g, doc["gates"][g]) for g in GATE_IDS if doc["gates"][g]["status"] == "waived"]
    skipped = [(g, doc["gates"][g]) for g in GATE_IDS if doc["gates"][g]["status"] == "skipped"]
    ask = [(g, doc["gates"][g]) for g, r in blocking if r["status"] == "ask"]
    pend_pub = [g for g in GATE_IDS if STAGE_OF[g] == "publish" and doc["gates"][g]["status"] not in PASSING]
    return {"recorded": True, "stage": stage, "complete": not blocking, "blocking": blocking, "ask": ask,
            "waived": waived, "skipped": skipped, "pending_publish": pend_pub}


_BOX = ('<div class="gate-banner" style="margin:12px 0 16px;padding:12px 14px;border-radius:8px;border:1px solid #d9a441;'
        'background:#fff7e6;color:#4a3500;font:14px/1.55 -apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif">')


def banner_html(ev: dict, allow_ungated: bool = False) -> str:
    e = lambda s: html.escape(str(s), quote=False)
    if not ev["recorded"]:
        return (_BOX + "<b>품질 점검 기록 없음</b> — 이 산출물을 만든 분석에는 품질 점검 기록이 없습니다. "
                "예산 승인·기준 데이터 확인·데이터 준비 상태·출처 표기 확인 여부를 산출물만으로는 알 수 없으니 수치를 보수적으로 읽으세요.</div>")
    parts = []
    if ev["blocking"]:
        items = "".join(f"<li>{e(NAMES[g])} — {e(r['status'])}: {e(r.get('evidence', ''))}</li>" for g, r in ev["blocking"])
        head = "품질 점검을 통과하지 못한 초안" if allow_ungated else "품질 점검 미통과"
        parts.append(f"<b>{head}</b> — 아래 항목이 끝나기 전 산출물은 초안이다.<ul style=\"margin:6px 0 0 18px\">{items}</ul>")
    if ev["waived"]:
        items = "".join(f"<li>{e(NAMES[g])} 면제 — {e(r.get('evidence', ''))} ({e(r.get('by', ''))})</li>" for g, r in ev["waived"])
        parts.append(f"<b>면제된 품질 점검</b> — 사유와 함께 공개합니다.<ul style=\"margin:6px 0 0 18px\">{items}</ul>")
    if ev.get("skipped"):
        parts.append("<span style=\"font-size:13px\">브랜드 사전 생략(사용자 선택) — 브랜드 귀속·판정은 잠정</span>")
    if not ev["blocking"] and ev["pending_publish"]:
        parts.append("<span style=\"font-size:13px\">발행 전 남은 확인: "
                     + e(" · ".join(NAMES[g] for g in ev["pending_publish"])) + "</span>")
    return (_BOX + "".join(f"<div>{p}</div>" for p in parts) + "</div>") if parts else ""


def inject(page: str, banner: str) -> str:
    """배너를 <body> 바로 뒤(래퍼 div가 이어지면 그 안)에 넣는다. body가 없으면 맨 앞."""
    if not banner:
        return page
    m = re.search(r"<body[^>]*>\s*(<div class=[\"']?wrap[\"']?[^>]*>)?", page) \
        or re.search(r"<div class=[\"']?wrap[\"']?[^>]*>", page)
    if not m:
        return banner + page
    return page[:m.end()] + banner + page[m.end():]


def command_hint(run: Path) -> str:
    return (f"  python3 lima_agent/skills/lima-agents/scripts/run_gate.py status --run {run}\n"
            f"  (자동 판정 갱신: check · 사람 기록: attest / waive / rules)")


def require_many(runs: dict, allow_ungated: bool = False, stage: str = "render") -> str:
    """여러 run을 묶는 산출물 — 하나라도 미통과면 중단, 배너는 run 이름을 붙여 합친다."""
    out, stop = [], []
    for label, run in runs.items():
        ev = evaluate(load(Path(run)), stage)
        if ev["recorded"] and ev["blocking"] and not allow_ungated:
            stop += [f"  × [{label}] {NAMES[g]}: {r['status']} — {r.get('evidence', '')}" for g, r in ev["blocking"]]
        b = banner_html(ev, allow_ungated)
        if b:
            out.append(b.replace(_BOX, _BOX + f"<div style=\"font-size:12px;opacity:.8\">run: {html.escape(str(label))}</div>", 1))
    if stop:
        raise SystemExit(f"[게이트] {stage} 단계 게이트 미통과 — 중단\n" + "\n".join(stop)
                         + "\n  python3 lima_agent/skills/lima-agents/scripts/run_gate.py status --run <run>\n"
                         "  초안이 꼭 필요하면 --allow-ungated (산출물에 미통과 배너가 들어간다)")
    return "".join(out)


def require_for_render(run: Path | None, allow_ungated: bool = False, override: Path | None = None) -> str:
    """렌더러 공통 진입점 — 배너 HTML을 돌려주거나, render 단계 미통과면 SystemExit."""
    if run is None:
        return (_BOX + "<b>게이트 기록 미연결</b> — 렌더러에 --run(분석 폴더)이 주어지지 않아 게이트 통과 여부를 확인하지 않았다.</div>")
    ev = evaluate(load(run, override), "render")
    if ev["recorded"] and ev["ask"] and not allow_ungated:
        q = next((r.get("question") for _, r in ev["ask"] if r.get("question")), DICT_QUESTION)
        rest = [(g, r) for g, r in ev["blocking"] if r["status"] != "ask"]
        raise SystemExit(f"[게이트] 사용자 결정 필요 — {q}\n"
                         + "\n".join(f"  · {NAMES[g]}: {r.get('evidence', '')}" for g, r in ev["ask"])
                         + f"\n  사용자에게 묻는다(AskUserQuestion). 채우기: 사전 작성 → run_gate.py check --run {run}"
                         + f"\n  건너뛰기: run_gate.py decide --run {run} --choice skip --by <이름>"
                         + ("\n그 밖에 남은 게이트:\n" + "\n".join(f"  × {NAMES[g]}: {r['status']} — {r.get('evidence', '')}" for g, r in rest)
                            if rest else ""))
    if ev["recorded"] and ev["blocking"] and not allow_ungated:
        lines = "\n".join(f"  × {NAMES[g]}: {r['status']} — {r.get('evidence', '')}" for g, r in ev["blocking"])
        raise SystemExit(f"[게이트] 렌더 전 게이트 미통과 — 렌더 중단\n{lines}\n{command_hint(run)}\n"
                         "  초안이 꼭 필요하면 --allow-ungated (산출물에 미통과 배너가 들어간다)")
    return banner_html(ev, allow_ungated)
