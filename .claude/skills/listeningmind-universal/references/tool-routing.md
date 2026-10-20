# 커넥터 라우팅 · 예산 프리셋 (④ 계층)

> **단가 근거 순서** — ① 공개 API 문서 https://listeningmind-data-api.ascentlab.io/ ② `lima-agents/references/daas-api-overview.md`
> §크레딧 참고(스냅샷) ③ 응답 `cost_detail.total_cost`(실제 청구). 셋이 어긋나면 **API 문서가 이긴다.**
> 이 문서는 단가를 **복제하지 않는다** — 라우팅 판단에 필요한 **상대 비용 순서만** 쓴다.
> 절대 수치가 필요하면 정본을 읽거나 `scripts/credit_estimate.py` 로 계산한다.
> (2026-08-28 serp 단가가 10→30으로 인상된 사례처럼, 복제본은 반드시 뒤처진다.)

## 1. 라우팅표

| 질문 | 주 | 보조 | 비고 |
|---|---|---|---|
| 수요·추세·시즌·인구(kr)·의도·SERP 피처 | keyword_info(all) | intent_finder | 볼륨 사전 검증은 `ads_metrics` — `all` 대비 크게 저렴 |
| 연관어·표현 변형·오타·모델명 수확·시드 프로브 | intent_finder | keyword_info | **가장 싼 구조 탐색** — 반환 수 비례 |
| CEP·KBF·엔티티·군집·관계 구조 | cluster_finder | intent_finder·keyword_info | 반환 고유 키워드 수 비례 — `limit`(관계 수 상한)으로 간접 통제 |
| 여정·전이·직전/직후·관문·이탈 | path_finder | cluster_finder | **최고가** — 경로 내 고유 키워드 수 비례 |
| 노출 화면·블록(AIO·PAA·광고·쇼핑) | serp | keyword_info.features | 키워드당 정액 · `features`로 충분하면 생략 |
| 급등 원인·최근 이슈·단발/지속 판정 | trend_finder | keyword_info(추세) | 시드당 정액 + 반환 이슈 비례 · 빈 결과는 실측이며 과금 0(기간 90→365 로 한 번 넓힘) · **시드는 급등 키워드 전체가 아니라 구별 토큰, 결과는 품목 어휘로 사후 필터**(`collect_demand.py explain`) · 매칭 1,000건 초과는 판정 보류 |
| 연관 키워드 묶음의 AIO 원문·인용 출처 | `*/keyword_list`(인텐트·관계망·여정) 또는 trend_finder(이슈) 확장 → 유니크 목록 → serp | keyword_info(ads_metrics 로 대상 축소) | 확장 호출 + serp 키워드당 정액 · 절차 `lima-agents/references/serp-api.md` |
| 정산·월간 사용량 | usage/summary | — | 조회 전용 · 무과금 |

**tie-breaker** — 목록이면 intent_finder, 구조면 cluster_finder, 순서·전이가 결정에 들어갈 때만 path_finder.
`*/keyword_list` 경량 계열은 구조가 필요 없을 때의 대안 — `intent_finder` 와 같은 과금 구조다.

## 2. 비용 순서 (절대 수치는 정본 참조)

싼 것으로 구조를 먼저 보고, 비싼 것은 **검증된 시드에만** 쓴다.

```
intent_finder  ·  */keyword_list   반환 수 비례        가장 쌈 — 구조 탐색·시드 프로브
keyword_info (ads_metrics)         키워드당 최소       볼륨 사전 검증
serp                               키워드당 정액       노출 화면 확인
trend_finder                       시드 정액 + 이슈 비례 급등 원인·최근 이슈 — limit 으로 통제
keyword_info (all)                 키워드당 정액       인텐트·인구·시계열이 필요할 때만
cluster_finder                     반환 고유 키워드 비례 limit(관계 수 상한)으로 간접 통제
path_finder                        경로 고유 키워드 비례 가장 비쌈 — 여정이 결론에 필요할 때만
```

과금 단위를 오해하지 않도록 두 가지만 기억한다.

- `cluster_finder` 는 **관계 수가 아니라 반환 고유 키워드 수**로 과금된다 — `limit`은 관계 수 상한이라 과금 수를 직접 정하지 못한다
- `path_finder` 는 **경로 수(limit)가 아니라 경로에 등장한 고유 키워드 수**로 과금된다 —
  같은 150경로여도 여정이 다양할수록 비싸진다

정확한 공식·실측 검증 이력 → `lima-agents/references/daas-api-overview.md` §크레딧 참고 및 커넥터별 명세.
호출 1건의 실제 비용은 언제나 응답 `cost_detail.total_cost` 가 유일 기준이다.

## 3. 예산 프리셋 (`scripts/credit_estimate.py --preset`)

아래 수치는 스크립트가 **정본 단가로 계산한 결과**다. 단가가 바뀌면 스크립트를 고치고 이 표를 재생성한다.

| 프리셋 | 구성 | 대략 |
|---|---|---|
| quick | 프로브 1 · keyword_info ads_metrics 200 · cluster keyword_list 300 | ~1,060 |
| standard | 프로브 2 · keyword_info all 500 · cluster 반환 고유 키워드 1,000 · path 1 | ~62,460 |
| deep | 프로브 3 · keyword_info all 3,000 · cluster 반환 고유 키워드 5,000 · path 4 | ~308,240 |
| demand-lite | 프로브 12 · keyword_info ads 852 | ~3,612 |
| demand | 프로브 24 · keyword_info ads 2,304 · cluster keyword_list 150×5 | ~9,474 |
| demand-deep | 프로브 40 · keyword_info ads 4,040 · cluster keyword_list 150×10 | ~16,540 |

실측 참고: 세그먼트 리포트 1건 3~4만(기본) · 대형 분석은 관계망·여정 비중이 커서 수십만까지 늘 수 있다 ·
CEP Finder 라이브 run은 수천~수만(REVERSE 여정 재시도가 늘리면 몇 배).

## 4. 호출 순서 원칙

1. 프로브(intent_finder)로 구조·오염을 보고 연관어를 확장한다 → 2. keyword_info(ads 계열)로 시드 규모를 잰다 →
3. cluster_finder는 hop 1로 구조·연관 키워드를 확장한다(목록만이면 `/keyword_list` · 구조는 limit 300 후 필요 시 확대) →
4. 확장한 유니크 전체의 규모를 keyword_info로 잰다(월별은 `ads_info` · `all`은 필요한 상위만) →
5. path_finder는 여정이 결론에 필요할 때만, 검증된 시드로만. 수요 잡은 `demand-pipeline.md`가 이 순서의 구현이다.
"넓게 한 번"이 아니라 "좁게 여러 번"이 싸다. 사용자 상한이 있으면 호출 전 예상치를 고지한다.
