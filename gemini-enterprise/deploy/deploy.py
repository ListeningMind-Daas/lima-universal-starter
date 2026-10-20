#!/usr/bin/env python3
"""ListeningMind 리서치 에이전트를 **고객사 GCP 프로젝트**의 Agent Engine 에 배포한다.

API 키는 이 스크립트가 다루지 않는다 — 고객 관리자가 Secret Manager 에 넣어 두고(README-GEMINI.md 1단계),
배포 설정은 그 비밀의 **이름**만 참조한다(SecretRef → 실행 시 환경변수 LM_API_KEY).

사용:
  python3 deploy/deploy.py --project P --location asia-northeast3 --staging-bucket gs://B \\
      --secret lm-daas-api-key --model <Gemini 모델 ID> [--report-bucket B2] [--dry-run]

  --check-key   배포 전에 비밀 값으로 검증 호출(keyword_info ads_metrics 1키워드 · 약 1크레딧).
                배포 계정에 그 비밀의 Secret Accessor 권한이 있어야 한다. 값은 출력하지 않는다.
  --dry-run     배포하지 않고 설정만 출력한다(키·비밀 값은 읽지 않는다)

배포 뒤 할 일(이 스크립트가 끝에 다시 안내한다):
  ① Agent Engine 서비스 에이전트(service-<프로젝트 번호>@gcp-sa-aiplatform-re.iam.gserviceaccount.com)에
     그 비밀의 roles/secretmanager.secretAccessor — 없으면 배포는 성공해도 컨테이너가 뜨지 않는다
  ② Gemini Enterprise 관리자가 콘솔 > 에이전트 > "Custom agent via Agent Runtime" 으로 출력된 리소스 이름을 등록
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "lima_agent"
REQUIREMENTS = (ROOT / "deploy/requirements.txt").read_text(encoding="utf-8").split()


def build_env(a) -> dict:
    """Agent Engine 환경변수 — 키는 SecretRef(이름)로만."""
    env: dict = {"LM_AGENT_MODEL": a.model, "LM_SESSION_BUDGET": str(a.session_budget),
                 "LM_SESSION_BUDGET_MAX": str(a.session_budget_max), "LM_AUTO_APPROVE_CREDITS": str(a.auto_approve)}
    if a.api_base:
        env["LM_API_BASE"] = a.api_base
    if a.report_bucket:
        env["LM_REPORT_BUCKET"] = a.report_bucket.removeprefix("gs://")
    return env


def check_key(a) -> None:
    from google.cloud import secretmanager                                  # noqa: PLC0415
    name = f"projects/{a.project}/secrets/{a.secret}/versions/{a.secret_version}"
    key = secretmanager.SecretManagerServiceClient().access_secret_version(name=name).payload.data.decode().strip()
    sys.path.insert(0, str(PKG / "skills/lima-agents/scripts"))
    sys.path.insert(0, str(PKG / "skills/lima-agents"))
    import setup_key                                                         # noqa: PLC0415
    from api import client as lm                                             # noqa: PLC0415
    code, msg, r = setup_key.validate(key, (a.api_base or lm.BASE_URL).rstrip("/"))
    if code != 0:
        raise SystemExit(f"[키 검증] {msg} — 배포를 멈춘다")
    print(f"[키 검증] 성공 · 이번 호출 {(r.get('cost_detail') or {}).get('total_cost')}크레딧 · "
          f"월간 누적 {r.get('used_credits')} (잔여량 아님)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--location", required=True, help="Agent Engine 리전 (예: asia-northeast3 · us-central1)")
    ap.add_argument("--staging-bucket", required=True, help="gs://… 배포 묶음 업로드용")
    ap.add_argument("--secret", required=True, help="DaaS 키를 담은 Secret Manager 비밀 이름")
    ap.add_argument("--secret-version", default="latest")
    ap.add_argument("--model", required=True, help="그 리전에서 쓸 수 있는 Gemini 모델 ID")
    ap.add_argument("--display-name", default="ListeningMind 리서치 에이전트")
    ap.add_argument("--api-base", default="", help="DaaS API 주소 (기본: 운영)")
    ap.add_argument("--report-bucket", default="", help="리포트 HTML 을 올릴 GCS 버킷 — 조직 내부 인증 링크로 공유")
    ap.add_argument("--service-account", default="", help="에이전트 실행 서비스 계정 (기본: Agent Engine 기본값)")
    ap.add_argument("--session-budget", type=int, default=3000)
    ap.add_argument("--session-budget-max", type=int, default=20000)
    ap.add_argument("--auto-approve", type=int, default=30, help="이 이하 견적은 확인 없이 실행")
    ap.add_argument("--check-key", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    if not (PKG / "skills/lima-agents/api/client.py").is_file():
        raise SystemExit("lima_agent/skills/ 가 없다 — 배포 패키지(zip)를 풀어 그 루트에서 실행한다")
    env = build_env(a)
    plan = {"project": a.project, "location": a.location, "display_name": a.display_name,
            "requirements": REQUIREMENTS, "extra_packages": ["lima_agent"],
            "env_vars": {**env, "LM_API_KEY": f"SecretRef({a.secret}:{a.secret_version})"},
            "service_account": a.service_account or "(Agent Engine 기본)"}
    print(json.dumps(plan, ensure_ascii=False, indent=1))
    if a.dry_run:
        return 0
    if a.check_key:
        check_key(a)

    os.environ.update(env)                         # agent.py 가 import 시 LM_AGENT_MODEL 을 읽는다
    os.chdir(ROOT)                                 # extra_packages 는 상대 경로로 묶인다
    sys.path.insert(0, str(ROOT))
    import vertexai                                                          # noqa: PLC0415
    from google.cloud.aiplatform_v1.types import env_var                     # noqa: PLC0415
    from vertexai import agent_engines                                       # noqa: PLC0415
    from lima_agent.agent import root_agent                                  # noqa: PLC0415

    vertexai.init(project=a.project, location=a.location, staging_bucket=a.staging_bucket)
    env_vars = {**env, "LM_API_KEY": env_var.SecretRef(secret=a.secret, version=a.secret_version)}
    kw = {"service_account": a.service_account} if a.service_account else {}
    remote = agent_engines.create(
        agent_engines.AdkApp(agent=root_agent),
        requirements=REQUIREMENTS, extra_packages=["lima_agent"], display_name=a.display_name,
        description="ListeningMind DaaS 검색 행동 데이터 리서치 (lima-universal)", env_vars=env_vars, **kw)
    print(f"\n[배포 완료] {remote.resource_name}")
    print("\n다음 할 일:\n"
          f"  ① 비밀 접근 권한 — gcloud secrets add-iam-policy-binding {a.secret} --project {a.project} \\\n"
          "       --member serviceAccount:service-<프로젝트 번호>@gcp-sa-aiplatform-re.iam.gserviceaccount.com \\\n"
          "       --role roles/secretmanager.secretAccessor\n"
          "  ② Gemini Enterprise 콘솔 > 에이전트 > 'Custom agent via Agent Runtime' 에 위 리소스 이름 등록\n"
          f"  ③ python3 deploy/smoke.py --project {a.project} --location {a.location} --resource <위 리소스 이름> 으로 DaaS 0크레딧 점검")
    return 0


if __name__ == "__main__":
    sys.exit(main())
