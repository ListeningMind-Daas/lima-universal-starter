#!/usr/bin/env python3
"""CEP Finder Lite 엔진 v0.6 — 오케스트레이터 (+ S2 증거 · S3 롱테일 · S5 가설 선행).

경량판이다 — 서버 없이 세션 안에서 끝나는 단일 스크립트이며 스타터 팩·플러그인에 싣기 위한 판이다.
기능 추가는 별도 정본 엔진에서 하고, 이 판은 버그 수정과 스타터 호환 유지만 한다.
파일명은 바꾸지 않는다 — 지난 run들의 run_manifest.json argv와 스타터 재현 대조가 이 이름에 걸려 있다.

구현 범위(v0.1): 브리지-스파인 발굴 경로 전체 — S0 뜻·후보 로드 → S1 프로브·캔버싱 →
S2 시즌 → S3 상황측 여정 → S5 허브 조립 → 게이트 → 산출(hub_graph·manifest·summary·llm_tasks).
LLM 판단 구간(라벨 압축·서사·패밀리 세분·잔여 태깅)은 core/llm_tasks.json으로 위임한다 —
엔진은 수치를 만들고, 이름은 사람이/LLM이 승인 흐름에서 만든다(정의서 §4.4).

v0.2 (2026-08-22) — 제품 앵커 run의 방법론 문제 B1~B6 반영:
  --anchor-level product : 품목 run 허브 **상속** + 제품 앵커 path_finder(**전이형**)가 기본 스파인(B1)
  sense.alias_groups     : 라인·기능 별칭군을 분리 캔버스·시계열·성연령(B2)
  product_anchor 시드 역할: 적합률 게이트 면제 · 연관어 수(intent_finder)는 특성값으로 보고(B3)
  전이 지표              : 자사 앵커라 퇴화하는 브랜드 도달 대신 경쟁 동반률·자사 라인 분기(B4)
  패싯 대조 확장         : C3 외 Line·SpecDimension·Technology도 허브 후보에서 분리(B5)
  run 폴더명 슬러그화    : 공백 → '-'(B6)
v0.3 (2026-08-22) — 경쟁 Context 프레임 검토에서 드러난 갭:
  B7 스위칭 방향성        : 여정 내 자사→경쟁 / 경쟁→자사 / 왕복 순서와 스위치 직전 노드(트리거) 집계 — 세션 인접 집계이며 개인 이탈 아님
  B9 Context×브랜드 겹침  : 컨텍스트(4도어·대용량·1등급·키친핏·가격·후기…) × 브랜드 결합쿼리 볼륨 매트릭스 → 겹침 지수·무브랜드 여지(검색량 기준 근사)
v0.5 (2026-08-22) — 샘플 리포트 대조에서 드러난 갭:
  S2 증거  : serp(AIO·PAA·연관검색·자연결과) 시드당 30크레딧(SERP_COST · 2026-08-28 인상) · 인용 원문·수집시각 보존 · grade extracted
  S3 롱테일: intent_finder vt=0 (품목 + longtail_seeds + 공간 시드 T2) → ads_info 1/kw · 0볼륨은 언어층 보존 · 노이즈 플래그(개수·볼륨)
  S5 가설  : 가설 파일 없으면 core/hypothesis_tasks.json 발주(세션 LLM이 7W 서사 작성) → --hypotheses 로 확증 재실행:
             코퍼스 봉인 매칭 · supported/unsupported 보존 · 기각률 0% = 편향 경고 · 성립 요건 + HUB_FLOOR 통과만 허브 후보
v0.4 (2026-08-22) — B8 기능 앵커 모드 (--anchor-level feature):
  기능은 CEP가 아니라 Need와 Product 사이에 개입하는 엔티티. 기능 앵커 여정의 노드를 층(상황·KBF/컨텍스트·기능 변형·라인·
  자사/경쟁 브랜드·경쟁 기능·평가·구매)으로 분류하고 앵커 앞/뒤 위치로 사슬 순서를 측정(Feature Association) ·
  변형 계열·이해형(뜻·기능·차이) 캔버스 · 경쟁 기능은 assumption 등급 · 온톨로지 후보는 ontology_delta.jsonl(승인 대기)

v0.6 (2026-08-22) — 기능 앵커 캠페인 타겟팅 실측에서 드러난 갭(B13·B14·B15 일부):
  B14 기능 사전 병합  : 버티컬 `references/feature-benefit-map.json`(adapter A4.feature_lexicon)의 기능→편익→소비자 일반어→경쟁 대응→
                        '기능이 아닌 것'을 S0에서 sense에 병합(sense 우선) · S1c가 일반어 볼륨을 실측해 일반어/고유명 비율 보고
  B13 편익 7W 분해    : S3c — 분해 사전(who/when/what/while/where)으로 세부 상황 셀을 만들고 셀별 시드를 자동 생성해 수확(vt=0) →
                        셀 판정(검색 타겟 / 약한 신호 / 표현만 / 근거 없음) · 코퍼스 합류 · S5 발주·확증에 cell 연결(검색 타겟 vs 크리에이티브 소재)
  B15 스펙 경계       : not_this_feature 어휘를 S3·S3c·S5에서 off_feature 플래그 — 같은 라인의 다른 수요를 기능 볼륨에서 제외

v0.6.1 (2026-08-28) — 키워드 조인 버그 수정:
  LM API는 요청 키워드의 띄어쓰기를 정규화해 돌려준다(요청 '오토오픈도어' → 응답 '오토 오픈 도어').
  요청어 키로 응답을 찾던 모든 keyword_info 조인이 이 경우 조용히 실패해 실측 볼륨이 null로 기록되고,
  하류(ontology_delta·summary)에서 '수요 없음'으로 오독됐다. join_by_request()로 공백 제거·소문자 키
  재매칭을 _kwinfo(전 단계 — 변형·이해형·경쟁 기능·일반어·롱테일·서사 시드)와 S1 캔버싱에 일괄 적용하고,
  재매칭 건은 로그·run_manifest.keyword_rematch·competing_features.measured_as 로 남긴다.

v0.6.2 (2026-08-28) — S5 판정 개선 5건:
  ① supported/strong 판정을 실측(볼륨>0) 매칭 기준으로 — 언어층은 matched에 보존하되 근거에서 제외.
  ② --baseline-seeds 로 판정 후 재수확 매칭을 corpus_extended로 분리 · rejection_rate_baseline 병기
     (실측: 기각된 가설의 어휘로 시드를 넓히자 기각률이 0%로 내려간 사례).
  ③ G14를 순열 기준선 대비로 — 자기 예측어 매칭 vs 타 가설 예측어 매칭. 같으면 판정이 가설을 구별하지 못한다.
  ④ 발주 프롬프트에 예측어 길이 가드(2~3어절) + overspecified_n 집계·경고.
  ⑤ --measure-unmatched 로 미매칭 예측어 직접 실측(1크레딧/kw) — 코퍼스 수확 커버리지 교란 제거
     (미매칭 예측어 대부분이 실측 볼륨을 가진 가설과 거의 갖지 않은 가설이 갈렸다 → 커버리지 공백과 예측 실패를 가른다).

v0.6.3 (2026-08-28) — ⑥ 허브 볼륨합에서 품목·브랜드·패싯 일반어 분리:
  HUB_FLOOR가 브랜드·품목어 하나로 통과되던 사례가 있었다.
  kw_kind()로 매칭 키워드를 상황 근거/일반어로 가르고 --floor-basis situational(기본)로 상황 볼륨만 판정한다.
  일반어 판정은 **적극 판정된 것만** — 온톨로지 라벨(C2·C3·Line·SpecDimension·Technology·Brand·PurchaseForm)
  전체 일치 · 품목어 제거 후 라벨 일치 · 라벨 반복 제거 후 잔여 없음 · EVAL_TERMS. 그 외는 근거로 인정한다
  (슬롯 어휘 기준으로 뒤집어 설계하면 표현 차이로 멀쩡한 근거가 날아간다).
  같은 키워드가 여러 가설의 근거면 shared_with로 표기(중복 계상 가시화).

v0.6.4 (2026-08-28) — --match exact 추가(기본 아님) + 상황 근거 계기판:
  exact=완전 일치만. 검토 결과 **기본으로 삼지 않는다** — 근처 어휘 확장을 막는 대신 정당한 더-특정 형태도
  떨군다(더 특정한 상황 결합어가 탈락한 실측 사례). 판별력 개선도 제한적
  (타가설 통과율 B세트 100→88% · FH세트 100→100%). 민감도 분석용 진단 모드로 둔다.
  backing.situational_measured_n + "상황 근거 얇음" 경고는 **게이트가 아니라 계기판**이다 — 상황 실측 ≥3을
  강제하면 기존에 승인된 CEP가 탈락한다(2026-08-28 회귀 실측).

v0.6.5 (2026-08-28) — 발주 프롬프트에 **품목+상황어** 기준 추가:
  짧게 쓰라는 v0.6.2 가드(④)만으로는 예측어가 일반어로 흘러 판별력이 떨어졌다(일반어 위주 예측어로 상황 볼륨이 0이 된 사례). instruction·blind_rule에 "품목 + 상황어(공간·시점·생애사건·상태·제약·증상),
  품목 + 일반어(검토어·브랜드·라인·세그먼트·스펙·구매형태) 금지"를 명시하고, 발주 파일에 keyword_rules를
  온톨로지 라벨에서 생성해 싣는다(코퍼스 노출 아님 — 블라인드 안전). 판정 시 backing.generic_predicted_n으로
  준수 여부를 되재고 과반이면 "발주 규칙 위반" 경고. 경고는 로그 말미에도 출력한다.

경계: stdlib 전용(§16.3) — 브랜드 사전 파서만 reports/cep-finder/render.py에서 import. 재현: --replay DIR 로 0크레딧.

사용:
  python3 run_cep_finder.py "에어컨" kr --vertical listeningmind-universal \
      --sense-file sense.json --budget 20000
  python3 run_cep_finder.py "에어컨" kr --vertical listeningmind-universal \
      --replay 99_Scratch/<저장된 run 폴더>          # 오프라인 재실행
  python3 run_cep_finder.py "<브랜드 제품명>" kr --vertical listeningmind-universal \
      --anchor-level product --sense-file sense.json \
      --inherit-from 90_Output/<품목-run> --budget 6000   # 제품 앵커
"""
from __future__ import annotations

import argparse, collections, json, re, sys, time
from pathlib import Path
ENGINE_VERSION = "0.6.5"   # 머리말 변경 이력의 최신 버전과 맞춘다 — 매니페스트에 기록돼 판정 로직을 구분한다


def _sha(p):
    import hashlib
    try:
        return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]
    except OSError:
        return None

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SKILLS_ROOT = SKILL.parent
WORKSPACE = SKILLS_ROOT.parent.parent
sys.path.insert(0, str(SKILL))
from api.client import DaasClient                       # noqa: E402
from api import keyword_info, path_finder, intent_finder, serp   # noqa: E402
from lib.vertical import load_adapter                   # noqa: E402
sys.path.insert(0, str(SKILL / "reports/cep-finder"))
try:
    from render import load_brand_map                   # noqa: E402  (B4 — brand-map.md ×/○ 파서 재사용)
except Exception:                                       # noqa: BLE001
    load_brand_map = None

DEPTH = {  # 프리셋 — 정의서 §9
    "quick":    {"probe_seeds": 1, "journeys": 1, "path_limit": 100},
    "standard": {"probe_seeds": 2, "journeys": 2, "path_limit": 150},
    "deep":     {"probe_seeds": 3, "journeys": 4, "path_limit": 150},
}
BRIDGE_FLOOR = 100          # 결합쿼리 성립 최소 월볼륨 (초기값 · manifest 기록)
# serp 단가 — 키워드당 30크레딧(출력 무과금). 2026-08-28 실측 재확인(이전 10에서 인상) ·
# 2026-09-16 run 재확인: 8시드 240크레딧. 표시·예산 게이트가 반드시 이 값 하나를 쓴다.
# (이전에는 10이 문자열·check()에 흩어져 박혀 있어 --budget이 실제 비용의 1/3만 막았다)
SERP_COST = 30
HUB_FLOOR = 500             # 허브 성립 최소 볼륨합
FACET_CLASSES = ("C3", "Line", "SpecDimension", "Technology")   # B5 — 허브 후보에서 분리할 온톨로지 클래스
# ⑥ 허브 볼륨합에서 분리할 일반어 클래스 — 품목·세그먼트·라인·스펙·기술·브랜드·구매형태.
#    "<브랜드> <품목>"·"<세그먼트><품목>"은 상황 수요가 아니라 품목/브랜드 수요다(2026-08-28 실측).
#    Attribute 포함(2026-08-28 실측) — 가성비·추천·최저가는 검토 축이지 상황이 아니다("가성비 <품목>").
GENERIC_CLASSES = ("C2", "C3", "Line", "SpecDimension", "Technology", "Brand", "PurchaseForm", "Attribute")
EVAL_TERMS = ["후기", "단점", "비교", "가격", "추천", "vs"]        # 제품 앵커 평가형 결합(구매 후·검토 쿼리 — CEP 아님)
# B9 — 기본 컨텍스트 (가전 기본값 · sense.contexts로 덮어씀). pos=prefix: "{brand} {ctx} {category}" / suffix: "{brand} {category} {ctx}"
FEATURE_UNDERSTANDING = ["뜻", "기능", "란", "장단점", "단점", "후기", "차이"]   # B8 — 기능 이해·평가형 결합
LAYER_RX = {   # B8 — Feature Association 노드 층 (기본 어휘 · sense.layer_lexicon으로 덮어씀)
    # 모델 코드 = 구매 직전 "모델 선택" 층. 제조사 모델명 패턴(영문+숫자 조합)
    "model_code": r"^[a-z]{1,2}\d{3}[a-z]{2,3}\d{2,3}[a-z0-9]*( [a-z가-힣]+)?$|\b(rf|rs|rt|rb|rh|rz|rq)\d{2,3}[a-z0-9]*\b",
    "kbf_context": r"리터|\d+l\b|용량|사이즈|크기|치수|도어|양문형|1등급|에너지|효율|키친핏|빌트인|대용량|소형|색상|컬러|베이지|패널|디자인|수납|정수|얼음|소음",
    "eval": r"후기|단점|장단점|비교|\bvs\b|차이|뜻|기능|란$|추천|순위",
    "purchase": r"가격|최저가|모델|할인|세일|구매|렌탈|사는법|싸게|어디서",
}
DEFAULT_CONTEXTS = [("4도어", "prefix"), ("양문형", "prefix"), ("대용량", "prefix"), ("1등급", "prefix"), ("키친핏", "prefix"),
                    ("빌트인", "prefix"), ("소형", "prefix"), ("가격", "suffix"), ("후기", "suffix"), ("단점", "suffix"), ("추천", "suffix")]


# ── 키워드 조인 정규화 (2026-08-28) ──
# LM API는 요청 키워드의 띄어쓰기를 자체 정규화해 돌려준다 — 요청 '오토오픈도어' → 응답 '오토 오픈 도어',
# 요청 '맥북 에어 무게' → 응답 '맥북에어 무게'. 요청어 키로 응답을 찾으면 조인이 깨져 실측 볼륨이
# null로 기록되고, 이는 하류에서 '수요 없음'으로 오독된다(2026-08-28 실측 — 볼륨 3건 정정).
def norm_kw(x) -> str:
    """조인 키 — 공백 제거 · 소문자."""
    return re.sub(r"\s+", "", str(x or "")).lower()


def index_responses(items) -> tuple[dict, dict]:
    """응답 항목 리스트 → (응답어 그대로의 dict, 정규화 키 dict). 먼저 온 항목 우선."""
    exact, norm = {}, {}
    for it in items or []:
        if not isinstance(it, dict):
            continue
        k = it.get("keyword")
        if not k:
            continue
        exact.setdefault(k, it)
        norm.setdefault(norm_kw(k), it)
    return exact, norm


def join_by_request(items, kws) -> tuple[dict, list]:
    """응답을 **요청어 키**로 되맞춘다 — 정확 일치 우선 · 실패 시 정규화 키로 재매칭.
    반환: (요청어 키 dict(+매칭 안 된 응답어 키도 보존), 정규화로만 붙은 [(요청어, 응답어)] 목록)."""
    exact, norm = index_responses(items)
    out, rematched = {}, []
    for k in kws or []:
        it = exact.get(k)
        if it is None:
            it = norm.get(norm_kw(k))
            if it is not None:
                rematched.append((k, it.get("keyword")))
        if it is not None:
            out[k] = it
    for k, it in exact.items():          # 요청과 못 붙은 응답어도 남긴다(응답어 기준 조회 대비)
        out.setdefault(k, it)
    return out, rematched


def match_corpus(kws, ckeys, corpus, mode="loose") -> list:
    """예측어를 봉인 코퍼스에 매칭 — exact=완전 일치만 · strict=+접두/접미(≤2) · loose=+부분 문자열(≤3).

    가설 루프와 순열 기준선(G14)이 같은 함수를 쓴다 — 기준선이 본 판정과 다른 규칙이면 비교가 무의미하다."""
    n_ = lambda s: re.sub(r"\s+", "", str(s)).lower()
    out, seen = [], set()
    for k in kws or []:
        nk = n_(k)
        if nk in ckeys:
            hits = [corpus[ckeys[nk]]]
        elif mode == "exact":
            hits = []                                     # 완전 일치만 — 근처 어휘로 근거를 불리지 않는다(⑤ 직접 실측과 짝)
        elif mode == "strict":
            hits = [corpus[q] for nq, q in ckeys.items() if len(nk) >= 5 and (nq.startswith(nk) or nq.endswith(nk))][:2]
        else:
            hits = [corpus[q] for nq, q in ckeys.items() if len(nk) >= 4 and nk in nq][:3]
        for m in hits:
            if m["q"] not in seen:
                seen.add(m["q"]); out.append(m)
    return out


class Ledger:
    """크레딧 원장 — 호출 전 예산 확인, cost_detail 합산 (§13)."""
    def __init__(self, budget: int | None):
        self.budget = budget
        self.spent = 0
        self.calls: list[dict] = []

    def check(self, estimate: int, what: str):
        if self.budget and self.spent + estimate > self.budget:
            raise SystemExit(f"[budget] {what} 예상 {estimate} — 잔여 {self.budget - self.spent} 미만. 중단")

    def add(self, tool: str, params: dict, resp: dict):
        c = (resp.get("cost_detail") or {}).get("total_cost", 0)
        self.spent += c
        self.calls.append({"tool": tool, "params": params, "cost": c})
        return c


class Engine:
    def __init__(self, a):
        self.a = a
        self.category, self.gl = a.category, a.gl
        self.adapter = load_adapter(a.vertical, SKILLS_ROOT)
        # 카테고리 커버리지 — ready ≠ "이 품목에 쓸 수 있다". 미등재면 A2·A3 partial → [준비도] 배너·warnings (2026-09-17)
        # product·feature 앵커는 제품/기능명이 사전 단위가 아니므로 sense.category(부모 품목)로 본다
        cov_cat = self.category
        if a.anchor_level != "category" and a.sense_file:
            try:
                cov_cat = json.loads(Path(a.sense_file).read_text(encoding="utf8")).get("category") or self.category
            except (OSError, json.JSONDecodeError):
                pass
        self.adapter.check_category_coverage(cov_cat)
        # 사전 공백은 실패가 아니라 사용자 결정이다 (2026-09-17) — 크레딧을 쓰는 실측 run은 지출 전에 묻는다.
        self.dict_gap = [i for sid in ("A2_noise_lexicon", "A3_entity_authority")
                         for i in (self.adapter.report["slots"].get(sid, {}).get("issues") or []) if "미등재" in str(i)]
        gap_choice = getattr(a, "on_dictionary_gap", "ask")
        if self.dict_gap and gap_choice == "ask" and not a.replay and not a.dry_run:
            print("[사전 공백] 이 품목의 사전(브랜드·품목 어휘)이 비어 있거나 부족합니다 — 크레딧을 쓰기 전에 멈춥니다.\n"
                  + "\n".join(f"  · {i}" for i in self.dict_gap)
                  + "\n사용자에게 묻는다(AskUserQuestion): 사전을 채울까요, 건너뛰고 진행할까요?"
                  + "\n  채우기  → 어댑터 사전(E0·brand-map)에 품목·브랜드를 채운 뒤 같은 명령으로 재실행"
                  + "\n  건너뛰기 → 같은 명령에 --on-dictionary-gap skip (산출물에 '사전 생략 · 잠정'이 남는다)", file=sys.stderr)
            raise SystemExit(10)
        self.ledger = Ledger(a.budget)
        self.replay = Path(a.replay).resolve() if a.replay else None
        self.client = None
        if not self.replay and not a.dry_run:
            self.client = DaasClient()                  # 키: api.client.resolve_api_key()
        ts = time.strftime("%Y%m%d-%H%M")
        self.run_id = f"{re.sub(r'[^0-9A-Za-z가-힣]+','-',self.category)}-{self.gl}-curr-{ts}"
        slug = re.sub(r"\s+", "-", self.category.strip())                      # B6 — 폴더명 공백 제거
        self.out = Path(a.out) / f"{time.strftime('%Y%m%d')}-{slug}-{self.gl}-cepfinder"
        self.product = a.anchor_level in ("product", "feature")     # 제품·기능 앵커 공통 스파인
        self.feature = (a.anchor_level == "feature")
        self.brand_rx = {}
        for d in ("raw", "core", "out", "logs"):
            (self.out / d).mkdir(parents=True, exist_ok=True)
        self.log_lines: list[str] = []
        self.gates: list[dict] = []
        self.warnings: list[str] = []
        self.rematched: list[dict] = []          # API 띄어쓰기 정규화로 되붙인 (요청어, 응답어) — manifest 기록
        self.canon = self.canon_preflight(cov_cat)

    def canon_preflight(self, category: str) -> dict | None:
        """정본 해석을 **수집 전에** 한다. 2026-09-17 실측: 품목의 주요 브랜드가 정본에 없는 채로 수집 크레딧을 쓴 분석이 있었고,
        정본 해석은 렌더 직전(gates.refresh)에만 돌았다. COVERED면 진행, 외부 열거 원자료가 없으면(UNRESOLVED) SERP 2쿼리(60크레딧)로
        D1을 먼저 하고 재판정, PARTIAL·ABSENT면 정본 작업 명령서를 쓰고 사용자 결정을 받는다(종료 코드 10 · --on-dictionary-gap skip이면 진행).
        replay·dry-run·--canon-preflight off는 건너뛴다(저장본 재실행은 크레딧을 쓰지 않는다)."""
        a = self.a
        if self.replay or a.dry_run or getattr(a, "canon_preflight", "on") == "off":
            return None
        resolver = None   # 이 패키지에는 정본 해석기가 없다
        if resolver is None:
            # 정본 해석기가 없는 설치(스타터 등) — 수집 전 판정은 건너뛰고 렌더 단계 게이트(gates.auto_canon)가 사용자에게 묻는다
            self.log("정본 해석(수집 전) — 해석기가 없는 설치라 건너뜀 · 렌더 전 게이트에서 확인")
            return None
        sys.path.insert(0, str(resolver.parent))
        import canon_resolve as cr                                        # noqa: E402
        cdir = self.out / "canon"
        cdir.mkdir(parents=True, exist_ok=True)
        data = Path(a.inherit_from).resolve() if getattr(a, "inherit_from", None) else None
        res = cr.resolve(a.vertical, category, self.gl, data)
        if res["state"] == "UNRESOLVED":
            for q in (category, f"{category} 추천"):
                f = self.out / "raw" / f"serp_{q.replace(' ', '_')}.json"
                if f.exists():
                    continue
                self.ledger.check(30, f"정본 해석 D1 serp '{q}'")
                r = serp.fetch(self.client, q, gl=self.gl)
                self.ledger.add("serp", {"keyword": q, "stage": "canon_preflight_d1"}, r)
                f.write_text(json.dumps(r, ensure_ascii=False), encoding="utf8")
            res = cr.resolve(a.vertical, category, self.gl, self.out)
        (cdir / "canon_resolution.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf8")
        if "work_order" in res:
            (cdir / f"{res['work_order']['id']}.json").write_text(json.dumps(res["work_order"], ensure_ascii=False, indent=2), encoding="utf8")
        self.log(f"정본 해석(수집 전) — {res['state']} · " + " · ".join(f"{k} {v['status']}" for k, v in res["checks"].items()))
        if res["state"] in ("PARTIAL", "ABSENT"):
            gaps = [d.get("name") for d in (res["checks"].get("R3") or {}).get("disagreements") or []]
            if getattr(a, "on_dictionary_gap", "ask") == "ask":
                print(f"[정본 공백] 정본이 '{category}'를 덮지 않습니다({res['state']}) — 수집 크레딧을 쓰기 전에 멈춥니다."
                      + (f"\n  정본에 없는 이름: {', '.join(map(str, gaps[:12]))}" if gaps else "")
                      + f"\n  정본 작업 명령서: {cdir}/{res['work_order']['id']}.json (추정 {res['work_order']['budget']['estimate']}크레딧)"
                      + "\n사용자에게 묻는다(AskUserQuestion): 정본 작업으로 채울까요, 건너뛰고 진행할까요?"
                      + "\n  채우기  → 정본(브랜드 사전·E0)을 채운 뒤 같은 명령으로 재실행"
                      + "\n  건너뛰기 → 같은 명령에 --on-dictionary-gap skip (산출물에 '정본 공백 · 잠정'이 남는다)", file=sys.stderr)
                raise SystemExit(10)
            self.warnings.append(f"정본 공백을 건너뛰고 진행({res['state']}) — 정본에 없는 이름: {', '.join(map(str, gaps[:12]))}")
        return res

    def _log_rematch(self, pairs: list, what: str):
        """정규화 재매칭 기록 — 조인이 요청어 그대로 붙지 않은 건은 로그·manifest에 남긴다(무성 실패 금지)."""
        if not pairs:
            return
        self.rematched += [{"what": what, "requested": a, "returned": b} for a, b in pairs]
        head = " · ".join(f"{a}→{b}" for a, b in pairs[:6]) + (" …" if len(pairs) > 6 else "")
        self.log(f"  ↔ [{what}] API 띄어쓰기 정규화 재매칭 {len(pairs)}건: {head}")

    # ── 온톨로지 패싯 라벨 (B5 — C3 + Line·SpecDimension·Technology) ──
    def facet_labels(self) -> dict:
        """{정규화 라벨: 클래스}. 세그먼트(C3)뿐 아니라 라인·스펙·기술도 상황 허브가 아니다."""
        if not hasattr(self, "_facets"):
            self._facets = {}
            f = self.adapter.path("A4_ontology_binding", "files", "nodes")
            if f:
                norm = lambda t: re.sub(r"\s+", "", str(t)).lower()
                for line in f.read_text(encoding="utf8").splitlines():
                    if not line.strip():
                        continue
                    try:
                        n = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if n.get("class") in FACET_CLASSES:
                        for a in [n.get("label", "")] + list(n.get("aliases") or []):
                            if len(norm(a)) >= 2:
                                self._facets.setdefault(norm(a), n["class"])
        return self._facets

    def generic_labels(self) -> dict:
        """{정규화 라벨: 클래스} — ⑥ 상황 근거에서 분리할 품목·브랜드·패싯 어휘(주석용 · facet_labels보다 넓다)."""
        if not hasattr(self, "_generics"):
            self._generics = {}
            f = self.adapter.path("A4_ontology_binding", "files", "nodes")
            if f:
                for line in f.read_text(encoding="utf8").splitlines():
                    if not line.strip():
                        continue
                    try:
                        n = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if n.get("class") in GENERIC_CLASSES:
                        for a in [n.get("label", "")] + list(n.get("aliases") or []):
                            if len(norm_kw(a)) >= 2:
                                self._generics.setdefault(norm_kw(a), n["class"])
        return self._generics

    def kw_kind(self, q: str, cat_tokens: set) -> tuple:
        """⑥ 매칭 키워드 1건을 (상황 근거 | 일반어)로 가른다.

        **뺄 수 있는 것만 뺀다** — 온톨로지 라벨로 일반어라고 적극 판정되는 것만 제외하고 나머지는 근거로 인정한다.
        반대로(슬롯 어휘를 담은 것만 인정) 설계하면 슬롯 표현과 검색어 표현이 다를 때 멀쩡한 근거가 날아간다
        (2026-08-28 실측: 검색어 표현과 슬롯 표현이 같은 뜻인데 어휘가 다른 사례).

        일반어 판정 3가지: ① 키워드 전체가 라벨(<세그먼트 품목>) ② 품목어를 떼면 아무것도 안 남음
        ③ 품목어를 뗀 나머지가 브랜드·패싯 라벨(<브랜드> <품목> → 브랜드 · 중고 <품목> → 중고 · <라인> <품목> → 라인)."""
        nq = norm_kw(q)
        g = self.generic_labels()
        if nq in g:
            return "generic", g[nq]
        rest = nq
        for c in sorted(cat_tokens, key=len, reverse=True):
            rest = rest.replace(norm_kw(c), "")
        if not rest:
            return "generic", "Category"
        if rest in g:
            return "generic", g[rest]
        hit = []                                          # 라벨을 반복해서 떼어 본다 — "<브랜드> <라인> <품목>" = Brand + Line
        for lab in sorted(g, key=len, reverse=True):
            if len(lab) >= 2 and lab in rest:
                rest = rest.replace(lab, ""); hit.append(g[lab])
                if not rest: break
        if not rest and hit:
            return "generic", "+".join(dict.fromkeys(hit))
        if rest in {norm_kw(x) for x in EVAL_TERMS}:      # 추천·비교·후기·가격·단점 — 검토 쿼리이지 상황이 아니다
            return "generic", "EvalTerm"
        return "situational", None

    def facet_class(self, combo: str):
        """결합형 전체가 패싯 라벨과 일치하면 그 클래스, 아니면 None."""
        return self.facet_labels().get(re.sub(r"\s+", "", combo).lower())

    def is_segment_facet(self, combo: str) -> bool:
        return self.facet_class(combo) is not None

    # ── 유틸 ──
    def log(self, msg):
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        print(line); self.log_lines.append(line)

    def gate(self, gid, name, verdict, detail):
        self.gates.append({"gate": gid, "name": name, "verdict": verdict, "detail": detail})
        self.log(f"  [{gid} {verdict}] {name} — {detail}")

    def save_raw(self, name, obj):
        """raw 저장 — 같은 이름이 이미 있으면 덮어쓰지 않고 _2, _3… 으로 저장(보충 실측 누적 보존 · 2026-08-22 충돌 버그 수정)."""
        f = self.out / "raw" / f"{name}.json"; i = 2
        while f.exists():
            f = self.out / "raw" / f"{name}_{i}.json"; i += 1
        f.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf8")

    # ── S0 · 뜻 고정과 세계지식 후보 ──
    def s0_candidates(self) -> dict:
        self.log("S0 뜻 고정·상황 후보")
        self.feature_entry = None; self.decomp_lexicon = None; self.off_re = None
        for b in self.adapter.banner():
            self.log("  [준비도] " + b); self.warnings.append(b)
        fams = dict(self.adapter.get("A4_ontology_binding", "context_lexicon") or {})
        fams.pop("spaces", None)
        sense = {}
        if self.a.sense_file:
            sense = json.loads(Path(self.a.sense_file).read_text(encoding="utf8"))
            for fam, terms in (sense.get("families") or {}).items():
                fams.setdefault(fam, [])
                fams[fam] = list(dict.fromkeys(list(fams[fam]) + list(terms)))
            self.log(f"  세계지식 후보 병합: {list((sense.get('families') or {}))}")
        else:
            w = "세계지식 후보 미제공(--sense-file) — 어댑터 사전만 캔버싱: 사전 맹점 위험(정의서 N6)"
            self.log("  ⚠ " + w); self.warnings.append(w)
        out = {"families": fams, "excludes": sense.get("excludes", []), "sense": sense.get("sense", "")}
        for k in ("longtail_seeds", "space_seeds", "evidence_seeds", "alias_groups", "own_brand", "own_lines", "competitors"):   # v0.5 — 전 모드 통과
            if sense.get(k) is not None: out[k] = sense[k]
        if self.product:                                   # B2 — 별칭군·자사 라인·품목 앵커
            out["alias_groups"] = dict(sense.get("alias_groups") or {})
            out["own_brand"] = sense.get("own_brand") or ""
            out["own_lines"] = list(sense.get("own_lines") or [])
            out["parent_category"] = sense.get("category") or ""
            out["eval_terms"] = list(sense.get("eval_terms") or EVAL_TERMS)
            for k in ("feature_variants", "understanding_terms", "competing_features", "layer_lexicon", "consumer_terms", "benefit", "benefit_keywords", "not_this_feature"):
                if sense.get(k) is not None: out[k] = sense[k]
            if self.feature:
                self._merge_feature_lexicon(out, sense)                                             # v0.6 B14
            if self.feature and not out["alias_groups"] and out.get("feature_variants"):
                out["alias_groups"] = {f"{self.category}(기능 변형)": list(out["feature_variants"])}
            if not out["alias_groups"]:
                out["alias_groups"] = {"anchor": [self.category]}
                w = "alias_groups 미제공 — 앵커 단일 군으로 캔버스 (라인·기능 분리 불가, B2)"
                self.log("  ⚠ " + w); self.warnings.append(w)
            self.log(f"  [product] 별칭군 {list(out['alias_groups'])} · 자사 {out['own_brand'] or '?'} · 라인 {out['own_lines']} · 품목 {out['parent_category'] or '?'}")
        nt = [x for x in (out.get("not_this_feature") or []) if x]
        self.off_re = re.compile("|".join(re.escape(x.lower()) for x in sorted(nt, key=len, reverse=True)), re.I) if nt else None   # v0.6 B15
        return out

    # ══════════ v0.6 — B14 소비자 일반어 동음이의 검증 (s0b) ══════════
    def s0b_sense_check(self, sense: dict) -> dict:
        """소비자 일반어(consumer_terms)마다 path_finder 경로를 받아 앵커 외 노드를 동음이의(homonym)/기능(feature)/기타로 분류 → 기능 의미 비중.
        판정: confirmed ≥0.6 · ambiguous 0.3~0.6 · homonym <0.3 · 볼륨 없는 어휘는 미측정. 결과는 S3(시드 가중)·S3c(기능 연결 어휘)·S1c(환산 볼륨)에 쓰인다.
        일반어는 AI 요약이 아니라 여정으로 검증한다 — AI 요약은 기능으로 해석해도 여정은 다른 문맥일 수 있다."""
        terms = list(sense.get("consumer_terms") or [])
        if not self.feature or not terms or self.a.no_sense_check:
            return {"measured": False, "note": "feature 모드 전용" if not self.feature else ("--no-sense-check" if self.a.no_sense_check else "consumer_terms 없음")}
        rules = sense.get("sense_rules") or {}
        hom = [(n, re.compile(rx, re.I)) for n, rx in (rules.get("homonym") or {}).items()]
        feat_rx = re.compile(rules.get("feature") or "|".join(re.escape(x.lower()) for x in (sense.get("feature_variants") or [self.category]) + [self.category]), re.I)
        got = self._kwinfo(terms, "ads_metrics", "일반어 볼륨(동음이의 검증 전)", "consumer_terms_ads_metrics")
        lim = self.a.sense_paths; res = {}
        self.log(f"S0b 일반어 동음이의 검증 — {len(terms)}어휘 × path_finder limit={lim} (50+40×고유 키워드) · 규칙 homonym {[n for n, _ in hom]}")
        for term in terms:
            v = ((got.get(term) or {}).get("ads_metrics") or {}).get("volume_avg")
            if not v:
                res[term] = {"volume": v, "verdict": "unmeasured", "note": "볼륨 없음 — 여정 미조회"}; self.log(f"  [{term}] 볼륨 없음 → 미측정"); continue
            name = f"paths_{self._slug(term)}"; r = self._load_raw_or(name)
            if r is None:
                if self.a.dry_run or (self.replay and not self.a.replay_topup):
                    res[term] = {"volume": v, "verdict": "unmeasured", "note": "replay/dry-run — 여정 미수집"}; self.log(f"  [replay] path_finder({term}) 미수집"); continue
                self.ledger.check(50 + 40 * min(lim * 3, 300), f"동음이의 검증 {term}")
                r = path_finder.fetch(self._client(), term, gl=self.gl, limit=lim)
                self.ledger.add("path_finder", {"kw": term, "limit": lim, "what": f"동음이의 검증 {term}"}, r); self.save_raw(name, r)
            paths = r.get("data") or []; mc = collections.Counter(); prev = collections.Counter(); nxt = collections.Counter()
            for pa in paths:
                if term not in pa: continue
                i = pa.index(term); others = " ".join(x for x in pa if x != term)
                if i > 0: prev[pa[i - 1]] += 1
                if i < len(pa) - 1: nxt[pa[i + 1]] += 1
                m = next((n for n, rx in hom if rx.search(others)), None)
                mc[m or ("feature" if feat_rx.search(others) else "other")] += 1
            n = sum(mc.values()) or 1; share = mc.get("feature", 0) / n
            verdict = "confirmed" if share >= 0.6 else ("ambiguous" if share >= 0.3 else "homonym")
            res[term] = {"volume": v, "n_paths": n, "feature_share": round(share, 3), "adjusted_volume": round(v * share), "counts": dict(mc), "verdict": verdict,
                         "prev": prev.most_common(5), "next": nxt.most_common(5), "raw_file": f"raw/{name}.json", "grade": "derived",
                         "note": "경로의 앵커 외 노드를 어휘 규칙으로 분류 — 경계 사례는 사람이 검토"}
            self.log(f"  [{term}] {v:,} · {n}경로 → 기능 {share:.0%} {dict(mc)} → {verdict}" + (f" · 환산 {round(v * share):,}" if verdict != "confirmed" else ""))
            if verdict == "homonym":
                self.warnings.append(f"소비자 일반어 '{term}' 동음이의 — 여정 기준 기능 의미 {share:.0%}: 볼륨은 환산값({round(v * share):,})으로, 기능 연결 어휘에서 제외")
        sense["consumer_term_sense"] = res
        sense["consumer_terms_confirmed"] = [x for x in terms if res.get(x, {}).get("verdict") in ("confirmed", "ambiguous")]
        return {"measured": any(x.get("n_paths") for x in res.values()), "terms": res, "rule_source": "sense_rules(기능 사전)" if rules else "feature_variants(기본)",
                "thresholds": {"confirmed": 0.6, "ambiguous": 0.3}, "note": "일반어의 의미는 AI 요약이 아니라 검색 여정으로 확인 — homonym 판정 어휘는 환산 볼륨·기능 연결 제외"}

    # ══════════ v0.6 — B14 기능→편익→일반어 사전 ══════════
    def _load_feature_lexicon(self):
        p = self.adapter.path("A4_ontology_binding", "feature_lexicon")
        if not p: return None
        try: return json.loads(p.read_text(encoding="utf8"))
        except (OSError, json.JSONDecodeError): return None

    def _merge_feature_lexicon(self, out: dict, sense: dict):
        """B14 — 버티컬 기능 사전(feature-benefit-map.json)을 sense에 병합. sense 값이 우선, 사전은 보충.
        소비자 일반어·편익 키워드는 S3 시드와 S2 증거 시드에 자동 합류 · 경쟁 대응 기능은 competing_features에 등급 보존 · not_this_feature는 off_feature 플래그 원천."""
        lex = self._load_feature_lexicon()
        if not lex:
            w = "기능 사전(A4.feature_lexicon) 없음 — 소비자 일반어·편익·경쟁 대응 미병합(B14): sense로만 실행"
            self.log("  ⚠ " + w); self.warnings.append(w); return
        key = self.category.lower().replace(" ", "")
        for e in lex.get("features") or []:
            names = [e.get("feature", "")] + list(e.get("variants") or []) + list(e.get("aliases") or [])
            if any(n and key == n.lower().replace(" ", "") for n in names):
                self.feature_entry = e; break
        if self.feature_entry and not out.get("parent_category") and self.feature_entry.get("category"):
            out["parent_category"] = self.feature_entry["category"]
        dl = lex.get("decomposition_lexicon") or {}
        self.decomp_lexicon = dl.get(out.get("parent_category") or "") or dl.get("_default")
        if not self.feature_entry:
            w = f"기능 사전에 '{self.category}' 항목 없음 — 일반어·편익 미병합(B14): references/feature-benefit-map.json 에 추가 필요"
            self.log("  ⚠ " + w); self.warnings.append(w); return
        e = self.feature_entry
        uniq = lambda *ls: list(dict.fromkeys([x for l in ls for x in (l or []) if x]))
        out["consumer_terms"] = uniq(sense.get("consumer_terms"), e.get("consumer_terms"))
        out["benefit"] = sense.get("benefit") or e.get("benefit")
        out["benefit_keywords"] = uniq(sense.get("benefit_keywords"), e.get("benefit_keywords"))
        out["not_this_feature"] = uniq(sense.get("not_this_feature"), e.get("not_this_feature"))
        out["benefit_lexemes"] = uniq(sense.get("benefit_lexemes"), e.get("benefit_lexemes"))
        out["sense_rules"] = sense.get("sense_rules") or e.get("sense_rules") or {}
        if not out.get("feature_variants") and e.get("variants"):
            out["feature_variants"] = list(e["variants"])
        comps = list(out.get("competing_features") or [])
        have = {(c["feature"] if isinstance(c, dict) else c) for c in comps}
        for c in e.get("competitor_equivalents") or []:
            if c.get("feature") and c["feature"] not in have:
                comps.append({"brand": c.get("brand"), "feature": c["feature"], "note": f"기능 사전 · {c.get('source') or ''}", "grade": c.get("grade") or "assumption"})
        out["competing_features"] = comps
        out["longtail_seeds"] = uniq(out.get("longtail_seeds"), [x for x in out["consumer_terms"] + out["benefit_keywords"] if x != self.category])
        out["evidence_seeds"] = uniq(out.get("evidence_seeds"), out["consumer_terms"][:2])
        out["feature_lexicon"] = {"id": e.get("id"), "brand": e.get("brand"), "consumer_terms": out["consumer_terms"], "benefit": out["benefit"],
                                  "benefit_keywords": out["benefit_keywords"], "competitor_equivalents": e.get("competitor_equivalents") or [],
                                  "not_this_feature": out["not_this_feature"], "source": e.get("source")}
        self.log(f"  [B14] 기능 사전 병합 {e.get('id')} — 일반어 {out['consumer_terms']} · 편익 '{(out['benefit'] or '')[:40]}' · 경쟁 대응 {[c['feature'] for c in comps if isinstance(c, dict)]} · 기능 외 어휘 {len(out['not_this_feature'])}")

    def build_combos(self, families: dict) -> dict:
        """상황어 → 결합형. S1(수집)과 G3(커버리지)가 반드시 같은 규칙을 공유한다."""
        combos = {}
        for fam, terms in families.items():
            for t in terms:
                if "{}" in t:                       # 명시적 자리표시자
                    combos[t.format(self.category)] = fam
                elif self.category in t:            # 카테고리를 이미 포함한 완성형 (예: 에어컨 수리)
                    combos[t] = fam
                else:                               # 기본: 상황어 + 카테고리
                    combos[f"{t} {self.category}"] = fam
        return combos

    # ── S1 · 캔버싱 (브리지-스파인 — 관계망보다 먼저) ──
    def s1_canvass(self, families: dict) -> dict:
        combos = self.build_combos(families)
        self.log(f"S1 캔버싱 — 패밀리 {len(families)} · 결합형 {len(combos)} (1크레딧/건)")
        if self.replay:
            saved = json.loads((self.replay / "canvass.json").read_text(encoding="utf8"))
            if "canvass" not in saved and isinstance(saved.get("data"), list):      # 엔진 raw 원본 형식 → 파일럿 형식으로 변환
                got, rem = join_by_request(saved["data"], list(combos))
                self._log_rematch(rem, "캔버싱(저장본)")
                req = {norm_kw(x) for x in (saved.get("request_detail", {}).get("keywords") or combos)}
                saved = {"canvass": {k: {"family": fam, "v": ((got.get(k) or {}).get("ads_metrics") or {}).get("volume_avg"),
                                         "trend": ((got.get(k) or {}).get("ads_metrics") or {}).get("volume_trend")} for k, fam in combos.items()
                                     if k in got or norm_kw(k) in req},
                         "cost": saved.get("cost_detail", {}).get("total_cost"), "season": {}}
                hf = self.replay / "head_ads_info.json"
                if hf.exists():
                    d = (json.loads(hf.read_text(encoding="utf8")).get("data") or [{}])[0]
                    mv = d.get("monthly_volume") or []
                    if mv:
                        bym = {}
                        for m in mv:
                            bym.setdefault(int(m["month"][5:7]), []).append(m["total"])
                        avg = {k: sum(v) / len(v) for k, v in bym.items()}; base = sum(avg.values()) / len(avg)
                        saved["season"] = {str(k): round(avg[k] / base, 3) for k in sorted(avg)}
                self.log("  [replay] 엔진 raw 원본 형식 인식 — 파일럿 형식으로 변환")
            rows = {k: dict(v, family=v.get("family")) for k, v in saved["canvass"].items()}
            self.log(f"  [replay] 저장본 {len(rows)}건 재사용 (기록 비용 {saved.get('cost')})")
            missing = {k: fam for k, fam in combos.items() if k not in rows}
            if missing and self.a.replay_topup:
                self.client = self.client or DaasClient()
                self.ledger.check(len(missing), "캔버싱 보충")
                r = keyword_info.fetch_batch(self.client, list(missing), gl=self.gl, data_type="ads_metrics")
                self.ledger.add("keyword_info", {"n": len(missing), "dt": "ads_metrics", "topup": True}, r)
                got, rem = join_by_request(r.get("data"), list(missing))
                self._log_rematch(rem, "캔버싱 보충")
                for k, fam in missing.items():
                    m = (got.get(k) or {}).get("ads_metrics") or {}
                    rows[k] = {"family": fam, "v": m.get("volume_avg"), "trend": m.get("volume_trend")}
                saved["canvass"] = {k: {kk: vv for kk, vv in v.items()} for k, v in rows.items()}
                (self.replay / ("canvass_replay.json" if "data" in json.loads((self.replay / "canvass.json").read_text(encoding="utf8")) else "canvass.json")).write_text(json.dumps(saved, ensure_ascii=False), encoding="utf8")
                self.log(f"  [topup] 부족분 {len(missing)}건 라이브 보충 · 저장본 갱신")
            season = saved.get("season") or {}
            return {"rows": rows, "season": season, "coverage": sorted(set(v['family'] for v in rows.values()))}
        if self.a.dry_run:
            self.log(f"  [dry-run] keyword_info ads_metrics × {len(combos)} ≈ {len(combos)}크레딧")
            return {"rows": {}, "season": {}, "coverage": sorted(families)}
        self.ledger.check(len(combos) + 1, "캔버싱")
        r = keyword_info.fetch_batch(self.client, list(combos), gl=self.gl, data_type="ads_metrics")
        self.ledger.add("keyword_info", {"n": len(combos), "dt": "ads_metrics"}, r)
        self.save_raw("canvass", r)
        got, rem = join_by_request(r.get("data"), list(combos))
        self._log_rematch(rem, "캔버싱")
        rows = {k: {"family": fam, "v": ((got.get(k) or {}).get("ads_metrics") or {}).get("volume_avg"),
                    "trend": ((got.get(k) or {}).get("ads_metrics") or {}).get("volume_trend")} for k, fam in combos.items()}
        # 시즌 지수 (헤드텀 ads_info 1크레딧)
        r2 = keyword_info.fetch_batch(self.client, [self.category], gl=self.gl, data_type="ads_info")
        self.ledger.add("keyword_info", {"n": 1, "dt": "ads_info"}, r2)
        self.save_raw("head_ads_info", r2)
        season = {}
        d = (r2.get("data") or [{}])[0]
        mv = d.get("monthly_volume") or []
        if mv:
            bym = {}
            for m in mv:
                bym.setdefault(int(m["month"][5:7]), []).append(m["total"])
            avg = {k: sum(v) / len(v) for k, v in bym.items()}
            base = sum(avg.values()) / len(avg)
            season = {str(k): round(avg[k] / base, 3) for k in sorted(avg)}
        return {"rows": rows, "season": season, "coverage": sorted(families)}

    # ══════════ 제품 앵커 모드 (v0.2) ══════════
    def _client(self):
        if self.client is None:
            self.client = DaasClient()                  # 키: api.client.resolve_api_key()
        return self.client

    def _replay_metrics(self) -> dict:
        """replay 디렉터리의 모든 keyword_info 응답에서 keyword → ads_metrics 를 모은다."""
        if not hasattr(self, "_rm"):
            self._rm = {}; self._rmn = {}; self._rm_requested = set(); self._rm_requested_n = set()
            if self.replay:
                for f in sorted(self.replay.glob("*.json")):
                    try:
                        r = json.loads(f.read_text(encoding="utf8"))
                    except (OSError, json.JSONDecodeError):
                        continue
                    if isinstance(r, dict) and isinstance(r.get("data"), list):
                        req = (r.get("request_detail") or {}).get("keywords") or []
                        self._rm_requested.update(req); self._rm_requested_n.update(norm_kw(x) for x in req)
                        for it in r["data"]:
                            if isinstance(it, dict) and it.get("keyword") and it.get("ads_metrics"):
                                self._rm.setdefault(it["keyword"], it)
                                self._rmn.setdefault(norm_kw(it["keyword"]), it)      # 응답 띄어쓰기 정규화 대비
        return self._rm

    def _measure_live(self, kws: list, what: str, save: str) -> dict:
        """ads_metrics를 라이브로 잰다 (⑤ 미매칭 예측어 직접 실측 전용).

        저장본 조회(_kwinfo)와 분리한 이유: 코퍼스에 없는 어휘라 저장본에 있을 리 없고,
        replay-topup(전 단계 일괄 보충)을 켜면 롱테일까지 딸려와 비용이 통제되지 않는다.

        2026-09-17 — replay 중에는 **같은 run이 이미 사둔 저장본을 재사용**한다.
        이전에는 replay에서도 무조건 라이브로 재과금해 '--replay = 0크레딧 재계산' 계약이
        이 단계에서만 깨졌다(2026-09-17 가설 재확증에서 발견: 예측어를 줄여도 재청구).
        저장본에 없는 어휘는 --replay-topup 을 켰을 때만 라이브로 보충하고, 아니면 미측정으로 남긴다."""
        if self.a.dry_run:
            self.log(f"  [dry-run] 직접 실측 {len(kws)}건 ≈ {len(kws)}크레딧 ({what})")
            return {}
        saved_j = {}
        if self.replay:
            saved = self._load_raw_batches(save)
            if saved is not None:
                j, rem = join_by_request(saved.get("data"), kws)
                self._log_rematch(rem, what + "(저장본)")
                miss = [k for k in kws if k not in j]
                self.log(f"  [replay] 직접 실측 저장본 재사용 {len(kws) - len(miss)}/{len(kws)}건 (0크레딧)")
                live = self.a.replay_topup or getattr(self.a, "replay_live_measure", False)
                if not miss or not live:
                    if miss:
                        self.log(f"  [replay] 저장본에 없는 {len(miss)}건은 미측정으로 남김(--replay-live-measure 로 이 단계만 보충)")
                    return j
                kws, saved_j = miss, j                     # 보충분만 사고, 저장본 결과와 합쳐 돌려준다
            elif not (self.a.replay_topup or getattr(self.a, "replay_live_measure", False)):
                self.log(f"  [replay] 직접 실측 저장본 없음 — {len(kws)}건 미측정으로 남김")
                return {}
        self.ledger.check(len(kws), what)
        r = keyword_info.fetch_batch(self._client(), kws, gl=self.gl, data_type="ads_metrics")
        self.ledger.add("keyword_info", {"n": len(kws), "dt": "ads_metrics", "what": what}, r)
        self.save_raw(save, r)
        j, rem = join_by_request(r.get("data"), kws)
        self._log_rematch(rem, what)
        return {**saved_j, **j}

    def _kwinfo(self, kws: list, dt: str, what: str, save: str):
        """keyword_info 배치 — replay면 저장본에서, 아니면 라이브(원장 기록)."""
        self._requested = getattr(self, "_requested", set())
        if self.replay:
            rm = self._replay_metrics()
            got, rem = {}, []
            for k in kws:
                it = rm.get(k)
                if it is None:
                    it = self._rmn.get(norm_kw(k))
                    if it is not None:
                        rem.append((k, it.get("keyword")))
                if it is not None:
                    got[k] = it
            self._log_rematch(rem, what + "(저장본)")
            self._requested |= {k for k in kws if k in self._rm_requested or norm_kw(k) in self._rm_requested_n}
            missing = [k for k in kws if k not in got and norm_kw(k) not in self._rm_requested_n]
            if missing and self.a.replay_topup and not self.a.dry_run:
                self.ledger.check(len(missing) * (10 if dt == "all" else 1), what + " 보충")
                for ci, i in enumerate(range(0, len(missing), 1000)):      # 배치 상한 1000 청크
                    chunk = missing[i:i + 1000]
                    r = keyword_info.fetch_batch(self._client(), chunk, gl=self.gl, data_type=dt)
                    self.ledger.add("keyword_info", {"n": len(chunk), "dt": dt, "topup": True, "what": what + (f" (청크{ci+1})" if len(missing) > 1000 else "")}, r)
                    self.save_raw(save + "_topup" + (f"_chunk{ci+1}" if len(missing) > 1000 else ""), r)
                    j, rem = join_by_request(r.get("data"), chunk)
                    self._log_rematch(rem, what + " 보충"); got.update(j)
                self._requested |= set(missing)
            elif missing:
                self.log(f"  [replay] {what} 부족 {len(missing)}건 — 미측정으로 둠")
            return got
        if self.a.dry_run:
            self.log(f"  [dry-run] keyword_info {dt} × {len(kws)} ≈ {len(kws) * (10 if dt == 'all' else 1)}크레딧 ({what})")
            return {}
        self.ledger.check(len(kws) * (10 if dt == "all" else 1), what)
        out = {}
        for ci, i in enumerate(range(0, len(kws), 1000)):          # 배치 상한 1000 — 대형 코퍼스 청크 처리
            chunk = kws[i:i + 1000]
            r = keyword_info.fetch_batch(self._client(), chunk, gl=self.gl, data_type=dt)
            self.ledger.add("keyword_info", {"n": len(chunk), "dt": dt, "what": what + (f" (청크{ci+1})" if len(kws) > 1000 else "")}, r)
            self.save_raw(save + (f"_chunk{ci+1}" if len(kws) > 1000 else ""), r)
            j, rem = join_by_request(r.get("data"), chunk)
            self._log_rematch(rem, what); out.update(j)
        self._requested |= set(kws)
        return out

    def s1b_alias_canvass(self, sense: dict) -> dict:
        """B2 — 별칭군별 볼륨(ads_metrics) + 평가형 결합 + 별칭 all(시계열·성연령·인텐트)."""
        groups = sense["alias_groups"]
        aliases = [a for al in groups.values() for a in al]
        self.log(f"S1b 별칭군 캔버스 — {len(groups)}군 · 별칭 {len(aliases)} · 평가형 {len(sense['eval_terms'])}×군")
        am = self._kwinfo(aliases, "ads_metrics", "별칭 볼륨", "alias_ads_metrics")
        evals = {}
        for g, al in groups.items():
            head = al[0]
            evals.update({f"{head} {t}": g for t in sense["eval_terms"]})
        ev = self._kwinfo(list(evals), "ads_metrics", "평가형 결합", "alias_eval_ads_metrics")
        allm = self._kwinfo(aliases, "all", "별칭 all(시계열·성연령·인텐트)", "alias_kwinfo_all") if not self.a.no_alias_all else {}
        def yoy(item):
            mv = sorted([m for m in item.get("monthly_volume") or [] if isinstance(m, dict) and m.get("month")], key=lambda m: m["month"])
            t = [m.get("total") if m.get("total") is not None else (m.get("pc") or 0) + (m.get("mobile") or 0) for m in mv]
            return round(sum(t[-13:-1]) / sum(t[-25:-13]) - 1, 3) if len(t) >= 25 and sum(t[-25:-13]) else None
        out = {}
        for g, al in groups.items():
            rows = []
            for a in al:
                m = (am.get(a) or {}).get("ads_metrics") or {}
                full = allm.get(a) or {}
                dm = full.get("demography") or {}; it = full.get("intents") or {}
                rows.append({"alias": a, "v": m.get("volume_avg"), "trend": m.get("volume_trend"),
                             "comp": m.get("competition_index"), "yoy": yoy(full) if full else None,
                             "f_ratio": dm.get("f_gender_ratio"), "a30": dm.get("a30_ratio"), "a40": dm.get("a40_ratio"), "a50": dm.get("a50_ratio"),
                             "intents": "".join(k.upper() for k in "inct" if it.get(k)) or None,
                             "aio": (full.get("features") or {}).get("f_ai_overview")})
            vols = [r["v"] for r in rows if r["v"]]
            out[g] = {"aliases": rows, "volume_sum": sum(vols), "volume_sum_note": "동의어 중복 가능 — 상한",
                      "eval": {k: ((ev.get(k) or {}).get("ads_metrics") or {}).get("volume_avg") for k, gg in evals.items() if gg == g}}
            self.log(f"  [{g}] 합 {sum(vols):,} · " + " · ".join(f"{r['alias']} {r['v'] or '[없음]'}" for r in rows))
        return out

    def s2b_probe(self) -> dict:
        """B3 — 제품 시드 연관어 수(특성값). 적합률 게이트 면제 · 표본 부족 ≠ 오염."""
        if self.a.no_probe:
            return {"n_related": None, "note": "--no-probe"}
        if self.replay:
            for f in list(self.replay.glob("seed_probe/*.json")) + list(self.replay.glob("probe_*.json")):
                try:
                    r = json.loads(f.read_text(encoding="utf8"))
                except (OSError, json.JSONDecodeError):
                    continue
                qs = r.get("queries") or [(k.get("keyword") if isinstance(k, dict) else str(k)) for k in (r.get("data") or [])]
                if r.get("seed", "") == self.category or f.stem.endswith(re.sub(r"[^0-9A-Za-z가-힣]+", "_", self.category)):
                    self.log(f"S2b [replay] 연관어 {len(qs)}건 ({f.name})")
                    return {"n_related": len(qs), "queries": qs[:20], "source": f.name}
            if not self.a.replay_topup:
                self.log("S2b [replay] 프로브 저장본 없음 — 미측정")
                return {"n_related": None, "note": "replay 저장본 없음"}
            self.log("S2b [replay] 프로브 저장본 없음 — 라이브 보충(--replay-topup)")
        if self.a.dry_run:
            self.log("S2b [dry-run] intent_finder 프로브 ≈ 30 + 2×n 크레딧"); return {"n_related": None}
        self.ledger.check(250, "연관어 프로브")
        r = intent_finder.fetch(self._client(), [self.category], gl=self.gl, limit=100)
        self.ledger.add("intent_finder", {"kw": self.category, "what": "제품 시드 연관어 프로브"}, r)
        self.save_raw(f"probe_{re.sub(r'[^0-9A-Za-z가-힣]+', '_', self.category)}", r)
        qs = [k.get("keyword") if isinstance(k, dict) else str(k) for k in (r.get("data") or [])]
        self.log(f"S2b 연관어 {len(qs)}건 — 제품 시드는 적합률 게이트 면제(특성값)")
        return {"n_related": len(qs), "queries": qs[:20]}

    def s3b_product_journey(self) -> list:
        """B1 — 전이형: 제품 앵커 자체 여정. product_anchor 역할(코퍼스 비편입)."""
        name = f"paths_{re.sub(r'[^0-9A-Za-z가-힣]+', '_', self.category)}"
        if self.replay:
            f = self.replay / f"{name}.json"
            if f.exists():
                d = json.loads(f.read_text(encoding="utf8")).get("data") or []
                self.log(f"S3b [replay] 제품 여정 {len(d)}경로"); return d
            if not self.a.replay_topup:
                self.log("S3b [replay] 제품 여정 저장본 없음 — 전이형 미측정"); return []
            self.log("S3b [replay] 제품 여정 저장본 없음 — 라이브 보충(--replay-topup)")
        est = 50 + 40 * DEPTH[self.a.depth]["path_limit"]
        if self.a.dry_run:
            self.log(f"S3b [dry-run] path_finder({self.category}) ≤ {est}크레딧"); return []
        self.ledger.check(est, f"제품 여정 {self.category}")
        r = path_finder.fetch(self._client(), self.category, gl=self.gl, limit=DEPTH[self.a.depth]["path_limit"])
        self.ledger.add("path_finder", {"kw": self.category, "role": "product_anchor"}, r)
        self.save_raw(name, r)
        d = r.get("data") or []
        self.log(f"S3b 제품 여정 {len(d)}경로"); return d

    def s4b_inherit(self, sense: dict, paths: list) -> list:
        """B1 — 품목 run 허브 상속 + 제품 연결 측정(0크레딧): ① 제품 여정 내 허브 렉심 co_path ② 품목 run 여정 내 자사 라인·별칭 도달."""
        src = Path(self.a.inherit_from).resolve() if self.a.inherit_from else None
        if not src or not (src / "core/hub_graph.json").exists():
            w = "상속 원천(--inherit-from) 없음 — 상황형 허브는 제품 레벨에서 구조적으로 0이므로 품목 run을 먼저 실행할 것(B1)"
            self.log("  ⚠ " + w); self.warnings.append(w); return []
        hg = json.loads((src / "core/hub_graph.json").read_text(encoding="utf8"))
        labels = {}
        lf = src / "core/labels.json"
        if lf.exists():
            try: labels = json.loads(lf.read_text(encoding="utf8"))
            except json.JSONDecodeError: labels = {}
        bvol = {b["combo"]: b.get("v") for b in hg.get("bridges") or []}
        parent = hg.get("category") or sense.get("parent_category") or ""
        cat_re = re.compile(re.escape(parent).replace(r"\ ", r"\s*")) if parent else None
        specs = labels.get("hubs") or [{"id": h["id"], "label": h.get("family") or h.get("label") or h["id"], "status": h.get("status", "candidate"),
                                        "bridges": [b["combo"] for b in h.get("bridges", [])]} for h in hg.get("hubs") or []]
        own_terms = [t.lower() for t in (sense.get("own_lines") or [])]
        prod_terms = [a.lower() for al in sense.get("alias_groups", {}).values() for a in al] + [self.category.lower()]
        parent_paths = {f.stem.replace("paths_", "").replace("_", " "): (json.loads(f.read_text(encoding="utf8")).get("data") or [])
                        for f in (src / "raw").glob("paths_*.json")}
        out = []
        for hs in specs:
            if hs.get("inherited"): continue
            combos = [c for c in hs.get("bridges", []) if c in bvol]
            lex = [cat_re.sub("", c).strip().lower() if cat_re else c.lower() for c in combos]
            lex = [l for l in lex if len(l) >= 2]
            def hit(l, text):
                return re.search(r"\b" + re.escape(l) + r"\b", text) is not None if re.fullmatch(r"[a-z0-9 ]+", l) else (l in text)
            co = sum(1 for p in paths if any(hit(l, " ".join(p).lower()) for l in lex))
            co_examples = [" → ".join(p) for p in paths if any(hit(l, " ".join(p).lower()) for l in lex)][:3]
            anchor = hs.get("journey_anchor") or next((a for a in parent_paths if a in combos), None)
            reach = None; n_parent = None; preach = None
            if anchor and anchor in parent_paths:
                pp = parent_paths[anchor]; n_parent = len(pp)
                reach = sum(1 for p in pp if any(t in " ".join(p).lower() for t in own_terms))
                preach = sum(1 for p in pp if any(t in " ".join(p).lower() for t in prod_terms))
            own_bridges = {f"{l} {self.category}": None for l in lex[:4]}
            out.append({"id": hs.get("id"), "label": hs.get("label"), "status": hs.get("status"), "source": src.name,
                        "volume_sum": sum(bvol.get(c) or 0 for c in combos), "bridges": combos, "lexemes": lex,
                        "product_journey_co_path": co, "product_journey_n": len(paths),
                        "parent_journey_anchor": anchor, "parent_journey_n": n_parent,
                        "parent_journey_own_line_reach": reach, "parent_journey_product_reach": preach,
                        "co_path_examples": co_examples,
                        "verdict": (f"연결 단서({co + (preach or 0)}경로)" if co or preach else
                                    "비연결(측정)" if paths and n_parent else
                                    "비연결(제품 여정 기준)" if paths else "미측정")})
            self.log(f"S4b 상속 {hs.get('id')} — 제품 여정 co_path {co}/{len(paths)} · 품목 여정({anchor or '-'}) 제품 별칭 도달 {preach if preach is not None else '미측정'}/{n_parent or '-'} (자사 라인 {reach if reach is not None else '-'})")
        return out

    def s5b_transition(self, sense: dict, paths: list, families: dict) -> dict:
        """B4 — 전이 지표: 위치·선행/후행·상황 렉심 도달·경쟁 브랜드 동반·자사 라인 분기."""
        if not paths:
            return {"measured": False, "note": "전이형 여정 미수집"}
        import collections
        a = self.category; prev = collections.Counter(); nxt = collections.Counter(); pos = collections.Counter()
        for p in paths:
            i = p.index(a) if a in p else -1
            pos["start" if i == 0 else ("end" if i == len(p) - 1 else "mid")] += 1
            if i > 0: prev[p[i - 1]] += 1
            if 0 <= i < len(p) - 1: nxt[p[i + 1]] += 1
        situ_terms = [t.format("").strip().lower() if "{}" in t else t.lower() for fam in families.values() for t in fam]
        situ_terms = [t for t in situ_terms if len(t) >= 2 and t not in a.lower()]
        situ = sum(1 for p in paths if any(t in " ".join(p).lower() for t in situ_terms))
        own = (sense.get("own_brand") or "").lower()
        comp = collections.Counter(); lines = collections.Counter()
        if not self.brand_rx and load_brand_map:
            try: self.brand_rx = load_brand_map(self.a.vertical, None)
            except Exception: self.brand_rx = {}   # noqa: BLE001
            self._brand_map_warn()
        for p in paths:
            s = " ".join(n for n in p if n != a).lower()
            for b, rx in self.brand_rx.items():
                if b.lower() != own and rx.search(s): comp[b] += 1
            for ln in sense.get("own_lines") or []:
                if ln.lower() in s and ln.lower() not in a.lower(): lines[ln] += 1
        return {"measured": True, "n": len(paths), "position": dict(pos), "prev": prev.most_common(10), "next": nxt.most_common(10),
                "situation_reach": situ, "competitor_cooccurrence": comp.most_common(8), "own_line_branch": lines.most_common(8),
                "note": "브랜드 도달은 자사 앵커라 퇴화 — 경쟁 동반률·자사 라인 분기로 대체(B4)"}

    def _brand_map_warn(self):
        """정본 파서 진단·우회를 run 경고로 올린다 — 조용한 대체 금지(정본 소비 규칙 4)."""
        try:
            from render import BRAND_MAP_WARNINGS
        except Exception:                                   # noqa: BLE001
            return
        for w in BRAND_MAP_WARNINGS:
            if w not in self.warnings:
                self.log("  ⚠ " + w); self.warnings.append(w)

    # ══════════ v0.3 ══════════
    def _brand_sides(self, sense: dict):
        """자사(브랜드+라인+별칭) / 경쟁 브랜드 정규식. 경쟁 목록은 sense.competitors, 없으면 brand-map 전체(자사 제외)."""
        own = [t.lower() for t in ([sense.get("own_brand")] if sense.get("own_brand") else []) + list(sense.get("own_lines") or [])
               + [a for al in (sense.get("alias_groups") or {}).values() for a in al]]
        if not self.brand_rx and load_brand_map:
            try: self.brand_rx = load_brand_map(self.a.vertical, None)
            except Exception: self.brand_rx = {}   # noqa: BLE001
            self._brand_map_warn()
        own_b = (sense.get("own_brand") or "").lower()
        own_rx = self.brand_rx.get(sense.get("own_brand") or "", None)
        comp_names = [c for c in (sense.get("competitors") or []) ] or [b for b in self.brand_rx if b.lower() != own_b]
        comp_rx = {}
        for c in comp_names:
            rx = self.brand_rx.get(c)
            comp_rx[c] = rx if rx is not None else re.compile(re.escape(c.lower()), re.I)
        def is_own(n):
            nl = n.lower()
            return any(t and t in nl for t in own) or (own_rx.search(nl) if own_rx else False)
        def comp_of(n):
            nl = n.lower()
            for c, rx in comp_rx.items():
                if rx.search(nl): return c
            return None
        return is_own, comp_of, comp_names

    def s5c_switching(self, sense: dict, paths: list) -> dict:
        """B7 — 여정 순서에서 자사↔경쟁 전환 방향과 트리거 노드. 세션 인접 집계 — 개인의 이탈·전환이 아님."""
        if not paths:
            return {"measured": False, "note": "여정 미수집"}
        import collections
        is_own, comp_of, comps = self._brand_sides(sense)
        c = collections.Counter(); out_trig = collections.Counter(); in_trig = collections.Counter()
        out_comp = collections.Counter(); in_comp = collections.Counter(); ex_out = []; ex_in = []
        for p in paths:
            tags = [("O" if is_own(n) else ("C" if comp_of(n) else "-")) for n in p]
            seq = "".join(t for t in tags if t != "-")
            if "O" in seq and "C" in seq:
                fo, fc = seq.index("O"), seq.index("C")
                if fo < fc:
                    c["own_to_comp"] += 1
                    i = next(i for i, t in enumerate(tags) if t == "C"); out_trig[p[i - 1] if i > 0 else p[0]] += 1; out_comp[comp_of(p[i])] += 1
                    if len(ex_out) < 5: ex_out.append(" → ".join(p))
                else:
                    c["comp_to_own"] += 1
                    i = next(i for i, t in enumerate(tags) if t == "O"); in_trig[p[i - 1] if i > 0 else p[0]] += 1
                    j = next(i for i, t in enumerate(tags) if t == "C"); in_comp[comp_of(p[j])] += 1
                    if len(ex_in) < 5: ex_in.append(" → ".join(p))
                if "OC" in seq and "CO" in seq: c["round_trip"] += 1
            elif "O" in seq: c["own_only"] += 1
            elif "C" in seq: c["comp_only"] += 1
            else: c["none"] += 1
        n = len(paths)
        res = {"measured": True, "n": n, "counts": dict(c),
               "switch_out_rate": round(c["own_to_comp"] / n, 3), "switch_in_rate": round(c["comp_to_own"] / n, 3),
               "switch_out_triggers": out_trig.most_common(8), "switch_in_triggers": in_trig.most_common(8),
               "switch_out_to": out_comp.most_common(5), "switch_in_from": in_comp.most_common(5),
               "examples_out": ex_out, "examples_in": ex_in, "competitors": comps,
               "note": "path_finder 집계 행동 그래프의 노드 순서 — 동일 세션 내 검토 순서이지 개인의 이탈·전환이 아님(인과 서술 금지)"}
        self.log(f"S5c 스위칭 — 자사→경쟁 {c['own_to_comp']} · 경쟁→자사 {c['comp_to_own']} · 왕복 {c['round_trip']} · 자사만 {c['own_only']} · 경쟁만 {c['comp_only']} /{n}")
        return res

    def s6b_context_matrix(self, sense: dict) -> dict:
        """B9 — 컨텍스트 × 브랜드 결합쿼리 볼륨(ads_metrics 1/건). 겹침 지수 = min/max(자사측, 경쟁측) · 무브랜드 여지 = generic ÷ (generic + 브랜드합)."""
        ctxs = [(c["term"], c.get("pos", "prefix")) if isinstance(c, dict) else tuple(c) if isinstance(c, (list, tuple)) else (c, "prefix")
                for c in (sense.get("contexts") or DEFAULT_CONTEXTS)]
        cat = sense.get("parent_category") or self.category
        brands = sense.get("brand_set") or (
            [{"label": sense["own_brand"], "term": sense["own_brand"].lower(), "side": "own", "with_category": True}] if sense.get("own_brand") else []) +             [{"label": l, "term": l.lower(), "side": "own", "with_category": False} for l in (sense.get("own_lines") or []) if l not in set(sense.get("own_lines_exclude") or [])]   # 제외 라인은 어댑터·sense 설정으로 (코드에 제품명을 박지 않는다) +             [{"label": c, "term": c.lower(), "side": "comp", "with_category": True} for c in (sense.get("competitors") or [])]
        combos = {}
        for ctx, pos in ctxs:
            combos[f"{ctx} {cat}" if pos == "prefix" else f"{cat} {ctx}"] = (ctx, "generic")
            for b in brands:
                core = f"{ctx} {cat}" if pos == "prefix" else f"{cat} {ctx}"
                if not b.get("with_category", True):
                    core = ctx if pos == "prefix" else ctx
                combos[f"{b['term']} {core}"] = (ctx, b["label"])
        self.log(f"S6b Context×브랜드 매트릭스 — 컨텍스트 {len(ctxs)} × (브랜드 {len(brands)} + generic) = 결합형 {len(combos)}")
        got = self._kwinfo(list(combos), "ads_metrics", "Context×브랜드 매트릭스", "context_matrix_ads_metrics")
        mat = {}
        for combo, (ctx, col) in combos.items():
            v = ((got.get(combo) or {}).get("ads_metrics") or {}).get("volume_avg")
            mat.setdefault(ctx, {})[col] = {"q": combo, "v": v, "measured": combo in got or combo in getattr(self, "_requested", set())}
        side = {b["label"]: b["side"] for b in brands}
        rows = []
        for ctx, cols in mat.items():
            own = sum((c["v"] or 0) for k, c in cols.items() if side.get(k) == "own")
            comp = sum((c["v"] or 0) for k, c in cols.items() if side.get(k) == "comp")
            gen = (cols.get("generic") or {}).get("v") or 0
            overlap = round(min(own, comp) / max(own, comp), 2) if max(own, comp) else None
            rows.append({"context": ctx, "own": own, "comp": comp, "generic": gen,
                         "overlap_index": overlap, "open_share": round(gen / (gen + own + comp), 2) if (gen + own + comp) else None,
                         "own_share": round(own / (own + comp), 2) if (own + comp) else None, "cells": cols})
        rows.sort(key=lambda r: -(r["own"] + r["comp"] + r["generic"]))
        measured = sum(1 for r in rows for c in r["cells"].values() if c["measured"])
        return {"measured": measured > 0, "brands": brands, "rows": rows, "n_cells": len(combos), "n_measured": measured,
                "denominator_basis": "브랜드 결합쿼리 볼륨 합 — 검색량 기준 근사 · 동의어 미합산(별칭 1형만)",
                "note": "겹침 지수 1.0 = 양측 동량 · 무브랜드 여지 = generic ÷ 전체 — 어느 브랜드도 못 잡은 컨텍스트 탐지"}

    # ══════════ v0.4 B8 — 기능 앵커 ══════════
    def s1c_feature_canvass(self, sense: dict) -> dict:
        """변형 × 이해형 결합 + 변형 간 '차이/vs' + 경쟁 기능(assumption) 볼륨. 전부 ads_metrics 1크레딧/건."""
        variants = list(sense.get("feature_variants") or [self.category])
        if self.category not in variants: variants.insert(0, self.category)
        terms = list(sense.get("understanding_terms") or FEATURE_UNDERSTANDING)
        combos = {}
        for v in variants:
            for t in terms:
                combos[(f"{v}{t}" if t == "란" else f"{v} {t}")] = (v, t)
        pairs = {}
        for i, a in enumerate(variants):
            for b in variants[i + 1:]:
                pairs[f"{a} {b} 차이"] = (a, b); pairs[f"{a} vs {b}"] = (a, b)
        comp_feats = list(sense.get("competing_features") or [])
        comp_kws = [c["feature"] if isinstance(c, dict) else c for c in comp_feats]
        self.log(f"S1c 기능 캔버스 — 변형 {len(variants)} × 이해형 {len(terms)} = {len(combos)} · 변형쌍 {len(pairs)} · 경쟁 기능 {len(comp_kws)}(assumption)")
        got_v = self._kwinfo(variants, "ads_metrics", "기능 변형 볼륨", "feature_variants_ads_metrics")
        got_u = self._kwinfo(list(combos), "ads_metrics", "기능 이해형 결합", "feature_understanding_ads_metrics")
        got_p = self._kwinfo(list(pairs), "ads_metrics", "변형 간 차이·vs", "feature_pairs_ads_metrics") if pairs else {}
        got_c = self._kwinfo(comp_kws, "ads_metrics", "경쟁 기능(assumption)", "competing_features_ads_metrics") if comp_kws else {}
        vol = lambda g, k: ((g.get(k) or {}).get("ads_metrics") or {}).get("volume_avg")
        tr = lambda g, k: ((g.get(k) or {}).get("ads_metrics") or {}).get("volume_trend")
        retk = lambda g, k: (lambda rk: rk if rk and rk != k else None)((g.get(k) or {}).get("keyword"))   # 응답어가 요청어와 다를 때만 보존(출처)
        out = {"variants": [{"term": v, "v": vol(got_v, v), "trend": tr(got_v, v), "measured_as": retk(got_v, v),
                             "understanding": {t: vol(got_u, (f"{v}{t}" if t == "란" else f"{v} {t}")) for t in terms}} for v in variants],
               "pairs": [{"q": k, "a": a, "b": b, "v": vol(got_p, k)} for k, (a, b) in pairs.items()],
               "competing_features": [{"brand": (c.get("brand") if isinstance(c, dict) else None), "feature": (c["feature"] if isinstance(c, dict) else c),
                                       "note": (c.get("note") if isinstance(c, dict) else None), "v": vol(got_c, c["feature"] if isinstance(c, dict) else c),
                                       "measured_as": retk(got_c, c["feature"] if isinstance(c, dict) else c),
                                       "grade": "assumption"} for c in comp_feats],
               "understanding_terms": terms}
        cterms = [c for c in (sense.get("consumer_terms") or []) if c not in variants]                 # v0.6 B14
        got_ct = self._kwinfo(cterms, "ads_metrics", "소비자 일반어(B14)", "consumer_terms_ads_metrics") if cterms else {}
        cs = sense.get("consumer_term_sense") or {}
        out["consumer_terms"] = [{"term": c, "v": vol(got_ct, c), "trend": tr(got_ct, c), "grade": "measured",
                                  "sense": (cs.get(c) or {}).get("verdict"), "feature_share": (cs.get(c) or {}).get("feature_share"),
                                  "v_adjusted": ((cs.get(c) or {}).get("adjusted_volume") if (cs.get(c) or {}).get("n_paths") else vol(got_ct, c))} for c in cterms]
        cv = sum((r["v"] or 0) for r in out["consumer_terms"]); pv = sum((r["v"] or 0) for r in out["variants"])
        cva = sum((r["v_adjusted"] or 0) for r in out["consumer_terms"])
        out["generic_vs_proper"] = {"consumer_terms": cv, "consumer_terms_adjusted": cva, "proper_variants": pv, "ratio": round(cv / pv, 2) if pv else None, "ratio_adjusted": round(cva / pv, 2) if pv else None,
                                    "note": "일반어 볼륨 / 고유명 볼륨 — 소비자가 기능을 부르는 말이 고유명과 다르면 캠페인 검색어 축이 둘로 갈린다(동의어 중복 가능, 합은 상한)"}
        out["benefit"] = sense.get("benefit"); out["not_this_feature"] = list(sense.get("not_this_feature") or [])
        if cterms: self.log("  [B14] 소비자 일반어: " + " · ".join(f"{r['term']} {r['v'] or '[없음]'}" + (f"(기능 {r['feature_share']:.0%}→{r['v_adjusted']:,})" if r.get('feature_share') is not None else "") for r in out["consumer_terms"]) + f" → 일반어 {cv:,}(환산 {cva:,}) vs 고유명 {pv:,}")
        for r in out["variants"]:
            self.log(f"  [{r['term']}] {r['v'] or '[없음]'} · " + " · ".join(f"{t} {r['understanding'][t] or '[없음]'}" for t in terms))
        live_pairs = [p for p in out["pairs"] if p["v"]]
        self.log("  변형쌍 성립: " + (" · ".join(f"{p['q']} {p['v']}" for p in live_pairs) or "없음"))
        return out

    def s7_feature_association(self, sense: dict, paths: list, families: dict) -> dict:
        """B8 핵심 — 기능 앵커 여정의 노드를 층으로 분류하고 앵커 앞/뒤 위치로 사슬 순서를 측정한다."""
        if not paths:
            return {"measured": False, "note": "기능 여정 미수집"}
        import collections
        a = self.category.lower()
        is_own, comp_of, _ = self._brand_sides(sense)
        lex = dict(LAYER_RX); lex.update(sense.get("layer_lexicon") or {})
        variants = [v.lower() for v in (sense.get("feature_variants") or []) if v.lower() != a]
        lines = [l.lower() for l in (sense.get("own_lines") or [])]
        comp_feats = [(c["feature"] if isinstance(c, dict) else c).lower() for c in (sense.get("competing_features") or [])]
        situ = [t.format("").strip().lower() if "{}" in t else t.lower() for fam in families.values() for t in fam]
        situ = [t for t in situ if len(t) >= 2 and t not in a]
        parent = (sense.get("parent_category") or "").lower()
        def layer(n: str):
            nl = n.lower()
            if nl == a: return None
            if any(v in nl for v in variants): return "feature_variant"
            if any(f in nl for f in comp_feats): return "competing_feature"
            if any(l in nl for l in lines): return "own_line"
            if comp_of(n): return "brand_comp"
            if any(t in nl for t in situ): return "situation"
            if re.search(lex["model_code"], nl): return "model_code"
            if re.search(lex["eval"], nl): return "eval"
            if re.search(lex["purchase"], nl): return "purchase"
            if re.search(lex["kbf_context"], nl): return "kbf_context"
            if is_own(n): return "brand_own"
            if parent and nl == parent: return "category_head"
            if parent and parent in nl: return "category_other"
            return "other"
        stats = collections.defaultdict(lambda: {"paths": 0, "before": 0, "after": 0, "nodes": collections.Counter(), "relpos": []})
        prev = collections.Counter(); nxt = collections.Counter(); pos = collections.Counter()
        for p in paths:
            i = p.index(self.category) if self.category in p else next((k for k, n in enumerate(p) if n.lower() == a), -1)
            if i < 0: continue
            pos["start" if i == 0 else ("end" if i == len(p) - 1 else "mid")] += 1
            if i > 0: prev[p[i - 1]] += 1
            if i < len(p) - 1: nxt[p[i + 1]] += 1
            seen = set()
            for k, n in enumerate(p):
                L = layer(n)
                if not L: continue
                st = stats[L]; st["nodes"][n] += 1
                if k < i: st["before"] += 1
                elif k > i: st["after"] += 1
                st["relpos"].append((k - i) / max(len(p) - 1, 1))
                if L not in seen: st["paths"] += 1; seen.add(L)
        n = len(paths); layers = {}
        for L, st in stats.items():
            rel = st["relpos"]
            layers[L] = {"paths": st["paths"], "share": round(st["paths"] / n, 3), "before": st["before"], "after": st["after"],
                         "mean_relpos": round(sum(rel) / len(rel), 3) if rel else None, "top_nodes": st["nodes"].most_common(8)}
        chain = sorted([(L, v["mean_relpos"]) for L, v in layers.items() if v["mean_relpos"] is not None], key=lambda x: x[1])
        forward_only = pos.get("start", 0) == n
        res = {"measured": True, "n": n, "position": dict(pos), "forward_only": forward_only,
               "prev": prev.most_common(10), "next": nxt.most_common(10), "layers": layers, "chain_order": chain,
               "note": ("앵커가 전 경로의 시작점(전방향 여정) — 선행 층은 측정 불가, 사슬 순서는 앵커 이후의 순서만 의미 · " if forward_only else "")
                       + "층 분류는 어휘 규칙(derived) · mean_relpos<0 = 앵커 앞(선행), >0 = 뒤(후행) · 세션 인접 집계이며 개인 여정 아님"}
        self.log("S7 Feature Association — " + " · ".join(f"{L} {v['paths']}({v['share']:.0%}, pos {v['mean_relpos']:+.2f})" for L, v in sorted(layers.items(), key=lambda x: -x[1]['paths'])))
        self.log("  사슬 순서(앞→뒤): " + " → ".join(f"{L}({r:+.2f})" for L, r in chain))
        return res

    def emit_ontology_delta(self, sense: dict, feat: dict, assoc: dict):
        """온톨로지 후보(append-only 제안) — Technology 노드 + variants/competes_with/attaches_to. 승인 전 candidate."""
        rows = []
        snap = time.strftime("%Y-%m-%d")
        rows.append({"op": "upsert_candidate", "node": {"id": f"TECH-{re.sub(r'[^0-9A-Za-z가-힣]+', '_', self.category)}", "class": "Technology",
                     "label": self.category, "axis": "demand", "grade": "measured", "snapshot": snap, "status": "candidate",
                     "source": f"cep-finder v0.4 feature run {self.run_id}",
                     "variants": [v["term"] for v in feat.get("variants", [])], "volume": {self.gl: {v["term"]: v["v"] for v in feat.get("variants", [])}}}})
        for c in feat.get("competing_features", []):
            rows.append({"op": "propose_edge", "edge": {"src": f"TECH-{re.sub(r'[^0-9A-Za-z가-힣]+', '_', self.category)}",
                         "dst": f"TECH-{re.sub(r'[^0-9A-Za-z가-힣]+', '_', c['feature'])}", "type": "competes_with",
                         "evidence": {"grade": "assumption", "brand": c.get("brand"), "volume": c.get("v"),
                                      "volume_measured_as": c.get("measured_as"),      # API 정규화 응답어(요청어와 다를 때만)
                                      "note": c.get("note"), "snapshot": snap}}})
        for L, v in (assoc.get("layers") or {}).items():
            if L in ("kbf_context", "situation", "own_line", "feature_variant", "model_code") and v["paths"] >= 3:
                rows.append({"op": "propose_edge", "edge": {"src": f"TECH-{re.sub(r'[^0-9A-Za-z가-힣]+', '_', self.category)}", "dst": f"LAYER-{L}",
                             "type": "attaches_to", "evidence": {"grade": "derived", "paths": v["paths"], "share": v["share"], "mean_relpos": v["mean_relpos"],
                                                                 "examples": [n for n, _ in v["top_nodes"][:5]], "snapshot": snap}}})
        (self.out / "core" / "ontology_delta.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf8")
        self.log(f"  ontology_delta.jsonl — 후보 {len(rows)}건 (승인 전 candidate · 온톨로지 직접 수정 없음)")

    # ══════════ v0.5 — S2 증거 · S3 롱테일 · S5 가설 선행 ══════════
    def _slug(self, s: str) -> str:
        return re.sub(r"[^0-9A-Za-z가-힣]+", "_", s).strip("_")

    def _load_raw_batches(self, name: str):
        """replay 디렉터리·현재 run raw의 name.json과 보충분 name_2.json… 을 한 응답으로 합친다.
        2026-09-17 — save_raw는 덮어쓰지 않고 _2로 쌓는데 읽기는 name.json만 봐서, 보충 실측이 다음 replay에서 사라졌다."""
        data, req, found = [], [], False
        for base in ([self.replay] if self.replay else []) + [self.out / "raw"]:
            for f in sorted(base.glob(f"{name}.json")) + sorted(base.glob(f"{name}_[0-9]*.json"), key=lambda x: int(x.stem.rsplit("_", 1)[1])):
                try:
                    r = json.loads(f.read_text(encoding="utf8"))
                except json.JSONDecodeError:
                    continue
                found = True
                data += r.get("data") or []
                req += (r.get("request_detail") or {}).get("keywords") or []
        return {"data": data, "request_detail": {"keywords": req}} if found else None

    def _load_raw_or(self, name: str):
        """replay 디렉터리 → (없으면) 현재 run raw 에서 저장본을 찾는다."""
        for base in ([self.replay] if self.replay else []) + [self.out / "raw"]:
            f = base / f"{name}.json"
            if f.exists():
                try: return json.loads(f.read_text(encoding="utf8"))
                except json.JSONDecodeError: pass
        return None

    def s2_evidence(self, sense: dict, bridges_sorted: list) -> dict:
        """S2 · SERP·AIO·PAA 증거 수집 (M2 · grade extracted). 시드당 SERP_COST(30)크레딧 · 인용 원문·수집시각 보존."""
        if self.a.no_evidence:
            return {"measured": False, "note": "--no-evidence"}
        seeds = [self.category]
        for g, al in (sense.get("alias_groups") or {}).items():
            if al and al[0] not in seeds: seeds.append(al[0])
        for b in bridges_sorted:
            if b["v"] >= BRIDGE_FLOOR and b["combo"] not in seeds: seeds.append(b["combo"])
        for s_ in sense.get("evidence_seeds") or []:
            if s_ not in seeds: seeds.append(s_)
        seeds = seeds[: self.a.serp_max]
        self.log(f"S2 증거 수집 — serp {len(seeds)}시드 × {SERP_COST}크레딧 ≈ {len(seeds) * SERP_COST}크레딧 (extracted · 저장본 재사용분 제외)")
        items, aio_hit, paa, related = [], 0, [], []
        for s_ in seeds:
            name = f"serp_{self._slug(s_)}"; r = self._load_raw_or(name)
            if r is None:
                if self.a.dry_run or (self.replay and not self.a.replay_topup):
                    self.log(f"  [{'dry-run' if self.a.dry_run else 'replay'}] serp({s_}) 미수집"); continue
                self.ledger.check(SERP_COST, f"serp {s_}")
                r = serp.fetch(self._client(), s_, gl=self.gl, num=20)
                self.ledger.add("serp", {"kw": s_}, r); self.save_raw(name, r)
            ts = r.get("request_at") or time.strftime("%Y-%m-%dT%H:%M:%S")
            aio = serp.ai_overview_snippets(r); qs = serp.questions(r); rel = serp.related_queries(r); org = serp.organic(r)
            if aio: aio_hit += 1
            for t in aio: items.append({"seed": s_, "kind": "aio", "text": t[:400], "collected_at": ts, "grade": "extracted"})
            for q in qs:
                qt = q.get("question") or q.get("title") or q.get("text") or ""
                if qt:
                    paa.append({"seed": s_, "q": qt, "a": (q.get("snippet") or q.get("answer") or "")[:300]})
                    items.append({"seed": s_, "kind": "paa", "text": qt, "snippet": (q.get("snippet") or "")[:300], "collected_at": ts, "grade": "extracted"})
            for q in rel: related.append({"seed": s_, "q": q})
            for o in org[:6]:
                items.append({"seed": s_, "kind": "organic", "text": (o.get("title") or "")[:160], "snippet": (o.get("snippet") or "")[:300], "url": o.get("link") or o.get("url"), "collected_at": ts, "grade": "extracted"})
        n = sum(1 for s_ in seeds if self._load_raw_or(f"serp_{self._slug(s_)}") is not None)
        res = {"measured": n > 0, "seeds": seeds, "n_seeds": n, "aio_exposure": (aio_hit, n), "items": items, "paa": paa, "related": related,
               "note": "SERP·AIO·PAA는 조회 시점 스냅샷(extracted) — 소비자 발화가 아니라 가설의 원천이며, 확증은 키워드 실측으로만"}
        self.log(f"  증거 {len(items)}건 · AIO 노출 {aio_hit}/{n} · PAA {len(paa)} · 연관검색 {len(related)}")
        return res

    def s3_longtail(self, sense: dict, known: set) -> dict:
        """S3 · 롱테일 수확 — intent_finder vt=0(시드당 30+2N) → keyword_info ads_info(1/kw). 0볼륨은 '언어층'으로 보존, 노이즈는 플래그만."""
        if self.a.no_longtail:
            return {"measured": False, "note": "--no-longtail"}
        seeds = [self.category] + [s_ for s_ in (sense.get("longtail_seeds") or []) if s_ != self.category]
        spaces = list(self.adapter.get("A4_ontology_binding", "context_lexicon", "spaces") or [])
        for sp in (sense.get("space_seeds") or [f"{sp} {self.category}" for sp in spaces[:3]]):
            if sp not in seeds: seeds.append(sp)
        for s_ in (self.a.longtail_seeds or "").split(","):
            if s_.strip() and s_.strip() not in seeds: seeds.append(s_.strip())
        lim = self.a.longtail_limit
        self.log(f"S3 롱테일 수확 — intent_finder vt=0 limit={lim} × {len(seeds)}시드 (시드당 ≈{30 + 2 * lim})")
        harvested = {}
        for s_ in seeds:
            name = f"longtail_{self._slug(s_)}"; r = self._load_raw_or(name)
            if r is None:
                if self.a.dry_run or (self.replay and not self.a.replay_topup):
                    self.log(f"  [{'dry-run' if self.a.dry_run else 'replay'}] intent_finder({s_}) 미수집"); continue
                self.ledger.check(30 + 2 * lim, f"롱테일 {s_}")
                r = intent_finder.fetch(self._client(), [s_], gl=self.gl, volume_threshold=0, limit=lim)
                self.ledger.add("intent_finder", {"kw": s_, "vt": 0, "limit": lim, "what": "롱테일 수확"}, r); self.save_raw(name, r)
            for k in (r.get("data") or []):
                q = (k.get("keyword") if isinstance(k, dict) else str(k)).strip()
                if q and q not in harvested: harvested[q] = s_
        new = [q for q in harvested if q not in known]
        got = self._kwinfo(new, "ads_info", "롱테일 볼륨(ads_info)", "longtail_ads_info") if new else {}
        noise_re, _ = self._noise_re()
        space_re = re.compile("|".join(re.escape(x) for x in (spaces + ["냉장고장", "인테리어", "리폼", "수납장", "가구"])), re.I) if spaces else None
        rows = []
        for q, seed in harvested.items():
            m = ((got.get(q) or {}).get("ads_metrics") or {})
            v = m.get("volume_avg"); measured = (q in got) or (q in getattr(self, "_requested", set()))
            rows.append({"q": q, "seed": seed, "v": v if v is not None else (0 if measured else None), "trend": m.get("volume_trend"),
                         "language_only": measured and not v, "noise": bool(noise_re.search(q.lower())) if noise_re else False,
                         "space_context": bool(space_re.search(q.lower())) if space_re else False,
                         "mentions_anchor": self.category.lower().replace(" ", "") in q.lower().replace(" ", ""),
                         "off_feature": bool(self.off_re.search(q.lower())) if self.off_re else False})          # v0.6 B15
        rows.sort(key=lambda r: -(r["v"] or 0))
        n = len(rows); vol = sum((r["v"] or 0) for r in rows); noise_n = sum(1 for r in rows if r["noise"]); noise_v = sum((r["v"] or 0) for r in rows if r["noise"])
        res = {"measured": n > 0, "seeds": seeds, "n": n, "with_volume": sum(1 for r in rows if r["v"]), "language_only": sum(1 for r in rows if r["language_only"]),
               "unmeasured": sum(1 for r in rows if r["v"] is None), "volume_sum": vol,
               "noise": {"n": noise_n, "share_n": round(noise_n / n, 3) if n else None, "share_v": round(noise_v / vol, 3) if vol else None},
               "space_context_n": sum(1 for r in rows if r["space_context"]), "off_feature_n": sum(1 for r in rows if r.get("off_feature")), "rows": rows,
               "note": "0볼륨 쿼리는 규모가 아니라 언어 근거(language_only) — 허브 볼륨 합산 금지 · 노이즈는 플래그만(개수·볼륨 양 기준)"}
        self.log(f"  수확 {n} · 볼륨 있음 {res['with_volume']} · 언어층(0) {res['language_only']} · 미측정 {res['unmeasured']} · 노이즈 {noise_n}({res['noise']['share_v'] or 0:.0%} 볼륨) · 공간 맥락 {res['space_context_n']} · 기능 외(off_feature) {res['off_feature_n']}")
        return res

    def s3c_benefit_decompose(self, sense: dict, longtail: dict) -> dict:
        """S3c · B13 — 편익 → 7W 세부 상황 분해. 분해 사전(who/when/what/while/where)으로 셀을 만들고 셀별 시드를 자동 생성해
        intent_finder vt=0 수확 → ads_info 볼륨 → 셀 판정(search_target / weak_signal / language_only / no_evidence).
        수확 쿼리는 롱테일 코퍼스에 합류(S5 매칭 대상) · 노이즈·off_feature 는 셀 집계에서 제외(플래그 보존)."""
        if not self.feature or self.a.no_benefit:
            return {"measured": False, "note": "feature 모드 전용" if not self.feature else "--no-benefit"}
        dl = self.decomp_lexicon
        if not dl:
            w = "분해 사전(decomposition_lexicon) 없음 — 편익 7W 분해 생략(B13)"; self.log("  ⚠ " + w); self.warnings.append(w)
            return {"measured": False, "note": w}
        cat = sense.get("parent_category") or self.category
        f1 = (sense.get("consumer_terms") or [self.category])[0]
        cells, total_seeds = [], 0
        for dim, W in (("who", "W4"), ("when", "W2"), ("what", "W5"), ("while", "W6"), ("where", "W3")):
            for c in dl.get(dim) or []:
                raw_seeds = list(c.get("seeds") or [c.get("seed")])                     # seeds[] 필수 — 시드 1개면 경고
                seeds = list(dict.fromkeys(s.replace("{c}", cat).replace("{f}", f1).strip() for s in raw_seeds if s))
                if len(seeds) < 2:
                    self.warnings.append(f"편익 셀 '{c['label']}' 시드 1개 — 근거 없음이 시드 실패인지 부재인지 구분 불가(seeds[] 2개 이상 권장)")
                cells.append({"dim": dim, "w": W, "label": c["label"], "seeds": seeds, "seed": seeds[0], "harvested": None, "seed_results": [],
                              "narrative_seeds": [s.replace("{c}", cat).replace("{f}", f1).strip() for s in (c.get("narrative_seeds") or []) if s],
                              "narrative_terms": list(c.get("narrative_terms") or [x for x in seeds[0].replace(cat, " ").split() if len(x) >= 2])})
                total_seeds += len(seeds)
        dropped = 0
        if total_seeds > self.a.benefit_seeds_max:                                         # 상한은 셀이 아니라 시드 총수 — 셀당 첫 시드부터 공평하게 배분
            budget_n = self.a.benefit_seeds_max; kept = 0
            for k in range(max(len(c["seeds"]) for c in cells)):
                for c in cells:
                    if k < len(c["seeds"]):
                        if kept < budget_n: kept += 1
                        else: c["seeds"][k] = None; dropped += 1
            for c in cells: c["seeds"] = [s for s in c["seeds"] if s]
        lim = self.a.longtail_limit
        self.log(f"S3c 편익 7W 분해 (B13) — 편익 '{(sense.get('benefit') or '?')[:40]}' · 셀 {len(cells)} · 시드 {total_seeds - dropped}" + (f" (상한으로 {dropped}시드 제외 — --benefit-seeds-max)" if dropped else "") + f" · 시드당 ≈{30 + 2 * lim}")
        rowmap = {r["q"]: r for r in (longtail.get("rows") or [])}
        harvested = {}
        for i, c in enumerate(cells):
            cell_qs = set()
            for s_ in c["seeds"]:
                name = f"longtail_{self._slug(s_)}"; r = self._load_raw_or(name)
                if r is None:
                    if self.a.dry_run or (self.replay and not self.a.replay_topup):
                        self.log(f"  [{'dry-run' if self.a.dry_run else 'replay'}] intent_finder({s_}) 미수집"); c["seed_results"].append({"seed": s_, "n": None}); continue
                    self.ledger.check(30 + 2 * lim, f"편익 셀 {s_}")
                    r = intent_finder.fetch(self._client(), [s_], gl=self.gl, volume_threshold=0, limit=lim)
                    self.ledger.add("intent_finder", {"kw": s_, "vt": 0, "limit": lim, "what": f"편익 셀 {c['dim']}:{c['label']}"}, r); self.save_raw(name, r)
                n = 0
                for k in (r.get("data") or []):
                    q = (k.get("keyword") if isinstance(k, dict) else str(k)).strip()
                    if q: n += 1; cell_qs.add(q); harvested.setdefault(q, []).append(i)
                c["seed_results"].append({"seed": s_, "n": n})
            c["harvested"] = len(cell_qs) if any(x["n"] is not None for x in c["seed_results"]) else None
            c["seeds_measured"] = sum(1 for x in c["seed_results"] if x["n"] is not None); c["seeds_hit"] = sum(1 for x in c["seed_results"] if x["n"])
        new = [q for q in harvested if q not in rowmap]
        got = self._kwinfo(new, "ads_info", "편익 셀 볼륨(ads_info)", "benefit_ads_info") if new else {}
        noise_re, _ = self._noise_re(); added = []
        for q, idxs in harvested.items():
            row = rowmap.get(q)
            if row is None:
                m = ((got.get(q) or {}).get("ads_metrics") or {}); v = m.get("volume_avg"); measured = (q in got) or (q in getattr(self, "_requested", set()))
                row = {"q": q, "seed": cells[idxs[0]]["seed"], "v": v if v is not None else (0 if measured else None), "trend": m.get("volume_trend"),
                       "language_only": measured and not v, "noise": bool(noise_re.search(q.lower())) if noise_re else False, "space_context": False,
                       "mentions_anchor": self.category.lower().replace(" ", "") in q.lower().replace(" ", ""),
                       "off_feature": bool(self.off_re.search(q.lower())) if self.off_re else False}
                rowmap[q] = row; added.append(row)
            row["benefit_cells"] = sorted(set(row.get("benefit_cells") or []) | set(idxs))
        catn = re.sub(r"\s+", "", cat).lower()
        cts = sense.get("consumer_terms_confirmed") if sense.get("consumer_term_sense") else (sense.get("consumer_terms") or [])   # 동음이의 판정 어휘는 기능 연결에서 제외
        link_terms = [re.sub(r"\s+", "", x).lower() for x in (cts or [])] + [re.sub(r"\s+", "", x).lower().replace(catn, "") for x in (sense.get("feature_variants") or []) + (sense.get("benefit_keywords") or [])]   # 일반어는 어순 그대로(동음이의 구분), 변형·편익어는 품목 제거
        link_terms = [x for x in link_terms if len(x) >= 2]
        ROLE = {"search_target": "검색 타겟(입찰 가능 검색어)", "weak_signal": "약한 신호 — 소재 + 저비용 검색", "language_only": "표현만 존재 — 크리에이티브 소재",
                "narrative_only": "크리에이티브 소재 — 기사·AI 요약에 존재, 실측 검색어 없음(대두 맥락 후보)",
                "benefit_narrative": "크리에이티브 소재 후보 — 서사에 편익 어휘만 일치(품목·기능 미언급 · 약한 서사)", "no_evidence": "근거 없음 — 제외 후보", "unmeasured": "미수집"}
        ben_lex = [x.lower() for x in (sense.get("benefit_lexemes") or []) if x]
        all_ns = list(dict.fromkeys(ns for c in cells for ns in (c.get("narrative_seeds") or [])))
        ns_vol = {}
        if all_ns:                                                                    # 서사 시드는 실제 쿼리여야 serp 데이터가 있다 — 존재 확인(1크레딧/건) 후 볼륨 있는 것만 조회
            got_ns = self._kwinfo(all_ns, "ads_metrics", "서사 시드 존재 확인", "narrative_seeds_ads_metrics")
            ns_vol = {k: ((got_ns.get(k) or {}).get("ads_metrics") or {}).get("volume_avg") for k in all_ns}
            self.log("  서사 시드 존재 확인: " + " · ".join(f"{k} {ns_vol[k] or '[인덱스 밖]'}" for k in all_ns))
        ev_items = ((self.v05.get("evidence") or {}).get("items") or [])          # 서사 증거(serp) 대조 — 검색어가 없어도 기사·AI 요약에 등장하는 맥락을 보존
        for c in cells:
            hits = []
            for it in ev_items:
                txt = (it.get("text") or "") + " " + (it.get("snippet") or "")
                if any(tm in txt for tm in c["narrative_terms"]):
                    hits.append({"kind": it.get("kind"), "seed": it.get("seed"), "text": txt.strip()[:180], "collected_at": it.get("collected_at"), "raw_file": f"raw/serp_{self._slug(it.get('seed') or '')}.json"})
            c["serp_hits"] = len(hits); c["serp_examples"] = hits[:3]
            # 서사 전용 시드 — 품목을 뗀 상황어로 serp만 조회(SERP_COST=30크레딧/시드). 결과 중 품목·기능 어휘가 함께 나오는 항목만 '관련 서사'로 인정
            c["narrative_seed_results"] = []; rel_terms = [catn] + [re.sub(r"\s+", "", x).lower() for x in (sense.get("consumer_terms") or []) + (sense.get("feature_variants") or [])]
            for ns in c.get("narrative_seeds") or []:
                if not ns_vol.get(ns):
                    c["narrative_seed_results"].append({"seed": ns, "items": 0, "relevant": 0, "volume": ns_vol.get(ns), "note": "인덱스 밖(검색량 없음) — serp 데이터 없음, 미조회"}); continue
                name = f"serp_{self._slug(ns)}"; r = self._load_raw_or(name)
                if r is None:
                    if self.a.dry_run or (self.replay and not self.a.replay_topup):
                        self.log(f"  [{'dry-run' if self.a.dry_run else 'replay'}] serp({ns}) 미수집"); c["narrative_seed_results"].append({"seed": ns, "items": None, "relevant": None, "volume": ns_vol.get(ns), "note": "검색량 있음 — serp 미수집(replay/dry-run) · '근거 없음'이 아니라 미측정"}); continue
                    self.ledger.check(SERP_COST, f"서사 시드 {ns}")
                    r = serp.fetch(self._client(), ns, gl=self.gl, num=20)
                    self.ledger.add("serp", {"kw": ns, "what": f"서사 시드 {c['dim']}:{c['label']}"}, r); self.save_raw(name, r)
                ts = r.get("request_at") or ""; items = []
                for txt in serp.ai_overview_snippets(r): items.append(("aio", txt))
                for q in serp.questions(r): items.append(("paa", (q.get("question") or q.get("title") or "") + " " + (q.get("snippet") or "")))
                for o in serp.organic(r)[:8]: items.append(("organic", (o.get("title") or "") + " — " + (o.get("snippet") or "")))
                rel = [(k, x) for k, x in items if any(rt and rt in re.sub(r"\s+", "", x).lower() for rt in rel_terms)]
                rel_set = {x for _, x in rel}
                ben = [(k, x) for k, x in items if x not in rel_set and any(bl in x.lower() for bl in ben_lex)]      # 편익 어휘만 일치 — 품목·기능 미언급(약한 서사, 별도 등급)
                c["narrative_seed_results"].append({"seed": ns, "items": len(items), "relevant": len(rel), "benefit_only": len(ben), "volume": ns_vol.get(ns), "raw_file": f"raw/{name}.json", "collected_at": ts})
                for k, x in rel[:2]:
                    hits.append({"kind": k, "seed": ns, "text": x.strip()[:180], "collected_at": ts, "raw_file": f"raw/{name}.json", "narrative_seed": True, "grade": "strict"})
                for k, x in ben[:2]:
                    c.setdefault("benefit_examples", []).append({"kind": k, "seed": ns, "text": x.strip()[:180], "collected_at": ts, "raw_file": f"raw/{name}.json", "narrative_seed": True, "grade": "benefit"})
            c["narrative_seed_hits"] = sum((x["relevant"] or 0) for x in c["narrative_seed_results"])
            c["benefit_narrative_hits"] = sum((x.get("benefit_only") or 0) for x in c["narrative_seed_results"]); c.setdefault("benefit_examples", [])
            c["serp_hits"] = len(hits); c["serp_examples"] = (c["serp_examples"] + [h for h in hits if h.get("narrative_seed")])[:4]
        for i, c in enumerate(cells):
            mine = [r for r in rowmap.values() if i in (r.get("benefit_cells") or [])]
            off = sum(1 for r in mine if r.get("off_feature")); rows = [r for r in mine if not r["noise"] and not r.get("off_feature")]
            withv = [r for r in rows if r["v"]]; vol = sum(r["v"] for r in withv); lang = sum(1 for r in rows if r["language_only"])
            linked = [r for r in rows if any(lt in re.sub(r"\s+", "", r["q"]).lower() for lt in link_terms)]   # 기능·편익 어휘를 품은 쿼리만 '기능 연결'
            if c["harvested"] is None: verdict = "unmeasured"
            elif len(withv) >= 3 and vol >= HUB_FLOOR: verdict = "search_target"
            elif vol > 0: verdict = "weak_signal"
            elif lang > 0: verdict = "language_only"
            elif c.get("serp_hits"): verdict = "narrative_only"
            elif c.get("benefit_narrative_hits"): verdict = "benefit_narrative"
            else: verdict = "no_evidence"
            role = ROLE[verdict]
            if verdict in ("search_target", "weak_signal") and not linked:
                role += " — 품목 수요(기능 연결 미확인)"
            c.update({"n": len(rows), "with_volume": len(withv), "volume_sum": vol, "language_only": lang, "off_feature_n": off,
                      "feature_linked_n": len(linked), "feature_linked_v": sum((r["v"] or 0) for r in linked), "linked_examples": [r["q"] for r in sorted(linked, key=lambda r: -(r["v"] or 0))[:3]],
                      "top": [{"q": r["q"], "v": r["v"]} for r in sorted(withv, key=lambda r: -r["v"])[:5]], "verdict": verdict, "role": role})
            self.log(f"  [{c['dim']}/{c['w']}] {c['label']} ← 시드 {c.get('seeds_hit', 0)}/{c.get('seeds_measured', 0)} 적중 {[x['seed'] for x in c['seed_results'] if x['n']]} 수확 {c['harvested'] if c['harvested'] is not None else '미수집'} · 볼륨 {len(withv)}건 {vol:,} · 언어 {lang} · 기능 외 {off} · 기능 연결 {len(linked)} · 서사 {c.get('serp_hits', 0)}(서사 시드 {c.get('narrative_seed_hits', 0)}/{sum((x['items'] or 0) for x in c.get('narrative_seed_results') or [])} · 편익 어휘만 {c.get('benefit_narrative_hits', 0)}) → {verdict}{'' if linked or verdict not in ('search_target', 'weak_signal') else '(품목 수요)'}")
        if added:
            longtail.setdefault("rows", []).extend(added); longtail["rows"].sort(key=lambda r: -(r["v"] or 0)); rows_all = longtail["rows"]
            longtail.update({"n": len(rows_all), "with_volume": sum(1 for r in rows_all if r["v"]), "language_only": sum(1 for r in rows_all if r["language_only"]),
                             "unmeasured": sum(1 for r in rows_all if r["v"] is None), "volume_sum": sum((r["v"] or 0) for r in rows_all),
                             "off_feature_n": sum(1 for r in rows_all if r.get("off_feature")), "benefit_added_n": len(added), "measured": True})
        # 정렬 우선순위(2026-08-22 확정) — A 검색 타겟·기능 연결 → B 약한 신호·기능 연결 → C 대두 맥락(검색어 0·서사 있음) → D 품목 수요(검색량 있으나 기능 연결 0)
        #   → E 표현만 → F 근거 없음 → G 미수집. 같은 단계 안에서는 볼륨합 ↓ → 서사 건수 ↓ → 기능 연결 ↓ → 사전 순서
        TIER = {"A": "검색 타겟 · 기능 연결", "B": "약한 신호 · 기능 연결", "C": "서사 맥락 (기능 연결 검색어 없음 · 기사/AI 요약에 품목·기능 언급)", "C2": "편익 어휘 일치 서사 (품목·기능 미언급 — 약한 서사)", "D": "품목 수요 (기능 연결 미확인 · 서사 없음)", "E": "표현만", "F": "근거 없음", "G": "미수집"}
        def tier(c):
            v, ln, sh = c["verdict"], c.get("feature_linked_n", 0), c.get("serp_hits", 0)
            if v == "search_target": return "A" if ln else "D"
            if v == "weak_signal": return "B" if ln else ("C" if sh else "D")
            if v == "language_only": return "C" if sh else "E"
            return {"narrative_only": "C", "benefit_narrative": "C2", "no_evidence": "F", "unmeasured": "G"}[v]
        for i, c in enumerate(cells): c["tier"] = tier(c); c["tier_label"] = TIER[c["tier"]]; c["_lex"] = i
        cells.sort(key=lambda c: (c["tier"], -(c.get("serp_hits") or 0) if c["tier"] == "C" else -(c.get("volume_sum") or 0), -(c.get("volume_sum") or 0) if c["tier"] == "C" else -(c.get("serp_hits") or 0), -(c.get("feature_linked_n") or 0), c["_lex"]))
        for r_, c in enumerate(cells, 1): c["rank"] = r_; c.pop("_lex", None)
        vc = {k: sum(1 for c in cells if c["verdict"] == k) for k in ROLE}
        res = {"measured": any(c["harvested"] is not None for c in cells), "benefit": sense.get("benefit"), "category": cat, "cells": cells, "verdict_counts": vc,
               "tier_counts": {k: sum(1 for c in cells if c["tier"] == k) for k in TIER}, "tier_labels": TIER,
               "sort_rule": "A 검색 타겟·기능 연결 → B 약한 신호·기능 연결 → C 서사 맥락(기사/AI 요약에 품목·기능 언급) → C2 편익 어휘만 일치 서사 → D 품목 수요 → E 표현만 → F 근거 없음 → G 미수집 · 단계 내 볼륨합↓ 서사↓ 기능 연결↓ (C는 서사↓ 볼륨↓)",
               "corpus_added": len(added), "dropped_cells": dropped, "floor": {"hub_floor": HUB_FLOOR, "min_queries": 3},
               "link_terms": link_terms, "narrative_source": "serp(AI 요약·연관 질문·자연결과) 발췌 — 수집 시점 스냅샷", "note": "검색량 있는 셀이 우선이지만, 검색어는 없고 기사·AI 요약에만 있는 셀(narrative_only)은 새로 대두되는 맥락 후보로 보존한다(이미 대응 중인 명제일 수 있는 고볼륨 셀과 구분). 셀 판정은 검색어 근거 강도(볼륨·건수)이지 상황의 실제 빈도가 아니다. '기능 연결'은 셀 쿼리에 기능 고유명·소비자 일반어·편익 어휘가 들어간 건수 — 0이면 그 세그먼트의 품목 수요일 뿐 이 기능의 수요로 읽지 않는다 — '표현만'·'근거 없음' 셀도 기사·AI 요약에 서사가 있으면 크리에이티브 소재로 쓸 수 있다(검색 타겟 아님). 노이즈·기능 외(off_feature) 쿼리는 셀 집계에서 제외"}
        self.log(f"  셀 판정 {vc} · 코퍼스 합류 {len(added)}")
        return res

    def _noise_re(self):
        try:
            p = self.adapter.get("A2_noise_lexicon", "patterns") or {}
            pats = list(p.get("common") or []) + list(p.get(self.gl) or []); raw = list(p.get(self.gl + "_regex") or [])
            parts = [re.escape(x) for x in pats] + raw
            return (re.compile("|".join(parts), re.I) if parts else None), "adapter:A2"
        except Exception:   # noqa: BLE001
            return None, "none"

    def s5_hypotheses(self, sense: dict, evidence: dict, longtail: dict, canvass: dict, journeys: dict) -> dict:
        """S5 · 가설 선행 — ① 가설 파일이 없으면 증거·코퍼스로 LLM 태스크 발주(0크레딧) ② 있으면 키워드로 확증(supported/unsupported/proposed 보존)."""
        hp = Path(self.a.hypotheses) if self.a.hypotheses else (self.out / "core" / "hypotheses.json")
        if not hp.is_absolute() and not hp.exists(): hp = (self.out / hp)
        corpus = {}
        for r in (longtail.get("rows") or []): corpus[r["q"]] = r
        for k, o in (canvass.get("rows") or {}).items(): corpus.setdefault(k, {"q": k, "v": o.get("v") or 0, "seed": "canvass", "language_only": not o.get("v"), "noise": False, "space_context": False})
        if not hp.exists():
            ev_items = [i for i in (evidence.get("items") or []) if i["kind"] in ("aio", "paa")][:60] + [i for i in (evidence.get("items") or []) if i["kind"] == "organic"][:30]
            top = [r for r in (longtail.get("rows") or []) if r["v"]][:80]; zero = [r for r in (longtail.get("rows") or []) if r["language_only"]][:40]
            blind = bool(self.a.blind)
            task = {"task": "hypotheses_7w", "blind": blind, "run_id": self.run_id, "category": self.category, "gl": self.gl, "anchor_level": self.a.anchor_level,
                    "instruction": ("증거(AIO·PAA·자연결과 발췌)와 롱테일 코퍼스를 읽고 7W 프레임으로 상황 가설을 10~20개 작성한다. 각 가설은 구매 전(pre) 상황이어야 하며 "
                                    "W1(Why) 필수 + W2(When) 또는 W3(Where) 중 하나 이상 + 총 3슬롯 이상. 근거가 될 법한 코퍼스 키워드(keywords_expected)를 5~15개 적되 "
                                    "코퍼스 밖 키워드는 만들지 않는다(코퍼스 봉인). keywords_expected는 **2~3어절의 소비자 실제 검색 형태**로 쓴다 — "
                                    "4어절 이상 결합은 코퍼스보다 길어 부분 문자열로도 매칭되지 않는다(2026-08-22 실측: 예측 7건 중 1건만 매칭). "
                                    "형태는 **품목 + 상황어**여야 한다(공간·시점·생애사건·상태·제약·증상). "
                                    "품목 + 일반어는 쓰지 않는다 — 검토어(추천·비교·후기·가격·단점)·브랜드·라인·세그먼트·스펙·구매형태는 "
                                    "그 상황이 아니라 품목 전체의 수요라서, 아무 가설에나 매칭돼 판정을 무력화한다(2026-08-28 실측: 짧은 일반어 세트는 "
                                    "타 가설의 예측어로도 100%가 supported였다). 규모가 큰 일반어를 넣어 근거를 부풀리면 상황 볼륨 집계에서 자동 분리된다. "
                                    "구매 후 상황(설치 직후·사용 중 불편)은 stage=post 로 표시. 서사는 assumption 등급. "
                                    "편익 분해 셀(benefit_decomposition)이 있으면 셀마다 가설 1건 이상을 쓰고 cell='{dim}:{label}'을 기입 — not_this_feature 어휘는 이 기능의 수요가 아니므로 가설에 쓰지 않는다. "
                                    "출력: core/hypotheses.json = {\"prompt_version\": \"…\", \"hypotheses\": [{id, narrative, stage, slots{W1..W7:{text}}, keywords_expected[], nano_intents[], kbf[], source_evidence[]}]}"),
                    "requirements": {"stage": "pre", "W1": "required", "W2_or_W3": "required", "min_slots": 3, "corpus_sealed": True},
                    "keyword_rules": {"form": f"{self.category} + 상황어(공간·시점·생애사건·상태·제약·증상)", "length": "2~3어절",
                                      "avoid_form": f"{self.category} + 일반어",
                                      "avoid_classes": list(GENERIC_CLASSES) + ["EvalTerm"],
                                      "avoid_examples": [f"{self.category} {e}" for e in EVAL_TERMS]
                                                        + [f"{lab} {self.category}" for lab in list(dict.fromkeys(
                                                            [l for l, c in self.generic_labels().items() if c == "Brand"]))[:3]],
                                      "why": "일반어는 그 상황이 아니라 품목 전체의 수요다 — 아무 가설에나 매칭돼 판정을 무력화하고, 상황 볼륨 집계에서 분리된다",
                                      "note": "avoid_examples는 온톨로지 사전 라벨에서 생성 — 코퍼스 노출이 아니다"},
                    "families": sense.get("families"), "evidence": ev_items, "paa": (evidence.get("paa") or [])[:40],
                    "benefit": sense.get("benefit"), "consumer_terms": sense.get("consumer_terms"), "not_this_feature": sense.get("not_this_feature"),
                    "benefit_decomposition": [{"cell": f"{c['dim']}:{c['label']}", "w": c["w"], "seed": c["seed"], "verdict": c["verdict"],
                                               "top_keywords": ([] if blind else [t["q"] for t in c["top"]])}
                                              for c in ((self.v05.get("benefit") or {}).get("cells") or [])],
                    "corpus_top": [] if blind else [{"q": r["q"], "v": r["v"]} for r in top],
                    "corpus_language_only": [] if blind else [r["q"] for r in zero],
                    "related": [] if blind else [x["q"] for x in (evidence.get("related") or [])][:60],
                    "journey_nodes_sample": [] if blind else sorted({n for ps in journeys.values() for p in ps for n in p})[:80],
                    "blind_rule": ("증거(AIO·PAA·자연결과)만 보고 작성. keywords_expected는 코퍼스 복사가 아니라 소비자가 칠 법한 검색어 예측 — 안 맞으면 unsupported로 남는다. "
                                   "짧게 쓴다: 2~3어절 · 실제로 치는 형태('집주인 <품목> 수리'가 아니라 '<품목> 고장 집주인'). 길게 특정할수록 빗나간다. "
                                   "단 짧게 쓴다고 일반어로 쓰지는 않는다 — 품목+상황어로 쓴다('<품목> 추천'·'<브랜드> <품목>'이 아니라 '원룸 <품목> 소음'·'자취 <품목> 용량')") if blind else None}
            tname = "hypothesis_tasks_blind.json" if blind else "hypothesis_tasks.json"
            (self.out / "core" / tname).write_text(json.dumps(task, ensure_ascii=False, indent=1), encoding="utf8")
            self.log(f"S5 가설 선행 — 가설 파일 없음 → core/{tname} 발주 (증거 {len(ev_items)} · 코퍼스 상위 {len(top)} · 언어층 {len(zero)}). 작성 후 --hypotheses 로 재실행(0크레딧)")
            return {"status": "awaiting_llm", "task_file": "core/hypothesis_tasks.json", "hypotheses": []}
        H = json.loads(hp.read_text(encoding="utf8")); hyps = H.get("hypotheses") or []
        cellmap = {f"{c['dim']}:{c['label']}": c for c in ((self.v05.get("benefit") or {}).get("cells") or [])}          # v0.6 B13
        self.log(f"S5 가설 확증 — {len(hyps)}건 (prompt_version {H.get('prompt_version', '?')})")
        norm = lambda t: re.sub(r"\s+", "", str(t)).lower()
        ckeys = {norm(q): q for q in corpus}
        # ② 재수확 분리 — 판정 기준 시드(baseline) 밖에서 온 매칭은 corpus_extended로 표시하고 기각률을 따로 낸다.
        #    2026-08-22 실측: 기각된 가설의 어휘로 시드를 넓히자 기각률이 0%로 내려갔다.
        seeds_now = sorted({(r.get("seed") or "?") for r in corpus.values()})
        (self.out / "core" / "s5_seeds.json").write_text(json.dumps(seeds_now, ensure_ascii=False, indent=1), encoding="utf8")
        base_seeds = None
        if getattr(self.a, "baseline_seeds", None):
            bs = self.a.baseline_seeds
            try:
                bp = Path(bs)
                base_seeds = set(json.loads(bp.read_text(encoding="utf8"))) if bp.exists() else set(x.strip() for x in bs.split(",") if x.strip())
            except Exception as e:
                self.log(f"  [경고] --baseline-seeds 해석 실패({e}) — 재수확 분리 생략")
            if base_seeds is not None:
                added = [s for s in seeds_now if s not in base_seeds]
                self.log(f"  판정 기준 시드 {len(base_seeds)} · 이번 코퍼스 시드 {len(seeds_now)} · 판정 후 추가 {len(added)}: {added[:6]}")

        # ⑤ 미매칭 예측어 직접 실측 — 코퍼스 교집합은 S3 수확 커버리지에 좌우된다.
        #    2026-08-28 실측: 미매칭 예측어 대부분이 볼륨을 가진 가설(커버리지 공백)과 거의 없는 가설(진짜 예측 실패)이 갈렸다.
        direct = {}
        if getattr(self.a, "measure_unmatched", False):
            need = []
            for h in hyps:
                for k in (h.get("keywords_expected") or []):
                    if k and not match_corpus([k], ckeys, corpus, self.a.match) and k not in need:
                        need.append(k)
            cap = int(getattr(self.a, "measure_unmatched_max", 40) or 40)
            if len(need) > cap:
                self.log(f"  [상한] 미매칭 예측어 {len(need)}건 중 {cap}건만 실측 — 나머지 {len(need) - cap}건은 미측정으로 남김(조용한 절단 금지)")
                need = need[:cap]
            if need:
                got = self._measure_live(need, "S5 미매칭 예측어 직접 실측", "s5_unmatched_ads_metrics")
                n_zero = n_none = 0
                for k in need:
                    v = ((got.get(k) or {}).get("ads_metrics") or {}).get("volume_avg")
                    if v is None: n_none += 1; continue
                    if not v: n_zero += 1; continue
                    direct[norm(k)] = {"q": k, "v": v, "seed": "direct(S5)", "language_only": False,
                                       "noise": False, "space_context": False, "_direct": True}
                self.log(f"  직접 실측 {len(need)}건 → 볼륨 보유 {len(direct)} · 볼륨 0 {n_zero} · 미측정(무응답) {n_none}")

        out = []; n_sup = n_unsup = 0
        for h in hyps:
            exp = [k for k in (h.get("keywords_expected") or []) if k]
            matched = match_corpus(exp, ckeys, corpus, self.a.match)
            seen = {m["q"] for m in matched}
            for k in exp:                                  # ⑤ 코퍼스에 없던 예측어의 직접 실측분
                dm = direct.get(norm(k))
                if dm and dm["q"] not in seen:
                    matched.append(dm); seen.add(dm["q"])
            n_pred = len(matched)
            tagged = []                                   # M3ⓒ 잔여 태깅 — 예측이 아니라 코퍼스를 본 뒤 붙인 키워드(post-hoc). 분리 집계
            for k in (h.get("keywords_tagged") or []):
                nk = norm(k)
                if nk in ckeys and ckeys[nk] not in seen: tagged.append(corpus[ckeys[nk]]); seen.add(ckeys[nk])
            matched = matched + tagged
            off_n = sum(1 for m in matched if m.get("off_feature"))                                                        # v0.6 B15 — 기능 외 수요는 근거에서 제외
            matched = [m for m in matched if not m.get("off_feature")]
            vol = sum((m.get("v") or 0) for m in matched); lang = sum(1 for m in matched if m.get("language_only"))
            # ⑥ 상황 근거 / 일반어 분리 — HUB_FLOOR는 상황 볼륨으로만 판정한다.
            #    슬롯 텍스트에서 품목어를 뺀 어휘가 그 가설의 '상황'이다(S6 _hub_sets와 같은 발상).
            cat_toks = {norm(x) for x in re.findall(r"[가-힣A-Za-z0-9]+", self.category) if len(x) >= 2}
            kinds = {m["q"]: self.kw_kind(m["q"], cat_toks) for m in matched}
            vol_sit = sum((m.get("v") or 0) for m in matched if kinds[m["q"]][0] == "situational")
            vol_gen = vol - vol_sit
            floor_basis = getattr(self.a, "floor_basis", "situational")
            vol_floor = vol_sit if floor_basis == "situational" else vol
            terms = [norm(m["q"]) for m in matched] + [norm(v.get("text", "")) for v in (h.get("slots") or {}).values() if isinstance(v, dict) and len(norm(v.get("text", ""))) >= 2]
            co = sum(1 for ps in journeys.values() for p in ps if any(t and t in norm(" ".join(p)) for t in terms[:30]))
            # v0.6 — 증거 사슬(evidence_chain): 판정의 모든 근거를 원천(커넥터·시드·원본 파일·수집시각)까지 추적 가능하게 남긴다
            ev_items = evidence.get("items") or []; chain_serp = []
            for s_ in (h.get("source_evidence") or []):
                m_ = re.match(r"\s*(aio|paa|organic)\s*\[([^\]]+)\]\s*(.*)", str(s_), re.I)
                kind, seed, frag = (m_.group(1).lower(), m_.group(2).strip(), m_.group(3).strip()) if m_ else (None, None, str(s_))
                hit = None; key_ = norm(frag)[:12]
                for it in ev_items:
                    if (kind is None or it.get("kind") == kind) and (seed is None or it.get("seed") == seed) and key_ and key_ in norm((it.get("text") or "") + " " + (it.get("snippet") or "")):
                        hit = it; break
                if hit is None and seed:
                    hit = next((it for it in ev_items if it.get("seed") == seed and (kind is None or it.get("kind") == kind)), None); loose = True
                else: loose = False
                chain_serp.append({"claim": str(s_), "kind": kind, "seed": seed, "resolved": hit is not None, "loose": loose and hit is not None,
                                   "text": (hit or {}).get("text"), "snippet": (hit or {}).get("snippet"), "url": (hit or {}).get("url"), "collected_at": (hit or {}).get("collected_at"),
                                   "raw_file": (f"raw/serp_{self._slug(seed)}.json" if seed else None), "connector": "serp"})
            tagged_q = {x["q"] for x in tagged}
            chain_kw = [{"q": m["q"], "v": m.get("v"), "language_only": m.get("language_only"), "harvest_seed": m.get("seed"), "post_hoc": m["q"] in tagged_q,
                         "raw_file": (f"raw/longtail_{self._slug(m['seed'])}.json" if m.get("seed") and m.get("seed") != "canvass" else "raw/canvass.json"),
                         "connector": "intent_finder(vt=0) 수확 → keyword_info ads_info 실측" if m.get("seed") != "canvass" else "keyword_info ads_metrics(캔버스)"} for m in matched]
            path_ex = []
            for anchor_, ps in journeys.items():
                for p in ps:
                    if any(t_ and t_ in norm(" ".join(p)) for t_ in terms[:30]):
                        path_ex.append({"anchor": anchor_, "path": list(p), "raw_file": f"raw/paths_{self._slug(anchor_)}.json"})
                        if len(path_ex) >= 3: break
                if len(path_ex) >= 3: break
            chain = {"serp": chain_serp, "unresolved_claims": sum(1 for c in chain_serp if not c["resolved"]), "keywords": chain_kw,
                     "paths": {"co_path": co, "n": sum(len(ps) for ps in journeys.values()), "examples": path_ex, "connector": "path_finder"},
                     "cluster": {"used": False, "note": "cluster_finder 미호출 — 관계망(클러스터) 근거 없음(이 run의 설계 범위 밖)"},
                     "note": "판정 근거 = ① serp 발췌(시드·수집시각·원본 파일) ② 검색어(수확 시드·실측 커넥터·원본 파일·사후 여부) ③ 여정 동반 경로 예시 ④ 관계망 사용 여부"}
            slots = h.get("slots") or {}; filled = [w for w in ("W1", "W2", "W3", "W4", "W5", "W6", "W7") if (slots.get(w) or {}).get("text")]
            # ① 근거는 실측 매칭으로만 센다 — 언어층(볼륨 0)은 matched에 보존하되 supported/strong 판정에서 제외.
            #    "언어가 존재한다"와 "수요가 확인됐다"는 다르다(2026-08-22 실측: 볼륨 0짜리 1건으로 supported였던 사례).
            measured = [m for m in matched if (m.get("v") or 0) > 0]
            ext_n = (sum(1 for m in matched if (m.get("seed") or "?") not in base_seeds and not m.get("_direct")) if base_seeds is not None else 0)
            base_measured = ([m for m in measured if (m.get("seed") or "?") in base_seeds or m.get("_direct")] if base_seeds is not None else measured)
            overspec = [k for k in exp if len(str(k).split()) >= 4]      # ④ 과잉 특정 — 코퍼스보다 길면 부분 문자열도 안 걸린다
            cat_toks0 = {norm(x) for x in re.findall(r"[가-힣A-Za-z0-9]+", self.category) if len(x) >= 2}
            gen_pred = [k for k in exp if self.kw_kind(k, cat_toks0)[0] == "generic"]   # 발주 규칙(품목+상황어) 준수 여부
            req = {"stage_pre": (h.get("stage") or "pre") == "pre", "W1": "W1" in filled, "W2_or_W3": ("W2" in filled or "W3" in filled), "min_slots": len(filled) >= 3, "keyword_backed": len(measured) > 0}
            qualified = all(req.values())
            demoted_to = None
            if matched and not qualified:
                demoted_to = ("Lifecycle/UseCase(구매 후)" if not req["stage_pre"] else "KBF/Attribute(상황 슬롯 없음)" if not (req["W2_or_W3"] and req["min_slots"]) else "검토")
            status = "supported" if measured else "unsupported"
            if status == "supported": n_sup += 1
            else: n_unsup += 1
            strength = "strong" if (len(measured) >= 3 and vol_floor >= HUB_FLOOR) else ("weak" if measured else "none")
            out.append({**{k: v for k, v in h.items() if k != "keywords_expected"}, "keywords_expected": exp, "status": status, "strength": strength,
                        "matched": [{"q": m["q"], "v": m.get("v"), "language_only": m.get("language_only"), "noise": m.get("noise"), "space_context": m.get("space_context"),
                                     "kind": kinds[m["q"]][0], "generic_class": kinds[m["q"]][1],
                                     "matched_source": ("direct" if m.get("_direct") else "corpus"),
                                     "corpus_extended": (bool(base_seeds is not None and not m.get("_direct") and (m.get("seed") or "?") not in base_seeds))} for m in matched],
                        "cell": h.get("cell"), "cell_verdict": (cellmap.get(h.get("cell") or "") or {}).get("verdict"), "cell_role": (cellmap.get(h.get("cell") or "") or {}).get("role"),
                        "backing": {"matched_n": len(matched), "measured_n": len(measured), "direct_measured_n": sum(1 for m in matched if m.get("_direct")),
                                    "volume_situational": vol_sit, "volume_generic": vol_gen, "floor_basis": floor_basis,
                                    "situational_measured_n": sum(1 for m in measured if kinds[m["q"]][0] == "situational"),
                                    "generic_examples": sorted([{"q": m["q"], "v": m.get("v") or 0, "class": kinds[m["q"]][1]}
                                                                for m in matched if kinds[m["q"]][0] == "generic"],
                                                               key=lambda x: -x["v"])[:5],
                                    "corpus_extended_n": ext_n, "overspecified_n": len(overspec),
                                    "generic_predicted_n": len(gen_pred), "generic_predicted": gen_pred[:5],
                                    "predicted_n": n_pred, "tagged_n": len(tagged), "post_hoc": len(tagged) > 0, "off_feature_excluded": off_n,
                                    "volume_sum": vol, "language_only_n": lang, "co_path": co, "denominator_basis": "매칭 키워드 볼륨 합(언어층 0 포함 안 함) — 규모가 아니라 근거 강도 · tagged는 post-hoc"},
                        "demoted_to": demoted_to, "evidence_chain": chain,
                        "requirements": req, "qualified": qualified, "slot_coverage": len(filled),
                        "hub_verdict": ("candidate" if qualified and strength == "strong" else "deferred" if qualified else "demoted(요건 미달)" if matched else "unsupported"),
                        "unsupported_reason": (None if measured else
                                               ("언어층만 매칭(볼륨 0) — 언어는 존재하나 수요 미확인" if matched else
                                                "코퍼스 미매칭 — 언어 부재 또는 시드 범위 밖(해당 어휘 시드로 S3 재수확 후 재판정 · --measure-unmatched 로 직접 실측 가능)"))})
            self.log(f"  {h.get('id')} {status}/{strength} — 매칭 {len(matched)}(실측 {len(measured)} · 예측 {n_pred} · 태깅 {len(tagged)} · 언어 {lang}"
                     + (f" · 직접 {sum(1 for m in matched if m.get('_direct'))}" if direct else "") + (f" · 확장 {ext_n}" if base_seeds is not None else "") + ")"
                     + f" · 볼륨합 {vol:,}(상황 {vol_sit:,} · 일반 {vol_gen:,}) · co_path {co} · 요건 {'✓' if qualified else '✗'} → {out[-1]['hub_verdict']}" + (f" [{demoted_to}]" if demoted_to else ""))
        shared = collections.Counter(m["q"] for h in out for m in h["matched"])
        for h in out:                                     # ⑥ 같은 키워드가 여러 가설의 근거면 표시(중복 계상 가시화)
            for m in h["matched"]:
                if shared[m["q"]] > 1: m["shared_with"] = shared[m["q"]] - 1
        n_gen_heavy = sum(1 for h in out if (h["backing"]["volume_situational"] or 0) < HUB_FLOOR <= (h["backing"]["volume_sum"] or 0))
        n_gen_pred = sum(1 for h in out if (h["backing"].get("generic_predicted_n") or 0) * 2 >= len(h.get("keywords_expected") or [1]))
        if n_gen_pred:
            self.warnings.append(f"발주 규칙 위반 — {n_gen_pred}건의 가설이 예측어 절반 이상을 품목+일반어로 썼다(브랜드·세그먼트·스펙·검토어). 상황어로 다시 발주할 것")
        n_thin = sum(1 for h in out if h["hub_verdict"] == "candidate" and (h["backing"].get("situational_measured_n") or 0) < 3)
        if n_thin:                                        # 게이트가 아니라 계기판 — 임계를 올리면 적재된 허브가 죽는다(2026-08-28 회귀)
            self.warnings.append(f"상황 근거 얇음 — 후보 {n_thin}건이 상황 실측 매칭 3건 미만이다(규모는 통과했으나 상황 어휘 근거가 얇다 · 사람 확인 권장)")
        if n_gen_heavy:
            self.warnings.append(f"일반어 의존 — {n_gen_heavy}건의 가설이 총 볼륨은 HUB_FLOOR를 넘지만 상황 볼륨은 미달이다(품목·브랜드·패싯 어휘로 규모가 부풀었다)")
        rej = round(n_unsup / len(hyps), 3) if hyps else None
        # ③ 순열 기준선 — 자기 예측어의 매칭이 '남의 예측어' 매칭보다 나은가. 같으면 supported는 그 가설에 대한 정보가 없다.
        #    2026-08-22 실측: 자기 예측어와 타 가설 예측어의 매칭 수가 같았다 — 기각률 0%의 진짜 원인.
        perm = []
        if len(hyps) >= 3:
            for h in hyps:
                for g in hyps:
                    if g is h: continue
                    perm.append(len(match_corpus(g.get("keywords_expected") or [], ckeys, corpus, self.a.match)))
        own_mean = round(sum(len(h["matched"]) for h in out) / len(out), 2) if out else None
        perm_mean = round(sum(perm) / len(perm), 2) if perm else None
        perm_sup = round(sum(1 for x in perm if x >= 1) / len(perm), 3) if perm else None
        permutation = {"own_mean": own_mean, "perm_mean": perm_mean, "perm_supported_rate": perm_sup,
                       "discriminating": (None if perm_mean is None else bool(own_mean > perm_mean * 1.2)),
                       "note": "자기 예측어 매칭 평균 vs 타 가설 예측어 매칭 평균 — 같으면 판정이 가설을 구별하지 못한다"}
        sup_base = sum(1 for h in out if any((m.get("v") or 0) > 0 and not m.get("corpus_extended") for m in h["matched"]))
        rej_base = round(1 - sup_base / len(hyps), 3) if hyps else None
        if hyps and n_unsup == 0:
            self.warnings.append("가설 기각률 0% — 확증 편향 신호(정의서 §4 통제 ②): 코퍼스 밖 키워드 생성 여부 점검")
        if perm_sup is not None and perm_sup >= 0.5:
            self.warnings.append(f"순열 기준선 — 타 가설의 예측어로도 {perm_sup:.0%}가 supported. 판정이 가설을 구별하지 못한다(코퍼스 밀도 과다·매칭 규칙 과대)")
        if perm_mean is not None and own_mean is not None and own_mean <= perm_mean * 1.2:
            self.warnings.append(f"순열 기준선 — 자기 예측어 매칭 {own_mean} ≈ 타 가설 {perm_mean}. supported가 가설별 정보를 담지 못한다")
        if base_seeds is not None and rej_base is not None and rej is not None and rej_base > rej:
            self.warnings.append(f"재수확 효과 — 판정 기준 시드만 쓰면 기각률 {rej_base:.0%}인데 확장 코퍼스에서는 {rej:.0%}다. 판정 후 넓힌 코퍼스가 기각을 지웠다")
        n_over = sum(1 for h in out if h["backing"].get("overspecified_n", 0) * 2 >= len(h.get("keywords_expected") or [1]))
        if n_over:
            self.warnings.append(f"예측어 과잉 특정 — {n_over}건의 가설이 4어절 이상 결합어를 절반 넘게 썼다. 코퍼스보다 길면 부분 문자열로도 매칭되지 않는다")
        hubs = [{"id": f"CEP-{self.category}-H{i + 1:02d}", "hypothesis": h["id"], "label": h.get("label") or h.get("narrative", "")[:40], "hub_type": "situational", "status": "candidate",
                 "grade": "derived", "source": "hypothesis-first(S5)", "volume_sum": h["backing"]["volume_sum"], "slot_coverage": h["slot_coverage"],
                 "bridges": [{"combo": m["q"], "v": m["v"], "language_only": m["language_only"]} for m in h["matched"]],
                 "co_path_paths": h["backing"]["co_path"], "backing": f"supported({h['strength']}) · 키워드 {h['backing']['matched_n']} · co_path {h['backing']['co_path']}"}
                for i, h in enumerate(out) if h["hub_verdict"] == "candidate"]
        n_cand = sum(1 for h in out if h["hub_verdict"] == "candidate")
        n_pred_sup = sum(1 for h in out if h["backing"]["predicted_n"] > 0)
        rej_pred = round(1 - n_pred_sup / len(hyps), 3) if hyps else None        # 예측 키워드만으로의 기각률 — 블라인드 무결성 지표
        return {"status": "confirmed", "prompt_version": H.get("prompt_version"), "blind": bool(H.get("blind")), "match": self.a.match,
                "n": len(hyps), "supported": n_sup, "unsupported": n_unsup, "rejection_rate": rej, "rejection_rate_predicted_only": rej_pred,
                "rejection_rate_baseline": rej_base, "permutation": permutation,
                "volume_basis": {"floor_basis": getattr(self.a, "floor_basis", "situational"), "hub_floor": HUB_FLOOR,
                                 "note": "HUB_FLOOR는 상황 볼륨(슬롯 어휘를 담은 키워드)으로만 판정 — 품목·브랜드·패싯 일반어는 volume_generic으로 분리",
                                 "generic_heavy_n": n_gen_heavy},
                "thin_situational_n": n_thin,
                "measured_basis": "supported/strong 판정은 실측(볼륨>0) 매칭 기준 — 언어층은 matched에 보존하되 근거에서 제외",
                "direct_measured_n": sum(h["backing"].get("direct_measured_n", 0) for h in out),
                "corpus_extended_n": sum(h["backing"].get("corpus_extended_n", 0) for h in out),
                "baseline_seeds_used": (sorted(base_seeds) if base_seeds is not None else None),
                "post_hoc_n": sum(1 for h in out if h["backing"]["post_hoc"]),
                "candidates": n_cand, "selection_rate": round(n_cand / len(hyps), 3) if hyps else None,
                "verdict_counts": {k: sum(1 for h in out if h["hub_verdict"] == k) for k in ("candidate", "deferred", "demoted(요건 미달)", "unsupported")},
                "hypotheses": out, "hypothesis_hubs": hubs, "note": "서사=assumption · 매칭 키워드=measured/언어층 · 승격은 성립 요건+HUB_FLOOR · unsupported는 보존"}

    # ══════════ v0.5 S6 — 구별성·병합 판정 (정의서 §4.3 자카드) ══════════
    def _hub_sets(self, hub: dict, cat_tokens: set):
        """허브 비교 집합 2종 — lexemes: 키워드에서 품목을 뺀 렉심(정의서 '슬롯 값'의 대용) · tokens: 렉심 토큰 + 짧은 슬롯 값(≤10자).
        슬롯의 긴 서술문은 제외 — 자유 텍스트를 섞으면 자카드가 희석돼 판정이 무력화된다(2026-08-22 실측)."""
        stop = {"추천", "가격", "디시", "및", "vs", "등", "중", "시", "때", "위한", "위해", "하는", "있는", "더쿠", "클리앙", "블라인드"} | cat_tokens
        cat_re = re.compile("|".join(re.escape(t) for t in sorted(cat_tokens, key=len, reverse=True)))
        lex, toks = set(), set()
        def add_lex(text):
            l = re.sub(r"\s+", " ", cat_re.sub(" ", str(text).lower())).strip()
            if len(l) >= 2 and l not in stop:
                lex.add(l)
                for t in re.split(r"[\s·/(),.\-–—]+", l):
                    if len(t) >= 2 and t not in stop and not re.fullmatch(r"\d+[a-z%]*\+?", t): toks.add(t)
        for b in hub.get("bridges") or []: add_lex(b.get("combo") or b.get("q") or "")
        for k in hub.get("lexemes") or []: add_lex(k)
        for w in ("W1", "W2", "W3", "W4"):
            sv = (hub.get("slots") or {}).get(w)
            if isinstance(sv, dict) and sv.get("text") and sv.get("grade", "x") != "gap":
                for part in re.split(r"[·/,—]", sv["text"]):
                    part = part.strip()
                    if 2 <= len(part) <= 10 and not re.search(r"\d", part): add_lex(part)
        return lex, toks

    def s6_merge(self, hubs: list, hyps: list, splits: list | None) -> dict:
        """허브 간 구별성 — 자카드(렉심 집합) ≥0.7 병합 · 0.6~0.7 사람 판단 · 포함도(overlap/min) ≥0.8 & J≥0.3 = 흡수(하위 허브) 제안 · 그 외 유지."""
        cat_tokens = set(re.split(r"\s+", self.category.lower()))
        units = []
        if splits:
            for h in splits:
                if h.get("inherited"): continue
                units.append({"id": h["id"], "label": h.get("label"), "kind": "family-split", "status": h.get("status"),
                              "bridges": [{"combo": c} for c in h.get("bridges") or []], "slots": h.get("slots") or {}})
        else:
            for h in hubs:
                if h.get("source") == "hypothesis-first(S5)": continue
                units.append({"id": h["id"], "label": h.get("family"), "kind": "family", "status": h.get("status"), "bridges": h.get("bridges") or [], "slots": {}})
        for h in hyps:
            if h.get("hub_verdict") != "candidate": continue
            units.append({"id": h["id"], "label": h.get("label"), "kind": "hypothesis", "status": "candidate",
                          "bridges": [{"combo": m["q"]} for m in h.get("matched") or []], "slots": h.get("slots") or {}})
        sets = {u["id"]: self._hub_sets(u, cat_tokens) for u in units}
        pairs = []
        for i, a in enumerate(units):
            for b in units[i + 1:]:
                LA, TA = sets[a["id"]]; LB, TB = sets[b["id"]]
                jl = round(len(LA & LB) / len(LA | LB), 3) if (LA | LB) else 0.0
                jt = round(len(TA & TB) / len(TA | TB), 3) if (TA | TB) else 0.0
                cont = round(len(TA & TB) / min(len(TA), len(TB)), 3) if min(len(TA), len(TB)) else 0.0
                j = max(jl, jt)
                if j >= 0.7: verdict = "병합 제안"
                elif j >= 0.6: verdict = "사람 판단"
                elif cont >= 0.8 and j >= 0.3: verdict = "흡수 제안(하위 허브)"
                elif j >= 0.3 or len(LA & LB) >= 2: verdict = "연관(유지·교차참조)"
                else: verdict = "유지"
                pairs.append({"a": a["id"], "b": b["id"], "jaccard": j, "jaccard_lexeme": jl, "jaccard_token": jt, "containment": cont,
                              "shared_lexemes": sorted(LA & LB)[:8], "shared_tokens": sorted(TA & TB)[:10], "verdict": verdict})
        pairs.sort(key=lambda x: (-x["jaccard"], -x["containment"]))
        parent = {u["id"]: u["id"] for u in units}
        def find(x):
            while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
            return x
        for p_ in pairs:
            if p_["verdict"] in ("병합 제안", "흡수 제안(하위 허브)"): parent[find(p_["a"])] = find(p_["b"])
        groups = {}
        for u in units: groups.setdefault(find(u["id"]), []).append(u["id"])
        consolidated = [{"members": m, "proposed": len(m) > 1} for m in groups.values()]
        self.log(f"S6 구별성 — 허브 {len(units)} · 쌍 {len(pairs)} · 병합 {sum(1 for p_ in pairs if p_['verdict'] == '병합 제안')} · 흡수 {sum(1 for p_ in pairs if p_['verdict'].startswith('흡수'))} · 사람 판단 {sum(1 for p_ in pairs if p_['verdict'] == '사람 판단')} · 연관 {sum(1 for p_ in pairs if p_['verdict'].startswith('연관'))}")
        for p_ in pairs[:10]: self.log(f"  {p_['a']}×{p_['b']} J={p_['jaccard']} (렉심 {p_['jaccard_lexeme']} · 토큰 {p_['jaccard_token']} · 포함 {p_['containment']}) 공유 {p_['shared_tokens'][:5]} → {p_['verdict']}")
        return {"units": [{"id": u["id"], "label": u["label"], "kind": u["kind"], "n_lexemes": len(sets[u["id"]][0]), "lexemes": sorted(sets[u["id"]][0])[:16], "tokens": sorted(sets[u["id"]][1])[:16]} for u in units],
                "pairs": pairs, "consolidated": consolidated,
                "thresholds": {"merge": 0.7, "human": 0.6, "absorb_containment": 0.8, "related": 0.3},
                "note": "자카드 = 렉심 집합(키워드에서 품목 제거) 기준, 토큰 자카드와 포함도 병기(derived) — 긴 슬롯 서술문은 제외. 임계는 정의서 §4.3 초기값. 최종 병합·분리는 승인 세션(사람)"}

    # ── S3 · 상황측 여정 (situation_anchor — 도달률은 측정값) ──
    def s3_journeys(self, bridges: list[dict]) -> dict:
        k = DEPTH[self.a.depth]["journeys"]
        top = [b for b in bridges if (b["v"] or 0) >= BRIDGE_FLOOR][:k]
        out = {}
        if self.replay:
            for f in self.replay.glob("paths_*.json"):
                r = json.loads(f.read_text(encoding="utf8"))
                anchor = f.stem.replace("paths_", "")
                out[anchor] = r.get("data") or []
                self.log(f"S3 [replay] 여정 {anchor} — {len(out[anchor])}경로")
            return out
        for b in top:
            est = 50 + 40 * DEPTH[self.a.depth]["path_limit"]
            self.ledger.check(est, f"여정 {b['combo']}")
            if self.a.dry_run:
                self.log(f"S3 [dry-run] path_finder({b['combo']}) ≤ {est}크레딧"); continue
            r = path_finder.fetch(self.client, b["combo"], gl=self.gl,
                                  limit=DEPTH[self.a.depth]["path_limit"])
            self.ledger.add("path_finder", {"kw": b["combo"]}, r)
            self.save_raw(f"paths_{re.sub(r'[^0-9A-Za-z가-힣]+','_',b['combo'])}", r)
            out[b["combo"]] = r.get("data") or []
            self.log(f"S3 여정 {b['combo']} — {len(out[b['combo']])}경로")
        return out

    # ── S5 · 허브 조립 (패밀리 단위 · v0.1 규칙 기반) ──
    def s5_assemble(self, canvass, journeys) -> dict:
        rows = canvass["rows"]
        cat_re = re.compile(re.escape(self.category).replace(r"\ ", r"\s*"))
        bridges = []
        for combo, o in rows.items():
            v = o.get("v")
            fcls = self.facet_class(combo); facet = fcls is not None
            bridges.append({"combo": combo, "family": o["family"], "v": v,
                            "trend": o.get("trend"),
                            "lexeme": cat_re.sub("", combo).strip(),
                            "segment_facet": facet, "facet_class": fcls,
                            "qualified": bool(v and v >= BRIDGE_FLOOR and not facet)})
        hubs, sparse = [], []
        fams = sorted({b["family"] for b in bridges})
        for fam in fams:
            mem = [b for b in bridges if b["family"] == fam and b["qualified"]]
            allm = [b for b in bridges if b["family"] == fam]
            vol = sum(b["v"] for b in mem)
            if not mem or vol < HUB_FLOOR:
                sparse.append({"family": fam, "canvassed": len(allm),
                               "max_v": max((b["v"] or 0) for b in allm),
                               "verdict": "실측된 희박 — 캔버스 완주, 노드 미생성"})
                continue
            # co_path 보강 — 이 패밀리 렉심이 여정에 등장하는가
            co = 0
            lex = [b["lexeme"] for b in mem if b["lexeme"]]
            for paths in journeys.values():
                for p in paths:
                    j = " ".join(p)
                    if sum(1 for t in lex if t and t in j) >= 1:
                        co += 1
            hubs.append({"id": f"CEP-{self.category}-F{fams.index(fam)+1:02d}",
                         "family": fam, "hub_type": "situational", "status": "candidate",
                         "grade": "derived", "anchor": self.category, "gl": self.gl,
                         "volume_sum": vol, "bridges": mem, "co_path_paths": co,
                         "backing": "measured 결합쿼리 + " + ("co_path" if co else "여정 미실측")})
        # 시즌 허브 — 결합쿼리가 아니라 헤드텀 시즌 지수로 성립 (진폭 ≥2)
        season = canvass.get("season") or {}
        if season:
            vals = list(season.values())
            amp = max(vals) / max(min(vals), 0.01)
            if amp >= 2:
                hubs.append({"id": f"CEP-{self.category}-SEASON", "family": "season",
                             "hub_type": "situational", "status": "candidate",
                             "grade": "derived", "anchor": self.category, "gl": self.gl,
                             "volume_sum": None, "season_amplitude": round(amp, 2),
                             "season_index": season,
                             "backing": f"시즌 지수 진폭 {amp:.1f}배 (measured 시계열)"})
                sparse = [s for s in sparse if s["family"] != "season"]
        return {"bridges": bridges, "hubs": hubs, "sparse_families": sparse}

    # ── 게이트 ──
    def run_gates(self, families, canvass, result):
        rows = canvass["rows"]
        # G3 캔버싱 커버리지 — 패밀리별 전수 완주 (v2.3: 미완주면 "상황형 0" 산출 금지)
        planned = self.build_combos(families)
        missing = [k for k in planned if k not in rows] if rows else list(planned)
        if missing:
            self.gate("G3", "캔버싱 커버리지", "차단", f"미완주 {len(missing)}건 — 상황형 판정 불가")
        else:
            self.gate("G3", "캔버싱 커버리지", "통과",
                      f"패밀리 {len(families)}종 · 결합형 {len(planned)}건 전수 완주")
        n_hub = len(result["hubs"])
        self.gate("G3", "허브 성립 수 (특성값 — 게이트 아님)", "보고",
                  f"상황형 후보 {n_hub} · 희박 패밀리 {len(result['sparse_families'])}")
        no_backing = [h["id"] for h in result["hubs"]
                      if h.get("volume_sum") and not h.get("co_path_paths")]
        if no_backing:
            self.gate("G3", "허브당 보강 근거", "경고", f"여정 미실측 허브 {no_backing} — 회색 표기")
        ev = self.v05.get("evidence") or {}; lt = self.v05.get("longtail") or {}; hy = self.v05.get("hypotheses") or {}
        self.gate("G12", "SERP·AIO 증거 (S2)", "통과" if ev.get("measured") else "경고",
                  f"{ev['n_seeds']}시드 · AIO 노출 {ev['aio_exposure'][0]}/{ev['aio_exposure'][1]} · PAA {len(ev['paa'])} · extracted" if ev.get("measured") else ev.get("note", "미수집"))
        self.gate("G13", "롱테일 코퍼스 (S3)", "통과" if lt.get("measured") else "경고",
                  f"{lt['n']}쿼리 · 볼륨 {lt['with_volume']} · 언어층 {lt['language_only']} · 미측정 {lt['unmeasured']} · 노이즈 {lt['noise']['n']}({(lt['noise']['share_v'] or 0):.0%} 볼륨) · 공간 {lt['space_context_n']}" if lt.get("measured") else lt.get("note", "미수집"))
        if hy.get("status") == "confirmed":
            _pm = hy.get("permutation") or {}
            _g14_warn = (hy["rejection_rate"] == 0 or (_pm.get("perm_supported_rate") or 0) >= 0.5 or _pm.get("discriminating") is False)
            self.gate("G14", "가설 확증 (S5)", "경고" if _g14_warn else "통과",
                      f"{'블라인드 · ' if hy.get('blind') else '코퍼스 노출 · '}match={hy.get('match')} · {hy['n']}건 · supported {hy['supported']} · unsupported {hy['unsupported']} · 기각률 {hy['rejection_rate']:.0%}(예측만 {hy.get('rejection_rate_predicted_only') or 0:.0%} · post-hoc 태깅 {hy.get('post_hoc_n', 0)}건) · 후보 {len(hy['hypothesis_hubs'])}(승격률 {hy.get('selection_rate') or 0:.0%}) · 판정 {hy.get('verdict_counts')}" + (f" · 순열 기준선 자기 {_pm.get('own_mean')} vs 타가설 {_pm.get('perm_mean')} · 타가설 통과율 {(_pm.get('perm_supported_rate') or 0):.0%}" if _pm.get("perm_mean") is not None else "")
                      + (f" · 기준시드 기각률 {hy['rejection_rate_baseline']:.0%}" if hy.get("rejection_rate_baseline") is not None else "")
                      + (f" · 직접실측 {hy.get('direct_measured_n') or 0}" if hy.get("direct_measured_n") else "")
                      + (f" · 상황근거 얇은 후보 {hy.get('thin_situational_n')}" if hy.get("thin_situational_n") else "")
                      + (" — 기각률 0% 편향 신호" if hy["rejection_rate"] == 0 else "")
                      + (" — 순열 기준선 대비 판정이 가설을 구별하지 못함" if (_pm.get("perm_supported_rate") or 0) >= 0.5 or _pm.get("discriminating") is False else ""))
        elif hy.get("status") == "awaiting_llm":
            self.gate("G14", "가설 확증 (S5)", "대기", "core/hypothesis_tasks.json 발주 — 가설 작성 후 --hypotheses 재실행")
        if self.product and self.product_data:
            pd = self.product_data
            n = pd["probe"].get("n_related")
            self.gate("G5", "제품 시드 연관어 수 (특성값 — 적합률 게이트 면제, B3)", "보고",
                      f"{n if n is not None else '미측정'}건 — 표본 부족은 오염이 아니라 제품 쿼리 공간의 두께")
            tr = pd["transition"]
            self.gate("G6", "전이형 여정 수집 (B1)", "통과" if tr.get("measured") else "경고",
                      f"{tr.get('n', 0)}경로 · 상황 렉심 도달 {tr.get('situation_reach', '-')} · 경쟁 동반 {dict(tr.get('competitor_cooccurrence') or [])}" if tr.get("measured") else "미수집 — 제품 진입 구조 판정 불가")
            inh = pd["inherited_hubs"]
            self.gate("G7", "품목 허브 상속·연결 (B1)", "통과" if inh else "경고",
                      " · ".join(f"{h['id']} {h['verdict']}" for h in inh) if inh else "상속 원천 없음 — 품목 run 선행 필요")
            self.gate("G8", "브랜드 도달 지표 (B4)", "보고", "자사 앵커라 퇴화 — 경쟁 동반률·자사 라인 분기로 대체")
            sw = pd.get("switching") or {}
            self.gate("G9", "스위칭 방향성 (B7)", "보고" if sw.get("measured") else "경고",
                      f"자사→경쟁 {sw['counts'].get('own_to_comp', 0)} · 경쟁→자사 {sw['counts'].get('comp_to_own', 0)} · 왕복 {sw['counts'].get('round_trip', 0)} /{sw['n']} — 세션 인접 집계, 개인 이탈 아님" if sw.get("measured") else "여정 미수집")
            if self.feature:
                fa = pd.get("association") or {}
                self.gate("G11", "Feature Association (B8)", "통과" if fa.get("measured") else "경고",
                          (" → ".join(f"{L}({r:+.2f})" for L, r in fa.get("chain_order", [])) + f" · {fa['n']}경로") if fa.get("measured") else "기능 여정 미수집 — 사슬 판정 불가")
            cm = pd.get("context_matrix") or {}
            self.gate("G10", "Context×브랜드 매트릭스 (B9)", "통과" if cm.get("measured") else "경고",
                      f"{cm.get('n_measured', 0)}/{cm.get('n_cells', 0)}셀 측정 · {cm.get('denominator_basis', '')}" if cm.get("measured") else cm.get("note", "미측정"))

    # ── 산출 ──
    def emit(self, sense, families, canvass, journeys, result):
        core = self.out / "core"; outd = self.out / "out"
        hub_graph = {"run_id": self.run_id, "category": self.category, "gl": self.gl,
                     "anchor_level": self.a.anchor_level,
                     "hub_type_note": "전이형은 헤드텀 여정 미수집 시 '미측정'",
                     "hubs": result["hubs"], "bridges": result["bridges"],
                     "sparse_families": result["sparse_families"], "facets": result.get("facets") or {},
                     "season": canvass.get("season")}
        hub_graph.update({"evidence": {k: v for k, v in (self.v05.get("evidence") or {}).items() if k != "items"} | {"items_n": len((self.v05.get("evidence") or {}).get("items") or [])},
                          "evidence_items": (self.v05.get("evidence") or {}).get("items") or [],
                          "longtail": self.v05.get("longtail"), "hypotheses": self.v05.get("hypotheses"), "merge": self.v05.get("merge"),
                          "benefit": self.v05.get("benefit"), "feature_lexicon": sense.get("feature_lexicon"), "sense_check": self.v05.get("sense_check")})
        if self.product and self.product_data:
            hub_graph.update({"parent_category": sense.get("parent_category"), "own_brand": sense.get("own_brand"),
                              "own_lines": sense.get("own_lines"), "alias_groups": self.product_data["alias_groups"],
                              "probe": self.product_data["probe"], "inherited_hubs": self.product_data["inherited_hubs"],
                              "transition": self.product_data["transition"],
                              "switching": self.product_data.get("switching"), "context_matrix": self.product_data.get("context_matrix"),
                              "feature": self.product_data.get("feature"), "association": self.product_data.get("association")})
        (core / "hub_graph.json").write_text(json.dumps(hub_graph, ensure_ascii=False, indent=1), encoding="utf8")
        llm_tasks = [{"task": "hub_label", "hub": h["id"],
                      "instruction": "브리지 렉심·슬롯에서 서사 문장을 만들고 라벨로 압축(§4.4). 코퍼스 봉인 준수 — 근거는 bridges의 결합쿼리 문자열만.",
                      "bridges": [b["combo"] for b in h.get("bridges", [])]}
                     for h in result["hubs"]]
        if self.product:
            llm_tasks.append({"task": "product_labels", "instruction": "상속 허브별 제품 연결 판정(비연결/단서/가설)을 서사로 압축하고, 전이형 관문(선행 노드)과 이탈(후행 노드)을 Nano Intent로 서술. 라인·기능 별칭군은 합산하지 말 것(B2)."})
        llm_tasks.append({"task": "family_split",
                          "instruction": "패밀리 단위 허브를 구별성(자카드) 기준으로 세분 제안 — v0.1 엔진 한계. 예: state → 공간(원룸·오피스텔) vs 동거(아기방·신생아)"})
        (core / "llm_tasks.json").write_text(json.dumps(llm_tasks, ensure_ascii=False, indent=1), encoding="utf8")
        manifest = {"run_id": self.run_id, "engine": f"cep-finder v{ENGINE_VERSION}", "spec": "기술 정의서 v2.3",
                    # 재현 조건 — 같은 값을 다시 만들려면 엔진 버전·실행 인자·입력 원자료가 모두 있어야 한다
                    "invocation": {"argv": sys.argv[1:], "engine_file_sha256": _sha(Path(__file__)),
                                   "hypotheses_sha256": _sha(Path(self.a.hypotheses)) if getattr(self.a, "hypotheses", None) else None,
                                   "sense_sha256": _sha(Path(self.a.sense_file)) if getattr(self.a, "sense_file", None) else None},
                    "anchor_level": self.a.anchor_level, "inherit_from": self.a.inherit_from,
                    "adapter": {"vertical": self.a.vertical, "version": self.adapter.version,
                                "validation": self.adapter.report},
                    "depth": self.a.depth, "replay": str(self.replay) if self.replay else None,
                    "sense": sense.get("sense"), "families": {k: len(v) for k, v in families.items()},
                    "thresholds": {"bridge_floor": BRIDGE_FLOOR, "hub_floor": HUB_FLOOR,
                                   "season_amp": 2.0},
                    "credits": {"spent": self.ledger.spent, "budget": self.ledger.budget,
                                "calls": self.ledger.calls},
                    "gates": self.gates, "warnings": self.warnings,
                    "keyword_rematch": {"n": len(self.rematched), "pairs": self.rematched,
                                        "note": "API 띄어쓰기 정규화로 요청어≠응답어인 건 — 공백 제거·소문자 키로 되붙인 실측값"}}
        (outd / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf8")
        lines = [f"# CEP Finder run — {self.category} ({self.gl}) · {self.run_id}",
                 f"엔진 v0.6 · 정의서 v2.3 · 어댑터 {self.a.vertical} v{self.adapter.version} · 앵커 레벨 {self.a.anchor_level}",
                 f"크레딧 {self.ledger.spent}" + (" (replay — 신규 지출 0)" if self.replay else ""), "",
                 "## 허브 후보 (candidate — 사람 승인 대기)"]
        for h in result["hubs"]:
            vs = f"{h['volume_sum']:,}" if h.get("volume_sum") else f"시즌 진폭 {h.get('season_amplitude')}배"
            lines.append(f"- **{h['id']}** [{h.get('family') or h.get('source') or '-'}] {vs} — {h['backing']}")
            for b in h.get("bridges", []):
                v = b.get("v"); vt = f"{v:,}" if v else ("0(언어)" if b.get("language_only") else "[없음]")
                lines.append(f"    - {b['combo']} {vt} (추세 {b['trend']:+.2f})" if b.get('trend') is not None else f"    - {b['combo']} {vt}")
        facets = [b for b in result["bridges"] if b.get("segment_facet")]
        if facets:
            lines.append("\n## 세그먼트·패싯으로 분리 (허브 아님 — 온톨로지 C3 일치)")
            for b in facets:
                lines.append(f"- {b['combo']} {b['v']:,} → C3 세그먼트 분석 경로로 이관")
        lines.append("\n## 실측된 희박 패밀리 (캔버스 완주 — gap 아님)")
        for s in result["sparse_families"]:
            lines.append(f"- {s['family']}: 캔버스 {s['canvassed']}건 · 최대 {s['max_v']:,} → {s['verdict']}")
        if self.product and self.product_data:
            pd = self.product_data
            lines.append("\n## 제품 앵커 — 별칭군 (B2 · 동의어 중복 가능, 합계는 상한)")
            for g, o in pd["alias_groups"].items():
                lines.append(f"- **{g}** 합 {o['volume_sum']:,} — " + " · ".join(f"{r['alias']} {r['v'] or '[없음]'}" + (f"(YoY {r['yoy']:+.1%})" if r.get('yoy') is not None else "") for r in o["aliases"]))
                ev = {k: v for k, v in o["eval"].items()}
                lines.append("    - 평가형: " + " · ".join(f"{k.split(' ', 1)[1] if ' ' in k else k} {v or '[없음]'}" for k, v in ev.items()))
            lines.append(f"\n## 제품 시드 연관어 (B3 — 특성값): {pd['probe'].get('n_related', '미측정')}")
            tr = pd["transition"]
            lines.append("\n## 전이형 진입 (B1·B4)")
            if tr.get("measured"):
                lines.append(f"- 경로 {tr['n']} · 위치 {tr['position']} · 상황 렉심 도달 {tr['situation_reach']}")
                lines.append("- 선행: " + " · ".join(f"{k} {v}" for k, v in tr["prev"][:6]))
                lines.append("- 후행: " + " · ".join(f"{k} {v}" for k, v in tr["next"][:6]))
                lines.append("- 경쟁 동반: " + (" · ".join(f"{k} {v}" for k, v in tr["competitor_cooccurrence"]) or "없음") + " / 자사 라인 분기: " + (" · ".join(f"{k} {v}" for k, v in tr["own_line_branch"]) or "없음"))
            else:
                lines.append("- 미수집")
            sw = pd.get("switching") or {}
            if sw.get("measured"):
                lines.append("\n## 스위칭 방향성 (B7 · 세션 인접 집계 — 개인 이탈 아님)")
                lines.append(f"- {sw['counts']} · 자사→경쟁 {sw['switch_out_rate']:.0%} · 경쟁→자사 {sw['switch_in_rate']:.0%}")
                lines.append("- 이탈 트리거(경쟁 직전 노드): " + (" · ".join(f"{k} {v}" for k, v in sw["switch_out_triggers"][:6]) or "없음") + " → " + (" · ".join(f"{k} {v}" for k, v in sw["switch_out_to"]) or ""))
                lines.append("- 유입 트리거(자사 직전 노드): " + (" · ".join(f"{k} {v}" for k, v in sw["switch_in_triggers"][:6]) or "없음") + " ← " + (" · ".join(f"{k} {v}" for k, v in sw["switch_in_from"]) or ""))
            cm = pd.get("context_matrix") or {}
            if cm.get("measured"):
                lines.append(f"\n## Context×브랜드 매트릭스 (B9 · {cm['denominator_basis']})")
                lines.append("| 컨텍스트 | 무브랜드 | 자사측 | 경쟁측 | 겹침 | 무브랜드 여지 | 자사 비중 |"); lines.append("|---|---:|---:|---:|---:|---:|---:|")
                for r in cm["rows"]:
                    lines.append(f"| {r['context']} | {r['generic']:,} | {r['own']:,} | {r['comp']:,} | {r['overlap_index'] if r['overlap_index'] is not None else '-'} | {r['open_share'] if r['open_share'] is not None else '-'} | {r['own_share'] if r['own_share'] is not None else '-'} |")
            fe = pd.get("feature") or {}; fa = pd.get("association") or {}
            if fe:
                lines.append("\n## 기능 변형·이해형 캔버스 (B8)")
                for r in fe["variants"]:
                    lines.append(f"- **{r['term']}** {r['v'] or '[없음]'} — " + " · ".join(f"{t} {r['understanding'][t] or '[없음]'}" for t in fe["understanding_terms"]))
                lines.append("- 변형쌍: " + (" · ".join(f"{p['q']} {p['v']}" for p in fe["pairs"] if p["v"]) or "전량 [없음]"))
                lines.append("- 경쟁 기능(assumption): " + (" · ".join(f"{c['brand'] or ''} {c['feature']} {c['v'] or '[없음]'}" + (f"(응답어 '{c['measured_as']}')" if c.get("measured_as") else "") for c in fe["competing_features"]) or "미지정"))
                if fe.get("consumer_terms"):
                    gp = fe.get("generic_vs_proper") or {}
                    lines.append("- 소비자 일반어(B14): " + " · ".join(f"{r['term']} {r['v'] or '[없음]'}" + (f"[{r['sense']} 기능 {r['feature_share']:.0%} → {r['v_adjusted']:,}]" if r.get('feature_share') is not None else "") for r in fe["consumer_terms"]) + f" → 일반어 {gp.get('consumer_terms', 0):,}(환산 {gp.get('consumer_terms_adjusted', 0):,}) vs 고유명 {gp.get('proper_variants', 0):,}")
            sc = self.v05.get("sense_check") or {}
            if sc.get("measured"):
                lines.append("\n## S0b 일반어 동음이의 검증 (B14 · path_finder · derived)")
                for term, x in sc["terms"].items():
                    lines.append(f"- **{term}** {x.get('volume') or '[없음]'} → " + (f"{x['n_paths']}경로 · 기능 {x['feature_share']:.0%} {x['counts']} → **{x['verdict']}** (환산 {x['adjusted_volume']:,}) · 직전 {x['prev'][:3]} · 직후 {x['next'][:3]}" if x.get("n_paths") else x.get("note", "미측정")))
            be = self.v05.get("benefit") or {}
            if be.get("measured"):
                lines.append(f"\n## S3c 편익 7W 분해 (B13) — '{be['benefit']}' · 셀 {len(be['cells'])} · {be['verdict_counts']}")
                lines.append(f"정렬: {be.get('sort_rule')}")
                for c in be["cells"]:
                    lines.append(f"- {c.get('rank')}. [{c.get('tier')} {c.get('tier_label')}] [{c['dim']}/{c['w']}] **{c['label']}** ← 시드 {c.get('seeds_hit', 0)}/{len(c.get('seeds') or [])} 적중 {c.get('seeds')} · 수확 {c['harvested'] if c['harvested'] is not None else '미수집'} · 볼륨 {c['with_volume']}건 {c['volume_sum']:,} · 언어 {c['language_only']} · 기능 외 {c['off_feature_n']} → {c['role']}" + (" · " + " · ".join(f"{x['q']} {x['v']:,}" for x in c['top'][:3]) if c['top'] else ""))
            if fa.get("measured"):
                lines.append(f"\n## Feature Association (B8 · {fa['n']}경로 · 위치 {fa['position']})")
                lines.append("- 사슬 순서(앞→뒤): " + " → ".join(f"{L}({r:+.2f})" for L, r in fa["chain_order"]))
                for L, v in sorted(fa["layers"].items(), key=lambda x: -x[1]["paths"]):
                    lines.append(f"- {L}: {v['paths']}경로({v['share']:.0%}) · 앞 {v['before']}/뒤 {v['after']} · " + " · ".join(f"{n} {c}" for n, c in v["top_nodes"][:5]))
                lines.append("- 선행: " + " · ".join(f"{k} {v}" for k, v in fa["prev"][:6]) + " / 후행: " + " · ".join(f"{k} {v}" for k, v in fa["next"][:6]))
            lines.append("\n## 상속 허브 — 품목 run 연결 측정 (B1)")
            for h in pd["inherited_hubs"]:
                lines.append(f"- **{h['id']}** {h['label']} [{h['source']}] {h['volume_sum']:,} → 제품 여정 co_path {h['product_journey_co_path']}/{h['product_journey_n']} · 품목 여정 제품 별칭 도달 {h['parent_journey_product_reach'] if h.get('parent_journey_product_reach') is not None else '미측정'}/{h['parent_journey_n'] or '-'} (자사 타라인 {h['parent_journey_own_line_reach'] if h['parent_journey_own_line_reach'] is not None else '-'}) → **{h['verdict']}**")
        ev = self.v05.get("evidence") or {}; lt = self.v05.get("longtail") or {}; hy = self.v05.get("hypotheses") or {}
        if ev.get("measured"):
            lines.append(f"\n## S2 증거 (extracted) — serp {ev['n_seeds']}시드 · AIO 노출 {ev['aio_exposure'][0]}/{ev['aio_exposure'][1]} · PAA {len(ev['paa'])}")
            for q in ev["paa"][:10]: lines.append(f"- [{q['seed']}] {q['q']}")
        if lt.get("measured"):
            lines.append(f"\n## S3 롱테일 코퍼스 — {lt['n']}쿼리 (볼륨 {lt['with_volume']} · 언어층 {lt['language_only']} · 노이즈 {lt['noise']['n']}) · 시드 {lt['seeds']}")
            for r in lt["rows"][:15]: lines.append(f"- {r['q']} {r['v'] if r['v'] is not None else '미측정'}" + (" [noise]" if r["noise"] else "") + (" [space]" if r["space_context"] else ""))
        if hy.get("status") == "confirmed":
            lines.append(f"\n## S5 가설 확증 — {hy['n']}건 · supported {hy['supported']} · unsupported {hy['unsupported']} · 기각률 {hy['rejection_rate']:.0%}")
            for h in hy["hypotheses"]:
                lines.append(f"- **{h.get('id')}** [{h['status']}/{h['strength']} → {h['hub_verdict']}] {h.get('narrative', '')[:80]} — 매칭 {h['backing']['matched_n']}(언어 {h['backing']['language_only_n']}) · 볼륨합 {h['backing']['volume_sum']:,} · co_path {h['backing']['co_path']}")
        elif hy.get("status") == "awaiting_llm":
            lines.append("\n## S5 가설 — core/hypothesis_tasks.json 발주(작성 후 --hypotheses 재실행)")
        mg = self.v05.get("merge") or {}
        if mg.get("pairs"):
            lines.append(f"\n## S6 구별성·병합 (자카드 · 허브 {len(mg['units'])})")
            for p_ in mg["pairs"][:12]: lines.append(f"- {p_['a']} × {p_['b']} J={p_['jaccard']}(포함 {p_['containment']}) 공유 {p_['shared_tokens'][:5]} → {p_['verdict']}")
        lines.append("\n## 게이트")
        for g in self.gates:
            lines.append(f"- [{g['gate']} {g['verdict']}] {g['name']} — {g['detail']}")
        (outd / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf8")
        (self.out / "logs" / "run.log").write_text("\n".join(self.log_lines) + "\n", encoding="utf8")
        # 분석 건별 게이트 기록 (run-gates/v1 · lib/gates.py) — 자동 판정 가능한 것만 채운다(회귀 테스트는 run_gate.py check)
        try:
            from lib import gates as _gates
            _doc = _gates.init(self.out, self.a.vertical, self.category, self.gl)
            _gates.save(self.out, _doc)
            _doc = _gates.refresh(self.out, run_tests=False, canon=True)
            if getattr(self.a, "on_dictionary_gap", "ask") == "skip" and _gates.evaluate(_doc, "render")["ask"]:
                _doc = _gates.decide(self.out, "skip", "사용자 선택(--on-dictionary-gap skip)")
            _ev = _gates.evaluate(_doc, "render")
            self.log("게이트 기록 → gates.json · 렌더 전 " + ("완료" if _ev["complete"] else
                     "미완: " + ", ".join(f"{_gates.NAMES[g]}({r['status']})" for g, r in _ev["blocking"])))
            if not _ev["complete"]:
                self.log(f"  다음: python3 .claude/skills/lima-agents/scripts/run_gate.py status --run {self.out}")
        except Exception as e:                             # noqa: BLE001 — 기록 실패가 run을 무효로 만들지 않게
            self.log(f"  ⚠ 게이트 기록 실패: {e}")
            self.warnings.append(f"게이트 기록 실패: {e}")
        if self.warnings:                                  # 경고는 manifest에만 두면 안 읽힌다 — 로그 끝에 한 번 더 세운다
            self.log(f"경고 {len(self.warnings)}건 (run_manifest.json warnings)")
            for w in self.warnings:
                self.log(f"  ⚠ {w}")
        self.log(f"산출 완료 → {self.out}")

    def run(self):
        self.log(f"run {self.run_id} · depth={self.a.depth} · anchor={self.a.anchor_level} · " +
                 ("REPLAY" if self.replay else ("DRY-RUN" if self.a.dry_run else "LIVE")))
        sense = self.s0_candidates()
        self.v05 = {}
        self.v05["sense_check"] = self.s0b_sense_check(sense)                                   # v0.6 B14 — 일반어 동음이의 검증(S3·S3c·S1c에 선행)
        canvass = self.s1_canvass(sense["families"])
        bridges_sorted = sorted(
            [{"combo": k, "family": v["family"], "v": v.get("v") or 0}
             for k, v in canvass["rows"].items() if not self.is_segment_facet(k)],
            key=lambda x: -x["v"])
        facets = {k: self.facet_class(k) for k in canvass["rows"] if self.is_segment_facet(k)}
        if facets:
            self.log(f"  [facet] 온톨로지 패싯(C3·Line·SpecDimension·Technology)과 일치 — 허브·여정에서 제외: {facets}")
        self.v05["evidence"] = self.s2_evidence(sense, bridges_sorted)
        known = set(canvass["rows"]) | {a for al in (sense.get("alias_groups") or {}).values() for a in al}
        self.v05["longtail"] = self.s3_longtail(sense, known)
        self.v05["benefit"] = self.s3c_benefit_decompose(sense, self.v05["longtail"])            # v0.6 B13
        if self.product:
            self.product_data = {"alias_groups": self.s1b_alias_canvass(sense), "probe": self.s2b_probe()}
            ppaths = [] if self.a.discover_only else self.s3b_product_journey()
            self.product_data["inherited_hubs"] = self.s4b_inherit(sense, ppaths)
            self.product_data["transition"] = self.s5b_transition(sense, ppaths, sense["families"])
            self.product_data["switching"] = self.s5c_switching(sense, ppaths)                       # v0.3 B7
            run_cm = (not self.a.no_context_matrix) and (not self.feature or self.a.with_context_matrix)
            self.product_data["context_matrix"] = self.s6b_context_matrix(sense) if run_cm else {"measured": False, "note": "feature 모드 기본 생략(--with-context-matrix) — 같은 품목의 제품 run 매트릭스 재사용" if self.feature else "--no-context-matrix"}   # v0.3 B9
            if self.feature:                                                                         # v0.4 B8
                self.product_data["feature"] = self.s1c_feature_canvass(sense)
                self.product_data["association"] = self.s7_feature_association(sense, ppaths, sense["families"])
                if not self.a.dry_run:
                    self.emit_ontology_delta(sense, self.product_data["feature"], self.product_data["association"])
            journeys = {self.category: ppaths} if ppaths else {}
        else:
            self.product_data = None
            journeys = {} if self.a.discover_only else self.s3_journeys(bridges_sorted)
        result = self.s5_assemble(canvass, journeys)
        result["facets"] = facets
        self.v05["hypotheses"] = self.s5_hypotheses(sense, self.v05["evidence"], self.v05["longtail"], canvass, journeys)
        for h in self.v05["hypotheses"].get("hypothesis_hubs") or []:
            result["hubs"].append(h)
        splits = None
        if self.a.hub_splits:
            try: splits = (json.loads(Path(self.a.hub_splits).read_text(encoding="utf8")).get("hubs") or None)
            except (OSError, json.JSONDecodeError): splits = None
        self.v05["merge"] = self.s6_merge(result["hubs"], self.v05["hypotheses"].get("hypotheses") or [], splits)
        self.run_gates(sense["families"], canvass, result)
        self.emit(sense, sense["families"], canvass, journeys, result)
        return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("category"); ap.add_argument("gl", choices=["kr", "jp", "us"])
    ap.add_argument("--vertical", required=True)
    ap.add_argument("--depth", default="standard", choices=list(DEPTH))
    ap.add_argument("--budget", type=int)
    ap.add_argument("--sense-file", help="S0 세계지식 후보 JSON {families:{fam:[terms]}, excludes, sense}")
    ap.add_argument("--replay", help="저장된 원본 디렉터리에서 0크레딧 재실행")
    ap.add_argument("--replay-topup", action="store_true", help="replay 부족분만 라이브 보충(저비용)")
    ap.add_argument("--replay-live-measure", action="store_true",
                    help="replay 중 S5 미매칭 예측어 직접 실측(--measure-unmatched)만 라이브 — serp·롱테일·여정은 저장본만 쓴다. "
                         "--replay-topup은 전 단계를 보충해 비용이 통제되지 않는다(정본 재수집 명령서용)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--on-dictionary-gap", choices=("ask", "skip"), default="ask",
                    help="어댑터 사전이 품목을 덮지 않을 때 — ask: 크레딧 쓰기 전에 멈추고 사용자 결정을 받는다(기본 · 종료 코드 10) · "
                         "skip: 사용자가 건너뛰기로 한 경우 진행하고 게이트에 '사전 생략'으로 기록")
    ap.add_argument("--canon-preflight", choices=("on", "off"), default="on",
                    help="수집 전 정본 해석 — on(기본): COVERED가 아니면 명령서를 쓰고 멈춘다(외부 열거가 없으면 serp 2쿼리 60크레딧 먼저) · "
                         "off: 사용자가 이미 정본 해석을 끝낸 경우만")
    ap.add_argument("--discover-only", action="store_true")
    ap.add_argument("--out", default=str(WORKSPACE / "90_Output"))
    ap.add_argument("--anchor-level", default="category", choices=["category", "product", "feature"],
                    help="product: 품목 run 허브 상속 + 제품 앵커 전이형 여정 (B1) / feature: + 변형·이해형 캔버스·Feature Association (B8)")
    ap.add_argument("--with-context-matrix", action="store_true", help="feature 모드에서도 Context×브랜드 매트릭스 실행(기본 생략)")
    ap.add_argument("--no-evidence", action="store_true", help="S2 serp 증거 수집 생략")
    ap.add_argument("--serp-max", type=int, default=12, help="S2 serp 시드 상한 (30크레딧/시드 · SERP_COST)")
    ap.add_argument("--no-longtail", action="store_true", help="S3 롱테일 수확 생략")
    ap.add_argument("--longtail-limit", type=int, default=100, help="S3 intent_finder limit (시드당 30+2N)")
    ap.add_argument("--longtail-seeds", default="", help="S3 추가 시드(쉼표) — sense.longtail_seeds 와 합집합")
    ap.add_argument("--hypotheses", help="S5 가설 파일(core/hypotheses.json) — 있으면 확증 패스 실행")
    ap.add_argument("--blind", action="store_true", help="S5 발주 파일에서 코퍼스·여정 노드를 제외(증거만) — 편향 통제")
    ap.add_argument("--hub-splits", help="S6 구별성 — labels.json의 세분 허브(hubs)를 패밀리 허브 대신 비교 단위로 사용")
    ap.add_argument("--match", default="loose", choices=["loose", "strict", "exact"], help="S5 키워드 매칭: loose=부분 문자열(≤3건) · strict=완전/접두·접미(≤2건) · exact=완전 일치만(--measure-unmatched와 함께 쓸 것)")
    ap.add_argument("--floor-basis", default="situational", choices=["situational", "total"], help="HUB_FLOOR 판정 기준: situational=상황 볼륨만(기본) · total=총 볼륨(v0.6.2 이전 동작)")
    ap.add_argument("--baseline-seeds", help="S5 판정 기준 시드(쉼표 또는 JSON 파일 · 이전 run의 core/s5_seeds.json) — 이후 추가된 시드에서 온 매칭은 corpus_extended로 분리하고 기준시드 기각률을 따로 낸다")
    ap.add_argument("--measure-unmatched", action="store_true", help="S5 미매칭 예측어를 keyword_info ads_metrics로 직접 실측(1크레딧/kw) — 코퍼스 수확 커버리지 교란 제거")
    ap.add_argument("--measure-unmatched-max", type=int, default=40, help="--measure-unmatched 실측 상한(기본 40) — 초과분은 미측정으로 남기고 로그에 남긴다")
    ap.add_argument("--inherit-from", help="product 모드 — 상속할 품목 run 폴더 (core/hub_graph.json · labels.json · raw/paths_*)")
    ap.add_argument("--no-probe", action="store_true", help="product 모드 — intent_finder 연관어 프로브 생략 (B3)")
    ap.add_argument("--no-alias-all", action="store_true", help="product 모드 — 별칭 keyword_info all(10/kw) 생략")
    ap.add_argument("--no-context-matrix", action="store_true", help="product 모드 — Context×브랜드 매트릭스(B9, ≈50크레딧) 생략")
    ap.add_argument("--no-sense-check", action="store_true", help="feature 모드 — S0b 소비자 일반어 동음이의 검증(path_finder) 생략")
    ap.add_argument("--sense-paths", type=int, default=100, help="S0b path_finder limit (어휘당 50+40×고유 키워드)")
    ap.add_argument("--no-benefit", action="store_true", help="feature 모드 — S3c 편익 7W 분해(B13) 생략")
    ap.add_argument("--benefit-seeds-max", type=int, default=64, help="S3c 시드 총수 상한(셀당 seeds[] 2~3개 필수) — 시드당 intent_finder 30+2×limit · 초과 시 셀당 뒤 시드부터 제외")
    Engine(ap.parse_args()).run()


if __name__ == "__main__":
    main()
