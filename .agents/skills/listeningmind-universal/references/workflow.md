# 실행 절차 (④ 계층 · 상세)

SKILL.md §1의 11단계(10단계 + 11 발행 전 확인·규칙 회수)를 실행 관점에서 풀어쓴다. 규율은 `_shared-core.md`, 판정은 `readiness-gate.md`.

## 1. 인테이크 — 뽑아야 할 필드

| 필드 | 없으면 |
|---|---|
| 대상(카테고리·브랜드·제품) + 시드 후보 | 메타 단어 제거 후 헤드텀·결합형 후보 3~5개 작성 |
| gl (kr/us/jp) | 기본 kr · 해외면 인구통계 사양을 배너에 |
| 기간·시점 | 기본 curr(최근 48개월) · 전후 비교는 time_point |
| 실행 주체 (브랜드 관점/중립/경쟁사) | 리포트면 AskUserQuestion · 텍스트면 중립 기본값 + 명시 |
| 결정 소유자(페르소나) | about-me.md Q2 → 없으면 발화에서 추론 |
| 산출 형식 | 즉답형=텍스트 · 다면적=HTML |
| 크레딧 상한 | 없으면 `credit_estimate.py` 추정치를 고지하고 진행 |
| 분석 단위 (카테고리/세그먼트) | SKILL.md §1-4 규칙 · 모호하면 질문 |

## 2. 플랜 — 최소 도구 세트

- 넓은 시드 1개로 공간을 지도화(intent_finder 프로브 or cluster_finder keyword_list) → 준비도 게이트가
  커버리지 공백을 보일 때만 동의어·문제어·상황어·비교어·브랜드 엔티티를 한 패밀리씩 추가한다.
- 표준 파이프라인은 **확장(intent 프로브·cluster_finder) 뒤에 keyword_info로 규모를 잰다.** 월별 계열만 필요하면
  `ads_info`(키워드당 1), 인텐트·인구·SERP 피처가 결정에 필요할 때만 `all`(키워드당 10). path_finder는 여정이 결정에
  필요할 때만, serp는 노출 화면이 필요할 때만. 수요·트렌드 잡은 `demand-pipeline.md`의 D1~D8을 그대로 쓴다.
- 예산 프리셋: `quick`(프로브 1·여정 0·keyword_info ads_metrics) / `standard`(프로브 2·여정 1~2·all) /
  `deep`(프로브 3·여정 4·cluster 5000) / 수요 잡 `demand-lite`·`demand`·`demand-deep`. `tool-routing.md` §3.

## 3. 시드 검증 (크레딧 쓰기 전 · `seed-verification.md`)

```bash
python3 scripts/seed_check.py --gl kr --anchor "전기자전거,전동자전거,자전거" "전기자전거" "전기자전거 추천" "전동자전거"
```
통과한 시드만 하류로. 판정은 `dictionary/seed_registry.csv`에 append. 상황 앵커·제품 앵커는 역할을
`--role situation|product`로 지정해 적합률 게이트를 면제한다(도달률은 측정 결과값).

## 4. 직렬 수집 — 순서와 스냅샷

1. `intent_finder/keyword_list(시드, limit 100)` — 시드 검증 프로브 겸 연관어 확장(`seed_check.py --dump`) · 콘텐츠·모델명 추출
2. `keyword_info(시드, ads_metrics)` — 시드 규모 · 구조 탐색 대상 선정
3. `cluster_finder(시드, hop 1)` — 목록만 필요하면 `/keyword_list`(limit 150), 군집·엔티티·관계가 필요하면 본 호출(limit 300→필요 시 확대)
4. `keyword_info(확장 유니크)` — 월별 계열은 `ads_info`, 인텐트·인구(kr)·SERP 피처는 필요한 상위 키워드에만 `all`
5. `path_finder(시드, limit 150)` — 여정(진입·분기·이탈) · 상황형 CEP는 상위 앵커로
6. `serp(키워드)` — 노출 블록이 필요할 때만
각 응답을 분석 폴더(`<run>/api/` 등)에 저장하고 원장(`ledger.json`)에 `{tool, params, cost}`를 누적한다.
수요·트렌드 잡은 이 순서를 코드로 고정한 `scripts/collect_demand.py`를 쓴다(`demand-pipeline.md`).

## 5. 게이트 루프

첫 패스 후 준비도를 채점한다. EXPAND면 **증거 패밀리를 하나씩** 추가(동의어 → 상황어 → 브랜드 → 여정),
새 호출이 구조를 거의 더하지 않으면 멈춘다. NARROW면 좁힌 범위를 배너에 명시한다.
볼륨 총량을 낼 때는 노이즈율을 **개수 기준이 아니라 볼륨 기준**으로 재확인한다(TV: 개수 25% vs 볼륨 93%).

## 6. 합성 — 층을 섞지 않는다

수요(volume) · 맥락(CEP) · 선택(KBF) · 마찰(여정) · 신뢰(RTB) · 채널을 분리해 읽는다. 연관어를 전부 "니즈"로
뭉개지 않는다. 구매 전 수요와 구매 후 층(사용법·가격 시그널·CS)은 분리 계상한다.

## 7. 결정 번역

발견을 구체적 결정으로 옮긴다 — 타겟 세그먼트 · 제품 요건 · 메시지 · 근거 자산 · 채널 · 콘텐츠 · 캠페인 ·
추가 조사. 실행 주체 단일 관점으로 백로그를 쓴다(브랜드 관점이면 자사 액션, 중립이면 시장 관찰).

## 8. 산출·보관

- 텍스트: `output-patterns.md` §1 구조. HTML: `render_report.py data.json → 90_Output/<대상>-리포트-<날짜>.html`.
- 응답 끝: 크레딧 실측(소진·월간 누적) · 다음 조사 추천(강한 추천 1 + 대안 2) · 추가 호출 없이 답할 수 있는 범위.
