"""산출물 어휘 검사 (lexicon/v1) — 화면에 보이는 문구에 분석 작업 용어가 남아 있으면 렌더 전에 찾는다.

왜: 분석 작업 용어('질의'·'짝 시드' 등)는 업무 사용자가 읽지 못한다. 결정 리포트(render.py)에만 용어 사전(GLOSSARY)이 있으면
다른 산출물에서 그대로 새어 나가고, 사람이 한 줄씩 짚어야 알게 된다. 숫자 대조처럼
어휘도 빌더가 렌더 전에 검사한다.

사전은 이 파일의 LEXICON 하나다 — 결정 리포트 GLOSSARY(자동 치환)와 references/lexicon-gate.md(과장 표현)를 흡수했다.
  jargon       분석 작업 용어 — 업무 사용자가 못 읽는다. 쉬운 말로 고쳐 쓴다                 차단
  exaggerate   과장·단정 표현(lexicon-gate §1) — 수치·범위를 병기하거나 바꾼다               경고
검사 범위: 화면 텍스트만. 태그·script·style·<code>·URL·파일 경로·따옴표 안 소비자 검색어(‘…’ “…”)는 보지 않는다.
예외는 산출물 설정의 lexicon_allow {용어: 사유}로만 둔다 — 사유 없는 예외는 무시된다.
"""
from __future__ import annotations

import html as _html
import json
import re
from dataclasses import dataclass
from pathlib import Path

# (패턴, 쉬운 말, 종류, 설명) — 패턴은 정규식. 한국어는 앞 글자 경계를 (?<![가-힣]) 로 막아 '전망'·'희망' 같은 오탐을 피한다
_K = r"(?<![가-힣A-Za-z])"
LEXICON: list[tuple[str, str, str, str]] = [
    # ── 수집 방법 용어
    (_K + r"짝\s*시드", "대표 모델명을 기준으로 모은", "jargon", "브랜드별 모델명 여러 개로 조사를 시작했다는 뜻"),
    (_K + r"시드(?:어)?", "기준 검색어", "jargon", "조사를 시작한 검색어"),
    (_K + r"중립\s*(?:어|검색어|시드)", "브랜드 없는 검색어", "jargon", "브랜드명이 들어가지 않은 검색어"),
    (_K + r"(?:검색\s*)?관계망|" + _K + r"검색망", "연관 키워드", "jargon", "기준 검색어와 같은 검색 흐름에서 함께 검색된 키워드"),
    (_K + r"망(?=의|은|는|에서|에는|에|을|이|과|와|\s*안|\s*대비|\))", "연관 키워드", "jargon", "'어린이 망의 25%'처럼 관계망을 줄인 말"),
    (_K + r"군집", "키워드 묶음", "jargon", "연관 키워드를 주제별로 나눈 묶음"),
    (_K + r"질의", "검색어", "jargon", "검색창에 입력한 말"),
    (r"\bhop\s*\d?\b", "N단계 연결", "jargon", "연관 키워드를 몇 단계까지 따라갔는가"),
    (r"\blimit\s*\d*\b", "수집 상한", "jargon", ""),
    (_K + r"캔버싱|" + _K + r"캔버스", "조합 검색어 전수 조회", "jargon", "상황어×품목어 조합을 모두 조회한 것"),
    (_K + r"코퍼스", "수집 검색어", "jargon", ""),
    (_K + r"롱테일", "세부 검색어", "jargon", ""),
    (_K + r"헤드텀", "대표 검색어", "jargon", ""),
    (_K + r"결합\s*쿼리|" + _K + r"결합형", "상황+품목 검색어", "jargon", ""),
    (_K + r"쿼리", "검색어", "jargon", ""),
    (_K + r"프로브", "연관어 탐색", "jargon", ""),
    (_K + r"리플레이|\breplay\b", "재계산", "jargon", ""),
    (_K + r"블라인드", "데이터를 보지 않고 쓴", "jargon", ""),
    (r"\bpost-hoc\b", "사후", "jargon", ""),
    (r"\bco_path\b", "동반 경로", "jargon", ""),
    (_K + r"자카드", "중복도", "jargon", ""),
    (_K + r"렉심", "핵심 어휘", "jargon", ""),
    (_K + r"매칭", "일치", "jargon", ""),
    (_K + r"볼륨", "검색량", "jargon", ""),
    (_K + r"허브", "진입점", "jargon", ""),
    (_K + r"슬롯", "상황 요소", "jargon", ""),
    (_K + r"앵커", "기준 축", "jargon", ""),
    (_K + r"브리지", "연결 검색어", "jargon", ""),
    (_K + r"패밀리", "상황군", "jargon", ""),
    (_K + r"노드", "항목", "jargon", ""),
    (_K + r"정본", "확정 기준 데이터", "jargon", "검증을 거쳐 확정한 분석 기준(온톨로지)"),
    (_K + r"게이트", "품질 점검", "jargon", ""),
    (_K + r"표기\s*계층", "품목어·브랜드명 표기 구분", "jargon", ""),
    (r"\bL[123]\b", "뜻으로 풀어 쓴다 — 표기 구분(품목어·브랜드명·모델명)인지 페이지 층(요약·카드·액션)인지", "jargon", ""),
    (r"\brun\b", "분석(회차)", "jargon", ""),
    (r"\b(?:SERP|serp)\b", "검색결과 화면", "jargon", ""),
    (r"\bAIO\b", "AI 검색 요약", "jargon", ""),
    (r"\bPAA\b", "연관 질문", "jargon", ""),
    (r"\b(?:keyword_info|intent_finder|cluster_finder|path_finder)\b", "검색량·연관 검색어·연관 키워드·검색 여정 데이터", "jargon", ""),
    (r"\bHUB_FLOOR\b|\bBRIDGE_FLOOR\b", "최소 규모 기준", "jargon", ""),
    (r"\b(?:supported|unsupported|candidate|confirmed|deferred)\b", "근거 있음·기각·후보·확정·보류", "jargon", ""),
    (r"\bS[0-9][a-c]\b|\(S[0-9]\)|엔진\s*S[0-9]\b|\bS[0-9](?=\s*(?:재수확|구별성|가설|증거|수확))", "단계 코드는 빼고 무엇을 했는지 쓴다", "jargon", "엔진 단계 번호(S3c 등) — 모델명 S9 FE·S6 lite는 제외"),
    # ── 과장·단정 (lexicon-gate §1)
    (_K + r"(?:완패|참패|궤멸|독주|장악|석권|압도적|폭발적|폭증|입증됐|확실시|사실상\s*소유|사실상\s*소멸)", "수치·범위를 병기한 표현", "exaggerate", "lexicon-gate §1"),
]
def _ab(p: str) -> str:
    """\\b는 한글도 단어 문자로 봐서 'run에는'·'AIO로'를 놓친다 — 영숫자 기준 경계로 바꾼다."""
    out, i = [], 0
    while i < len(p):
        if p.startswith("\\b", i):
            nxt = p[i + 2:i + 3]
            out.append("(?<![A-Za-z0-9_])" if (nxt and (nxt.isalnum() or nxt in "\\([-")) else "(?![A-Za-z0-9_])")
            i += 2
        else:
            out.append(p[i]); i += 1
    return "".join(out)


_COMPILED = [(re.compile(_ab(p)), plain, kind, why) for p, plain, kind, why in LEXICON]

_QUOTED = re.compile(r"‘[^’]{0,80}’|“[^”]{0,120}”|'[^'\n]{0,80}'|\"[^\"\n]{0,80}\"")
_SKIP_SPANS = re.compile(r"<(script|style|code)\b.*?</\1>", re.S | re.I)
_URL_PATH = re.compile(r"https?://\S+|\b[\w./-]+\.(?:json|html|md|py|csv|jsonl)\b|\bR-0\d\d\b|\b[A-Z]{2,}-[\w가-힣-]+\b")
SKIP_KEYS = {"id", "kind", "grade", "match", "raw_file", "raw", "url", "href", "collected_at", "at", "file", "hub", "cell", "run",
             "seed", "q", "keyword", "queries", "topQueries", "chips", "examples", "ex", "bridges", "matched", "rows", "p",
             "slug", "cfg", "source_run", "hypothesis", "anchor", "type", "tier", "chip", "members", "series", "month",
             "doc_links", "files", "runs", "clusters", "perSeed", "narrative_seed_results", "evidence_chain", "text",
             "verdict", "strength"}   # 판정 코드(candidate 등)는 식별자다 — 화면 표시는 verdictLabel(2026-09-17 치환이 코드를 바꿔 발견)


@dataclass
class Hit:
    where: str
    term: str
    plain: str
    kind: str
    context: str


def visible(text: str) -> str:
    """태그·script·code·URL·파일 경로·따옴표 안 소비자 검색어를 지운 화면 텍스트."""
    t = _SKIP_SPANS.sub(" ", text)
    t = re.sub(r"<[^>]+>", " ", t)
    t = _html.unescape(t)
    t = _URL_PATH.sub(" ", t)
    return _QUOTED.sub(" ", t)


def scan_text(text: str, where: str, allow: dict | None = None) -> list[Hit]:
    allow = {k: v for k, v in (allow or {}).items() if v}          # 사유 없는 예외는 무시
    t, out = visible(text), []
    for rx, plain, kind, _ in _COMPILED:
        for m in rx.finditer(t):
            term = m.group(0).strip()
            if term in allow or any(re.fullmatch(a, term) for a in allow if a.startswith("^")):
                continue
            out.append(Hit(where, term, plain, kind, t[max(0, m.start() - 30):m.end() + 30].replace("\n", " ").strip()))
    return out


def scan_json(obj, where: str, allow: dict | None = None, path: str = "") -> list[Hit]:
    """산출물 JSON — 화면에 나가는 문자열 값만. 식별자·원자료 필드(SKIP_KEYS)와 한글 없는 값은 건너뛴다."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in SKIP_KEYS or k.startswith("_"):
                continue
            out += scan_json(v, where, allow, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += scan_json(v, where, allow, f"{path}[{i}]")
    elif isinstance(obj, str) and re.search(r"[가-힣]", obj):
        out += scan_text(obj, f"{where}{path}", allow)
    return out


def scan_tsx(src: str, where: str, allow: dict | None = None) -> list[Hit]:
    """React 컴포넌트 — JSX 텍스트와 한글이 든 문자열 리터럴만(주석 제외)."""
    src = re.sub(r"//[^\n]*|/\*.*?\*/", " ", src, flags=re.S)
    parts = re.findall(r">([^<>{}]*[가-힣][^<>{}]*)<", src) + re.findall(r"\"([^\"\n]*[가-힣][^\"\n]*)\"|`([^`]*[가-힣][^`]*)`", src)
    def strip_code(t):                                   # {코드 식}은 화면 문구가 아니다 — 중첩 괄호는 안쪽부터 지운다
        while True:
            u = re.sub(r"\$?\{[^{}]*\}", " ", t)
            if u == t:
                return re.sub(r"[{}]", " ", re.sub(r"\b\w+(?:\.\w+)+\b", " ", u))
            t = u
    texts = [strip_code(p if isinstance(p, str) else " ".join(x for x in p if x)) for p in parts]
    return [h for t in texts for h in scan_text(t, where, allow)]


def summarize(hits: list[Hit]) -> dict:
    by = {}
    for h in hits:
        by.setdefault((h.kind, h.term), 0)
        by[(h.kind, h.term)] += 1
    return dict(sorted(by.items(), key=lambda kv: -kv[1]))


def gate(label: str, hits: list[Hit], max_show: int = 12) -> str | None:
    """차단 메시지(jargon 있음) 또는 None. exaggerate는 호출자가 경고로 출력한다."""
    jar = [h for h in hits if h.kind == "jargon"]
    if not jar:
        return None
    lines = [f"[어휘 검사] {label} — 업무 사용자가 읽기 어려운 분석 작업 용어 {len(jar)}건이 있어 렌더를 멈춥니다"]
    for h in jar[:max_show]:
        lines.append(f"  × '{h.term}' → {h.plain} · …{h.context}…")
    if len(jar) > max_show:
        lines.append(f"  … 외 {len(jar) - max_show}건 — python3 .agents/skills/lima-agents/scripts/check_lexicon.py 로 전체 목록")
    lines.append("  고치는 법: 문구를 쉬운 말로 고친다. 꼭 필요한 용어는 설정 lexicon_allow {용어: 사유}에 사유와 함께 둔다")
    return "\n".join(lines)


def warn_lines(hits: list[Hit]) -> list[str]:
    return [f"  ⚠ 과장 표현 '{h.term}' — {h.plain} · …{h.context}…" for h in hits if h.kind == "exaggerate"]

# ── 자동 치환 (안전 목록) — 뜻이 1:1로 대응해 문장을 다시 쓰지 않아도 되는 용어만. 빌더가 출력 직전에 적용하고,
#    남는 jargon(문장을 다시 써야 하는 것: 짝 시드·'망의'·run·L1/L2·단계 코드·정본 등)은 gate가 차단한다.
#    긴 패턴 먼저. 대체어의 받침에 맞춰 뒤 조사를 고친다(허브는 → 진입점은).
STAGES = {"0b": "일반어 뜻 확인", "0": "일반어 뜻 확인", "1": "조합 검색어 전수 조회", "2": "검색결과 화면 증거 수집", "3": "세부 검색어 수확",
          "3b": "제품 여정 수집", "3c": "편익 세부 상황 분해", "4": "여정 수집", "5": "가설 확증", "6": "진입점 중복 판정"}
SAFE: list[tuple[str, str]] = [
    (r"(?:검색\s*)?(?:관계망|검색망|연관 키워드)\s*(\d+)\s*시드\s*(?:검색어\s*)?(\d[\d,]*)\s*(?:개|질의)", r"기준 검색어 \1개의 연관 키워드 \2개"),
    (r"(?:검색\s*)?(?:관계망|검색망)\s*(\d[\d,]*)\s*(?:개\s*)?(?:질의|쿼리)", r"연관 키워드 \1개"),
    (r"(?:검색\s*)?(?:관계망|검색망|연관 키워드)\s*검색어\s*(\d[\d,]*)\s*개", r"연관 키워드 \1개"),
    (r"(\d[\d,]*)\s*시드", r"기준 검색어 \1개"),
    (r"전\s*시드", "모든 기준 검색어"), (r"(\d[\d,]*)\s*(?:질의|쿼리)", r"검색어 \1개"),
    (r"(?:검색\s*)?(?:관계망|검색망)\s*군집", "연관 키워드 묶음"),  # '짝 시드'는 자동 치환하지 않는다 — '짝 시드했습니다'가 비문이 된다(2026-09-17 테스트에서 발견)
    (r"중립\s*(?:어|검색어)", "브랜드 없는 검색어"), (r"중립\s*시드", "브랜드 없는 기준 검색어"),
    (r"품질\s*게이트", "품질 점검"), (r"볼륨\s*합", "검색량 합"), (r"분석\s+run\b", "분석"), (r"정본\s*온톨로지", "확정 온톨로지"), (r"정본", "기준 데이터"),
    (r"검색\s*관계망|관계망|검색망", "연관 키워드"),
    (r"망(?=의|은|는|에서|에는|에|을|이|과|와|\s*안|\s*대비)", "연관 키워드"), (r"결합\s*쿼리|결합형\s*검색어|결합형", "상황+품목 검색어"),
    (r"고유\s*질의|고유\s*쿼리", "고유 검색어"), (r"질의|쿼리", "검색어"), (r"볼륨", "검색량"), (r"매칭", "일치"),
    (r"롱테일\s*코퍼스", "세부 검색어 집합"), (r"코퍼스", "수집 검색어"), (r"롱테일", "세부 검색어"), (r"헤드텀", "대표 검색어"),
    (r"군집", "키워드 묶음"), (r"캔버싱|캔버스", "조합 검색어 전수 조회"), (r"프로브", "연관어 탐색"),
    (r"블라인드", "데이터 미열람"), (r"자카드", "중복도"), (r"렉심", "핵심 어휘"), (r"게이트", "품질 점검"),
    (r"회색\s*허브", "근거 보강 필요 진입점"), (r"허브", "진입점"), (r"빈\s*슬롯", "빈 상황 요소"), (r"슬롯", "상황 요소"),
    (r"편익\s*앵커", "편익 기준 검색어"), (r"앵커", "기준 축"), (r"브리지", "연결 검색어"), (r"패밀리", "상황군"), (r"노드", "항목"), (r"표기\s*계층", "품목어·브랜드명 표기 구분"),
    (r"시드(?=\s*\d|\s*[‘'“(]|\s*(?:목록|수|별|당|로|를|은|는|가|이|와|과|중|에도|에서|에|의|재수확|·|,|\)|$))", "기준 검색어"),
]
SAFE_ASCII: list[tuple[str, str]] = [
    # 표기 구분 코드 — 표·문장 속 L1/L2/L3을 뜻으로 풀어 쓴다(겹침이 생기는 조합을 먼저)
    (r"\(L1\s*품목\s*일반어\)", "(품목 일반어)"), (r"\(L2\s*·\s*", "("), (r"\bL1\s*품목\s*일반어", "품목 일반어 표기"),
    (r"\bL2\s*브랜드-품목어", "브랜드명+품목어 표기"), (r"\bL1\s*품목어\s*표기", "품목어 표기"), (r"\bL2\s*브랜드\s*표기", "브랜드명 표기"),
    (r"\bL1\s*(‘[^’]+’)\s*표기", r"품목어 \1 표기"), (r"\bL1\s*\+\s*L2", "품목어+브랜드명 표기"), (r"\bL2\s*~\s*L3", "브랜드·모델명 표기"),
    (r"\bL1\(", "품목어("), (r"\bL2\(", "브랜드명("), (r"\bL3\s*모델어", "모델명 표기"),
    (r"\bL1\s+$", "품목어 "), (r"\bL1\s*([\d,]+)\s*대\s*L2\s*([\d,]+)", r"품목어 표기 \1 대 브랜드명 표기 \2"),
    (r"\bL2\s*대칭", "브랜드명 표기 대칭"), (r"\bL2\s*브랜드\s*(\d+)\s*종", r"브랜드명 표기 \1종"),
    # L1·L2·L3 단독은 치환하지 않는다 — 페이지 층 번호(L1 요약 → L2 카드 → L3 액션)로도 쓰여 뜻이 갈린다(2026-09-17 오역). 검사가 멈추고 사람이 고친다
    # 엔진 단계 코드
    (r"\s*\(S\d[a-c]?\)", ""), (r"엔진\s*S(\d[a-c]?)", lambda m: f"{STAGES.get(m.group(1), '분석')} 단계"),
    (r"\bS3\s*재수확", "세부 검색어 재수확"), (r"\bS0b\b", "일반어 뜻 확인"),
    (r"\bco_path\b", "동반 경로"), (r"\bAIO\b|\bAI Overview\b", "AI 검색 요약"), (r"\bPAA\b", "연관 질문"), (r"\bSERP\b|\bserp\b", "검색결과 화면"),
    (r"\bkeyword_info\b", "검색량 데이터"), (r"\bintent_finder\b", "연관 검색어 데이터"), (r"\bcluster_finder\b", "연관 키워드 데이터"),
    (r"\bpath_finder\b", "검색 여정 데이터"), (r"\bhop\s*(\d)\b", r"\1단계 연결"), (r"\bpost-hoc\b", "사후"),
    (r"--replay\s*재현", "원자료로 재계산 가능"), (r"\braw\s*동봉", "원자료 동봉"),
    (r"\bdeep\s+run\b", "심층 분석"), (r"\bquick\s+run\b", "간이 분석"), (r"\brun\b", "분석"),
    (r"\blimit\s*(\d[\d,]*)", r"수집 상한 \1"), (r"\blimit\b", "수집 상한"),
    (r"\bunsupported\b", "기각"), (r"\bsupported\b", "근거 있음"), (r"\bcandidate\b", "후보"), (r"\bconfirmed\b", "확정"), (r"\bdeferred\b", "보류"),
]
_SAFE = [(re.compile(_ab(_K + p)), r) for p, r in SAFE] + [(re.compile(_ab(p)), r) for p, r in SAFE_ASCII]
_PARTICLE = [("은", "는"), ("이", "가"), ("을", "를"), ("과", "와"), ("으로", "로"), ("이라", "라"), ("이다", "다"), ("이며", "며"), ("이고", "고"),
             ("이었", "였")]


def _batchim(ch: str) -> bool | None:
    if not ("가" <= ch <= "힣"):
        return None
    return (ord(ch) - 0xAC00) % 28 != 0


def _fix_particle(rep: str, rest: str) -> str:
    """대체어 끝 받침에 맞게 바로 뒤 조사를 고친다. rest는 대체어 뒤 문자열."""
    b = _batchim(rep[-1]) if rep else None
    if b is None:
        return rest
    rieul = rep and (ord(rep[-1]) - 0xAC00) % 28 == 8          # ㄹ 받침은 '로'
    for with_b, without_b in sorted(_PARTICLE, key=lambda x: -len(x[0])):
        for cand in (with_b, without_b):
            if rest.startswith(cand) and not re.match(r"[가-힣]", rest[len(cand):len(cand) + 1] or " ") or \
               (rest.startswith(cand) and cand in ("이라", "이다", "이며", "이고", "이었", "라", "다", "며", "고", "였")):
                want = without_b if (not b or (with_b == "으로" and rieul)) else with_b
                return want + rest[len(cand):]
    return rest


def _sub_outside_quotes(t: str, fn) -> str:
    parts = re.split(r"(‘[^’]{0,80}’|“[^”]{0,120}”|<code\b.*?</code>|https?://\S+|\b[\w./-]+\.(?:json|html|md|py|csv|jsonl)\b)", t, flags=re.S)
    return "".join(p if i % 2 else fn(p) for i, p in enumerate(parts))


def translate(text: str) -> str:
    """안전 목록 자동 치환 — 따옴표 안 소비자 검색어·code·URL·파일 경로는 그대로 둔다."""
    if not isinstance(text, str) or not re.search(r"[가-힣]|co_path|AIO|PAA|SERP|serp|_info|_finder|hop|run|limit|L[123]|S\d|supported|candidate|confirmed|deferred", text):
        return text
    def fn(seg):
        for rx, rep in _SAFE:
            out, pos = [], 0
            for m in rx.finditer(seg):
                r = rep(m) if callable(rep) else m.expand(rep)
                out.append(seg[pos:m.start()]); out.append(r)
                pos = m.end()
                paren = re.match(r"\([^()]{0,60}\)", seg[pos:])
                if paren:                                    # '연관 키워드(그 주제의 검색 표면)은' — 괄호 뒤 조사도 대체어 받침을 따른다
                    end = pos + paren.end()
                    tail = _fix_particle(r, seg[end:end + 3])
                    if tail != seg[end:end + 3]:
                        out.append(seg[pos:end] + tail); pos = end + 3
                    continue
                tail = _fix_particle(r, seg[pos:pos + 3])
                if tail != seg[pos:pos + 3]:
                    out.append(tail); pos += 3
            out.append(seg[pos:]); seg = "".join(out)
        return seg
    return _sub_outside_quotes(text, fn)


def translate_json(obj):
    if isinstance(obj, dict):
        return {k: (v if (k in SKIP_KEYS or k.startswith("_")) else translate_json(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [translate_json(v) for v in obj]
    return translate(obj) if isinstance(obj, str) else obj


def translate_html(html: str) -> str:
    """태그 밖 텍스트와 <script type="application/json"> 데이터에 적용. 일반 JS 코드는 건드리지 않는다."""
    def data_block(m):
        body = m.group(2)
        try:
            obj = json.loads(body.replace("<\\/", "</"))
        except json.JSONDecodeError:
            return m.group(0)
        return m.group(1) + json.dumps(translate_json(obj), ensure_ascii=False).replace("</", "<\\/") + m.group(3)
    html = re.sub(r'(<script[^>]*type="application/json"[^>]*>)(.*?)(</script>)', data_block, html, flags=re.S)
    parts = re.split(r"(<script.*?</script>|<style.*?</style>|<[^>]+>)", html, flags=re.S)
    return "".join(p if i % 2 else translate(p) for i, p in enumerate(parts))



# ── 빌더 연결 ────────────────────────────────────────────────────────────────
ALLOW_FLAG = "--allow-jargon"


def scan_html(html: str, where: str, allow: dict | None = None) -> list[Hit]:
    """화면 텍스트 + 페이지에 실린 데이터(<script type=application/json>) + 인라인 스크립트의 한글 문자열."""
    hits = scan_text(html, where, allow)
    for m in re.finditer(r"<script([^>]*)>(.*?)</script>", html, re.S):
        attrs, body = m.groups()
        if "application/json" in attrs:
            try:
                hits += scan_json(json.loads(body.replace("<\\/", "</")), where + "#data", allow)
            except json.JSONDecodeError:
                pass
        else:
            hits += scan_js(body, where + "#script", allow)
    return hits


def scan_js(src: str, where: str, allow: dict | None = None) -> list[Hit]:
    """인라인 스크립트 — 코드가 아니라 화면에 붙는 조각만: ${식}을 안쪽부터 지운 뒤 >텍스트<와 한글이 든 '…'·"…" 문자열."""
    src = re.sub(r"//[^\n]*|/\*.*?\*/", " ", src, flags=re.S)
    while True:
        u = re.sub(r"\$\{[^{}`]*\}", " ", src)
        if u == src:
            break
        src = u
    parts = re.findall(r">([^<>`]*[가-힣][^<>`]*)<", src) + re.findall(r"'([^'\n]*[가-힣][^'\n]*)'|\"([^\"\n]*[가-힣][^\"\n]*)\"", src)
    texts = [re.sub(r"\$\{.*", " ", p if isinstance(p, str) else " ".join(x for x in p if x), flags=re.S) for p in parts]
    return [h for t in texts for h in scan_text(t, where, allow)]


def _enforce(label: str, hits: list[Hit], allow_jargon: bool):
    for w in warn_lines(hits):
        print(w)
    msg = gate(label, hits)
    if msg:
        if not allow_jargon:
            raise SystemExit(msg)
        print(msg.replace("렌더를 멈춥니다", f"초안으로 렌더합니다({ALLOW_FLAG})"))
    else:
        print(f"어휘 검사 통과 — {label}")


def _readability():
    """제목·문장 검토 모듈 — 없는 설치(검토 기록부를 두지 않는 배포본)에서는 어휘 검사만 한다."""
    try:
        from . import readability as _rd
        return _rd
    except ImportError:
        return None


def finalize_html(label: str, html: str, allow: dict | None = None, allow_jargon: bool = False) -> str:
    """안전 목록 치환 → 어휘 검사 → 제목·문장 검토 기록 확인. 반환값을 파일로 쓴다."""
    import sys
    _rd = _readability()
    html = translate_html(html)
    _enforce(label, scan_html(html, label, allow), allow_jargon)
    if _rd:
        _rd.enforce_html(label, html, _rd.ALLOW_FLAG in sys.argv)
    return html


def finalize_json(label: str, obj, allow: dict | None = None, allow_jargon: bool = False):
    import sys
    _rd = _readability()
    obj = translate_json(obj)
    _enforce(label, scan_json(obj, label, allow), allow_jargon)
    if _rd:
        _rd.enforce_json(label, obj, _rd.ALLOW_FLAG in sys.argv)
    return obj
