#!/usr/bin/env python3
"""Contract test: Content Engine claims use sessions and stable gateway keys."""
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

feedparser_stub = types.ModuleType("feedparser")
feedparser_stub.parse = lambda *args, **kwargs: None
anthropic_stub = types.ModuleType("anthropic")
anthropic_stub.Anthropic = object
sys.modules.setdefault("feedparser", feedparser_stub)
sys.modules.setdefault("anthropic", anthropic_stub)

import generate

html = (ROOT / "index.html").read_text(encoding="utf-8")
for required in ["ops_login_code_v2", "claim_pool_content", "pool_claim_snapshot", "stableClaimKey"]:
    assert required in html, required
for forbidden in ["s.from('aff_claims')", "s.rpc('aff_login_code'"]:
    assert forbidden not in html, forbidden

sample = {
    "source": {"url": "https://example.test/story", "headline": "Story", "date": "2026-08-30"},
    "solo": "luca",
}
key = generate.stable_claim_key(sample)
assert key == generate.stable_claim_key(sample)
assert len(key) == 28 and key.startswith("SRC-")
assert all(char in "0123456789ABCDEF" for char in key[4:])
print("secure claim gateway: 8/8 PASS")
