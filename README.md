# Monitoring zpráv o Romech ve světě

Automatický pipeline, který **dvakrát denně** projde zpravodajské zdroje
napříč jazyky, nechá Claude vytřídit relevantní zprávy o Romech, seřadí je
podle důležitosti, ke každé napíše české shrnutí a odkaz na zdroj, a pošle
hotový přehled e-mailem.

## Dva režimy

- **Režim B – feed pro ChatGPT (`gather.py`) — NASAZENÝ, AKTIVNÍ.** Aplikace
  jen NASBÍRÁ kandidáty a publikuje je jako veřejný JSON na
  `https://raw.githubusercontent.com/zdenekrysavy-lang/roma-monitor/main/feed/candidates.json`.
  Třídění a česká shrnutí dělá naplánovaný agent v ChatGPT (kryto předplatným,
  bez API poplatků). Prompt a návod: `chatgpt_task.md`.
- **Režim A – plný pipeline (`main.py`) — připravený, vypnutý.** Sběr →
  třídění/shrnutí přes Anthropic API → e-mail. Vyžaduje API klíč (drobný
  pay-as-you-go náklad); cron v `digest.yml` je zakomentovaný.

## Jak to funguje

```
Google News RSS (15 jazyků)     ┐
GDELT (globální, vícejazyčný)    ├─► dedup ─► seen.json ─► feed (B) / Claude+e-mail (A)
13 romských RSS feedů            │
10 webů bez feedu (GN site:)     ┘
```

- **Sběr** je zdarma a bez klíčů (Google News RSS, GDELT).
- **Třídění** vyřadí šum (město Řím, AS Roma, film *Roma*) a označí důležitost.
- **Shrnutí** píše Claude česky; jediná placená část (Anthropic API).

## Co potřebuješ

1. **API klíč Anthropic** – z <https://console.anthropic.com> → *API Keys*.
   Pozor: účtuje se zvlášť (pay-as-you-go), **není součástí Claude Pro**.
   Náklady jsou nízké – Claude dostává jen titulky a krátké úryvky.
   Výchozí model je `claude-sonnet-5`; pro další úsporu přepni
   `CLAUDE_MODEL` na `claude-haiku-4-5-20251001`.
2. **SMTP přístup** pro odesílání e-mailu (např. schránka na romea.cz).
3. **Účet na GitHubu** (kvůli bezplatnému plánovači GitHub Actions).

## Lokální test (na svém počítači)

```bash
pip install -r requirements.txt
cp .env.example .env        # vyplň hodnoty
set -a; source .env; set +a # načti proměnné (Linux/macOS)
python main.py
```

Bez vyplněného SMTP se přehled jen vypíše do konzole – ideální pro první test.

## Nasazení na GitHub Actions (běží samo 2× denně)

1. Vytvoř na GitHubu **privátní** repozitář a nahraj tento obsah.
2. V repu: *Settings → Secrets and variables → Actions → New repository secret*
   a přidej: `ANTHROPIC_API_KEY`, `EMAIL_TO`, `EMAIL_FROM`,
   `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`
   (volitelně `CLAUDE_MODEL`).
3. Časy běhu uprav v `.github/workflows/digest.yml` (cron je v UTC).
4. První běh spusť ručně: záložka *Actions → roma-news-digest → Run workflow*.

## Úpravy

- **Zdroje / jazyky:** `config.py` → `GOOGLE_NEWS_QUERIES`. Přidej řádek
  `('<dotaz>', '<jazyk>', '<země>')` — ale jen pro jazyky s jednoznačným
  termínem pro Romy (jinak dotaz zaplaví AS Roma / město Řím; takové jazyky
  nech na GDELT).
- **Přidání zdroje (web/feed):** `config.py`, sekce „TVOJE ZDROJE".
  Má-li web RSS feed → přidej `(URL_feedu, 'jazyk')` do `RSS_FEEDS`. Nemá
  feed → přidej `('doména', 'jazyk', 'země')` do `WATCH_SITES` (pipeline se
  zeptá Google News na tu doménu ve správném jazyce).
- **Pravidla třídění a shrnutí:** prompt `SYSTEM` v `analyze.py`.
- **Vzhled e-mailu:** `render.py`.
- **Frekvence:** cron v `digest.yml` (přidej/uber řádky `- cron:`).

## Struktura

| Soubor | Účel |
|---|---|
| `config.py`  | nastavení a zdroje |
| `fetch.py`   | sběr a deduplikace |
| `analyze.py` | třídění a shrnutí přes Claude |
| `render.py`  | sestavení HTML přehledu |
| `notify.py`  | odeslání e-mailu |
| `main.py`    | orchestrace |

## Poznámky

- Okna: Google News `LOOKBACK_HOURS=13`; GDELT a romské feedy/weby 72 h
  (GDELT má děravé čerstvé okno, malé weby publikují řídce). Opakování mezi
  běhy hlídá perzistentní `state/seen.json` (TTL 14 dní) – feed obsahuje
  jen NOVÉ zprávy, prázdný feed je normální stav.
- GDELT i Google News mají proměnlivou dostupnost; pipeline je odolný –
  když jeden zdroj selže, ostatní pokračují a stav se propíše do pole
  `sources` ve feedu (`gdelt_status`, `gdelt_note`, `google_news_status`).
