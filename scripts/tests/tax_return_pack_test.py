#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import json
import uuid
from decimal import Decimal
from datetime import date
from pathlib import Path

D = Decimal

def d(x: str) -> Decimal:
    return Decimal(x)

def load_voucher_preview() -> dict:
    p = Path("artifacts/tax_voucher_preview.json")
    if not p.exists():
        raise RuntimeError("missing artifacts/tax_voucher_preview.json; run TAX-GL-WIRE-02 first")
    return json.loads(p.read_text(encoding="utf-8"))

def sum_by_subject(lines, subject_code: str, side: str) -> Decimal:
    # side: "debit" or "credit"
    s = D("0.00")
    for ln in lines:
        if ln["subject_code"] == subject_code:
            s += d(ln[side])
    return s

def build_vat_return_pack(voucher: dict) -> dict:
    lines = voucher["lines"]
    vat_payable = sum_by_subject(lines, "vat_payable", "credit") - sum_by_subject(lines, "vat_payable", "debit")
    surtax_payable = sum_by_subject(lines, "surtax_payable", "credit") - sum_by_subject(lines, "surtax_payable", "debit")

    # For this stage we only validate payable numbers (税额口径穿透)
    today = date.today()
    period = today.strftime("%Y%m")

    pack = {
        "pack_id": f"taxpack-{period}-{uuid.uuid4().hex[:12]}",
        "tax_type": "VAT",
        "period": period,
        "generated_on": today.isoformat(),
        "summary": voucher.get("summary", ""),
        "vat": {
            "vat_payable": str(vat_payable),
            "surtax_total": str(surtax_payable)
        },
        "attachments": {
            "voucher_preview_path": "artifacts/tax_voucher_preview.json"
        }
    }
    return pack

def build_archive_manifest(return_pack: dict) -> dict:
    # This is “电子档案元数据”，不做真实验签，只保留字段与状态
    manifest = {
        "metadata_pack_id": return_pack["pack_id"],
        "original_format": "JSON",
        "signature_verify_status": "not_applicable",
        "archive_dir_path": f"var/archives/tax/{return_pack['period']}/{return_pack['tax_type'].lower()}",
        "retention_years": 10,
        "regulator_report_status": "not_submitted",
        "source": {
            "type": "tax_return_pack",
            "path": f"artifacts/tax_return_pack_{return_pack['period']}_vat.json"
        }
    }
    return manifest

def main() -> None:
    voucher = load_voucher_preview()
    pack = build_vat_return_pack(voucher)

    out_pack = Path(f"artifacts/tax_return_pack_{pack['period']}_vat.json")
    out_pack.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = build_archive_manifest(pack)
    out_manifest = Path("artifacts/tax_archive_manifest.json")
    out_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # Assertions: payable must match voucher lines
    lines = voucher["lines"]
    vat_payable_voucher = sum_by_subject(lines, "vat_payable", "credit") - sum_by_subject(lines, "vat_payable", "debit")
    surtax_payable_voucher = sum_by_subject(lines, "surtax_payable", "credit") - sum_by_subject(lines, "surtax_payable", "debit")

    if d(pack["vat"]["vat_payable"]) != vat_payable_voucher:
        raise AssertionError("vat payable mismatch between return pack and voucher preview")
    if d(pack["vat"]["surtax_total"]) != surtax_payable_voucher:
        raise AssertionError("surtax mismatch between return pack and voucher preview")

    print("[OK] wrote", str(out_pack))
    print("[OK] wrote", str(out_manifest))
    print("[ASSERT] vat_payable =", vat_payable_voucher, "surtax_total =", surtax_payable_voucher)

if __name__ == "__main__":
    main()
