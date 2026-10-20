# 탐색 세션 · 다중 시드 누적 조회

## 개념

첫 시드로 그래프 조회 → 조사원이 결과 보고 후속 시드 3~5개 제안 → 사용자가 고르면 추가 조회 → HTML 안 탭으로 누적. 시장을 하나의 시드가 아니라 <b>탐색 여정</b>으로 다룸.

## 세션 구조

한 세션 = 하나의 WORKDIR · 여러 시드 조회가 누적.

```
$WORKDIR/                                # 첫 시드로 만든 폴더
├── sessions.json                        # 시드 이력 · 탐색 로그 · 크레딧 누적
├── seed_1/                              # 첫 시드
│   ├── cluster_1.json                   # cluster_finder 응답
│   ├── all_kws.txt
│   ├── kw_info.json
│   └── cluster_data.json                # 완성된 CLUSTER_DATA
├── seed_2/                              # 두 번째 시드 (사용자 선택 후 조회)
│   ├── cluster_1.json
│   └── ...
├── seed_3/
│   └── ...
└── cluster-viz.html                     # 모든 시드가 탭으로 담긴 통합 뷰
```

WORKDIR 이름은 첫 시드 기준:
```bash
SAFE=$(echo "${FIRST_SEED}" | tr ' /\\:*?"<>|' '_')
TS=$(date +%Y%m%d-%H%M%S)
WORKDIR="$HOME/Downloads/lima-agents-explorer-${SAFE}-${TS}"
```

## sessions.json 스키마

```json
{
  "workdir": "~/Downloads/lima-agents-explorer-전기자전거-20260822-104900",
  "gl": "kr",
  "started_at": "2026-08-22T10:49:00",
  "total_credits": 56010,
  "seeds": [
    {
      "index": 1,
      "seed": "전기자전거",
      "hop": 2,
      "orientation": "UNDIRECTED",
      "queried_at": "2026-08-22T10:49:00",
      "credits": 29010,
      "rels_count": 498,
      "nodes_count": 460,
      "clusters_count": 3,
      "workdir_sub": "seed_1",
      "reason": "user provided (first seed)"
    },
    {
      "index": 2,
      "seed": "모토벨로",
      "hop": 2,
      "orientation": "UNDIRECTED",
      "queried_at": "2026-08-22T10:55:00",
      "credits": 27000,
      "rels_count": 500,
      "nodes_count": 450,
      "clusters_count": 4,
      "workdir_sub": "seed_2",
      "reason": "follow-up: 감지된 브랜드 카테고리 (경쟁사 딥다이브)"
    },
    {
      "index": 3,
      "seed": "세발 전기자전거",
      "hop": 2,
      "orientation": "UNDIRECTED",
      "queried_at": "2026-08-22T11:02:00",
      "credits": 15000,
      "rels_count": 280,
      "nodes_count": 250,
      "clusters_count": 3,
      "workdir_sub": "seed_3",
      "reason": "follow-up: 라이징 세그먼트 딥다이브"
    }
  ]
}
```

시드 1은 실측(2026-08-22 · limit 500), 시드 2·3의 수치는 형식 예시 — 실제 값은 항상 응답 `cost_detail` 기준.

## 세션 재개

사용자가 이전 세션 이어서 하려면:
1. WORKDIR 경로 지정 (사용자 발화 or 최신 자동 감지)
2. `sessions.json` 읽어서 이력 파악
3. 각 `seed_N/cluster_data.json` 읽어서 → 각각 inner HTML 렌더 → srcdoc 배열 조립
4. 통합 shell HTML 재빌드 (SKILL.md Phase 5 코드 그대로)

## 신규 시드 추가 흐름

사용자가 후속 제안 중 하나 선택하면:

1. `seed_N/` 폴더 생성 (N = 다음 인덱스)
2. `cluster_finder` + `keyword_info` 실행 · `seed_N/cluster_data.json` 저장
3. `sessions.json`에 seed 엔트리 추가 · `total_credits` 갱신
4. shell HTML 전체 재빌드 (모든 시드의 inner HTML을 다시 렌더 · srcdoc 배열 재조립)
5. `ACTIVE_SESSION_IDX`는 새로 추가한 시드로 (= `len(sessions) - 1`)

## HTML 렌더 · shell + iframe 구조

**단일 문서 내 다중 세션은 불가능** (Claude Desktop Artifact 환경 · `document.write`/`location.reload` 모두 실패). 반드시 shell + iframe:

- **shell** (`_shared/render/shell.html`) · 탭바 + `<iframe>` 하나 · 각 세션 완성된 HTML을 `srcdoc` 필드에 보관
- **inner** (`_shared/render/inner-template.html`) · iframe 안 렌더 · 단일 CLUSTER_DATA만 받음 (기존 그대로)
- 탭 클릭 = `iframe.srcdoc = sessions[idx].srcdoc` · iframe 자체가 새 문서로 완전 재로드

Shell 안 데이터 형식:

```javascript
// __SHELL_DATA_START__
const CLUSTER_SESSIONS = [
  { seed: "전기자전거", seed_index: 1, meta: {gl,hop,orientation,nodes,clusters,credits}, srcdoc: "<!DOCTYPE html>..." },
  { seed: "모토벨로", seed_index: 2, meta: {...}, srcdoc: "..." }
];
let ACTIVE_SESSION_IDX = 1;  // 가장 최근 시드 활성
// __SHELL_DATA_END__
```

### 중요 · script 태그 이스케이프

srcdoc는 HTML 문자열 (`<script>` · `</script>` 포함). shell script 태그 안 JSON 문자열에 그대로 넣으면 브라우저가 `</script>`에서 shell script를 조기 종료함. 반드시 이스케이프:

```python
def escape_for_script(json_text):
    return (json_text
            .replace('</', '<\\/')
            .replace('<!--', '<\\!--')
            .replace('-->', '--\\>'))
```

그리고 마커 사이 대체는 `re.sub` 대신 문자열 replace (re.sub는 replacement의 `\n`을 특수 시퀀스로 해석 · 파일에 raw newline 삽입돼 JS SyntaxError):

```python
def replace_between(text, start_marker, end_marker, new_content):
    s = text.index(start_marker)
    e = text.index(end_marker, s + len(start_marker))
    return text[:s + len(start_marker)] + '\n' + new_content + '\n' + text[e:]
```

전체 렌더 코드는 SKILL.md Phase 5 참조.

## 크레딧 누적 안내

매 후속 시드 조회 전 사용자에게 예상 크레딧 안내:

```
다음 시드 "모토벨로" 조회 시:
- 예상 관계 ~500 · 예상 반환 고유 키워드 ~450 (limit 500 기준)
- 예상 크레딧 ~27,000 — cluster_finder(150+반환 고유 키워드 수×50) + keyword_info(키워드 수×10, all 기준)
  (예: 반환 고유 키워드 460 → 23,150 + 4,600 = 27,750 · 실제 비용은 응답 cost_detail.total_cost 기준)
- 누적 크레딧: 29,010 → 약 56,000

계속할까요? (Y/n · 다른 시드 선택 가능)
```

## 크기 상한 · 안전장치

- 세션당 시드 최대 10개 (초과 시 사용자 확인 필요)
- 누적 크레딧 30만 초과 시 경고
- 통합 HTML 파일 크기 15MB 초과 시 · 오래된 시드 요약 (`session_pruned.json`) 이동 및 최근 5개만 유지 옵션 제시
