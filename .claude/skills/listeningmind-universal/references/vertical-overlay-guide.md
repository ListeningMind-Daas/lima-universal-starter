# 버티컬·고객사 오버레이 만들기 — 4계층 체크리스트

이 스킬은 표준 베이스다. 산업(버티컬) 또는 고객사 전용 스킬은 **코어 규율을 재작성하지 않고** 아래 항목만 얹는다.
여러 산업 버티컬 구축에서 검증된 절차다.

## 0. 폴더 골격

```
.claude/skills/<listeningmind-{industry} | {customer}-search-intelligence>/
├── SKILL.md                  # 프론트도어: 트리거 서술(예시 발화 포함) · 실행 순서 · 페르소나 · 경계 규칙
├── adapter.yaml              # cep-finder-adapter/v1 — A1~A7 status 선언 (absent도 명시)
├── references/
│   ├── {x}-frames.md         # ① 업권 질문 프레임 (질문→잡→커넥터→절차→산출→가드레일)
│   ├── {x}-taxonomy.md       # ② 계층·클래스·분석 단위(무엇이 C3인가)
│   ├── brand-map.md          # ② 엔티티 사전 (×/○ 계약)
│   ├── seed-verification.md  # ② 업권 오염 유형·임계·대체 규칙 (범용판을 복제 후 보강)
│   ├── {x}-guardrails.md     # ③ 업권 규제·안전·표현 규칙 + mandatory 문구
│   ├── report-template.html  # ④ 섹션 스파인·토큰 교체 (범용판 복제 후 변형)
│   └── (jobs·readiness-gate·decision-structure·tool-routing·workflow·output-patterns — 복제 금지, 범용 참조)
├── ontology/                 # (선택) 정본 그래프 nodes/edges.jsonl · E0 사전 · 스냅샷
└── scripts/                  # (선택) seed_check.py 오버라이드 · 실측 스크립트
```

> **주의** — Claude Code는 `.claude/skills/<스킬명>/SKILL.md` 위치만 인식한다. 한 단계라도 깊으면 인식되지 않는다
> 스킬 간 파일 복제가 불가피하면 복제본 전부를 동기화하는 규칙을 README에 쓴다.

## 1. ① 질문 프레임
- [ ] 페르소나 4~6 (역할·트리거·산출물·기본 잡)
- [ ] 프레임 6~10 — 범용 F1~F10을 업권 질문으로 구체화(발화 예시 포함)
- [ ] 분석 단위 규칙 (카테고리/세그먼트, 업권 계층 C1~C4)
- [ ] 경계 규칙 — 인접 스킬과의 라우팅(예: 화장품 vs 피부과, 식료품 vs 건기식)

## 2. ② 해석 사전
- [ ] 엔티티 사전 brand-map.md (gl별 · 채널 분리 · 동음이의 keep_only)
- [ ] 노이즈 어휘 (E0 `Noise` 클래스 + adapter A2 patterns) — 업권 실측에서 수확
- [ ] 시드 오염 유형·임계 조정 (예: 그로서리는 외식률·레시피율, 피부과는 고민 단독 금지)
- [ ] 동의어 합산·금지 쌍
- [ ] (선택) 온톨로지 정본 + 스냅샷 규칙 + append-only

## 3. ③ 표현 규율
- [ ] 업권 가드레일 파일 + adapter A5 `mandatory` 문구(푸터 삽입 확인 대상)
- [ ] 수치 출처 규칙(공시·공식·공표) · 카피 초안 문구(심의 주체 명시)
- [ ] 데이터 사양 고지(인구통계·월 그레인·검색≠행동) — 범용 배너 그대로

## 4. ④ 실행 파이프라인
- [ ] 리포트 템플릿: 범용판의 CSS·토큰 유지, 섹션 스파인만 업권에 맞게 (예: 식료품 = 요리 매개 수요·채널 SoV·장바구니)
- [ ] `render_report.py` 호환 — 섹션 마커·플레이스홀더 계약 유지
- [ ] (선택) 운영 모드 스크립트(월간 모니터링·VOC 감지)
- [ ] adapter.yaml A1 훅(seed_check) · A6 템플릿 경로 · 검증: `python3 -c "from lib.vertical import load_adapter; print(load_adapter('<skill>').banner())"`

## 5. 고객사 층 (버티컬 위)
- 고객사 전용 사전(매장·서비스·앱 이름·CS 접점 클래스) · 부서별 질문 카탈로그 · 내부 데이터 계약(필요 항목은
  NOT READY 처리) · 운영 파이프라인(월 수집·poll·판정표·스냅샷)
- 배포: zip → `~/.claude/skills/` 또는 프로젝트 `.claude/skills/` · README에 설치·키 세팅·첫 발화 예시

## 6. 드리프트 방지
- 코어 규율은 이 스킬의 `_shared-core.md`만이 정본. 오버레이는 링크만.
- 버전은 SKILL.md 상단·adapter.yaml `adapter_version`(semver)에 기록. 내용 변경 patch↑, 슬롯 구조 minor↑.
- 실측에서 새 오염·새 브랜드·새 규칙이 나오면 해당 사전에 append하고 날짜·근거를 남긴다.
