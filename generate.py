#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BullsFX Content Engine
----------------------
Ogni run:
  1. Prende notizie fresche (<=5 giorni) da Google News RSS su piu' temi/lingue.
  2. Deduplica per URL rispetto agli item gia' presenti in index.html.
  3. Sceglie ~10-12 candidati (spread tra le categorie).
  4. Per ognuno chiede all'API di Claude un contenuto pronto stile Mik Cosentino
     (JSON) nel rispetto delle regole di compliance.
  5. Append + prune (>7 giorni) + rinumera + riscrive index.html.

Girato da GitHub Actions ogni ora, senza bisogno del computer acceso.
Richiede la variabile d'ambiente ANTHROPIC_API_KEY.
"""

import os, re, sys, json, html, time, socket, urllib.parse
from datetime import datetime, date, timezone, timedelta

import feedparser
from anthropic import Anthropic

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
HERE       = os.path.dirname(os.path.abspath(__file__))
HTML_PATH  = os.path.join(HERE, "index.html")
MODEL      = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
FRESH_DAYS = 5          # notizie usate solo se pubblicate negli ultimi N giorni
KEEP_DAYS  = 7          # item piu' vecchi di N giorni vengono eliminati
TARGET     = int(os.environ.get("ITEMS_PER_RUN", "12"))   # item da generare per run
PER_QUERY  = 8          # candidati letti da ogni query
# NB: NON impostare socket.setdefaulttimeout() a livello globale: rompe il
# client httpx dell'SDK Anthropic (handshake SSL) -> "Connection error" su ogni
# chiamata API. Il timeout si applica SOLO durante la lettura dei feed RSS.
FEED_TIMEOUT = 15

# Ogni "canale" = una ricerca Google News + i metadati dell'item.
# solo="alberto" + lang="es"  => contenuto visibile SOLO ad Alberto (spagnolo).
CHANNELS = [
    # ---- MACRO USA / globale ------------------------------------------------
    dict(cat="Macro",    area="USA / Mercati globali", lang="it", solo=None,
         q="wall street s&p 500 nasdaq when:5d", hl="en", gl="US", ceid="US:en"),
    dict(cat="Macro",    area="USA / Fed",             lang="it", solo=None,
         q="federal reserve tassi inflazione when:5d", hl="en", gl="US", ceid="US:en"),
    dict(cat="Macro",    area="USA / Big Tech",        lang="it", solo=None,
         q="nvidia apple microsoft tesla azioni when:5d", hl="en", gl="US", ceid="US:en"),
    # ---- MACRO Europa / Italia ---------------------------------------------
    dict(cat="Macro",    area="Europa / Italia",       lang="it", solo=None,
         q="borsa milano ftse mib spread btp when:5d", hl="it", gl="IT", ceid="IT:it"),
    dict(cat="Macro",    area="Europa / BCE",          lang="it", solo=None,
         q="bce tassi euro inflazione when:5d",        hl="it", gl="IT", ceid="IT:it"),
    dict(cat="Macro",    area="Europa",                lang="it", solo=None,
         q="dax cac borse europee francoforte parigi when:5d", hl="it", gl="IT", ceid="IT:it"),
    # ---- POLITICA ----------------------------------------------------------
    dict(cat="Politica", area="Italia",                lang="it", solo=None,
         q="governo manovra economia tasse italia when:5d", hl="it", gl="IT", ceid="IT:it"),
    dict(cat="Politica", area="USA",                   lang="it", solo=None,
         q="usa dazi tariffe economia when:5d",        hl="it", gl="IT", ceid="IT:it"),
    dict(cat="Politica", area="Mondo",                 lang="it", solo=None,
         q="elezioni economia mercati politica when:5d", hl="it", gl="IT", ceid="IT:it"),
    # ---- GEO / energia -----------------------------------------------------
    dict(cat="Geo",      area="Medio Oriente",         lang="it", solo=None,
         q="medio oriente petrolio tensioni when:5d",  hl="it", gl="IT", ceid="IT:it"),
    dict(cat="Geo",      area="Energia",               lang="it", solo=None,
         q="petrolio gas prezzo energia when:5d",      hl="it", gl="IT", ceid="IT:it"),
    dict(cat="Geo",      area="Cina / Asia",           lang="it", solo=None,
         q="cina economia esportazioni yuan when:5d",  hl="it", gl="IT", ceid="IT:it"),
    # ---- TRADING / cripto / commodities / forex ----------------------------
    dict(cat="Trading",  area="Cripto",                lang="it", solo=None,
         q="bitcoin prezzo when:5d",                   hl="it", gl="IT", ceid="IT:it"),
    dict(cat="Trading",  area="Cripto",                lang="it", solo=None,
         q="ethereum altcoin cripto when:5d",          hl="it", gl="IT", ceid="IT:it"),
    dict(cat="Trading",  area="Cripto",                lang="it", solo=None,
         q="crypto etf bitcoin regolamentazione when:5d", hl="it", gl="IT", ceid="IT:it"),
    dict(cat="Trading",  area="Materie prime",         lang="it", solo=None,
         q="oro argento prezzo record when:5d",        hl="it", gl="IT", ceid="IT:it"),
    dict(cat="Trading",  area="Valute",                lang="it", solo=None,
         q="euro dollaro cambio forex when:5d",        hl="it", gl="IT", ceid="IT:it"),
    # ---- RANDOM / finanza personale ---------------------------------------
    dict(cat="Random",   area="Italia",                lang="it", solo=None,
         q="caro vita bollette stipendi risparmio when:5d", hl="it", gl="IT", ceid="IT:it"),
    dict(cat="Random",   area="Italia",                lang="it", solo=None,
         q="mutui tassi casa prestiti when:5d",        hl="it", gl="IT", ceid="IT:it"),
    dict(cat="Random",   area="Italia",                lang="it", solo=None,
         q="pensioni inps risparmio investimenti when:5d", hl="it", gl="IT", ceid="IT:it"),
    dict(cat="Random",   area="Lavoro",                lang="it", solo=None,
         q="lavoro stipendi occupazione italia when:5d", hl="it", gl="IT", ceid="IT:it"),
    # ---- SPAGNOLO (visibile solo ad Alberto) -------------------------------
    dict(cat="Macro",    area="Espana",                lang="es", solo="alberto",
         q="economia espana bolsa ibex when:5d",       hl="es", gl="ES", ceid="ES:es"),
    dict(cat="Macro",    area="Espana / BCE",          lang="es", solo="alberto",
         q="bce tipos inflacion euro when:5d",         hl="es", gl="ES", ceid="ES:es"),
    dict(cat="Trading",  area="Cripto (ES)",           lang="es", solo="alberto",
         q="bitcoin criptomonedas precio when:5d",     hl="es", gl="ES", ceid="ES:es"),
    dict(cat="Random",   area="Espana",                lang="es", solo="alberto",
         q="hipotecas ahorro precios luz espana when:5d", hl="es", gl="ES", ceid="ES:es"),
]

SYSTEM_PROMPT = """Sei il SOCIAL MEDIA MANAGER del pool "BullsFX": una squadra di talent che pubblica video verticali (TikTok/Instagram/YouTube Shorts) partendo dalle notizie del giorno.

Ricevi UNA notizia reale (outlet, titolo, data, link, categoria, area) e produci UN contenuto PRONTO DA GIRARE, in stile "Mik Cosentino" (newsjacking aggressivo, hook fortissimo nei primi 1-2 secondi, ritmo alto, forte retention).

REGOLE DI CONFORMITA' (assolute):
- NON nominare MAI un broker. Usa sempre l'espressione "un partner regolamentato". Mai scrivere nomi di broker.
- ZERO cifre di profitto, ZERO percentuali di vincita, ZERO garanzie o promesse di guadagno.
- Cita SEMPRE la fonte a schermo (outlet + testata + data): screenshot o overlay, non serve per forza green screen.
- NON inserire alcun disclaimer o avviso di rischio sul trading nella caption (niente warning, niente "non e' consulenza").

DIREZIONE CREATIVA:
- Hook che ferma il pollice entro 1-2 secondi. Vari il formato tra i contenuti (Screen-recording, Talking head, B-roll + testo, POV / personale). Green screen OPZIONALE.
- La nota di regia deve dare un'idea di ripresa concreta e virale (inquadratura, testo a schermo, montaggio) pensata per l'algoritmo di TikTok/Instagram.

SCALA DELLE CTA (regola fondamentale: NON ogni contenuto vende):
Scegli il "cta_type" in base al TIPO di contenuto, non mettere sempre la stessa CTA:
- "none"  -> contenuti personali/aneddotici/lifestyle/storytelling emotivo. NESSUNA CTA: lo script chiude con una frase finale che lascia respirare il contenuto. Il campo "cta" resta VUOTO e lo script NON contiene la riga "CTA:".
- "engage"-> newsjacking / opinione / reaction a caldo. La CTA e' UNA domanda secca che spinge i commenti (es. "E tu come la leggi? 👇"). Resta in-app.
- "save"  -> contenuti educativi/di valore ("capire il denaro", spiegazioni). CTA di retention: "salva questo", "salva e rileggilo". Resta in-app.
- "follow"-> contenuti serializzabili ("parte 1 di..."). CTA: "segui per la parte 2". Resta in-app.
- "link"  -> SOLO circa 1 contenuto su 5, i piu' operativi/di metodo: CTA verso il canale/approfondimento ("nel canale", "link in bio"). Non abusarne: se e' ovunque, non converte.
Regole: mai spingente; vari SEMPRE il testo (non ripetere "nel canale" su ogni link); privilegia CTA native (salva/commenta/condividi/segui) che non fanno uscire dall'app.

Rispondi ESCLUSIVAMENTE con un oggetto JSON valido (nessun testo prima o dopo), con ESATTAMENTE queste chiavi:
{
 "categoria": "<Macro|Geo|Politica|Trading|Random>",
 "area": "<area geografica>",
 "format": "<Screen-recording|Talking head|B-roll + testo|POV / personale>",
 "tipo": "<breve tipo di video>",
 "durata": "<es. 20-35s>",
 "titolo": "<titolo interno breve della scheda>",
 "overlay": "<testo grande da mettere a schermo>",
 "script": "HOOK: ...\\nBODY: ...\\nCTA: ...   (ometti del tutto la riga CTA se cta_type=none)",
 "caption": "<caption pronta con hashtag, SENZA disclaimer>",
 "cta_type": "<none|engage|save|follow|link>",
 "cta": "<testo della CTA coerente col cta_type; VUOTO se cta_type=none>",
 "fornire": "<cosa deve preparare il talent per girarlo>",
 "regia": "<nota di regia concreta e virale>"
}
Scrivi in ITALIANO, salvo quando ti indico lingua=es: in quel caso scrivi titolo/overlay/script/caption/cta/fornire/regia in SPAGNOLO."""


# ----------------------------------------------------------------------------
# NEWS
# ----------------------------------------------------------------------------
def gnews_url(ch):
    base = "https://news.google.com/rss/search?q="
    return (base + urllib.parse.quote(ch["q"])
            + f"&hl={ch['hl']}&gl={ch['gl']}&ceid={urllib.parse.quote(ch['ceid'])}")

def clean(t):
    return html.unescape(re.sub(r"\s+", " ", t or "").strip())

def parse_entry(e, ch):
    title = clean(getattr(e, "title", ""))
    outlet = ""
    src = getattr(e, "source", None)
    if src and getattr(src, "title", None):
        outlet = clean(src.title)
    # Google News mette " - Outlet" in coda al titolo
    m = re.search(r"\s-\s([^-]+)$", title)
    if m and not outlet:
        outlet = clean(m.group(1))
    headline = re.sub(r"\s-\s[^-]+$", "", title).strip() if m else title
    # data
    d = None
    if getattr(e, "published_parsed", None):
        d = datetime(*e.published_parsed[:6], tzinfo=timezone.utc).date()
    return dict(outlet=outlet or "Google News", headline=headline,
                url=getattr(e, "link", ""), pub=d, ch=ch)

def collect_candidates(existing_urls):
    today = datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=FRESH_DAYS)
    cands = []
    # rotazione: ogni run parte da un canale diverso, cosi' i temi in cima
    # cambiano ora dopo ora e non si pesca sempre dallo stesso feed.
    off = datetime.now(timezone.utc).hour % len(CHANNELS)
    rotated = CHANNELS[off:] + CHANNELS[:off]
    socket.setdefaulttimeout(FEED_TIMEOUT)   # timeout SOLO per i feed RSS
    try:
        for ch in rotated:
            try:
                feed = feedparser.parse(gnews_url(ch))
            except Exception as ex:
                print(f"[warn] feed error {ch['q'][:30]}: {ex}", file=sys.stderr)
                continue
            picked = 0
            for e in feed.entries:
                c = parse_entry(e, ch)
                if not c["url"] or not c["headline"]:
                    continue
                if c["pub"] and c["pub"] < cutoff:
                    continue
                if c["url"] in existing_urls:
                    continue
                cands.append(c)
                existing_urls.add(c["url"])
                picked += 1
                if picked >= PER_QUERY:
                    break
    finally:
        socket.setdefaulttimeout(None)
    return cands

def pick_spread(cands, n):
    """Sceglie n candidati alternando i canali per varieta'."""
    buckets = {}
    for c in cands:
        buckets.setdefault(c["ch"]["q"], []).append(c)
    out, keys = [], list(buckets.keys())
    i = 0
    while len(out) < n and any(buckets.values()):
        k = keys[i % len(keys)]
        if buckets[k]:
            out.append(buckets[k].pop(0))
        i += 1
        if i > n * 20:
            break
    return out


# ----------------------------------------------------------------------------
# CLAUDE
# ----------------------------------------------------------------------------
def generate_item(client, c):
    ch = c["ch"]
    lang = ch["lang"]
    user = (
        f"NOTIZIA:\n"
        f"- outlet: {c['outlet']}\n"
        f"- titolo: {c['headline']}\n"
        f"- data: {c['pub'].isoformat() if c['pub'] else 'oggi'}\n"
        f"- link: {c['url']}\n"
        f"- categoria: {ch['cat']}\n"
        f"- area: {ch['area']}\n"
        f"- lingua: {lang}\n"
        f"Genera l'item JSON come da istruzioni."
    )
    msg = client.messages.create(
        model=MODEL,
        max_tokens=1400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user}],
    )
    txt = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    txt = txt.strip()
    # estrai il primo blocco JSON
    a, b = txt.find("{"), txt.rfind("}")
    if a < 0 or b < 0:
        raise ValueError("no JSON in response")
    obj = json.loads(txt[a:b + 1])
    # blindatura compliance lato codice
    cap = obj.get("caption", "")
    cap = re.split(r"\u26a0", cap)[0].rstrip()          # via eventuale warning
    obj["caption"] = cap
    # normalizza la CTA in base al cta_type
    cta_type = (obj.get("cta_type") or "").strip().lower()
    if cta_type not in ("none", "engage", "save", "follow", "link"):
        cta_type = "engage"
    scr = obj.get("script", "")
    if cta_type == "none":
        obj["cta"] = ""
        # rimuovi l'eventuale riga "CTA: ..." dallo script
        scr = "\n".join(l for l in scr.split("\n")
                        if not l.strip().lower().startswith("cta:")).rstrip()
        obj["script"] = scr
    item = {
        "id": 0,
        "date": (c["pub"].isoformat() if c["pub"] else datetime.now(timezone.utc).date().isoformat()),
        "categoria": obj.get("categoria", ch["cat"]),
        "area": obj.get("area", ch["area"]),
        "format": obj.get("format", "Talking head"),
        "tipo": obj.get("tipo", "News reaction"),
        "durata": obj.get("durata", "20-35s"),
        "titolo": obj.get("titolo", c["headline"][:80]),
        "overlay": obj.get("overlay", ""),
        "script": obj.get("script", ""),
        "caption": obj["caption"],
        "cta_type": cta_type,
        "cta": obj.get("cta", ""),
        "fornire": obj.get("fornire", ""),
        "source": {"outlet": c["outlet"], "headline": c["headline"],
                   "date": (c["pub"].isoformat() if c["pub"] else datetime.now(timezone.utc).date().isoformat()),
                   "url": c["url"]},
        "regia": obj.get("regia", ""),
    }
    if ch["solo"]:
        item["solo"] = ch["solo"]
        item["lang"] = lang
    return item


# ----------------------------------------------------------------------------
# HTML I/O
# ----------------------------------------------------------------------------
DATA_RE = re.compile(r'(<script id="data" type="application/json">)(.*?)(</script>)', re.S)

def read_html():
    with open(HTML_PATH, encoding="utf-8") as f:
        h = f.read()
    m = DATA_RE.search(h)
    if not m:
        raise SystemExit("blocco dati non trovato in index.html")
    data = json.loads(m.group(2))
    return h, m, data

def write_html(h, m, data):
    new = m.group(1) + "\n" + json.dumps(data, ensure_ascii=False, indent=2) + "\n" + m.group(3)
    h2 = h[:m.start()] + new + h[m.end():]
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(h2)


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def main():
    # Il secret puo' essere stato incollato con spazi/newline finali: se il valore
    # della chiave contiene '\n' diventa un header HTTP illegale e OGNI chiamata
    # fallisce con "Connection error" (LocalProtocolError). Ripuliamo qui una volta
    # e riscriviamo l'env cosi' anche l'SDK (che lo legge da solo) usa la versione pulita.
    api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY mancante")
    os.environ["ANTHROPIC_API_KEY"] = api_key

    h, m, data = read_html()
    items = data.get("items", [])
    existing_urls = {i.get("source", {}).get("url", "") for i in items}

    cands = collect_candidates(set(existing_urls))
    print(f"[info] candidati freschi: {len(cands)}")
    chosen = pick_spread(cands, TARGET)
    print(f"[info] selezionati: {len(chosen)}")

    # --- diagnostica connettivita' verso l'API (aiuta a capire i "Connection error") ---
    try:
        ip = socket.gethostbyname("api.anthropic.com")
        print(f"[net] DNS api.anthropic.com -> {ip}")
    except Exception as ex:
        print(f"[net] DNS FAIL: {ex!r}", file=sys.stderr)
    try:
        import httpx as _httpx
        r = _httpx.get("https://api.anthropic.com/v1/models", timeout=30,
                       headers={"x-api-key": api_key,
                                "anthropic-version": "2023-06-01"})
        print(f"[net] GET /v1/models -> HTTP {r.status_code}")
    except Exception as ex:
        print(f"[net] handshake FAIL: {type(ex).__name__}: {ex!r} cause={getattr(ex, '__cause__', None)!r}",
              file=sys.stderr)

    # client con retry automatici e timeout generoso (i runner a volte hanno la
    # prima connessione lenta: senza retry basta un singolo intoppo per perdere l'item)
    client = Anthropic(api_key=api_key, max_retries=5, timeout=60.0)
    added = 0
    for c in chosen:
        try:
            item = generate_item(client, c)
            items.append(item)
            added += 1
            print(f"[ok] + {item['categoria']:8} {item['titolo'][:55]}")
        except Exception as ex:
            print(f"[skip] {c['headline'][:45]}: {type(ex).__name__}: {ex!r} "
                  f"cause={getattr(ex, '__cause__', None)!r}", file=sys.stderr)
        time.sleep(1)

    # prune > KEEP_DAYS
    today = datetime.now(timezone.utc).date()
    keep_cut = today - timedelta(days=KEEP_DAYS)
    before = len(items)
    kept = []
    for i in items:
        try:
            d = date.fromisoformat(i.get("date", ""))
        except Exception:
            d = today
        if d >= keep_cut:
            kept.append(i)
    pruned = before - len(kept)

    # ordina per data desc e rinumera
    kept.sort(key=lambda i: i.get("date", ""), reverse=True)
    for idx, i in enumerate(kept, 1):
        i["id"] = idx
    data["items"] = kept

    # safety: nessun warning residuo nelle caption
    for i in kept:
        i["caption"] = re.split(r"\u26a0", i.get("caption", ""))[0].rstrip()

    write_html(h, m, data)
    oggi = sum(1 for i in kept if i.get("date") == today.isoformat())
    print(f"[done] added={added} pruned={pruned} total={len(kept)} oggi={oggi}")

if __name__ == "__main__":
    main()
