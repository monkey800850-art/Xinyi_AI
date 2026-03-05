#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = ROOT / "docs" / "evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        if not k:
            continue
        # Keep existing environment precedence.
        if k not in os.environ:
            os.environ[k] = v.strip()


def load_flask_app():
    load_dotenv()
    sys.path.insert(0, str(ROOT))
    try:
        from app.wsgi import app as flask_app  # type: ignore
        return flask_app
    except Exception:
        pass

    try:
        import app as app_module  # type: ignore
        if hasattr(app_module, "create_app"):
            return app_module.create_app()
        if hasattr(app_module, "app"):
            return app_module.app
    except Exception as exc:
        raise RuntimeError(f"Unable to import Flask app: {exc}") from exc

    raise RuntimeError("Unable to locate Flask application instance")


def main() -> int:
    app = load_flask_app()

    entries = []
    for rule in app.url_map.iter_rules():
        methods = sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"})
        entries.append(
            {
                "path": str(rule.rule),
                "methods": methods,
                "endpoint": str(rule.endpoint),
            }
        )

    entries = sorted(entries, key=lambda x: (x["path"], ",".join(x["methods"]), x["endpoint"]))

    api_entries = [e for e in entries if e["path"].startswith("/api/")]
    api_paths = sorted({e["path"] for e in api_entries})

    (EVIDENCE_DIR / "api_index.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (EVIDENCE_DIR / "api_paths.txt").write_text(
        "\n".join(api_paths) + ("\n" if api_paths else ""),
        encoding="utf-8",
    )

    print(f"API_INDEX_OK total_routes={len(entries)} api_routes={len(api_entries)} unique_api_paths={len(api_paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
