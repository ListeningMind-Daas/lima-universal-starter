# 후속 시드 제안 · 4가지 카테고리

## 개념

조사원이 첫 시드 결과를 보고 <b>다음에 조회하면 좋을 시드 3~5개</b>를 자동 제안. 사용자가 골라서 이어 조사 · 시장 지도가 점점 넓어짐.

## 4가지 발굴 카테고리 (모두 사용)

각 카테고리마다 1~2개씩 · 총 3~5개 후보 제안.

### A. 허브 키워드 상위 (그래프 확장)

**로직**: `hub_keywords` 중 아직 조회 안 된 키워드 · degree 높은 순.

**언제 좋은가**: 지금 그래프의 <b>주변 확장</b>이 필요할 때 · 아직 특정 방향에 집중 아니고 시장 전체를 넓게 보고 싶을 때.

```python
def suggest_by_hub(cluster_data, already_queried):
    hubs = cluster_data["hub_keywords"]
    # degree 정보를 nodes에서 재계산
    from collections import Counter
    degree = Counter()
    for a, b in cluster_data["rels"]:
        degree[a] += 1
        degree[b] += 1
    candidates = [h for h in hubs if h not in already_queried]
    candidates.sort(key=lambda k: -degree.get(k, 0))
    return candidates[:2]
```

**제안 예**:
```
[허브 확장] "삼천리 전기자전거 추천" · degree 194 · 2번 클러스터 대표
· 지금 그래프의 인접 상위 허브 · 확장 조회 시 인접 시장 노출
```

### B. 감지된 브랜드 (경쟁사 딥다이브)

**로직**: `detected_entities.brands` 중 볼륨 큰 브랜드 · 아직 시드로 조회 안 됨.

**언제 좋은가**: <b>특정 브랜드의 검색 지형</b>을 깊게 볼 때 · 그 브랜드가 어떤 CEP·페인포인트를 소유하는지.

```python
def suggest_by_brands(cluster_data, already_queried):
    brands = cluster_data.get("detected_entities", {}).get("brands", [])
    brands_sorted = sorted(brands, key=lambda b: -b.get("total_volume", 0))
    candidates = [b["name"] for b in brands_sorted if b["name"] not in already_queried]
    return candidates[:2]
```

**제안 예**:
```
[브랜드 딥다이브] "모토벨로" · brand_volume 48,356 · 전업 브랜드 (단독 쿼리 최대)
· 이 브랜드가 소유하는 CEP · 사용자가 이 브랜드를 어떤 맥락에서 검색하는지 확인
```

### C. CEP 공백 W (기회 세그먼트)

**로직**: `cep_grouped` W별 total_volume 최하위 · <b>그 W의 대표 서브그룹 라벨</b>을 시드 후보로.

**언제 좋은가**: 대형 브랜드가 놓친 세그먼트 · <b>진입 기회</b>를 찾을 때.

```python
def suggest_by_cep_gap(cluster_data, already_queried):
    cep = cluster_data.get("cep_grouped", {})
    # W별 total_volume 오름차순 (작은 것이 공백)
    w_sorted = sorted(cep.items(), key=lambda x: x[1].get("total_volume", 0))
    suggestions = []
    for w_key, w_info in w_sorted[:2]:  # 하위 2개 W
        # 각 W의 최대 서브그룹 라벨
        subgroups = w_info.get("subgroups", {})
        if subgroups:
            top_sub = max(subgroups.items(), key=lambda x: x[1].get("total_volume", 0))
            sub_label = top_sub[0]
            # 서브그룹 상위 키워드 하나를 시드로 (예: "여성·시니어" → "여성 전기자전거 추천")
            top_kw = top_sub[1]["keywords"][0]["keyword"] if top_sub[1].get("keywords") else sub_label
            suggestions.append({
                "seed": top_kw,
                "reason": f"CEP 공백 · {w_key} '{sub_label}' 세그먼트 (총 볼륨 {top_sub[1].get('total_volume',0):,})"
            })
    return [s for s in suggestions if s["seed"] not in already_queried]
```

**제안 예**:
```
[공백 세그먼트] "여성 전기자전거 추천" · WHOM 결합 쿼리 190/월 (헤드텀의 0.1%)
· 상위 브랜드 미공략 세그먼트 · 진입 기회 확인용
```

### D. 라이징 신흥 후보

**로직**: 감지 브랜드 중 <b>볼륨은 낮지만 트렌드 상승</b> or `keyword_info.volume_trend` 상승률 상위 노드. 트렌드 데이터가 없으면 · 신흥 시그널 (WebSearch "스타트업·와디즈·크라우드펀딩" 언급) 있는 브랜드.

**언제 좋은가**: <b>초기 성장 브랜드</b>·<b>미래 지형</b>이 궁금할 때 · 시장 상위만 보면 놓치는 것들.

```python
def suggest_by_rising(cluster_data, already_queried, kw_info_data):
    # 노드 중 volume_trend 상승률 상위
    trend_map = {}
    for item in kw_info_data:
        kw = item.get("keyword")
        volume_trend = item.get("volume_trend", {})
        # 최근 3개월 평균 vs 이전 3개월 평균
        recent = list(volume_trend.values())[-3:] if isinstance(volume_trend, dict) else []
        prev = list(volume_trend.values())[-6:-3] if isinstance(volume_trend, dict) else []
        if recent and prev and sum(prev) > 0:
            ratio = sum(recent) / sum(prev)
            if ratio > 1.3:  # 30%+ 상승
                trend_map[kw] = ratio
    rising = sorted(trend_map.items(), key=lambda x: -x[1])
    return [{"seed": kw, "reason": f"트렌드 상승 · +{int((r-1)*100)}%"} for kw, r in rising[:2] if kw not in already_queried]
```

**제안 예**:
```
[라이징] "세발 전기자전거" · 8,903/월 · ▲11~17% (세발·삼륜 세그먼트 합 13,779)
· 하락 시장에서 유일한 상승 세그먼트 · 50대+ 45% 시그널 확인용
```

## 제안 응답 형식 (표준)

매 시드 조회 응답 마지막에:

```markdown
---

## 다음에 조사하면 좋을 시드 (조사원 자동 발굴)

이미 조회한 시드: 전기자전거 (1)

**A. 그래프 확장 (허브 상위)**
1. "삼천리 전기자전거 추천" · degree 194 · 2번 클러스터 대표 노드
   · 인접 상위 허브 · 시장 주변 확장 조회

**B. 브랜드 딥다이브**
2. "모토벨로" · brand_volume 48,356 · 전업 브랜드 (단독 쿼리 최대)
   · 이 브랜드가 소유하는 CEP · 페인포인트 확인
3. "삼천리 전기자전거" · 25,053 · 결합 쿼리 1위
   · 종합 브랜드 vs 전업 브랜드 대조

**C. CEP 공백 딥다이브**
4. "여성 전기자전거 추천" · WHOM 세그먼트 (190/월 · 0.1%)
   · 상위 브랜드 미공략 · 진입 기회

**D. 라이징 신흥**
5. "세발 전기자전거" · ▲11~17% · 50대+ 45%
   · 하락 시장의 유일한 상승 세그먼트

---

어떤 시드로 이어서 조사할까요? (번호 · or "다른 시드" · or "종료")

- 예상 크레딧 · 각 시드당 약 25,000~30,000 (limit 500 기준 · limit 5000이면 5~9만)
- 누적 크레딧 (현재 29,010) → 다음 조회 후 약 55,000~60,000
- 조회 후 통합 HTML 뷰에 새 탭으로 추가됩니다
```

## 자동 발굴 코드 통합

```python
def suggest_next_seeds(session, current_cluster_data, kw_info_data):
    already = [s["seed"] for s in session["seeds"]]
    suggestions = {
        "허브 확장 (A)": suggest_by_hub(current_cluster_data, already),
        "브랜드 딥다이브 (B)": suggest_by_brands(current_cluster_data, already),
        "CEP 공백 (C)": suggest_by_cep_gap(current_cluster_data, already),
        "라이징 신흥 (D)": suggest_by_rising(current_cluster_data, already, kw_info_data),
    }
    return suggestions
```

## 조사원 원칙

- **매번 4개 카테고리 다 훑음** · 발굴되는 게 없으면 그 카테고리는 skip
- **최소 3개 · 최대 5개** 제안 (너무 많으면 사용자 판단 어려움)
- **각 제안에 왜 이 시드인지 이유 명시** · 무작정 나열 금지
- **크레딧 누적 안내 필수** · 다음 조회의 예상 · 누적치
- **사용자가 "종료" 하면 세션 종료** · sessions.json 최종 저장 · 종합 인사이트 리포트

## 종합 리포트 (세션 종료 시)

사용자가 종료하면 · 지금까지 조회한 모든 시드를 종합해서 요약:

```markdown
## 탐색 세션 종합 리포트

**조회 시드 3개**: 전기자전거 → 모토벨로 → 세발 전기자전거
**총 크레딧**: 85,000 (예시 · 실제는 응답 cost_detail 합산)
**소요 시간**: 12분

**핵심 발견 (교차 시드 인사이트)**
1. 모토벨로는 전업 브랜드 — 단독 쿼리 포함 여부로 SoV 1위가 역전 (24%→43%)
2. 세발·삼륜은 하락 시장의 유일한 상승 세그먼트 (▲11~17% · 50대+ 45%)
3. 공통 관문 = "전기자전거 추천"·가격 노드 — 여정 첫 관문 (직후 70/150)

**추가 조사 권장** (다음 세션 후보)
- "전기자전거 면허" · 여정 최대 마찰 노드 (43회 등장 · PAS vs 스로틀)
- "전기스쿠터" · 인접 시장 확인
```
