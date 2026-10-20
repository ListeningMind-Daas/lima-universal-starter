# B-1 · 연령별·성별 관심사·KBF 차이 분석

## 답하는 질문

이 시장에서 · 연령(연령대) · 성별로 · 어떤 관심사·KBF(Key Benefit Factor)의 차이가 있나?

## 목표 청중

- 마케팅 전략가 · 세그먼트 타겟팅 결정
- 크리에이티브·인플루언서·매체 선정 담당
- 상품 기획 · 세그먼트별 니즈 파악

## 핵심 인사이트 3가지

1. **세그먼트 지배도** · 어느 연령대·성별이 가장 활발한지 · 총 볼륨 점유율
2. **KBF (편익 요인) 격차** · 세그먼트마다 무엇을 중요시하는지 (예: 20대=맛·30대=기능·40대=안전성)
3. **관심 키워드 대조** · 세그먼트별 TOP 10 키워드 · 겹치는 것 vs 고유한 것

## 필요 데이터

- `cluster_finder` · 관계 그래프 (limit=5000, hop=2)
- `keyword_info(data_type=all)` ·
  - `demography.a13/a20/a25/a30/a40/a50` · 연령대 태그
  - `demography.m_gender/f_gender` · 성별 태그
  - `ads_metrics.volume_avg` · 월평균 검색량
  - `intents` · 인텐트 4개 (i/n/c/t)

## UI 구조 (template.html)

1. **헤더** · 카테고리·조사 기간·데이터 규모·KPI 4개
2. **Sticky 탭** · [전체] [연령대별] [성별] [KBF 매트릭스] [실행 권고]
3. **각 탭**
   - 전체 · 세그먼트 볼륨 도넛 · 세그먼트별 KPI
   - 연령대별 · 그룹별 TOP 키워드 bar · KBF bar
   - 성별 · 남녀 대조 bar · 성별×연령 매트릭스
   - KBF · CEP HOW_FEEL 서브그룹 · 세그먼트별 편익 요인 랭킹
   - 실행 권고 · 조사원 문구 · 세그먼트별 크리에이티브 방향

## 크레딧 예상

- cluster_finder · 시드 1개 · hop=2 · limit=5000 · **~56k** (150 + 고유 키워드수×50)
- keyword_info · 1000~1500 kws · data_type=all · **~11~15k** (키워드수×10)
- **합계 · 약 67k (실측 67,290 = 56,100 + 11,190)**

## 로컬 테스트

```bash
python3 scripts/run_analysis.py B-1 "전기자전거" kr $API_KEY
open ~/Downloads/lima-agents-B-1-전기자전거-*/report.html
```
