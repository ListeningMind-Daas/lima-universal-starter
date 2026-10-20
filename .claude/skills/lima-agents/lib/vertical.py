#!/usr/bin/env python3
"""어댑터 로더·검증기 — 엔진 × 버티컬 계약 (cep-finder-adapter/v1).

정본: lima-agents/references/adapter-schema.md
경계: 이 모듈은 stdlib 전용(정의서 v2.2 §16.3). PyYAML이 있으면 쓰고, 없으면 내장 파서로 폴백한다.

사용:
    from lib.vertical import load_adapter
    ad = load_adapter("listeningmind-universal")
    ad.status("A3_entity_authority")      # ready | partial | absent
    ad.banner()                           # 준비도 배너 문자열 목록
    ad.report                             # run_manifest['adapter_validation']에 그대로 기록
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

SCHEMA_ID = "cep-finder-adapter/v1"
SLOT_IDS = ["A1_seed_policy", "A2_noise_lexicon", "A3_entity_authority", "A4_ontology_binding",
            "A5_guardrails", "A6_render", "A7_modifier_implication"]
STATUS_VALUES = {"ready", "partial", "absent"}
VALID_MARKETS = {"kr", "jp", "us"}
TOP_REQUIRED = ["schema", "adapter_version", "vertical", "spec_ref", "updated", "markets", "slots"]

# 슬롯별 ready 요건 — 미충족 시 partial 강등(실행은 계속)
READY_FIELDS = {
    "A1_seed_policy": ["thresholds", "banned_seeds", "notation_pairs_required"],
    "A2_noise_lexicon": ["patterns", "volume_check_required"],
    "A3_entity_authority": ["format", "rules", "homonyms", "generic_rule"],
    "A4_ontology_binding": ["files", "id_prefixes", "cep_id_format", "status_values", "append_only"],
    "A5_guardrails": ["mandatory"],
    "A6_render": ["template", "renderer"],
    "A7_modifier_implication": ["version", "entries"],
}
# 존재를 확인할 경로 필드 (슬롯 → 접근 경로)
PATH_FIELDS = {
    "A1_seed_policy": [("authority",), ("hook", "cmd")],
    "A2_noise_lexicon": [("authority",), ("dictionary", "file")],
    "A3_entity_authority": [("authority",)],
    "A4_ontology_binding": [("files", "nodes"), ("files", "edges"),
                            ("files", "bridge_nodes"), ("files", "bridge_edges")],
    "A5_guardrails": [("authority",)],
    "A6_render": [("template",)],
    "A7_modifier_implication": [("authority",)],
}
# status가 ready 미만일 때 엔진이 낮춰 실행하는 내용 (배너 문구)
FALLBACK_NOTE = {
    "A1_seed_policy": "시드 정책 기본값 — 임계 20%/60%/10, 금지 시드 없음",
    "A2_noise_lexicon": "노이즈 사전 없음 — 범용 어휘만, 오염 위험",
    "A3_entity_authority": "별칭 정본 없음 — 브랜드·SoV 지표 산출 생략",
    "A4_ontology_binding": "온톨로지 미연결 — delta만 산출, 자산 누적 불가",
    "A5_guardrails": "버티컬 가드레일 없음 — 엔진 공통 문구만 삽입",
    "A6_render": "기본 템플릿 사용",
    "A7_modifier_implication": "함의 사전 없음 — 함의 역추론 생략, 제약(L4) gap 처리",
}
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
PREFIX_RE = re.compile(r"^[A-Z][A-Z0-9]{0,5}$")


# ─────────────────────────────────────────── 최소 YAML 파서 (stdlib 폴백)
def _scalar(tok: str):
    t = tok.strip()
    if not t:
        return None
    if t[0] in "\"'" and t[-1] == t[0] and len(t) >= 2:
        body = t[1:-1]
        if t[0] == '"':                       # 큰따옴표만 이스케이프 해석 (YAML 규칙)
            body = body.replace('\\"', '"').replace("\\\\", "\\")
        return body
    low = t.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", t):
        return int(t)
    if re.fullmatch(r"-?\d*\.\d+", t):
        return float(t)
    return t


def _split_top(s: str):
    """중괄호·대괄호·따옴표를 존중하며 콤마로 분리."""
    out, buf, depth, q = [], "", 0, None
    for ch in s:
        if q:
            buf += ch
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch; buf += ch; continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(buf); buf = ""; continue
        buf += ch
    if buf.strip():
        out.append(buf)
    return out


def _inline(tok: str):
    t = tok.strip()
    if t.startswith("[") and t.endswith("]"):
        return [_inline(x) for x in _split_top(t[1:-1])]
    if t.startswith("{") and t.endswith("}"):
        d = {}
        for part in _split_top(t[1:-1]):
            if ":" in part:
                k, v = part.split(":", 1)
                d[_scalar(k)] = _inline(v)
        return d
    return _scalar(t)


def _strip_comment(line: str) -> str:
    out, q = "", None
    for ch in line:
        if q:
            out += ch
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch; out += ch; continue
        if ch == "#":
            break
        out += ch
    return out.rstrip()


def _parse_block(lines, i: int, indent: int):
    """lines[i:] 를 indent 수준의 블록으로 파싱 → (값, 다음 인덱스)."""
    # 리스트인지 매핑인지 판별
    while i < len(lines) and lines[i][1] == "":
        i += 1
    if i >= len(lines):
        return {}, i
    is_list = lines[i][1].startswith("- ") or lines[i][1] == "-"

    if is_list:
        items = []
        while i < len(lines):
            ind, text = lines[i]
            if text == "":
                i += 1; continue
            if ind < indent or not (text.startswith("- ") or text == "-"):
                break
            body = text[2:].strip() if text.startswith("- ") else ""
            if body and not re.match(r"^[\w\-\.]+\s*:", body):
                items.append(_inline(body)); i += 1; continue
            if body.startswith("{"):
                items.append(_inline(body)); i += 1; continue
            # 매핑 항목: 첫 줄 + 이어지는 들여쓰기 줄
            sub = []
            if body:
                sub.append((ind + 2, body))
            i += 1
            while i < len(lines) and (lines[i][1] == "" or lines[i][0] > ind):
                if lines[i][1] != "":
                    sub.append(lines[i])
                i += 1
            val, _ = _parse_block(sub, 0, sub[0][0] if sub else 0)
            items.append(val)
        return items, i

    d = {}
    while i < len(lines):
        ind, text = lines[i]
        if text == "":
            i += 1; continue
        if ind < indent:
            break
        m = re.match(r"^([^:]+):\s*(.*)$", text)
        if not m:
            i += 1; continue
        key = _scalar(m.group(1))
        rest = m.group(2).strip()
        if rest:
            d[key] = _inline(rest); i += 1
        else:
            i += 1
            sub = []
            while i < len(lines) and (lines[i][1] == "" or lines[i][0] > ind):
                if lines[i][1] != "":
                    sub.append(lines[i])
                i += 1
            d[key] = _parse_block(sub, 0, sub[0][0])[0] if sub else {}
    return d, i


def _flow_depth(s: str) -> int:
    """따옴표 밖의 [ { ] } 균형."""
    d, q = 0, None
    for ch in s:
        if q:
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
        elif ch in "[{":
            d += 1
        elif ch in "]}":
            d -= 1
    return d


def _minimal_yaml(text: str):
    lines, buf, ind, depth = [], None, 0, 0
    for raw in text.splitlines():
        stripped = _strip_comment(raw)
        if buf is not None:                       # flow 컬렉션 이어붙이기
            buf += " " + stripped.strip()
            depth += _flow_depth(stripped)
            if depth <= 0:
                lines.append((ind, buf)); buf = None; depth = 0
            continue
        if not stripped.strip():
            lines.append((0, "")); continue
        cur_ind = len(stripped) - len(stripped.lstrip())
        body = stripped.strip()
        d = _flow_depth(body)
        if d > 0:                                 # 이 줄에서 열리고 안 닫힘
            buf, ind, depth = body, cur_ind, d; continue
        lines.append((cur_ind, body))
    if buf is not None:
        lines.append((ind, buf))
    return _parse_block(lines, 0, 0)[0]


def parse_yaml(text: str):
    """PyYAML이 있으면 사용, 없으면 내장 파서."""
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text)
    except ImportError:
        return _minimal_yaml(text)


# ─────────────────────────────────────────── 카테고리 커버리지 유틸
TAXON_CLASSES = ("C1", "C2", "C3", "Line")
# 품목이 아닌 앵커(CEP가 TPO·Look도 연다). 이름이 정확히 같을 때만 앵커로 인정한다
# (부분 일치는 '여름 하객룩 원피스' 같은 품목 run을 TPO로 오인한다). 브랜드 커버리지(A3)는 품목에만 뜻이 있어 검사하지 않는다.
ANCHOR_CLASSES = ("TPO", "Look")
try:                                                        # brand-map-md/v1 줄 패턴의 정본은 lib/canon.py
    from lib.canon import BRAND_LINE
except ImportError:                                         # lib 패키지 밖에서 import될 때
    from canon import BRAND_LINE                            # type: ignore


def _norm(s: str) -> str:
    return re.sub(r"[\s·・/()\[\]\-_.,]+", "", str(s)).lower()


def _hit(text: str, terms) -> str | None:
    """text에 terms 중 하나가 있으면 그 term. 영문은 단어 경계, 한글은 공백·가운뎃점 무시 부분 문자열."""
    low, nt = text.lower(), _norm(text)
    for t in sorted(terms, key=len, reverse=True):
        if len(_norm(t)) < 2:
            continue
        if re.fullmatch(r"[a-z0-9 +\-]+", t.lower()):
            if re.search(r"(?<![a-z0-9])" + re.escape(t.lower()) + r"(?![a-z0-9])", low):
                return t
        elif _norm(t) in nt:
            return t
    return None


def _category_terms(category: str, rows: list[dict] | None) -> tuple[set, set, list]:
    """품목어 확장 — E0에서 품목 노드(C1~C3·Line)를 찾아 (품목어, 섹션어, 매칭 노드)를 돌려준다.

    찾는 규칙: 노드 라벨/별칭이 category와 같거나 category 안에 들어 있음('가벼운 ○○' → ○○).
    품목어 = category + 매칭 노드와 그 부모 C2의 라벨·별칭 — 브랜드 줄 대조용.
    섹션어 = 품목어 + 대분류(C1 노드 또는 C2의 group 약칭, '인접' 접두 제거) — 섹션 제목 대조용.
    대분류어('생활'·'주방')는 넓어서 브랜드 줄에는 쓰지 않는다."""
    own, matched = {category}, []
    if not rows:
        return own, set(own), matched
    names = lambda r: [r["label"]] + [a for a in r["aliases"].split("|") if a]
    nc = _norm(category)
    by_label = {_norm(r["label"]): r for r in rows if r["class"] in TAXON_CLASSES}
    top = set()
    for r in rows:
        if r["class"] not in TAXON_CLASSES:
            continue
        if not any(len(_norm(n)) >= 2 and (_norm(n) == nc or (_norm(n) in nc and not re.fullmatch(r"[a-z0-9]+", _norm(n))))
                   for n in names(r)):
            continue
        matched.append(f"{r['class']}:{r['label']}")
        (top if r["class"] == "C1" else own).update(names(r))
        cur = r
        while cur and cur["class"] in ("C2", "C3") and cur.get("group"):
            parent = by_label.get(_norm(cur["group"]))
            if parent is not None and parent is not cur:
                (top if parent["class"] == "C1" else own).update(names(parent))
                cur = parent
            else:
                if cur["class"] == "C2":
                    top.add(re.sub(r"^인접", "", cur["group"]))
                cur = None
    return own, own | top, matched


# ─────────────────────────────────────────── 어댑터
class Adapter:
    def __init__(self, data: dict, root: Path, report: dict):
        self.data = data
        self.root = root
        self.report = report

    # 접근자
    @property
    def vertical(self) -> str:
        return self.data.get("vertical", "unknown")

    @property
    def version(self) -> str:
        return self.data.get("adapter_version", "0.0.0")

    def slot(self, sid: str) -> dict:
        return (self.data.get("slots") or {}).get(sid) or {}

    def status(self, sid: str) -> str:
        return self.report["slots"].get(sid, {}).get("effective_status", "absent")

    def get(self, sid: str, *path, default=None):
        cur = self.slot(sid)
        for p in path:
            if not isinstance(cur, dict) or p not in cur:
                return default
            cur = cur[p]
        return cur

    def path(self, sid: str, *path) -> Path | None:
        """경로 필드를 절대 경로로. 파일이 없으면 None."""
        v = self.get(sid, *path)
        if not v:
            return None
        p = (self.root / str(v)).resolve()
        return p if p.exists() else None

    def banner(self) -> list[str]:
        """준비도 배너 — 낮춰 실행한 슬롯을 사용자에게 노출(조용한 대체 금지)."""
        out = []
        for sid in SLOT_IDS:
            st = self.status(sid)
            if st == "ready":
                continue
            if st == "partial":
                issues = self.report["slots"].get(sid, {}).get("issues") or []
                why = "; ".join(issues) if issues else "선언상 부분 구현 — 일부 기능만 적용"
                out.append(f"[{sid} · partial] {why}")
            else:
                out.append(f"[{sid} · absent] {FALLBACK_NOTE[sid]}")
        return out

    # ── 카테고리 커버리지 (2026-09-17) ──
    # ready는 "파일이 있고 형식이 맞다"만 뜻했다. 품목 브랜드가 brand-map에 0건인데도
    # A3가 ready로 통과한 실측 사례가 있다(2026-09-17). 이번 분석 품목을
    # 정본이 실제로 덮는지 본다 — 판정은 거칠게, "0건이면 partial 강등 + 경고"만 확실히.
    def check_category_coverage(self, category: str, brand_map: Path | None = None) -> dict:
        """A2(E0 어휘)·A3(brand-map 브랜드)가 category를 덮는지 검사 → report·effective_status 갱신."""
        rows = self._e0_rows()
        own, section, matched = _category_terms(category, rows)
        cov: dict = {"category": category, "terms": sorted(own), "section_terms": sorted(section - own),
                     "e0_matched": matched}

        # 품목 매칭이 없고 E0의 TPO·Look 행 이름(라벨·별칭)이 category와 정확히 같으면 비품목 앵커 run
        anchor = None
        if not matched and rows:
            nc = _norm(category)
            for r in rows:
                if r["class"] in ANCHOR_CLASSES and nc in {_norm(n) for n in [r["label"]] + [x for x in r["aliases"].split("|") if x]}:
                    anchor = f"{r['class']}:{r['label']}"
                    break
        if anchor:
            cov["anchor"] = anchor

        # A2 — E0에 품목 노드(C1~C3·Line)가 있는가 (비품목 앵커 run은 그 TPO·Look 행으로 대신한다)
        if self.status("A2_noise_lexicon") != "absent" and anchor:
            cov["A2"] = {"checked": True, "hits": [anchor], "anchor": True}
        elif self.status("A2_noise_lexicon") != "absent":
            if self.get("A2_noise_lexicon", "dictionary", "format") != "e0-csv/v1" or rows is None:
                cov["A2"] = {"checked": False, "reason": "E0 사전 없음 또는 e0-csv/v1 아님"}
            else:
                cov["A2"] = {"checked": True, "hits": matched}
                if not matched:
                    self._uncovered("A2_noise_lexicon", f"카테고리 '{category}' 미등재 — E0 사전에 이 품목 어휘가 없음")

        # A3 — brand-map의 섹션 제목(섹션어) · 브랜드 줄(품목어) · 품목에 연결된 E0 Line/Brand의 별칭
        if self.status("A3_entity_authority") != "absent" and anchor:
            cov["A3"] = {"checked": False, "reason": f"비품목 앵커({anchor}) — 브랜드 커버리지는 품목에만 뜻이 있다. 앵커가 여는 품목의 브랜드는 외부 열거 단계가 본다"}
        elif self.status("A3_entity_authority") != "absent":
            bm = Path(brand_map) if brand_map else self.path("A3_entity_authority", "authority")   # brand_map: 회귀 테스트용 대체 정본
            if self.get("A3_entity_authority", "format") != "brand-map-md/v1" or not bm:
                cov["A3"] = {"checked": False, "reason": "brand-map-md/v1 정본 없음"}
            else:
                lines = [l.strip() for l in bm.read_text(encoding="utf8").splitlines()]
                entries = [l for l in lines if BRAND_LINE.match(l)]   # 엔진 파서(render.load_brand_map)가 읽는 줄만 — 표·원칙 불릿 제외
                hits = []
                for l in lines:
                    t = _hit(l, section) if l.startswith("#") else (_hit(l, own) if l in entries else None)
                    if t:
                        hits.append(f"{'section' if l.startswith('#') else 'entry'}:{t} ← {l[:60]}")
                # 품목어가 들어간 E0 Line·Brand(예: 무풍 = '무풍에어컨')의 별칭이 브랜드 줄에 있는가
                # E0 Brand 행만으로는 통과시키지 않는다 — 엔진은 brand-map 줄만 읽으므로 E0에만 있으면 쓰이지 않는다
                linked = set()
                for r in rows or []:
                    if r["class"] in ("Line", "Brand") and _hit(" ".join([r["group"], r["label"], r["aliases"], r["note"]]), own):
                        linked |= {r["label"], *[x for x in r["aliases"].split("|") if x]}
                linked -= own
                for l in entries if linked else []:
                    t = _hit(l, linked)
                    if t:
                        hits.append(f"linked:{t} ← {l[:60]}")
                cov["A3"] = {"checked": True, "n_hits": len(hits), "hits": hits[:12]}
                if not hits:
                    self._uncovered("A3_entity_authority", f"카테고리 '{category}' 미등재 — 정본 사전에 이 품목 브랜드가 없음")

        self.report["coverage"] = cov
        self.report["ready_slots"] = sum(1 for s in self.report["slots"].values() if s.get("effective_status") == "ready")
        return cov

    def _uncovered(self, sid: str, issue: str):
        entry = self.report["slots"][sid]
        entry.setdefault("issues", []).append(issue)
        if entry.get("effective_status") == "ready":
            entry["effective_status"] = "partial"
            self.report["warnings"].append(f"{sid}: ready → partial 강등 ({issue})")
        else:
            self.report["warnings"].append(f"{sid}: {issue}")

    def _e0_rows(self) -> list[dict] | None:
        f = self.path("A2_noise_lexicon", "dictionary", "file")
        if not f:
            return None
        with f.open(encoding="utf8") as fh:
            return [{k: (r.get(k) or "") for k in ("class", "group", "label", "aliases", "note")}
                    for r in csv.DictReader(fh)]

    def approved_implications(self) -> list[dict]:
        """A7 승인 항목만 — pending은 절대 반환하지 않는다(G2 차단)."""
        if self.status("A7_modifier_implication") == "absent":
            return []
        return [e for e in (self.get("A7_modifier_implication", "entries") or [])
                if e.get("status") == "approved"]


def load_adapter(vertical: str, skills_root: Path | None = None) -> Adapter:
    """버티컬 스킬의 adapter.yaml 로드·검증. 실행을 차단하지 않는다 — 차단은 게이트의 몫."""
    skills_root = skills_root or Path(__file__).resolve().parents[2]
    root = skills_root / vertical
    f = root / "adapter.yaml"
    report: dict = {"vertical": vertical, "file": str(f), "errors": [], "warnings": [], "slots": {}}

    if not f.exists():
        report["errors"].append(f"adapter.yaml 없음: {f}")
        report["slots"] = {s: {"declared": "absent", "effective_status": "absent",
                               "reason": "어댑터 파일 없음"} for s in SLOT_IDS}
        return Adapter({}, root, report)

    try:
        data = parse_yaml(f.read_text(encoding="utf8")) or {}
    except Exception as e:                                    # noqa: BLE001
        report["errors"].append(f"YAML 파싱 실패: {e}")
        report["slots"] = {s: {"declared": "absent", "effective_status": "absent",
                               "reason": "파싱 실패"} for s in SLOT_IDS}
        return Adapter({}, root, report)

    # 규칙 1 — 스키마 식별자·필수 필드·semver
    if data.get("schema") != SCHEMA_ID:
        report["errors"].append(f"schema 불일치: {data.get('schema')} (기대 {SCHEMA_ID})")
    for k in TOP_REQUIRED:
        if k not in data:
            report["errors"].append(f"최상위 필수 필드 누락: {k}")
    if not SEMVER.match(str(data.get("adapter_version", ""))):
        report["errors"].append(f"adapter_version semver 아님: {data.get('adapter_version')}")

    # 규칙 4 — markets
    bad = set(data.get("markets") or []) - VALID_MARKETS
    if bad:
        report["errors"].append(f"markets 미지원 값: {sorted(bad)}")

    slots = data.get("slots") or {}
    for sid in SLOT_IDS:
        sl = slots.get(sid)
        entry: dict = {}
        if not sl:
            entry.update(declared="absent", effective_status="absent", reason="슬롯 미선언")
            report["slots"][sid] = entry
            continue

        declared = sl.get("status", "absent")
        entry["declared"] = declared
        if declared not in STATUS_VALUES:
            report["errors"].append(f"{sid}: status 값 오류 '{declared}'")
            declared = "absent"

        reasons = []
        # 규칙 2 — ready 요건
        missing = [k for k in READY_FIELDS[sid] if k not in sl]
        if declared == "ready" and missing:
            reasons.append(f"필수 필드 누락 {missing}")
        # 규칙 3 — 경로 존재
        missing_paths = []
        for pth in PATH_FIELDS.get(sid, []):
            cur = sl
            for p in pth:
                cur = cur.get(p) if isinstance(cur, dict) else None
                if cur is None:
                    break
            if cur and not (root / str(cur)).exists():
                missing_paths.append("/".join(pth) + "=" + str(cur))
        if missing_paths:
            reasons.append(f"경로 없음 {missing_paths}")

        eff = declared
        if declared == "ready" and reasons:
            eff = "partial"
            report["warnings"].append(f"{sid}: ready → partial 강등 ({'; '.join(reasons)})")
        entry.update(effective_status=eff, issues=reasons)
        report["slots"][sid] = entry

    # 규칙 4 — 임계·접두사
    th = (slots.get("A1_seed_policy") or {}).get("thresholds") or {}
    for k in ("noise_rate_max", "fit_rate_min"):
        v = th.get(k)
        if v is not None and not (isinstance(v, (int, float)) and 0 <= v <= 1):
            report["errors"].append(f"A1.thresholds.{k} 범위 오류: {v}")
    bh = th.get("brand_hits_min")
    if bh is not None and not (isinstance(bh, int) and bh > 0):
        report["errors"].append(f"A1.thresholds.brand_hits_min 오류: {bh}")
    for p in (slots.get("A4_ontology_binding") or {}).get("id_prefixes") or []:
        if not PREFIX_RE.match(str(p)):
            report["errors"].append(f"A4.id_prefixes 형식 오류: {p}")

    # 규칙 5 — A7 pending ∩ entries
    a7 = slots.get("A7_modifier_implication") or {}
    appr = {e.get("modifier") for e in (a7.get("entries") or []) if isinstance(e, dict)}
    pend = {e.get("modifier") for e in (a7.get("pending") or []) if isinstance(e, dict)}
    dup = (appr & pend) - {None}
    if dup:
        report["errors"].append(f"A7: pending과 entries 중복 {sorted(dup)} — 승인 전 사용 위험")
    non_approved = [e.get("modifier") for e in (a7.get("entries") or [])
                    if isinstance(e, dict) and e.get("status") != "approved"]
    if non_approved:
        report["warnings"].append(f"A7.entries에 미승인 항목 {non_approved} — 엔진이 사용하지 않음")

    report["ok"] = not report["errors"]
    report["ready_slots"] = sum(1 for s in report["slots"].values()
                                if s.get("effective_status") == "ready")
    return Adapter(data, root, report)


if __name__ == "__main__":
    import json, sys
    ad = load_adapter(sys.argv[1] if len(sys.argv) > 1 else "listeningmind-universal")
    print(json.dumps(ad.report, ensure_ascii=False, indent=2))
    print("\n준비도 배너:")
    for b in ad.banner() or ["(전 슬롯 ready)"]:
        print("  " + b)
