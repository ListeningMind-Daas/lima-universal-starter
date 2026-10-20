# Cluster 시각화 렌더링 가이드 · 템플릿 사용 강제

## 절대 원칙 · 반드시 `run_explorer.py --rerender` 사용

- 템플릿 파일: `{SKILL_DIR}/explorers/cluster-explorer/_shared/render/inner-template.html`
- **UI 코드 (HTML·CSS·JS) 직접 작성 금지** · 항상 완전한 템플릿 사용
- **CLUSTER_DATA 주입도 직접 하지 말 것** · `run_explorer.py`가 검증된 헬퍼로 처리
- 실제 흐름 · `cluster_data.json` 저장 → `run_explorer.py --rerender <WORKDIR>` 실행

**직접 조립 시 발생하는 문제**
- `json.dumps(data, indent=2)`의 개행이 · bash/sed/f-string에서 리터럴 `\n`으로 깨짐
- HTML 안에 `\n\n` 문자가 그대로 보임
- `Uncaught SyntaxError: Invalid or unexpected token`
- Artifact가 완전히 broken

## 왜 이 원칙이 절대적인가

Claude가 응답할 때마다 UI를 다시 작성하면:
- **햄버거 JS 핸들러 빼먹음**→ 사이드바 토글 안 됨
- **뷰 토글 4개 중 일부 누락**→ 뷰 안 보임
- **드래그앤드롭 코드 스킵**→ 인터랙션 안 됨
- **CEP·엔티티 렌더 함수 축소**→ 카드 비어 보임

**템플릿에는 이 모든 게 완성되어 있음** · 재작성하면 반드시 뭔가 빠짐.

## 5-Step 흐름

```
1. 템플릿 파일 Read
2. placeholder 8개 치환
3. CLUSTER_DATA JS 객체 주입 (// __DATA_START__ ~ __DATA_END__ 사이)
4. WORKDIR/explorer.html 저장
5. 응답에 코드 블록으로 삽입 (```html ... ```)
```

## Step 1 · 템플릿 Read

```python
from pathlib import Path
SKILL_DIR = "<워크스페이스>/.agents/skills/lima-agents" # 실행 시 실제 경로 확인
tmpl = Path(f"{SKILL_DIR}/explorers/cluster-explorer/_shared/render/inner-template.html").read_text(encoding='utf-8')
```

## Step 2 · placeholder 치환

| Placeholder | 값 |
|---|---|
| `__CATEGORY__` | 시드 라벨 (예: "전기자전거") |
| `__GL__` | 국가 (kr/us/jp) |
| `__NODE_COUNT__` | 총 노드 수 |
| `__CLUSTER_COUNT__` | 클러스터 수 |
| `__HUB_COUNT__` | 허브 수 |
| `__ORIENTATION__` | UNDIRECTED/NATURAL/REVERSE |
| `__HOP__` | 1/2/3 |
| `__SEED1__` | 첫 시드 (배열 첫 요소) | ```python
tmpl = tmpl.replace("__CATEGORY__", CATEGORY)
tmpl = tmpl.replace("__GL__", GL)
tmpl = tmpl.replace("__NODE_COUNT__", str(len(nodes)))
tmpl = tmpl.replace("__CLUSTER_COUNT__", str(len(communities)))
tmpl = tmpl.replace("__HUB_COUNT__", str(len(hub_keywords)))
tmpl = tmpl.replace("__ORIENTATION__", ORIENTATION)
tmpl = tmpl.replace("__HOP__", str(HOP))
tmpl = tmpl.replace("__SEED1__", SEEDS[0])
```

## Step 3 · CLUSTER_DATA 주입

**모든 필수 필드 포함** (하나라도 빠지면 뷰 비어 보임):

```javascript
const CLUSTER_DATA = {
 seeds: ["전기자전거"],
 communities: { "0": [...], "1": [...] },
 rels: [ ["a", "b"], ... ],
 nodes: [ { keyword, volume, community }, ... ],
 hub_keywords: [ ... ], // 필수
 cluster_labels: { "0": { letter, name, total_volume, size }, ... }, // 필수
 bridge_kws: [], // 시드 2개일 때만
 detected_entities: { // 필수! (자주 놓침)
 brands: [...],
 ingredients: [...],
 other: [...]
 },
 cep_grouped: { // 필수! (자주 놓침 · 이름 주의: cep_groups 아님)
 WHY: {...}, WHEN: {...}, WHERE: {...},
 WHILE: {...}, WHOM: {...}, WITH_WHAT: {...}, HOW_FEEL: {...}
 }
};
```

주입 코드:
```python
import re, json
data_js = f"const CLUSTER_DATA = {json.dumps(CLUSTER_DATA, ensure_ascii=False, indent=2)};"
tmpl = re.sub(
 r'// __DATA_START__.*?// __DATA_END__',
 f'// __DATA_START__\n{data_js}\n// __DATA_END__',
 tmpl, flags=re.DOTALL
)
```

## Step 4 · 파일 저장

```python
Path(f"{WORKDIR}/explorer.html").write_text(tmpl, encoding='utf-8')
```

파일도 저장하는 이유:
- 사용자가 브라우저에서 직접 열기 가능 (fallback)
- 재현 · 감사 · 디버깅용

## Step 5 · 응답에 코드 블록으로 삽입

```markdown
### [시장] 클러스터 그래프

[조사원 요약]

**핵심 지표**[지표 표]

**인터랙티브 그래프**:

\`\`\`html
[explorer.html 전체 내용]
\`\`\`

**크레딧**: [실측]
```

Claude Desktop이 이 코드 블록을 자동으로 <b>Artifact</b>로 렌더링 · 오른쪽 패널에 인터랙티브 뷰 표시.

## 템플릿 안 이미 구현된 기능들

**모두 재작성 금지** · 템플릿에 완성되어 있음:

### UI 구성 요소
- 사이드바 · 허브 토글 · 클러스터 칩 리스트 · 키워드 검색
- **햄버거 메뉴** · 사이드바 접기/펼치기 (JS 핸들러 포함)
- 뷰 토글 4개 · 그래프뷰 · 카드뷰 · CEP뷰 · 엔티티뷰
- 툴팁 · fixed position · clientX/Y 좌표

### 그래프뷰
- d3.js force simulation · 클러스터 중력
- 파스텔 팔레트 22색
- 노드 크기 상한 · min 2.5 · max 14
- 엣지 · stroke-width 0.4 · 확대 시 화면 고정
- 라벨 · 노드 우측 정중앙 · 화면 크기 고정 (1/k 역보정)
- 줌 배율 따라 라벨 페이드인 (선형 곡선)
- 클러스터 격리 모드 (칩 클릭 · 자동 줌인)
- 클러스터 자동 이름 생성 (cluster_labels 데이터에서)
- 허브 도넛 스타일 (외곽선만)

### 카드뷰
- 클러스터별 카드 · A/B/C 알파벳 라벨
- 내부 스크롤 · 전체 키워드
- 허브 표시 없음 (요구사항)

### CEP뷰
- 7W 카드 · 글라스모피즘
- 커스텀 SVG 아이콘 7개 (WHY·WHEN·WHERE·WHILE·WHOM·WITH_WHAT·HOW_FEEL)
- 2단계 트리 (W → 서브그룹 → 키워드)
- 서브그룹 hover · − 제거 · ⇢ 이동 버튼
- 드래그 · 다른 W로 이동
- 카드 세로 560px 고정 · 내부 스크롤

### 엔티티뷰
- 3카테고리 카드 · 브랜드/성분/기타 · 글라스모피즘
- 커스텀 SVG 아이콘 (태그·플라스크·사용자)
- 개별 엔티티 · hover 액션 (− ⇢)
- 드래그앤드롭 · 병합 (엔티티 위) · 이동 (카테고리 위)
- Undo/Reset 아이콘 (↩ ⟲)
- Undo 스낵바 (5초)
- 카테고리 이동 모달

### 공통 (전 뷰)
- 모든 인터랙션 JS 이미 있음
- Ctrl 스크롤·확대·팬
- 반응형

## 검증 · 응답 전 반드시 확인

- [ ] 템플릿 파일을 Read로 읽음 (직접 작성 X)
- [ ] placeholder 8개 모두 치환
- [ ] CLUSTER_DATA 필수 필드 모두 포함 (특히 detected_entities · cep_grouped)
- [ ] `// __DATA_START__` ~ `// __DATA_END__` 사이에 데이터 주입 (다른 위치 X)
- [ ] 응답에 완전한 HTML 코드 블록 (```html ... ```)
- [ ] 파일도 저장 (fallback)

## 실행 스크립트 표준

이 스킬은 이 스크립트를 참고해 직접 실행:

```python
import json, re
from pathlib import Path

SKILL_DIR = "{SKILL_DIR}"
WORKDIR = "{WORKDIR}"
CATEGORY = "{CATEGORY}"
GL = "{GL}"
SEEDS = ["전기자전거"]
ORIENTATION = "UNDIRECTED"
HOP = 2

# CLUSTER_DATA (Phase 4에서 준비된 것)
with open(f"{WORKDIR}/cluster_data.json") as f:
 CLUSTER_DATA = json.load(f)

# 템플릿 로드
tmpl = Path(f"{SKILL_DIR}/explorers/cluster-explorer/_shared/render/inner-template.html").read_text(encoding='utf-8')

# placeholder 치환
tmpl = tmpl.replace("__CATEGORY__", CATEGORY)
tmpl = tmpl.replace("__GL__", GL)
tmpl = tmpl.replace("__NODE_COUNT__", str(len(CLUSTER_DATA["nodes"])))
tmpl = tmpl.replace("__CLUSTER_COUNT__", str(len(CLUSTER_DATA["communities"])))
tmpl = tmpl.replace("__HUB_COUNT__", str(len(CLUSTER_DATA["hub_keywords"])))
tmpl = tmpl.replace("__ORIENTATION__", ORIENTATION)
tmpl = tmpl.replace("__HOP__", str(HOP))
tmpl = tmpl.replace("__SEED1__", SEEDS[0])

# CLUSTER_DATA 주입
data_js = f"const CLUSTER_DATA = {json.dumps(CLUSTER_DATA, ensure_ascii=False, indent=2)};"
tmpl = re.sub(
 r'// __DATA_START__.*?// __DATA_END__',
 f'// __DATA_START__\n{data_js}\n// __DATA_END__',
 tmpl, flags=re.DOTALL
)

# 저장
Path(f"{WORKDIR}/explorer.html").write_text(tmpl, encoding='utf-8')
print(f"저장: {WORKDIR}/explorer.html · {len(tmpl):,} bytes")

# 응답에 삽입 · Bash에서 파일 내용 출력해서 코드 블록으로
```

응답에 삽입 (Bash):
```bash
cat "$WORKDIR/explorer.html"
```
