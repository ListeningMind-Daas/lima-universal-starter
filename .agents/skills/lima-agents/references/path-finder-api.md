# path_finder API · 완전 참조

**엔드포인트**: `POST /path_finder` · `POST /path_finder/keyword_list`
**목적**: 검색 여정 조회 — 시드 키워드 앞뒤로 이어지는 쿼리 시퀀스
**래퍼**: `api/path_finder.py` · `fetch()` · `fetch_keyword_list()` · `paths()`
**검증**: 라이브 OpenAPI 파라미터 + 실측 응답 (gl=kr · 2026-08-14 2건 · 2026-08-22 전기자전거)

## 언제 호출하나 (보수적 기준)

**여정·전이·선후행이 판단의 일부일 때만** 호출한다. 수요 크기·경쟁 구도·니즈 구조는
`keyword_info`·`cluster_finder`로 답이 나오므로 path_finder를 쓸 이유가 없다.
4개 커넥터 중 **단가가 가장 높다** (아래 크레딧 참고).

호출 전 반드시 시드를 검증한다 — 오염된 시드의 경로는 전량 폐기 대상이다.

## 요청 표준

```bash
curl -X POST "https://listeningmind-data-api.ascentlab.io/path_finder" \
 -H "Content-Type: application/json" \
 -H "LM-API-KEY: $API_KEY" \
 -d '{
 "keyword": "전기자전거",
 "gl": "kr",
 "time_point": "curr",
 "limit": 150
 }'
```

## 파라미터

| 파라미터 | 타입 | 기본 | 설명 |
|---|---|---|---|
| `keyword` | 문자열 | (필수) | **단일 시드**. 배열이 아니다 — `cluster_finder`·`keyword_info`와 다른 점 |
| `gl` | 문자열 | `kr` | 국가. `kr`·`us`·`jp` |
| `time_point` | 문자열 | `curr` | `curr` · `3m` · `6m` · `9m` · `12m` — 정책·시즌 전후 비교에 사용 |
| `limit` | 정수 | API 300 / **래퍼 150** | 반환 **경로 수** 상한 |

`time_point` 값은 래퍼가 화이트리스트로 검증한다 (`TIME_POINTS`).

**래퍼 기본값이 API 기본값과 다르다** — API는 300이지만 래퍼는 150으로 낮춰 잡았다.
여정 분석에는 충분하고 비용은 절반 수준이다. 더 필요하면 `limit`을 명시적으로 올린다.

## 응답 구조 (실측)

```json
{
  "result": "OK",
  "request_detail": {"keyword": "전기자전거", "gl": "kr", "time_point": "curr", "limit": 150},
  "cost_detail": {"input_cost": 50, "input_count": 1, "input_total_cost": 50,
                  "output_cost": 40, "output_count": 125, "output_total_cost": 5000,
                  "total_cost": 5050},
  "used_credits": 123456,
  "data": [
    ["전기자전거", "삼천리 전기자전거", "알톤 전기자전거"],
    ["전기자전거", "전기자전거 가격", "전기자전거 면허", "전기자전거 면허 필요"]
  ]
}
```

**`data`는 경로의 배열이고, 각 경로는 키워드 시퀀스(순서 있음)다.**
실측에서 경로 길이는 3~8단계로 분포했다(전기자전거 150경로: 3단계 42 · 4단계 49 · 5단계+ 59).
시드는 경로의 시작에 오는 경우가 다수지만(실측 124/150) 끝에 오기도 한다(26/150).

**방향은 요청 파라미터가 아니다.** FORWARD(후속)·REVERSE(선행) 구분은 응답을 받은 뒤
각 경로에서 시드의 위치(index)를 찾아 앞뒤를 나누는 **분석 측 처리**다 —
각 경로에서 시드 위치를 찾아 전이(시드 이후 등장)와 선행(시드 직전 등장)을 분리한다.

래퍼 `paths()`는 2개 미만 시퀀스를 걸러내고 공백을 정리해 반환한다.

**해석 규율** · 이 데이터는 **집계 행동 그래프이며 개인 추적이 아니다**. 경로는 세션 인접
관계이지 특정 개인의 시간순 여정이 아니므로, 리포트에서 "한 사람이 A→B→C로 이동했다"로
서술하지 않는다.

## 크레딧 (실측 검증 · 가장 비싼 커넥터)

```
total_cost = 50 (input_cost) + 40 × 경로에 등장한 고유 키워드 수
```

**과금 단위는 경로 수가 아니라 고유 키워드 수다.** 실측 전 건에서 `output_count`가
`data` 전체를 펼친 고유 키워드 집합의 크기와 정확히 일치했다 (125·168·209).
경로를 많이 받아도 키워드가 겹치면 비용은 그만큼 줄어든다 — 반대로 시드가 넓으면
경로 수는 같아도 비용이 크게 뛴다.

| 실측 사례 | limit | 경로 수 | 고유 키워드 | 크레딧 |
|---|---|---|---|---|
| `전기자전거` (kr · 2026-08-22) | 150 | 150 | 125 | **5,050** |
| limit 300 실측 2건 (2026-08-14) | 300 | 300 | 168 · 209 | **6,770 · 8,410** |
| 소규모 여정 (래퍼 주석) | — | 5 | 10 | 450 |

**비용 통제** · ① 래퍼 기본 `limit=150` 유지 ② 경로 시퀀스가 필요 없으면
`path_finder/keyword_list` 사용 ③ 시드를 좁혀 고유 키워드 수를 줄인다.

## path_finder/keyword_list · 서브 엔드포인트

**엔드포인트**: `POST /path_finder/keyword_list`
**목적**: 여정에 등장하는 키워드 목록만 · 경로 시퀀스 없음
**용도**: 여정 반경의 키워드 수집만 필요할 때 (전이 구조가 불필요한 경우)
**래퍼**: `path_finder.fetch_keyword_list()` — 파라미터는 `fetch()`와 동일

## 오류 코드

`cluster_finder`와 동일 체계 · 401(키) · 402(크레딧 부족) · 403(권한) · 422(파라미터 —
`keyword`는 배열이 아닌 단일 문자열) · 429(rate limit) · 500(서버).
과금 여부는 오류 응답의 `cost_detail`로 확인한다.

## Python 사용

```python
from api.client import DaasClient
from api import path_finder

c = DaasClient(api_key=API_KEY)
r = path_finder.fetch(c, "전기자전거", gl="kr", time_point="curr", limit=150)
seqs = path_finder.paths(r)              # [["...", "...", "..."], ...]
cost = r["cost_detail"]["total_cost"]
```
