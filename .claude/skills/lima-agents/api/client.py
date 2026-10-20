"""ListeningMind DaaS API 공통 클라이언트.

- 표준 헤더 (LM-API-KEY)
- 재시도 · 백오프
- 병렬 배치 (max 3 concurrent · API 정책)
"""
from __future__ import annotations

import json
import os
import pathlib
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Iterable

_DEFAULT_BASE_URL = "https://listeningmind-data-api.ascentlab.io"

# 키·주소를 찾는 순서 (Claude Code · Codex · Gemini Enterprise 공통 — 모든 스크립트가 이 함수만 쓴다)
#   ① 환경변수 LM_API_KEY / LM_API_BASE  (Gemini: Secret Manager → 환경변수 주입)
#   ② 워크스페이스 00_Context/.lm-api-key / .lm-api-base  (CWD와 이 모듈 위치에서 위로 올라가며)
#   ③ 사용자 설정 ~/.config/listeningmind/api-key / api-base  (Codex 개인 설치 등 워크스페이스 밖)
# 스킬 폴더 기준 상대경로(SKILLS_ROOT.parent.parent)로 찾지 않는다 — ~/.codex/skills 에 설치되면 엉뚱한 곳을 본다.
KEY_ENV, BASE_ENV = "LM_API_KEY", "LM_API_BASE"
WORKSPACE_KEY, WORKSPACE_BASE = "00_Context/.lm-api-key", "00_Context/.lm-api-base"


def user_config_dir() -> pathlib.Path:
    root = os.environ.get("XDG_CONFIG_HOME", "").strip() or str(pathlib.Path.home() / ".config")
    return pathlib.Path(root) / "listeningmind"


def _search_dirs() -> list[pathlib.Path]:
    cwd = pathlib.Path.cwd()
    here = pathlib.Path(__file__).resolve()
    seen, out = set(), []
    for d in [cwd, *cwd.parents, *here.parents]:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def _read_first_line(f: pathlib.Path) -> str:
    try:
        if f.is_file():
            return f.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return ""


def _lookup(env: str, workspace_rel: str, user_name: str) -> tuple[str, str]:
    """(값, 출처) — 출처는 'env:LM_API_KEY' · 파일 경로 · '' (못 찾음). 값은 로그에 남기지 않는다."""
    v = os.environ.get(env, "").strip()
    if v:
        return v, f"env:{env}"
    for d in _search_dirs():
        f = d / workspace_rel
        v = _read_first_line(f)
        if v:
            return v, str(f)
    f = user_config_dir() / user_name
    v = _read_first_line(f)
    if v:
        return v, str(f)
    return "", ""


class MissingApiKey(RuntimeError):
    pass


def find_api_key() -> tuple[str, str]:
    """(키, 출처). 못 찾으면 ('', '')."""
    return _lookup(KEY_ENV, WORKSPACE_KEY, "api-key")


def resolve_api_key() -> str:
    """키를 찾아 돌려준다. 없으면 설정 방법을 담은 MissingApiKey."""
    key, _ = find_api_key()
    if not key:
        raise MissingApiKey(
            "ListeningMind DaaS API 키가 없습니다 — 터미널에서 직접 실행: "
            "python3 .claude/skills/lima-agents/scripts/setup_key.py "
            f"(또는 환경변수 {KEY_ENV})"
        )
    return key


def _resolve_base_url() -> str:
    """LM_API_BASE env → 00_Context/.lm-api-base → ~/.config/listeningmind/api-base → 기본값(운영 엔드포인트).

    설정 파일은 CWD와 이 모듈 위치의 상위 경로에서 차례로 찾고, 없으면 사용자 설정 폴더를 본다 — 워크스페이스 루트
    밖에서 실행해도 같은 엔드포인트로 해석되게 하기 위함이다. 별도 설정이 없으면
    운영 엔드포인트 기본값을 쓴다.
    """
    base, _ = _lookup(BASE_ENV, WORKSPACE_BASE, "api-base")
    return (base or _DEFAULT_BASE_URL).rstrip("/")


BASE_URL = _resolve_base_url()
MAX_CONCURRENT = 3
DEFAULT_TIMEOUT = 180
# 스킬 경유 호출 표시 (OpenAPI v1.0.13~ 모든 POST 의 선택 파라미터 · 이력 history.is_skills 로 적재 · 서버 기본값 false).
# 이 클라이언트는 스킬에서만 쓰이므로 post() 가 body 에 없으면 true 를 넣는다 — 호출부가 명시한 값은 덮지 않는다
IS_SKILLS = True


class DaasClient:
    def __init__(self, api_key: str | None = None, base_url: str = BASE_URL, timeout: int = DEFAULT_TIMEOUT):
        """api_key 를 생략하면 resolve_api_key() 순서로 찾는다."""
        if api_key is None:
            api_key = resolve_api_key()
        if not api_key:
            raise ValueError("api_key required")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def post(self, endpoint: str, body: dict, retries: int = 2) -> dict:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        if IS_SKILLS and "is_skills" not in body:
            body = {**body, "is_skills": True}
        data = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "LM-API-KEY": self.api_key,
        }
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(url, data=data, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                # 429·5xx 재시도
                if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                    time.sleep(2 ** attempt)
                    last_err = e
                    continue
                raise
            except Exception as e:
                last_err = e
                if attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                raise
        if last_err:
            raise last_err
        raise RuntimeError("unexpected retry loop exit")


    def get(self, endpoint: str, params: dict | None = None, retries: int = 2) -> dict:
        """GET 요청 (쿼리 파라미터) · /usage/summary 등 조회 전용 endpoint용."""
        import urllib.parse
        qs = f"?{urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})}" if params else ""
        url = f"{self.base_url}/{endpoint.lstrip('/')}{qs}"
        headers = {"LM-API-KEY": self.api_key}
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                    time.sleep(2 ** attempt)
                    last_err = e
                    continue
                raise
            except Exception as e:
                last_err = e
                if attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                raise
        if last_err:
            raise last_err
        raise RuntimeError("unexpected retry loop exit")

    def download(self, response: dict, verify: bool = True) -> Any:
        """`response_format=download_url` 응답의 데이터 본문을 받아 JSON 으로 돌려준다 (모든 POST 공통 기능).

        모든 POST 엔드포인트가 `response_format` 을 받는다 — `download_url` 이면 data 대신 `download`
        {download_url, browser_download_url, file_name, sha256, size_bytes, item_count} 만 온다.
        `browser_download_url` 은 인증 없는 GET 이고, 받은 뒤 sha256 을 대조한다(verify=True).
        데이터가 이미 `data` 에 있으면(json 형식) 그대로 돌려준다.
        """
        if response.get("data") is not None or not response.get("download"):
            return response.get("data")
        meta = response["download"]
        url = meta.get("browser_download_url") or meta.get("download_url")
        req = urllib.request.Request(url, headers={"Accept": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read()
        if verify and meta.get("sha256"):
            import hashlib
            got = hashlib.sha256(raw).hexdigest()
            if got != meta["sha256"]:
                raise ValueError(f"download sha256 mismatch: {got} != {meta['sha256']}")
        return json.loads(raw.decode("utf-8"))

    def post_parallel(self, endpoint: str, bodies: Iterable[dict], max_workers: int = MAX_CONCURRENT) -> list[dict]:
        """여러 body를 병렬로 POST · 순서 보존 · 실패는 예외 그대로 전파."""
        bodies_list = list(bodies)
        results: list[Any] = [None] * len(bodies_list)
        errors: list[Exception] = []
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(self.post, endpoint, b): i for i, b in enumerate(bodies_list)}
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    results[idx] = fut.result()
                except Exception as e:
                    errors.append(e)
                    results[idx] = {"result": "ERROR", "reason": str(e)}
        if errors and all(isinstance(r, dict) and r.get("result") == "ERROR" for r in results):
            raise errors[0]
        return results

    def batched_post(
        self,
        endpoint: str,
        items: list,
        make_body: Callable[[list], dict],
        batch_size: int,
        max_workers: int = MAX_CONCURRENT,
    ) -> list[dict]:
        """items를 batch_size로 나눠 · 병렬 POST · 응답 리스트 반환.

        make_body(chunk) → dict · endpoint에 맞는 body 조립기.
        """
        chunks = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
        bodies = [make_body(c) for c in chunks]
        return self.post_parallel(endpoint, bodies, max_workers=max_workers)
