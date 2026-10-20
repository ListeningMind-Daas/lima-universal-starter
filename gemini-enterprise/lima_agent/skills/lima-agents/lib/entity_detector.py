"""엔티티 감지 (브랜드·성분·기타).

Python 후보 추출 (첫 단어 3회+ 반복) + WebSearch 검증 (Claude 대화 내 처리).
이 모듈은 · 후보 추출·products 조립 등 순수 계산만.
"""
from __future__ import annotations

from collections import Counter
import re

MIN_OCCURRENCE = 3


def extract_candidates(keywords: list[str]) -> list[str]:
    """키워드 리스트에서 · 첫 단어가 3회+ 반복되는 것 후보로."""
    first_words = Counter()
    for kw in keywords:
        parts = re.split(r"\s+", kw.strip())
        if parts and parts[0]:
            first_words[parts[0]] += 1
    return [w for w, c in first_words.most_common() if c >= MIN_OCCURRENCE]


def build_products(entity_name: str, kw2vol: dict[str, int]) -> list[dict]:
    """엔티티 관련 키워드 · products 배열.

    1. 엔티티 이름 자체가 노드에 있으면 최우선 포함
    2. 엔티티 이름으로 시작하는 파생어 · 볼륨 순
    """
    products = []
    if entity_name in kw2vol:
        products.append({"keyword": entity_name, "volume": kw2vol[entity_name]})
    prefix_kws = [
        (kw, vol)
        for kw, vol in kw2vol.items()
        if kw != entity_name and kw.startswith(entity_name)
    ]
    prefix_kws.sort(key=lambda x: -x[1])
    products.extend({"keyword": kw, "volume": vol} for kw, vol in prefix_kws)
    return products


def assemble_entity(
    name: str,
    category: str,
    description: str,
    source_url: str,
    kw2vol: dict[str, int],
    sub_lines: list[str] | None = None,
) -> dict:
    """엔티티 단일 항목 dict 조립.

    category · 'brands' | 'ingredients' | 'other' (호출 측에서 판단)
    """
    products = build_products(name, kw2vol)
    brand_vol = kw2vol.get(name, 0)
    total_vol = sum(p["volume"] for p in products)
    return {
        "name": name,
        "description": description,
        "source_url": source_url or "",
        "sub_lines": sub_lines or [],
        "brand_volume": brand_vol,
        "products": products,
        "product_count": len(products),
        "total_volume": total_vol,
    }
