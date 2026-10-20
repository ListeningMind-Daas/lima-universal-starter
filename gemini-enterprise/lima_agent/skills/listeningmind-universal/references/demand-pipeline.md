# 수요 파이프라인 (④ 계층 · 잡 1 수요·트렌드 수집 계약)

잡 1(수요·트렌드)은 시드 몇 개가 아니라 **시장 경계를 덮는 키워드 집합의 월별 48개월 검색량**으로 규모·YoY·시즌을 낸다.
시장 인텔리전스 파이프라인의 시드 설계·확장 수집·전처리·트렌드 단계를 범용 스킬 크기로 옮긴 계약이다.
실행은 `scripts/collect_demand.py` 한 스크립트 — 단계마다 분석 폴더에 입력·원본 응답·출력을 남기고 `--replay`로 0크레딧 재실행한다.

```
D1 plan     시드 레이어 설계 검사                      0크레딧
D2 expand   시드 검증 + 연관어(프로브 재사용)          시드당 약 100~230
D3          시드 볼륨(ads_metrics)                      키워드당 1
D4          구조 탐색(cluster_finder/keyword_list hop 1) 호출당 30 + 반환×2
D5          유니크 정리 · 제외 표시                      0크레딧
D6 collect  유니크 전체 keyword_info(ads_info)          키워드당 1 — 월평균 + 48개월 월별
D7 build    노이즈·브랜드·중복 제거                      0크레딧
D8          수요 지표 → core/demand_metrics.json        0크레딧
   report   렌더러 입력 뼈대(수치 필드)                  0크레딧
```

단가는 `scripts/credit_estimate.py`(`--preset demand-lite|demand|demand-deep`)에서만 읽는다.
**월별 계열은 `ads_info`(키워드당 1)가 준다** — `all`(키워드당 10)은 인텐트·인구(kr)·SERP 피처가 결정에 필요할 때,
D8 상위 키워드에만 따로 부른다(잡 5·6). 수요 지표에는 쓰지 않는다.

## D1. 시드 레이어 설계 — `seed_layer_config.json`

에이전트가 요청에서 대상·재화 유형·관여도를 판정해 초안을 쓰고, **시드 목록을 사용자에게 보여 확인받는다.**

| 층 | 뜻 | 기준 |
|---|---|---|
| `M1_problem` | 문제·욕구 표현 (상위 수요) | 20% 이상 — 없으면 상위 수요 클러스터가 통째로 빠진다 |
| `M2_market` | 시장 경계를 정하는 솔루션 범주 | 10% 이상 — 규모의 기준점 |
| `M3_supply` | 브랜드·제품명 | 40% 이하 — **D1에서는 비워 둔다.** D2 코퍼스에서 수확해 채운다 |
| `M4_substitute` | 대체재·경쟁 솔루션 | 10% 이상 — 없으면 시장 경계가 좁게 그려진다 |
| `dynamic.<이름>` | 재화 유형별 층 | 기능재: feature·spec_comparison·compatibility / 표현재: occasion·aesthetic·body_demo·price_tier / 서비스재: use_case·pain_point·review_signal / 정보재: topic·skill_level·format_pref / B2B: job_role·company_size·integration |

총 12개 이상, 권장 20~30. M3를 에이전트 기억으로 채우지 않는 이유 — 새 카테고리는 브랜드 사전이 비어 있어 누락·환각이 생긴다.

```json
{"target": "전기자전거", "gl": "kr", "anchor": ["자전거", "전기"], "preset": "demand",
 "good_type": ["functional"], "involvement": "high",
 "layers": {"M1_problem": ["출퇴근 힘들다", "언덕 자전거 힘들다"], "M2_market": ["전기자전거", "전동자전거"],
            "M3_supply": [], "M4_substitute": ["전동킥보드", "스쿠터"],
            "dynamic": {"feature": ["접이식 전기자전거"], "spec_comparison": ["전기자전거 추천"]}}}
```

`anchor`는 확장어의 카테고리 적합 판정 기준이다(D5). **품목 전용 어휘로 쓴다** — 상위 카테고리어('자전거')를 넣으면
구조 탐색의 일반 품목 노드(어린이 자전거·강아지 자전거)가 핵심 층에 남는다. `plan`은 층 비율·총수 경고와 예상 크레딧 범위를 `plan.json`에 낸다.

## D2. 시드 검증 + 연관어

`seed_check.py --dump <run>/probe`를 시드마다 한 번 부른다(없는 시드만). 프로브 반환어를 **확장 코퍼스로 재사용**한다 —
층별 intent_finder를 따로 부르지 않아 같은 호출을 두 번 사지 않는다. `시드 교체`·`폐기` 판정 시드는
하류에서 뺀다(`expand.json`의 `rejected`). **M3 브랜드 시드는 적합률을 면제한다** — 연관어가 모델명('모토벨로 m10')이라
카테고리 어휘가 거의 없다(seed-verification.md 제품 앵커 규칙과 같다). 노이즈율 교체·사전 폐기는 그대로 둔다. M2 시드 코퍼스에서 브랜드를 수확해 `<run>/E0_<카테고리>.csv`(Brand 행)를 쓰고
`M3_supply`를 채운 뒤 `expand`를 다시 돌리면 새 시드만 프로브한다(시드 볼륨도 새 시드만 잰다).
**E0의 라벨·별칭에 일반 품목 제조사명 단독('삼천리자전거')을 넣지 않는다** — 라벨도 매칭어라 확장어 적합 판정·브랜드
태깅으로 일반 품목 수요가 들어온다. 대상 품목 결합형·전용 라인명('삼천리 팬텀')만 쓴다.
단독이 다른 뜻인 브랜드(벤츠·혼다·인물 광고 모델)는 note에 `결합형만`을 적으면 라벨 단독은 매칭하지 않고 별칭(결합형)만 매칭한다 —
예: `Brand,벤츠,벤츠 전기자전거|벤츠 전기 자전거,결합형만 — 단독은 자동차` · 광고 모델 검색을 브랜드로 귀속할 때도 같다(`서경석 전기자전거`→비아지오).
사전을 고친 뒤에는 `expand --replay → collect --replay → build`로 0크레딧 재계산한다.

## D3~D4. 시드 볼륨 · 구조 탐색

통과 시드를 `ads_metrics`로 잰다. **M2·동적 층 시드 중 월평균 1,000 이상** 상위 N개(프리셋: lite 0 · demand 5 · deep 10)에
`cluster_finder/keyword_list`(hop 1 · limit 150)를 부른다. 키워드 목록만 필요하므로 본 호출(150 + 반환 고유 키워드×50)보다 크게 싸다.
군집 구조가 필요한 잡 2·4와 함께 돌 때만 본 호출로 바꾼다. **hop 2는 쓰지 않는다.**

## D5. 유니크 정리 — `unique_keywords.csv`

조인 키는 NFKC·소문자·공백 제거다. 같은 키가 여럿이면 먼저 들어온 소스를 남긴다:
`seed → intent:M2 → intent:M1 → intent:M4 → intent:dynamic → intent:M3 → cluster`.
시드가 아닌 행에 `excluded_reason`을 표시한다(지우지 않는다): `사전 Noise` · `노이즈 패턴`(adapter A2) ·
`앵커 무관`(anchor 어휘·등록 브랜드가 없음 — 대체재 층 확장어는 출처 시드 토큰도 인정. anchor가 비면 출처 시드 토큰으로 판정). 표시된 행은 D6에서 재지 않는다(`--include-excluded`로 재기).

## D6. 월별 수집 — `keyword_info_all.csv`

제외 표시 없는 유니크 전체에 `keyword_info(ads_info)`를 1,000개 배치로 부른다. 배치마다 즉시
`api/kwinfo_ads_info_NNN.json`으로 저장하고 `ledger.json`에 `total_cost`를 더한다. 호출 전 `--budget`으로 멈출 수 있다.
응답은 요청어에 정확 일치 → 정규화 키 순으로 조인하고(`collect.json`의 `rematched`),
요청하지 않은 표기 변형 행은 버린다(`unrequested_rows`). 저장본에 이미 있는 요청어는 다시 부르지 않는다.

## D7. 전처리 — `keywords_master.csv`

| 열 | 판정 |
|---|---|
| `is_noise` | D5 제외 표시 · 사전 Noise · 노이즈 패턴 |
| `brand` | E0 Brand/SubBrand(기본 + `<run>/E0_*.csv`) 단어 경계 매칭 |
| `is_variant` · `canonical` | 월별 계열(월 × total·gg·nv)이 완전히 같은 행은 한 검색 — 대표만 센다. 48개월 합계 1,000 미만이면 토큰 겹침·띄어쓰기 동일일 때만 묶는다(`lima-agents/lib/series_dedup.py`) |
| `gg_shared_with` | 구글 계열만 같은 표기 변형 — 구글은 대표만, 네이버는 각자 더한다 |
| `below_threshold` | 월평균이 임계(프리셋: lite 100 · demand 30 · deep 10) 미만 — 시드는 예외 |
| `counted` | 측정됨 · 노이즈 아님 · 변형 아님 · 임계 이상 |

## D8. 수요 지표 — `core/demand_metrics.json`

`counted` 행만 더한다. 최신 미완월은 뺀다(기준월 `--as-of`, 기본 오늘이 속한 달).
**헤드라인(월별 계열·YoY·시즌·채널)은 핵심 층(M2 시장 · M3 브랜드 · 동적 층)만 합산한다.** 문제(M1)·대체재(M4) 층은
다른 수요라 더하면 대상 품목의 규모가 부풀어 오른다 — `scope.context_last12`·`by_layer_last12`에 맥락으로 따로 낸다.
맥락 층에서 확장된 검색어라도 anchor 어휘를 담으면('하이브리드 전기자전거') 대상 품목 수요라 헤드라인에 넣고
`by_layer_last12`에 `M4_substitute→core`처럼 표시한다. 시드는 층을 유지한다.

- `monthly_total·gg·nv` 완결월 계열 · `last12_sum·avg` · `yoy`(최근 12 vs 직전 12 — 24개월 미만이면 null)
- `seasonality_index` 최근 36개 완결월의 달별 평균 / 전체 평균 · `peak_months` 1.5 이상 · `season_amplitude` max/min
- `channel_share_last12` 구글·네이버 비중 · `by_layer_last12` · `by_source_last12`
- `coverage` — `screen_volume_share`(임계 통과 볼륨 비중) · `m1_m4_share_last12`(문제·대체재 층 비중 — 원본 SEED-COVERAGE) ·
  `dedup_removed_last12`(핵심 층에서 중복 제거로 빠진 양) · `scope.all_layers_last12`(맥락 층 포함 전체)
- `keywords` — 유니크·측정·제외·변형·임계 미만·집계 수 · 미요청 변형 행 수

`core/`에 두는 이유: `render_report.py --run <run>`의 문구 숫자 대조가 `core/*.json`을 사실 원천으로 읽는다.
준비도 배너(readiness-gate.md)에 `coverage`와 `keywords`의 제외·변형 수를 그대로 쓴다. 급등월이 보이면 trend_finder로 원인을 확인한다.

`report`는 이 파일에서 KPI 4장·24개월 추이·준비도 한계·크레딧 원장을 채운 `report-skeleton.json`을 낸다 — 서술 필드는 에이전트가 쓴다.

## D9~D10 · 잡 4 · 잡 5 — build 산출물을 재사용하는 후속 단계

| 명령 | 하는 일 | 출력 | 크레딧 |
|---|---|---|---|
| `rising` | 헤드라인 층 키워드마다 최근 3개 완결월 평균 vs 전년 같은 달 평균. 기본: 최근 1,000 이상이면서 2배 이상, 또는 전년 100 미만에서 신규. 카테고리 월별 YoY를 함께 적어 "합계는 조용한데 키워드는 뛴다"를 가른다 | `core/rising.json` | 0 |
| `explain` | 상위 N개(기본 5) 라이징의 구별 토큰(anchor가 아니고 집계 키워드 중 가장 드문 토큰 · 두 글자 이하는 이웃과 붙임)으로 trend_finder(90일 → 비면 365일 · limit 20) · 토큰과 품목 어휘가 함께 나오는 이슈만 남긴다. 판정: 원인 이슈 있음 · 무관 이슈만 · 이슈 없음 · 매칭 과다(1,000건 초과) 판정 보류 | `core/rising_explained.json` | 토큰당 최대 90 · 빈 결과 0 |
| `share` | 헤드라인 층을 브랜드(E0 Brand)·판매 채널(E0 Channel)·커뮤니티(E0 Reviewer)·무브랜드로 나눈 최근 12개월 검색 점유와 YoY. 한 키워드는 한 브랜드(가장 긴 별칭). 미등재 브랜드·유형 후보(앵커를 담은 토큰 앞 토큰 · 시드 어휘·'-용'·일반 수식어 제외)는 사람이 골라 E0에 넣는다 | `core/brand_share.json` | 0 |
| `content` | 목적별 묶음(문제해결·구매·비교·검증·정보·사용·탐색)과 권장 형식 · 시드 제외 비중 병기 · `--serp-top N`이면 상위 검색어 serp의 연관 질문·AI 개요 노출률·자연결과 상위 10 사이트 분포와 그 검색어들의 구글 비중 | `core/content.json` | serp 30×N |

trend_finder 이슈의 `summary`는 검색결과의 AI 요약이다 — 소비자 발화가 아니라 외부 요약으로 표기한다. 이슈 인덱스는 2025-05-26 이후·최대 365일만 덮는다.
SERP는 구글 결과 스냅샷이다 — 구글 비중이 낮으면 노출 지형을 단정하지 않고, 시계열 비교에 쓰지 않는다.

## 분석 폴더

```
seed_layer_config.json  plan.json  expand.json  collect.json  ledger.json  gates.json
probe/ (seed_check --dump)   cluster/   api/seed_volume.json   api/kwinfo_ads_info_NNN.json
unique_keywords.csv   keyword_info_all.csv   keywords_master.csv   core/demand_metrics.json   report-skeleton.json
core/rising.json   core/rising_explained.json   core/brand_share.json   core/content.json   api/trend_*.json   api/serp_*.json
E0_<카테고리>.csv (선택 · 분석별 브랜드 사전)
```

## 순서 (예)

```bash
S=lima_agent/skills/listeningmind-universal/scripts; R=99_Scratch/ebike-demand
python3 $S/collect_demand.py plan    --run $R                  # 경고·예상 크레딧 → 사용자 확인
python3 $S/collect_demand.py expand  --run $R --budget 8000     # D2~D5 (M3 채운 뒤 한 번 더)
python3 $S/collect_demand.py collect --run $R --budget 5000     # D6
python3 $S/collect_demand.py build   --run $R                  # D7~D8
python3 $S/collect_demand.py report  --run $R                  # 뼈대 → 서술 → render_report.py --run $R
python3 $S/collect_demand.py rising  --run $R                  # 키워드 단위 라이징
python3 $S/collect_demand.py explain --run $R --budget 500     # 라이징 원인(trend_finder)
python3 $S/collect_demand.py share   --run $R                  # 잡 4 브랜드 점유
python3 $S/collect_demand.py content --run $R --serp-top 10 --budget 300   # 잡 5 콘텐츠·SERP
```

게이트 기록은 `lima-agents/scripts/run_gate.py`로 남긴다 — 예산(plan 추정·사용자 상한) · 수집(collect.json 측정 수) · 준비도.
