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

## 단건 월별 검색량 · `POST /keyword_info/monthly_volume`

키워드 **1개**의 `monthly_volume`만 돌려주는 경량 엔드포인트. 운영 명세 **v1.0.15**부터 지원한다. 분석 파이프라인은 아래 배치 경로를 쓴다.
**DaaS(data) 키 전용**. 래퍼 `keyword_info.fetch_monthly_volume(client, keyword, gl=…)`.

| 파라미터 | 필수 | 설명 |
|---|---|---|
| `keyword` | ✅ | 키워드 1개 (문자열 · 배열 아님) |
| `gl` | ✅ | `kr` · `jp` · `us` |
| `user_query` · `response_format` · `is_skills` · `skill_desc` | — | 공통 파라미터 ([[references/daas-api-overview.md]]) |

- 응답 `data` = `[{keyword, monthly_volume: [{month, gg, nv, total}, …]}]` — 명세 설명상 `/keyword_info` 응답의 같은 항목과 **값이 동일**.
  색인에 없거나 월별 검색량이 없으면 빈 리스트. 네이버 검색량 미수집 월은 `nv_code: 1`
- 크레딧 · **input 1 / output 0** (명세 기본값 · 2026-11-04 1건 실측 total_cost 1 · 그 호출은 48개월 반환)
- 언제 쓰나 · 시계열 하나만 빠르게 볼 때. 키워드가 여럿이면 `keyword_info(data_type="ads_info")` 배치(1/kw · 최대 1,000개 · `ads_metrics`까지 포함)가
  같은 단가로 한 번에 받으므로 그쪽을 쓴다

```bash
curl -X POST "https://listeningmind-data-api.ascentlab.io/keyword_info/monthly_volume" \
 -H "Content-Type: application/json" \
 -H "LM-API-KEY: $API_KEY" \
 -d '{"keyword": "냉장고", "gl": "kr", "is_skills": true}'
```

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
| `volume_trend` | 최신 월 ÷ 3개월 전 월 − 1 (소수 둘째 자리 **버림**, -1~∞) | "최근 석 달 사이 움직였나?" — 한 달 대 한 달 비교라 시즌·일시 급등에 크게 흔들린다. 판정은 `monthly_volume` 전년 동기로 |
| `gg_volume_avg` | 구글만 월평균 (한국은 낮음) | "구글에서 얼마나?" |
| `nv_volume_avg` | 네이버만 월평균 (한국 강세) | "네이버에서 얼마나?" |

> 집계 기간(공개 문서 'ListeningMind Data API 기술 자료' 응답 필드 정의 · 2026-10-19 실측 대조): `volume_avg` = 최근 3개월 월별 검색량 평균 · `volume_total` = 최근 12개월 합 · `volume_trend` = 3개월 전 대비 최근 월 증감률(비율값, 0.19 = +19%). 실측 '검색 데이터 분석'(kr): 7~9월 28·30·27 → avg 28, 6월 10 → trend (27−10)/10 = 1.7 — 응답값과 일치. `gg_`·`nv_` 접두 필드도 같은 기간.
> **관측된 일치(2026-10-25 운영 응답 1건 · 키워드 4개 × 합계·구글·네이버 = 12값, 선크림·썬크림 구글 계열이 같아 독립 11값)** — 정의로 확정하지 않는다: `trunc((M[최신] − M[최신−3]) / M[최신−3], 2)` — `M`은 `monthly_volume` 의 같은 채널 값, 끝자리는 반올림이 아니라 **버림**(예: −0.0973 → −0.09, −0.4482 → −0.44). 반올림으로 대조하면 어긋난다. 다른 표본에서는 일치하는 식을 찾지 못한 기록이 있고 원인은 미확인이다(버림·반올림 차이, 마지막 달 정정 시점 차이 가능성). 표본을 넓혀 다시 대조하기 전까지 판정 근거로 쓰지 않는다는 원칙을 유지한다(한 달 대 한 달 비교라 변동도 크다). 같은 응답에서 `volume_avg`(최근 3개월 평균, 소수점 버림)·`volume_total`(최근 12개월 합)도 12값 모두 일치했다. 키워드 3개를 요청했는데 4행이 왔다(표기 변형 '썬크림' 추가 ).
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

### intents (검색 의도 4개 · **0/1 플래그** · 동시에 여러 개가 1일 수 있다 — 비율이 아니다)

| 필드 | 의미 | 예 |
|---|---|---|
| `i` Informational | 정보 찾는 중 | "전기자전거 면허" |
| `n` Navigational | 특정 사이트 가려고 | "삼천리자전거" |
| `c` Commercial | 살까 말까 비교 | "전기자전거 추천" |
| `t` Transactional | 진짜 살거 | "전기자전거 최저가" | **해석**:
- `t` = 1 → 구매 직결 · 광고 가치 큼
- `i` = 1 → 인지 단계 · 콘텐츠 마케팅 대상
- `c` = 1 → 비교 검토 · 리뷰·비교 콘텐츠
- 2026-10-25 운영 응답 4행 모두 정수 0/1이었고 두 개가 동시에 1인 행이 2개였다(예: i·t). 키워드 묶음의 의도 구성을 그릴 때는 '플래그가 1인 키워드 수'를 의도마다 세고, 합 100% 차트(도넛·100% 막대)로 그리지 않는다

### demography (성별·연령 · 유의미 여부 + 비율)

**gl=kr 전용** — us/jp는 demography 미반환 (데이터 사양).

| 필드 | 의미 |
|---|---|
| `m_m_gender_ratio`·`m_f_gender_ratio` | 남/녀 유의미 여부 (1/0) — 유의 플래그는 이 2개와 `m_a0`~`m_a50` 7개, **모두 9개뿐**이다. `m_`로 시작한다고 플래그가 아니다(`m_gender_ratio`는 비율, `m_avg_volume`은 실수) |
| `m_gender_ratio`·`f_gender_ratio` | 남/녀 비율 (%) |
| `m_a0`·`m_a13`·`m_a20`·`m_a25`·`m_a30`·`m_a40`·`m_a50` | 각 연령대 유의미 (1/0) |
| `a0_ratio`~`a50_ratio` | 각 연령대 비율 (%) |
| `m_avg_volume` | 의미 미확인(정본에 정의 없음) — 쓰지 않는다 |

> 키 이름은 2026-10-25 운영 응답 4행과 저장본(2026-08~09)에서 확인했다. 옛 판 문서의 `m_gender`·`a20` 같은 플래그 키는 응답에 없다.

연령 코드 범위(공개 문서 '키워드 조회 API 활용 가이드' · 2026-10-20 대조): a0 12세 이하 · a13 13~19세 · a20 20~24세 · a25 25~29세 · a30 30~39세 · a40 40~49세 · a50 50세 이상.
플래그 판정(같은 가이드): 표준편차(1시그마) 이상으로 해당 집단의 검색 비중이 높으면 1 — 여러 집단이 동시에 1일 수 있다(위 예시: 남·녀 모두 1).
`demography`의 집계 기간은 명세·가이드에 정의돼 있지 않다 — volume_avg(최근 3개월)로 가중하는 합산은 두 기간이 비슷하다는 [가정]이다.
**해석**:
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

적용 조건: 구글 값이 같다는 것은 **중복 의심 신호**이고, 아래가 모두 맞을 때만 중복으로 확정한다.
① 두 표기가 같은 품목어·브랜드명의 표기 변형이다(오타·띄어쓰기·외래어 표기 — 동의어 '노트북·랩탑'은 해당하지 않는다)
② 같은 조합(같은 수식어 '… 추천')끼리 비교한다 ③ 구글 값이 정확히 같다(근사치는 해당 없음).
확정한 쌍과 뺀 검색량은 결과와 함께 기록한다.

## 요청하지 않은 표기 변형 행

응답 `data`에는 입력하지 않은 오타·표기 변형 행이 섞여 올 수 있다. 변형 행은 원형과 검색량이 같아서 더하면 중복이다.
입력 검색어와 띄어쓰기·대소문자 무시로 일치하는 행만 쓰고 나머지는 버린다. 같은 검색어가 두 행으로 오면 한 번만 쓴다.
