"""usage API wrapper.

Endpoint · GET /usage/summary

사용량 대시보드 집계 조회 — 기간별 크레딧 소비 정산·리포트용.
크레딧 수치는 소비 로그이며 잔액이 아님 · 계약 잔여량은 담당자에게 문의.
"""
from __future__ import annotations

from .client import DaasClient


def summary(
    client: DaasClient,
    date_from: str,
    date_to: str,
    platform: str | None = None,
) -> dict:
    """기간별 사용량 집계 조회.

    - date_from / date_to · "YYYY-MM-DD" (필수)
    - platform · 선택 필터

    Returns · 원본 API 응답 dict
    """
    params = {"from": date_from, "to": date_to, "platform": platform}
    return client.get("usage/summary", params)
