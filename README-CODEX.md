# lima-universal 스타터 패키지 (Codex 판) v1.4.0

ListeningMind DaaS 검색 행동 데이터 기반 **마켓 인텔리전스 에이전트 워크스페이스**의 Codex 판입니다.
Claude Code 판과 같은 스킬 두 개(오케스트레이터 `lima-agents` · 표준 베이스 `listeningmind-universal`)를
Codex 구조(`.agents/skills/` · `AGENTS.md`)로 배치했습니다.

## 시작하기

> **준비물** — Python **3.12 이상**(`python3 --version`으로 확인 · macOS 기본 3.9로는 일부 렌더러가 실행되지 않습니다)

1. **압축 해제** — 이 폴더를 원하는 위치에 둡니다 (폴더명 자유)
2. **git 저장소로 만들기 (권장)** — Codex는 현재 폴더에서 저장소 루트까지 `.agents/skills/`를 찾습니다.
   동봉된 `.gitignore`가 API 키 파일을 제외합니다
   ```bash
   git init
   ```
3. **API 키 설정** — ListeningMind DaaS **REST API 키**(발급: ListeningMind/Ascent 계약 담당 경유)를
   터미널에서 직접 입력합니다. 대화창에 붙여넣지 마세요
   ```bash
   python3 .agents/skills/lima-agents/scripts/setup_key.py
   ```
   검증 호출(1크레딧 — `keyword_info` `ads_metrics` 1키워드)에 성공해야 `00_Context/.lm-api-key`(권한 600)에 저장됩니다.
   - 확인: `setup_key.py --check` · 워크스페이스 밖에 두기: `--scope user` (`~/.config/listeningmind/api-key`)
   - 환경변수 `LM_API_KEY`가 있으면 파일보다 먼저 쓰입니다
4. **Codex 열기** — 이 폴더(루트)에서 Codex를 엽니다. **프로젝트 신뢰 여부를 물으면 신뢰를 고릅니다** —
   그래야 `.codex/config.toml`(DaaS 호출용 네트워크 허용)이 적용됩니다
5. **첫 세션** — 에이전트가 온보딩 6문항(이름·역할·산업·목적·형식·API 키 확인)을 묻고 `00_Context/about-me.md`에 기록합니다
6. **첫 리포트** — 예) `리포트· 전기자전거 한국 시장 세그먼트 리포트, 중립 조사 관점으로`
   스킬을 직접 부르려면 `$lima-agents` · `$listeningmind-universal`

## 구성

```
AGENTS.md                  운영 규칙 (Codex 대응표 + 라우팅·판정·온보딩·가드레일)
.codex/config.toml         이 워크스페이스 전용 Codex 설정 — 네트워크 허용
.agents/skills/            분석 스킬 2종
  └ lima-agents/               오케스트레이터 — Explorer·Report·CEP Finder 3모드 · API 래퍼 · setup_key.py
  └ listeningmind-universal/   표준 베이스 — 7 표준잡 · 시드 검증 · 준비도 게이트 · 리포트 렌더러
90_Output/                 결과물 저장 폴더 (HTML 리포트는 여기 저장되고 브라우저로 엽니다)
```

## 자주 묻는 것

- **네트워크 허용의 범위** — `network_access = true`는 DaaS 주소 하나가 아니라 **이 프로젝트에서 Codex가 실행하는 모든 명령**에
  외부 네트워크를 엽니다. 임의의 주소 접속·외부 전송이 가능해지므로, 신뢰하지 않는 스크립트를 이 폴더에서 돌리지 마세요
- **API 호출이 "연결 실패"로 끝나요** — Codex 기본 샌드박스는 외부 네트워크가 꺼져 있습니다.
  프로젝트를 신뢰했는지, `.codex/config.toml`의 `network_access = true`가 남아 있는지 확인하세요.
  조직 정책상 상시 허용이 어렵다면 그 줄을 지우고 호출할 때마다 승인하는 방식으로 쓸 수 있습니다
- **크레딧은 얼마나 쓰나요?** — 분석 전에 `credit_estimate.py`로 예상치를 알리고, 상한을 말하면 그 안에서만 호출합니다.
  호출 1건의 비용은 응답 `cost_detail.total_cost`, `used_credits`는 **당월 누적 사용량**(잔여량 아님)입니다
- **Claude Code 판과 다른 점** — 스킬·스크립트·판정 규칙은 같습니다. 결과물은 오른쪽 패널 대신 `90_Output/`의 HTML 파일로 나오고,
  검토 서브에이전트가 맡던 확인 항목은 사용자에게 직접 묻습니다
- **키 보안** — 키는 파일(또는 환경변수)로만 보관하고 리포트·문서·커밋에 넣지 않습니다. 노출이 의심되면 즉시 재발급을 요청하세요
