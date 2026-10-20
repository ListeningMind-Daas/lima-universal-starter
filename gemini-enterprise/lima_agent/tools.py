"""Gemini Enterprise(ADK) 에이전트의 도구 — ListeningMind DaaS REST 호출을 크레딧 통제 아래에 둔다.

키: 고객사 GCP Secret Manager → Agent Engine 이 환경변수 LM_API_KEY 로 주입 → lima-agents api.client.resolve_api_key().
    키는 이 모듈·로그·응답 어디에도 쓰지 않는다.

회사 전체가 키 하나를 같이 쓰므로 호출마다 세 겹으로 막는다:
  ① 견적 — 호출 전에 상한 견적(credit_estimate.cost). 견적이 자동 승인 한도(LM_AUTO_APPROVE_CREDITS)를 넘으면
     실행하지 않고 needs_confirmation 을 돌려준다 → 모델이 사용자에게 예상치를 알리고 승인받은 뒤 confirm=True 로 다시 부른다
  ② 세션 예산 — 세션 누적(실소비) + 견적이 세션 예산(LM_SESSION_BUDGET)을 넘으면 거절. 사용자가 명시적으로 올리면
     set_session_budget 으로 관리자 상한(LM_SESSION_BUDGET_MAX)까지 올린다
  ③ 사용 기록 — 실소비(cost_detail.total_cost)·월간 누적(used_credits)을 사용자 ID 와 함께 표준출력 JSON 한 줄로 남긴다
     (Agent Engine 은 표준출력을 Cloud Logging 으로 보낸다 — 누가 얼마나 썼는지 나눠 보는 근거)

큰 응답(cluster_finder 등)은 원본을 세션 아티팩트로 저장하고 모델에는 요약만 돌려준다.
ADK 없이도 import·테스트된다(tool_context 는 state·user_id·save_artifact 만 쓴다).
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

PKG = Path(__file__).resolve().parent


def _skills_dir() -> Path:
    """lima-agents·listeningmind-universal 이 든 폴더 — 배포본은 패키지 안 skills/."""
    env = os.environ.get("LM_SKILLS_DIR", "").strip()
    cands = [Path(env)] if env else []
    cands += [PKG / "skills", *(p / ".claude" / "skills" for p in PKG.parents)]
    for c in cands:
        if (c / "lima-agents/api/client.py").is_file():
            return c
    raise RuntimeError("lima-agents 스킬을 찾지 못했다 — 패키지 손상 또는 LM_SKILLS_DIR 확인")


SKILLS = _skills_dir()
LIMA, UNIV = SKILLS / "lima-agents", SKILLS / "listeningmind-universal"
for _p in (str(LIMA), str(UNIV / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from api import client as lm                                              # noqa: E402
from api import cluster_finder as _cf, intent_finder as _if, keyword_info as _ki   # noqa: E402
from api import path_finder as _pf, serp as _serp, trend_finder as _tf    # noqa: E402
from credit_estimate import cost as _unit_cost                            # noqa: E402


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


AUTO_APPROVE = _env_int("LM_AUTO_APPROVE_CREDITS", 30)       # 이 이하 견적은 확인 없이 실행
SESSION_BUDGET = _env_int("LM_SESSION_BUDGET", 3000)          # 세션 기본 예산
SESSION_BUDGET_MAX = _env_int("LM_SESSION_BUDGET_MAX", 20000)  # 관리자 상한 — 사용자 요청으로도 넘지 못한다
GL_CHOICES = ("kr", "us", "jp")
_SPENT, _BUDGET, _LEDGER = "lm_spent", "lm_budget", "lm_ledger"

_client: lm.DaasClient | None = None


def _get_client() -> lm.DaasClient:
    global _client
    if _client is None:
        _client = lm.DaasClient()          # 키: resolve_api_key() — 배포본은 환경변수 LM_API_KEY
    return _client


# ───────────────────────── 크레딧 통제
def _state(tc) -> dict:
    return tc.state if tc is not None else _LOCAL_STATE


_LOCAL_STATE: dict = {}


def _budget(tc) -> int:
    return int(_state(tc).get(_BUDGET) or SESSION_BUDGET)


def _spent(tc) -> int:
    return int(_state(tc).get(_SPENT) or 0)


def _log(tc, **rec) -> None:
    rec = {"event": "lm_daas_call", "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "user_id": getattr(tc, "user_id", None), "invocation_id": getattr(tc, "invocation_id", None), **rec}
    print(json.dumps(rec, ensure_ascii=False), flush=True)


def _gate(tc, estimate: int, what: str, confirm: bool) -> dict | None:
    """실행해도 되면 None, 아니면 모델에 돌려줄 응답."""
    spent, budget = _spent(tc), _budget(tc)
    if spent + estimate > budget:
        return {"status": "over_budget", "estimate_max": estimate, "session_spent": spent, "session_budget": budget,
                "message": f"{what}: 세션 예산 초과 — 범위(limit·키워드 수)를 줄이거나, 사용자가 명시적으로 원하면 "
                           f"set_session_budget 으로 올린다(관리자 상한 {SESSION_BUDGET_MAX:,})"}
    if estimate > AUTO_APPROVE and not confirm:
        return {"status": "needs_confirmation", "estimate_max": estimate, "session_spent": spent, "session_budget": budget,
                "message": f"{what}: 예상 최대 {estimate:,}크레딧 — 사용자에게 예상치를 알리고 승인을 받은 뒤 "
                           "같은 인자에 confirm=True 로 다시 호출한다. 승인 없이 confirm=True 를 쓰지 않는다"}
    return None


def _record(tc, tool: str, estimate: int, resp: dict) -> dict:
    cost = int((resp.get("cost_detail") or {}).get("total_cost") or 0)
    st = _state(tc)
    st[_SPENT] = _spent(tc) + cost
    ledger = list(st.get(_LEDGER) or [])
    ledger.append({"tool": tool, "estimate_max": estimate, "cost": cost})
    st[_LEDGER] = ledger
    _log(tc, tool=tool, estimate_max=estimate, cost=cost, used_credits=resp.get("used_credits"))
    return {"cost": cost, "session_spent": st[_SPENT], "session_budget": _budget(tc),
            "used_credits_month": resp.get("used_credits"),
            "note": "cost = 이번 호출 실소비 · used_credits_month = 당월 누적 사용량(잔여량 아님)"}


def _call(tc, tool: str, estimate: int, what: str, confirm: bool, fn) -> tuple[dict | None, dict]:
    """(응답, 크레딧 정보) — 막히면 (None, 거절 사유)."""
    blocked = _gate(tc, estimate, what, confirm)
    if blocked:
        return None, blocked
    try:
        resp = fn(_get_client())
    except lm.MissingApiKey as e:
        return None, {"status": "error", "message": f"API 키 미설정 — 관리자가 Secret Manager·배포 설정을 확인해야 한다 ({e})"}
    except Exception as e:                                           # noqa: BLE001
        code = getattr(e, "code", None)
        msg = {401: "키 거절(401) — 관리자에게 키 상태 확인 요청", 403: "권한 없음(403) — 계약 플랜·커넥터 권한 확인",
               429: "호출 한도(429) — 잠시 후 다시"}.get(code, f"{type(e).__name__}: {str(e)[:200]}")
        _log(tc, tool=tool, estimate_max=estimate, cost=None, error=msg)
        return None, {"status": "error", "message": msg}
    if resp.get("result") == "ERROR":
        return None, {"status": "error", "message": str(resp.get("reason") or resp.get("message") or "API 오류")[:300]}
    return resp, _record(tc, tool, estimate, resp)


async def _save_raw(tc, tool: str, resp: dict) -> str | None:
    """원본을 세션 아티팩트로 저장(가능하면). 이름을 돌려준다."""
    if tc is None or not hasattr(tc, "save_artifact"):
        return None
    try:
        from google.genai import types                                   # noqa: PLC0415
        name = f"{tool.replace('/', '_')}-{datetime.datetime.now().strftime('%H%M%S%f')}.json"
        await tc.save_artifact(name, types.Part.from_bytes(
            data=json.dumps(resp, ensure_ascii=False).encode("utf-8"), mime_type="application/json"))
        return name
    except Exception:                                                    # noqa: BLE001  (아티팩트 서비스 없음 — 요약만)
        return None


def _gl(gl: str) -> str:
    gl = (gl or "kr").lower()
    if gl not in GL_CHOICES:
        raise ValueError(f"gl 은 {GL_CHOICES} 중 하나")
    return gl


def _vol(item: dict) -> dict:
    m = item.get("ads_metrics") or {}
    out = {"keyword": item.get("keyword"), "volume_avg": m.get("volume_avg"),
           "google": m.get("gg_volume_avg"), "naver": m.get("nv_volume_avg"),
           "trend": m.get("volume_trend"), "cpc": m.get("cpc"), "competition": m.get("competition_index")}
    if item.get("intents"):
        out["intents"] = item["intents"]
    if item.get("demography"):
        out["demography"] = item["demography"]
    mv = item.get("monthly_volume")
    if isinstance(mv, list) and mv:                     # 배열 순서에 기대지 않고 month 값으로 최신 12개월을 고른다
        out["monthly_volume_last12"] = sorted(mv, key=lambda r: str(r.get("month")))[-12:]
    return {k: v for k, v in out.items() if v is not None}


# ───────────────────────── 도구 (모델이 부른다 — 이름·인자·docstring 이 곧 사용 설명)
async def estimate_credits(calls: list[dict], tool_context=None) -> dict:
    """여러 호출의 크레딧을 실행 전에 견적한다(0크레딧). 분석을 시작하기 전에 계획 전체를 견적해 사용자에게 알린다.

    Args:
        calls: [{"tool": "keyword_info", "keywords": 200, "data_type": "all"},
                {"tool": "intent_finder", "limit": 100}, {"tool": "cluster_finder", "unique_keywords": 300},
                {"tool": "path_finder", "unique_keywords": 50}, {"tool": "serp", "keywords": 3},
                {"tool": "trend_finder", "limit": 20}] — 출력 과금 도구는 상한(limit·unique_keywords) 기준
    """
    rows, total = [], 0
    for c in calls:
        c = dict(c)
        tool = c.pop("tool")
        try:
            n = _unit_cost(tool, **c)
        except (ValueError, TypeError) as e:
            return {"status": "error", "message": f"{tool}: {e}"}
        rows.append({"tool": tool, **c, "credits_max": n})
        total += n
    return {"total_max": total, "rows": rows, "session_spent": _spent(tool_context), "session_budget": _budget(tool_context),
            "auto_approve_under": AUTO_APPROVE,
            "note": "상한 견적 — 실소비는 응답 cost_detail.total_cost 가 유일 기준"}


async def keyword_info(keywords: list[str], gl: str = "kr", data_type: str = "ads_metrics",
                       confirm: bool = False, tool_context=None) -> dict:
    """키워드별 검색량(구글·네이버 합산 월평균)·추세·CPC를 조회한다. data_type="all" 이면 의도(i/n/c/t)·월별 추이·인구통계(kr만)까지.

    Args:
        keywords: 조회할 키워드 목록(최대 1000)
        gl: kr | us | jp
        data_type: ads_metrics(1크레딧/키워드) | ads_info(1 · 월별 추이 포함) | all(10)
        confirm: 견적이 자동 승인 한도를 넘을 때, 사용자 승인을 받은 뒤에만 True
    """
    gl = _gl(gl)
    kws = list(dict.fromkeys(k.strip() for k in keywords if k and k.strip()))[:1000]
    est = _unit_cost("keyword_info", keywords=len(kws), data_type=data_type)
    resp, credit = _call(tool_context, "keyword_info", est, f"keyword_info {len(kws)}개({data_type})", confirm,
                         lambda c: _ki.fetch_batch(c, kws, gl=gl, data_type=data_type))
    if resp is None:
        return credit
    items = [_vol(i) for i in resp.get("data") or []]
    got = {i.get("keyword") for i in items}
    return {"status": "ok", "rows": items, "missing": [k for k in kws if k not in got], "credits": credit,
            "raw_artifact": await _save_raw(tool_context, "keyword_info", resp)}


async def intent_finder(keywords: list[str], gl: str = "kr", limit: int = 100,
                        confirm: bool = False, tool_context=None) -> dict:
    """시드 키워드의 연관 검색어를 검색량 순으로 확장한다(검색량 수치는 없음 — 필요하면 keyword_info 로 조회).

    Args:
        keywords: 시드 키워드(보통 1~3개)
        gl: kr | us | jp
        limit: 반환 수 상한(비용 = 30 + 2 × 반환 수)
        confirm: 사용자 승인 뒤에만 True
    """
    gl, limit = _gl(gl), max(1, min(int(limit), 1000))
    est = _unit_cost("intent_finder", limit=limit)
    resp, credit = _call(tool_context, "intent_finder", est, f"intent_finder limit {limit}", confirm,
                         lambda c: _if.fetch(c, keywords, gl=gl, limit=limit))
    if resp is None:
        return credit
    return {"status": "ok", "keywords": resp.get("data") or [], "credits": credit}


async def cluster_finder(keyword: str, gl: str = "kr", limit: int = 50, hop: int = 2,
                         confirm: bool = False, tool_context=None) -> dict:
    """시드 주변의 동시 검색 관계망을 군집(커뮤니티)으로 묶어 돌려준다 — 시장 지형·인식 군집(CEP) 파악용.

    비용이 크다(150 + 50 × 반환 고유 키워드 수). 기본 limit 50 → 최대 2,700크레딧 · 300이면 15,200 (반환 고유 키워드 상한 limit+1).
    Args:
        keyword: 시드 키워드 1개
        gl: kr | us | jp
        limit: 관계(rels) 수 상한 — 과금 단위인 반환 고유 키워드는 최대 limit+1개. 작게 시작한다
        hop: 1 또는 2
        confirm: 사용자 승인 뒤에만 True
    """
    gl, limit = _gl(gl), max(10, min(int(limit), 5000))
    est = _unit_cost("cluster_finder", unique_keywords=limit + 1)
    resp, credit = _call(tool_context, "cluster_finder", est, f"cluster_finder 관계 상한 {limit}", confirm,
                         lambda c: _cf.fetch(c, keyword, gl=gl, limit=limit, hop=int(hop)))
    if resp is None:
        return credit
    comm = (resp.get("data") or {}).get("communities") or {}
    groups = sorted(((str(k), list(v or [])) for k, v in comm.items()), key=lambda kv: -len(kv[1]))
    return {"status": "ok", "unique_keywords": len(_cf.unique_keywords(resp)),
            "communities": [{"id": k, "size": len(v), "keywords": v[:25]} for k, v in groups[:20]],
            "truncated": len(groups) > 20, "credits": credit,
            "raw_artifact": await _save_raw(tool_context, "cluster_finder", resp)}


async def path_finder(keyword: str, gl: str = "kr", limit: int = 30, time_point: str = "curr",
                      confirm: bool = False, tool_context=None) -> dict:
    """시드 전후로 이어지는 검색 경로(여정)를 돌려준다. 4커넥터 중 가장 비싸다(50 + 40 × 경로 내 고유 키워드).

    여정이 판단에 꼭 필요할 때만 부른다. 세션 인접(같은 검색 세션의 앞뒤)만 잡는다 — 긴 생애 여정은 잡지 못한다.
    Args:
        keyword: 시드 키워드 1개
        gl: kr | us | jp
        limit: 경로 내 고유 키워드 상한 — 기본 30(최대 1,250크레딧)
        time_point: curr | 3m | 6m | 9m | 12m
        confirm: 사용자 승인 뒤에만 True
    """
    gl, limit = _gl(gl), max(5, min(int(limit), 300))
    est = _unit_cost("path_finder", unique_keywords=limit)
    resp, credit = _call(tool_context, "path_finder", est, f"path_finder 키워드 상한 {limit}", confirm,
                         lambda c: _pf.fetch(c, keyword, gl=gl, time_point=time_point, limit=limit))
    if resp is None:
        return credit
    ps = _pf.paths(resp)
    return {"status": "ok", "paths": ps[:40], "n_paths": len(ps), "credits": credit}


async def serp(keyword: str, gl: str = "kr", device: str = "mobile", confirm: bool = False, tool_context=None) -> dict:
    """키워드 1개의 구글 검색결과 화면 — 상위 사이트·연관 질문·연관 검색어·AI 개요 요약. 키워드당 30크레딧.

    Args:
        keyword: 키워드 1개
        gl: kr | us | jp
        device: mobile | desktop
        confirm: 사용자 승인 뒤에만 True
    """
    gl = _gl(gl)
    est = _unit_cost("serp", keywords=1)
    resp, credit = _call(tool_context, "serp", est, "serp 1키워드", confirm,
                         lambda c: _serp.fetch(c, keyword, gl=gl, device=device))
    if resp is None:
        return credit
    org = [{k: o.get(k) for k in ("position", "site_name", "title", "url") if o.get(k) is not None} for o in _serp.organic(resp)[:10]]
    return {"status": "ok", "blocks": _serp.block_counts(resp), "organic": org,
            "questions": _serp.questions(resp)[:10], "related": _serp.related_queries(resp)[:20],
            "ai_overview": _serp.ai_overview_snippets(resp)[:5], "credits": credit}


async def trend_finder(keyword: str, gl: str = "kr", period_days: int = 14, limit: int = 20,
                       confirm: bool = False, tool_context=None) -> dict:
    """시드 주변의 최근 급부상 이슈(요약·출처 링크)를 돌려준다. 50 + 2 × 반환 이슈. 빈 결과는 오류가 아니라 '이슈 없음' 실측.

    구글 기반 인덱스다 — 네이버 비중이 큰 카테고리에서 '국내 이슈 전체'로 단정하지 않는다.
    Args:
        keyword: 시드 키워드
        gl: kr | us | jp
        period_days: 14 → 없으면 90 → 365 로 넓혀 한 번 더
        limit: 반환 상한
        confirm: 사용자 승인 뒤에만 True
    """
    gl, limit = _gl(gl), max(1, min(int(limit), 200))
    est = _unit_cost("trend_finder", limit=limit)
    resp, credit = _call(tool_context, "trend_finder", est, f"trend_finder limit {limit}", confirm,
                         lambda c: _tf.fetch(c, keyword, gl=gl, period_days=int(period_days), limit=limit))
    if resp is None:
        return credit
    its = [{k: i.get(k) for k in ("keyword", "issue_score", "summary", "source_links", "index_date")} for i in _tf.items(resp)]
    return {"status": "ok", "total": resp.get("total"), "items": its, "credits": credit}


async def set_session_budget(credits: int, tool_context=None) -> dict:
    """이 대화(세션)의 크레딧 예산을 바꾼다. **사용자가 숫자를 명시해 요청했을 때만** 부른다 — 모델이 스스로 올리지 않는다.

    Args:
        credits: 새 세션 예산(관리자 상한을 넘으면 상한으로 맞춘다)
    """
    n = max(0, min(int(credits), SESSION_BUDGET_MAX))
    _state(tool_context)[_BUDGET] = n
    _log(tool_context, tool="set_session_budget", budget=n)
    return {"status": "ok", "session_budget": n, "admin_max": SESSION_BUDGET_MAX, "session_spent": _spent(tool_context)}


async def credit_status(tool_context=None) -> dict:
    """이 세션의 크레딧 사용 내역(호출별 견적·실소비)과 예산. 리포트 푸터의 '이번 분석 소진'은 이 합계를 쓴다(0크레딧)."""
    st = _state(tool_context)
    return {"session_spent": _spent(tool_context), "session_budget": _budget(tool_context),
            "auto_approve_under": AUTO_APPROVE, "ledger": list(st.get(_LEDGER) or [])}


_REF_ROOTS = {"lima-agents": LIMA, "listeningmind-universal": UNIV}


async def list_references() -> dict:
    """분석 규칙 문서 목록(0크레딧). 잡 라우팅·질문 프레임·가드레일·커넥터 명세가 여기 있다 — 분석 전에 필요한 문서를 read_reference 로 읽는다."""
    out = {}
    for name, root in _REF_ROOTS.items():
        out[name] = ["SKILL.md", *sorted(str(p.relative_to(root)) for p in (root / "references").glob("*.md"))]
    return out


async def read_reference(skill: str, path: str) -> dict:
    """규칙 문서 하나를 읽는다(0크레딧).

    Args:
        skill: lima-agents | listeningmind-universal
        path: list_references 가 준 상대 경로(예: "references/jobs.md", "SKILL.md")
    """
    root = _REF_ROOTS.get(skill)
    if root is None:
        return {"status": "error", "message": f"skill 은 {list(_REF_ROOTS)} 중 하나"}
    p = (root / path).resolve()
    if not p.is_relative_to(root.resolve()) or p.suffix != ".md" or not p.is_file():
        return {"status": "error", "message": "목록에 있는 .md 문서만 읽는다"}
    text = p.read_text(encoding="utf-8")
    return {"status": "ok", "skill": skill, "path": path, "text": text[:60000], "truncated": len(text) > 60000}


async def render_report(data: dict, tool_context=None) -> dict:
    """리포트 데이터(JSON)를 표준 HTML 리포트로 렌더하고 세션 아티팩트로 저장한다(0크레딧).

    data 키는 read_reference("listeningmind-universal", "references/output-patterns.md")와 렌더러 스키마를 따른다:
    title, owner(필수), kpis, trend, sov, decision, journey, backlog, footer{credits_total, used_credits, guardrails} …
    문구 속 숫자가 계산값과 다르거나 업무 사용자가 못 읽는 작업 용어가 남으면 렌더가 멈춘다 — 메시지대로 고쳐 다시 부른다.
    제목·문장 검토 기록이 없으므로 결과는 '초안' 배너가 붙는다.
    """
    with tempfile.TemporaryDirectory(prefix="lm-render-") as d:
        src, out = Path(d) / "data.json", Path(d) / "report.html"
        src.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, str(UNIV / "scripts/render_report.py"), str(src), "-o", str(out),
                            "--allow-ungated", "--allow-unreviewed"], capture_output=True, text=True, timeout=120)
        if r.returncode != 0 or not out.is_file():
            return {"status": "error", "message": (r.stderr or r.stdout).strip()[-1500:]}
        html = out.read_bytes()
    name = f"{(data.get('title') or 'report')[:40]}-{datetime.date.today().isoformat()}.html".replace("/", "_")
    saved = None
    if tool_context is not None and hasattr(tool_context, "save_artifact"):
        from google.genai import types                                   # noqa: PLC0415
        await tool_context.save_artifact(name, types.Part.from_bytes(data=html, mime_type="text/html"))
        saved = name
    link = _upload_report(name, html)
    return {"status": "ok", "artifact": saved, "url": link, "bytes": len(html), "log": r.stdout.strip()[-500:],
            "note": "초안 — 제목·문장 검토 전" + ("" if link else " · 공유 링크는 LM_REPORT_BUCKET 설정 시 생성")}


def _upload_report(name: str, html: bytes) -> str | None:
    """LM_REPORT_BUCKET 이 있으면 고객 GCS 에 올리고 조직 내부 인증 링크를 돌려준다(공개 링크를 만들지 않는다)."""
    bucket = os.environ.get("LM_REPORT_BUCKET", "").strip()
    if not bucket:
        return None
    try:
        from google.cloud import storage                                 # noqa: PLC0415
        obj = f"lima-reports/{datetime.date.today():%Y/%m}/{name}"
        storage.Client().bucket(bucket).blob(obj).upload_from_string(html, content_type="text/html; charset=utf-8")
        return f"https://storage.cloud.google.com/{bucket}/{obj}"
    except Exception as e:                                               # noqa: BLE001
        print(json.dumps({"event": "lm_report_upload_failed", "error": f"{type(e).__name__}: {str(e)[:200]}"}), flush=True)
        return None


TOOLS = [estimate_credits, list_references, read_reference, keyword_info, intent_finder, cluster_finder,
         path_finder, serp, trend_finder, credit_status, set_session_budget, render_report]
