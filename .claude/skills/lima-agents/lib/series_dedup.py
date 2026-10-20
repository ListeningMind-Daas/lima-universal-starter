"""같은 검색의 중복 행 판정 — 월별 시계열이 완전히 같은 행은 한 검색으로 센다(표준 라이브러리만).

keyword_info 는 요청하지 않은 표기 변형(띄어쓰기·어순·오타)에 원형과 같은 월별 계열을 복제해 준다. 행마다 더하면
한 검색을 여러 번 센다. 규칙:
  1. 월별 계열(월 × total·gg·nv)이 완전히 같은 행 → 한 묶음, 대표 1행만 센다.
     계열 합계가 MIN_SERIES_TOTAL 미만이면 버킷 반올림으로 무관 키워드가 우연히 같을 수 있다 → 대표와 토큰이 겹치거나
     띄어쓰기 제거 표기가 같을 때만 묶는다.
  2. 계열이 없거나 합계 0 인 행은 묶지 않는다.
  3. 대표 우선순위: 노이즈 아님 > 시드 > 브랜드 태깅됨 > 짧은 표기 > 사전순.
행은 지우지 않고 canonical·is_variant 로 표시만 한다. [추정] 규칙 기반 판정.

mark_gg_shared() — 구글 계열만 같고 네이버 계열이 다른 표기 변형(테블릿·타블릿)은 구글을 한 번만, 네이버는 각자 더한다.
"""
from __future__ import annotations

import re
import unicodedata

MIN_SERIES_TOTAL = 1000   # [가정] 48개월 합계가 이보다 작으면 토큰 겹침을 추가로 요구


def canon(kw: str) -> str:
    """NFKC · 소문자 · 공백 제거 — 띄어쓰기 변형 판정·조인 키."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(kw)).lower())


def tokens(kw: str) -> set:
    """공백 토큰 집합 — 영어 복수형 's' 는 떼고 비교한다."""
    t = re.split(r"\s+", unicodedata.normalize("NFKC", str(kw)).lower().strip())
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in t if w}


def signature(monthly, fields=("total", "gg", "nv")) -> tuple[str, float] | None:
    """monthly_volume 목록 → (계열 서명, total 합계). 계열이 없거나 합계 0 이면 None."""
    rows = sorted((m for m in monthly or [] if m.get("month")), key=lambda m: m["month"])
    if not rows:
        return None
    total = sum(float(m.get("total") or 0) for m in rows)
    if total <= 0:
        return None
    sig = "|".join(m["month"] + ":" + "/".join(repr(float(m.get(f) or 0)) for f in fields) for m in rows)
    return sig, total


def _rank(r: dict):
    return (bool(r.get("is_noise")), not r.get("is_seed"), not r.get("brand"), len(str(r["keyword"])), str(r["keyword"]))


def _group(rows: list[dict], sig_of, min_series_total: int) -> list[list[dict]]:
    buckets: dict[str, list[dict]] = {}
    for r in rows:
        s = sig_of(r)
        if s is not None:
            buckets.setdefault(s[0], []).append(r)
    out = []
    for members in buckets.values():
        if len(members) < 2:
            continue
        strong = sig_of(members[0])[1] >= min_series_total
        members.sort(key=_rank)
        groups: list[tuple[dict, set, str, list]] = []
        for r in members:
            kw = r["keyword"]
            for rep, rtok, rcan, mem in groups:
                if strong or canon(kw) == rcan or (tokens(kw) & rtok):
                    mem.append(r)
                    break
            else:
                groups.append((r, tokens(kw), canon(kw), [r]))
        out += [mem for _, _, _, mem in groups if len(mem) > 1]
    return out


def mark_variants(rows: list[dict], min_series_total: int = MIN_SERIES_TOTAL) -> dict:
    """rows: {keyword, monthly, is_noise, is_seed, brand}. 각 행에 canonical·is_variant 를 채운다. 요약 반환."""
    for r in rows:
        r["canonical"], r["is_variant"] = r["keyword"], False
    groups = _group(rows, lambda r: signature(r.get("monthly")), min_series_total)
    for mem in groups:
        for r in mem[1:]:
            r["canonical"], r["is_variant"] = mem[0]["keyword"], True
    return {"groups": len(groups), "variant_rows": sum(len(m) - 1 for m in groups)}


def mark_gg_shared(rows: list[dict], min_series_total: int = MIN_SERIES_TOTAL) -> dict:
    """대표 행들 중 구글 계열만 같은 묶음 — 대표 외 구성원에 gg_shared_with 를 채운다(구글은 대표만 센다)."""
    for r in rows:
        r["gg_shared_with"] = ""
    live = [r for r in rows if not r.get("is_variant")]

    def gg_sig(r):
        s = signature(r.get("monthly"), fields=("gg",))
        if s is None:
            return None
        gg_total = sum(float(m.get("gg") or 0) for m in r.get("monthly") or [])
        return (s[0], gg_total) if gg_total > 0 else None

    groups = _group(live, gg_sig, min_series_total)
    for mem in groups:
        for r in mem[1:]:
            r["gg_shared_with"] = mem[0]["keyword"]
    return {"groups": len(groups), "gg_shared_rows": sum(len(m) - 1 for m in groups)}
