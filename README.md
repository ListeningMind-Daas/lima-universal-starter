# lima-universal 스타터 v1.4.0

ListeningMind DaaS 검색 행동 데이터로 시장·브랜드·상품·검색 여정 질문에 답하는 **마켓 인텔리전스 에이전트**입니다.
같은 분석 스킬(오케스트레이터 `lima-agents` · 표준 베이스 `listeningmind-universal`)을 세 가지 도구에서 씁니다.

| 쓰는 도구 | 시작 방법 | 안내서 |
|---|---|---|
| **Claude Code / Claude Desktop** | 이 폴더를 그대로 엽니다 | [README-STARTER.md](README-STARTER.md) |
| **Codex** | 이 폴더를 그대로 엽니다 (프로젝트 신뢰 필요) | [README-CODEX.md](README-CODEX.md) |
| **Gemini Enterprise** | `gemini-enterprise/`를 귀사 GCP에 배포합니다 | [gemini-enterprise/README-GEMINI.md](gemini-enterprise/README-GEMINI.md) |

Claude Code 와 Codex 는 한 폴더를 함께 씁니다 — Claude Code 는 `CLAUDE.md`·`.claude/skills/`, Codex 는 `AGENTS.md`·`.agents/skills/`·`.codex/`만 읽어 서로 간섭하지 않습니다.
두 스킬 폴더는 같은 판이며, 안의 경로 표기(`.claude/skills` ↔ `.agents/skills`)만 각 도구에 맞게 다릅니다.

## 준비물

Python **3.12 이상**(`python3 --version`) · ListeningMind DaaS **REST API 키**

## API 키

ListeningMind DaaS **REST API 키**(발급: ListeningMind/Ascent 계약 담당 경유)가 필요합니다. 키는 대화창에 붙여넣지 않습니다.

- **Claude Code / Codex** — 터미널에서 직접 입력합니다. 검증 호출(1크레딧)에 성공해야 `00_Context/.lm-api-key`(권한 600)에 저장됩니다
  ```bash
  python3 .claude/skills/lima-agents/scripts/setup_key.py
  ```
  (Codex 경로 `.agents/skills/lima-agents/scripts/setup_key.py` 도 같은 스크립트입니다)
- **Gemini Enterprise** — 귀사 Secret Manager 에 넣고, 배포 설정은 비밀의 이름만 참조합니다

키를 찾는 순서는 세 도구 모두 같습니다: 환경변수 `LM_API_KEY` → `00_Context/.lm-api-key` → `~/.config/listeningmind/api-key`.
`used_credits` 는 **당월 누적 사용량**이지 잔여량이 아닙니다.
