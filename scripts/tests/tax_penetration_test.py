#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tax penetration test (no external network):
- Build deterministic sample dataset
- Compute VAT payable: output VAT - deductible input VAT + input tax transfer-out
- Compute surtaxes (附加税): e.g., 城建税/教育费附加/地方教育附加 (configurable)
- Generate a "return" object + expected voucher lines
- Assert: math correctness, sign correctness, and voucher debit/credit balance.

This script does NOT call remote tax bureau APIs; it validates core calculation plumbing.
"""

from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Tuple

D = Decimal

def q2(x: Decimal) -> Decimal:
    return x.quantize(D("0.01"), rounding=ROUND_HALF_UP)

@dataclass
class VatInvoice:
    amount_excl_tax: Decimal
    tax_amount: Decimal
    tax_rate: Decimal
    status: str
    certify_status: str
    usage: str
    transfer_out: Decimal = D("0.00")

def calc_vat(input_invoices: List[VatInvoice], output_sales: List[VatInvoice]) -> Dict[str, Decimal]:
    # output VAT: sum of tax_amount where status is normal and treated as taxable
    out_vat = sum((i.tax_amount for i in output_sales if i.status == "normal"), D("0.00"))

    # deductible input VAT:
    # only normal, certified, usage=deductible
    in_deduct = sum(
        (i.tax_amount for i in input_invoices
         if i.status == "normal" and i.certify_status in ("deducted", "certified") and i.usage == "deductible"),
        D("0.00")
    )

    transfer_out = sum((i.transfer_out for i in input_invoices if i.transfer_out > 0), D("0.00"))
    vat_payable = out_vat - in_deduct + transfer_out
    return {
        "out_vat": q2(out_vat),
        "in_deduct": q2(in_deduct),
        "transfer_out": q2(transfer_out),
        "vat_payable": q2(vat_payable),
    }

def calc_surtax(vat_payable: Decimal, rates: Dict[str, Decimal]) -> Dict[str, Decimal]:
    # rates: e.g., {"city":0.07, "edu":0.03, "local_edu":0.02}
    surtaxes = {k: q2(vat_payable * v) for k, v in rates.items()}
    surtaxes["total"] = q2(sum(surtaxes.values(), D("0.00")))
    return surtaxes

def build_expected_voucher(vat_payable: Decimal, surtax_total: Decimal) -> List[Tuple[str, Decimal, Decimal]]:
    """
    Simple payable model:
    - Recognize tax expense and tax payable.
    - In real system, VAT payable may net against input VAT carry-forward; here we test correctness of mapping.
    """
    lines = []
    if vat_payable >= 0:
        # Dr: Taxes & surcharges expense (or tax expense) ; Cr: VAT payable
        lines.append(("tax_expense_vat", q2(vat_payable), D("0.00")))
        lines.append(("vat_payable", D("0.00"), q2(vat_payable)))
    else:
        # VAT refundable/carry-forward
        lines.append(("vat_refundable", q2(-vat_payable), D("0.00")))
        lines.append(("tax_expense_vat", D("0.00"), q2(-vat_payable)))

    if surtax_total > 0:
        lines.append(("tax_expense_surtax", q2(surtax_total), D("0.00")))
        lines.append(("surtax_payable", D("0.00"), q2(surtax_total)))

    # assert balanced
    dr = sum((l[1] for l in lines), D("0.00"))
    cr = sum((l[2] for l in lines), D("0.00"))
    if q2(dr) != q2(cr):
        raise AssertionError(f"voucher not balanced: dr={dr} cr={cr}")
    return lines

def main() -> None:
    # Sample scenario:
    # - Output sales: taxable sales 100,000 excl, VAT 13,000
    # - Input invoices: deductible VAT 6,500 (50,000*13%)
    # - Transfer-out: 1,000 (change-of-use / abnormal loss)
    out = [VatInvoice(D("100000.00"), D("13000.00"), D("0.13"), "normal", "n/a", "taxable")]
    inn = [
        VatInvoice(D("50000.00"), D("6500.00"), D("0.13"), "normal", "certified", "deductible", transfer_out=D("0.00")),
        VatInvoice(D("0.00"), D("0.00"), D("0.00"), "normal", "certified", "deductible", transfer_out=D("1000.00")),
    ]

    vat = calc_vat(inn, out)
    assert vat["out_vat"] == D("13000.00")
    assert vat["in_deduct"] == D("6500.00")
    assert vat["transfer_out"] == D("1000.00")
    assert vat["vat_payable"] == D("7500.00")

    surtax = calc_surtax(vat["vat_payable"], {"city": D("0.07"), "edu": D("0.03"), "local_edu": D("0.02")})
    # total rate 12% => 900.00
    assert surtax["total"] == D("900.00")

    voucher = build_expected_voucher(vat["vat_payable"], surtax["total"])
    # Smoke: print proof
    print("VAT:", vat)
    print("SURTAX:", surtax)
    print("VOUCHER_LINES:")
    for sub, dr, cr in voucher:
        print(f"  {sub}: DR={dr} CR={cr}")

if __name__ == "__main__":
    main()


# ---- DB wiring (optional) -----------------------------------------------------
import os, json as _json
import pathlib
from datetime import date as _date, datetime as _dt

def _load_map() -> dict:
    mp = pathlib.Path("app/config/tax_voucher_map.json")
    return _json.loads(mp.read_text(encoding="utf-8"))

def build_voucher_payload(vat_payable: Decimal, surtax_total: Decimal) -> dict:
    mp = _load_map()
    lines = build_expected_voucher(vat_payable, surtax_total)
    return {
        "source_type": mp["voucher_source_type"],
        "voucher_date": _date.today().isoformat(),
        "summary": f'{mp["voucher_summary_prefix"]} { _date.today().isoformat() }',
        "lines": [
            {"subject_code": sub, "debit": str(dr), "credit": str(cr)}
            for sub, dr, cr in lines
        ]
    }

def write_preview(payload: dict) -> str:
    out = pathlib.Path("artifacts/tax_voucher_preview.json")
    out.write_text(_json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out)

def main_db_wire() -> None:
    # Always create preview artifact
    out = [VatInvoice(D("100000.00"), D("13000.00"), D("0.13"), "normal", "n/a", "taxable")]
    inn = [
        VatInvoice(D("50000.00"), D("6500.00"), D("0.13"), "normal", "certified", "deductible", transfer_out=D("0.00")),
        VatInvoice(D("0.00"), D("0.00"), D("0.00"), "normal", "certified", "deductible", transfer_out=D("1000.00")),
    ]
    vat = calc_vat(inn, out)
    surtax = calc_surtax(vat["vat_payable"], {"city": D("0.07"), "edu": D("0.03"), "local_edu": D("0.02")})
    payload = build_voucher_payload(vat["vat_payable"], surtax["total"])
    preview_path = write_preview(payload)
    print(f"[preview] wrote {preview_path}")

    # Optional DB write (requires mysqlclient/pymysql or your existing DB layer; keep portable)
    # We only attempt if env TAX_GL_WRITE=1 and pymysql exists.
    if os.environ.get("TAX_GL_WRITE", "0") != "1":
        print("[db] TAX_GL_WRITE!=1, skip db write.")
        return
    try:
        import pymysql  # type: ignore
    except Exception as e:
        print(f"[db] pymysql missing, skip db write. err={e}")
        return

    db = {
        "host": os.environ.get("DB_HOST","127.0.0.1"),
        "port": int(os.environ.get("DB_PORT","3306")),
        "user": os.environ.get("DB_USER","root"),
        "password": os.environ.get("DB_PASSWORD",""),
        "database": os.environ.get("DB_NAME","xinyi_ai"),
        "charset": "utf8mb4",
        "autocommit": False,
    }
    print(f"[db] connecting {db['host']}:{db['port']}/{db['database']} user={db['user']}")
    conn = pymysql.connect(**db)
    try:
        with conn.cursor() as cur:
            # Minimal insert: assumes gl_vouchers/gl_voucher_entries exist.
            # You may need to adapt column names; we keep it best-effort and fail-fast.
            cur.execute(
                "INSERT INTO gl_vouchers (ledger_id, voucher_date, source_type, source_id, status, created_at) "
                "VALUES (%s,%s,%s,%s,%s,NOW())",
                (1, payload["voucher_date"], payload["source_type"], 0, "posted"),
            )
            voucher_id = cur.lastrowid
            line_no = 1
            for ln in payload["lines"]:
                # subject lookup by code
                cur.execute("SELECT id FROM gl_subjects WHERE ledger_id=%s AND code=%s", (1, ln["subject_code"]))
                row = cur.fetchone()
                if not row:
                    raise RuntimeError(f"subject code not found: {ln['subject_code']}")
                subject_id = row[0]
                cur.execute(
                    "INSERT INTO gl_voucher_entries (voucher_id, line_no, subject_id, summary, debit_amount, credit_amount, created_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,NOW())",
                    (voucher_id, line_no, subject_id, payload["summary"], ln["debit"], ln["credit"])
                )
                line_no += 1
        conn.commit()
        print(f"[db] wrote voucher_id={voucher_id}")
    finally:
        conn.close()

# Execute DB wire in addition to existing main
if __name__ == "__main__":
    try:
        main_db_wire()
    except Exception as e:
        print(f"[wire] FAIL: {e}")
