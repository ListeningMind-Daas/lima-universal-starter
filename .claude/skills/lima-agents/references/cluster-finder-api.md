# cluster_finder API · 완전 참조 (공식 검증 · 2026-07-14)

**엔드포인트**: `POST /cluster_finder`
**목적**: 시드 키워드 주변의 검색 네트워크·클러스터 구조 확보
**공식 문서**: https://kr.listeningmind.com/docs/cluster-finder-api/

## 파라미터 (공식)

| 파라미터 | 타입 | 필수 | 기본값 | 범위·옵션 |
|---|---|---|---|---|
| `keyword` | string | | – | 단일 문자열 · 배열 불가 |
| `gl` | string | | – | `kr` / `jp` / `us` |
| `time_point` | string | | `curr` | `curr` / `3m` / `6m` / `9m` / `12m` |
| `limit` | integer | | **⭐ 이 스킬 기본 5000** (API 기본 500) | ** 반환 <span style="color:red">관계(rels) 수</span> 상한****반환 고유 키워드 수 아님**|
| `hop` | integer | | **2**| 1 ~ 3 · 관계 확장 깊이 |
| `orientation` | string | | `UNDIRECTED` | `UNDIRECTED` / `NATURAL` / `REVERSE` |
| `data_type` | string | | `communities` | `communities` / `rels` / `all` |

### limit · 반드시 정확히 이해할 것

**limit = 관계(rels) 배열의 최대 개수** · <b>반환 고유 키워드 수가 아님</b>. 과금 단위(반환 고유 키워드)는 limit으로 직접 정할 수 없고, 저장 응답 58건에서는 모두 limit+1 이하였다(2026-10-13 · 중앙값 limit의 약 0.62배).

#### 이 스킬의 규칙
- **기본값 `limit=5000` 강제** (API 기본 500은 부족 · .com UI 재현 위해 5000)
- 사용자가 명시하지 않으면 <b>무조건 5000</b>
- `hop=2`가 API 기본이므로 유지

#### 왜 관계 수인가
- 응답 `data.rels` 배열의 pair 개수 상한
- 반환 고유 키워드 수는 `rels` 양쪽 키워드를 unique화한 수 (= `cost_detail.output_count`)
- 예: 관계 498개 → 반환 고유 키워드 460개 (실측 · 전기자전거 KR · limit=500)

#### 관계 vs 노드 비율 (경험)
| 시장 규모 | 관계 : 노드 대략 |
|---|---|
| 좁은 시장 (hop=1) | 관계 ≈ 노드 × 1.2 |
| 표준 시장 (hop=2) | 관계 ≈ 노드 × 1.5 |
| 넓은 시장 (hop=2·많은 브랜드) | 관계 ≈ 노드 × 2 |

#### limit이 큰데 실제 반환이 작으면
- 그래프 실제 관계 수가 limit 미만 = 그대로 반환
- limit 5000인데 실제 반환 1,659면 · 이 그래프의 <u>진짜 크기가 1,659</u>
- limit 올려도 <b>없는 관계가 새로 생기지 않음</b>
- 크레딧은 <u>반환된 고유 키워드 수 기준</u>으로 청구 (150 + 고유 키워드×50) — 관계 수 기준이 아님

#### 실측 예 (2026-08-22 · 전기자전거 KR · hop=2)
- `limit=500` → 관계 498 반환 · 반환 고유 키워드 460 · 클러스터 3 · 크레딧 **23,150** — cost_detail 기준 output_count 460 → 150+460×50=23,150 (비용 계산은 응답 `cost_detail.total_cost`가 유일 기준)
- limit을 올려도 실제 그래프 크기 이상의 관계는 반환되지 않는다 — 반환 관계 수가 limit에 못 미치면 그것이 그래프의 진짜 크기다

**결론**: `limit=5000` 기본이면 대부분 시장에서 그래프 전체 확보 가능. 크레딧은 시장 크기에 따라 자연 조절.

### orientation · 3방향

| 값 | 의미 | 언제 |
|---|---|---|
| `UNDIRECTED` (기본) | 양방향 · 시드와 함께 검색된 모든 키워드 | 시장 전체 구조 |
| `NATURAL` | 순방향 · 시드 <b>이후</b> 검색된 키워드 | 구매 여정·다음 행동 |
| `REVERSE` | 역방향 · 시드 <b>이전</b> 검색된 키워드 | 진입 동기·상위 유입 |

### hop · 확장 깊이

| hop | 반환 관계 규모 |
|---|---|
| 1 | 시드 직접 결합 · 좁고 명확 |
| 2 (기본) | 시장 전체 구조 · **공식 기본값**|
| 3 | 인접 시장까지 · 노이즈 증가·크레딧 큼 | 노이즈·크레딧 급증 — 반드시 필요한 분석에서만 사용.

### data_type · 반환 데이터 범위

| data_type | 반환 필드 | 이 스킬 사용 |
|---|---|---|
| `communities` (기본) | 클러스터별 키워드 리스트만 · `{cluster_id: [kw,...]}` | 클러스터 구조만 필요할 때 |
| `rels` | 관계 pairs만 · `[[a, b], ...]` | 그래프 엣지만 필요할 때 |
| `all` | 위 둘 다 | **이 스킬 기본** · 시각화용 |

## 요청 표준 (Bash)

```bash
# 이 스킬 표준 요청 · limit=5000 강제
curl -X POST "https://listeningmind-data-api.ascentlab.io/cluster_finder" \
 -H "Content-Type: application/json" \
 -H "LM-API-KEY: $API_KEY" \
 -d '{
 "keyword": "전기자전거",
 "gl": "kr",
 "time_point": "curr",
 "limit": 5000,
 "hop": 2,
 "orientation": "UNDIRECTED",
 "data_type": "all"
 }'
```

## 응답 구조 (data_type=all)

```json
{
 "result": "OK",
 "reason": "SUCCESS",
 "cost_detail": {
 "input_cost": 150,
 "output_cost": 23000,
 "total_cost": 23150
 },
 "used_credits": 1234567,
 "data": {
 "communities": {
 "0": ["전기자전거", "국산 전기자전거 추천", "전기자전거 쿠팡", ...],
 "1": ["모토벨로 전기자전거", "모토벨로 전기자전거 후기", ...],
 "2": ["국내산 전기자전거", "전기 전동자전거", ...]
 },
 "rels": [
 ["전기자전거", "모토벨로 전기자전거"],
 ["모토벨로 전기자전거", "모토벨로 전기자전거 후기"],
 ...
 ]
 }
}
```

**주의**: 응답에 `nodes` 필드는 <b>공식 문서에 명시 없음</b>. 노드 볼륨은 별도 `keyword_info` 호출로 확보 필요.
**주의**: `used_credits`는 <b>당월 누적 사용량</b>이며 잔액이 아님 (잔액 필드는 응답에 없음). 호출 비용은 `cost_detail.total_cost` 기준.

### communities · 클러스터별 노드 리스트
- 키 = `cluster_id` (문자열 정수)
- 값 = 소속 키워드 배열
- 정렬 기준 · 공식 명시 없음 (경험상 볼륨·중심성 기준 추정)

### rels · 관계 pairs
- 방향 무관 (UNDIRECTED 기본)
- 각 항목 `[source, target]`
- 같은 pair가 반복 X (중복 제거됨)

## 크레딧 공식

**공식**: `150 (입력) + 고유 키워드 수 × 50 (출력)`

**과금 기준은 관계(rels) 수가 아니라 반환 고유 키워드 수다.** 라이브 OpenAPI의
`ClusterFinderCost.output_count` 설명이 "출력 키워드의 Unique 키워드 수"이며,
실측 스냅샷 18건에서 `150 + output_count × 50 == total_cost`가 전수 일치했다.
관계 수는 반환 고유 키워드 수의 1.5~3.7배이므로, 관계 수로 예산을 잡으면 크게 과대 추정된다.

### 실측 사례 (gl=kr · hop=2)

| 시드 | limit | 관계(rels) | 고유 키워드 | 크레딧 |
|---|---|---|---|---|
| 전기자전거 (2026-08-22) | 500 | 498 | 460 | **23,150** |
| 공식 계산 예 — 노드 1,000 | 5000 | — | 1,000 | 50,150 |
| 공식 계산 예 — 노드 1,800 | 5000 | — | 1,800 | 90,150 |

limit=5000 대형 시드는 고유 키워드 1,000~1,800개 규모로 5~9만 크레딧이 일반적이다(공식 계산).

비용 계산의 유일한 기준은 응답 `cost_detail.total_cost`다.

## 허브 키워드 (Hub Keyword) 판별 · 스킬 로직

### 공식 정의 (원문)
> "전체 클러스터 그래프에서 <b>많은 키워드와 연결이 되어 있어 관계성이 높은 키워드</b>로, 검색 의사 결정의 핵심 키워드"

### API에서 판별 방법
**API는 hub 플래그를 반환하지 않음**. 스킬이 응답에서 자체 계산:

```python
from collections import Counter

# rels 배열에서 각 키워드의 연결 수(degree) 계산
degree = Counter()
for a, b in rels:
 degree[a] += 1
 degree[b] += 1

# 방법 1 · 전체 그래프 상위 N 허브 (예 10개)
top_hubs = [kw for kw, d in degree.most_common(10)]

# 방법 2 · 각 클러스터 내 degree 최고 노드 = 클러스터 허브
cluster_hubs = {}
for cid, kws in communities.items():
 cluster_hubs[cid] = max(kws, key=lambda k: degree.get(k, 0))

# 이 스킬 표준 · 두 방법 결합
# 클러스터 허브 (각 클러스터 1개) + 전체 상위 degree TOP 3~5
```

### 시각화 표시 표준
- **허브 키워드**: <u>도넛 모양</u> (외곽선만 · 내부 투명 · 굵기 3px)
- **시드 키워드**: 굵은 검은 외곽선 (허브 여부와 별개)
- **일반 노드**: 채워진 색 (파스텔 팔레트 · 클러스터 색상)
- **라벨 표시**: 허브 + 시드만 (일반은 hover 시)

## 시드 2개 처리

시드 1~2개 지원 · 2개일 때:

1. 각 시드마다 `cluster_finder` 개별 호출 (병렬)
2. 두 응답의 `rels` 병합 · 중복 제거 (방향 무관 pair)
3. Louvain 알고리즘으로 재군집화 (`_shared/lib/louvain.py`)
4. 두 시드 모두에 등장하는 <b>다리 키워드(bridge)</b> 감지

## 응답 검증 (필수)

응답의 `request_detail`로 요청 파라미터 검증 가능 (요청값이 그대로 반환됨). 추가로 <u>사전 로깅</u> 병행 관리 권장.

## 오류 코드

| HTTP | 원인 | 해결 |
|---|---|---|
| 401 | API Key 미입력·유효 X | 헤더 재확인 |
| 402 | 크레딧 부족 | 충전 |
| 403 | 엔드포인트 권한 없음 | 계정 확인 |
| 422 | 파라미터 오류 | `keyword` 단일 · 파라미터 값 범위 재확인 |
| 429 | Rate Limit 초과 | 요청 속도 조절 |
| 500 | 서버 오류 | 재시도·기술 지원 | **과금**: 오류 응답의 과금 여부는 응답 `cost_detail`로 확인.

## Rate Limit · 동시 요청

**공식 문서에 구체 숫자 미명시** · 429 Rate Limit 오류만 언급.
- 실전 경험 · 시드 2개 병렬 호출 안정 작동
- 신중히 · max 3 concurrent 관행 유지 권장

## 실전 사용 · 크레딧 최소화 팁

1. **먼저 keyword_list로 크기 확인** · `cluster_finder/keyword_list`는 30 + 결과×2 (매우 저렴)
2. **적정 limit** · limit=500 (전기자전거 실측: 관계 498·노드 460 = 23,150 크레딧) 기본이 안전 · 전체 그래프가 필요할 때만 5000
3. **hop=2 기본 유지** · hop=3은 특별 목적 시만
4. **시드 1개로 먼저** · 필요 시 두 번째 시드 추가 (병합·재군집화)

## cluster_finder/keyword_list · 서브 엔드포인트

**엔드포인트**: `POST /cluster_finder/keyword_list`
**목적**: 관계 네트워크 기반 키워드 목록만 · 클러스터 구조 없음
**크레딧**: 30 (입력) + 반환 키워드 수 × 2 (출력)

**용도**:
- 시각화 전 크기 미리 확인
- 키워드 리스트만 필요할 때 (예: 시드 확장)
- 저비용

이 스킬은 <u>선택적으로 사용</u> · 시각화 목적엔 본 API 필요.

## 파라미터 소요 시간 (경험 참고)

- hop=1 · 약 15초
- hop=2 · 약 30초 (기본)
- hop=3 · 1분+ (권장 안 함)
- 시드 2개 병렬 · 위와 비슷
