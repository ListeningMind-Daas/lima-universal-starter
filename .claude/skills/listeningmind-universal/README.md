# listeningmind-universal — 범용 검색 행동 분석 스킬 패키지 (v2.0 · 2026-08-25)

리스닝마인드 DaaS 커넥터(핵심 4 + 보조 2 — serp·trend_finder) 데이터로 **산업 무관** 시장·브랜드·상품·여정 질문에 답하는 표준 베이스 스킬.
복수 산업·카테고리 실측(2026-07~08)에서 검증된 규율 — 시드 검증·준비도 배너·크레딧 원장·스크립트 렌더 —
을 범용 규격으로 내장했다.

## 설치

```
.claude/skills/listeningmind-universal/   ← 이 폴더째 (Claude Code는 이 깊이의 SKILL.md만 인식)
```
- 프로젝트 설치: 워크스페이스 `.claude/skills/` 아래 복사 · 전역 설치: `~/.claude/skills/` 아래 복사
- API 키: `lima-agents/scripts/setup_key.py`로 설정(`00_Context/.lm-api-key` · 권한 600) · 환경변수 `LM_API_KEY` · 스크립트 `--key` 옵션
- 엔드포인트: 기본값은 운영 서버 — 별도 설정 불필요. 필요 시 `LM_API_BASE` 환경변수로 재정의
- `lima-agents` 스킬(이 스타터에 동봉)이 함께 있으면 그 `api/`·CEP Finder 엔진을 재사용하고,
  없으면 내장 클라이언트로 단독 동작

## 구조 — 4계층

```
listeningmind-universal/
├── SKILL.md                      프론트도어: 트리거·실행 순서 11단계·7잡·6층·게이트·가드레일·산출물
├── adapter.yaml                  CEP Finder 어댑터 (cep-finder-adapter/v1 · A4·A7 absent 선언)
├── README.md · agents/openai.yaml
├── references/
│   ├── _shared-core.md           ③ 표현 규율 정본 (정직성·라벨 5등급·크레딧·국가/사양·호출·렌더·포크)
│   ├── guardrails.md             ③ 범용 가드레일 + 규제 도메인 추가 규칙
│   ├── readiness-gate.md         ③ 준비도 6차원 · 배너 규격(프롬프트로 못 막는 제약)
│   ├── question-frames.md        ① 역할별 질문 카탈로그 · 발화 템플릿 · 범용 프레임 F1~F10
│   ├── jobs.md                   ① 표준 7잡 플레이북 (절차·산출·실측 함정)
│   ├── decision-structure.md     ① 6층 정의 · CEP 상황형/전이형 분기
│   ├── seed-verification.md      ② 시드 검증 3단계 · 역할 3종 · 오염 유형 8종 대체 규칙
│   ├── entity-dictionary.md      ② brand-map 표기 계약 · 채널/리뷰어 분리 · 동음이의·동의어
│   ├── tool-routing.md           ④ 커넥터 라우팅 · 실측 단가 · 예산 프리셋
│   ├── workflow.md               ④ 실행 절차 상세
│   ├── output-patterns.md        ④ 텍스트 구조 · HTML 스파인(세그먼트/카테고리)
│   ├── ops-monitoring.md         ④ 월간 모니터링·구조 변화 감지·크레딧 원장
│   ├── vertical-overlay-guide.md 산업·고객사 오버레이 만들기 체크리스트
│   └── report-template.html      ④ HTML 리포트 템플릿 (섹션 마커 · inline SVG · 라이트/다크)
├── dictionary/
│   ├── E0_사전.csv               ② 범용 노이즈·채널·리뷰어 사전 (e0-csv/v1 · append-only)
│   ├── brand-map.md              ② 엔티티 사전 빈 템플릿 (brand-map-md/v1)
│   └── seed_registry.csv         ② 시드 판정 기록 (seed_check.py가 append)
├── scripts/
│   ├── seed_check.py             시드 검증 프로브 (intent_finder ~230크레딧/시드 · --replay 0크레딧 · --mode cs · --role)
│   ├── credit_estimate.py        호출 계획 → 예상 크레딧 (실측 단가 · --preset quick/standard/deep · --budget)
│   ├── render_report.py          data.json → HTML (섹션 제거·번호·SVG·가드레일 문구 경고)
│   └── render_cep_deck.py        deck.json → CEP 카드 덱 HTML (카드·NI/KBF·매트릭스·부재 판정·크로스)
├── examples/
│   ├── sample-report.json / .html 렌더러 검증용 가상 샘플
│   ├── cep-deck-sample.json       CEP 카드 덱 가상 샘플 (render_cep_deck 검증용)
│   └── probe-replay/             seed_check --replay 픽스처 (스냅샷 2건 · 0크레딧 재실행 데모)
└── evals/evals.json              테스트 프롬프트 3건
```

## 빠른 검증 (설치 후 · 크레딧 0)

```bash
python3 scripts/credit_estimate.py --preset standard
python3 scripts/seed_check.py --replay examples/probe-replay --anchor "삼계탕,닭갈비,닭" --skip-brand-gate --no-registry
python3 scripts/render_report.py examples/sample-report.json -o 99_Scratch/sample.html
python3 scripts/render_cep_deck.py examples/cep-deck-sample.json -o 99_Scratch/deck.html
```

## 첫 발화 예시

```
리포트· 전기자전거 한국 시장 세그먼트 리포트
- gl=kr / 세그먼트 리포트 / 실행 주체: 중립 조사
- 잡: 수요·트렌드 주축 + 경쟁·브랜드(SoV) 보강 · 크레딧 6만 이내 / HTML + Artifact
```

## 버전

- **2.0 (2026-08-25)** 스타터 패키지 전달본. 4계층 구조 · 시드 검증 스크립트·사전 · 준비도 배너 규격 ·
  카테고리/세그먼트 스파인 · 스크립트 렌더 템플릿 · 크레딧 원장·실측 단가 · 운영 모드 · CEP 유형 분기 ·
  adapter.yaml 계약 · 규제 도메인 추가 규칙 · 오버레이 가이드.
