# 마케팅팀 표준 질문 프레임 · A~D 14개

**출처** · 마케팅팀 표준 조사 질문 프레임(A~D)

이 표는 · 사용자 발화 → 질문 코드 매핑 · 각 코드는 `reports/<code-slug>/`에 구현.

## A · 시장 흐름

| 코드 | 질문 | 필요 데이터 | 템플릿 폴더 | 상태 |
|---|---|---|---|---|
| A-1 | 메인 키워드 월별 검색량 추이·전년 대비 증감 | keyword_info.monthly_volume | a1-volume-trend | 준비 중 |
| A-2 | 메인 키워드 검색자 성별·연령 분포 | keyword_info.demography | a2-demography | 준비 중 |
| A-3 | 소비자 검색 목적·인텐트 | cluster_finder + CEP 7W | a3-search-intent | 준비 중 |
| A-4 | 인지→구매 검색 경로 | path_finder | a4-search-path | 준비 중 |
| A-5 | 브랜드 비보조 인지도 (검색 점유율) | cluster_finder + WebSearch | a5-brand-awareness | 준비 중 |

## B · 타겟 심층

| 코드 | 질문 | 필요 데이터 | 템플릿 폴더 | 상태 |
|---|---|---|---|---|
| **B-1** | **연령별·성별 관심사·KBF 차이** | cluster_finder + keyword_info.demography + CEP HOW_FEEL | **b1-segment-intent** | **✅ MVP** |

## C · 브랜드 맵

| 코드 | 질문 | 필요 데이터 | 템플릿 폴더 | 상태 |
|---|---|---|---|---|
| C-1 | 라이징·경쟁 브랜드 | detected_entities.brands · volume_trend | c1-rising-brand | 준비 중 |
| C-2 | 자사 vs 경쟁 검색 점유율 | detected_entities · volume | c2-share-of-search | 준비 중 |
| C-3 | 자사 검색 전환·이탈 구간 | path_finder | c3-conversion-path | 준비 중 |
| C-4 | 자사·경쟁 페인포인트·부정 키워드 | CEP HOW_FEEL 부작용·우려 서브그룹 | c4-painpoint | 준비 중 |

## D · 전략 제안

| 코드 | 질문 | 필요 데이터 | 템플릿 폴더 | 상태 |
|---|---|---|---|---|
| D-1 | 카테고리 선점 CEP | cluster_finder + CEP 7W 전체 | d1-cep-preemption | 준비 중 |
| D-2 | 검색 여정 노출 점유율 도메인 | serp 커넥터 | d2-serp-share | 미지원 |
| D-3 | 자사 강점·부족 검색 키워드 | detected_entities + volume | d3-strength-gap | 준비 중 |
| D-4 | 함께 검색되는 라이징 CEP·연관 아이템 | CEP WITH_WHAT + rels | d4-rising-cep | 준비 중 |

## 사용자 발화 → 코드 라우팅 (Claude가 수행)

**정확한 매치**
- "연령별", "성별", "세그먼트 인텐트", "KBF" → B-1
- "라이징 브랜드", "신흥 브랜드" → C-1
- "선점할 CEP", "카테고리 진입점" → D-1

**애매한 매치**
- "○○ 시장 분석" · 광범위 → 사용자에게 "어떤 각도로? 세그먼트·브랜드·CEP·페인포인트?" 확인

**MVP 시점 응답**
- B-1이면 실제 진행
- 다른 코드면 · "이 질문은 곧 준비 예정입니다 · 대신 B-1 (연령별 세그먼트 분석) 가능"
