# Monitoring zpráv o Romech ve světě

Automatický pipeline, který **dvakrát denně** projde zpravodajské zdroje
napříč jazyky, nechá Claude vytřídit relevantní zprávy o Romech, seřadí je
podle důležitosti, ke každé napíše české shrnutí a odkaz na zdroj, a pošle
hotový přehled e-mailem.

## Dva režimy

- **Režim A – plný pipeline (`main.py`).** Sběr → třídění/shrnutí přes Anthropic
  API → e-mail. Vše řídí kód, výstup je konzistentní. Vyžaduje API klíč (drobný
  pay-as-you-go náklad).
- **Režim B – feed pro ChatGPT (`gather.py`).** Aplikace jen NASBÍRÁ kandidáty
  a publikuje je jako veřejný JSON. Třídění a česká shrnutí dělá tvůj naplánovaný
  agent v ChatGPT (kryto předplatným, bez API poplatků). Návod: `chatgpt_task.md`.

Níže popsaný tok platí pro režim A; režim B je jeho první polovina bez AI kroku.

## Jak to funguje

```
Google News RSS (11 jazyků)  ┐
GDELT (globální, vícejazyčný) ├─►  dedup  ─►  Claude (třídí + shrnuje)  ─►  HTML e-mail
vlastní RSS feedy (volitelné) ┘
```

- **Sběr** je zdarma a bez klíčů (Google News RSS, GDELT).
- **Třídění** vyřadí šum (město Řím, AS Roma, film *Roma*) a označí důležitost.
- **Shrnutí** píše Claude česky; jediná placená část (Anthropic API).

## Co potřebuješ

1. **API klíč Anthropic** – z <https://console.anthropic.com> → *API Keys*.
   Pozor: účtuje se zvlášť (pay-as-you-go), **není součástí Claude Pro**.
   Náklady jsou nízké – Claude dostává jen titulky a krátké úryvky.
   Pro další úsporu přepni `CLAUDE_MODEL` na `claude-haiku-4-5-20251001`.
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
  `('<dotaz>', '<jazyk>', '<země>')` pro další jazyk.
- **Přidání zdroje (web/feed):** `config.py`, sekce „TVOJE ZDROJE".
  Má-li web RSS feed → přidej jeho URL do `RSS_FEEDS`. Nemá feed (nebo nevíš)
  → přidej jen doménu do `WATCH_SITES` (pipeline si sama udělá dotaz přes
  Google News na tu doménu). Předvyplněno: `rroma.org` (feed) a `errc.org` (web).
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

- Okno `LOOKBACK_HOURS=13` mírně přesahuje 12h kadenci, aby nevypadly zprávy
  na hraně mezi běhy. Drobné překryvy řeší dedup; pro tvrdou ochranu proti
  opakování lze doplnit perzistentní seznam již viděných URL.
- GDELT i Google News mají proměnlivou dostupnost; pipeline je odolný –
  když jeden zdroj selže, ostatní pokračují.
