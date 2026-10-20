# serp API · 완전 참조

**엔드포인트**: `POST /serp`
**목적**: 키워드의 검색결과 화면(SERP)을 블록 단위로 조회
**래퍼**: `api/serp.py` · `fetch()` + 파싱 헬퍼 6종
**검증**: 운영 OpenAPI v1.0.13 파라미터 대조(2026-10-13) + 실측 응답 (gl=kr · num=10 · 2026-08-25 전기자전거)

> ⚠️ **단가 주의** — 아래 예시 응답의 `cost_detail.total_cost: 10` 은 **2026-08-19 시점 스냅샷**이다.
> serp 단가는 2026-08-28 실측으로 **30 / 키워드**로 인상됐다. 견적은 30/kw 로 잡는다.
> 운영 OpenAPI v1.0.13 의 `input_cost` 기본값도 30 이라 문서와 실측이 일치한다.
> 같은 판에서 응답에 `collected_at`(SERP 스냅샷 수집 시각·UTC)이 추가됐고, 요청에 `user_query`·`response_format` 이 생겼다
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

**시계열 비교에는 쓸 수 없다.** 반환값은 조회 시점의 스냅샷이다. 시점 비교가 필요하면
`keyword_info`의 `features`(월 그레인)를 쓴다.

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
빈 리스트는 "그 시점 AIO 미노출"이다(오류 아님). 인용 출처는 `ai_overview` 블록의 `snippet_links[]` 에 있다.
응답의 `collected_at` 을 키워드별로 기록한다.
- **AIO 노출 비율** = AIO 가 나온 키워드 수 / 조회 키워드 수
- `features=["ai_overview"]` 로 블록을 좁히는 요청은 **미실측**이다. 과금이 키워드당 정액이라 전체를 받아
  파싱해도 비용은 같다 — 기본은 전체 조회
- 동시 요청은 1 (429 방지)

**비용** = ① 확장 호출 합 + (② `ads_metrics` 를 쓰면 1 × 확장 키워드 수) + ③ 30 × 최종 키워드 수.
예: intent_finder 1회(100개 반환) 230 + ads_metrics 100 + serp 상위 50개 1,500 = 1,830 (계산 예시 · 실소비는 각 응답 `cost_detail`).

**미리 거르기 판단** — `keyword_info(all)` 의 `f_ai_overview`(10/kw)로 노출 키워드만 골라 serp 를 부르면,
AIO 노출 비율이 약 2/3 미만일 때 전체 serp 보다 싸다(10 + 30p < 30 → p < 2/3 · 파생 계산).
단, `f_ai_overview` 는 월 그레인이고 serp 는 조회 시점 스냅샷이라 둘이 어긋날 수 있다 — 거른 목록의 비율을 "전체 노출 비율"로 쓰지 않는다.

## 파라미터

| 파라미터 | 타입 | 기본 | 설명 |
|---|---|---|---|
| `keyword` | 문자열 | (필수) | **단일 키워드**. 배열이 아니다 |
| `gl` | 문자열 | (필수) | `kr` · `jp` · `us` |
| `num` | 정수 | 20 | **10 또는 20만 허용**. 과금은 num과 무관 |
| `device` | 문자열 | `mobile` | `mobile` · `desktop` — 모바일/데스크톱 SERP는 블록 구성이 다르다 |
| `features` | 배열/null | null | 특정 블록만 요청. 생략 시 전체 |

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

### 블록 type (실측 확인 · `전기자전거` kr/mobile/num=10 · 2026-08-25)

| type | 개수 | 주요 필드 |
|---|---|---|
| `organic_results` | 17 | `position` · `site_name` · `title` · `url` · `snippet` · `thumbnail` |
| `ai_overview` | 1 | `text_blocks[].list[].snippet` · `snippet_links[]` |
| `people_also_ask_for` | 1 | `items[].question` · `url` · `title` |
| `related_searches` | 1 | `items[].query` |
| `people_also_search_for` | 1 | `items[].query` |
| `local_results` | 1 | 지도·매장 |
| `video_results` | 1 | `items[]` |
| `images` | 2 | `grid` |

블록 구성은 키워드마다 다르다(예: `knowledge_panel`은 이 키워드에 없음). `num=10` 요청에
`organic_results`가 17개 반환됐다 — `num`은 자연결과 개수를 정확히 고정하지 않는다.
실제 개수는 응답에서 세어 확인한다.

## 크레딧

```
total_cost = 30 (키워드당 · 입력 과금만 · 2026-08-28 실측 — 2026-08-19의 10에서 인상)
```

`output_cost`는 0이라 반환 블록이 몇 개든 비용은 동일하다 — 4개 커넥터 중 가장 예측 가능한 단가다.
(2026-08-19 라이브 OpenAPI `SerpCost.input_cost=10` → 2026-08-28 실측 30.)

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
serp.ai_overview_snippets(r)  # AI 개요 본문 · 미노출 키워드는 빈 리스트
serp.blocks(r, "video_results")
```

## 해석 규율

SERP는 **구글 검색결과**다. 국내 분석에서 네이버 비중이 큰 카테고리라면 이 데이터만으로
"검색 노출 지형"을 단정하지 않는다 — `keyword_info.ads_metrics`의 `gg_volume_avg` /
`nv_volume_avg` 비율을 함께 보고 서술한다.
