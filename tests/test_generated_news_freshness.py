#!/usr/bin/env python3
"""Fail the scheduled publish when the generated news pool is stale or collapsed."""
from datetime import date, timedelta
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
html = (ROOT / "index.html").read_text(encoding="utf-8")
match = re.search(
    r'<script id="data" type="application/json">\s*(.*?)\s*</script>',
    html,
    re.S,
)
assert match, "dashboard data payload missing"
payload = json.loads(match.group(1))
items = payload.get("items") or []
assert items, "news pool empty"

cutoff = date.today() - timedelta(days=5)
fresh = []
for item in items:
    source = item.get("source") or {}
    try:
        source_day = date.fromisoformat(str(source.get("date") or ""))
    except ValueError:
        continue
    if source_day >= cutoff:
        fresh.append(item)

assert len(fresh) >= 8, f"fresh news pool too small: {len(fresh)}"
assert len({item.get("categoria") for item in fresh if item.get("categoria")}) >= 4, "fresh categories collapsed"
assert len({(item.get("source") or {}).get("outlet") for item in fresh}) >= 4, "fresh outlets collapsed"
urls = [(item.get("source") or {}).get("url") for item in fresh]
urls = [url for url in urls if url]
assert len(urls) == len(set(urls)), "duplicate fresh source URLs"
print(f"generated news freshness: {len(fresh)} fresh items, PASS")
