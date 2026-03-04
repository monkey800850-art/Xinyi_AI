#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import json
from decimal import Decimal
from pathlib import Path

D = Decimal

def d(x: str) -> Decimal:
    return Decimal(x)

def load_json(p: str) -> dict:
    pp = Path(p)
    if not pp.exists():
        raise RuntimeError(f"missing file: {p}")
    return json.loads(pp.read_text(encoding="utf-8"))

def main() -> None:
    # locate latest return pack by glob
    packs = sorted(Path("artifacts").glob("tax_return_pack_*_vat.json"))
    if not packs:
        raise RuntimeError("no return pack found; run TAX-RETURN-PACK-03 first")
    pack_path = packs[-1]
    pack = load_json(str(pack_path))

    # load form templates
    vat_form = load_json("app/config/tax_forms/vat_general_v1.json")
    surtax_form = load_json("app/config/tax_forms/surtax_v1.json")

    vat_payable = d(pack["vat"]["vat_payable"])
    surtax_total = d(pack["vat"]["surtax_total"])

    # For this stage, we only fill the payable lines from pack, and compute surtax breakdown deterministically
    city = (vat_payable * D("0.07")).quantize(D("0.01"))
    edu = (vat_payable * D("0.03")).quantize(D("0.01"))
    local_edu = (vat_payable * D("0.02")).quantize(D("0.01"))
    computed_total = (city + edu + local_edu).quantize(D("0.01"))

    # Assertions
    if computed_total != surtax_total:
        raise AssertionError(f"surtax total mismatch: computed={computed_total} pack={surtax_total}")

    forms_out = {
        "period": pack["period"],
        "pack_id": pack["pack_id"],
        "forms": [
            {
                "form_code": vat_form["form_code"],
                "version": vat_form["version"],
                "lines": [
                    {"line_no": "20", "name": "应纳税额", "amount": str(vat_payable), "source": "pack", "trace": pack_path.name}
                ]
            },
            {
                "form_code": surtax_form["form_code"],
                "version": surtax_form["version"],
                "lines": [
                    {"line_no": "A1", "name": "城建税", "amount": str(city), "source": "computed", "trace": "vat_payable*7%"},
                    {"line_no": "A2", "name": "教育费附加", "amount": str(edu), "source": "computed", "trace": "vat_payable*3%"},
                    {"line_no": "A3", "name": "地方教育附加", "amount": str(local_edu), "source": "computed", "trace": "vat_payable*2%"},
                    {"line_no": "A9", "name": "附加税合计", "amount": str(computed_total), "source": "computed", "trace": "sum(A1..A3)"}
                ]
            }
        ]
    }

    out = Path(f"artifacts/tax_forms_{pack['period']}.json")
    out.write_text(json.dumps(forms_out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[OK] wrote", str(out))
    print("[ASSERT] surtax_total=", surtax_total, "computed_total=", computed_total)

if __name__ == "__main__":
    main()
