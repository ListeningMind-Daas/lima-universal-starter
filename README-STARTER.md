# lima-universal 스타터 패키지 v1.4.0

ListeningMind DaaS 검색 행동 데이터 기반 **마켓 인텔리전스 에이전트 워크스페이스**입니다.
산업 무관 표준 스킬(listeningmind-universal)과 오케스트레이터(lima-agents)로 구성되어
어떤 카테고리든 바로 분석을 시작할 수 있습니다.

## 시작하기 (5분)

> **준비물** — Python **3.12 이상**(`python3 --version`으로 확인 · macOS 기본 3.9로는 일부 렌더러가 실행되지 않습니다)

1. **압축 해제** — 이 폴더를 원하는 위치에 둡니다 (폴더명 자유)
2. **Claude Code / Claude Desktop**에서 이 폴더를 워크스페이스로 엽니다
3. **첫 세션에서 온보딩이 자동 시작됩니다** — 에이전트가 6문항(이름·역할·산업·목적·형식·API 키)을
   질문하고, 답변을 `00_Context/about-me.md`에 Q&A 기록으로 저장합니다
4. **API 키**: 온보딩 중 ListeningMind DaaS **REST API 키**(발급: ListeningMind/Ascent 계약 담당 경유)를
   터미널에서 직접 입력하도록 안내받습니다 — 대화창에 붙여넣지 마세요
   ```bash
   python3 .claude/skills/lima-agents/scripts/setup_key.py
   ```
   검증 호출(1크레딧 — data_type=ads_metrics 1키워드)에 성공하면 `00_Context/.lm-api-key`(권한 600)에 저장되고
   분석이 활성화됩니다. 확인은 `setup_key.py --check`, 워크스페이스 밖에 두려면 `--scope user`
   (`~/.config/listeningmind/api-key`). 환경변수 `LM_API_KEY`가 있으면 파일보다 먼저 쓰입니다.
   엔드포인트는 운영 서버 기본값이 내장되어 있어 별도 설정이 필요 없습니다
5. **첫 리포트**: 예) `리포트· 전기자전거 한국 시장 세그먼트 리포트, 중립 조사 관점으로` 라고 말해보세요

## 무엇이 들어 있나

```
README.md · VERSION       합본 안내 · 판 번호
CLAUDE.md                  운영 규칙 정본 (라우팅·판정·온보딩·가드레일)
.claude/skills/            분석 스킬 2종
  └ lima-agents/               오케스트레이터 — Explorer·Report·CEP Finder 3모드
      └ references/            DaaS 커넥터 명세 6종 (파라미터·응답 필드·크레딧 공식·실측 검증)
  └ listeningmind-universal/   표준 베이스 — 7 표준잡 · 시드 검증 · 준비도 게이트 · 리포트 렌더러
      └ references/vertical-overlay-guide.md   산업·사내 전용 오버레이 만들기 가이드
90_Output/                 결과물 저장 폴더
00_Context/ 10_Projects/  작업 폴더 골격 (온보딩·프로젝트) · 임시 폴더 99_Scratch/는 처음 쓸 때 생기며 git에서 제외됩니다
AGENTS.md · .agents/ · .codex/ · README-CODEX.md   Codex 판 (같은 스킬)
gemini-enterprise/         Gemini Enterprise 배포 패키지
```

## 무엇을 할 수 있나

| 하고 싶은 것 | 발화 예 |
|---|---|
| 시장·카테고리 훑어보기 | "탐색· 캠핑용품 클러스터 보여줘" |
| 정적 분석 리포트 | "리포트· 무선이어폰 한국 시장 세그먼트 리포트" |
| 수요·트렌드·시즌성 | "○○ 검색 추이와 시즌성 알려줘" — 시드를 층별로 설계·확장해 키워드 전체의 48개월 검색량으로 계산 |
| 브랜드 검색 점유(SoV) | "○○ 카테고리 브랜드 점유 비교해줘" |
| 검색 여정(CDJ) | "○○ 구매 전 검색 경로 어디서 이탈해?" |
| 진입 상황(CEP) 발굴 | "○○는 어떤 상황에서 찾기 시작해? CEP 분석해줘" |
| 콘텐츠·키워드 기회 | "○○ 콘텐츠로 다룰 질문·쿼리 뽑아줘" |

## 자주 묻는 것

- **리포트는 어떻게 공유하나요?** — `90_Output/`의 HTML 파일을 그대로 전달하면 브라우저에서
  열립니다 (설치·계정·서버 불필요). 리포트 차트는 페이지 안에 그려져 인터넷 연결 없이도 보입니다.
  단, Explorer(인터랙티브 탐색기) 화면은 그래프 라이브러리(d3)를 CDN에서 불러오므로 인터넷 연결이 필요합니다
- **크레딧은 얼마나 드나요?** — 세그먼트 리포트 1건 약 3~7만 크레딧. 분석 전에 에이전트가
  `credit_estimate.py`로 예상치를 고지하고, 사용자가 상한을 말하면 하드 상한으로 지킵니다.
  호출 1건의 비용은 응답 `cost_detail.total_cost`, `used_credits`는 당월 누적 사용량(잔여량 아님)입니다
- **시드 검증이 뭔가요?** — 다의어 시드(예: "tv", "이사")는 무관한 검색을 끌어와 비싼 실측을 통째로
  망칩니다. 그래서 본 실측 전에 저비용 프로브(시드당 약 100~230크레딧 — 반환 수 비례)로 시드 오염을 걸러냅니다 —
  이 규율이 `listeningmind-universal`에 내장되어 있습니다
- **우리 산업 전용으로 확장할 수 있나요?** — `listeningmind-universal/references/vertical-overlay-guide.md`의
  체크리스트를 따라 산업·사내 전용 오버레이 스킬을 표준 베이스 위에 얹을 수 있습니다
  (페르소나·질문 프레임·엔티티 사전·가드레일만 추가, 코어 규율은 재사용)
- **키 보안** — 키는 `00_Context/.lm-api-key` 파일로만 보관하세요. git 사용 시 동봉된
  `.gitignore`가 키 파일을 제외합니다
- **권한 설정** — 권한 설정 파일은 동봉하지 않습니다. DaaS API 호출과 분석 스크립트 실행(`python3`)은 실행할 때마다
  확인을 받습니다. 매번 확인이 번거로우면 조직 보안 정책 안에서 `.claude/settings.local.json`에 허용 규칙을 직접 추가하세요

## 분석 건별 게이트

분석마다 폴더에 `gates.json`이 남고, 렌더러는 렌더 전 게이트(예산·정본·수집·준비도·테스트)가 통과해야 렌더합니다.

**품목 사전이 비어 있으면 실패가 아니라 질문입니다.** 범용 스킬의 사전은 분석마다 채우는 틀이라, 새 품목을 분석하면
에이전트가 **"이 품목의 사전을 채울까요, 건너뛰고 진행할까요?"**라고 먼저 묻습니다. 크레딧을 쓰는 CEP 실측은 지출 전에 묻습니다.

| 답 | 이후 |
|---|---|
| 채운다 | 에이전트가 `listeningmind-universal/dictionary/`의 brand-map·E0 사전에 품목·브랜드를 채우고 이어서 분석 |
| 건너뛴다 | 그대로 분석·렌더. 산출물에 "사전 생략(사용자 선택) — 브랜드 귀속·정본 판정은 잠정" 한 줄만 남습니다 |

기록 명령(에이전트가 실행): `run_gate.py decide --run <분석 폴더> --choice fill|skip --by <이름>` ·
CEP 실측을 건너뛰기로 진행할 때는 `run_cep_finder.py … --on-dictionary-gap skip`.

외부로 전달하기 전에는 출처 라벨 확인(`attest --gate labels`)과 규칙 회수(`rules`)를 기록하고
`status --stage publish`가 0인지 확인합니다. 계약: `.claude/skills/lima-agents/references/run-gates.md`

## 설치 후 자가 검증 (크레딧 0)

```bash
cd .claude/skills/listeningmind-universal
python3 scripts/credit_estimate.py --preset standard
python3 scripts/seed_check.py --replay examples/probe-replay --anchor "삼계탕,닭갈비,닭" --skip-brand-gate --no-registry
python3 scripts/render_report.py examples/sample-report.json -o ../../../99_Scratch/sample.html
python3 scripts/render_cep_deck.py examples/cep-deck-sample.json -o ../../../99_Scratch/deck.html
python3 ../lima-agents/scripts/run_gate.py --help
python3 ../lima-agents/scripts/check_lexicon.py file ../../../99_Scratch/sample.html
```

## 변경 이력

- **v1.4 (2026-10-13)** — Codex·Gemini Enterprise 판 · API 키 설정 스크립트 · trend_finder 커넥터 · 수요·트렌드 잡 수집 파이프라인
  (v1.3은 따로 발행하지 않고 이 판에 포함했다)
  - **API 명세 기준을 운영 OpenAPI v1.0.13으로** — `/ai_overview/analyze` 삭제 반영 · 모든 호출에 선택 파라미터 `is_skills` 추가(클라이언트가 기본으로 넣는다) ·
    단가는 동봉한 명세 사본(`lima-agents/api/openapi-prod-pinned.json`)에서 `api/spec.py`가 읽는다
  - **cluster_finder 과금 단위 표기 통일** — 관계 수가 아니라 '반환 고유 키워드 수' × 50 (+150). 견적 입력 이름도 같게
  - **차트는 inline SVG로 통일** — 질문 코드 리포트(B-1)가 외부 Chart.js를 쓰던 것을 페이지 안에서 그리도록 바꿨다(인터넷 없이 열림 · 축은 0 기준)
  - **리포트마다 데이터 출처와 크레딧 사용 내역** — `render_report.py`가 분석 폴더의 호출 원장(`ledger.json` · `collect_demand.py`가 기록)을 읽어
    리포트 끝에 부록(호출 순서 · 호출 로그 · 비용 보고서)을 붙이고, 같은 이름으로 `.calls.csv`·`.cost.json`을 함께 저장한다. 원장이 없으면 '호출 기록 없음'으로 표시
  - **한 폴더를 Claude Code 와 Codex 가 함께 연다** — Codex 판(`AGENTS.md` · `.agents/skills/` · `.codex/config.toml`) 동봉. 안내 `README-CODEX.md`
  - **Gemini Enterprise 판** `gemini-enterprise/` — 귀사 GCP Agent Engine 에 배포하는 에이전트(키는 Secret Manager). 안내 `gemini-enterprise/README-GEMINI.md`
  - **API 키 설정 `lima-agents/scripts/setup_key.py`** — 터미널에서 직접 입력 → 검증 호출(1크레딧) 성공 시 권한 600으로 저장 · `--check`로 확인.
    키를 찾는 순서가 모든 스크립트에서 같다: 환경변수 `LM_API_KEY` → `00_Context/.lm-api-key` → `~/.config/listeningmind/api-key`
  - **분석 스크립트가 키를 명령줄 인자로 받지 않는다** — `run_explorer.py`·`run_analysis.py`의 `<API_KEY>` 인자 제거(셸 이력·대화 기록 노출 방지 · 예전 방식도 동작)
  - **trend_finder 커넥터** 명세·래퍼 추가 — 시드 주변 최근 급부상 이슈(요약·출처 링크) · 커넥터 명세 6종
  - 권한 설정 파일(`.claude/settings.local.json`)은 동봉하지 않는다는 안내로 정정 · 필요한 Python 판(3.12 이상) 명시
  - **`listeningmind-universal/scripts/collect_demand.py`** · 계약 `references/demand-pipeline.md` — 시드 레이어 설계
    (문제·시장·브랜드·대체재 + 재화 유형 층) → 시드 검증 프로브를 연관어 확장으로 재사용 → 고볼륨 시드 구조 탐색
    (cluster_finder/keyword_list hop 1) → 유니크 정리 → 유니크 전체 `keyword_info(ads_info)` 월별 48개월(키워드당 1크레딧)
    → 노이즈·표기 변형·같은 월별 계열 중복 제거 → YoY·시즌·채널 지표. 단계마다 저장본을 남기고 `--replay`로 0크레딧 재계산
  - 헤드라인 수요는 시장·브랜드·재화 유형 층만 더하고, 문제·대체재 층은 맥락으로 따로 표기한다
  - 후속 단계 — `rising`(키워드 단위 라이징) · `explain`(라이징 원인: 구별 토큰으로 trend_finder를 부르고 품목 어휘로 거른다) ·
    `share`(브랜드·판매 채널·무브랜드 검색 점유와 미등재 브랜드 후보) · `content`(목적별 검색어 묶음 · 상위 검색어 SERP의 연관 질문·
    AI 개요·상위 사이트와 그 검색어들의 구글 비중)
  - 같은 월별 계열 중복 판정 `lima-agents/lib/series_dedup.py` · 예산 프리셋 `credit_estimate.py --preset demand-lite|demand|demand-deep`
  - 호출 순서 규정을 한 가지로 통일(검증·확장 → 규모 → 구조 → 확장어 규모 → 여정) — SKILL.md·workflow.md·tool-routing.md·jobs.md
  - **명세 보강** — `keyword-info-api.md`의 `monthly_volume` 배열 순서(**오래된 달 → 최신 달**)를 명시했다.
    배열 위치가 아니라 `month` 값으로 최신 달을 고른다
  - `serp-api.md` — DaaS 키로 연관 키워드 묶음의 AI 요약(AIO)을 모으는 경로(확장 → 유니크 목록 → serp) 추가
  - `trend-finder-api.md` — 빈 결과 호출은 과금 0으로 실측 · 띄어쓴 여러 단어 시드는 단어 하나만 맞아도 이슈를 가져온다
  - 브랜드 매칭(`lib/canon.py`) 모델 표지 확장 · 어댑터 준비도 검사(`lib/vertical.py`)가 품목이 아닌 앵커(TPO·Look)를 인식

- **v1.2 (2026-09-18)** — 엔진 버그 수정과 리포트 품질 점검 추가(구성 범위는 v1.1.1과 같다)
  - **replay 보충분 유실 수정** — `--replay-topup`으로 보충 실측한 결과가 `이름_2.json`으로 저장되는데 다음 replay는 `이름.json`만 읽어
    보충분이 사라졌고, 보충할 때 저장본 결과가 응답에서 빠졌다. 이제 보충 파일을 모두 합쳐 읽는다. 특정 단계만 라이브로 보충하는
    `--replay-live-measure`(S5 미매칭 예측어 실측만) 추가
  - **실행 재현 기록** — 분석 매니페스트에 엔진 버전·실행 인자·입력 파일 해시를 남긴다
  - **브랜드 매칭 보강** (`lib/canon.py`) — 동음이의 표에 오른 단독 별칭은 넣은 형태가 함께 있을 때만 센다(다른 단어 속 부분 일치 오탐 방지) ·
    넣은 형태를 담은 이름은 동음이의로 판정하지 않는다 · 이름 뒤 모델 표지(미니·프로·7세대·S10·FE 등)를 떼고 라인을 다시 조회한다 ·
    한 글자 단독어도 동음이의로 판정한다
  - **리포트 문구 숫자 대조** (`lib/prose_check.py`) — 결정 리포트·범용 리포트(`--run`)·CEP 덱이 렌더 전에 문장 속 숫자를 계산값과 대조
  - **산출물 어휘 검사** (`lib/lexicon_check.py` · `scripts/check_lexicon.py file`) — 분석 작업 용어를 업무 용어로 바꾸고 남으면 멈춘다 ·
    결정 리포트의 절 제목·표 머리를 업무 용어로 정리
  - **수집 전 정본 해석 자리** — 정본 해석기가 설치된 환경에서는 수집 크레딧을 쓰기 전에 판정한다. 스타터에는 해석기가 없어
    이 단계는 건너뛰고, 종전처럼 렌더 전 게이트에서 사전을 채울지 묻는다
  - **범용 스킬 사전 경로 수정** — 정본 파서가 `references/brand-map.md`만 찾아, 범용 스킬 사용자가 `dictionary/brand-map.md`에 채운
    브랜드 사전을 읽지 못하고 있었다(v1.1부터). 이제 두 위치를 모두 찾고, 채우기 전 템플릿 자리표시자 줄은 브랜드로 읽지 않는다
  - 자가 검증 예시 입력의 작업 용어 정리(어휘 검사 통과)
  - 게이트 안내 문구를 업무 용어로('게이트' → '품질 점검')
- **v1.1.1 (2026-09-17)** — 품목 사전 공백을 게이트 대기·실패로 두지 않고 **사용자에게 채울지 묻고, 아니면 건너뛰도록** 변경.
  게이트 상태 `결정 필요`·`작성 중`·`생략` 추가, `run_gate.py decide`, CEP 엔진은 사전 공백이면 크레딧 지출 전에 멈추고
  `--on-dictionary-gap skip`으로 진행. 건너뛰면 산출물에 '사전 생략 · 잠정' 한 줄만 남긴다(v1.1의 '사유를 적고 면제' 안내 대체)
- **v1.1 (2026-09-17)** — 엔진과 지식 갱신(구성 범위는 v1.0과 같다)
  - **serp 단가 30/키워드 반영** — 2026-08-28 실측으로 10에서 인상. 엔진 예산 게이트·견적 스크립트·커넥터 명세·운영 규칙을
    모두 30으로 맞췄다(v1.0 엔진은 serp 예산을 실제의 1/3로 잡았다). 단가 근거 순서: 공개 API 문서 → 명세 스냅샷 → 응답 `total_cost`
  - **CEP Finder 엔진 v0.6.1~v0.6.5** — API 띄어쓰기 정규화로 실측 볼륨이 null로 기록되던 키워드 조인 버그 수정
    (`join_by_request`), S5 가설 판정 개선(실측 매칭 기준·순열 기준선·미매칭 예측어 직접 실측·일반어 분리·발주 규칙),
    replay 중 직접 실측 저장본 재사용(재과금 방지)
  - **준비도 커버리지 검사** — 어댑터 사전이 분석 품목을 한 건도 덮지 않으면 ready를 partial로 강등하고 경고
  - **정본 파서 단일화** (`lima-agents/lib/canon.py`) — 브랜드 사전 파싱·매칭 규칙을 한 곳으로. 이어 쓴 줄·한 줄 두 브랜드를
    진단하고, 브랜드 줄 0건으로 내장 사전에 대체될 때 조용히 넘어가지 않고 경고한다
  - **분석 건별 게이트 기록** (`lima-agents/scripts/run_gate.py` · `references/run-gates.md`) — 예산·정본·수집·준비도·테스트를
    렌더 전에, 출처 라벨 확인·규칙 회수를 발행 전에 기록·확인한다. 결정 리포트·범용 리포트·CEP 덱 렌더러가 기록을 읽는다
  - **표준 실행 순서 11단계** — 10단계 뒤에 '발행 전 확인 · 규칙 회수'를 추가
  - **엔티티 사전 규칙 보강** — 브랜드당 한 줄 · 동음이의 결합형 선택 절차 · 부분 문자열 오탐 점검 · 결합형 수식어 한계
  - **표기 정규화 절** (`keyword-info-api.md`) · **어휘 게이트** (`references/lexicon-gate.md`)

- **v1.0 (2026-08-25)** — 최초 전달본. 구성: ① 오케스트레이터 `lima-agents`(Explorer·Report·CEP Finder
  3모드, DaaS 래퍼 전체, 커넥터 명세 5종) ② 표준 베이스 `listeningmind-universal`(7 표준잡 · 4계층
  패키지 · 시드 검증 스크립트·사전 · 준비도 게이트 · HTML 리포트/CEP 덱 렌더러 · 오버레이 가이드)
  ③ 워크스페이스 골격(00_Context 온보딩 · 90_Output · 99_Scratch) + 운영 규칙 정본(CLAUDE.md)

---
v1.4.0 · Ascent AI · 문의: ListeningMind DaaS 담당자
