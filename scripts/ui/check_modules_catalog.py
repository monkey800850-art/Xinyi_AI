import json, sys, os

CATALOG_PATH = "app/modules_catalog.json"
ALLOWED_STATUS = {"active", "stub", "hidden"}
REQUIRED = {"key", "title", "path", "source", "status"}

def die(msg):
    print("ERROR:", msg)
    sys.exit(1)

if not os.path.exists(CATALOG_PATH):
    die(f"missing {CATALOG_PATH}")

data = json.load(open(CATALOG_PATH, "r", encoding="utf-8"))

mode = None
entries = []

# Mode A: items[]
if isinstance(data.get("items"), list) and len(data.get("items")) > 0:
    mode = "items"
    entries = data["items"]

# Mode B: groups{ name: [ ... ] }
elif isinstance(data.get("groups"), dict) and len(data.get("groups")) > 0:
    mode = "groups"
    for gname, arr in data["groups"].items():
        if not isinstance(arr, list):
            die(f"group '{gname}' is not a list")
        for it in arr:
            if not isinstance(it, dict):
                die(f"group '{gname}' has non-dict entry: {it!r}")
            it.setdefault("group", gname)
            entries.append(it)

else:
    die("catalog has neither non-empty items[] nor non-empty groups{}")

bad = []
for it in entries:
    miss = REQUIRED - set(it.keys())
    if miss:
        bad.append((it.get("key"), "missing=" + ",".join(sorted(miss))))
        continue

    path = it["path"]
    if not isinstance(path, str) or not path.startswith("/"):
        bad.append((it.get("key"), f"invalid path={path!r}"))

    st = it["status"]
    if st not in ALLOWED_STATUS:
        bad.append((it.get("key"), f"invalid status={st!r}"))

if bad:
    print(f"mode={mode} entries={len(entries)}")
    for k, reason in bad[:50]:
        print("BAD:", k, reason)
    sys.exit(1)

print(f"OK mode={mode} entries={len(entries)}")
