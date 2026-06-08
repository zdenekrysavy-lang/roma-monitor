# CLAUDE.md — kontext projektu pro Claude Code

## Co to je
Automatický pipeline, který **2× denně** projde zpravodajské zdroje napříč
jazyky, nechá Claude (přes Anthropic API) vytřídit relevantní zprávy o Romech
ve světě, seřadí je podle důležitosti, ke každé napíše **české** shrnutí
a odkaz na zdroj, a pošle hotový přehled e-mailem. Plánování řeší GitHub Actions.

## Dva režimy
- **A (plný):** `main.py` → sběr + Claude třídí/shrnuje + e-mail. Vyžaduje API klíč.
- **B (feed pro ChatGPT):** `gather.py` → jen sběr + publikace `feed/candidates.json`
  (workflow `gather.yml`). AI/třídění dělá agent v ChatGPT (viz `chatgpt_task.md`).
  Tenhle režim nepotřebuje žádný API klíč.

## Architektura
```
Google News RSS (více jazyků) ┐
GDELT (globální, bez klíče)    ├─► dedup ─► Claude (třídí + shrnuje) ─► HTML e-mail (SMTP)
RSS_FEEDS + WATCH_SITES        ┘
```

## Soubory
- `config.py`  — nastavení + zdroje (sekce „TVOJE ZDROJE": `RSS_FEEDS`, `WATCH_SITES`)
- `fetch.py`   — sběr (Google News, GDELT, feedy, weby bez feedu) + dedup
- `analyze.py` — třídění/shrnutí přes Claude; prompt `SYSTEM` je srdce kvality
- `render.py`  — HTML přehled
- `notify.py`  — odeslání e-mailu (SMTP)
- `main.py`    — orchestrace (`python main.py`)
- `.github/workflows/digest.yml` — cron 2× denně + ruční spuštění

## Jak spustit / testovat
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...     # nutné pro analyze.py
python main.py                   # bez SMTP se přehled vypíše do konzole
```
Bez vyplněného `EMAIL_TO`/`SMTP_HOST` se e-mail neodesílá, jen se vytiskne náhled —
ideální pro vývoj.

## Konvence a pravidla (DŮLEŽITÉ)
- **Shrnutí vždy česky.** Výstup míří pro českou redakci (ROMEA.cz).
- **Žádné tajné údaje v kódu.** API klíč, SMTP heslo jen z proměnných prostředí.
  Necommitovat `.env`.
- **Odolnost zdrojů:** když jeden feed/zdroj selže, zaloguj a pokračuj — běh
  nesmí spadnout kvůli jednomu mrtvému feedu.
- **Relevance:** filtr musí vyřazovat šum: město Řím (Roma), AS Roma, film *Roma*,
  příjmení typu „Roma…", fotbalisté jménem Romulo apod.
- Modely: výchozí `claude-sonnet-4-6`; levnější varianta `claude-haiku-4-5-20251001`
  (přes `CLAUDE_MODEL`).

## TODO / kam to posunout
1. **Ověřit živý běh** — pustit `python main.py`, zkontrolovat, kolik kandidátů
   přinese který zdroj (Google News vs GDELT vs feedy). Doladit jazykové dotazy.
2. **Ověřit feed `rroma.org/feed/`** a zvážit přidání dalších zdrojů do `config.py`.
3. **Perzistence „viděných" URL** — proti opakování zpráv mezi běhy (např.
   `state/seen.json` + actions/cache ve workflow). Zatím řešeno jen časovým oknem.
4. **Doladit prompt `SYSTEM`** v `analyze.py` podle reálných výsledků (false
   positives/negatives).
5. **Nasazení** — privátní GitHub repo, vyplnit Secrets (ANTHROPIC_API_KEY,
   EMAIL_*, SMTP_*), upravit časy cronu (UTC) v `digest.yml`, první běh ručně.

## Pozn. k účtům
Stavění v Claude Code pokrývá předplatné. **Běh hotového pipeline** ale volá
Anthropic API a vyžaduje vlastní API klíč (pay-as-you-go z console.anthropic.com) —
jak při lokálním testu, tak v GitHub Actions.
