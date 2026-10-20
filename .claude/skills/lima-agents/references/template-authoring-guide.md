# 새 템플릿 추가 가이드 · 개발자 분업용

## 원칙

각 질문 코드 = `reports/<code-slug>/` 폴더 하나 · **완전 자립**.
- 다른 템플릿에 의존 X (`_shared/`만 공용)
- 폴더 추가·삭제로 스킬 확장·축소

## 새 템플릿 만드는 5단계

### 1. 폴더 생성

```bash
mkdir -p reports/c1-rising-brand
cd reports/c1-rising-brand
```

폴더명 규칙 · `<코드소문자>-<슬러그>` · 예 · `b1-segment-intent`, `c4-painpoint`

### 2. README.md · 기획 문서

```markdown
# C-1 · 라이징·경쟁 브랜드

## 답하는 질문
"이 시장에서 새로 뜨는 브랜드는? 자사 대비 경쟁사는?"

## 목표 청중
브랜드 매니저 · 신규 진입 검토 · 경쟁 대응

## 핵심 인사이트 3가지
1. 볼륨은 낮지만 트렌드 상승 브랜드 (라이징 후보)
2. 자사 브랜드 vs 경쟁 브랜드 볼륨 격차
3. 각 브랜드의 검색 인텐트 분포 (인지 vs 구매)

## 필요 데이터
- cluster_finder (관계 그래프)
- keyword_info (data_type=all · volume_trend·intents·demography)
- WebSearch (브랜드 검증)

## UI 구조
- 헤더 · 카테고리·조사 기간·KPI 4개
- 섹션 1 · 라이징 브랜드 TOP 10 (볼륨·트렌드·인텐트 매트릭스)
- 섹션 2 · 브랜드별 상세 카드
- 섹션 3 · 실행 권고

## 크레딧 예상
cluster_finder 56k + keyword_info 11k = 약 67k (실측 67,290)
```

### 3. schema.json · 데이터 계약

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "C-1 Data Contract",
  "type": "object",
  "required": ["meta", "brands"],
  "properties": {
    "meta": {
      "type": "object",
      "properties": {
        "category": {"type": "string"},
        "gl": {"type": "string"},
        "total_nodes": {"type": "integer"},
        "total_credits": {"type": "integer"},
        "generated_at": {"type": "string"}
      }
    },
    "brands": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "volume", "trend"],
        "properties": {
          "name": {"type": "string"},
          "volume": {"type": "number"},
          "trend": {"type": "number"},
          "intents": {"type": "object"},
          "description": {"type": "string"}
        }
      }
    }
  }
}
```

### 4. prepare.py · 데이터 준비

```python
"""C-1 · 라이징 브랜드 데이터 준비."""
from api.client import DaasClient
from api import cluster_finder, keyword_info
from lib.entity_detector import extract_candidates, assemble_entity


def prepare(category: str, gl: str, api_key: str) -> dict:
    """schema.json에 부합하는 dict 반환."""
    c = DaasClient(api_key)
    cf = cluster_finder.fetch(c, category, gl=gl, limit=5000, hop=2)
    all_kws = cluster_finder.unique_keywords_from_nodes(cf)
    info_list, cost_ki = keyword_info.fetch_all(c, all_kws, gl=gl, data_type="all")
    info_by_kw = keyword_info.index_by_keyword(info_list)

    # ...엔티티 감지·브랜드 필터링·트렌드 계산...
    brands = []
    # 여기 로직 구현

    return {
        "meta": {
            "category": category,
            "gl": gl,
            "total_nodes": len(all_kws),
            "total_credits": cf["cost_detail"]["total_cost"] + cost_ki,
            "generated_at": "..."  # 호출 측에서 채우거나
        },
        "brands": brands
    }
```

### 5. template.html · 리포트 뷰

- `reports/_shared/base.css` `<link>` 로 import
- `reports/_shared/chart-helpers.js` 사용 — 차트는 `limaDonut`·`limaHBar`·`limaVBar`로 inline SVG를 그린다. Chart.js 등 외부 차트 라이브러리·CDN은 쓰지 않는다(`listeningmind-universal/references/_shared-core.md` §7)
- 데이터는 `__DATA_JSON__` 자리에 dict → JSON 문자열 주입
- 페이지 로드 시 `const DATA = /* injected */; renderReport(DATA);` 로 채움

```html
<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="UTF-8"><title>C-1 · 라이징 브랜드 · __CATEGORY__</title>
<style>/* base.css inline · 배포 편의 · 또는 <link> import */</style>
</head><body>
<div class="wrap">
  <header class="top">
    <div class="eyebrow">C-1 · 라이징·경쟁 브랜드</div>
    <h1>__CATEGORY__ · __GL__</h1>
    <div class="meta-row"><!-- chips --></div>
  </header>
  <!-- 섹션들 -->
</div>
<script>
// __DATA_START__
const DATA = /* CLAUDE: 여기 dict → JSON 주입 */ null;
// __DATA_END__
// 렌더 함수 여기
</script>
</body></html>
```

## 로컬 테스트

```bash
python3 scripts/run_analysis.py C-1 "전기자전거" kr
open ~/Downloads/lima-agents-C-1-*/report.html
```

## 완료 체크리스트

- [ ] `README.md` · 질문·데이터·UI 구조 명시
- [ ] `schema.json` · JSON Schema 유효
- [ ] `prepare.py` · api/·lib/ 사용 · 예외 처리
- [ ] `template.html` · base.css 스타일 · inline SVG 차트(외부 CDN 없음) · 데이터 주입 마커
- [ ] 로컬 테스트 · 실제 데이터로 정상 렌더
- [ ] `question-frame.md` 표에 · 상태 "✅ 지원"으로 갱신
