#!/usr/bin/env python3
"""Set conversation-cache flags in a Strata serve config, with a backup."""

import json
import os
import shutil
import sys
import time
from pathlib import Path

path = Path(sys.argv[1])
budget = int(sys.argv[2])
slots = int(sys.argv[3])
min_free = int(sys.argv[4])
min_tokens = int(sys.argv[5])

doc = json.loads(path.read_text(encoding="utf-8"))
managed = {
    "--conversation-cache-mib",
    "--conversation-cache-slots",
    "--conversation-cache-min-free-mib",
    "--conversation-cache-min-tokens",
}
args = []
index = 0
while index < len(doc["args"]):
    flag = doc["args"][index]
    if flag in managed:
        index += 2
        continue
    args.append(flag)
    index += 1
args.extend([
    "--conversation-cache-mib", str(budget),
    "--conversation-cache-slots", str(slots),
    "--conversation-cache-min-free-mib", str(min_free),
    "--conversation-cache-min-tokens", str(min_tokens),
])
doc["args"] = args

backup = path.with_name(path.name + ".bak-convcache-" + time.strftime("%Y%m%d-%H%M%S"))
shutil.copy2(path, backup)
tmp = path.with_name(path.name + ".tmp")
tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, path)
print(json.dumps({
    "backup": str(backup),
    "budget_mib": budget,
    "slots": slots,
    "min_free_mib": min_free,
    "min_tokens": min_tokens,
}, ensure_ascii=False))
