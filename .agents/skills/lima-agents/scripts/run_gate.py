#!/usr/bin/env python3
"""분석 건별 게이트 기록 CLI (run-gates/v1) — 신규 분석이 파이프라인 게이트를 통과했는지 run 폴더에 남긴다. (크레딧 0)

계약: references/run-gates.md · lib/gates.py 머리말 (파이프라인 단계 6 · 6.5 · 7~8 · 9 · 10 · 11)

사용
  init    python3 run_gate.py init   --run <분석 폴더> --vertical <버티컬> --category <품목> [--market kr]
  check   python3 run_gate.py check  --run <분석 폴더> [--no-tests] [--no-canon]    # 자동 판정 갱신
  attest  python3 run_gate.py attest --run <분석 폴더> --gate labels --by <이름> --note "출처 라벨 전수 확인"
  waive   python3 run_gate.py waive  --run <분석 폴더> --gate canon --by <이름> --note "정본 없이 초벌 — 사용자 명시 요청"
  decide  python3 run_gate.py decide --run <분석 폴더> --choice fill|skip --by <이름> [--note "…"]   # 사전 공백 결정
  rules   python3 run_gate.py rules  --run <분석 폴더> --by <이름> [--new <규칙 ID>] [--reconfirm <규칙 ID>] [--none "사유"]
  status  python3 run_gate.py status --run <분석 폴더> [--stage render|publish]   # 종료 코드 0 = 그 단계 완료 · 8 = 미완

종료 코드: 기록 명령(init·check·attest·waive·rules)은 기록 성공이면 0, 입력 오류 2. 완료 여부는 status만 알린다.

게이트: budget(예산 승인) · canon(정본 해석) · data(수집·엔진) · readiness(준비도) · tests(회귀 테스트)
        · labels(출처 라벨 확인) · rules(규칙 회수)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib import gates as G  # noqa: E402


def show(doc: dict | None, stage: str) -> int:
    if doc is None:
        print("gates.json 없음 — run_gate.py init 먼저")
        return 9
    ev = G.evaluate(doc, stage)
    meta = doc.get("meta") or {}
    print(f"게이트 — {meta.get('category', '?')} · {meta.get('vertical', '?')} · {doc.get('run')}")
    mark = {"pass": "  OK ", "waived": "면제", "na": " n/a", "pending": "대기", "fail": "실패",
            "ask": "결정", "filling": "작성중", "skipped": "생략"}
    for gid, name, st_stage, step in G.GATES:
        r = doc["gates"][gid]
        who = f" ({r.get('by')})" if r.get("by") else ""
        print(f"  [{mark.get(r['status'], r['status'])}] {step:>4} {name:<10} {st_stage:<7} {r.get('evidence', '')}{who}")
    print(f"\n{stage} 단계: {'완료' if ev['complete'] else '미완 — ' + ', '.join(G.NAMES[g] for g, _ in ev['blocking'])}")
    if ev.get("ask"):
        q = next((r.get("question") for _, r in ev["ask"] if r.get("question")), G.DICT_QUESTION)
        print(f"\n사용자 결정 필요: {q}\n  채우기 → 사전 작성 후 check · 건너뛰기 → decide --choice skip --by <이름>")
    return 0 if ev["complete"] else 8


def main(argv=None):
    ap = argparse.ArgumentParser(description="분석 건별 게이트 기록")
    sub = ap.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--run", required=True, type=Path)
    common.add_argument("--gates-file", type=Path, help="gates.json 위치를 바꿀 때(테스트용)")
    p = sub.add_parser("init", parents=[common]); p.add_argument("--vertical"); p.add_argument("--category"); p.add_argument("--market", default="kr")
    p = sub.add_parser("check", parents=[common]); p.add_argument("--no-tests", action="store_true"); p.add_argument("--no-canon", action="store_true")
    for name in ("attest", "waive"):
        p = sub.add_parser(name, parents=[common]); p.add_argument("--gate", required=True, choices=G.GATE_IDS)
        p.add_argument("--by", required=True); p.add_argument("--note", required=True)
    p = sub.add_parser("decide", parents=[common]); p.add_argument("--choice", required=True, choices=("fill", "skip"))
    p.add_argument("--by", required=True); p.add_argument("--note", default=""); p.add_argument("--gate", action="append", choices=G.DICT_GATES)
    p = sub.add_parser("rules", parents=[common]); p.add_argument("--by", required=True)
    p.add_argument("--new", nargs="*", default=[]); p.add_argument("--reconfirm", nargs="*", default=[])
    p.add_argument("--none", dest="none_reason"); p.add_argument("--note", default="")
    p = sub.add_parser("status", parents=[common]); p.add_argument("--stage", choices=("render", "publish"), default="publish")
    p.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    try:
        if a.cmd == "init":
            doc = G.init(a.run, a.vertical, a.category, a.market, a.gates_file)
            G.save(a.run, doc, a.gates_file)
            print(f"→ {G.path_for(a.run, a.gates_file)}")
            show(doc, "render")
            return 0
        if a.cmd == "check":
            doc = G.refresh(a.run, a.gates_file, run_tests=not a.no_tests, canon=not a.no_canon)
            show(doc, "render")
            return 0
        if a.cmd in ("attest", "waive"):
            doc = G.attest(a.run, a.gate, "pass" if a.cmd == "attest" else "waived", a.by, a.note, a.gates_file)
            show(doc, "publish")
            return 0
        if a.cmd == "decide":
            doc = G.decide(a.run, a.choice, a.by, a.note, a.gate, a.gates_file)
            show(doc, "render")
            return 0
        if a.cmd == "rules":
            doc = G.record_rules(a.run, a.by, a.new, a.reconfirm, a.none_reason, a.note, a.gates_file)
            if a.reconfirm:
                print(f"※ 재확인한 규칙({', '.join(a.reconfirm)})은 등록부 근거 열에 업권·날짜를 덧붙인다 — "
                      "두 업권이 되면 공통 규칙으로 승격")
            show(doc, "publish")
            return 0
        doc = G.load(a.run, a.gates_file)
        if a.json:
            print(json.dumps({"gates": doc, "evaluation": {k: v for k, v in G.evaluate(doc, a.stage).items()
                                                           if k not in ("blocking", "waived")}}, ensure_ascii=False, indent=1))
            return 0 if G.evaluate(doc, a.stage)["complete"] else 8
        return show(doc, a.stage)
    except ValueError as e:
        print(f"[게이트] {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
