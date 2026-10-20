"""lima-agents · 분석 실행 · 질문 코드 받아 prepare → template 렌더 → HTML 저장.

Usage:
    python3 scripts/run_analysis.py <CODE> "<CATEGORY>" <GL> <API_KEY>

예:
    python3 scripts/run_analysis.py B-1 "전기자전거" kr D-xxx...

Output:
    ~/Downloads/lima-agents-<CODE>-<CATEGORY_SAFE>-<TS>/report.html
    ~/Downloads/lima-agents-<CODE>-<CATEGORY_SAFE>-<TS>/data.json  (디버그용)
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
REPORTS_ROOT = SKILL_ROOT / "reports"
SHARED_DIR = REPORTS_ROOT / "_shared"

# 질문 코드 → 폴더명 매핑 (신규 추가는 여기)
CODE_TO_FOLDER = {
    "B-1": "b1-segment-intent",
    # 나머지 코드는 준비 되는 대로 추가
}


def safe_name(s: str) -> str:
    return re.sub(r"[^\w가-힣ㄱ-ㅎㅏ-ㅣ]", "_", s.strip())



def _key_arg(v: str | None) -> str:
    """명령줄 키 인자 — 생략하거나 '-' 면 api.client.resolve_api_key() 로 찾는다.
    키를 명령줄에 쓰면 셸 이력·대화 기록에 남는다. 새 사용은 '-' 또는 생략."""
    if v and v != "-":
        return v
    if str(SKILL_ROOT) not in sys.path:
        sys.path.insert(0, str(SKILL_ROOT))
    from api.client import MissingApiKey, resolve_api_key   # noqa: PLC0415
    try:
        return resolve_api_key()
    except MissingApiKey as e:
        print(e, file=sys.stderr)
        sys.exit(3)


def load_prepare_module(folder: str):
    """reports/<folder>/prepare.py를 임포트."""
    prepare_path = REPORTS_ROOT / folder / "prepare.py"
    if not prepare_path.exists():
        raise FileNotFoundError(f"prepare.py 없음 · {prepare_path}")
    # api·lib 임포트를 위해 SKILL_ROOT를 path에 추가
    if str(SKILL_ROOT) not in sys.path:
        sys.path.insert(0, str(SKILL_ROOT))
    spec = importlib.util.spec_from_file_location(f"lima_prepare_{folder}", prepare_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def render_template(folder: str, category: str, gl: str, data: dict) -> str:
    """template.html 로드 · placeholder 치환 · 데이터 주입 · 최종 HTML 반환."""
    tmpl_path = REPORTS_ROOT / folder / "template.html"
    if not tmpl_path.exists():
        raise FileNotFoundError(f"template.html 없음 · {tmpl_path}")
    html = tmpl_path.read_text(encoding="utf-8")

    # placeholder 치환
    html = html.replace("__CATEGORY__", category)
    html = html.replace("__GL__", gl)

    # base.css inline
    base_css = (SHARED_DIR / "base.css").read_text(encoding="utf-8")
    html = html.replace("/* __BASE_CSS_INLINE__ */", base_css)

    # chart-helpers.js inline
    helpers = (SHARED_DIR / "chart-helpers.js").read_text(encoding="utf-8")
    html = html.replace("// __CHART_HELPERS_INLINE__", helpers)

    # 데이터 주입 · JSON → JS literal
    data_js = "const DATA = " + json.dumps(data, ensure_ascii=False) + ";"
    html = _replace_between(
        html,
        "// __DATA_START__",
        "// __DATA_END__",
        data_js,
    )
    return html


def _replace_between(text: str, start_marker: str, end_marker: str, new_content: str) -> str:
    """마커 사이 텍스트 교체 · re.sub의 백슬래시 이스케이프 문제 회피."""
    s = text.index(start_marker)
    e = text.index(end_marker, s + len(start_marker))
    return text[: s + len(start_marker)] + "\n" + new_content + "\n" + text[e:]


def main():
    if len(sys.argv) < 4:
        print("Usage · python3 scripts/run_analysis.py <CODE> \"<CATEGORY>\" <GL>   # 키는 setup_key.py 로 저장한 것을 쓴다")
        sys.exit(1)

    code = sys.argv[1].upper()
    category = sys.argv[2]
    gl = sys.argv[3]
    api_key = _key_arg(sys.argv[4] if len(sys.argv) > 4 else None)

    if code not in CODE_TO_FOLDER:
        available = ", ".join(sorted(CODE_TO_FOLDER.keys()))
        print(f"코드 '{code}' 지원 안 함 · 지원 · {available}")
        sys.exit(2)

    folder = CODE_TO_FOLDER[code]
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    workdir = Path.home() / "Downloads" / f"lima-agents-{code}-{safe_name(category)}-{ts}"
    workdir.mkdir(parents=True, exist_ok=True)

    print(f"[{code}] {category} · {gl} 분석 시작 · workdir · {workdir}")

    # 1. prepare 실행
    prepare_mod = load_prepare_module(folder)
    print("데이터 조회 중 (cluster_finder + keyword_info)...")
    data = prepare_mod.prepare(category, gl, api_key)
    (workdir / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"  · 노드 {data['meta']['total_nodes']} · 태그된 노드 {data['meta']['total_keywords_with_demo']} · 크레딧 {data['meta']['total_credits']:,}")

    # 2. template 렌더
    print("템플릿 렌더 중...")
    html = render_template(folder, category, gl, data)
    report_path = workdir / "report.html"
    report_path.write_text(html, encoding="utf-8")
    print(f"\nOK · {report_path}")
    print(f"파일 크기 · {report_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
