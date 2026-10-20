# trend_finder API · 완전 참조

**엔드포인트**: `POST /trend_finder/issue_list`
**목적**: 시드 키워드 주변에서 최근 급부상한 이슈 항목(요약·핵심 구문·출처 링크·토픽·이슈 점수) 조회
**래퍼**: `api/trend_finder.py` · `fetch()` · `widen()` + 파싱 헬퍼 5종
**검증**: 운영 OpenAPI v1.0.13 파라미터 대조(2026-10-13) + 실측 응답 1건 (gl=kr · 로봇청소기 · period_days=14 · limit=3 · 2026-09-23)
**추가일**: 2026-09-23

## 요청 표준

> 엔드포인트 주소는 `LM_API_BASE` → `00_Context/.lm-api-base` 순으로 해석한다
> 상세: [[references/daas-api-overview.md]]

```bash
curl -X POST "${LM_API_BASE}/trend_finder/issue_list" \
 -H "Content-Type: application/json" \
 -H "LM-API-KEY: $API_KEY" \
 -d '{"keyword": "로봇청소기", "gl": "kr", "period_days": 14, "limit": 50, "sort": "score", "order": "desc"}'
```

## 언제 호출하나

`keyword_info` 는 검색량이 **얼마나** 움직였는지를, `intent_finder`·`cluster_finder` 는 **어떤 말**들이 붙어
있는지를 준다. 이 엔드포인트는 그 키워드 주변에서 **지금 무슨 일이 일어나는지**를 내용 근거(요약문·출처 링크)와
함께 준다 — 검색량 급등의 원인 확인, 브랜드·제품 키워드의 최근 이슈 모니터링, 단발 스파이크인지 지속 트렌드인지
판정(기간을 늘려 재조회), 콘텐츠 기회의 소재 확인.

호출이 정당한 경우 · 수요·트렌드 잡(J1)에서 급등 원인을 설명해야 할 때 · 라이징 워치·시즌 이슈 확인 ·
CEP 허브의 "왜 지금" 근거 보강. 검색량 수치만 필요하면 부르지 않는다.

**실시간 크롤이 아니다.** 2025-05-26 부터 쌓인 일별 이슈 인덱스를 검색한다. **빈 결과는 오류가 아니라
실측**("그 기간에 매칭된 이슈 없음")이다 — 기간을 14 → 90 → 365 로 넓혀 한 번 더 본 뒤 결론을 내리고,
이슈를 지어내지 않는다.

## 파라미터

| 파라미터 | 타입 | 기본 | 설명 |
|---|---|---|---|
| `keyword` | 문자열 | (필수) | **단일 시드 키워드**. 배열이 아니다. 영문은 소문자로 |
| `gl` | 문자열 | (필수) | `kr` · `jp` · `us` — 국가별 인덱스라 다국가는 나눠 부른다 |
| `period_days` | 정수 | 14 | 최신 N일의 이슈 인덱스 검색 · 1~365 |
| `limit` | 정수 | 1000 | 반환 이슈 항목 수 · 최대 10,000 · **출력 과금 2/건** — 래퍼 기본 50 |
| `sort` | 문자열 | `score` | `score`(이슈 점수) · `date`(기록일) |
| `order` | 문자열 | `desc` | `desc` · `asc` |
| `content_type` | 문자열/null | null | 최상단 콘텐츠 유형 필터 `news` · `video` · `web` · 미지정 시 전체 |
| `user_query` | 문자열/null | null | 이 호출을 유발한 사용자 질의 원문 (LLM 경유 호출용 · 이력에 적재) |
| `response_format` | 문자열 | `json` | `json` · `download_url` (대용량 — `download` 메타만 받고 파일로 내려받는다 · `client.download()`) |

## 응답 구조 (실측)

```json
{
  "result": "OK", "reason": "SUCCESS", "user_type": "data",
  "request_detail": {"keyword": "로봇청소기", "gl": "kr", "period_days": 14, "limit": 3, "sort": "score", "order": "desc", "response_format": "json"},
  "cost_detail": {"input_cost": 50, "input_count": 1, "input_total_cost": 50,
                  "output_cost": 2, "output_count": 3, "output_total_cost": 6, "total_cost": 56},
  "used_credits": 1234567,
  "total": 7,
  "data": [
    {"keyword": "드리미 x60", "issue_score": 5.5857, "content_type": "web", "topic": null, "category": null,
     "freshness": 0.0,
     "summary": ["드리미 X60 시리즈는 최고의 청소 성능을 자랑합니다.", "X60 Ultra 모델은 …", "…"],
     "key_phrase": ["드리미", "x60", "ultra", "로봇청소기", "청소", "흡입력", "배터리", "구매", "혜택", "리뷰"],
     "source_links": ["https://kr.dreametech.com/promotion/x60_series", "https://prod.danawa.com/info/?pcode=107992037", "…"],
     "recorded_at": "…", "index_date": "…"},
    {"keyword": "로보락 s10", "issue_score": 5.2789, "content_type": "web", "topic": "로보락", "category": null, "…": "…"}
  ]
}
```

**`total` 은 과금과 무관하게 매칭된 이슈 전체 수**다 — 먼저 작은 `limit` 으로 규모를 본 뒤 필요한 만큼만 늘린다.

### 항목 필드

| 필드 | 뜻 |
|---|---|
| `keyword` | 이슈 키워드 (시드가 아니라 급부상한 연관 표현 — 모델명·브랜드 결합형이 많다) |
| `issue_score` | 이슈 점수 (관련성·영향 · sort=score 기준) |
| `content_type` | 최상단 콘텐츠 유형 · news / video / web |
| `topic` · `category` | 이슈 토픽·카테고리 (null 가능 — 실측 3건 중 topic 1건만 채워짐) |
| `freshness` | 검색결과 발행일 기반 신선도 지표 (실측 3건 모두 0.0 — 해석 기준은 미확인, 단정하지 않는다) |
| `summary` | 구글 SERP 의 AI 생성 요약 문장 배열 |
| `key_phrase` | 핵심 구문 배열 |
| `source_links` | 근거 출처 URL 배열 (원문 검증에 쓴다 — 실측 항목당 10개 안팎) |
| `recorded_at` · `index_date` | 기록 시각 · 어느 일별 인덱스에서 왔는지 |

## 크레딧

```
total_cost = 50 (시드 키워드당 · 입력) + 2 × 반환 이슈 항목 수 (출력)     # 2026-09-23 실측 · limit=3 → 56
```

- 시드 1개 · limit 50 상한 견적 = 50 + 100 = 150 (실제는 매칭 수만큼만)
- **빈 결과 호출은 과금 0이었다** (2026-09-29 실측: `캠핑체어` period_days=14 → total 0 · input_count 0 · total_cost 0).
  그러니 `widen()` 으로 기간을 넓힐 때 과금되는 것은 결과가 나온 호출뿐이다 — 견적 상한은 여전히 호출마다 `50 + 2 × limit`
- 띄어쓴 여러 단어 시드는 단어 중 하나만 맞아도 이슈를 가져온다(같은 날 실측: «캠핑 의자» total 147 · 반환 50 중 의자 1건 ·
  «캠핑의자» total 1). 결과 건수가 아니라 범위 밖을 거른 뒤의 건수로 판단한다
- 견적은 `api/trend_finder.estimate(limit, seeds)` · 실소비는 응답 `cost_detail.total_cost` 가 유일 기준

## 시드 고르기 — 구별 토큰 + 품목 사후 필터

급등 키워드의 원인을 물을 때 그 키워드를 통째로 시드로 넣지 않는다. 여러 단어 시드는 단어 하나만 맞아도 이슈를 가져와서
흔한 단어('규정'·'전기자전거') 쪽 이슈가 상위를 채운다. **급등을 만든 구별 토큰 하나(인물·모델·정책명)를 붙여 쓴 형태로** 부르고,
반환 항목 중 품목 anchor 어휘가 `keyword`·`summary`·`key_phrase`에 함께 나오는 것만 근거로 쓴다.

2026-09-30 전기자전거 수요 파일럿(period_days=90 · limit 10 · 4회 210크레딧):

| 시드 | total | 상위 10건 중 시드 단어 전부 포함 | 원인 이슈 |
|---|---|---|---|
| 서경석 전기자전거 | 168 | 0 | 없음 — 일반 전기자전거·게임 대회 이슈 |
| 전기자전거 헬멧 규정 | 743 | 0 | 없음 — 축구 구단 재정 규정 위반 등 |
| 서경석 | 13 | 품목 anchor 필터 후 1 | "방송인 서경석이 비아지오 전기자전거 광고 모델로 활동" (index 2026-09-13) |
| 전기자전거헬멧 | 0 (과금 0) | — | 인덱스에 없음 — 기간을 넓히거나 구별 토큰('헬멧 의무화')으로 다시 |

같은 날 `collect_demand.py explain`으로 라이징 5개를 더 봤다(90일 · limit 20):

| 라이징 키워드 | 구별 토큰 | 매칭 | 판정 |
|---|---|---|---|
| 모토벨로 fn10 | fn10 | 4 | 원인 이슈 있음 — 신모델 소개 |
| 서경석 전기자전거 | 서경석 | 13 | 원인 이슈 있음 — 비아지오 광고 모델 |
| 전현무 전기자전거 | 전현무 | 591 | 무관 이슈만 |
| 몬테 리아 전기자전거 | 몬테리아 | 593,793 | 매칭 과다 · 판정 보류 |
| 그라인드 전기자전거 | 그라인드 | 1 | 무관 이슈만 |

원인이 잡힌 것은 매칭이 적은 드문 토큰(4·13건)뿐이었다. 키워드 전체를 붙여 쓴 재조회(365일)도 1.9만~5.1만 건으로
넓게 매칭돼 상위 20건에 관련 이슈가 없었다 — 재조회는 기본으로 하지 않는다. 매칭이 1,000건을 넘으면 '없다'고 쓰지 않고 판정 보류로 둔다.

## 오류 코드

`cluster_finder`와 동일 체계 · 401(키) · 402(크레딧 부족) · 403(권한) · 422(파라미터 — `keyword` 는 단일 문자열,
`period_days` 1~365, `limit` 1~10,000, `content_type` 는 세 값 중 하나) · 429(rate limit) · 500(서버).

## Python 사용

```python
from api.client import DaasClient
from api import trend_finder

c = DaasClient(api_key=API_KEY)
r = trend_finder.fetch(c, "로봇청소기", gl="kr", period_days=14, limit=50)
r["total"], trend_finder.cost(r)          # 매칭 전체 수 · 실소비 크레딧
trend_finder.brief(r, n=10)               # 리포트용 축약 [{keyword, issue_score, content_type, topic, summary, sources, index_date}]
trend_finder.by_topic(r)                  # topic 별 묶음
trend_finder.sources(r, max_per_item=2)   # (이슈 키워드, 출처 URL) 평탄화 — 인용용

r, tried = trend_finder.widen(c, "온다 리프팅", gl="kr")   # 14 → 90 → 365 일, 처음 비지 않은 응답에서 멈춤
```

## 해석 규율

- 이슈 인덱스는 **구글** 자동완성·SERP 기반이다. 네이버 비중이 큰 카테고리에서는 "국내 이슈 전체"로 단정하지
  않고 `keyword_info.ads_metrics` 의 gg/nv 비율과 함께 서술한다.
- `summary` 는 AI 생성 요약이다 — 리포트에 옮길 때는 **출처 링크를 열어 확인한 문장만** 실측으로 라벨하고,
  요약문 자체는 파생으로 표기한다.
- 같은 이슈 키워드가 여러 인덱스 날짜에 반복될 수 있다. 지속 여부는 `index_date` 분포로 본다.
- 급등의 **원인** 설명에는 쓰되, 검색량 수치는 `keyword_info` 에서 가져온다 — 이 응답에 검색량은 없다.
- 이슈 키워드(`data[].keyword`)의 AIO 원문이 필요하면 유니크 목록으로 만들어 `serp` 로 수집한다 — [[references/serp-api.md]] '연관 키워드 묶음의 AIO 수집'.
