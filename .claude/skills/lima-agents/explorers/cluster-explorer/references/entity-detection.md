# 엔티티 감지 절차 · WebSearch 검증 (필수)

**이 단계는 절대 스킵 금지**. detected_entities가 없으면 엔티티뷰가 비어 보임.

## 3단계 파이프라인

```
Step 1 · Python 패턴 감지 (후보 추출)
Step 2 · WebSearch 병렬 검증 (max 3 concurrent)
Step 3 · 3카테고리 분류 (brands/ingredients/other)
```

## Step 1 · Python 후보 추출

각 키워드의 <b>첫 단어</b>가 3회 이상 반복되면 엔티티 후보:

```python
from collections import defaultdict
import re

# 카테고리·너무 흔한 단어는 제외 (시장별 조정)
EXCLUDE = {
 '전기자전거', '전동자전거', '자전거', '전기', '전동', '자전차',
 '추천', '가격', '렌탈', '대여', '배달', '배달용', '출퇴근', '출퇴근용',
 '접이식', '미니', '초경량', '국산', '국내산', '성인', '성인용',
 '세발', '삼륜', '중고', 'pas', '스로틀', '쿠팡', '코스트코',
 '싼', '가성비', '종류', '면허'
}

first_word_kws = defaultdict(list)
for kw in all_kws:
 parts = kw.split()
 if not parts: continue
 first = parts[0].strip().lower()
 if len(first) < 2 or first in EXCLUDE: continue
 first_word_kws[first].append(kw)

candidates = [w for w, kws in first_word_kws.items() if len(kws) >= 3]
```

## Step 2 · WebSearch 병렬 검증

각 후보에 대해 <b>"{후보} 뜻 브랜드 회사"</b> 검색.
Claude가 검색 결과를 보고 판별.

**동시 요청 max 3개**. 예:

```
배치 1: 후보 1, 2, 3 병렬 WebSearch
배치 2: 후보 4, 5, 6 병렬 WebSearch
...
```

**검색 쿼리 템플릿** (선택):
- `{후보} 브랜드 회사` · 브랜드 확인용
- `{후보} 성분 뜻` · 성분·재료 확인용
- `{후보} 유튜버 셀럽` · 인물 확인용

## Step 3 · 3카테고리 분류

WebSearch 결과 기반 · Claude가 판별:

| 카테고리 | 판별 기준 |
|---|---|
| **brands**| 실제 회사·제품 브랜드 · 공식 홈페이지 존재 · 판매 이력 |
| **ingredients**| 성분·재료·규격 (예: ISP=Isolated Soy Protein) · 화학·영양 용어 |
| **other**| 인물(셀럽·유튜버) · 모호 (브랜드/성분 경계) · 그 외 |

### 하위 라인 처리
같은 회사 브랜드 하위 라인은 `sub_lines`로 통합. 예:
- 삼천리자전거 (상위)
- 팬텀 (삼천리 전기자전거 하위 라인)
→ 삼천리자전거 항목의 `sub_lines: ["팬텀"]` · 볼륨·products 통합

## 최종 데이터 구조

```json
{
 "brands": [
 {
 "name": "모토벨로",
 "description": "전기자전거 전업 브랜드 (국내) · 단독 쿼리도 카테고리 의도",
 "source_url": "",
 "sub_lines": [],
 "brand_volume": 48356,
 "products": [
 { "keyword": "모토벨로", "volume": 48356 },
 { "keyword": "모토벨로 전기자전거", "volume": 14623 },
 { "keyword": "모토벨로 tx7", "volume": 3400 }
 ],
 "product_count": 3,
 "total_volume": 66379
 }
 ],
 "ingredients": [
 {
 "name": "PAS",
 "description": "Pedal Assist System · 페달 보조 구동방식 (스로틀 방식과 대비)",
 "source_url": "",
 "sub_lines": [],
 "brand_volume": 0,
 "products": [
 { "keyword": "pas 전기자전거", "volume": 6026 },
 { "keyword": "pas 전용 전기자전거", "volume": 1233 }
 ],
 "product_count": 2,
 "total_volume": 7259
 }
 ],
 "other": [
 {
 "name": "전현무",
 "description": "방송인 · 광고 모델 결합 쿼리 (브랜드 미확인 시 총량 제외)",
 "source_url": "",
 "sub_lines": [],
 "brand_volume": 0,
 "products": [
 { "keyword": "전현무 전기자전거", "volume": 3380 }
 ],
 "product_count": 1,
 "total_volume": 3380
 }
 ]
}
```

## 실측 예 (전기자전거 KR · 2026-08-22)

**프로브 코퍼스**: 154개 쿼리 (intent_finder 3시드)
**첫 토큰 빈도 수확 → 웹 검증 후 확정**: 브랜드 27종

**brands (27)**: 삼천리자전거(하위: 팬텀) · 알톤(하위: 니모) · 모토벨로 · 비아지오 · 자이언트 · 메리다 ·
스페셜라이즈드 · 브롬톤 · 샤오미 · AU테크 · 나노휠 · 레이윙 · 스카닉 · 벤츠 · 디스커버리 외
**ingredients 상당 (구동방식)**: PAS · 스로틀
**other (2)**: 서경석 · 전현무 (인물·광고 모델 결합 — 노이즈 처리)

웹 검증 없이는 · "벤츠·디스커버리 같은 라이선스 브랜드를 놓침"·"부릉이 같은 신생 브랜드 오분류" 같은 실수 발생.

## 완료 조건

- [ ] Python 후보 추출 완료 (3회+ 반복)
- [ ] 각 후보 WebSearch 검증 완료
- [ ] 3카테고리 분류 완료 (brands/ingredients/other)
- [ ] 하위 라인 통합 완료
- [ ] JSON 구조 완성 (위 예 참조)
- [ ] `CLUSTER_DATA.detected_entities`에 주입

## 필수 필드 · brands · ingredients · other 3카테고리 공통

**모든 엔티티 항목은 아래 필드를 반드시 포함**. 하나라도 누락하면 뷰가 crash.

| 필드 | 타입 | 필수 |
|---|---|---|
| name | string | 필수 |
| description | string | 필수 (없으면 "") |
| source_url | string | 권장 (없으면 "") |
| sub_lines | array | 필수 (없으면 []) |
| brand_volume | number | 필수 (없으면 0) |
| products | array of {keyword, volume} | 필수 · **문자열 배열 금지** · **엔티티 자체 키워드도 노드에 있으면 포함** |
| product_count | number | 필수 (없으면 0) |
| total_volume | number | 필수 (없으면 0) |

**흔한 실수**:
- `products: ["kw1", "kw2"]` (문자열 배열) → 반드시 `[{keyword: "kw1", volume: 100}, ...]` 형식
- ingredients·other에서 `total_volume` 누락 → 브라우저에서 `undefined.toLocaleString()` crash
- `brand_volume`만 넣고 `total_volume` 생략 → 위와 동일 crash
- **엔티티 이름 자체가 검색어인데 products에 안 넣음** · 예: 브랜드 "모토벨로"가 노드에도 검색어로 존재하는데(48,356) products 리스트엔 "모토벨로 전기자전거 디시" 같은 파생어만 · <b>반드시 엔티티 이름 자체도 products 배열 맨 위에 포함</b> (nodes에 존재하는 경우)

### products 조립 표준 (Python)

```python
def build_products(entity_name, all_nodes):
    # nodes 딕셔너리 · {keyword: volume}
    products = []
    # 1. 엔티티 이름 자체가 노드에 있으면 최우선으로
    if entity_name in all_nodes:
        products.append({"keyword": entity_name, "volume": all_nodes[entity_name]})
    # 2. 엔티티 이름으로 시작하는 다른 노드들 · 볼륨 순
    prefix_kws = [
        (kw, vol) for kw, vol in all_nodes.items()
        if kw != entity_name and kw.startswith(entity_name)
    ]
    prefix_kws.sort(key=lambda x: -x[1])
    products.extend({"keyword": kw, "volume": vol} for kw, vol in prefix_kws)
    return products
```
