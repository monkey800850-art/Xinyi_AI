#!/usr/bin/env python3
from __future__ import annotations
import runpy
import sys
from pathlib import Path


def main():
    here = Path(__file__).resolve().parents[2]
    app_py = here / "app.py"

    if str(here) not in sys.path:
        sys.path.insert(0, str(here))

    ns = runpy.run_path(str(app_py), run_name="xinyi_app_entry")
    app = ns.get("app")
    if app is None:
        raise SystemExit("ERROR: app not found in app.py")

    rules = []
    for r in sorted(app.url_map.iter_rules(), key=lambda x: str(x)):
        methods = ",".join(sorted([m for m in (r.methods or []) if m not in ("HEAD", "OPTIONS")]))
        rules.append(f"{r.rule}\t{methods}\t{r.endpoint}")

    Path("evidence/UI-HOME-WIRE-01/url_map.txt").write_text("\n".join(rules) + "\n", encoding="utf-8")

    root = [x for x in rules if x.split("\t", 1)[0] == "/"]
    Path("evidence/UI-HOME-WIRE-01/root_rules.txt").write_text(
        "\n".join(root) + ("\n" if root else ""), encoding="utf-8"
    )

    print("total_rules=", len(rules))
    print("root_rules=", len(root))
    for x in root:
        print(x)


if __name__ == "__main__":
    main()
