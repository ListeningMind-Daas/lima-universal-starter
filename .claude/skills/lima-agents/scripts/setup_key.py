#!/usr/bin/env python3
"""ListeningMind DaaS API 키 설정 — 입력 → 검증 호출 → 저장 (Claude Code · Codex · Gemini 배포 공통).

키는 **사용자가 터미널에서 직접** 입력한다. 대화창·명령줄 인자로 받지 않는다(기록·셸 이력에 남는다).

사용:
  python3 setup_key.py                    # 대화형 입력 (화면에 보이지 않음) → 검증 → 저장
  python3 setup_key.py --scope user       # ~/.config/listeningmind/api-key 에 저장 (워크스페이스 밖 · Codex 개인 설치)
  python3 setup_key.py --base <URL>       # API 주소도 같은 위치에 저장 (키와 그 키를 발급한 서버 주소를 함께 저장한다)
  python3 setup_key.py --stdin            # 표준입력 1줄 (배포 스크립트용 — Gemini: Secret Manager 등록 전 검증)
  python3 setup_key.py --stdin --no-save  # 검증만 하고 저장하지 않는다
  python3 setup_key.py --check            # 이미 설정된 키를 찾아 검증 (출처만 표시, 값은 표시하지 않음)

검증: keyword_info · ads_metrics 1키워드 (약 1크레딧). 응답의 used_credits 는 **당월 누적 사용량**이다(잔여량 아님).
저장 위치(--scope): workspace = <워크스페이스>/00_Context/.lm-api-key · user = ~/.config/listeningmind/api-key
  기본은 현재 폴더에서 위로 00_Context/ 가 보이면 workspace, 아니면 user. 권한 0600.
읽는 순서는 api/client.py find_api_key() — 환경변수 LM_API_KEY 가 있으면 파일보다 먼저 쓰인다.
종료 코드: 0 성공 · 2 키 거절(401/403) · 3 네트워크·서버 오류 · 4 입력 없음 · 5 저장 실패
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import urllib.error
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT))
from api import client as lm                              # noqa: E402

PROBE_KEYWORD, PROBE_GL = "노트북", "kr"
MAX_TRIES = 2          # 온보딩 절차: 2회 실패 시 발급처 문의 안내


def workspace_root() -> Path | None:
    cwd = Path.cwd()
    for d in [cwd, *cwd.parents]:
        if (d / "00_Context").is_dir():
            return d
    return None


def target_paths(scope: str) -> tuple[Path, Path]:
    """(키 파일, 주소 파일)."""
    if scope == "workspace":
        root = workspace_root()
        if root is None:
            raise SystemExit("워크스페이스(00_Context/)를 찾지 못했습니다 — 워크스페이스 루트에서 실행하거나 --scope user")
        return root / lm.WORKSPACE_KEY, root / lm.WORKSPACE_BASE
    d = lm.user_config_dir()
    return d / "api-key", d / "api-base"


def validate(key: str, base: str) -> tuple[int, str, dict]:
    """(코드, 메시지, 응답). 코드 0 성공 · 2 키 거절 · 3 기타 오류."""
    c = lm.DaasClient(key, base_url=base, timeout=60)
    try:
        r = c.post("keyword_info", {"keywords": [PROBE_KEYWORD], "gl": PROBE_GL, "data_type": "ads_metrics"}, retries=1)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return 2, f"키가 거절됐습니다 (HTTP {e.code}) — 오탈자·발급 상태·API 주소({base})를 확인하세요", {}
        return 3, f"서버 오류 (HTTP {e.code}) — 잠시 후 다시 시도하세요", {}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 3, f"연결 실패 ({type(e).__name__}) — 네트워크를 확인하세요. Codex 는 샌드박스 네트워크 허용이 필요합니다", {}
    if r.get("result") == "ERROR":
        return 3, f"API 오류 응답: {r.get('reason') or r.get('message') or '사유 없음'}", r
    return 0, "검증 성공", r


def report(r: dict) -> None:
    cost = (r.get("cost_detail") or {}).get("total_cost")
    used = r.get("used_credits")
    print(f"  · 이번 검증 호출 비용: {cost if cost is not None else '응답에 없음'} 크레딧")
    print(f"  · 월간 누적 사용량(used_credits): {f'{used:,}' if isinstance(used, int) else '응답에 없음'} — 잔여량이 아니다")


def write_private(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(value + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def gitignore_warning(key_file: Path) -> str | None:
    root = workspace_root()
    if root is None or not (root / ".git").exists():
        return None
    gi = root / ".gitignore"
    rel = key_file.relative_to(root).as_posix() if key_file.is_relative_to(root) else None
    if rel and (not gi.is_file() or rel not in gi.read_text(encoding="utf-8").split()):
        return f"⚠ .gitignore 에 {rel} 이 없습니다 — 커밋되지 않도록 추가하세요"
    return None


def read_key(use_stdin: bool, attempt: int) -> str:
    if use_stdin:
        return sys.stdin.readline().strip()
    prompt = "ListeningMind DaaS API 키 (입력은 화면에 보이지 않음): " if attempt == 1 else "다시 입력: "
    return getpass.getpass(prompt).strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ListeningMind DaaS API 키 설정·검증")
    ap.add_argument("--scope", choices=["workspace", "user"], default="")
    ap.add_argument("--base", default="", help="API 주소 — 지정하면 키와 같은 위치에 저장한다")
    ap.add_argument("--stdin", action="store_true", help="키를 표준입력 1줄로 받는다 (재시도 없음)")
    ap.add_argument("--no-save", action="store_true", help="검증만 한다")
    ap.add_argument("--check", action="store_true", help="이미 설정된 키를 찾아 검증한다")
    a = ap.parse_args(argv)

    base = (a.base or lm.BASE_URL).rstrip("/")

    if a.check:
        key, src = lm.find_api_key()
        if not key:
            print("설정된 키가 없습니다 — python3 setup_key.py 로 설정하세요", file=sys.stderr)
            return 4
        print(f"키 출처: {src}\nAPI 주소: {base}")
        code, msg, r = validate(key, base)
        print(("✓ " if code == 0 else "✗ ") + msg)
        if code == 0:
            report(r)
        return code

    scope = a.scope or ("workspace" if workspace_root() else "user")
    key_file, base_file = target_paths(scope)
    tries = 1 if a.stdin else MAX_TRIES
    for attempt in range(1, tries + 1):
        key = read_key(a.stdin, attempt)
        if not key:
            print("입력된 키가 없습니다", file=sys.stderr)
            return 4
        if any(ch.isspace() for ch in key):
            print("키에 공백·줄바꿈이 섞여 있습니다 — 키만 붙여넣으세요", file=sys.stderr)
            if attempt < tries:
                continue
            return 2
        print(f"검증 호출 중 · {base} · keyword_info ads_metrics 1키워드 (약 1크레딧)")
        code, msg, r = validate(key, base)
        if code == 0:
            break
        print("✗ " + msg, file=sys.stderr)
        if code != 2 or attempt == tries:
            if code == 2 and not a.stdin:
                print("  2회 실패 — ListeningMind/Ascent 계약 담당에게 키 발급 상태를 문의하세요", file=sys.stderr)
            return code
    print("✓ " + msg)
    report(r)

    if a.no_save:
        print("저장하지 않았습니다 (--no-save)")
        return 0
    if os.environ.get(lm.KEY_ENV, "").strip():
        print(f"  ※ 환경변수 {lm.KEY_ENV} 가 설정돼 있어 파일보다 먼저 쓰입니다 — 파일 키를 쓰려면 해제하세요")
    try:
        write_private(key_file, key)
        if a.base:
            write_private(base_file, base)
    except OSError as e:
        print(f"저장 실패: {e}", file=sys.stderr)
        return 5
    print(f"저장: {key_file} (권한 600)" + (f" · 주소: {base_file}" if a.base else ""))
    warn = gitignore_warning(key_file)
    if warn:
        print(warn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
