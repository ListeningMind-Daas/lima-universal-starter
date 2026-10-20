# lima-universal 리서치 에이전트 (Gemini Enterprise 판) v1.4.0

ListeningMind DaaS 검색 행동 데이터로 시장·브랜드·상품·검색 여정 질문에 답하는 에이전트를
**귀사 GCP 프로젝트**의 Agent Engine 에 배포하고 Gemini Enterprise 에 등록하는 패키지입니다.
API 키는 귀사 Secret Manager 에만 있고, 이 패키지·배포 설정·로그 어디에도 값이 들어가지 않습니다.

## 준비물

- Gemini Enterprise (ADK 에이전트 등록이 되는 에디션 — Standard · Plus · Pay-as-you-go · Frontline 문서 기준) 과 그 관리자 권한
- GCP 프로젝트 · Vertex AI API · Secret Manager API · Discovery Engine API 사용 설정
- 배포 묶음을 올릴 GCS 버킷 (`gs://…`)
- ListeningMind DaaS **REST API 키** (발급: ListeningMind/Ascent 계약 담당 경유)
- Python 3.12 이상

## 1. API 키를 Secret Manager 에 넣기

키는 화면·셸 이력에 남지 않게 표준입력으로 넣습니다.

```bash
read -rs LM_KEY && printf '%s' "$LM_KEY" | gcloud secrets create lm-daas-api-key --project <프로젝트> --data-file=- && unset LM_KEY
```

Agent Engine 서비스 에이전트에 이 비밀을 읽을 권한을 줍니다 — **빠지면 배포는 성공해도 에이전트가 뜨지 않습니다.**

```bash
gcloud secrets add-iam-policy-binding lm-daas-api-key --project <프로젝트> \
  --member serviceAccount:service-<프로젝트 번호>@gcp-sa-aiplatform-re.iam.gserviceaccount.com \
  --role roles/secretmanager.secretAccessor
```

## 2. 배포

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r deploy/requirements.txt
python3 deploy/selfcheck.py                                    # 0크레딧 자가 점검
python3 deploy/deploy.py --project <프로젝트> --location <리전> --staging-bucket gs://<버킷> \
  --secret lm-daas-api-key --model <그 리전의 Gemini 모델 ID> --check-key
```

- `--check-key`: 배포 전에 비밀 값으로 검증 호출(약 1크레딧)을 합니다. 배포 계정에 그 비밀의 Secret Accessor 권한이 있어야 합니다
- `--dry-run`: 배포하지 않고 설정만 확인합니다 (비밀 값을 읽지 않습니다)
- `--report-bucket <버킷>`: 리포트 HTML 을 이 버킷에 올리고 **조직 내부 인증 링크**로 돌려줍니다 (공개 링크를 만들지 않습니다)
- 끝에 출력되는 리소스 이름(`projects/…/reasoningEngines/…`)을 다음 단계에 씁니다

## 3. Gemini Enterprise 에 등록

Gemini Enterprise 관리자가 콘솔에서 앱 > **에이전트** > **Custom agent via Agent Runtime** 을 고르고
이름·설명·위 리소스 이름을 넣어 만듭니다. 키는 서버 쪽에서 쓰므로 OAuth 인증 설정은 필요 없습니다.

점검(DaaS 0크레딧 · 모델 호출 비용만):

```bash
python3 deploy/smoke.py --project <프로젝트> --location <리전> --resource <리소스 이름>
```

## 크레딧 통제

회사 전체가 키 하나를 같이 쓰므로 에이전트가 세 겹으로 막습니다.

| 장치 | 기본값 | 바꾸는 법 (`deploy.py`) |
|---|---|---|
| 자동 승인 한도 — 이보다 비싼 호출은 예상치를 알리고 사용자 승인 뒤에만 실행 | 30크레딧 | `--auto-approve` |
| 대화(세션)당 예산 | 3,000크레딧 | `--session-budget` |
| 관리자 상한 — 사용자가 요청해도 세션 예산을 이 위로 못 올림 | 20,000크레딧 | `--session-budget-max` |

호출마다 사용자 ID·도구·견적·실소비·월간 누적이 Cloud Logging 에 JSON 한 줄(`"event": "lm_daas_call"`)로 남습니다.
`used_credits` 는 **당월 누적 사용량**이지 잔여량이 아닙니다.

## 구성

```
lima_agent/            ADK 에이전트 (agent.py · tools.py · instruction.md)
  └ skills/            분석 규칙과 API 래퍼 — lima-agents · listeningmind-universal
deploy/                deploy.py · smoke.py · selfcheck.py · requirements.txt
```

## 알아 둘 것

- 결과 리포트는 **초안**입니다 — 제목·문장 검토를 거치지 않았다는 배너가 붙습니다
- 산업 무관 표준만 싣습니다. 업권 전용 사전이 없어 결과에 "업권 정본 없음 · 잠정"이 표기됩니다
- 인구통계(성·연령)는 한국(gl=kr)에서만 제공됩니다
- 키 노출이 의심되면 즉시 재발급을 요청하고 비밀에 새 버전을 추가한 뒤(`gcloud secrets versions add`) `deploy.py`로 다시 배포하세요
