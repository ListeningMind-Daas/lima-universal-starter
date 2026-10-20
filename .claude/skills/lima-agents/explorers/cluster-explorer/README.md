# Cluster Explorer

인터랙티브 클러스터 데이터 탐색기 · 기존 cluster-finder 스킬의 UI를 이식.

## 목적

사용자가 <b>정해진 답이 없는 상태</b>에서 · 데이터를 훑어보며 감을 잡을 때. 리포트가 아니라 대시보드.

## 사용자 발화 예

- "전기자전거 클러스터 그래프"
- "○○ 시장 탐색해줘"
- "훑어볼래"
- "브랜드 지형 보여줘"

## 6개 사이드바 모드

- **클러스터** · 커뮤니티 색상·필터
- **검색인텐트** · 정보형/이동형/상업형/거래형
- **트렌드** · 상승/안정/하락 · Sparkline Wall
- **검색노출** · SERP 요소 10종
- **유저특성** · 성별·연령대
- **상업성** · 프리미엄/저비용/정보성/저가치

## 뷰

- 그래프뷰 · d3 force-directed
- 카드뷰 · 클러스터·모드별 카드
- CEP뷰 · 7W 서브그룹 (조회 시 LLM 분류 필요)
- 엔티티뷰 · 브랜드/성분/기타

## 데이터 요구사항

`prepare.py` 실행 시 · 아래 필드 모두 조립:
- seeds · communities · rels · nodes · hub_keywords · bridge_kws
- cluster_labels · detected_entities · cep_grouped · keyword_info

## 이식 소스

- 렌더 템플릿(`_shared/render/inner-template.html` · `_shared/render/shell.html`)은 원본 스킬에서 이식
- prepare 로직 · lima-agents/api/, lib/ 사용

## 크레딧

- cluster_finder · ~56k
- keyword_info(all) · ~11k
- **합계 · 약 67k (실측 67,290)** (기존 cluster-finder와 동일)

## CEP 분류 · 엔티티 감지

MVP · CEP는 빈 dict · 엔티티는 빈 dict로 시작 (Claude가 대화 내에서 · 필요 시 추가 프롬프트로 분류·감지).
UI는 데이터 없으면 자동으로 빈 상태 표시.

## 로컬 테스트

```bash
python3 scripts/run_explorer.py "전기자전거" kr
open ~/Downloads/lima-agents-explorer-전기자전거-<TS>/explorer.html
```
