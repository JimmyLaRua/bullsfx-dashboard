# BullsFX Content Engine

Motore che aggiorna la dashboard dei talent **da solo, ogni ora, 24/7** — senza bisogno
del tuo computer acceso o dell'app Claude aperta.

Gira su **GitHub Actions** (gratis) e pubblica su **GitHub Pages** (gratis). Ogni ora:
prende le notizie fresche, scrive i contenuti pronti da girare con l'API di Claude,
aggiorna `index.html` e lo ripubblica online.

La dashboard resta identica per i talent (login col codice + spunte "preso/libero" via
Supabase): cambia solo il "motore" dietro le quinte.

---

## Cosa faccio io e cosa devi fare tu

Tutto il codice è già pronto in questa cartella. A te restano **4 passaggi**, perché
richiedono il TUO account (io non posso creare account o inserire le tue chiavi):

1. Creare il repository su GitHub e caricarci questi file.
2. Ottenere una **API key di Claude**.
3. Incollarla come "secret" nel repository.
4. Accendere GitHub Pages e lanciare il motore una volta.

Tempo stimato: ~15 minuti. Segui la guida qui sotto.

---

## Passo 1 — Crea il repository e carica i file

1. Vai su **https://github.com** e accedi (se non hai un account, crealo: è gratis).
2. In alto a destra: **+ → New repository**.
3. Nome: `bullsfx-dashboard`. Lascialo **Public**. Clicca **Create repository**.
4. Nella pagina del repo vuoto: **uploading an existing file**.
5. Trascina questi file dalla cartella `bullsfx-engine`:
   `index.html`, `generate.py`, `requirements.txt`, `.gitignore`, `README.md`.
   Poi in fondo clicca **Commit changes**.
6. Il file del "programma orario" sta in una sottocartella, quindi va creato a mano:
   - **Add file → Create new file**.
   - Nel nome scrivi ESATTAMENTE: `.github/workflows/refresh.yml`
     (mentre scrivi le `/`, GitHub crea le cartelle da solo).
   - Apri il file `refresh.yml` di questa cartella, copia tutto il contenuto e incollalo.
   - **Commit changes**.

## Passo 2 — Ottieni la API key di Claude

1. Vai su **https://console.anthropic.com** e accedi.
2. Sezione **API Keys → Create Key**. Copia la chiave (inizia con `sk-ant-...`).
3. Serve avere del credito attivo sull'account API (sezione Billing). Vedi "Costi" sotto.

## Passo 3 — Incolla la chiave come secret

1. Nel repository: **Settings → Secrets and variables → Actions**.
2. **New repository secret**.
3. Name: `ANTHROPIC_API_KEY`  ·  Secret: incolla la chiave `sk-ant-...`.
4. **Add secret**. (La chiave resta nascosta e cifrata, non finisce mai nel codice.)

## Passo 4 — Accendi il sito e lancia il motore

1. **Settings → Pages**. In *Source* scegli **Deploy from a branch**,
   branch **main**, cartella **/ (root)**, **Save**.
   Dopo un minuto compare l'indirizzo del sito (tipo
   `https://TUONOME.github.io/bullsfx-dashboard/`). Quello è il nuovo link per i talent.
2. Vai sul tab **Actions**, accetta di abilitare i workflow se richiesto.
3. Clicca **BullsFX content refresh → Run workflow → Run workflow**.
4. Dopo 1-2 minuti il pallino diventa verde: i nuovi contenuti sono online.
   Da qui in poi parte **da solo ogni ora**.

---

## Costi (importante)

Ogni contenuto generato è una chiamata all'API di Claude. Con l'impostazione di default
(`ITEMS_PER_RUN=5`, ogni ora) sono circa **120 contenuti al giorno**.

- Modello di default: `claude-sonnet-5` (qualità migliore).
- Per spendere molto meno: nel file `refresh.yml` cambia
  `ANTHROPIC_MODEL: claude-sonnet-5` in `ANTHROPIC_MODEL: claude-haiku-4-5-20251001`.
- Per generare di più/di meno: cambia `ITEMS_PER_RUN` (es. `3` o `10`).
- Per cambiare frequenza: modifica la riga `cron: "0 * * * *"` (ogni ora).
  Es. ogni 2 ore = `"0 */2 * * *"`.

GitHub Actions e GitHub Pages su repository **pubblico** sono gratuiti e senza limiti di
minuti: l'unico costo reale è l'API di Claude.

## Come funziona (in breve)

- `generate.py` — legge le notizie (Google News RSS, gratis) su mercati globali, politica
  ed economia italiana, geopolitica, cripto, dolori sociali italiani, più fonti spagnole
  **visibili solo ad Alberto**. Deduplica, sceglie un mix, e per ognuna chiede a Claude un
  contenuto pronto (hook, script, caption, overlay, regia) in stile Mik Cosentino.
- Regole di conformità già dentro al prompt: broker mai nominato ("un partner
  regolamentato"), niente cifre di profitto/garanzie, fonte sempre citata a schermo,
  **nessun disclaimer sul trading** nelle caption.
- Elimina in automatico i contenuti più vecchi di 7 giorni e rinumera tutto.

## Note

- La dashboard usa Supabase per login e spunte: è già configurato dentro `index.html`,
  non devi toccare nulla.
- Il vecchio sito Netlify può restare o essere spento: il link "ufficiale" diventa quello
  di GitHub Pages. Volendo, in futuro si può collegare un dominio tuo.
