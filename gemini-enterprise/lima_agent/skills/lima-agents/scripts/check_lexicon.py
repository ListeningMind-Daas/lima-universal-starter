#!/usr/bin/env python3
"""산출물 어휘 검사 CLI (lexicon/v1 · 크레딧 0) — 계약: lib/lexicon_check.py 머리말 · references/lexicon-gate.md §6

사용
  python3 check_lexicon.py file <경로>…           # HTML·JSON 산출물
  옵션: --all  과장 표현(경고)까지 출력 · --terms  용어별 집계만 · --strict  겹친 낱말도 실패로
종료 코드: 0 = 작업 용어 없음 · 11 = 있음 · 12 = 겹친 낱말만 있음(--strict) (과장 표현은 경고만)
겹친 낱말('세부 검색어 검색어' — 용어 치환이 이웃 낱말과 겹친 흔적)은 항상 출력한다. 빌더는 렌더 때 이것도 막고,
CLI 기본값은 경고다
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from lib import lexicon_check as LX  # noqa: E402


def scan_file(p: Path) -> list:
    text = p.read_text(encoding="utf8")
    if p.suffix == ".json":
        return LX.scan_json(json.loads(text), str(p))
    return LX.scan_html(text, str(p))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", choices=["file"])
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--terms", action="store_true")
    ap.add_argument("--strict", action="store_true", help="겹친 낱말도 실패(종료 코드 12)")
    a = ap.parse_args(argv)
    hits = [h for p in a.paths for h in scan_file(p.resolve())]
    jar = [h for h in hits if h.kind == "jargon"]
    rpt = [h for h in hits if h.kind == "repeat"]
    if a.terms:
        for (kind, term), n in LX.summarize(hits).items():
            print(f"{n:5d}  {kind:10s} {term}")
    else:
        for h in hits:
            if h.kind in ("jargon", "repeat") or a.all:
                print(f"[{h.kind}] {h.where} — '{h.term}' → {h.plain}\n    …{h.context}…")
    print(f"어휘 검사 — 파일 {len(a.paths)} · 작업 용어 {len(jar)} · 겹친 낱말 {len(rpt)}{'' if a.strict else '(경고)'}"
          f" · 과장 표현(경고) {len(hits) - len(jar) - len(rpt)}")
    return 11 if jar else (12 if rpt and a.strict else 0)


if __name__ == "__main__":
    sys.exit(main())
