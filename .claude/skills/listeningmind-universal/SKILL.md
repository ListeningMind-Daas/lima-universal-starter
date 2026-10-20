---
name: listeningmind-universal
description: Industry-agnostic ListeningMind (리스닝마인드) search-behavior analysis skill — the standard base that industry or customer-specific overlays sit on. Use it whenever a user asks a market, category, brand, product-planning, audience, content, search-journey, or go-to-market question in any industry — e.g. laptops/IT devices, fashion, travel, education, SaaS, pet, furniture, automotive, HR/recruiting, B2B, services — or when the industry is unspecified ("○○ 시장 분석해줘", "○○ 수요 추이", "○○ 브랜드 검색 점유", "○○ 검색 여정", "○○ CEP 찾아줘", "○○ 콘텐츠 기회", "지금 진입해도 되나"). Routes every request into the standard 7 jobs (수요·트렌드 / 니즈·구매요인 CEP·KBF / 검색여정 CDJ / 경쟁·브랜드 SoV / 콘텐츠·기회 / 세분화·타겟팅 / 종합·진입) and runs the 4-layer package — ① question frames ② interpretation dictionary (seed verification, entity/noise dictionary) ③ expression discipline (measured/derived/assumption/missing labels, credit ledger, monthly-grain caveats) ④ execution pipeline (keyword_info · intent_finder · cluster_finder · path_finder · serp, readiness gate, script-rendered HTML report, monthly monitoring). Also the starting point for building an industry or customer-specific overlay (read references/vertical-overlay-guide.md).
metadata:
  build: v1.4.0
---

# ListeningMind Universal — 범용 검색 행동 분석 스킬 (표준 베이스)

리스닝마인드 DaaS 커넥터(핵심 4 + 보조 2 — serp·trend_finder)의 검색 행동 데이터로 마케팅·브랜드·상품기획·이커머스·경영진의
시장 질문에 답하는 **산업 무관 표준 스킬**이다. 산업·고객사 오버레이를 만들 때는 이 스킬의
공통 코어·7잡·정직성/렌더 규율을 재사용한다(§9). 응답은 항상 한국어.

**설계 근거** — 복수 산업·카테고리 실측(2026-07~08)에서 검증된 규율을 내장했다:
시드 검증(크레딧 쓰기 전), 준비도 배너(프롬프트로 못 막는 데이터 제약), 카테고리/세그먼트 분석 단위,
스크립트 렌더 HTML 리포트, 크레딧 원장·실측 단가, 월 그레인 운영 모드, CEP Finder 어댑터 계약.

## 0. 패키지 지도 — 4계층

| 층 | 하는 일 | 파일 |
|---|---|---|
| ① 질문 프레임 | 어떤 질문을 받고 어느 틀로 답할지 | `references/question-frames.md` · `references/jobs.md` |
| ② 해석 사전 | 시드·엔티티·노이즈를 어떻게 세나 | `references/seed-verification.md` · `references/entity-dictionary.md` · `dictionary/` · `scripts/seed_check.py` |
| ③ 표현 규율 | 어떻게 말하나 (라벨·크레딧·한계 고지) | `references/_shared-core.md` · `references/guardrails.md` · `references/readiness-gate.md` |
| ④ 실행 파이프라인 | 어떻게 돌리나 (수집·게이트·렌더·운영) | `references/workflow.md` · `references/tool-routing.md` · `references/demand-pipeline.md` · `scripts/collect_demand.py` · `references/report-template.html` · `scripts/render_report.py` · `scripts/credit_estimate.py` · `references/ops-monitoring.md` |

`adapter.yaml`은 CEP Finder 엔진(`lima-agents/scripts/run_cep_finder.py`)과의 계약(`cep-finder-adapter/v1`)이다 —
범용 스킬은 온톨로지·함의 사전이 없으므로 A4·A7은 `absent`로 선언하고, 엔진은 이를 준비도 배너에 기록한다.

## 1. 실행 순서 (11단계)

1. **라우팅 확인.** 별도 설치된 산업·고객사 오버레이 스킬의 범위에 드는 발화면 그 스킬로 보낸다.
   규제 도메인(의료·금융·식품 효능 등)을 건드리면 `references/guardrails.md` §3의 도메인별 추가 규칙을
   적용한다. 그 외에는 여기서 진행한다.
2. **컨텍스트 로드.** `references/_shared-core.md`(표현 규율 정본)를 먼저 읽는다. 리포트 요청이면
   `references/question-frames.md` §2 발화 템플릿으로 빠진 분기(실행 주체·gl·분석 단위·크레딧 상한)를 확인한다.
3. **인테이크.** 대상·시드·gl(kr/us/jp)·기간·실행 주체(브랜드 관점/중립/경쟁사 관점)·결정 소유자·산출 형식을
   뽑는다. 시드에서 "시장/분석/트렌드/조사" 같은 메타 단어를 제거한다. **실행 주체가 없으면** 리포트는
   미완성이므로 AskUserQuestion으로 확인한다(즉답형 텍스트 답변은 중립 기본값으로 진행).
4. **분석 단위 판정 — 카테고리 vs 세그먼트.** 프리픽스(`카테고리·`/`세그먼트·`)가 최우선. 없으면 어휘로
   판정한다: 대상 아래 의미 있는 하위 세그먼트가 나뉘면 카테고리(TAM·세그먼트 구성 스파인), 모델·브랜드
   레벨만 남으면 세그먼트(SoV·결정구조·여정 스파인). 양쪽 다 성립하면 AskUserQuestion — 즉시 실행 금지.
5. **잡 라우팅.** `references/jobs.md`의 7잡 중 주축 1개 + 보조 잡을 정한다. 넓은 요청이라도 결정에 필요한
   잡만 돌린다 — 기본값으로 옴니버스 리포트를 만들지 않는다.
6. **데이터 플랜·예산.** `references/tool-routing.md`로 최소 커넥터 조합과 호출 순서를 정하고
   `scripts/credit_estimate.py`로 예상 크레딧을 낸다. 동일 (gl, 카테고리, 기간)의 저장 스냅샷
   (`99_Scratch/<분석>/api/`)이 있으면 **크레딧을 쓰기 전에** 리플레이(0크레딧) 사용 여부를 확인한다.
7. **시드 검증 — 크레딧을 쓰기 전에.** `references/seed-verification.md`를 읽고
   `scripts/seed_check.py --gl <gl> --anchor "<앵커 어휘>" "<시드>" ...`를 실행한다(시드당 약 100~230크레딧 — 반환 수 비례).
   사전 `Noise` 등재 시드는 0크레딧에서 차단된다. 새 카테고리는 브랜드 사전이 비어 히트 0이 나오므로 `--dump`로
   코퍼스를 저장해 브랜드를 수확하고 `E0_<카테고리>.csv`를 만든 뒤 `--replay --dict`로 0크레딧 재채점한다.
   검증되지 않은 시드로 `path_finder`·`cluster_finder`를 실행하지 않는다 — 오염된 시드 하나가 하류 실측 전체를 무효로 만든다(실측: 20,500크레딧 손실 사례).
8. **직렬 수집.** 순서는 하나다 — **검증·확장(intent 프로브) → 규모(keyword_info ads 계열) → 구조(cluster_finder hop 1)
   → 확장어 규모(keyword_info) → 여정(path_finder, 필요할 때만)**. 확장한 키워드는 반드시 그 뒤에 볼륨을 잰다.
   수요·트렌드 잡은 `references/demand-pipeline.md`(D1~D8 · `scripts/collect_demand.py`)로 돌린다 — 시드 레이어 설계
   (문제·시장·브랜드·대체재) → 프로브 재사용 확장 → 구조 탐색 → 유니크 정리 → `ads_info` 월별 수집 → 중복 제거 → 지표.
   커넥터 동시 요청은 1(429 방지). 응답 원본은 분석 폴더에 보관하고 호출마다 `cost_detail.total_cost`를 원장에 합산한다.
9. **준비도 게이트 → 분석.** `references/readiness-gate.md`로 READY / READY WITH LIMITS / EXPAND / NARROW /
   NOT READY를 판정하고 배너 문구를 만든다. EXPAND면 증거 패밀리를 하나씩 추가하고, NOT READY면 결론 대신
   방법·데이터 요청을 낸다. 그다음 `references/decision-structure.md`의 6층(CEP·Nano Intent·KBF·Constraint·
   Avoidance·RTB)을 근거 쿼리와 함께 채운다 — 신호 없는 층은 비워 둔다.
10. **산출.** 좁은 질문은 텍스트, 다면적이면 HTML 리포트(`references/output-patterns.md`). HTML은 반드시
    `scripts/render_report.py <data.json> --run <분석 폴더>`로 렌더한다
    `--run`을 주면 data.json 문구의 숫자를 그 분석 폴더 원자료·core 계산값과 대조한다 — 게이트 기록이 있는 run은 미통과 시 중단, 초안은 `--allow-unverified-numbers`(배너).
    렌더 직전에 분석 작업 용어(질의·관계망·허브 등)를 업무 용어로 바꾸고, 다시 써야 하는 용어가 남으면 멈춘다(`lima-agents/references/lexicon-gate.md` §6 · 초안 `--allow-jargon`).(셸/sed/f-string 직접 주입 금지 — 개행이 `\n` 리터럴로
    깨진다). 크레딧 실측(이번 분석 소진 + 월간 누적)을 응답에 포함하고, 결과물은 `90_Output/`에 저장한다.
    **게이트 기록** — 분석 폴더에 `lima-agents/scripts/run_gate.py init·check`로 게이트를 남긴다. 렌더 전 게이트
    (예산·정본·수집·준비도·테스트)가 미통과면 렌더러가 멈춘다(`lima-agents/references/run-gates.md`).
    이 스킬의 사전은 분석마다 채우는 틀이라 품목이 비어 있으면 **'결정 필요'**가 나온다 — 실패가 아니다.
    AskUserQuestion으로 "이 품목의 사전을 채울까요, 건너뛰고 진행할까요?"를 묻고 `run_gate.py decide --choice fill|skip`으로 남긴다.
11. **발행 전 확인 · 규칙 회수.** 산출물을 보고 출처 라벨을 확인해 `run_gate.py attest --gate labels`로 남긴다.
    이번 분석에서 새로 알게 된 판정(매칭·오탐·판정 절차)이 있으면 사내 규칙 문서에 올리고 `run_gate.py rules`로 남긴다 —
    없으면 `--none "<사유>"`. `run_gate.py status --stage publish`가 0이어야 외부로 전달한다.

## 2. 기본 페르소나 (발화에서 추론 · 실행 주체 기본값)

| 페르소나 | 관심 | 기본 잡 |
|---|---|---|
| 브랜드매니저 | 포지셔닝·경쟁·메시지·런칭 | 경쟁·브랜드 + 니즈·구매요인 |
| 상품기획자 | 컨셉·KBF·제약·가격대·RTB | 니즈·구매요인 + 세분화 |
| 퍼포먼스·콘텐츠 마케터 | 쿼리 기회·비교 콘텐츠·랜딩·전환 | 콘텐츠·기회 + 검색여정 |
| 이커머스·리테일 | 구색·탐색·상세페이지·채널 | 검색여정 + 경쟁(채널 SoV) |
| 소비자 인사이트 | 상황·언어·세그먼트·미충족 니즈 | 세분화 + 니즈·구매요인 |
| 경영진·카테고리 리드 | 시장 방향·성장 공간·진입 타이밍 | 수요·트렌드 + 종합·진입 |

`00_Context/about-me.md`의 역할(Q2)이 있으면 그것이 실행 주체 기본값이다.

## 3. 표준 7잡 (요약 — 상세 `references/jobs.md`)

| 알고 싶은 것 | 잡 | 주 커넥터 |
|---|---|---|
| 얼마나 커/뜨나 · 전년 대비 · 시즌성 · 급등 원인 | **수요·트렌드** | intent 확장 → keyword_info(ads_info) · `demand-pipeline.md` (+trend_finder) |
| 왜 찾나 · 무엇을 따지나 (CEP·KBF) | **니즈·구매요인** | cluster_finder (+intent_finder) |
| 인지→검토→행동 경로 · 이탈 | **검색여정(CDJ)** | path_finder |
| 누가 존재감이 큰가 (SoV·SoJ) | **경쟁·브랜드** | cluster_finder + keyword_info |
| 어떤 질문·쿼리를 콘텐츠로 | **콘텐츠·기회** | intent_finder (+serp) |
| 누가 검색하나 (성·연령 — gl=kr만) | **세분화·타겟팅** | keyword_info.demography |
| 지금 진입/확장해도 되나 | **종합·진입** | 위 조합 |

## 4. 의사결정 구조 6층 + CEP 유형 (요약 — 상세 `references/decision-structure.md`)

- **CEP** 카테고리 진입 상황 — *상황·트리거·문제·기회*만. 제품 속성은 CEP가 아니다.
  CEP는 두 유형으로 갈린다: **상황형**(이사·입주·출산·시즌 같은 생활 맥락에서 진입)과 **전이형**(상위
  카테고리·관문 쿼리 "○○ 추천"에서 진입). 상황은 품목·제품 레벨 쿼리에 거의 나타나지 않으므로
  ("신혼 로봇청소기" 4/월 vs "신혼 가전 리스트" 3,046/월) 상황형은 **상위 앵커·여정(co_path)**에서 찾는다.
- **Nano Intent** 원하는 결과+방식 — **KBF** 비교 기준 — **Constraint** 선행 필터(예산·자격·공간·규제) —
  **Avoidance** 회피·우려(소비자 신호이지 제품 성능 진술이 아님) — **RTB** 믿게 하는 근거 체인(주장·증거·출처·확신).

## 5. 준비도 게이트·배너 (요약 — 상세 `references/readiness-gate.md`)

수량·커버리지·목적 적합·안정성·품질·다양성 6차원을 판정하고, 리포트 배너에 **프롬프트로 못 막는 제약**을
명시한다: 인구통계는 gl=kr 전용(us/jp는 "데이터 사양"), 롱테일 볼륨 커버리지(임계 미만은 언어 근거로만),
동의어군 볼륨 중복(합산 전 dedup), 범용 허브 노이즈(총량 제외), **월 그레인·3~7주 지연**(주간 경보 불가).

## 6. 필수 가드레일 (요약 — 상세 `references/guardrails.md`)

- 검색은 관심 신호다 — 판매·점유율·계약·방문이 아니다. SoV는 "검색량 기준 근사".
- `null`은 결측이지 0이 아니다. 알고리즘이 주지 않은 등급(HOT·급상승)을 만들지 않는다.
- 모든 수치에 `[실측]`/`[파생]`/`[가정]`/`[없음]`(+공표값 `[fact]`) 라벨. 인과는 단정하지 않고 상관·동향으로.
- 검색 행동에서 민감 개인 속성을 추정하지 않는다. 집계 데이터만 다룬다.
- 규제 도메인(의료·금융·식품 효능·화장품 효능)의 수치·주장은 공시·공식 출처만 인용하고, 카피는
  "심의·준법검토 전 초안"으로 표기한다. 해당 버티컬 스킬이 있으면 그쪽으로 보낸다.

## 7. 산출물 (요약 — 상세 `references/output-patterns.md`)

- **텍스트(기본)**: 범위·준비도·핵심 발견 3~5·결정구조·시사점·액션·한계/다음 데이터. 조사원 인사이트
  5분류(세그먼트 격차·리스크 신호·라이징·기회 공백·진입점 지배)를 먼저 제시한다.
- **HTML 리포트**: 마스트헤드(실행 주체 필수) → 준비도 배너 → KPI 4장 → 수행한 잡의 섹션만 → 기회 백로그
  (지금 대응/지켜볼/위험 3분류 + L/M/S 임팩트 배지) → 부록(호출 순서·호출 로그·비용 보고서) → 푸터(방법·크레딧·가드레일). 차트는 inline SVG,
  외부 CDN 금지(자동 검사·축 규칙·재현성 — `_shared-core.md` §7). 세그먼트 스파인이 기본형, 카테고리 스파인은 TAM·Intent Mix 섹션으로 변형.
- **인터랙티브 탐색**은 `lima-agents` Explorer로 안내한다.

## 8. 운영 모드 (요약 — 상세 `references/ops-monitoring.md`)

"모니터링·감시·알림" 발화는 리포트 스파인 대신 운영 스택을 탄다. LM 시계열은 **월 그레인 48개월·3~7주
지연**뿐이므로 주간 실시간 경보는 만들 수 없다 — 주간 트리거는 내부 데이터, LM은 월간 구조·이유 층.

## 9. 버티컬·고객사 오버레이 만들기

이 스킬 위에 산업·고객사 층을 얹을 때는 `references/vertical-overlay-guide.md`의 4계층 체크리스트를 따른다
— 페르소나·질문 프레임·엔티티/노이즈 사전·가드레일·adapter.yaml만 추가하고 코어 규율은 재작성하지 않는다.

## 10. 완료 체크리스트

- [ ] 버티컬 라우팅 확인 · 실행 주체 확정 · 분석 단위(카테고리/세그먼트) 판정
- [ ] 시드 검증 통과(`seed_check.py`) 후에만 cluster/path 호출 · 판정을 `dictionary/seed_registry.csv`에 기록
- [ ] 예상 크레딧 고지 → 호출 → 원장 합산(`total_cost`) · 월간 누적(`used_credits`)은 잔여가 아님
- [ ] 준비도 배너에 데이터 사양·제약 명시 · 수치마다 라벨
- [ ] HTML은 `render_report.py`로만 · `grep -c '\\n'`이 0에 가까운지 확인 · `90_Output/` 저장 후 Artifact
- [ ] 다음 조사 추천(강한 추천 1 + 대안) · 추가 호출 없이 답할 수 있는 범위 고지
- [ ] 게이트 기록(`run_gate.py`) — 렌더 전 게이트 통과 후 렌더 · 출처 라벨 확인·규칙 회수 기록 후 `status --stage publish` 0
