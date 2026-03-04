import json,sys

p="app/modules_catalog.json"

data=json.load(open(p,"r",encoding="utf-8"))

allowed={"active","stub","hidden"}

for it in data.get("items",[]):

    for k in ["group","key","title","path","source","status"]:
        if k not in it:
            print("missing field:",k,it)
            sys.exit(1)

    if not it["path"].startswith("/"):
        print("invalid path:",it)
        sys.exit(1)

    if it["status"] not in allowed:
        print("invalid status:",it)
        sys.exit(1)

print("OK")
