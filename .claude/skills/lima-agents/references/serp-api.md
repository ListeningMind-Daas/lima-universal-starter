# serp API · 완전 참조

**엔드포인트**: `POST /serp`
**목적**: 키워드의 검색결과 화면(SERP)을 블록 단위로 조회
**래퍼**: `api/serp.py` · `fetch()` + 파싱 헬퍼 7종
**검증**: OpenAPI v1.0.29 파라미터 대조(2026-11-27) + 실측 응답 (gl=kr · num=10 · 2026-08-25 전기자전거)

> ⚠️ **단가 주의** — 저장본 `/serp` 는 **10 / 키워드**다(운영 명세 v1.0.29 · 2026-11-27 확인).
> 이력: 2026-08-19 10 → 2026-08-28 30 으로 인상 → 2026-11-27 운영 v1.0.29 에서 다시 10. 아래 예시 응답의 `total_cost: 10` 은 2026-08-19 스냅샷이다.
> 같은 판에 실시간 수집 `/serp/live`(30 / 키워드)가 들어왔다(아래 절). 견적 숫자는 문서가 아니라 `api/spec.py` 가 고정 명세에서 읽는다.
> 2026-08-19 이후 명세에서 응답에 `collected_at`(SERP 스냅샷 수집 시각·UTC)이 추가됐고, 요청에 `user_query`·`response_format` 이 생겼다
> ([[references/daas-api-overview.md]] 공통 파라미터). 최신 단가는 공개 API 문서 https://listeningmind-data-api.ascentlab.io/ 를 대조한다.

## 요청 표준

```bash
curl -X POST "https://listeningmind-data-api.ascentlab.io/serp" \
 -H "Content-Type: application/json" \
 -H "LM-API-KEY: $API_KEY" \
 -d '{"keyword": "전기자전거", "gl": "kr", "num": 20, "device": "mobile"}'
```

## 언제 호출하나

`keyword_info(data_type=all)`의 `features`는 **어떤 블록이 몇 개 있는지**(f_ai_overview·f_ads_top 등 24개)만
알려준다. 그 이상 — 실제 노출된 제목·URL·스니펫, 연관 질문 문구, AI 개요 본문 — 이 필요할 때만 `/serp`을 쓴다.

호출이 정당한 경우 · SEO 진입 가능성 판단(누가 상위에 있나) · 콘텐츠 기회 발굴(PAA 질문 문구) ·
AI Overview 노출 내용 확인 · 경쟁사 SERP 장악력 점검.

**시계열 비교에는 쓸 수 없다.** 반환값은 실시간 크롤이 아니라 **저장된 스냅샷**이다(OpenAPI v1.0.15 설명). 그 시점은 요청 시각(`request_at`)이 아니라 **`collected_at`**(스냅샷 수집 시각·UTC)이다. 차트·리포트에는 `collected_at` 을 적고 "현재 검색결과"로 서술하지 않는다. 시점 비교가 필요하면
`keyword_info`의 `features`(월 그레인)를 쓴다.

## 스냅샷 신선도

**실측** (2026-11-02 · v1.0.15 · mobile · num=20). 표본은 일반적인 키워드 40개념 × 3개국 + 미국 긴 키워드 30건이다.

| 표본 | 데이터 있음 | 나이 중앙값 | 최소~최대 | 1년 초과 |
|---|---|---|---|---|
| kr 40 | 40 | 30.5일 | 4.6~519.5일 | 3 |
| us 40 | 40 | 16.0일 | 0.7~663.2일 | 1 |
| jp 40 | 40 | 31.4일 | 5.2~643.3일 | 8 |
| us 긴 키워드 30 | 22 | 77.7일 | 4.8~654.2일 | 5 |

나이와 빈 응답 비율은 표본에 따라 달라질 수 있다. 시장별 대표값으로 쓰지 말고 **호출한 키워드마다 나이를 계산**한다.

- **빈 응답** · 스냅샷이 없으면 `200 OK` + `data: []` + `collected_at: null` + **0크레딧**이다. "검색결과 없음"이나 "AIO 미노출"이 아니라 데이터 공백이다.
- **호출이 수집을 유발하는가** · 약 11분 뒤 재호출한 빈 응답 8건은 그대로 비어 있었다. 더 긴 간격은 미확인이다.
- **처음 부른 키워드** · 자체 호출 기록에 없는 키워드 30건 중 24시간 이내 스냅샷은 0건이었다(계정 전체 이력은 미조회).
- **재호출** · 10분 간격 20쌍과 1.35일 이내 저장본 24쌍은 `collected_at` 과 데이터가 모두 같았다.
- **갱신 주기는 미확인** · 스냅샷이 바뀐 것으로 관측된 간격 4건이 33~34일이었다. 4건뿐이라 주기로 쓰지 않는다.
- **한계** · 이 절의 수치는 운영 서버에서 다시 재지 않았다. 저장 스냅샷이라는 설명은 운영 OpenAPI 에 있다.

## 연관 키워드 묶음의 AIO 수집 (2026-09-23 · 2026-10-13 갱신)

전용 엔드포인트 `/ai_overview/analyze` 는 2026-10-13 운영 API(v1.0.13)에서 삭제됐다.
"연관 키워드 묶음의 AIO 원문"이 필요하면 **확장 → 유니크 목록 → serp** 세 단계로 모은다.

**① 키워드 확장** — 목적에 맞는 원천을 고른다 (여럿을 섞어도 된다).

| 원천 | 엔드포인트 | 무엇을 모으나 | 크레딧 |
|---|---|---|---|
| 인텐트 확장 | `intent_finder/keyword_list` | 검색량 임계값 이상 연관어 | 30 + 반환×2 |
| 관계망 확장 | `cluster_finder/keyword_list` | 동시검색 관계망의 키워드 | 30 + 반환×2 |
| 여정 확장 | `path_finder/keyword_list` | 검색 여정에 등장한 키워드 | 30 + 반환×2 |
| 이슈 확장 | `trend_finder/issue_list` | 최근 급부상 이슈 키워드 (`data[].keyword`) | 50 + 반환×2 |

**② 유니크 목록** — 원천별 결과를 합쳐 공백·대소문자를 정규화하고 중복을 제거한다. 원천(어느 API에서 왔나)을
키워드마다 남긴다. 키워드 수가 곧 serp 비용이므로 여기서 대상을 줄인다:
검색량이 필요하면 `keyword_info(ads_metrics)`(1/kw)로 확인해 임계값 미만을 빼고 검색량 내림차순 상위 N만 남긴다.

**③ serp 수집** — 목록의 키워드마다 `serp.fetch()` → `serp.ai_overview_snippets()` 로 AIO 본문을 뽑는다.
`data` 가 있는데 AIO 본문이 빈 리스트면 "그 스냅샷에서 AIO 미노출"이고(오류 아님), `data: []` 면 미노출이 아니라 데이터 공백이다. 블록 단위 인용 출처는 `ai_overview` 블록의 `references[]`(`title`·`url`·`source`·`origin_url`, 때로 `snippet`)에 있다 — `serp.ai_overview_references()`. `snippet_links`(`text`·`url`)는 블록 단위가 아니라 `text_blocks` 안 문장·목록 항목에 붙는 링크 조각이다 — 2026-08~09 저장본 200개 중 131개에 있었고 10-25 응답 2건에는 없었다.
응답의 `collected_at` 을 키워드별로 기록한다.
- **AIO 노출 비율** = AIO 가 나온 키워드 수 / `data` 가 있는 키워드 수 — 빈 응답 수는 따로 적는다
- `features=["ai_overview"]` 로 블록을 좁히는 요청은 **미실측**이다. 과금이 키워드당 정액이라 전체를 받아
  파싱해도 비용은 같다 — 기본은 전체 조회
- 동시 요청은 1 (429 방지)

**비용** = ① 확장 호출 합 + (② `ads_metrics` 를 쓰면 1 × 확장 키워드 수) + ③ serp 단가(10 · 운영 v1.0.29) × 최종 키워드 수(빈 응답은 0이라 상한이다).
예: intent_finder 1회(100개 반환) 230 + ads_metrics 100 + serp 상위 50개 500 = 830 (계산 예시 · 실소비는 각 응답 `cost_detail`).

**미리 거르기 판단** — `keyword_info(all)` 의 `f_ai_overview`(10/kw)로 노출 키워드만 골라 serp 를 부르는 것은
serp 가 10 이 된 뒤(2026-11-27 운영 v1.0.29)로는 비용으로 이득이 없다(10 + 10p ≥ 10 · 파생 계산 — 30 시절엔 p < 2/3 이면 크레딧이 적게 들었다).
`keyword_info(all)` 를 다른 이유로 이미 받았을 때만 그 값으로 거른다.
단, `f_ai_overview` 는 월 그레인이고 serp 는 `collected_at` 시점 스냅샷이라 둘이 어긋날 수 있다 — 거른 목록의 비율을 "전체 노출 비율"로 쓰지 않는다.

## 파라미터

| 파라미터 | 타입 | 기본 | 설명 |
|---|---|---|---|
| `keyword` | 문자열 | (필수) | **단일 키워드**. 배열이 아니다 |
| `gl` | 문자열 | (필수) | `kr` · `jp` · `us` |
| `num` | 정수 | 20 | **10 또는 20만 허용**. 응답·과금 모두 달라지지 않았다(2026-11-02 kr 40쌍) |
| `device` | 문자열 | `mobile` | `mobile` · `desktop` — 모바일/데스크톱 SERP는 블록 구성이 다르다 |
| `features` | 배열/문자열/null | null | 블록 유형 **최대 1개**(초과 시 422 · 단일 문자열도 허용). 생략·빈 리스트면 전체. 허용값 13종: `ai_overview` · `organic_results` · `people_also_search_for` · `related_searches` · `people_also_ask_for` · `video_results` · `short_videos` · `images` · `knowledge_panel` · `featured_snippet` · `sitelinks` · `app_results` · `top_stories` |

`num` 값은 래퍼가 화이트리스트로 검증한다 (`NUM_CHOICES`).

## 응답 구조 (실측)

```json
{
  "result": "OK",
  "reason": "SUCCESS",
  "request_detail": {"keyword": "전기자전거", "gl": "kr", "num": 10, "device": "mobile"},
  "cost_detail": {"input_cost": 10, "input_count": 1, "input_total_cost": 10,
                  "output_cost": 0, "output_count": 1, "output_total_cost": 0,
                  "total_cost": 10},
  "used_credits": 1234567,
  "data": [
    {"sequence": 1, "type": "organic_results", "position": 1,
     "site_name": "prod.danawa.com", "title": "전기자전거 : 다나와 가격비교", "url": "...", "snippet": "..."},
    {"sequence": 2, "type": "ai_overview", "text_blocks": [...]}
  ]
}
```

**`data`는 SERP 블록의 배열이며 화면 순서(`sequence`)를 따른다.** `organic_results`는
결과 1건마다 별도 블록으로 반복된다(`position` 보유).

### 블록 type (실측 확인 · `전기자전거` kr/mobile/num=10 · 2026-08-25 · `ai_overview` 행은 2026-10-25 재확인)

| type | 개수 | 주요 필드 |
|---|---|---|
| `organic_results` | 17 | `position` · `site_name` · `title` · `url` · `snippet` · `thumbnail` |
| `ai_overview` | 1 | `text_blocks[]` — `type: paragraph` 는 자기 `snippet`, `type: list` 는 `list[].snippet`(다시 `list[]` 가 중첩될 수 있음) · `references[]` · `ved` |
| `people_also_ask_for` | 1 | `items[].question` · `url` · `title` |
| `related_searches` | 1 | `items[].query` |
| `people_also_search_for` | 1 | `items[].query` |
| `local_results` | 1 | 지도·매장 |
| `video_results` | 1 | `items[]` |
| `images` | 2 | `grid` |

블록 구성은 키워드마다 다르다(예: `knowledge_panel`은 이 키워드에 없음). `num=10` 요청에
`organic_results`가 17개 반환됐다 — `num`은 자연결과 개수를 고정하지 않는다.
2026-11-02 kr 40쌍에서 `num=10`과 `num=20`의 `collected_at`·`data` 해시가 40/40 같았고 자연결과 수 중앙값은 둘 다 17이었다.
`num`으로 응답 크기를 줄일 수 있다고 가정하지 말고, 실제 개수는 응답에서 세어 확인한다.

## 크레딧

```
total_cost = 10 (키워드당 · 입력 과금만)   # API v1.0.29 기본값 · 2026-11-27 (2026-08-28~11-26 은 30)
```

`output_cost`는 0이라 반환 블록이 몇 개든 비용은 동일하다 — 단가 자체는 예측 가능하다.
스냅샷이 없어 `data: []` 인 응답은 **0크레딧**이다(2026-11-02 16회). 견적의 키워드당 단가는 상한으로 본다.
(2026-08-19 라이브 OpenAPI `SerpCost.input_cost=10` → 2026-08-28 실측 30 → 2026-11-27 v1.0.29 에서 다시 10. `num`은 과금에 영향이 없다 — 2026-11-02 kr 40건.)

## 오류 코드

`cluster_finder`와 동일 체계 · 401(키) · 402(크레딧 부족) · 403(권한) · 422(파라미터 —
`num`은 10·20만, `keyword`는 단일 문자열) · 429(rate limit) · 500(서버).

## Python 사용

```python
from api.client import DaasClient
from api import serp

c = DaasClient(api_key=API_KEY)
r = serp.fetch(c, "전기자전거", gl="kr", num=20)

serp.block_counts(r)          # {"organic_results": 17, "ai_overview": 1, ...}
serp.organic(r)               # [{position, site_name, title, url, snippet}, ...] · position 순
serp.related_queries(r)       # related_searches + people_also_search_for 통합·중복 제거
serp.questions(r)             # [{question, url, title}, ...] · People Also Ask
serp.ai_overview_snippets(r)  # AI 개요 본문(문단 + 목록 항목, 화면 순서) · 미노출 키워드는 빈 리스트
serp.ai_overview_references(r)  # AI 개요 인용 출처 [{title, url, source, origin_url}]
serp.blocks(r, "video_results")
```

## 해석 규율

SERP는 **구글 검색결과**다. 국내 분석에서 네이버 비중이 큰 카테고리라면 이 데이터만으로
"검색 노출 지형"을 단정하지 않는다 — `keyword_info.ads_metrics`의 `gg_volume_avg` /
`nv_volume_avg` 비율을 함께 보고 서술한다.


## 실시간 수집 `POST /serp/live` (운영 v1.0.29 · 2026-11-27 등록)

운영 명세 v1.0.29(2026-11-27)에서 공개됐다.

- **래퍼**: `api/serp.py` · `fetch_live(client, keyword, gl, num, features, timeout=300)` — 응답 형식이 `/serp` 와 같아 파싱 헬퍼를 그대로 쓴다
- **요청**: `keyword` · `gl`(kr·jp·us) 필수 · `num` 10·20 · `device` mobile 고정 · `features` 최대 1개 · `response_format`
- **응답**: `collected_at` 은 이번 요청의 수집 완료 시각(UTC)
- **비용**: 키워드당 30크레딧 · 출력 과금 없음 · 명세상 결과가 있을 때만 과금, 수집 실패(500)는 무과금
- **시간**: 명세는 수십 초~수 분, 타임아웃 5분 권장. 래퍼는 재시도하지 않는다(다시 부르면 수집·과금이 한 번 더)

실측 ("로봇청소기 추천" · gl=kr · num=20 · 2026-11-25 · 2건):

| 호출 | 응답 시간 | 블록 | 비용 |
|---|---|---|---|
| 전체 | 79초 (수집 완료는 요청 16초 뒤) | 23개 | 30 |
| `features=["ai_overview"]` | 68초 | 1개 | 30 |

- 필터는 응답에 담는 블록만 줄인다 — 비용·시간은 같았다
- 같은 키워드의 저장본(`/serp` · 수집 2026-11-03)과 최상위 필드·블록 구조가 같았다
- 3분 간격 두 호출의 AI 개요는 첫 문장의 추천 모델과 인용 수(11 → 10)가 달랐다 — 한 번의 결과를 고정값으로 쓰지 않는다
- 확인하지 않은 것: `response_format=download_url` · us·jp · AI 개요가 없는 키워드에 필터를 걸었을 때의 과금 · 수집 실패 시 무과금

같은 판(v1.0.29)에서 저장본 `/serp` 의 `input_cost` 기본값이 30 → 10 이 됐다(2026-11-27 명세 확인) — 견적은 고정 명세를 따라 10.
