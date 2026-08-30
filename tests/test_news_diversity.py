#!/usr/bin/env python3
"""Contract test: the news picker must stay varied and audience-safe."""
from datetime import date
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# The selection contract is pure Python; CI does not need network SDKs here.
feedparser_stub = types.ModuleType("feedparser")
feedparser_stub.parse = lambda *args, **kwargs: None
anthropic_stub = types.ModuleType("anthropic")
anthropic_stub.Anthropic = object
sys.modules.setdefault("feedparser", feedparser_stub)
sys.modules.setdefault("anthropic", anthropic_stub)

import generate

source = pathlib.Path(generate.__file__).read_text(encoding="utf-8")
assert '"categoria": ch["cat"]' in source
assert '"area": ch["area"]' in source


def candidate(cat, outlet, headline, tier="authoritative", solo=None, lang="it"):
    return {
        "outlet": outlet,
        "headline": headline,
        "url": "https://example.test/" + headline.replace(" ", "-"),
        "pub": date.today(),
        "source_tier": tier,
        "ch": {
            "cat": cat,
            "area": "test",
            "lang": lang,
            "solo": solo,
            "q": headline,
        },
    }


rows = [
    candidate("Cronaca", "ANSA", "Una storia italiana che cambia il quartiere"),
    candidate("Scienza", "Nature", "Nuova scoperta sui microbi del suolo"),
    candidate("Tecnologia", "ANSA Tecnologia", "Intelligenza artificiale e privacy nelle scuole"),
    candidate("Ambiente", "NASA JPL", "Satellite osserva un fenomeno climatico raro"),
    candidate("Cultura", "ANSA Cultura", "Il film indipendente diventato fenomeno sociale"),
    candidate("Curiosita", "ANSA Lifestyle", "La scoperta archeologica che sorprende gli studiosi"),
    candidate("Politica", "Reuters", "Nuova decisione europea sulla vita quotidiana", "discovery"),
    candidate("Macro", "Sole 24 Ore", "Inflazione italiana e prezzi di questa settimana", "discovery"),
    # Near duplicate: must not enter together with the Nature item.
    candidate("Scienza", "Altro", "Nuova scoperta sui microbi del suolo oggi", "discovery"),
    # Private language pools.
    candidate("Scienza", "El Pais", "Descubrimiento cientifico sorprende a los investigadores", "discovery", "alberto", "es"),
    candidate("Tecnologia", "Le Monde", "Une innovation technologique change le quotidien", "discovery", "nabil", "fr"),
]

picked = generate.pick_spread(rows, 8)
assert len(picked) == 8, len(picked)
assert sum(not r["ch"]["solo"] for r in picked) == 6
assert sum(r["ch"]["solo"] == "alberto" for r in picked) == 1
assert sum(r["ch"]["solo"] == "nabil" for r in picked) == 1
shared = [r for r in picked if not r["ch"]["solo"]]
assert sum(r["source_tier"] == "authoritative" for r in shared) >= 3
assert len({r["ch"]["cat"] for r in shared}) == len(shared)
assert max(sum(r["ch"]["cat"] == cat for r in picked) for cat in generate.CATEGORY_ORDER) <= 2
assert len({r["outlet"].casefold() for r in picked}) == len(picked)
assert not any(
    generate._too_similar(a, b)
    for i, a in enumerate(picked)
    for b in picked[i + 1:]
)
print("news diversity: 8/8 PASS")
