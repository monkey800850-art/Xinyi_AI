import importlib.util
import os

spec = importlib.util.spec_from_file_location("appfile", "app.py")
m = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(m)

create_app = getattr(m, "create_app", None)
if create_app is None:
    raise RuntimeError("create_app not found in app.py")

app = create_app()

host = os.getenv("HOST", "0.0.0.0")
port = int(os.getenv("PORT", "5000"))
print(f"== Starting server on http://{host}:{port} ==")
app.run(host=host, port=port, debug=False)
