#!/usr/bin/env python3
"""Contract test: public dashboard security headers remain fail-closed."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
config = (ROOT / "netlify.toml").read_text(encoding="utf-8")

for required in [
    'X-Content-Type-Options = "nosniff"',
    'X-Frame-Options = "DENY"',
    'Strict-Transport-Security = "max-age=31536000; includeSubDomains"',
    "object-src 'none'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "https://iuvkbjmgxbkhrvuervrz.supabase.co",
]:
    assert required in config, required

assert "service_role" not in (ROOT / "hub.html").read_text(encoding="utf-8").lower()
print("security headers: 8/8 PASS")
