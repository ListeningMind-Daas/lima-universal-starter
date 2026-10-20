# keyword_info API · 완전 참조

**엔드포인트**: `POST /keyword_info`
**목적**: 특정 키워드의 볼륨·트렌드·인구통계·SERP feature·의도 조회
**파라미터**: `keywords` (배열 · 1~1000개)

## 요청 표준

```bash
curl -X POST "https://listeningmind-data-api.ascentlab.io/keyword_info" \
 -H "Content-Type: application/json" \
 -H "LM-API-KEY: $API_KEY" \
 -d '{
 "keywords": ["전기자전거", "전기자전거 추천"],
 "gl": "kr",
 "data_type": "all"
 }'
```

## data_type 3가지 (공식 · 라이브 OpenAPI cost 스키마 기준)

 **중요**: data_type별 크레딧 단가는 <b>차등</b> — `ads_metrics`·`ads_info` 키워드당 1크레딧, `all` 키워드당 10크레딧 · 출력 과금 없음.

| data_type | 크레딧/kw | 반환 필드 | 언제 사용 |
|---|---|---|---|
| `ads_metrics` (기본) | **1**| `ads_metrics` 만 | 최소 조회 · 볼륨 사전 검증 |
| `ads_info` | **1**| `ads_metrics` + `monthly_volume` | 시즌성만 필요 시 |
| `all` | **10**| `ads_metrics` + `monthly_volume` + `features` + `intents` + `demography` | ** 이 스킬 기본** · 인텐트·인구·시계열이 필요한 분석은 `all` 사용 (최대 정보 확보) |

**크레딧 안내** (data_type=all 기준):
- 1개 조회 → 10 크레딧
- 100개 조회 → 1,000 크레딧
- 1000개 조회 (최대) → 10,000 크레딧
- (`ads_metrics`/`ads_info`는 동일 건수에 1/10 비용)


## 응답 · data_type=all 전체 구조

```json
{
 "data": [
 {
 "keyword": "전기자전거",
 "ads_metrics": {
 "competition": "HIGH",
 "competition_index": 100,
 "cpc": 0.4,
 "low_bid_micros": 62004,
 "high_bid_micros": 702350,
 "volume_avg": 245333,
 "volume_total": 2567300,
 "volume_trend": -0.3,
 "gg_volume_avg": 56833,
 "gg_volume_total": 628800,
 "gg_volume_trend": -0.33,
 "nv_volume_avg": 188500,
 "nv_volume_total": 1938500,
 "nv_volume_trend": -0.3
 },
 "features": {
 "f_ai_overview": 1,
 "f_organic_results": 17,
 "f_ads_top": 0,
 "f_ads_bottom": 0,
 "f_featured_snippet": 0,
 "f_people_also_ask_for": 1,
 "f_people_also_search_for": 1,
 "f_related_searches": 1,
 "f_images": 2,
 "f_video_results": 1,
 "f_knowledge_panel": 0,
 "f_local_results": 1
 },
 "intents": {
 "i": 1,
 "n": 0,
 "c": 0,
 "t": 1
 },
 "demography": {
 "m_m_gender_ratio": 1,
 "m_f_gender_ratio": 0,
 "m_gender_ratio": 72.88,
 "f_gender_ratio": 27.11,
 "a0_ratio": 0.13,
 "a13_ratio": 2.27,
 "a20_ratio": 4.27,
 "a25_ratio": 8.27,
 "a30_ratio": 27.15,
 "a40_ratio": 31.69,
 "a50_ratio": 26.19,
 "m_avg_volume": 161541.66
 },
 "monthly_volume": [
 { "month": "2022-08", "gg": 60500, "nv": 298400, "total": 358900 },
 { "month": "2026-07", "gg": 49500, "nv": 166800, "total": 216300 }
 ]
 }
 ]
}
```

## 필드별 해석 가이드

### ads_metrics (검색량·광고)

| 필드 | 의미 | 사용자 질문 매핑 |
|---|---|---|
| `volume_avg` | 월평균 검색량 | "이 키워드 얼마나 검색되나?" |
| `volume_total` | 누적 검색량 | "연간 총 검색량은?" |
| `volume_trend` | 기간 대비 증감률 (-1~∞) | "성장 중인가?" · +30%↑ 급성장 · -50%↓ 급락 |
| `gg_volume_avg` | 구글만 월평균 (한국은 낮음) | "구글에서 얼마나?" |
| `nv_volume_avg` | 네이버만 월평균 (한국 강세) | "네이버에서 얼마나?" |

> 집계 기간은 공식 미공표 — 기간 의존 해석 시 실측 대조 권장.
| `cpc` | 클릭당 광고 비용 (USD) | "광고 단가는?" |
| `competition_index` | 광고 경쟁도 (0~100) | "광고 경쟁 심한가?" · 100 가까울수록 상업 가치 큼 |
| `competition` | HIGH/MEDIUM/LOW | 등급 표현 |
| `low_bid_micros`·`high_bid_micros` | 최저·최고 입찰가 (마이크로) | 광고 예산 계획 |

### features (SERP 화면 구조 · 24개 · 공식 확인 2026-07-14)

**AI·광고**| 필드 | 의미 |
|---|---|
| `f_ai_overview` | AI Overview (1/0) · 있으면 CTR 하락 위험 |
| `f_ads_top` | 상단 광고 수 |
| `f_ads_bottom` | 하단 광고 수 | **Organic**| 필드 | 의미 |
|---|---|
| `f_organic_results` | 일반 웹결과 수 |
| `f_organic_results_rating` | 리뷰·평점 있는 결과 수 |
| `f_organic_results_video` | 동영상 포함 결과 수 | **Featured Snippet · 세분화**| 필드 | 의미 |
|---|---|
| `f_featured_snippet` | Featured Snippet 존재 (1/0) |
| `f_featured_snippet_ordered_list` | 번호 리스트 형태 (1/0) |
| `f_featured_snippet_unordered_list` | 불릿 리스트 형태 (1/0) |
| `f_featured_snippet_table` | 표 형태 (1/0) |
| `f_featured_snippet_video_exist` | 동영상 포함 (1/0) | **People Also (질문·검색)**| 필드 | 의미 |
|---|---|
| `f_people_also_ask_for` | PAA 박스 수 |
| `f_people_also_search_for` | 관련 검색 수 |
| `f_related_searches` | 관련 검색어 수 |
| `f_spell_check` | 철자 확인 (1/0) | **미디어·플랫폼**| 필드 | 의미 |
|---|---|
| `f_images` | 이미지 결과 수 |
| `f_video_results` | 동영상 결과 수 |
| `f_video_carousels` | 동영상 캐러셀 수 |
| `f_articles` | 뉴스·아티클 수 |
| `f_sns` | SNS 결과 수 | **Knowledge·앱·로컬**| 필드 | 의미 |
|---|---|
| `f_knowledge_panel` | 지식 패널 (1/0) |
| `f_sitelinks` | 사이트링크 (1/0) |
| `f_local_results` | 지도/로컬 결과 수 |
| `f_google_play` | 구글 플레이 결과 (1/0) |
| `f_app_results` | 앱 결과 수 |

### intents (검색 의도 4개 · 합 = 1.0 ± 0.05)

| 필드 | 의미 | 예 |
|---|---|---|
| `i` Informational | 정보 찾는 중 | "전기자전거 면허" |
| `n` Navigational | 특정 사이트 가려고 | "삼천리자전거" |
| `c` Commercial | 살까 말까 비교 | "전기자전거 추천" |
| `t` Transactional | 진짜 살거 | "전기자전거 최저가" | **해석**:
- `t` 높음 → 구매 직결 · 광고 가치 큼
- `i` 높음 → 인지 단계 · 콘텐츠 마케팅 대상
- `c` 높음 → 비교 검토 · 리뷰·비교 콘텐츠

### demography (성별·연령 · 유의미 여부 + 비율)

**gl=kr 전용** — us/jp는 demography 미반환 (데이터 사양).

| 필드 | 의미 |
|---|---|
| `m_gender`·`f_gender` | 남/녀 유의미 여부 (1/0) |
| `m_gender_ratio`·`f_gender_ratio` | 남/녀 비율 (%) |
| `a0`·`a13`·`a20`·`a25`·`a30`·`a40`·`a50` | 각 연령대 유의미 (1/0) |
| `a20_ratio` 등 | 각 연령대 비율 (%) | **해석**:
- 특정 성별·연령이 지배적 → 페르소나 명확
- 여러 세그먼트 균형 → 대중 시장

### monthly_volume (48개월 시계열)

- 배열 · 과거 → 최신 순 (오름차순 · 실측 확인). 그래도 코드는 배열 위치가 아니라 `month` 최댓값으로 기준월을 읽는다
- 각 항목 · `{ month, gg, nv, total }`
- 시즌성 분석 필수 · 매년 같은 달 비교

## 사용자 질문 유형별 대응

### 유형 1 · "이 키워드 정보 알려줘"
→ keyword_info(all) 호출 · 상위 요약 답변
- volume · 트렌드 · 성별·연령 · SERP 특성 · 의도 mix

### 유형 2 · "왜 이 노드가 크지?"
→ 클러스터 그래프의 노드 클릭 상황 · 즉시 keyword_info(all)
→ volume_avg 강조 + 트렌드·의도로 맥락 설명

### 유형 3 · "이 키워드 트렌드는?"
→ volume_trend + monthly_volume 12~24개월 시계열 노출
→ 급성장/안정/하락 판단

### 유형 4 · "누가 검색하지?"
→ demography 필드 · 성별·연령 비율 노출
→ 페르소나 추정

### 유형 5 · "SEO 진입 가능성?"
→ features + competition_index + cpc 조합
→ AI Overview·Featured Snippet 유무 · 광고 경쟁·유기적 여지

### 유형 6 · "여러 키워드 비교"
→ keyword_info(all) 배치 · 각 필드별 비교 표

## 표기 정규화 (2026-08-29 실측)

응답의 `keyword`는 **요청 표기가 아니라 API 정규화 표기**로 돌아온다: 대문자→소문자(`MLB`→`mlb`),
붙임/띄어쓰기 재조정(`여름코디`→`여름 코디`). 요청 112건에 응답 130건(변형 포함)이 온 사례도 있다.
→ 요청 키워드로 exact-match 인덱싱하면 정상 응답을 무응답으로 오판한다(112건 중 28건 오판 실측).
**공백 제거+casefold로 양쪽을 정규화해 매칭**하라. 무응답 판정은 그 후에만 유효하다.
CEP Finder 엔진은 `join_by_request()`로 이 재매칭을 전 단계에 적용하고 재매칭 건을 `run_manifest.keyword_rematch`에 남긴다.

## 크레딧 관리

- 사용자 요청 시 <b>사전 안내</b>: "N개 × 10 = M 크레딧 소비 예정 · 진행할까요?"
- 저비용 확인만 필요 시 · `ads_metrics`로 스크리닝 후 · 필요한 것만 `all`
- 배치는 <b>최대 1000개</b> · 초과 시 분할 필요

## 실전 발견 (2026-08-22 · 전기자전거 KR)

**표기·오타 변형은 별도 키워드로 독립 볼륨을 갖는다**:
- 오타 변형 `전기 자건거`가 헤드텀과 별개로 57,363/월 반환 (헤드텀 245,333의 약 23%)
- 동의어 `전동자전거`도 별도 키워드 (11,240/월)
- → 총량 산출 시 변형 합산 여부와 근거를 준비도 배너에 명시 (동의어군은 볼륨 dedup 후 합산)

## 표기 변형 합산 시 구글 중복

품목어 표기 변형의 검색량을 원형과 더할 때, 변형의 `gg_volume_avg`가 원형과 **같으면** 구글이 비슷한 표기를 한 묶음으로 센 값이다 —
네이버(`nv_volume_avg`)만 더한다.

## 요청하지 않은 표기 변형 행

응답 `data`에는 입력하지 않은 오타·표기 변형 행이 섞여 올 수 있다. 변형 행은 원형과 검색량이 같아서 더하면 중복이다.
입력 검색어와 띄어쓰기·대소문자 무시로 일치하는 행만 쓰고 나머지는 버린다. 같은 검색어가 두 행으로 오면 한 번만 쓴다.
