# Codex에서 이 워크스페이스를 쓸 때 (먼저 읽는다)

이 파일 아래의 운영 규칙은 Claude Code 판과 같은 정본이다. Codex에서는 다음 대응표로 읽는다.
스킬 문서(`.agents/skills/*/SKILL.md`·`references/`)의 표현도 같은 대응표를 따른다.

| 문서의 표현 | Codex에서 하는 일 |
|---|---|
| `AskUserQuestion`으로 확인 | 선택지에 번호를 붙여 묻고 **답을 받을 때까지 실행하지 않는다** (즉시 실행 금지 규칙은 그대로) |
| HTML Artifact · 오른쪽 패널 렌더 | 렌더 스크립트로 `90_Output/`에 HTML 파일을 저장하고 경로를 알린다 — 사용자가 브라우저로 연다 |
| `TodoWrite`로 진행 추적 | Codex 계획(plan) 기능으로 단계를 적고 갱신한다 |
| 서브에이전트·검토 에이전트에 맡긴다 | Codex에는 없다 — 그 검토 항목은 사용자에게 확인을 요청한다 |
| `Skill()` 호출 · 스킬 이름 언급 | `$lima-agents` · `$listeningmind-universal` 로 부르거나, 요청이 스킬 설명과 맞으면 자동으로 쓴다 |
| `CLAUDE.md` | 이 파일(`AGENTS.md`) |
| Claude Desktop 안에서 실행 | Codex 안에서 실행 (스크립트·명령은 같다) |

## API 키 (가장 먼저)

분석 전에 `python3 .agents/skills/lima-agents/scripts/setup_key.py --check`로 확인한다(값은 출력되지 않는다 · 1크레딧).
종료 코드 4(키 없음)면 사용자에게 **본인 터미널에서** 다음을 실행하도록 안내한다 — 키를 대화창에 붙여넣게 하지 않는다.

```bash
python3 .agents/skills/lima-agents/scripts/setup_key.py
```

키 입력은 Codex 안에서 받지 않는다(입력 화면이 대화 기록에 남을 수 있다). 분석 스크립트는 키 인자를 받지 않고
`LM_API_KEY` → `00_Context/.lm-api-key` → `~/.config/listeningmind/api-key` 순서로 스스로 찾는다.

## 네트워크

DaaS 호출에는 외부 네트워크가 필요하다. Codex 기본 샌드박스는 네트워크가 꺼져 있어서 이 워크스페이스는
`.codex/config.toml`에서 켠다 — **프로젝트를 신뢰(trust)해야** 이 파일이 읽힌다.
연결 실패(`setup_key.py` 종료 코드 3 · `URLError`)가 나면 키 문제로 단정하지 말고 먼저 네트워크 허용을 확인하도록 안내한다.

---

# lima-universal

ListeningMind DaaS 검색 행동 데이터 기반 마케팅 리서치 워크스페이스.
사용자 발화를 분석해 최적의 리서치 모드(Explorer / Report / CEP Finder)로 라우팅하고,
산업 무관 표준 스킬(listeningmind-universal)의 규율로 분석을 수행합니다.

> **Ascent AI**가 제공하는 도구
> **배포 방식**: Codex 저장소 스킬 (`.agents/skills/`) — 플러그인 설치 불필요

---

## 프로젝트 개요

- **목적**: ListeningMind DaaS API(`keyword_info` · `intent_finder` · `cluster_finder` · `path_finder` · `serp` · `trend_finder`)의 검색 행동 데이터로 마케팅팀의 시장·브랜드·상품 의사결정을 지원
- **핵심 사용자**: 마케터, 브랜드매니저, 상품기획자, 이커머스 담당자, 경영진 (`00_Context/about-me.md` 참고)
- **아키텍처**: 오케스트레이터(`lima-agents`)가 모드를 판정하고, 표준 베이스(`listeningmind-universal`)가 7잡 라우팅·시드 검증·정직성/렌더 규율을 제공. 산업·사내 전용 오버레이가 필요하면 표준 베이스 위에 얹는다 (`listeningmind-universal/references/vertical-overlay-guide.md`)

---

## 컨텍스트 파일 로딩

매 세션 시작 시:
1. `00_Context/about-me.md` 존재 확인 (없으면 아래 "초기 설정"으로 온보딩 — 스타터 최초 실행 시 정상 경로)
2. 있으면 → `about-me.md` → (있다면) `voice.md` → `working-style.md` 순서로 읽고 이후 모든 작업에 적용
3. `10_Projects/{프로젝트명}/AGENTS.md`가 있으면 해당 프로젝트 작업 시 추가 로드 (현재 비어 있음)

## 초기 설정 (온보딩)

`00_Context/about-me.md`가 없을 때만 자동 트리거.

AskUserQuestion으로 다음 6문항을 확인 후 `about-me.md`를 생성·갱신:
1. 이름/소속
2. **담당 역할(직무)** — 브랜드매니저 / 상품기획 / 퍼포먼스·콘텐츠 마케터 / 이커머스·리테일 /
   소비자 인사이트 / 데이터 분석 / 경영진·카테고리 리드 (→ 리포트 실행 주체·백로그 관점 기본값)
3. 주로 다루는 산업·카테고리 (자유 기입 — 자주 쓰는 시드·엔티티 사전 구축과 오버레이 제작 시 참고)
4. 주요 리서치 목적 (시장 진입 검토, 브랜드 포지셔닝, 상품기획, 콘텐츠 기회, 세그먼트 분석 등)
5. 결과물 선호 형식 (인터랙티브 탐색 vs 정적 리포트)
6. **API 키 세팅** (아래 절차 — 최초 1회 필수)

### about-me.md 기록 형식 (Q&A 구조)

프로필은 **질문과 답의 기록**으로 저장한다 — 요약문·표로 재가공하지 않는다. 문항별로
"질문 원문 → 답 → 적용(이 답이 라우팅·산출물에 어떻게 반영되는지)" 3요소를 남긴다.
재설정 시 어떤 질문에 무엇을 답했는지 추적할 수 있다.

```markdown
# 사용자 프로필 — 온보딩 Q&A 기록

## Q1. 이름/소속은?
**A.** {이름} / {소속}

## Q2. 담당 역할(직무)은?
**A.** {브랜드매니저 / 상품기획 / 마케터 / 이커머스·리테일 / 소비자 인사이트 / 데이터 분석 / 경영진 중 답}
→ 적용: 리포트 **실행 주체 기본값** + 백로그 액션 관점 (발화에 주체가 없으면 이 역할로 제안)

## Q3. 주로 다루는 산업·카테고리는?
**A.** {답}
→ 적용: 기본 시드·엔티티 사전 구축, 오버레이 제작 시 참고

## Q4. 주요 리서치 목적은?
**A.** {답}
→ 적용: 기본 잡 라우팅·백로그 관점에 반영

## Q5. 결과물 선호 형식은?
**A.** {인터랙티브 탐색 / 정적 리포트}
→ 적용: Explorer/Report 모드 기본값

## Q6. API 키 세팅
**A.** {완료/보류} — 검증 호출 {성공 여부} (키 값은 절대 기록하지 않음)

## 메타
- 최초 설정: {YYYY-MM-DD} / 최근 갱신: {YYYY-MM-DD} / 갱신 사유: {…}
```

### API 키 세팅 절차 (최초 1회)

키 확인은 항상 스크립트로 한다 — `python3 .agents/skills/lima-agents/scripts/setup_key.py --check`
(키 출처만 표시하고 값은 표시하지 않음 · 검증 호출 1크레딧). 종료 코드 4(키 없음)면 **어떤 분석도 시작하기 전에**:

1. 사용자에게 **본인 터미널에서 직접** 다음을 실행하도록 안내한다 — 키를 대화창에 붙여넣지 않게 한다(대화 기록에 남는다)
   ```bash
   python3 .agents/skills/lima-agents/scripts/setup_key.py
   ```
   입력은 화면에 보이지 않고, 검증 호출(`keyword_info` 1키워드 `ads_metrics`, 1크레딧)에 성공해야
   `00_Context/.lm-api-key`(권한 600)에 저장된다. 401/403이면 다시 입력받고 2회 실패하면 발급처 문의를 안내한다
   (키가 없다고 하면: ListeningMind/Ascent 계약 담당을 통한 발급 절차를 안내하고 분석 보류)
2. 사용자가 완료했다고 하면 `setup_key.py --check`로 확인하고, 출력된 이번 호출 비용과
   `used_credits`(**당월 누적 사용량** — 잔여량 아님)를 보고한다
3. 키를 찾는 순서는 환경변수 `LM_API_KEY` → `00_Context/.lm-api-key` → `~/.config/listeningmind/api-key`.
   분석 스크립트는 키 인자를 받지 않고 이 순서로 스스로 찾는다 — 명령줄에 키를 쓰지 않는다

**보안 수칙**: 키는 파일로만 보관하고 리포트·문서·로그·커밋에 절대 포함하지 않는다.
워크스페이스를 git 저장소로 만들 경우 동봉된 `.gitignore`가 키 파일을 제외한다.
키 노출이 의심되면 즉시 재발급을 안내한다.

---

## 응답 언어

기본은 사용자 입력 언어 감지 후 동일 언어로 응답. 단, `lima-agents`·`listeningmind-universal` 스킬 실행 중에는 각 스킬 규칙(항상 한국어)이 우선함.

---

## 스킬 시스템

### 배포 스킬 (2개, `.agents/skills/`)

모든 스킬은 `.agents/skills/<스킬명>/SKILL.md` 표준 위치에 평평하게(flat) 설치돼 있음 — Codex는
현재 폴더에서 저장소 루트까지 `.agents/skills/`를 찾는다. 워크스페이스 루트에서 Codex를 연다(폴더가 한 단계라도 더 깊으면 인식되지 않는다).

| 스킬명 (`Skill()` 호출) | 역할 |
|---|---|
| `lima-agents` | **메인 오케스트레이터.** Explorer(인터랙티브 클러스터 탐색) · Report(질문 코드별 정적 리포트) · CEP Finder(상황형 진입점 발굴) 3모드 + DaaS API 래퍼·커넥터 명세 6종 |
| `listeningmind-universal` | **표준 베이스 스킬.** 산업 무관 7 표준잡 · 4계층 패키지(질문 프레임 → 해석 사전 → 표현 규율 → 실행 파이프라인) · 시드 검증 · 준비도 게이트 · HTML 리포트 렌더러 |

### 라우팅 우선순위

```
① 시장·브랜드·상품·여정·콘텐츠 질문 → listeningmind-universal (표준 7잡으로 내부 라우팅)
② "탐색/훑어보기" vs "리포트/보고" 톤 → lima-agents 내부에서 Explorer/Report 모드 판정 (아래 참고)
③ CEP·진입점·상황 발굴 발화("CEP 분석"·"진입점 찾아줘"·"상황 지도") → CEP Finder 파이프라인
   (lima-agents SKILL.md '세 번째 모드' — Explorer/Report 아님)
④ 모호할 때 → AskUserQuestion으로 모드·범위 확인 (즉시 실행 금지)
```

**lima-agents Explorer vs Report 판정** (상세: [`.agents/skills/lima-agents/SKILL.md`](.agents/skills/lima-agents/SKILL.md))

| 신호 | 모드 |
|---|---|
| "클러스터 그래프", "탐색해줘", "훑어볼래", "감 잡고 싶어", "브랜드 지형" | **Explorer** — HTML Artifact, 6모드 사이드바·4뷰·상세 Drawer |
| "리포트 뽑아줘", "분석해줘", "○○ 페인포인트 조사", 질문 코드 명시(예: B-1) | **Report** — 정적 리포트 |
| 프리픽스 명시: `탐색·`/`explore·` → Explorer, `리포트·`/`report·` → Report | 사용자가 직접 지정 |

**리포트의 분석 단위 판정: 카테고리 vs 세그먼트**

리포트 요청은 산출 스파인이 다른 두 단위 중 하나로 판정한다:

```
① 프리픽스 명시 (최우선): "카테고리· 미국 TV" → 카테고리 / "세그먼트· 미국 OLED TV" → 세그먼트
② 어휘 자동 판정: 대상이 카테고리 항목 그대로(TV·냉장고·청소기)이거나
   "시장 전체/구조/지도/TAM/세그먼트 구성" 톤 → 카테고리 리포트
   대상에 한정어(기술·가격대·용도: OLED TV·로봇청소기·게이밍 모니터)가 붙거나
   "브랜드 경쟁/여정/페인포인트/특정 브랜드" 톤 → 세그먼트 리포트
   리트머스: 대상 아래 의미 있는 하위 세그먼트가 나뉘면 카테고리, 모델 레벨만 남으면 세그먼트
③ 모호하면 AskUserQuestion (예: "로봇청소기"는 양쪽 다 성립 — 즉시 실행 금지)
```

- **카테고리 리포트**: TAM·세그먼트 구성 → 전체 SoV(Generic 분리 표기) → 의도 구성 → 백로그
- **세그먼트 리포트**: 수요 트렌드 → 세그먼트 SoV(브랜드+모델 합산) → 결정구조(CEP·KBF) → 여정(CDJ) → 백로그
- **데이터 소스**: 기본은 LM 커넥터 실측. 동일 (gl, 카테고리, 기간)의 저장 스냅샷(`99_Scratch/<분석>/api/`)이
  있으면 **크레딧을 쓰기 전에** 리플레이(0크레딧) 사용 여부를 확인하고, 사용 시 출처·스냅샷 시점을 명기한다.
- 혼합 요청("세그먼트를 카테고리 맥락과 함께")은 세그먼트 리포트 + 카테고리 맥락 1섹션 하이브리드로 처리한다.

---

## 데이터 소스 · API

- **ListeningMind DaaS API**: `keyword_info`(검색량·트렌드·인구통계·SERP 피처), `intent_finder`(연관 쿼리), `cluster_finder`(클러스터·엔티티·관계구조), `path_finder`(검색 여정), `serp`(검색결과 화면 블록), `trend_finder`(시드 주변 최근 급부상 이슈)
- **엔드포인트**: 기본값은 운영 서버(`api/client.py`에 내장) — 별도 설정 불필요. 필요 시 `LM_API_BASE` 환경변수로 재정의
- **데이터 호출 방식**: REST API + API 키(`LM-API-KEY` 헤더) 전용
- **API 키**: `LM_API_KEY` → `00_Context/.lm-api-key` → `~/.config/listeningmind/api-key` 순서로 찾는다(`setup_key.py --check`로 확인, 없으면 위 "API 키 세팅 절차"로 온보딩)
- **인구통계(성·연령)는 gl=kr 전용**: 미국(us)·일본(jp)은 keyword_info가 demography를 반환하지 않음. 해외 시장 리포트에서는 이를 "데이터 공백"이 아니라 "데이터 사양"으로 서술하고, 세그먼트 판단은 쿼리 언어·맥락 근거로만 수행
- **커넥터 명세 (정본)**: 파라미터·응답 필드·크레딧 공식은 `.agents/skills/lima-agents/references/`의 커넥터별 문서 6종 — `cluster-finder-api.md` · `keyword-info-api.md` · `intent-finder-api.md` · `path-finder-api.md` · `serp-api.md` · `trend-finder-api.md`. 해당 커넥터를 처음 쓰는 분석 전에 읽는다 (지도·조합 원칙은 `daas-api-overview.md`)
- **크레딧 단가 (실측)**: cluster_finder `150 + 반환 고유 키워드 수×50`(관계 수가 아님) / keyword_info `all` 10·`ads_metrics`·`ads_info` 1 per kw / intent_finder `30 + 반환키워드×2` / serp `30`(키워드당·출력 무과금 — 2026-08-28 실측, 2026-08-19의 `10`에서 인상) / **path_finder `50 + 경로 내 고유 키워드×40`**(경로 수가 아님 — 최고가, 여정이 판단에 필요할 때만 호출하고 limit으로 통제) / trend_finder `50 + 반환 이슈×2`(빈 결과는 과금 0 · limit으로 통제) / `*/keyword_list` 계열 `30 + 반환키워드×2`
- **시드 검증 (본 실측 전 필수)**: cluster_finder·path_finder를 쓰기 전에 `listeningmind-universal/scripts/seed_check.py`로 시드 오염을 거른다 (시드당 약 100~230크레딧 — 반환 수 비례 · 규칙: `listeningmind-universal/references/seed-verification.md`). 오염된 시드의 하류 실측은 전량 폐기 대상
- **Bash 호출**: `curl`, `python3`로 API 직접 호출 후 로컬에서 JSON 가공 (스킬별 references 참고)
- **크레딧 용어 (혼동 금지)**: 호출 1건의 비용 = 응답 `cost_detail.total_cost` / `used_credits` = **월간 누적 사용량**(해당 월 리셋, 잔여량 아님). 리포트의 "이번 분석 소진"은 `total_cost` 합산, "누적"은 반드시 "월간 누적"으로 표기

---

## 폴더 구조

```
lima-universal-starter/
├── README.md                     # 합본 안내 (Claude Code · Codex · Gemini Enterprise)
├── VERSION
├── gemini-enterprise/            # Gemini Enterprise 배포 패키지 (안내 README-GEMINI.md)
├── (Codex 판 파일)               # AGENTS.md · .agents/skills/ · .codex/ — 안내 README-CODEX.md
├── AGENTS.md
├── README-CODEX.md
├── .codex/
│   └── config.toml              # 이 워크스페이스 전용 Codex 설정 — DaaS 호출용 네트워크 허용 (조직 정책에 맞게 수정 가능)
├── .agents/
│   └── skills/
│       ├── lima-agents/                          # 메인 오케스트레이터
│       │   ├── SKILL.md
│       │   ├── api/                              # DaaS 래퍼 전체 (client.py + 커넥터 6종 + usage)
│       │   ├── references/                       # 페르소나·커넥터 명세 6종·질문 프레임·어댑터 계약·가이드
│       │   ├── lib/                              # louvain·CEP 분류·엔티티 탐지·어댑터 로더
│       │   ├── explorers/cluster-explorer/       # Explorer 모드 (references/ + prepare.py)
│       │   ├── reports/                          # Report 모드 (_shared/ · b1-segment-intent/ · cep-finder/)
│       │   └── scripts/                          # run_explorer.py · run_analysis.py · run_cep_finder.py · run_gate.py · setup_key.py · check_lexicon.py
│       └── listeningmind-universal/              # 표준 베이스 (구조는 스킬 README 참고)
├── 00_Context/                   # 전역 컨텍스트 (매 세션 자동 로드)
│   │                             #  ↓ 아래는 최초 온보딩 시 생성됨 (스타터에는 미포함)
│   ├── about-me.md               # 사용자 프로필 (Q&A 기록)
│   ├── .lm-api-key               # API 키 (git 추적 제외)
│   └── scripts/                  # (비어 있음)
├── 10_Projects/                  # 프로젝트별 AGENTS.md (비어 있음)
├── 90_Output/                    # 최종 결과물 저장
└── 99_Scratch/                   # 임시 작업 파일·API 응답 스냅샷 (처음 쓸 때 생김 · git 제외)
```

---

## 출력 규칙

- 기본 산출물은 **HTML** (Explorer: 인터랙티브 탐색기 / Report: 정적 리포트) — docx/xlsx/pptx가 기본값이 아님
- 최종 결과물은 `90_Output/`, 중간 작업 파일(JSON·API 스냅샷 등)은 `99_Scratch/`에 저장
- Explorer 렌더링은 반드시 `run_explorer.py --rerender`, 리포트 렌더링은 `render_report.py` 사용 — bash/sed/f-string으로 템플릿에 데이터 직접 주입 금지(개행이 리터럴 `\n`으로 깨져 JS SyntaxError 발생)
- 생성된 파일에는 다운로드 경로 제공, 내부 시스템 경로는 사용자에게 노출하지 않음

---

## 품질 기준

- **범용 가드레일 강제** (`listeningmind-universal/references/guardrails.md`): 검색은 관심 신호(판매·계약·방문 아님) · SoV는 "검색량 기준 근사" · null은 결측(0 아님) · 인과 단정 금지(상관·동향) · 임의 등급 금지 · 집계 데이터만(민감 개인 속성 추정 금지)
- **규제 도메인 추가 규칙**: 의료·금융·식품 효능·화장품 효능 등을 건드리면 guardrails §3의 도메인별 추가 규칙을 푸터에 그대로 삽입 (권유·단정 금지, 수치는 공시·공식 출처만, 카피는 "심의·준법검토 전 초안" 표기)
- API 호출 후 **크레딧 실측**(이번 소진 + 월간 누적)을 응답에 포함
- **분석 건별 게이트 기록**: 분석마다 `lima-agents/scripts/run_gate.py`로 분석 폴더에 `gates.json`을 남긴다(CEP Finder는
  엔진이 자동 생성). 렌더러는 렌더 전 게이트(예산·정본·수집·준비도·테스트) 미통과면 멈추고, 외부 전달 전에는
  출처 라벨 확인(`attest --gate labels`)·규칙 회수(`rules`)를 기록한다 — `status --stage publish` 0. 계약: `lima-agents/references/run-gates.md`
  **사전 공백은 실패·대기가 아니라 질문이다** — '결정 필요'(엔진은 종료 코드 10)가 나오면 AskUserQuestion으로
  "이 품목의 사전을 채울까요, 건너뛰고 진행할까요?"를 묻고, 채우기면 사전 작성 후 `check`, 건너뛰기면 `decide --choice skip`
  (엔진은 `--on-dictionary-gap skip`). 건너뛰면 산출물에 "사전 생략 · 잠정" 한 줄만 남는다.
- **리포트 문구의 숫자 대조**: 결정 리포트·범용 리포트·CEP 덱 렌더러는 렌더 전에 문장 속 숫자를 분석 폴더 원자료·계산값과 대조한다.
  계산값에 없는 숫자가 있으면 게이트 기록이 있는 분석은 렌더를 멈춘다 — 합산 수치는 임시 계산이 아니라 저장본과 스크립트로만 만든다.
  초안이 꼭 필요하면 `--allow-unverified-numbers`(산출물에 미통과 배너)
- **산출물 어휘**: 화면 문구는 업무 사용자가 읽을 수 있는 말로 쓴다. 렌더러가 출력 직전에 1:1 대응 작업 용어를 바꾸고
  (질의→검색어 · 관계망→연관 키워드 · 허브→진입점 …), 문장을 다시 써야 하는 용어가 남으면 멈춘다. 파일 검사:
  `lima-agents/scripts/check_lexicon.py file <경로>` · 계약: `lima-agents/references/lexicon-gate.md` §6
- 모든 수치에 `[실측]`/`[파생]`/`[가정]`/`[없음]`(+공표값 `[fact]`) 라벨
- 요청이 모호하면 AskUserQuestion으로 확인 (즉시 실행하지 않음)
- 복합 업무 시 TodoWrite로 진행 상황 추적

---

## 트러블슈팅

| 증상 | 해결 방법 |
|---|---|
| 스킬이 인식되지 않음 | `.agents/skills/` 하위 각 폴더에 `SKILL.md` 존재 확인. 워크스페이스 루트에서 Codex를 열었는지 · 프로젝트를 신뢰했는지 확인 후 Codex 재시작 |
| 렌더 결과에 `\n` 리터럴 노출 | 렌더 스크립트 대신 shell/sed로 직접 조립한 경우 — 반드시 스크립트 재실행 |
| API 키 오류 (401/403) | `setup_key.py --check`로 출처·검증 확인 (환경변수 `LM_API_KEY`가 파일보다 먼저 쓰인다). 다시 설정은 `setup_key.py`. 2회 실패 시 발급처 문의 |
| 크레딧이 예상보다 큼 | 호출 전 `credit_estimate.py`로 추정 → cluster_finder는 limit, path_finder는 여정 필요 시에만 |
| SoV·여정 결과가 이상함 | 시드 오염 의심 — `seed_check.py` 재검증, `E0_사전.csv` Noise 등재 여부 확인 |
