from typing import Dict, Optional


_CATEGORY_DEFS = {
    "ASSET": {"name": "资产", "prefixes": ("1",), "keywords": ("资产",)},
    "LIABILITY": {"name": "负债", "prefixes": ("2",), "keywords": ("负债",)},
    "EQUITY": {"name": "权益", "prefixes": ("3",), "keywords": ("权益", "所有者权益")},
    "COST": {"name": "成本", "prefixes": ("4",), "keywords": ("成本",)},
    "PNL": {"name": "损益", "prefixes": ("5", "6"), "keywords": ("损益", "收入", "费用", "收益")},
}


def derive_category_by_subject_code(subject_code: str) -> Dict[str, str]:
    code = (subject_code or "").strip()
    head = code[:1]
    for category_code, cfg in _CATEGORY_DEFS.items():
        if head in cfg["prefixes"]:
            return {"category_code": category_code, "category_name": cfg["name"]}
    return {"category_code": "UNKNOWN", "category_name": "未分类"}


def map_category_text(category_text: str) -> Optional[Dict[str, str]]:
    text = (category_text or "").strip()
    if not text:
        return None
    for category_code, cfg in _CATEGORY_DEFS.items():
        if any(k in text for k in cfg["keywords"]):
            return {"category_code": category_code, "category_name": cfg["name"]}
    return None


def check_category_consistency(subject_code: str, category_text: str) -> Dict[str, object]:
    derived = derive_category_by_subject_code(subject_code)
    mapped = map_category_text(category_text)
    if mapped is None:
        return {
            "ok": True,
            "reason": "category_empty_or_unmapped",
            "expected": derived,
            "actual": None,
        }
    return {
        "ok": mapped["category_code"] == derived["category_code"],
        "reason": "matched" if mapped["category_code"] == derived["category_code"] else "prefix_mismatch",
        "expected": derived,
        "actual": mapped,
    }


def resolve_subject_category(subject_code: str, category_text: str) -> Dict[str, str]:
    derived = derive_category_by_subject_code(subject_code)
    mapped = map_category_text(category_text)
    text = (category_text or "").strip()
    if not text:
        return {
            "category_code": derived["category_code"],
            "category_name": derived["category_name"],
            "category_source": "prefix_fallback",
        }
    if mapped is None:
        return {
            "category_code": derived["category_code"],
            "category_name": text,
            "category_source": "category_field",
        }
    if mapped["category_code"] == derived["category_code"]:
        return {
            "category_code": mapped["category_code"],
            "category_name": text,
            "category_source": "category_field",
        }
    return {
        "category_code": derived["category_code"],
        "category_name": derived["category_name"],
        "category_source": "prefix_fallback",
    }
