# intent_finder API · 완전 참조

**엔드포인트**: `POST /intent_finder/keyword_list`
**목적**: 시드 키워드의 인텐트 유형별 연관 키워드 리스트 확장
**래퍼**: `api/intent_finder.py` · `fetch()`
**검증**: 라이브 OpenAPI 파라미터 + 실측 응답 42건 (gl=kr · 2026-08-14)

## 언제 호출하나 (보수적 기준)

표준 파이프라인(cluster_finder + keyword_info)으로 완결되면 **호출하지 않는다**.
`keyword_info` 응답의 `intents`(i/n/c/t) 벡터로 충분한 분석에는 불필요하다.

호출이 정당한 경우 · 시드 검증(오염 판정) · 연관 쿼리 목적별 그룹핑 · 클러스터에 안 잡히는
롱테일 확장 · 콘텐츠/광고 키워드 후보 수집.

## 요청 표준

```bash
curl -X POST "https://listeningmind-data-api.ascentlab.io/intent_finder/keyword_list" \
 -H "Content-Type: application/json" \
 -H "LM-API-KEY: $API_KEY" \
 -d '{
 "keywords": ["전기자전거"],
 "gl": "kr",
 "volume_threshold": 100,
 "limit": 100,
 "sort": "volume_avg",
 "order": "desc"
 }'
```

## 파라미터

| 파라미터 | 타입 | 기본 | 설명 |
|---|---|---|---|
| `keywords` | 배열 | (필수) | 시드 키워드. **단수 시드 권장** — 복수 시드는 결과 귀속이 섞여 판정이 흐려진다 |
| `gl` | 문자열 | `kr` | 국가. `kr`·`us`·`jp` |
| `volume_threshold` | 정수 | 100 | 검색량 하한. 낮출수록 롱테일이 늘고 노이즈·비용도 함께 는다 |
| `limit` | 정수 | 100 | 반환 키워드 수 상한. **비용에 직결** — 래퍼 기본 100 유지 권장 |
| `sort` | 문자열 | `volume_avg` | `volume_avg` · `volume_total` · `volume_trend` · `cpc` · `competition_index` |
| `order` | 문자열 | `desc` | `desc` · `asc` |

`sort` 값은 래퍼가 화이트리스트로 검증한다 (`SORT_FIELDS`) — 오타는 호출 전에 `ValueError`로 막힌다.

## 응답 구조 (실측)

```json
{
  "result": "OK",
  "reason": null,
  "source": "...",
  "version": "...",
  "user_type": "...",
  "request_at": "...",
  "request_detail": {"keywords": ["전기자전거"], "gl": "kr", "volume_threshold": 100,
                     "limit": 100, "sort": "volume_avg", "order": "desc"},
  "cost_detail": {"input_cost": 30, "input_count": 1, "input_total_cost": 30,
                  "output_cost": 2, "output_count": 100, "output_total_cost": 200,
                  "total_cost": 230},
  "used_credits": 123456,
  "data": ["전기자전거", "삼천리 전기자전거", "전기자전거 추천", "전기자전거 렌탈", "..."]
}
```

**`data`는 키워드 문자열의 단순 배열이다.** 볼륨·인텐트 수치는 함께 오지 않는다 —
수치가 필요하면 반환된 키워드를 `keyword_info`로 다시 조회해야 한다(비용 별도).

`request_detail`에 요청값이 그대로 반환되므로 파라미터 검증에 사용한다.
`used_credits`는 **당월 누적 사용량**이며 잔여량이 아니다.

## 크레딧 (실측 검증)

```
total_cost = 30 (input_cost × 시드 수) + 2 × 반환 키워드 수
```

`output_count`는 `data` 길이와 정확히 일치한다 (실측 42건 전수 확인).
`limit`은 상한일 뿐이라 시드가 빈약하면 그만큼만 반환되고 비용도 그만큼만 든다.

| 반환 키워드 | 크레딧 | 비고 |
|---|---|---|
| 100 (limit 상한 도달) | **230** | 일반적인 시드 (전기자전거 실측 2026-08-22) |
| 43 | 116 | 중간 |
| 1 | 32 | 거의 빈 시드 — 시드 오염·오타 의심 |

실측 42회 호출 누적 7,126 크레딧 (평균 170).

## 활용 · 시드 검증

`listeningmind-universal/scripts/seed_check.py`가 이 엔드포인트를 시드 오염 판정에 사용한다.
반환된 100개 키워드를 노이즈 정규식·브랜드 사전에 대조해 노이즈율(<20%)·적합률(≥60%)·
브랜드히트(≥10)를 계산하며, 시드당 약 230크레딧으로 본 실측 전에 오염 시드를 걸러낸다.
`cluster_finder`·`path_finder`를 미검증 시드에 쓰기 전에 이 단계를 먼저 통과시킨다.

## 오류 코드

`cluster_finder`와 동일 체계 · 401(키) · 402(크레딧 부족) · 403(권한) · 422(파라미터) ·
429(rate limit) · 500(서버). 과금 여부는 오류 응답의 `cost_detail`로 확인한다.

## Python 사용

```python
from api.client import DaasClient
from api import intent_finder

c = DaasClient(api_key=API_KEY)
r = intent_finder.fetch(c, ["전기자전거"], gl="kr", limit=100)
kws  = r["data"]
cost = r["cost_detail"]["total_cost"]
```
