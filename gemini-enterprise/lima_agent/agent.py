"""ListeningMind 리서치 에이전트 — Gemini Enterprise 등록용 ADK root_agent.

모델은 배포 시 환경변수 LM_AGENT_MODEL 로 정한다(고객 리전에서 쓸 수 있는 Gemini 모델 — deploy/deploy.py --model).
"""
from __future__ import annotations

import os
from pathlib import Path

from google.adk.agents import Agent

from .tools import TOOLS

MODEL = os.environ.get("LM_AGENT_MODEL", "").strip()
if not MODEL:
    raise RuntimeError("LM_AGENT_MODEL 이 비어 있다 — 배포 시 --model 로 Gemini 모델을 지정한다")

root_agent = Agent(
    name="lima_universal",
    model=MODEL,
    description="ListeningMind 검색 행동 데이터로 시장·브랜드·상품·검색 여정 질문에 답하는 리서치 에이전트",
    instruction=(Path(__file__).with_name("instruction.md")).read_text(encoding="utf-8"),
    tools=TOOLS,
)
