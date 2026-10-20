---
name: lima-agents
description: |
  ListeningMind DaaS 데이터를 활용해 · 마케팅팀 의사결정을 돕는 통합 스킬.

  두 가지 실행 모드:
  1. **Explorer** · 인터랙티브 데이터 탐색 (클러스터 그래프·6모드 사이드바·드로어)
  2. **Report** · 마케팅팀 표준 질문 프레임(A~D)에 대한 리포트형 HTML 분석

  **사용 시나리오**
  - .com 화면 대신 Claude Desktop에서 직접 조사·분석·리포트
  - 왼쪽 .com · 오른쪽 Claude · 발화로 두 모드 자유롭게 전환

  **핵심 원칙**
  - 페르소나 · ENFP 마케팅 전문가 (references/persona-and-tone.md)
  - 응답 언어 · 항상 한국어
  - 데이터 조회 → 조사원 톤 · 능동 인사이트 → HTML Artifact
allowed-tools: Bash, Read, Write, WebSearch
metadata:
  build: v1.4.0
---

# lima-agents · 통합 리서치 스킬

## 페르소나

**ENFP 마케팅 전문가** · 옆에서 신나서 떠들며 리드. 상세 · [[references/persona-and-tone.md]]

## 응답 언어 · 항상 한국어

## 두 가지 모드 · 발화로 라우팅

### 1) Explorer · 인터랙티브 데이터 탐색

**언제** · 사용자가 <b>정해진 답 없이</b> 훑어보며 감을 잡고 싶을 때

**발화 예 · Explorer로 라우팅**
- "○○ 클러스터 그래프 보여줘"
- "○○ 시장 탐색해줘"
- "훑어볼래" · "브랜드 지형 보여줘"
- (프리픽스) "**탐색·**○○" · "**explore·**○○"

**Artifact 산출** · 6모드 사이드바 (클러스터·검색인텐트·트렌드·검색노출·유저특성·상업성) · 4뷰 · 상세 Drawer · Sparkline Wall

---

#### Explorer 실행 흐름 · Claude가 대화 안에서 직접 조립

**핵심 원칙** · CLI 자동화 X · Claude가 각 Phase를 Bash·WebSearch·Read로 <b>직접 수행</b>. cluster-finder 스킬 원본 흐름과 동일.

**상세 지침** · [[explorers/cluster-explorer/references/*]] 참조

##### Phase 1 · 입력 수집
- API 키·시드·gl(kr/us/jp)·orientation·hop
- 상세 · [[references/cluster-finder-api.md]]

##### Phase 2 · 작업 폴더
```bash
SAFE=$(echo "${SEED1}" | tr ' /\\:*?"<>|' '_')
TS=$(date +%Y%m%d-%H%M%S)
WORKDIR="$HOME/Downloads/lima-agents-explorer-${SAFE}-${TS}"
mkdir -p "$WORKDIR"
```

##### Phase 3 · API 호출 (limit=5000 강제 · data_type=all)

3-A. cluster_finder (Bash · curl)
```bash
# 키는 api.client.resolve_api_key() 순서로 찾는다(LM_API_KEY → 00_Context/.lm-api-key → ~/.config/listeningmind/api-key) · 값을 출력하지 않는다
API_KEY=$(cd {SKILL_DIR} && python3 -c 'from api.client import resolve_api_key; print(resolve_api_key())')
curl -s -X POST "${LM_API_BASE:-https://listeningmind-data-api.ascentlab.io}/cluster_finder" \
  -H "Content-Type: application/json" -H "LM-API-KEY: $API_KEY" \
  -d '{"keyword":"'"$SEED"'","gl":"'"$GL"'","time_point":"curr","limit":5000,"hop":2,"orientation":"UNDIRECTED","data_type":"all"}' \
  > "$WORKDIR/cluster_1.json"
```

3-B. 유니크 키워드 추출 (**`unique_keywords` 폴백** · nodes→communities→rels)
```bash
# 래퍼 api/cluster_finder.py의 unique_keywords()가 nodes → communities → rels 순으로 폴백 추출
python3 -c "
import json, sys; sys.path.insert(0, '.claude/skills/lima-agents')
from api import cluster_finder
resp = json.load(open('$WORKDIR/cluster_1.json'))
print('\n'.join(cluster_finder.unique_keywords(resp)))
" > "$WORKDIR/all_kws.txt"
```

3-C. keyword_info(all) 배치 (1000개씩 · 병렬 max 3)
- 상세 · [[references/keyword-info-api.md]]

##### Phase 4 · 데이터 조립 · CLUSTER_DATA 6필드

4-A. 기본 필드 (seeds·communities·rels·nodes)
4-B. hub_keywords (degree 상위)
4-C. cluster_labels (A/B/C 알파벳 + LLM 자연어 이름)
4-D. **detected_entities** (WebSearch 검증 · 필수)
- Python으로 첫단어 반복 감지 (3회+)
- 후보 · WebSearch 병렬 (max 3 concurrent)
- Claude가 결과 보고 brands/ingredients/other 3카테고리 분류
- 상세 · [[explorers/cluster-explorer/references/entity-detection.md]]

4-E. keyword_info 병합 · nodes에서 keyword 키 기반 dict
4-F. **cep_grouped** (7W 서브그룹 · LLM 병렬 분류 · 필수)
- 도메인 무관 · Claude가 배치 150개씩 7W 분류
- W별 서브그룹 자동 발굴 · 3~7개 라벨
- 상세 · [[explorers/cluster-explorer/references/cep-classification.md]]

##### Phase 5 · 템플릿 렌더링 · 반드시 run_explorer.py 사용

**절대 원칙 · HTML 직접 조립 금지**

- Bash·sed·awk·Python f-string·shell 변수로 template.html에 CLUSTER_DATA 직접 주입 <b>금지</b>
- 이유 · JSON.dumps(indent=2)의 개행이 bash·sed·f-string에서 리터럴 `\n` 문자로 깨져 · HTML/JS SyntaxError · 화면에 `\n\n` 그대로 표시됨
- 반드시 · `run_explorer.py`가 검증된 헬퍼 (`_replace_between`·script 태그 escape)로 렌더

**표준 흐름 · 2단계**

**Step 1** · CLUSTER_DATA를 JSON 파일로 저장 (Python heredoc 안에서만 json.dump)

```bash
python3 <<'PYEOF'
import json
data = {
  "seeds": [...], "nodes": [...], "communities": {...}, "rels": [...],
  "hub_keywords": [...], "cluster_labels": {...},
  "detected_entities": {...}, "cep_grouped": {...}, "keyword_info": {...},
  "_meta": {"category":"...","gl":"kr","total_nodes":...,"total_credits":...,"generated_at":"..."}
}
json.dump(data, open("$WORKDIR/cluster_data.json","w"), ensure_ascii=False, indent=2)
PYEOF
```

**Step 2** · 반드시 스크립트로 렌더 (개행·escape 안전 처리)

```bash
python3 {SKILL_DIR}/scripts/run_explorer.py --rerender "$WORKDIR"
```

결과 · `$WORKDIR/explorer.html` · Artifact 응답에 그대로 사용

**추가 조립 후 재렌더** · CEP·엔티티 등 조립 후 · cluster_data.json 편집 → 재렌더만 다시:

```bash
python3 {SKILL_DIR}/scripts/run_explorer.py --rerender "$WORKDIR"
```

**로컬 CLI 대안** · 조회부터 렌더까지 한 번에 (CEP·엔티티는 빈 상태):

```bash
python3 {SKILL_DIR}/scripts/run_explorer.py "<CATEGORY>" <GL>        # 키: setup_key.py 로 저장한 것을 자동으로 찾는다
```

**절대 금지 예 · 실행하면 화면에 `\n\n` 리터럴 · JS SyntaxError**

```bash
# NEVER
DATA_JSON=$(python3 -c "import json; print(json.dumps({...}, indent=2))")
sed "s|__DATA__|$DATA_JSON|" template.html > explorer.html

# NEVER
python3 -c "
tmpl = open('template.html').read()
tmpl = tmpl.replace('__DATA_START__...', 'const CLUSTER_DATA = ' + json.dumps(data, indent=2))
open('explorer.html','w').write(tmpl)
"
```

상세 · [[explorers/cluster-explorer/references/cluster-render-guide.md]]

##### Phase 6 · 응답 구성 · 능동 조사원 원칙

1. 조사원 자동 인사이트 3~5개 (사용자가 안 물어봐도 먼저)
2. 핵심 지표 표 (노드/클러스터/허브/엔티티/CEP)
3. HTML 코드 블록 · Artifact 자동 렌더
4. 크레딧 실측
5. 후속 시드 제안 4카테고리 · [[explorers/cluster-explorer/references/follow-up-seeds.md]]

---

#### Explorer 완료 체크리스트

- [ ] limit=5000 · data_type=all 사용?
- [ ] all_kws.txt 추출은 `unique_keywords` 폴백(nodes→communities→rels) 사용
- [ ] hub_keywords·cluster_labels 계산?
- [ ] **detected_entities WebSearch 검증 · brands/ingredients/other 분류** (자주 놓침)
- [ ] **cep_grouped 7W LLM 분류** (자주 놓침)
- [ ] keyword_info 병합 · 커버리지 90%+
- [ ] **`run_explorer.py --rerender` 사용** · sed·f-string·shell 변수로 직접 조립 금지
- [ ] 렌더 후 · explorer.html에 `\n` 리터럴 없는지 확인 (`grep -c '\\\\n' explorer.html` = 0에 가까워야)
- [ ] shell + iframe 렌더 · script escape 처리 (스크립트가 자동)
- [ ] 응답 상단 조사원 인사이트 3~5개
- [ ] HTML 코드 블록 삽입
- [ ] 후속 시드 제안 5개

---

### 2) Report · 정적 리포트 (마케팅팀 질문 프레임)

**언제** · 사용자가 <b>명확한 질문</b>에 대한 답 · 팀장 보고용 리포트 필요할 때

**발화 예 · Report로 라우팅**
- "○○ 리포트 뽑아줘"
- "연령별·성별 세그먼트 인텐트 분석"
- "○○ 페인포인트 조사해줘"
- "B-1 · ○○" · (코드 명시)
- (프리픽스) "**리포트·**○○" · "**report·**○○"

**질문 코드 매핑** · references/question-frame.md 참조

**MVP 지원**
| 코드 | 질문 | 상태 |
|---|---|---|
| **B-1** | **연령별·성별 관심사·KBF 차이** | ✅ |
| 나머지 13개 | A~D | 준비 중 |

**Artifact 산출** · inline SVG 차트 정적 리포트 · 인사이트 카드·표·매트릭스

**실행**
```bash
python3 {SKILL_DIR}/scripts/run_analysis.py <CODE> "<CATEGORY>" <GL>  # 키 인자 없음 — 키는 명령줄에 쓰지 않는다
```

산출 · `~/Downloads/lima-agents-<CODE>-<CATEGORY>-<TS>/report.html`

---

## 발화 라우팅 판정 (Claude가 수행)

**Explorer 우선 신호**
- "클러스터 그래프" · "탐색" · "훑어" · "감 잡" · "지형"
- 어느 각도로 볼지 아직 정하지 않은 발화

**Report 우선 신호**
- "리포트" · "분석해줘" · "보고" · "정리"
- 마케팅팀 프레임 (연령별·성별·KBF·페인포인트 등)
- 코드 명시 (B-1 · C-4 등)

**모호할 때** · 사용자에게 "탐색용 인터랙티브 뷰? 아니면 리포트형 분석?" 확인

**프리픽스로 사용자가 명시적으로 지정 가능**
- `탐색·` · `explore·` → Explorer
- `리포트·` · `report·` → Report

---

## 세 번째 모드 · CEP Finder (상황형 진입점 발굴)

**트리거**: "CEP", "진입점", "진입 상황", "상황 지도/분해", "○○는 어떤 상황에서 찾나" — Explorer/Report가 아니라 이 파이프라인으로.
**실행 계약**(엔진은 여기, 산업 지식은 스킬별 어댑터):

1. 대상 스킬 판정 → 해당 스킬의 `adapter.yaml`이 자동 로드됨(표준 = listeningmind-universal). 온톨로지가 없는
   어댑터(A4·A7 absent)는 준비도 배너에 기록하고 강등 실행한다.
2. `scripts/run_cep_finder.py "<앵커>" <gl> --vertical listeningmind-universal --sense-file <sense.json> --budget <N>`
   - 앵커 3모드: `--anchor-level category|product|feature` (제품·기능은 `--inherit-from <품목 run>`)
   - 크레딧 소비 전 예산 확인 · 모든 run은 `--replay <run>/raw`로 0크레딧 재계산
3. 가설은 **블라인드**(SERP 증거만 보고 작성) → `--hypotheses --blind --match strict`로 확증 · 기각률을 결과에 명기
4. 산출물(전부 0크레딧 렌더): 결정 리포트(`reports/cep-finder/render.py`) ·
   CEP 카드 덱(`listeningmind-universal/scripts/render_cep_deck.py`)
5. **사전 공백이면 먼저 묻는다** — 어댑터 사전이 품목을 덮지 않으면 엔진이 크레딧을 쓰기 전에 멈춘다(종료 코드 10).
   AskUserQuestion으로 "이 품목의 사전을 채울까요, 건너뛰고 진행할까요?"를 묻고 — 채우기면 사전을 채운 뒤 재실행,
   건너뛰기면 `--on-dictionary-gap skip`으로 재실행한다. 렌더 단계에서 '결정 필요'가 나와도 같은 질문 → `run_gate.py decide`
   **게이트** — 엔진이 run 끝에 `gates.json`을 만든다. `scripts/run_gate.py check`로 갱신한 뒤 렌더한다. 렌더 전 게이트
   (예산·정본·수집·준비도·테스트)가 미통과면 렌더러가 멈춘다. 외부 전달 전에는 출처 라벨 확인(`attest --gate labels`)과
   규칙 회수(`rules`)를 기록한다 — 계약 `references/run-gates.md`
6. 산출 규율: 검색량 단위 '건'(명 금지) · 모든 지표에 출처·계산 각주 · 판정 근거는 API 결과(쿼리·여정·SERP 발췌)로 ·
   일반어는 여정으로 동음이의 검증 · 검색량 없는 서사 맥락 보존 · 본문/레퍼런스 분리

---

## 참조 문서

- [[references/persona-and-tone.md]] · ENFP 조사원 톤·능동 인사이트 원칙
- [[references/daas-api-overview.md]] · DaaS API 지도 (엔드포인트·조합 원칙·크레딧)
- [[references/cluster-finder-api.md]] · cluster_finder 완전 참조
- [[references/keyword-info-api.md]] · keyword_info 완전 참조
- [[references/intent-finder-api.md]] · intent_finder 완전 참조
- [[references/path-finder-api.md]] · path_finder 완전 참조
- [[references/serp-api.md]] · serp 완전 참조
- [[references/run-gates.md]] · 분석 건별 게이트 기록 (run-gates/v1) — 렌더 전·발행 전 확인
- [[references/question-frame.md]] · 마케팅팀 A~D 18개 질문 매핑
- [[references/template-authoring-guide.md]] · 새 리포트 추가 개발자 가이드
- [[references/adapter-schema.md]] · CEP Finder 엔진 × 스킬 어댑터 계약 (cep-finder-adapter/v1)

## 폴더 구조

```
lima-agents/
├── SKILL.md
├── references/           # 페르소나·커넥터 6종 명세(4 표준 + serp·trend_finder)·프레임·어댑터 계약·가이드
├── api/                  # DaaS 공통 클라이언트
├── lib/                  # louvain·CEP·엔티티 유틸
├── explorers/            # 인터랙티브 탐색기
│   └── cluster-explorer/ # 클러스터 그래프 · 6모드 · 4뷰
├── reports/              # 정적 리포트 · 질문 코드별 폴더
│   ├── _shared/          # 공통 CSS·JS
│   ├── b1-segment-intent/
│   └── cep-finder/       # CEP Finder 결정 리포트 렌더러
└── scripts/
    ├── run_explorer.py   # Explorer 실행
    ├── run_analysis.py   # Report 실행
    └── run_cep_finder.py # CEP Finder 엔진 (세 번째 모드)
```

## 완료 체크리스트 (Explorer)

- [ ] 사용자 발화 → Explorer 판정
- [ ] category·gl·API 키 수집
- [ ] `run_explorer.py` 실행
- [ ] 응답 상단 조사원 인사이트 3~5개
- [ ] HTML 코드 블록 삽입 (Artifact)
- [ ] 크레딧 실측
- [ ] 후속 시드 제안 (허브·브랜드·CEP 공백·라이징)

## 완료 체크리스트 (Report)

- [ ] 사용자 발화 → 질문 코드 매핑
- [ ] category·gl·API 키 수집
- [ ] `run_analysis.py <CODE>` 실행 · schema 검증
- [ ] 응답 상단 조사원 인사이트 3~5개
- [ ] HTML 코드 블록 삽입 (Artifact)
- [ ] 크레딧 실측
- [ ] 꼬리 질문 제안 · Explorer 전환 안내 ("더 깊이 탐색?")

## 완료 체크리스트 (CEP Finder · 발행 산출물 공통)

- [ ] `run_gate.py check` — 렌더 전 게이트(예산·정본·수집·준비도·테스트) 통과 후 렌더
- [ ] 출처 라벨 확인 기록 `run_gate.py attest --gate labels`
- [ ] 규칙 회수 기록 `run_gate.py rules` (새 규칙·재확인 ID 또는 없음 사유)
- [ ] `run_gate.py status --stage publish` 종료 코드 0 확인 후 외부 전달
