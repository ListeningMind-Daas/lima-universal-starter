"""lima-agents · Explorer 실행 · cluster-explorer 인터랙티브 HTML 생성.

Usage:
    (신규 조회)
    python3 scripts/run_explorer.py "<CATEGORY>" <GL> <API_KEY>

    (재렌더 · 기존 cluster_data.json 재사용 · CEP·엔티티 병합 후)
    python3 scripts/run_explorer.py --rerender <WORKDIR>
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import datetime
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
EXPLORERS_ROOT = SKILL_ROOT / "explorers"
DEFAULT_EXPLORER = "cluster-explorer"


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


def load_prepare(folder: str):
    prepare_path = EXPLORERS_ROOT / folder / "prepare.py"
    if not prepare_path.exists():
        raise FileNotFoundError(f"prepare.py 없음 · {prepare_path}")
    if str(SKILL_ROOT) not in sys.path:
        sys.path.insert(0, str(SKILL_ROOT))
    spec = importlib.util.spec_from_file_location(f"lima_explorer_{folder}", prepare_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def _replace_between(text: str, start: str, end: str, new: str) -> str:
    s = text.index(start)
    e = text.index(end, s + len(start))
    return text[: s + len(start)] + "\n" + new + "\n" + text[e:]


def _escape_for_script(json_text: str) -> str:
    """shell script 안 srcdoc JSON을 위한 이스케이프 · 브라우저의 </script> 감지 회피."""
    return (
        json_text.replace("</", "<\\/")
        .replace("<!--", "<\\!--")
        .replace("-->", "--\\>")
    )


def _concat_js_modules(js_dir: Path) -> str:
    """js/ 폴더의 모든 .js 파일을 이름 순으로 concat.

    파일명 · `01-*.js` `02-*.js` ... 순서 · zero-padded prefix로 실행 순서 보장.
    """
    if not js_dir.is_dir():
        return ""
    files = sorted(p for p in js_dir.iterdir() if p.suffix == ".js")
    parts = []
    for f in files:
        parts.append(f"\n// ===== {f.name} =====\n")
        parts.append(f.read_text(encoding="utf-8"))
    return "".join(parts)


def render_inner(folder: str, category: str, gl: str, cluster_data: dict) -> str:
    render_dir = EXPLORERS_ROOT / folder / "_shared/render"
    inner_path = render_dir / "inner-template.html"
    tmpl = inner_path.read_text(encoding="utf-8")
    tmpl = tmpl.replace("__CATEGORY__", category)
    tmpl = tmpl.replace("__GL__", gl)
    tmpl = tmpl.replace("__NODE_COUNT__", str(len(cluster_data.get("nodes", []))))
    tmpl = tmpl.replace("__CLUSTER_COUNT__", str(len(cluster_data.get("communities", {}))))
    tmpl = tmpl.replace("__HUB_COUNT__", str(len(cluster_data.get("hub_keywords", []))))
    tmpl = tmpl.replace("__ORIENTATION__", "UNDIRECTED")
    tmpl = tmpl.replace("__HOP__", "2")
    tmpl = tmpl.replace("__SEED1__", category)
    # CLUSTER_DATA 주입
    cd_for_ui = {k: v for k, v in cluster_data.items() if not k.startswith("_")}
    data_js = "const CLUSTER_DATA = " + json.dumps(cd_for_ui, ensure_ascii=False) + ";"
    tmpl = _replace_between(tmpl, "// __DATA_START__", "// __DATA_END__", data_js)
    # JS 모듈 concat 후 · __JS_MODULES__ 마커 대체
    js_modules = _concat_js_modules(render_dir / "js")
    tmpl = tmpl.replace("// __JS_MODULES__", js_modules)
    return tmpl


def render_shell(folder: str, category: str, gl: str, inner_html: str, meta: dict) -> str:
    shell_path = EXPLORERS_ROOT / folder / "_shared/render/shell.html"
    shell = shell_path.read_text(encoding="utf-8")
    sessions = [{
        "seed": category,
        "seed_index": 1,
        "meta": {
            "gl": gl,
            "hop": 2,
            "orientation": "UNDIRECTED",
            "nodes": meta.get("total_nodes", 0),
            "clusters": len(meta.get("_communities_count") or []) if False else 0,
            "credits": meta.get("total_credits", 0),
        },
        "srcdoc": inner_html,
    }]
    sessions_json = json.dumps(sessions, ensure_ascii=False)
    sessions_safe = _escape_for_script(sessions_json)
    shell_js = (
        "const CLUSTER_SESSIONS = " + sessions_safe + ";\n"
        "let ACTIVE_SESSION_IDX = 0;"
    )
    return _replace_between(shell, "// __SHELL_DATA_START__", "// __SHELL_DATA_END__", shell_js)


def _do_render(workdir: Path, folder: str, category: str, gl: str, cluster_data: dict) -> Path:
    (workdir / "cluster_data.json").write_text(
        json.dumps(cluster_data, ensure_ascii=False, indent=2)
    )
    meta = cluster_data.get("_meta", {})
    inner_html = render_inner(folder, category, gl, cluster_data)
    final_html = render_shell(folder, category, gl, inner_html, {
        "total_nodes": meta.get("total_nodes", 0),
        "total_credits": meta.get("total_credits", 0),
    })
    out_path = workdir / "explorer.html"
    out_path.write_text(final_html, encoding="utf-8")
    return out_path


def cmd_rerender(workdir_path: str):
    """기존 workdir의 cluster_data.json을 다시 읽어서 explorer.html 재렌더.

    Claude가 CEP·엔티티를 대화 안에서 조립한 뒤 · cluster_data.json에 병합 저장하고 이 명령을 실행.
    """
    workdir = Path(workdir_path).expanduser().resolve()
    if not workdir.is_dir():
        print(f"WORKDIR 없음 · {workdir}")
        sys.exit(2)
    data_path = workdir / "cluster_data.json"
    if not data_path.exists():
        print(f"cluster_data.json 없음 · {data_path}")
        sys.exit(2)
    cluster_data = json.loads(data_path.read_text(encoding="utf-8"))
    meta = cluster_data.get("_meta", {})
    category = meta.get("category") or "unknown"
    gl = meta.get("gl") or "kr"
    folder = DEFAULT_EXPLORER

    print(f"[rerender] {category} · {gl} · workdir · {workdir}")
    # 재렌더에는 prepare 모듈이 필요 없지만 · 파일 경로만 사용
    out_path = _do_render(workdir, folder, category, gl, cluster_data)
    print(f"OK · {out_path}")
    print(f"파일 크기 · {out_path.stat().st_size:,} bytes")


def main():
    # 재렌더 모드
    if len(sys.argv) >= 3 and sys.argv[1] == "--rerender":
        cmd_rerender(sys.argv[2])
        return

    if len(sys.argv) < 3:
        print("Usage:")
        print("  python3 scripts/run_explorer.py \"<CATEGORY>\" <GL> [- [<EXPLORER_FOLDER>]]   # 키는 setup_key.py 로 저장한 것을 쓴다")
        print("  python3 scripts/run_explorer.py --rerender <WORKDIR>")
        sys.exit(1)

    category = sys.argv[1]
    gl = sys.argv[2]
    api_key = _key_arg(sys.argv[3] if len(sys.argv) > 3 else None)
    folder = sys.argv[4] if len(sys.argv) > 4 else DEFAULT_EXPLORER

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    workdir = Path.home() / "Downloads" / f"lima-agents-explorer-{safe_name(category)}-{ts}"
    workdir.mkdir(parents=True, exist_ok=True)

    print(f"[explorer:{folder}] {category} · {gl} · workdir · {workdir}")

    prepare_mod = load_prepare(folder)
    print("데이터 조회 중 (cluster_finder + keyword_info)...")
    cluster_data = prepare_mod.prepare(category, gl, api_key)
    meta = cluster_data.get("_meta", {})
    print(f"  · 노드 {meta.get('total_nodes', 0)} · 크레딧 {meta.get('total_credits', 0):,}")

    print("렌더 중 (inner + shell)...")
    out_path = _do_render(workdir, folder, category, gl, cluster_data)
    print(f"\nOK · {out_path}")
    print(f"파일 크기 · {out_path.stat().st_size:,} bytes")
    print(f"\n다음 · CEP·엔티티 조립 필요하면 · cluster_data.json 편집 후:")
    print(f"  python3 scripts/run_explorer.py --rerender {workdir}")


if __name__ == "__main__":
    main()
