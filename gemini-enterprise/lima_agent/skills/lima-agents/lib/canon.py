"""정본 해석기 — brand-map-md/v1 단일 파서·매처 (2026-09-17 신설).

왜 필요한가
  같은 brand-map.md를 여러 곳이 따로 읽으면 규칙이 갈라져 괄호 속 영문 별칭을 놓치거나 자체 매칭에서 오탐이 생긴다.
  정본 소비 규칙: **엔티티는 이 모듈을 거쳐서만 얻는다.**

제공
  parse_brand_map(path)      → Canon (브랜드별 ×사명/○서브 별칭 · 동음이의 · 차단 목록 · 파서 진단)
  Canon.lookup(name)         → 이름 하나가 정본에 어떻게 있는가 (registered/homonym/blocked/absent)
  Canon.brands_in(text)      → 텍스트에 걸린 브랜드 (원칙 3: 단독 사명 쿼리 제외)
  Canon.regex_map()          → {브랜드: 정규식} — 엔진 렌더러 호환 형식
  alias_hit(alias, text)     → 영문은 단어 경계, 한글은 띄어쓰기 무시 부분 문자열
  load_canon(vertical)       → 버티컬 adapter.yaml A3 authority + homonyms까지 합친 Canon

매칭 규칙
  · 브랜드당 한 줄 — 이어 쓴 줄·한 줄 두 브랜드·브랜드 줄 0건을 diagnostics로 드러낸다
  · 영문·숫자 별칭은 단어 경계, 한글은 띄어쓰기 무시 부분 문자열
  · 결합형 부분 문자열 매칭은 사이 수식어를 놓친다('○○ 여름 원피스' ≠ '○○ 원피스') — 과소 집계
  보강 규칙
    · 동음이의 표에 오른 단독 별칭은 넣은 형태(keep_only)가 함께 있을 때만 브랜드로 센다('모바일 ○○'이 '모바' 브랜드로 잡힌 오탐)
    · 넣은 형태(keep_only)를 담은 이름은 동음이의로 판정하지 않는다('<제품명> 미니'가 '미니' 동음이의 규칙에 걸렸다)
    · 모델 표지(미니·프로·세대·S10 등)를 뒤에서 떼고 다시 조회한다 — 등재 라인의 모델은 공백이 아니다
    · 1글자 단독어(갤·탭)도 동음이의 판정에는 쓴다 — 브랜드·차단 목록 대조는 여전히 2글자 이상
  모델 표지는 업권마다 다르다 — 공통 목록(MODEL_SUFFIX)은 IT·가전 표지만 갖는다. 업권 라인 표지(건기식 골드·키즈…)는
    adapter.yaml A3의 model_suffixes(글자 그대로)·model_suffix_regex(정규식)로 선언하고 load_canon이 합친다.
    공통 목록에 업권 어휘를 넣지 않는다 — 다른 업권의 '○○ 골드'가 라인으로 오판된다

표준 라이브러리만 쓴다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parents[2]
BRAND_LINE = re.compile(r"^- \*\*(.+?)\*\*\s*—\s*(.+)$", re.M)
_ASCII = re.compile(r"^[a-z0-9 .+\-]+$")
_SPACE = re.compile(r"[\s·・/()\[\]\-_.,]+")
# 이름 뒤에 붙는 모델 표지 — '<제품명> 미니'·'<제품명> 7세대'·'<제품명> s10 fe'에서 떼고 라인을 다시 조회한다
MODEL_SUFFIX = re.compile(r"^(미니|프로|에어|울트라|플러스|라이트|맥스|슬림|기본형|mini|pro|air|ultra|plus|lite|max|slim|go|fe|se|[a-z]|\+|"
                          r"\d+세대|\d+(\.\d+)?(인치|형)?|[a-z]{1,3}\d{1,4}[a-z+]{0,3}|m\d)$", re.I)


def norm(s: str) -> str:
    """띄어쓰기·구두점 무시 소문자 — '갤럭시탭'/'갤럭시 탭'을 같은 말로 본다."""
    return _SPACE.sub("", str(s or "")).lower()


def alias_hit(alias: str, text: str) -> bool:
    """정본 매칭 규칙 하나.
    · 영문·숫자 별칭은 **단어 경계** — 부분 문자열로 보면 'hashphotos'가 'hp'로 잡힌다(2026-09-17 실측 오탐).
    · 한글·혼합 별칭은 **띄어쓰기 무시 부분 문자열** — '갤럭시탭'/'갤럭시 탭' 변형을 함께 잡는다."""
    a = str(alias).lower().strip()
    if not a:
        return False
    low = re.sub(r"\s+", " ", str(text).lower())
    if _ASCII.match(a):
        return re.search(r"(?<![a-z])" + re.escape(a) + r"(?![a-z])", low) is not None
    return norm(a) in norm(text)


def _clean_alias(a: str) -> str:
    a = re.sub(r"\(.*?\)|\[.*?\]|—.*$", " ", a).strip()
    return re.sub(r"\s*\S*(한정|취급|유지|결합형|모델명).*$", "", a).strip()


@dataclass
class Brand:
    name: str
    corp: list = field(default_factory=list)    # × 사명 별칭 — 단독 쿼리는 집계 제외(원칙 3)
    sub: list = field(default_factory=list)     # ○ 서브브랜드·제품 별칭 — 단독 쿼리 유지
    other: list = field(default_factory=list)   # ×/○ 표기 없는 조각 — 엔진 렌더러가 과거부터 읽어 온 것

    @property
    def aliases(self) -> list:
        return self.corp + self.sub + self.other


@dataclass
class Canon:
    source: str
    brands: dict = field(default_factory=dict)       # name → Brand
    homonyms: dict = field(default_factory=dict)     # norm(term) → {term, collision, keep_only}
    blocked: dict = field(default_factory=dict)      # norm(name) → 분류(리뷰어·커뮤니티·유통 …)
    diagnostics: list = field(default_factory=list)  # 파서가 조용히 버리던 것
    model_suffix_extra: list = field(default_factory=list)  # 업권 모델 표지 정규식(adapter A3)

    def is_model_suffix(self, tok: str) -> bool:
        """공통 표지(MODEL_SUFFIX) 또는 이 업권이 선언한 라인 표지인가."""
        return bool(MODEL_SUFFIX.match(tok)) or any(re.fullmatch(p, tok, re.I) for p in self.model_suffix_extra)

    # ── 조회 ──
    def corp_only(self) -> set:
        return {norm(a) for b in self.brands.values() for a in b.corp}

    def _alias_counts(self, a: str, text: str) -> bool:
        """별칭 적중 + 동음이의 가드 — 표에 오른 단독 별칭은 넣은 형태가 텍스트에 함께 있을 때만 센다."""
        if not alias_hit(a, text):
            return False
        h = self.homonyms.get(norm(a))
        return not h or any(alias_hit(k, text) for k in h.get("keep_only") or [])

    def brands_in(self, text: str, exclude_corp_only: bool = True) -> set:
        if exclude_corp_only and norm(text) in self.corp_only():
            return set()      # brand-map 원칙 3 — 단독 사명 쿼리는 의도 불명이라 집계 제외
        return {b.name for b in self.brands.values() if any(self._alias_counts(a, text) for a in b.aliases)}

    def lookup(self, name: str) -> dict:
        """이름 하나를 정본에 대조한다. 끝에서부터 잘라 보는 **꼬리 스팬** 규칙:
        '브랜드 제품명' → '제품명'가 ○ 별칭이면 등재. 한국어 명사구는 끝이 머리라
        앞의 사명·수식어가 붙어도 같은 물건이다. 반대로 '갤럭시 탭'의 앞 '갤럭시'만 등재돼 있으면
        미등재다 — 다른 품목의 별칭이 이 품목을 덮지 않는다."""
        toks = str(name).split()
        nname = norm(name)
        for i in range(len(toks)):
            tail = norm(" ".join(toks[i:]))
            if not tail:
                continue
            if len(tail) < 2:                              # 1글자(갤·탭)는 동음이의 판정에만 쓴다
                h = self.homonyms.get(tail)
                if h and len(toks) == 1:
                    return {"status": "homonym", "term": h["term"], "collision": h.get("collision", ""),
                            "keep_only": h.get("keep_only", []), "matched_tail": toks[i]}
                continue
            for b in self.brands.values():
                for kind, al in (("sub", b.sub), ("other", b.other), ("corp", b.corp)):
                    for a in al:
                        if norm(a) == tail:
                            return {"status": "registered", "brand": b.name, "alias": a, "kind": kind,
                                    "matched_tail": " ".join(toks[i:])}
            if tail in self.homonyms:
                h = self.homonyms[tail]
                if not any(norm(k) in nname for k in h.get("keep_only") or []):
                    return {"status": "homonym", "term": h["term"], "collision": h.get("collision", ""),
                            "keep_only": h.get("keep_only", []), "matched_tail": " ".join(toks[i:])}
            if tail in self.blocked:
                return {"status": "blocked", "kind": self.blocked[tail], "matched_tail": " ".join(toks[i:])}
        if len(toks) > 1 and self.is_model_suffix(toks[-1]):
            base = self.lookup(" ".join(toks[:-1]))
            if base["status"] in ("registered", "homonym"):   # '탭 S' → '탭'(동음이의) — 조각은 동음이의 판정을 물려받는다
                return {**base, "model_suffix": " ".join([*base.get("model_suffix", "").split(), toks[-1]]).strip()}
        return {"status": "absent"}

    def regex_map(self) -> dict:
        """엔진 렌더러 호환 — {브랜드: re.Pattern}. 영문은 \\b 경계, 한글은 그대로."""
        rx = {}
        for b in self.brands.values():
            al = sorted({a.lower() for a in b.aliases}, key=len, reverse=True)
            if al:
                rx[b.name] = re.compile("|".join(
                    r"\b" + re.escape(a) + r"\b" if re.match(r"^[a-z]", a) else re.escape(a) for a in al), re.I)
        return rx


def parse_brand_map(path: Path | str) -> Canon:
    p = Path(path)
    canon = Canon(source=str(p))
    try:
        txt = p.read_text(encoding="utf8")
    except OSError as e:
        canon.diagnostics.append(f"정본 파일을 읽지 못함: {e}")
        return canon

    lines = txt.splitlines()
    for idx, raw in enumerate(lines):
        m = BRAND_LINE.match(raw)
        if not m:
            continue
        if "{{" in m.group(1) or "{{" in m.group(2):
            continue                                    # 채우기 전 템플릿 자리표시자 줄 — 브랜드가 아니다
        name = re.sub(r"\s*\(.*?\)", "", m.group(1)).split("·")[0].strip()
        body = m.group(2)
        b = canon.brands.setdefault(name, Brand(name))
        if body.count("×") > 1 or body.count("○") > 1:
            canon.diagnostics.append(f"{idx + 1}행 '{name}': ×/○ 표기가 두 번 이상 — 두 브랜드를 한 줄에 쓴 것 같다(오귀속 위험)")
        for part in re.split(r"\s*/\s*", body):
            s = part.strip()
            bucket = b.corp if s.startswith("×") else b.sub if s.startswith("○") else b.other
            for a in re.sub(r"^[×○]\s*:\s*", "", s).split(","):
                a = _clean_alias(a)
                if a and len(a) >= 2 and not a.startswith("("):
                    bucket.append(a)
            # 괄호 속 영문 별칭 — '서피스(surface)' → surface
            bucket += [x for x in re.findall(r"\(([a-z][a-z ]+)\)", s) if len(x) >= 3]
        # 이어 쓴 줄 — 파서가 읽지 않는다. 조용히 사라지지 않게 진단으로 남긴다
        nxt = lines[idx + 1] if idx + 1 < len(lines) else ""
        if nxt.strip() and not nxt.lstrip().startswith(("-", "#", "|", ">", "*")) and ("," in nxt or "○" in nxt or "×" in nxt):
            canon.diagnostics.append(f"{idx + 2}행: '{name}' 줄을 이어 쓴 것으로 보임 — 파서는 한 줄만 읽어 이 별칭들은 누락된다")

    # 동음이의 표 — 첫 열 '단독어'를 '·'로 나눈다
    for m in re.finditer(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$", txt, re.M):
        head, coll, keep = m.groups()
        if head in ("단독어",) or set(head) <= set("-: "):
            continue
        # 동음이의 절 아래의 표만 — 표 머리에 '단독어'가 있는 절
        start = txt.rfind("\n#", 0, m.start())
        section = txt[start:m.start()]
        if "단독어" not in section:
            continue
        for term in re.split(r"\s*·\s*", head):
            if term:
                canon.homonyms[norm(term)] = {"term": term, "collision": coll,
                                              "keep_only": [k.strip() for k in re.split(r"\s*·\s*", keep) if k.strip()]}

    # 차단 목록 — '브랜드가 아닌 것' 절의 '- **분류**: a, b(c), d'
    blk = re.search(r"^#+\s*브랜드가 아닌 것.*?$(.*?)(?=^#|\Z)", txt, re.M | re.S)
    if blk:
        for m in re.finditer(r"^- \*\*(.+?)\*\*\s*:\s*(.+)$", blk.group(1), re.M):
            for a in m.group(2).split(","):
                for form in [re.sub(r"\(.*?\)", "", a).strip()] + re.findall(r"\(([^)]+)\)", a):
                    if len(norm(form)) >= 2:
                        canon.blocked[norm(form)] = m.group(1)

    if not canon.brands:
        canon.diagnostics.append("brand-map-md/v1 브랜드 줄('- **이름** — 본문')이 0건 — 표 형식이면 파서가 읽지 못한다")
    return canon


def load_canon(vertical: str, brand_map: Path | str | None = None, skills_root: Path | None = None) -> Canon:
    """버티컬의 A3 정본. adapter.yaml의 homonyms도 합친다. brand_map을 주면 그 파일로 대체(회귀 테스트용)."""
    root = (skills_root or SKILLS_ROOT) / vertical
    # 버티컬은 references/brand-map.md, 범용 스킬은 dictionary/brand-map.md(분석마다 채우는 틀 · adapter A3 template)에 둔다.
    # 2026-09-18 스타터 v1.2 검증에서 발견: references만 보아 범용 스킬 사용자가 채운 사전을 읽지 못하고 있었다
    path = Path(brand_map) if brand_map else next((root / r for r in ("references/brand-map.md", "dictionary/brand-map.md")
                                                   if (root / r).exists()), root / "references/brand-map.md")
    canon = parse_brand_map(path)
    ad = root / "adapter.yaml"
    if ad.exists():
        text = ad.read_text(encoding="utf8")
        for m in re.finditer(r"\{term:\s*\"([^\"]+)\",\s*collision:\s*\"([^\"]*)\",\s*keep_only:\s*\[([^\]]*)\]\}", text):
            term, coll, keep = m.groups()
            canon.homonyms.setdefault(norm(term), {"term": term, "collision": coll,
                                                   "keep_only": re.findall(r"\"([^\"]+)\"", keep)})
        # 업권 모델 표지 — model_suffixes는 글자 그대로, model_suffix_regex는 정규식(YAML 큰따옴표의 \\ 는 \ 로 푼다)
        for key, literal in (("model_suffixes", True), ("model_suffix_regex", False)):
            m = re.search(rf"^\s*{key}:\s*\[(.*?)\]", text, re.M | re.S)
            if m:
                for v in re.findall(r"\"((?:[^\"\\]|\\.)*)\"", m.group(1)):
                    v = v.replace("\\\\", "\\")
                    canon.model_suffix_extra.append(re.escape(v) if literal else v)
    return canon
