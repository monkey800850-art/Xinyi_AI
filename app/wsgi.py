import os
from app import config  # ensure env loader exists (if your project uses it)
from app import __init__  # package marker

# Import create_app from project root app.py
from importlib.util import spec_from_file_location, module_from_spec

spec = spec_from_file_location("appfile", "app.py")
m = module_from_spec(spec)
spec.loader.exec_module(m)

create_app = getattr(m, "create_app")
app = create_app()

# Optional: expose for gunicorn / tooling
application = app
