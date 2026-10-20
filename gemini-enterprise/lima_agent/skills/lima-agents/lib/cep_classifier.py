"""CEP 7W LLM 병렬 분류.

키워드 리스트를 · Claude가 의미로 7W (WHY·WHEN·WHERE·WHILE·WHOM·WITH_WHAT·HOW_FEEL)에 분류.

주의 · 이 스킬은 Anthropic SDK 대신 · Claude Desktop 대화 내 · Claude가 직접 분류하는 방식.
Python 함수는 · 분류 결과를 받아서 병합·서브그룹 계산·구조 조립만.
"""
from __future__ import annotations

from collections import defaultdict

W_LABELS = {
    "WHY": "왜? · 동기·목적",
    "WHEN": "언제? · 시점·타이밍",
    "WHERE": "어디서? · 장소·채널",
    "WHILE": "무엇 하면서? · 동반 활동",
    "WHOM": "누구와/누구를 위해? · 대상",
    "WITH_WHAT": "무엇과 함께? · 조합·페어링",
    "HOW_FEEL": "어떤 감정으로? · 상태·감정",
}
W_ORDER = list(W_LABELS.keys())
BATCH_SIZE = 150

CLASSIFY_PROMPT = """당신은 CEP 7W 프레임워크로 키워드를 분류하는 조사원이다.
카테고리: {category} · 시장: {gl}

아래 키워드들을 7W 중 하나 이상에 분류하라. 해당 안 되면 넣지 말 것.

7W 정의:
- WHY: 동기·목적·이유 (예: 다이어트, 근성장, 선물)
- WHEN: 시점·타이밍·시즌 (예: 아침, 운동 후, 겨울)
- WHERE: 장소·채널·구매처 (예: 편의점, 온라인, 카페)
- WHILE: 동반 활동·행위 중 (예: 운동 중, 요리하며)
- WHOM: 대상·페르소나·수혜자 (예: 여성용, 아이, 초보)
- WITH_WHAT: 조합·페어링·같이 쓰는 것 (예: 우유와, 커피와)
- HOW_FEEL: 감정·상태·가치·품질 (예: 부작용, 가성비, 맛)

키워드 리스트:
{keywords_json}

JSON 응답만 (다른 텍스트 없음):
{{"WHY": ["kw1", ...], "WHEN": [...], "WHERE": [...], "WHILE": [...], "WHOM": [...], "WITH_WHAT": [...], "HOW_FEEL": [...]}}
"""

SUBGROUP_PROMPT = """카테고리: {category}
7W 중 {w_key} ({w_label})에 분류된 키워드들이다.
의미가 비슷한 서브그룹 3~7개로 자동 묶어라.
각 서브그룹에 짧은 라벨 (2~10글자) 부여 · 한국 시장이면 한국어 · 미국 시장이면 영어.

키워드:
{keywords_json}

JSON 응답만:
{{"서브그룹1": ["kw", ...], "서브그룹2": [...]}}
"""


def build_batches(keywords: list[str], batch_size: int = BATCH_SIZE) -> list[list[str]]:
    return [keywords[i:i + batch_size] for i in range(0, len(keywords), batch_size)]


def merge_classification(batch_results: list[dict]) -> dict[str, list[str]]:
    """여러 배치 결과 병합 · 중복 제거."""
    merged = {w: [] for w in W_ORDER}
    seen = {w: set() for w in W_ORDER}
    for result in batch_results:
        for w in W_ORDER:
            for kw in result.get(w, []) or []:
                if kw not in seen[w]:
                    seen[w].add(kw)
                    merged[w].append(kw)
    return merged


def assemble_cep_grouped(
    subgroups_by_w: dict[str, dict[str, list[str]]],
    kw2vol: dict[str, int],
) -> dict:
    """서브그룹 결과를 최종 cep_grouped 구조로 조립.

    subgroups_by_w · {W_KEY: {sub_label: [kws]}}
    kw2vol · {keyword: volume}
    """
    cep_grouped = {}
    for w_key in W_ORDER:
        subs_input = subgroups_by_w.get(w_key, {})
        if not subs_input:
            continue
        subs_out = {}
        total_kws = set()
        for sub_label, kws in subs_input.items():
            kws_sorted = sorted(kws, key=lambda k: -kw2vol.get(k, 0))
            subs_out[sub_label] = {
                "keywords": [
                    {"keyword": k, "volume": kw2vol.get(k, 0)} for k in kws_sorted
                ],
                "count": len(kws_sorted),
                "total_volume": sum(kw2vol.get(k, 0) for k in kws_sorted),
            }
            total_kws.update(kws_sorted)
        if subs_out:
            cep_grouped[w_key] = {
                "label": W_LABELS[w_key],
                "subgroups": dict(
                    sorted(subs_out.items(), key=lambda x: -x[1]["total_volume"])
                ),
                "total_count": len(total_kws),
                "total_volume": sum(kw2vol.get(k, 0) for k in total_kws),
            }
    return cep_grouped
