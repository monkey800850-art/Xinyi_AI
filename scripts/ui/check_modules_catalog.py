import json, sys, os

CATALOG_PATH="app/modules_catalog.json"
ALLOWED_STATUS={"active","stub","hidden"}

def die(msg):
    print("ERROR:", msg)
    sys.exit(1)

def iter_entries_from_groups(groups: dict):
    # Accept multiple shapes:
    # 1) groups[name] == list[entry]
    # 2) groups[name] == dict with one of: routes/templates/items lists
    for gname, gv in groups.items():
        if isinstance(gv, list):
            for it in gv:
                if not isinstance(it, dict):
                    die(f"group '{gname}' has non-dict entry: {it!r}")
                it.setdefault("group", gname)
                yield it
            continue

        if isinstance(gv, dict):
            # try routes/templates/items
            for subkey in ("items","routes","templates"):
                sub = gv.get(subkey)
                if isinstance(sub, list):
                    for it in sub:
                        if not isinstance(it, dict):
                            die(f"group '{gname}'[{subkey}] has non-dict entry: {it!r}")
                        it.setdefault("group", gname)
                        it.setdefault("source", "route" if subkey=="routes" else ("template" if subkey=="templates" else it.get("source","manual")))
                        yield it
            continue

        die(f"group '{gname}' is neither list nor dict (type={type(gv).__name__})")

def validate_entry(it: dict):
    # normalize minimal defaults for validation
    it.setdefault("source", "manual")
    it.setdefault("status", "active")
    # key/title/path must exist
    for k in ("key","title","path"):
        if k not in it:
            return f"missing field {k}"
    path=it["path"]
    if not isinstance(path,str) or not path.startswith("/"):
        return f"invalid path={path!r}"
    st=it["status"]
    if st not in ALLOWED_STATUS:
        return f"invalid status={st!r}"
    return None

if not os.path.exists(CATALOG_PATH):
    die(f"missing {CATALOG_PATH}")

data=json.load(open(CATALOG_PATH,"r",encoding="utf-8"))

entries=[]
mode=None

if isinstance(data.get("items"), list) and len(data["items"])>0:
    mode="items"
    for it in data["items"]:
        if not isinstance(it, dict):
            die(f"items has non-dict entry: {it!r}")
        entries.append(it)

elif isinstance(data.get("groups"), dict) and len(data["groups"])>0:
    mode="groups"
    for it in iter_entries_from_groups(data["groups"]):
        entries.append(it)

else:
    die("catalog has neither non-empty items[] nor non-empty groups{}")

bad=[]
for it in entries:
    err=validate_entry(it)
    if err:
        bad.append((it.get("key"), err, it.get("group"), it.get("source")))

if len(entries)==0:
    die(f"mode={mode} but entries=0 (no list found under groups routes/templates/items)")

if bad:
    print(f"mode={mode} entries={len(entries)} bad={len(bad)}")
    for row in bad[:50]:
        print("BAD:", row)
    sys.exit(1)

print(f"OK mode={mode} entries={len(entries)}")
