#!/usr/bin/env python3
"""ListeningMind DaaS 운영 API 명세(OpenAPI) — 받기 · 축약 · 단가 · 차이 (2026-10-13).

왜: 단가·파라미터가 견적 스크립트와 문서에 복제돼 있어 API가 바뀌면 늦게 반영됐다(2026-08-28 serp 10→30,
2026-10-13 ai_overview 삭제·is_skills 추가). 이제 단가는 이 모듈이 명세에서 읽고, 코드에는 숫자를 두지 않는다.

명세·단가 대조의 기준은 **운영 서버 명세**다(2026-10-13).

  고정 사본  openapi-prod-pinned.json (이 파일 옆) — 오프라인·회귀 테스트·재현의 기준. 매일 감시가 운영과 다르면 알린다
  단가       명세 components 의 *Cost 스키마 기본값 (input_cost·output_cost). keyword_info 처럼 data_type 마다
             스키마가 다르면 data_type 별로 담는다 (KeywordInfoAllCost → all)

사용 (/openapi.json 은 공개·무과금):
  python3 spec.py show                       # 고정 사본 요약
  python3 spec.py diff                       # 운영 명세와 고정 사본 비교 — 다르면 exit 1
  python3 spec.py pin [--date YYYY-MM-DD]    # 운영 명세를 받아 고정 사본을 다시 쓴다
  python3 spec.py pin --from 원본.json --date YYYY-MM-DD   # 저장해 둔 원본으로
라이브러리:
  load("pinned"|"live"|"auto") → 축약 명세 · rate(spec, path, data_type) → (입력 단가, 출력 단가) · diff(a, b) → 차이 목록
  환경변수 LM_API_SPEC 이 load() 의 기본 출처를 정한다 (기본 pinned — 테스트·오프라인이 네트워크에 기대지 않게)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

PROD_URL = "https://listeningmind-data-api.ascentlab.io/openapi.json"
PINNED = Path(__file__).with_name("openapi-prod-pinned.json")
SCHEMA = "lm-openapi-pin/v2"


# ───────────────────────── 축약
def _deref(spec: dict, node: dict | None) -> dict:
    node = node or {}
    seen = 0
    while "$ref" in node and seen < 10:
        o = spec
        for part in node["$ref"].lstrip("#/").split("/"):
            o = o[part]
        node, seen = o, seen + 1
    return node


def _ref_name(node: dict | None) -> str | None:
    ref = (node or {}).get("$ref")
    return ref.rsplit("/", 1)[-1] if ref else None


def _snake(camel: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", camel).lower()


def _costs(spec: dict, op: dict, params: dict) -> dict:
    """200 응답의 cost_detail 이 가리키는 *Cost 스키마 → {키: {input_cost, output_cost, output_unit}}.
    스키마가 하나면 키 '*', 여럿이면 data_type 열거값(KeywordInfoAllCost → all)."""
    resp = _deref(spec, (((op.get("responses") or {}).get("200") or {}).get("content") or {})
                  .get("application/json", {}).get("schema"))
    cd = (resp.get("properties") or {}).get("cost_detail") or {}
    refs = [_ref_name(o) for o in (cd.get("anyOf") or cd.get("oneOf") or [cd])]
    comps = spec.get("components", {}).get("schemas", {})
    table = {}
    for name in refs:
        p = (comps.get(name) or {}).get("properties") or {}
        if not name or "input_cost" not in p:
            continue
        out = p.get("output_cost") or {}
        table[name] = {"input_cost": p["input_cost"].get("default"), "output_cost": out.get("default", 0),
                       "output_unit": " ".join(str(out.get("description") or "").split())}
    if len(table) <= 1:
        return {"*": next(iter(table.values()))} if table else {}
    enum = (params.get("data_type") or {}).get("enum") or []
    by = {}
    for v in enum:
        hits = [n for n in table if _snake(n).endswith("_" + v + "_cost")]
        if hits:
            by[v] = table[max(hits, key=len)]
    return by or {"*": next(iter(table.values()))}


def normalize(spec: dict, pinned_at: str, source: str = PROD_URL) -> dict:
    """원본 OpenAPI → 축약 사본. params 는 요청 본문(application/json) 속성만 — 쿼리 파라미터는 넣지 않는다."""
    out = {"schema": SCHEMA, "info": {k: spec["info"].get(k) for k in ("title", "version")},
           "pinned_at": pinned_at, "source": source, "paths": {}}
    for path, ops in sorted(spec["paths"].items()):
        method, op = next(iter(ops.items()))
        body = _deref(spec, op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema"))
        props = body.get("properties", {}) if body else {}
        params = {k: _deref(spec, v) for k, v in props.items()}
        costs = _costs(spec, op, params)
        entry = {"method": method.upper(), "summary": op.get("summary"), "params": sorted(props),
                 "required": sorted(body.get("required", [])) if body else [],
                 "costs": costs}
        # 하위 호환 · 상한 견적용 — 가장 비싼 변형의 단가 (keyword_info 는 all)
        if costs:
            top = max(costs.values(), key=lambda c: (c["input_cost"] or 0, c["output_cost"] or 0))
            entry["cost"] = {"input_cost": top["input_cost"], "output_cost": top["output_cost"]}
        else:
            entry["cost"] = {}
        enum = {k: v.get("enum") for k, v in params.items() if v.get("enum")}
        if enum:
            entry["enums"] = enum
        out["paths"][path] = entry
    return out


# ───────────────────────── 출처
def fetch(url: str = PROD_URL, timeout: float = 15) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "lm-agent-spec/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def load(source: str | None = None) -> dict:
    """축약 명세. source: pinned(고정 사본) · live(운영 명세를 받아 축약) · auto(live 실패 시 pinned + 경고)."""
    source = source or os.environ.get("LM_API_SPEC", "pinned")
    if source == "pinned":
        return json.loads(PINNED.read_text(encoding="utf8"))
    if source not in ("live", "auto"):
        raise ValueError(f"LM_API_SPEC={source!r} — pinned · live · auto")
    try:
        return normalize(fetch(), _dt.date.today().isoformat())
    except Exception as e:          # noqa: BLE001 — 네트워크·파싱 실패 모두 같은 처리
        if source == "live":
            raise
        pin = json.loads(PINNED.read_text(encoding="utf8"))
        print(f"[spec] 운영 명세를 받지 못해 고정 사본({pin['info']['version']} · {pin['pinned_at']})으로 견적한다 — {e}",
              file=sys.stderr)
        return pin


_CACHE: dict = {}


def default() -> dict:
    """프로세스 안에서 한 번만 읽는 기본 명세 (LM_API_SPEC)."""
    key = os.environ.get("LM_API_SPEC", "pinned")
    if key not in _CACHE:
        _CACHE[key] = load(key)
    return _CACHE[key]


def rate(spec: dict, path: str, data_type: str | None = None) -> tuple[int, int]:
    """(입력 단가, 출력 단가). 명세에 없는 경로나 단가 없는 경로는 ValueError — 견적에 지어낸 숫자를 넣지 않는다."""
    entry = spec["paths"].get(path)
    if entry is None:
        raise ValueError(f"{path} — 운영 명세({spec['info']['version']})에 없는 엔드포인트")
    costs = entry.get("costs") or {}
    if not costs:
        raise ValueError(f"{path} — 명세에 단가가 없다")
    if "*" in costs:
        c = costs["*"]
    else:
        if data_type is None:
            raise ValueError(f"{path} — data_type 별 단가라 data_type 이 필요하다: {sorted(costs)}")
        if data_type not in costs:
            raise ValueError(f"{path} — data_type {data_type!r} 의 단가가 명세에 없다: {sorted(costs)}")
        c = costs[data_type]
    return int(c["input_cost"] or 0), int(c["output_cost"] or 0)


# ───────────────────────── 차이
def diff(old: dict, new: dict) -> list[str]:
    """두 축약 명세의 차이 — 판 번호 · 엔드포인트 추가/삭제 · 파라미터 · 필수 · 단가."""
    out = []
    if old["info"].get("version") != new["info"].get("version"):
        out.append(f"판 {old['info'].get('version')} → {new['info'].get('version')}")
    a, b = old["paths"], new["paths"]
    for p in sorted(set(b) - set(a)):
        out.append(f"+ 엔드포인트 {p}")
    for p in sorted(set(a) - set(b)):
        out.append(f"- 엔드포인트 {p}")
    for p in sorted(set(a) & set(b)):
        x, y = a[p], b[p]
        add, rem = sorted(set(y["params"]) - set(x["params"])), sorted(set(x["params"]) - set(y["params"]))
        if add or rem:
            out.append(f"~ 파라미터 {p} +{add} -{rem}")
        if x.get("required", []) != y.get("required", []):
            out.append(f"~ 필수 {p} {x.get('required')} → {y.get('required')}")
        cx, cy = x.get("costs", {}), y.get("costs", {})
        for k in sorted(set(cx) | set(cy)):
            ox = {f: (cx.get(k) or {}).get(f) for f in ("input_cost", "output_cost")}
            oy = {f: (cy.get(k) or {}).get(f) for f in ("input_cost", "output_cost")}
            if ox != oy:
                out.append(f"~ 단가 {p}[{k}] {ox} → {oy}")
    return out


# ───────────────────────── CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show")
    d = sub.add_parser("diff"); d.add_argument("--from", dest="src", help="저장한 원본 OpenAPI (없으면 운영에서 받는다)")
    p = sub.add_parser("pin"); p.add_argument("--from", dest="src"); p.add_argument("--date", default=_dt.date.today().isoformat())
    a = ap.parse_args(argv)

    if a.cmd == "show":
        s = load("pinned")
        print(f"{s['info']['title']} {s['info']['version']} · 고정 {s['pinned_at']} · {s['source']}")
        for path, e in s["paths"].items():
            cs = " · ".join(f"{k}:{c['input_cost']}+{c['output_cost']}" for k, c in (e.get("costs") or {}).items()) or "단가 없음"
            print(f"  {e['method']:5} {path:32} {cs}")
        return 0
    raw = json.loads(Path(a.src).read_text(encoding="utf8")) if a.src else fetch()
    if a.cmd == "pin":
        PINNED.write_text(json.dumps(normalize(raw, a.date), ensure_ascii=False, indent=1) + "\n", encoding="utf8")
        print(f"고정 사본 갱신 — {raw['info']['version']} · {a.date} → {PINNED.name}")
        return 0
    old, new = load("pinned"), normalize(raw, _dt.date.today().isoformat())
    changes = diff(old, new)
    if not changes:
        print(f"차이 없음 — 운영 {new['info']['version']} = 고정 사본 ({old['pinned_at']})")
        return 0
    print(f"운영 명세가 고정 사본({old['info']['version']} · {old['pinned_at']})과 다르다 — 래퍼·커넥터 문서·고정 사본을 갱신한다")
    for c in changes:
        print("  " + c)
    return 1


if __name__ == "__main__":
    sys.exit(main())
