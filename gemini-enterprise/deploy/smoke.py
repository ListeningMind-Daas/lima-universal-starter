#!/usr/bin/env python3
"""배포된 에이전트 점검 — DaaS 크레딧 0 (Gemini 모델 호출 비용만 든다).

에이전트에게 크레딧 현황(credit_status)과 규칙 문서 목록(list_references)만 묻는다 — 둘 다 DaaS 를 부르지 않는다.
키가 주입됐는지는 이 점검으로 알 수 없다(키를 쓰는 도구를 부르지 않으므로). 키 확인은 deploy.py --check-key.

사용: python3 deploy/smoke.py --project P --location L --resource projects/…/reasoningEngines/…
"""
from __future__ import annotations

import argparse
import json
import sys

PROMPT = "credit_status 와 list_references 도구만 호출해서 결과를 짧게 알려줘. 다른 도구는 부르지 마."


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True)
    ap.add_argument("--location", required=True)
    ap.add_argument("--resource", required=True)
    ap.add_argument("--user-id", default="smoke-test")
    a = ap.parse_args(argv)

    import vertexai                                                          # noqa: PLC0415
    from vertexai import agent_engines                                       # noqa: PLC0415
    vertexai.init(project=a.project, location=a.location)
    remote = agent_engines.get(a.resource)
    calls, text = [], []
    for ev in remote.stream_query(message=PROMPT, user_id=a.user_id):
        for part in ((ev.get("content") or {}).get("parts") or []):
            if part.get("function_call"):
                calls.append(part["function_call"].get("name"))
            if part.get("text"):
                text.append(part["text"])
    print(json.dumps({"tool_calls": calls, "reply": "".join(text)[:800]}, ensure_ascii=False, indent=1))
    paid = {"keyword_info", "intent_finder", "cluster_finder", "path_finder", "serp", "trend_finder"} & set(calls)
    if paid:
        print(f"✗ 점검에서 유료 도구가 불렸다: {sorted(paid)} — 지시문(instruction.md) 확인", file=sys.stderr)
        return 2
    ok = "credit_status" in calls and "list_references" in calls
    print("✓ 점검 통과" if ok else "✗ 기대한 도구가 불리지 않았다", file=sys.stderr if not ok else sys.stdout)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
