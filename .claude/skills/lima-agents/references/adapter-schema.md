# adapter.yaml 스키마 v1.0 — 엔진 × 버티컬 계약 정본

> 2026-08-21 확정 · 근거: CEP Finder 기술 정의서 v2.2 §6.2 (어댑터 7슬롯)
> 이 문서가 스키마의 정본이다. 검증은 `lib/vertical.py`의 경량 함수로 구현한다(jsonschema 미도입 — §16 원칙).
> §15 미결정 "어댑터 형식" 해소: **선언(YAML) 기본 + A1만 실행 훅 허용**하는 하이브리드로 확정한다.

## 0. 설계 결정

1. **선언 우선.** 산업 지식은 데이터(경로·목록·임계·문구)로 넘긴다. 판정 로직이 필요한 슬롯은
   A1(시드 검증) 하나뿐이며, 여기만 실행 훅을 허용한다. A7(함의)은 선언 + 사람 승인 흐름으로
   충분하므로 훅을 두지 않는다.
2. **경로는 어댑터 파일 기준 상대 경로.** 어댑터가 버티컬 스킬 루트에 있으므로 스킬 내부 자산을
   짧게 가리킨다. 절대 경로 금지.
3. **모든 슬롯에 `status`.** `ready | partial | absent`. 엔진은 absent/partial 슬롯을 범용
   기본값으로 낮춰 실행하되, 어느 슬롯이 낮춰졌는지를 **준비도 배너와 run_manifest에 기록**한다.
   조용한 대체 금지(정의서 §6.2). 어떤 슬롯도 실행을 차단하지 않는다 — 차단은 게이트(G0~G4)의 몫.
4. **버전.** `adapter_version`은 semver. 내용 변경 시 patch↑, 슬롯 구조 변경 시 minor↑,
   본 스키마 비호환 변경 시 major↑. run_manifest에 `adapter_version`이 기록된다(재현 요소).

## 1. 최상위 필드

```yaml
schema: cep-finder-adapter/v1        # 필수 · 본 스키마 식별자 (고정 문자열)
adapter_version: "0.1.0"             # 필수 · semver
vertical: appliance                  # 필수 · 버티컬 식별자 (kebab-case)
spec_ref: "기술 정의서 v2.2"          # 필수 · 준거 정의서 버전
updated: "2026-08-21"                # 필수 · YYYY-MM-DD
owner: "..."                         # 선택 · 관리 주체
markets: [kr, us]                    # 필수 · 이 어댑터가 검증된 gl 목록
slots:                               # 필수 · A1~A7 (아래 §2)
  A1_seed_policy: {...}
  ...
```

## 2. 슬롯별 스키마

각 슬롯 공통: `status`(필수) · `authority`(사람용 정본 문서 경로 — status가 ready·partial이면 필수) ·
`note`(선택). 이하 슬롯별 추가 필드.

### A1_seed_policy — 시드 검증 (실행 훅 허용 슬롯)

```yaml
status: ready
authority: references/seed-verification.md
hook:                                # 선택 · 있으면 엔진이 내장 프로브 대신 호출
  cmd: scripts/seed_check.py         # 실행 파일 (어댑터 기준 상대 경로)
  contract: seed-check/v1            # 훅 계약 식별자 (아래 §3)
thresholds:                          # 필수 · 내장 프로브의 폴백 값이기도 함
  noise_rate_max: 0.20               # 초과 시 시드 교체 (개수·볼륨 양측 산출)
  fit_rate_min: 0.60                 # 미만 시 시드 교체
  brand_hits_min: 10                 # 미만 시 시드 풀링
banned_seeds:                        # 필수 · gl별 금지 시드 (bare 형태)
  common: [...]
  kr: [...]
  us: [...]
replacements:                        # 선택 · 금지 시드 → 대체 시드 매핑
  "tv": ["tv 추천", "스마트tv", "4k tv"]
notation_pairs_required: true        # 필수 · 영/한 표기쌍 개별 검증 여부
seed_roles:                          # v2.3 · 시드 역할 구분 — 상황 앵커는 적합률 게이트 면제
  category_seed: "..."               #   코퍼스 편입 · 적합률 = 통과 게이트
  situation_anchor: "..."            #   여정 전용 · 도달률 = 측정 결과값 (게이트 아님)
```

### A2_noise_lexicon — 노이즈 판별 어휘

```yaml
status: ready
authority: references/seed-verification.md   # §3 노이즈 판별 어휘
dictionary:                          # 선택 · 구조화 사전 (권장)
  file: ontology/E0_후보사전_v0.1.csv
  format: e0-csv/v1                  # class=Noise 행 · aliases는 '|' 구분 · note에 사유
patterns:                            # 필수 · gl별 정규식 조각 (엔진이 OR 결합)
  common: [...]
  kr: [...]
  us: [...]
volume_check_required: true          # 필수 · 노이즈율은 개수+볼륨 양측 산출 (TV 25%/93% 교훈)
```

### A3_entity_authority — 브랜드 별칭 정본

```yaml
status: ready
authority: references/brand-map.md
format: brand-map-md/v1              # 파싱 계약: "**대표명 (…)** — ×: 사명별칭 / ○: 서브브랜드별칭"
rules:
  corporate_standalone_exclude: true # × 별칭 단독 쿼리는 SoV 분모·분자 제외 + [가정] 명시
  subbrand_standalone_keep: true     # ○ 별칭 단독 쿼리는 유지
  matched_aliases_disclosure: true   # 리포트에 실제 매칭 별칭 목록 표기 (폭 대등성 검증)
homonyms:                            # 필수 · 동음이의어 — 결합형만 집계
  - {term: "미니", collision: "크기 형용사", keep_only: ["미니 쿠퍼"]}
generic_rule: alias-nonmatch         # 필수 · 논브랜드 판별 = 브랜드 별칭 미매칭 쿼리 (계산 규칙 · 어휘 목록 아님)
```

### A4_ontology_binding — 온톨로지 연결

```yaml
status: ready
authority: ontology/README.md
files:
  nodes: ontology/nodes.jsonl
  edges: ontology/edges.jsonl
  bridge_nodes: ontology/bridge_nodes.jsonl    # 결합 쿼리 (N3)
  bridge_edges: ontology/bridge_edges.jsonl
id_prefixes: [C1, C2, C3, BR, ..., HYP, SEV, MI, AQ]   # 이 버티컬에서 실제로 쓰는 접두사 전수
# 접두사 충돌 규칙 — A4가 접두사의 정본이다. 정의서 §8의 id 형식은 기본값이며,
# 버티컬에 선점 클래스가 있으면 A4에서 오버라이드한다.
#   예) ContextHypothesis 기본 CH- 는 appliance의 Channel(CH-)과 충돌 → HYP- 사용
cep_id_format: "CEP-{anchor}-{nn}"
status_values: [candidate, confirmed, deferred, rejected]
append_only: true                    # 필수 · delta는 append만 · 사람 승인 후 confirmed
context_lexicon:                     # 필수(v2.3↑) · 상황 패밀리별 이벤트 사전 — 캔버싱의 커버리지 기준
  self_purchase: [...]               # 자기구매(장만) 이벤트
  gift: [...]                        # 선물 상황시장어 — 부재 시 패밀리 통째 미탐 위험 (파일럿 실증)
  season: [...]                      # 시즌 어휘
  spaces: [...]                      # Space 어휘 (별도 세션 조회 대상)
```

### A5_guardrails — 산출물 강제 문구

```yaml
status: ready
authority: references/appliance-guardrails.md
mandatory:                           # 필수 · 산출물 삽입 확인 대상 (G4 차단 항목)
  - id: sov-approx
    text: "브랜드 점유는 검색량 기준 근사"
  - id: search-not-purchase
    text: "검색은 관심 신호이며 실제 구매가 아님"
  # ... 버티컬 고유 문구
```

### A6_render — 리포트 렌더

```yaml
status: ready
template: references/report-template.html
renderer: script-only                # 필수 · 셸/sed 직접 주입 금지 (렌더 규율)
gate_overrides: {}                   # 선택 · 게이트 임계 오버라이드 {gate_id: value} — 완화는 사유 필수
sections: [...]                      # 선택 · 섹션 스파인 (템플릿 기본과 다를 때만)
```

### A7_modifier_implication — 함의 사전 (선언 전용 · 훅 없음)

```yaml
status: partial
authority: references/space-context-typology.md   # T6 설치 제약이 초기 씨앗
version: "0.1"
entries:                             # 승인된 함의만 엔진이 사용
  - modifier: "무배기|ventless"
    implied_condition: "배기구 설치 불가"
    w_slot: W3
    ambiguity: "1:1"
    status: approved
    evidence: "ventless dryer 20,500/월 (2026-08 실측)"
    approved_by: "..."
pending:                             # LLM 제안 대기 — 엔진은 절대 사용하지 않음 (G2 차단)
  - modifier: "저소음"
    candidates: ["영유아 동거", "야간 사용", "층간소음 민감"]
    ambiguity: "1:N"                 # 분해 전 배치 금지 (N1 규칙)
```

## 3. 훅 계약 — seed-check/v1

- 호출: `python3 <cmd> --gl <gl> "<seed>" ["<seed>" ...]` (작업 디렉터리 = 어댑터 위치)
- 종료 코드 0 = 정상 (판정 결과와 무관). 비0 = 훅 실패 → 엔진은 내장 프로브로 폴백하고 manifest에 기록.
- 표준 출력: 시드당 JSON 1행
  `{"seed": str, "gl": str, "verdict": "pass|replace|pool|discard", "noise_rate": float, "fit_rate": float, "brand_hits": int, "alt_seeds": [str], "cost": int}`
- 크레딧을 쓰는 훅이므로 엔진은 호출 전 `--budget` 잔여를 확인하고, cost 합산을 원장에 기록한다.

## 4. 엔진 폴백 규칙 (status별)

| 슬롯 | absent/partial 시 엔진 동작 | 배너 기록 |
|---|---|---|
| A1 | 내장 프로브(임계 기본값 20%/60%/10) · 금지 시드 없이 진행 | "시드 정책 기본값" |
| A2 | 범용 노이즈 어휘만( ○○ 영어로 · 기업 노드 등) — 볼륨 재확인 필수 유지 | "노이즈 사전 없음 — 오염 위험" |
| A3 | 엔티티 미검증 전원 별도 목록 · SoV/브랜드 매트릭스 산출 생략 | "별칭 정본 없음 — 브랜드 지표 생략" |
| A4 | delta만 산출, 자산 반영 대상 없음 · 사전 매핑 없이 전량 신규 판정 | "온톨로지 미연결 — 누적 불가" |
| A5 | 엔진 공통 문구만 삽입(근사·검색≠구매·개인정보) | "버티컬 가드레일 없음" |
| A6 | 엔진 기본 템플릿 | "기본 템플릿" |
| A7 | 함의 역추론 생략 — 제약(L4)은 gap 처리 | "함의 사전 없음 — L4 공백" |

## 5. 검증 규칙 (lib/vertical.py 구현 대상)

1. `schema == cep-finder-adapter/v1` · 필수 최상위 필드 존재 · `adapter_version` semver 형식.
2. 각 슬롯: `status` 값 유효 · ready인데 필수 필드 누락이면 **partial로 강등하고 경고**(실행은 계속).
3. 경로 필드: 파일 존재 확인 — 없으면 해당 슬롯 partial 강등 + 배너.
4. `thresholds` 범위(0~1, 정수>0) · `id_prefixes` 정규식 `^[A-Z][A-Z0-9]{0,5}$` (C1·C2·C3 등 숫자 포함) · `markets ⊆ {kr, jp, us}`.
5. A7 `pending` 항목이 `entries`에 중복되면 오류(승인 전 사용 방지).
6. 검증 결과 전문을 run_manifest `adapter_validation`에 기록.
7. **카테고리 커버리지** (2026-09-17 · `Adapter.check_category_coverage`) — 1~6은 "파일이 있고 형식이 맞는가"만
   본다. 엔진은 로드 직후 분석 품목으로 A2·A3를 다시 보고, **0건이면 ready → partial 강등** + `issues`·배너·warnings에
   `카테고리 '<X>' 미등재 — …`를 남긴다(실행은 계속). 판정 대상은 `category` 앵커면 그 품목,
   product·feature 앵커면 sense `category`(부모 품목).
   - 품목어 확장: E0(`e0-csv/v1`)에서 라벨·별칭이 품목과 같거나 품목명 안에 든 C1~C3·Line 노드 → 라벨·별칭 + 부모 C2.
     대분류어(C1·C2 group 약칭 — '생활'·'주방')는 넓어서 **섹션 제목 대조에만** 쓴다.
   - A2: E0에 품목 노드가 1건 이상.
   - A3(`brand-map-md/v1`): ① `#` 섹션 제목에 품목어·대분류어 ② 파서가 읽는 `- **X** — …` 줄에 품목어
     ③ 품목어가 든 E0 Line·Brand(예: 무풍='무풍에어컨')의 별칭이 그 줄에 있음 — 중 하나라도.
     표·원칙 불릿·E0 Brand 행만으로는 통과시키지 않는다(엔진 `load_brand_map`이 읽지 않으므로).
   - 검사 근거는 `adapter_validation.coverage`(terms·hits)에 남긴다. 거친 판정이다 — 통과가 "브랜드 폭이 충분하다"는 뜻은 아니다.
