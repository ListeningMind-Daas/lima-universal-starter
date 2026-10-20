# DaaS API 개요

**Base URL** · `https://listeningmind-data-api.ascentlab.io`
**인증** · `LM-API-KEY` 헤더

## 엔드포인트 (라이브 OpenAPI 기준 · 전체 래퍼 제공)

> **최상위 근거** · 공개 API 문서 https://listeningmind-data-api.ascentlab.io/ — 단가·파라미터·응답 필드는 **항상 여기를 먼저 대조한다.**
> 이 문서는 그 스냅샷이며, 문서와 어긋나면 **문서가 이긴다.**
>
> **스냅샷 기준** · `listeningmind-data-api` 운영 **v1.0.13** · 확인일 **2026-10-13** (serp 단가는 2026-08-28 실측으로 30/kw 갱신).
> 직전 스냅샷 대비 `/ai_overview/analyze`가 삭제됐고, 모든 엔드포인트에 선택 파라미터 `is_skills`(bool · 기본 false)가 추가됐다.
> API 스펙이 갱신되면 이 절과 커넥터 명세 6종의 파라미터·단가를 재대조한다.

모든 엔드포인트에 `api/` 래퍼가 있다. **호출 원칙은 보수적** — 표준 파이프라인은
cluster_finder + keyword_info 2개로 완결하고, 나머지는 해당 분석이 반드시 요구할 때만 호출한다.

| 엔드포인트 | 목적 | 래퍼 | 호출 기준 |
|---|---|---|---|
| POST /cluster_finder | 시드 키워드의 관계 그래프·커뮤니티 | `cluster_finder.fetch` | ✅ 표준 파이프라인 |
| POST /keyword_info | 키워드별 검색량·인텐트·인구·SERP·48개월 시계열 | `keyword_info.fetch_all` | ✅ 표준 파이프라인 (data_type=all) |
| POST /cluster_finder/keyword_list | 관계 그래프의 키워드 리스트만 (경량) | `cluster_finder.fetch_keyword_list` | 그래프 구조 불필요 시 |
| POST /intent_finder/keyword_list | 인텐트 유형별 키워드 리스트 확장 | `intent_finder.fetch` | keyword_info의 intents 벡터로 부족할 때만 |
| POST /path_finder | 검색 여정 (A→B→C 시퀀스) | `path_finder.fetch` | 여정 분석이 필요한 질문에만 (키워드 수 비례 과금) |
| POST /path_finder/keyword_list | 여정 등장 키워드 리스트만 (경량) | `path_finder.fetch_keyword_list` | 경로 시퀀스 불필요 시 |
| POST /serp | 키워드의 SERP 결과 조회 (블록 단위) | `serp.fetch` | 검색결과 화면 자체가 필요할 때 (keyword_info의 `features`로 부족한 경우) |
| POST /trend_finder/issue_list | 시드 주변 최근 급부상 이슈 (요약·핵심 구문·출처·이슈 점수) | `trend_finder.fetch` · `widen` | 급등 원인·최근 이슈·단발/지속 판정이 결론에 필요할 때 (검색량만 필요하면 keyword_info) |
| GET /usage/summary | 기간별 사용량 집계 (정산·리포트) | `usage.summary` | 과금 리포트 작성 시 |

연관 키워드 묶음의 AIO 원문은 `*/keyword_list`·`trend_finder` 확장 → 유니크 목록 → `serp` 로 모은다 ([[references/serp-api.md]]).

**공통 파라미터 (v1.0.x 부터 · 모든 POST)** · `user_query`(이 호출을 유발한 사용자 질의 원문 — 선택, 이력에 적재) ·
`is_skills`(스킬 경유 호출 여부 — 선택·기본 false, 이력에 적재 · v1.0.13~. `DaasClient.post()` 가 body 에 없으면 `true` 를 넣는다) ·
`response_format`(`json` 기본 / `download_url` — 대용량 조회 시 `data` 대신 `download` 메타(주소·sha256·크기)만 오고 파일로
내려받는다 · `DaasClient.download(response)` 가 sha256 대조까지 한다). `*/keyword_list` 경량 계열은 `response_format` 만 받는다.

### 커넥터별 상세 명세

파라미터·응답 필드·크레딧 공식은 커넥터별 참조 문서에 있다. 실질 분석 전에 해당 문서를 읽는다.

| 커넥터 | 상세 문서 |
|---|---|
| cluster_finder | [[references/cluster-finder-api.md]] |
| keyword_info | [[references/keyword-info-api.md]] |
| intent_finder | [[references/intent-finder-api.md]] |
| path_finder | [[references/path-finder-api.md]] |
| serp | [[references/serp-api.md]] |
| trend_finder | [[references/trend-finder-api.md]] (2026-09-23 추가 · 실측 1건) |

`usage/summary`는 조회 전용이라 별도 문서를 두지 않는다 — `api/usage.py` 참조
(`date_from`·`date_to` 필수 · `platform` 선택).

## 조합 원칙

**표준 조회 파이프라인**
1. `cluster_finder(seed, limit=5000, hop=2, data_type=all)` · 관계 그래프
2. 유니크 키워드 추출 — 스펙 정의 필드는 `rels`·`communities`. `nodes`는 스펙 미정의이나 응답에 있으면 우선 사용 (래퍼 `unique_keywords`가 nodes→communities→rels 순 폴백)
3. `keyword_info(all_kws, data_type=all)` · 각 키워드 상세

**크레딧 참고** (읽기용 요약 — 견적 숫자는 `api/spec.py` 가 운영 명세에서 읽는다. 둘이 다르면 명세가 이긴다)
- cluster_finder · **150 + 반환 고유 키워드 수 × 50** (관계 수가 아님 · 실측 18건 전수 검증)
- keyword_info · data_type별 차등 — `ads_metrics`·`ads_info` 1 / kw · `all` 10 / kw (인텐트·인구·시계열 필요 분석은 all, 볼륨 사전 검증은 ads_metrics)
- path_finder · **50 + 40 × 경로에 등장한 고유 키워드 수** (경로 수가 아님 · 실측 5,050·6,770·8,410) — 래퍼 기본 limit=150으로 통제
- intent_finder · **30 + 2 × 반환 키워드 수** (실측 42건 전수 일치 · limit=100 도달 시 230)
- `*/keyword_list` 경량 계열(cluster_finder·path_finder·intent_finder) · **30 + 반환 키워드 × 2** 공통
- serp · **30 / 키워드** (입력 과금만 · 출력 과금 없음 · 2026-08-28 실측 — 2026-08-19의 10에서 인상)
- trend_finder · **50 (시드당) + 2 × 반환 이슈 항목 수** (2026-09-23 실측 · limit=3 → 56) — `limit` 으로 통제, 래퍼 기본 50
- usage/summary · 조회 전용 (사용량 정산)

**동시 요청 상한** · 3 concurrent (429 오류 방지)

## 응답 구조 요약 (핵심 필드만)

### cluster_finder

```json
{
  "result": "OK",
  "data": {
    "rels": [["kw_a", "kw_b"], ...],
    "communities": {"0": ["kw1", "kw2"], "1": [...]}
  },
  "cost_detail": {"total_cost": 23150}
}
```

**참고**: 스펙(OpenAPI)에 정의된 응답 필드는 `rels`·`communities`뿐이다. `nodes`는 스펙 미정의 —
응답에 포함되면 우선 사용하되, 래퍼 `unique_keywords`가 nodes→communities→rels 순으로 방어적 폴백 처리한다.

### keyword_info (data_type=all)

```json
{
  "data": [{
    "keyword": "전기자전거",
    "ads_metrics": {
      "volume_avg": 245333, "volume_total": 2567300, "volume_trend": -0.3,
      "gg_volume_avg": 56833, "nv_volume_avg": 188500,
      "competition": "HIGH", "competition_index": 100, "cpc": 0.4
    },
    "features": {"f_ai_overview": 1, "f_organic_results": 17, ...},
    "intents": {"i": 1, "n": 0, "c": 0, "t": 1},
    "demography": {
      "m_gender_ratio": 72.88, "f_gender_ratio": 27.11,
      "a20_ratio": 4.27, "a25_ratio": 8.27, "a30_ratio": 27.15, "a40_ratio": 31.69, "a50_ratio": 26.19
    },
    "monthly_volume": [{"month": "2022-08", "gg": 60500, "nv": 298400, "total": 358900}, ...]
  }]
}
```

## Python 사용 (api/ 모듈)

```python
from api.client import DaasClient
from api import cluster_finder, keyword_info

c = DaasClient()   # 키 생략 → resolve_api_key(): LM_API_KEY → 00_Context/.lm-api-key → ~/.config/listeningmind/api-key
cf = cluster_finder.fetch(c, "전기자전거", gl="kr", limit=5000, hop=2)
all_kws = cluster_finder.unique_keywords(cf)  # nodes→communities→rels 폴백
info_list, cost = keyword_info.fetch_all(c, all_kws, gl="kr", data_type="all")
info_by_kw = keyword_info.index_by_keyword(info_list)
```
