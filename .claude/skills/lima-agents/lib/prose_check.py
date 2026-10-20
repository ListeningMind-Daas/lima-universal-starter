"""작성 문구 숫자 대조 — 설정·리포트에 사람이 쓴 숫자가 계산 결과에 있는 값인지 렌더 전에 확인한다.

왜: 리포트 설명문에 옮겨 적은 수치는 사전·계산이 바뀌면 재계산 값과 어긋나고,
저장되지 않은 임시 계산 값이 섞이기 쉽다. 숫자를 문장에 옮겨 적는
순간 계산과 끊어진다. 이 모듈은 문장 속 숫자를 계산 데이터와 대조해 끊어진 숫자를 찾는다.

대조 방식 (문맥이 있을수록 엄격하게)
  브랜드와 붙은 숫자 '브랜드A(46)' · '브랜드B 186' · '46개가 브랜드A' → (브랜드, 수) 짝이 데이터에 있어야 한다
  'N개 중 M개/M%'  '400개 중 120개' · '300개 중 15%'        → (전체, 부분) 짝이 같은 망·같은 여정에 있어야 한다
  'M%(A/B)'        '15%(60/400)'                              → (B, A) 짝
  그 밖의 숫자     '12,345건' · '56%'                         → 데이터 어딘가에 있는 값이어야 한다(약한 검사)
건너뛰는 숫자: 날짜(2026-09-17) · 영문·숫자 모델명(X10·m1·a1·2in1) · 단위가 규격인 수(10인치·3세대·20대) · 허용 목록.

한계: '그 밖의 숫자'는 값 존재만 본다 — 다른 자리의 같은 값과 우연히 맞으면 통과한다. 문맥 패턴에 맞춰 쓰면 검사가 엄격해진다.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

norm = lambda s: re.sub(r"\s+", "", str(s)).lower()
_num = lambda s: int(s.replace(",", ""))

SKIP_UNITS = ("인치", "세대", "대 ", "대)", "대·", "대 ", "년", "월", "일", "시간", "분", "만원", "원", "위", "차", "주", "배", "회", "hz", "gb", "kg", "g ")
NUM = r"\d{1,3}(?:,\d{3})+|\d+"


@dataclass
class Facts:
    ints: set = field(default_factory=set)
    pcts: set = field(default_factory=set)
    pairs: set = field(default_factory=set)      # (norm 이름, int)
    ratios: set = field(default_factory=set)     # (전체, 부분 int 또는 ('%', int))
    names: set = field(default_factory=set)      # 짝 이름(norm) — 문장에서 이 이름 바로 뒤 숫자는 짝으로 대조한다
    seeds: dict = field(default_factory=dict)    # 관계망 시드(norm) → 질의 수 — 파생 선언에서 '관계망:시드'로 부른다
    sigs: set = field(default_factory=set)       # 관계망 서명 (브랜드 비율 %, 브랜드 norm, 건수) — '40%(브랜드A 120)'

    def add_pair(self, name, v):
        for nm in {norm(name), norm(re.sub(r"\(.*?\)", "", str(name)))}:   # '<라인>(일반 라인)'은 '<라인>'으로도 부른다
            if nm:
                self.pairs.add((nm, int(v))); self.names.add(nm)

    def add_int(self, v):
        if isinstance(v, bool):
            return
        if isinstance(v, int):
            self.ints.add(v)
        elif isinstance(v, float):
            if 0 <= v <= 1:
                self.pcts.add(round(v * 100))
            if v.is_integer():
                self.ints.add(int(v))
            elif v > 1:                                  # 여성 54.3 → '54%'
                self.ints.add(round(v)); self.pcts.add(round(v))


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def collect(obj, facts: Facts | None = None) -> Facts:
    """계산 데이터(JSON 호환 구조)에서 수·짝·비율을 모은다."""
    f = facts or Facts()
    if _is_num(obj):
        f.add_int(obj)
    elif isinstance(obj, list):
        if len(obj) == 2 and isinstance(obj[0], str) and _is_num(obj[1]):
            f.add_int(obj[1])
            if isinstance(obj[1], int) or float(obj[1]).is_integer():
                f.add_pair(obj[0], obj[1])
        else:
            for x in obj:
                collect(x, f)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if _is_num(v) and not isinstance(v, bool) and float(v).is_integer():
                f.add_pair(k, v)
            elif isinstance(v, dict) and isinstance(v.get("volume_sum"), int):
                f.add_pair(k, v["volume_sum"])            # {'<라인>': {volume_sum: 5229}}
            collect(v, f)
        name = obj.get("brand") or obj.get("name")
        if isinstance(obj.get("vol"), int):
            for key in ("short", "label"):                  # 상황 이름 — '<상황>(12,345)'
                if isinstance(obj.get(key), str):
                    f.add_pair(obj[key], obj["vol"])
        if isinstance(obj.get("seed"), str) and isinstance(obj.get("nodes"), int):
            f.add_pair(obj["seed"], obj["nodes"])        # 관계망 시드 → 질의 수
            f.seeds[norm(obj["seed"])] = obj["nodes"]
        if isinstance(obj.get("volume_sum"), int):
            for key in ("id", "family", "label"):           # 허브·가설 id·계열명('고장·수명')으로 부를 수 있게
                if isinstance(obj.get(key), str):
                    f.add_pair(obj[key], obj["volume_sum"])
        if isinstance(name, str):
            for key in ("n", "total"):
                if isinstance(obj.get(key), int):
                    f.add_pair(name, obj[key])
        if isinstance(obj.get("nodes"), int):
            n = obj["nodes"]
            for key in ("brandNodes", "brand_nodes"):
                if isinstance(obj.get(key), int):
                    f.ratios.add((n, obj[key]))
            for key in ("brandShare", "brand_share", "communityShare", "community_share"):
                if _is_num(obj.get(key)):
                    f.ratios.add((n, ("%", round(obj[key] * 100))))
            bs = obj.get("brands") or []
            bitems = bs.items() if isinstance(bs, dict) else [tuple(b) for b in bs if isinstance(b, list) and len(b) == 2]
            share = next((obj[k] for k in ("brandShare", "brand_share") if _is_num(obj.get(k))), None)
            for bn, bv in bitems:
                if isinstance(bv, int):
                    f.ratios.add((n, bv))
                    if share is not None:
                        f.sigs.add((round(share * 100), norm(bn), bv))
        if isinstance(obj.get("requests"), int) and isinstance(obj.get("rematched"), int):   # 요청 N건 중 재매칭 M건
            f.ratios.add((obj["requests"], obj["rematched"]))
        if isinstance(obj.get("pathN"), int) and isinstance(obj.get("brandPathN"), int):
            f.ratios.add((obj["pathN"], obj["brandPathN"]))
    return f


def keyword_facts(run: Path, decl: dict, facts: Facts) -> list[str]:
    """설정에 선언한 외부 실측값 — {raw 파일: [검색어…]}. 파일에서 값을 읽어 사실로 더한다(문구에 적은 값이 아니라 원자료 값)."""
    errs = []
    for rel, kws in (decl or {}).items():
        p = Path(run) / rel
        if not p.exists():
            errs.append(f"선언한 원자료 없음: {rel}")
            continue
        idx = {}
        for it in (json.loads(p.read_text(encoding="utf8")).get("data") or []):
            if isinstance(it, dict) and "keyword" in it:
                idx[norm(it["keyword"])] = (it.get("ads_metrics") or {}).get("volume_avg")
        for kw in kws:
            v = idx.get(norm(kw))
            if v is None:
                errs.append(f"선언한 검색어가 원자료에 없거나 미측정: {kw} ({rel})")
                continue
            facts.ints.add(v); facts.add_pair(kw, v)
    return errs


_PH = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


def fill(text: str, values: dict) -> tuple[str, list[str]]:
    """{{이름}} 자리표시자를 계산값으로 채운다. 모르는 이름은 되돌려 준다."""
    missing = []

    def rep(m):
        k = m.group(1)
        if k not in values:
            missing.append(k)
            return m.group(0)
        return str(values[k])
    return _PH.sub(rep, text), missing


def _strip(text: str) -> str:
    t = re.sub(r"<code>.*?</code>", " ", text or "")
    t = re.sub(r"</?(td|th|tr|li|p|div|br|ul|ol|table|thead|tbody|h\d)[^>]*>", " · ", t)   # 칸·줄 경계 — 숫자가 붙지 않게
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"\b\d{8}-\S+", " ", t)                    # run 폴더명(YYYYMMDD-<품목>-kr-cepfinder)
    return re.sub(r"\d{4}-\d{2}(?:-\d{2})?", " ", t)


def check(text: str, facts: Facts, brands: set[str] | None = None, allow: set[int] | None = None) -> list[str]:
    """문구 한 덩어리의 숫자를 대조해 문제 목록을 돌려준다."""
    t = _strip(text)
    allow = allow or set()
    issues, used = [], set()
    ctx = lambda m: "…" + t[max(0, m.start() - 18):m.end() + 12].replace("\n", " ") + "…"
    bnames = sorted({norm(b) for b in (brands or set())}, key=len, reverse=True)

    # 1) 'N개 중 M개/M%'
    for m in re.finditer(rf"({NUM})\s*(?:개|질의|건|경로)(?:의)?\s*중\s*({NUM})\s*(%|개|건)", t):
        tot, part, unit = _num(m.group(1)), _num(m.group(2)), m.group(3)
        key = (tot, ("%", part)) if unit == "%" else (tot, part)
        if key not in facts.ratios:
            issues.append(f"'{m.group(0)}' — 전체 {tot:,} 중 {part:,}{'%' if unit == '%' else ''} 짝이 계산값에 없음 {ctx(m)}")
        used.update({m.start(1), m.start(2)})
    # 1b) 'N질의의 M%' · 'N개 질의에서도 브랜드 비중 M%' — 같은 관계망의 브랜드·커뮤니티 비율
    # 2026-09-17 화면 표기를 '검색어 N개'로 바꿨다 — 'N질의'와 같은 뜻으로 읽는다
    for m in re.finditer(rf"(?:({NUM})\s*(?:개\s*)?질의|검색어\s*\(?({NUM})\s*개\)?)[^0-9%]{{0,16}}?(\d+)\s*%", t):
        g = 1 if m.group(1) else 2
        tot, pc = _num(m.group(g)), int(m.group(3))
        if (tot, ("%", pc)) not in facts.ratios:
            issues.append(f"'{m.group(0)}' — 검색어 {tot:,}개 망의 {pc}% 비율이 계산값에 없음 {ctx(m)}")
        used.update({m.start(g), m.start(3)})
    # 1c) 'M%(브랜드A N)' · 'M% 중 브랜드A N' · 'M%에 브랜드A가 N' — 비율과 브랜드 건수가 같은 망에서 나와야 한다
    if bnames:
        alt_ = "|".join(re.escape(b) for b in bnames)
        for m in re.finditer(rf"(\d+)\s*%\s*(?:\(|중|에|이고 그중)\s*(?:<[^>]+>)?\s*({alt_})(?:가|이)?\s*({NUM})", t, re.I):
            pc, b, n = int(m.group(1)), norm(m.group(2)), _num(m.group(3))
            if (pc, b, n) not in facts.sigs and n not in allow:
                issues.append(f"'{m.group(0)}' — 브랜드 비율 {pc}%·{m.group(2)} {n:,}인 관계망이 계산값에 없음 {ctx(m)}")
            used.update({m.start(1), m.start(3)})
    # 2) 'M%(A/B)'
    for m in re.finditer(rf"\(({NUM})/({NUM})\)", t):
        if (_num(m.group(2)), _num(m.group(1))) not in facts.ratios:
            issues.append(f"'{m.group(0)}' — {m.group(2)} 중 {m.group(1)} 짝이 계산값에 없음 {ctx(m)}")
        used.update({m.start(1), m.start(2)})
    # 3) 브랜드 뒤 숫자
    if bnames:
        alt = "|".join(re.escape(b) for b in bnames)
        for m in re.finditer(rf"({alt})(?:가|이|는|은)?\s*\(?\s*({NUM})(?![\d,.]|\s*%|\s*인치|\s*세대|강|위|등|차|\s*경로)", t, re.I):
            if m.start(2) in used:
                continue
            n = _num(m.group(2))
            quoted = t[max(0, m.start() - 1):m.start()] in ("'", "‘", "\"", "“")
            if quoted and any(nm_ == n and norm(m.group(1)) in nm for nm, nm_ in facts.pairs):
                used.add(m.start(2)); continue           # "'브랜드A' 16"은 여정 노드 약칭 — 그 브랜드를 담은 노드 값이면 인정
            if n >= 1000 and any(v_ == n and nm.startswith(norm(m.group(1))) for nm, v_ in facts.pairs):
                used.add(m.start(2)); continue           # '브랜드 N' = '브랜드+품목어' 검색량. 관계망 건수 같은 작은 수는 엄격히 본다
            if (norm(m.group(1)), n) not in facts.pairs and n not in allow:
                issues.append(f"'{m.group(0).strip()}' — ({m.group(1)}, {n:,}) 짝이 계산값에 없음 {ctx(m)}")
            used.add(m.start(2))
    # 3b) 'N개가 브랜드' — '그중 40개가 브랜드A'
    if bnames:
        for m in re.finditer(rf"({NUM})\s*(?:개|건|질의)(?:가|이|는|은)?\s*(?:<[^>]+>)?\s*({alt})", t, re.I):
            if m.start(1) in used:
                continue
            n = _num(m.group(1))
            if (norm(m.group(2)), n) not in facts.pairs and n not in allow:
                issues.append(f"'{m.group(0).strip()}' — ({m.group(2)}, {n:,}) 짝이 계산값에 없음 {ctx(m)}")
            used.add(m.start(1))
    # 4) 그 밖의 숫자 — 범위('4~40%')는 양 끝에 같은 단위
    for m in re.finditer(rf"(?<![0-9A-Za-z.,])({NUM})(?:\s*[~–]\s*({NUM}))?(?![0-9A-Za-z]|\.\d)(\s*%)?", t):
        after = t[m.end():m.end() + 4].lower()
        before = t[max(0, m.start() - 1):m.start()]
        if re.match(r"[A-Za-z\-가-힣]", before) or any(after.startswith(u) for u in SKIP_UNITS):   # '북3'·'s10' 같은 모델 표기
            continue
        if re.search(r"(약|대략|~|±|≈)\s*$", t[max(0, m.start() - 4):m.start()]) or re.match(r"\s*(여|\+|만|천|억)", t[m.end():]):
            continue                                     # 어림값은 대조하지 않는다(한계)
        if re.search(r"(hop|limit|top|k)\s*$", t[max(0, m.start() - 6):m.start()], re.I):
            continue                                     # API 호출 인자
        _open = t.rfind("(", 0, m.start())
        in_credit_paren = _open >= 0 and ")" not in t[_open:m.start()] and "크레딧" in t[_open:m.start()]
        if re.match(r"\s*크레딧", t[m.end():]) or re.search(r"크레딧\s*\([^)]*$", t[max(0, m.start() - 20):m.start()]) or in_credit_paren:
            continue                                     # 크레딧 누계는 예산 게이트(budget) 기록의 몫 — 여기서 대조하지 않는다
        if not m.group(2) and not m.group(3) and re.fullmatch(r"20\d\d", m.group(1)):
            continue                                     # 연도
        pct = bool(m.group(3))
        # 이름 바로 뒤 숫자('<검색어> 11,636' · "'<검색어>' 58")는 그 이름의 값이어야 한다.
        # 이름에 '·'가 들어갈 수 있으므로('고장·수명') 뒤에서부터 '·' 조각을 늘려 가며 아는 이름을 찾는다
        full = re.split(r"[,(:—→/]|\s-\s", t[max(0, m.start() - 40):m.start()])[-1]
        parts = [re.sub(r"[‘’'\"“”]", "", re.sub(r"^(직전|직후|최대|합|계|약)\s*", "", x.strip())).strip() for x in full.split("·")]
        cands = [c for c in ("·".join(parts[i:]) for i in range(len(parts))) if c and norm(c) in facts.names]
        qm = re.search(r"[‘'\"“]([^‘’'\"“”]+)[’'\"”]\s*\(?\s*$", t[max(0, m.start() - 40):m.start()])   # "'테블릿 추천' 11,636"
        if qm and norm(qm.group(1)) in facts.names:
            cands.insert(0, qm.group(1))
        counted = re.match(r"\s*(경로|질의|개|건 중|종|축|시드|/)", t[m.end():])     # 개수·분수 — 검색량 짝이 아니다
        if not pct and not m.group(2) and not counted and m.start(1) not in used and cands:
            n = _num(m.group(1))
            ok = any((norm(c), n) in facts.pairs or any(v_ == n and norm(c) in nm for nm, v_ in facts.pairs) for c in cands)
            if n and not ok and n not in allow:          # 0은 '미측정·거짓 0' 설명에 쓰인다 · 약칭('<라인>' → '<브랜드> <라인> <품목>') 인정
                issues.append(f"'{cands[0]} {m.group(1)}' — ({cands[0]}, {n:,}) 짝이 계산값·원자료에 없음 {ctx(m)}")
            if n:
                continue
        for gi in (1, 2):
            if not m.group(gi) or m.start(gi) in used:
                continue
            n = _num(m.group(gi))
            if n in allow:
                continue
            ok = (n in facts.pcts) if pct else (n in facts.ints)
            if not ok:
                issues.append(f"'{m.group(0).strip()}' — {n:,}{'%' if pct else ''} 계산값에 없음 {ctx(m)}")
    return issues


def texts_of(obj, path="") -> list[tuple[str, str]]:
    """설정 구조에서 문자열을 경로와 함께 뽑는다."""
    out = []
    if isinstance(obj, str):
        out.append((path, obj))
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            out += texts_of(x, f"{path}[{i}]")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out += texts_of(v, f"{path}.{k}" if path else k)
    return out


# ── 빌더 공용 진입점 ──────────────────────────────────────────────────────────
REF_KEYS = {"cell", "cells", "hub", "hyp", "run", "runs", "file", "raw", "anchor", "group", "key", "id", "hubs", "clusters", "seed", "seeds",
            "source", "data_files", "data_files_extra"}


def config_texts(cfg: dict, skip: set[str] | None = None) -> list[tuple[str, str]]:
    """설정에서 대조할 문자열 — '_'로 시작하는 주석 키와 skip 경로(앞부분 일치)는 뺀다."""
    skip = set(skip or ())
    out = []
    for where, text in texts_of(cfg):
        parts = re.split(r"[.\[]", where)
        if any(p.startswith("_") for p in parts):
            continue
        if any(where == s or where.startswith(s + ".") or where.startswith(s + "[") for s in skip):
            continue
        if parts and parts[-1].rstrip("]") in REF_KEYS:
            continue                                     # 다른 데이터를 찾는 열쇠(셀 라벨·허브 id·파일) — 문구가 아니다
        if re.fullmatch(r"[\w./\-가-힣#:]*(90_Output|raw/|core/|\.json|\.html)[\w./\-가-힣#:]*", text):
            continue                                     # 파일 경로
        out.append((where, text))
    return out


def brand_names(vertical: str | None) -> set[str]:
    """정본 brand-map의 브랜드 이름(없으면 빈 집합 — 브랜드 짝 검사를 건너뛴다)."""
    if not vertical:
        return set()
    try:
        from lib.canon import load_canon
        return set(load_canon(vertical).brands)
    except Exception:  # noqa: BLE001 — 정본을 못 읽으면 짝 검사만 약해진다
        return set()


def gate(label: str, texts: list[tuple[str, str]], data_objs: list, *, run: Path | None = None, number_check: dict | None = None,
         brands: set[str] | None = None, ws: Path | None = None) -> list[str]:
    """문구 목록을 계산 데이터와 대조해 문제 목록을 돌려준다. 호출한 빌더가 비어 있지 않으면 멈춘다.
    run: 분석 폴더 하나 또는 여럿 — 원자료 검색량·여정 집계를 사실로 더한다(run_facts).
    number_check: {compare_data: {이름: 데이터 JSON 경로(ws 기준)}, derived: [파생값 선언], allow: [{values, why}]}"""
    nc = number_check or {}
    facts = Facts()
    for o in data_objs:
        collect(o, facts)
    runs = run if isinstance(run, (list, tuple)) else ([run] if run is not None else [])
    errs = []
    runs = list(runs) + [Path(ws) / x if ws else Path(x) for x in nc.get("runs") or []]   # 문구가 인용하는 다른 run
    for r in runs:
        run_facts(r, facts)
        for f in sorted((Path(r) / "core").glob("*.json")):          # 엔진 core 산출(합산·전이·별칭군 등)
            try:
                collect(json.loads(f.read_text(encoding="utf8")), facts)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        if nc.get("keywords"):
            errs += keyword_facts(r, nc["keywords"], facts) if all((Path(r) / k).exists() for k in nc["keywords"]) else []
    for name, rel in (nc.get("compare_data") or {}).items():
        p = (Path(ws) / rel) if ws else Path(rel)
        if p.exists():
            body = p.read_text(encoding="utf8")
            collect([json.loads(x) for x in body.splitlines() if x.strip()] if p.suffix == ".jsonl" else json.loads(body), facts)
        else:
            errs.append(f"비교 데이터 없음: {rel} ({name})")
    errs += derived_facts(nc.get("derived"), facts)
    allow = {int(v) for a in nc.get("allow") or [] for v in a["values"]}
    for where, text in texts:
        errs += [f"{where}: {m}" for m in check(text, facts, brands or set(), allow)]
    return errs


def abort_message(label: str, errs: list[str]) -> str:
    return (f"[숫자 대조] {label} — 작성 문구에 계산값과 맞지 않는 숫자가 있어 렌더를 멈춥니다\n"
            + "\n".join(f"  × {e}" for e in errs)
            + "\n  고치는 법: 계산값으로 문구를 고치거나, 원자료 검색어는 number_check.keywords에, 다른 산출물 수치는 "
              "number_check.compare_data에 선언한다")


def run_facts(run: Path, facts: Facts, *, volumes: bool = True, paths: bool = True) -> Facts:
    """run 원자료에서 사실을 모은다.
    volumes — raw의 keyword_info 계열 응답: (검색어, 검색량) 짝만 더한다(이름 없이 적힌 검색량은 인정하지 않는다).
    paths   — raw/paths_*.json: 앵커 경로 수, 앵커 직전·직후 노드별 건수와 비율, 앵커로 시작·끝나는 경로 수."""
    raw = Path(run) / "raw"
    if volumes and raw.exists():
        for f in sorted(raw.glob("*.json")):
            if f.name.startswith(("cluster_", "paths_", "serp_", "intent_")):
                continue
            try:
                d = json.loads(f.read_text(encoding="utf8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            items = d.get("data") if isinstance(d, dict) else None
            for it in items if isinstance(items, list) else []:
                if isinstance(it, dict) and isinstance(it.get("keyword"), str):
                    v = (it.get("ads_metrics") or {}).get("volume_avg") if isinstance(it.get("ads_metrics"), dict) else it.get("volume_avg")
                    if isinstance(v, int):
                        facts.add_pair(it["keyword"], v)
                    tr = (it.get("ads_metrics") or {}).get("volume_trend") if isinstance(it.get("ads_metrics"), dict) else None
                    if isinstance(tr, (int, float)):
                        facts.pcts.add(round(abs(tr) * 100))    # 추세 비율 '+200%' · '-14%'
    if paths and raw.exists():
        from collections import Counter
        total, axes = 0, 0
        for f in sorted(raw.glob("paths_*.json")):
            try:
                ps = json.loads(f.read_text(encoding="utf8")).get("data") or []
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            anchor = norm(f.stem[len("paths_"):].replace("_", " "))
            n = len(ps)
            facts.ints.add(n); total += n; axes += 1
            prev, nxt, start, end = Counter(), Counter(), 0, 0
            for pa in ps:
                idx = next((i for i, x in enumerate(pa) if norm(x) == anchor), None)
                if idx is None:
                    continue
                start += idx == 0; end += idx == len(pa) - 1
                if idx > 0: prev[pa[idx - 1]] += 1
                if idx < len(pa) - 1: nxt[pa[idx + 1]] += 1
            for cnt in (prev, nxt):
                for node, c in cnt.items():
                    facts.add_pair(node, c); facts.ints.add(c)
                    facts.ratios.add((n, c)); facts.ratios.add((n, ("%", round(c / n * 100)))); facts.pcts.add(round(c / n * 100))
            for c in (start, end):
                facts.ints.add(c); facts.ratios.add((n, c)); facts.ratios.add((n, ("%", round(c / n * 100))))
        if axes:
            facts.ints.update({total, axes})                  # '여정 7축 1,050경로'
    return facts


def derived_facts(decl: list, facts: Facts) -> list[str]:
    """파생값 선언을 원자료로 다시 계산해 맞으면 사실로 더한다.
    {"value": 37716, "sum": ["<품목> 추천", "<표기 변형> 추천", "<표기 변형2> 추천"]} · {"value": 39, "pct": [58, 150]} ·
    {"value": 139000, "sum": [...], "round": 1000}. 항목은 계산값에 있는 수 또는 짝 이름(검색어·브랜드·허브 id)
    · 이름이 검색어와 관계망 시드에 함께 쓰이면 '관계망:시드'로 질의 수를 지정한다.
    파생값은 선언 순서대로 쌓인다 — 앞에서 확인한 값을 뒤 선언의 항목으로 쓸 수 있다."""
    errs = []
    lookup = {}
    for name, v in facts.pairs:
        lookup.setdefault(name, set()).add(v)

    def val(x):
        if isinstance(x, str) and x.startswith("관계망:"):
            if norm(x[4:]) not in facts.seeds:
                raise KeyError(x)
            return facts.seeds[norm(x[4:])]
        if isinstance(x, (int, float)):
            if x not in facts.ints:                       # 선언한 수도 계산값이어야 한다
                raise KeyError(x)
            return x
        vs = lookup.get(norm(x))
        if not vs or len(vs) != 1:
            raise KeyError(x)
        return next(iter(vs))
    for d in decl or []:
        try:
            if "sum" in d:
                got = sum(val(x) for x in d["sum"])
            elif "pct" in d:
                a, b = (val(x) for x in d["pct"])
                got = round(a / b * 100)
                facts.ratios.add((b, a)); facts.ratios.add((b, ("%", got)))
            else:
                errs.append(f"파생값 선언 형식 오류: {d}"); continue
        except KeyError as e:
            errs.append(f"파생값 구성 요소를 원자료에서 못 찾음(없거나 값이 여럿): {e} — {d}"); continue
        r = d.get("round")
        if r:
            got = round(got / r) * r
        if got != d["value"]:
            errs.append(f"파생값이 원자료로 재현되지 않음: 선언 {d['value']:,} · 재계산 {got:,} — {d}"); continue
        (facts.pcts if "pct" in d else facts.ints).add(d["value"])
    return errs


def banner_html(errs: list[str]) -> str:
    """초안 허용(--allow-unverified-numbers)으로 렌더할 때 산출물 머리에 붙이는 경고."""
    if not errs:
        return ""
    import html as _h
    items = "".join(f"<li>{_h.escape(e)}</li>" for e in errs[:12]) + (f"<li>… 외 {len(errs) - 12}건</li>" if len(errs) > 12 else "")
    return ('<div class="gate-banner" style="margin:12px 0 16px;padding:12px 14px;border-radius:8px;border:1px solid #d9a441;'
            'background:#fff7e6;color:#4a3500;font:14px/1.55 -apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif">'
            f'<b>계산값과 맞지 않는 숫자 {len(errs)}건 — 배포 전 수정이 필요한 초안</b> 작성 문구의 숫자 일부가 계산값·원자료와 맞지 않습니다. '
            f'배포 전에 고치세요.<ul style="margin:6px 0 0 18px;font-size:12.5px">{items}</ul></div>')


def enforce(run: Path | None, errs: list[str], allow_unverified: bool) -> bool:
    """막을지 정한다 — 게이트 기록(gates.json)이 있는 run은 막고, 기록 이전 run(레거시)은 배너만 붙인다.
    run-gates 계약과 같은 원칙: 레거시 산출물을 소급 차단하지 않되 미통과 사실은 산출물에 드러낸다."""
    if not errs or allow_unverified:
        return False
    return run is not None and (Path(run) / "gates.json").exists()
