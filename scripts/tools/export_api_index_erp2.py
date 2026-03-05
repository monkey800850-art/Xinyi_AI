#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def load_dotenv():
    env = ROOT / '.env'
    if not env.exists():
        return
    for raw in env.read_text(encoding='utf-8', errors='replace').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        k = k.strip()
        if k and k not in os.environ:
            os.environ[k] = v.strip()


def find_app():
    load_dotenv()

    try:
        from app.wsgi import app as flask_app  # type: ignore
        return flask_app
    except Exception:
        pass

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location('xinyi_app_py', str(ROOT / 'app.py'))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore
        if hasattr(mod, 'create_app'):
            return mod.create_app()
        for _, v in mod.__dict__.items():
            if getattr(v.__class__, '__name__', '') == 'Flask':
                return v
    except Exception as e:
        print('WARN import app.py failed:', e)

    raise SystemExit('FATAL: cannot locate Flask app instance for url_map export')


app = find_app()
items = []
for rule in app.url_map.iter_rules():
    methods = sorted([m for m in rule.methods if m not in ('HEAD', 'OPTIONS')])
    path = str(rule.rule)
    endpoint = str(rule.endpoint)
    if path.startswith('/static'):
        continue
    items.append({'path': path, 'methods': methods, 'endpoint': endpoint})

items = sorted(items, key=lambda x: (x['path'], ','.join(x['methods']), x['endpoint']))
out = {
    'generated_at': datetime.now().isoformat(timespec='seconds'),
    'count': len(items),
    'items': items,
}
Path('docs/evidence_erp2').mkdir(parents=True, exist_ok=True)
Path('docs/evidence_erp2/api_index.json').write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print('OK api_index.json count=', len(items))
