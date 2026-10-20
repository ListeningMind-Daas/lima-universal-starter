#!/usr/bin/env python3
"""(래퍼) G2 시드 게이트 — 판정은 통합 엔진에 위임하고, 엔진이 없으면 동결본으로 폴백한다.

통합 엔진은 스타터에 동봉되지 않으므로
엔진 부재 시 같은 폴더의 _seed_check_legacy.py(v0 동결본)로 폴백한다 — 고객 환경에서도 죽지 않는다.
OSB_ENGINE 환경변수로 엔진 경로를 오버라이드할 수 있다(패키징 테스트용 — 존재하지 않는 경로를 주면 폴백 경로 검증).

API 키 (2026-10-07): 엔진·동결본은 --key <파일>만 받는다. --key 가 없으면 래퍼가 lima-agents
api.client.find_api_key() 순서(LM_API_KEY → 00_Context/.lm-api-key → ~/.config/listeningmind/api-key)로
찾아 넘긴다 — 동결본은 고치지 않는다. 환경변수로 받은 키(Gemini Secret Manager 주입)는 0600 임시 파일로 넘기고 끝나면 지운다.
"""
import os, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = Path(os.environ.get("OSB_ENGINE") or HERE / "_engine_not_bundled")
LEGACY = HERE / "_seed_check_legacy.py"


def _find_key() -> tuple[str, str]:
    """(키, 출처). lima-agents 가 없으면 같은 순서의 내장 탐색."""
    la = HERE.parents[1] / "lima-agents"
    if (la / "api/client.py").is_file():
        sys.path.insert(0, str(la))
        try:
            from api.client import find_api_key        # noqa: PLC0415
            return find_api_key()
        except Exception:                               # noqa: BLE001
            pass
    v = os.environ.get("LM_API_KEY", "").strip()
    if v:
        return v, "env:LM_API_KEY"
    cwd = Path.cwd()
    for d in [cwd, *cwd.parents, *HERE.parents]:
        f = d / "00_Context/.lm-api-key"
        if f.is_file() and f.read_text(encoding="utf8").strip():
            return f.read_text(encoding="utf8").strip(), str(f)
    f = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "listeningmind/api-key"
    if f.is_file() and f.read_text(encoding="utf8").strip():
        return f.read_text(encoding="utf8").strip(), str(f)
    return "", ""


def _run(cmd: list[str]) -> None:
    args = cmd[2:]
    needs_key = not any(a == "--key" or a.startswith("--key=") for a in args) and "--replay" not in args
    if needs_key:
        key, src = _find_key()
        if src and not src.startswith("env:"):
            cmd = [*cmd, "--key", src]
        elif key:                                       # 환경변수 키 → 임시 파일 (execv 를 못 쓰고 끝나면 지운다)
            fd, tmp = tempfile.mkstemp(prefix="lm-key-")
            try:
                with os.fdopen(fd, "w", encoding="utf8") as fh:
                    fh.write(key)
                sys.exit(subprocess.call([*cmd, "--key", tmp]))
            finally:
                os.unlink(tmp)
    os.execv(sys.executable, cmd)


if ENGINE.is_file():
    _run([sys.executable, str(ENGINE), "--skill", "listeningmind-universal", *sys.argv[1:]])
if LEGACY.is_file():                       # 자체완결 폴백 — v0 동결본 (v0 CLI 그대로)
    _run([sys.executable, str(LEGACY), *sys.argv[1:]])
sys.exit("seed_check: 엔진도 동결본도 없음 — 설치 손상. _seed_check_legacy.py 가 있는지 확인")
