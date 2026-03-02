from uuid import uuid4


def make_book_payload(
    sid: str,
    suffix: str = "",
    account_book_type: str = "legal",
    start_period: str = "2026-01",
) -> dict:
    suffix_part = f"{suffix}_" if suffix else ""
    nonce = uuid4().hex[:8]
    uniq = f"{suffix_part}{nonce}"
    return {
        "book_code": f"BK_{sid}_{uniq}",
        "book_name": f"TestBook_{sid}_{uniq}",
        "name": f"TestBook_{sid}_{uniq}",
        "start_period": start_period,
        "account_book_type": account_book_type,
        "accounting_standard": "enterprise",
    }
