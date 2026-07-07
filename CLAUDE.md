# CLAUDE.md — kontext projektu pro Claude Code

## Co to je
Automatický pipeline, který **2× denně** projde zpravodajské zdroje napříč
jazyky a publikuje kandidátské zprávy o Romech ve světě. Třídění, česká
shrnutí a e-mail pak dělá naplánovaný agent v ChatGPT (režim B, NASAZENO)
nebo Claude přes API (režim A, připraveno, vypnuto). Plánování řeší GitHub
Actions v repu `zdenekrysavy-lang/roma-monitor` (veřejné).

## Dva režimy
- **B (feed pro ChatGPT) — AKTIVNÍ:** `gather.py` → sběr + publikace
  `feed/candidates.json` (workflow `gather.yml`, cron 2× denně). Bez API klíčů.
  Veřejná URL feedu:
  `https://raw.githubusercontent.com/zdenekrysavy-lang/roma-monitor/main/feed/candidates.json`
  Prompt agenta: `chatgpt_task.md`.
- **A (plný):** `main.py` → sběr + Claude třídí/shrnuje + e-mail. Vyžaduje
  ANTHROPIC_API_KEY + SMTP secrets. Cron v `digest.yml` je zakomentovaný,
  jde spustit jen ručně (workflow_dispatch).

## Architektura sběru (fetch.py)
```
Google News RSS (15 jazyků, when:1d, strop 12/dotaz) ┐
GDELT (globální translingual, okno 72h)              ├─► dedup ─► seen.json filtr ─► feed
RSS_FEEDS (13 romských feedů, okno 72h)              │
WATCH_SITES (10 webů bez feedu, přes GN site:)       ┘
```
- **Google News:** dotazy jen pro jazyky s JEDNOZNAČNÝM termínem pro Romy
  (Ρομά, Romowie, ciganos, romer…). Jazyky, kde se kořen „rom/Roman" sráží
  s AS Roma / městem Řím / Rom-Com (ru, nl, tr, sr, hr, sq, uk) se NEřeší
  dedikovaným dotazem — pokrývá je GDELT přes překlad. Čeština záměrně
  vynechána (domácí dění si ROMEA pokrývá sama).
- **GDELT:** vrtkavá free služba. Retry (6 pokusů, backoff + rozptyl) na
  všechny chyby; okno 72h, protože jejich čerstvé (real-time) okno má díry
  a 13h vracelo prázdno (7/2026). Do feedu jde `gdelt_status` + diagnostika
  `gdelt_note` (co GDELT reálně vrátil).
- **Google News rate-limit:** 25 dotazů jede s pauzou GN_PAUSE=2 s, browser
  UA, retry na 429/503; do feedu jde `google_news_status`.
- **seen.json (`state/seen.json`):** perzistentní dedup mezi běhy (TTL 14
  dní), commituje ho workflow. Feed obsahuje jen NOVÉ položky. Ukládá se až
  PO úspěšném zápisu feedu (jinak by se články ztratily).
- **Okna:** Google News 13h (LOOKBACK_HOURS), GDELT 72h (GDELT_TIMESPAN),
  řídce publikující feedy/weby FEED_LOOKBACK_HOURS=72; opakování mezi běhy
  hlídá seen.json.

## Soubory
- `config.py`  — nastavení + zdroje („TVOJE ZDROJE": `RSS_FEEDS` jako
  (url, jazyk), `WATCH_SITES` jako (doména, hl, gl))
- `fetch.py`   — sběr + dedup + LAST_STATS (statistika běhu → feed `sources`)
- `gather.py`  — režim B: feed + seen.json (JSON i lidsky čitelný MD)
- `analyze.py` — režim A: třídění/shrnutí přes Claude; prompt `SYSTEM`
- `render.py` / `notify.py` / `main.py` — režim A: HTML, SMTP, orchestrace
- `.github/workflows/gather.yml` — režim B, cron 2× denně (5:00, 15:00 UTC)
- `.github/workflows/digest.yml` — režim A, cron VYPNUTÝ

## Jak spustit / testovat
```bash
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install feedparser requests                  # režim B (anthropic netřeba)
python gather.py
```
POZOR při lokálním testu: `gather.py` přepíše `feed/*` a `state/seen.json`.
Buď je po testu vrať (`git checkout -- feed/ state/`), nebo testuj
s přesměrováním: `FEED_DIR=/tmp/f SEEN_PATH=/tmp/s.json python gather.py`.
Necommituj lokálně vygenerovaný feed — přepsal bys produkční (bot commituje
vlastní).

## Konvence a pravidla (DŮLEŽITÉ)
- **Shrnutí vždy česky.** Výstup míří pro českou redakci (ROMEA.cz).
- **Žádné tajné údaje v kódu.** V režimu B žádné nejsou; režim A bere vše
  z proměnných prostředí. Necommitovat `.env`.
- **Odolnost zdrojů:** když jeden zdroj selže, zaloguj (a propiš stav do
  feedu `sources`) a pokračuj — běh nesmí spadnout kvůli jednomu zdroji.
- **Relevance:** sběr je záměrně široký (recall), šum (AS Roma, město Řím,
  Gypsy Rose, gypsy moth…) dotřiďuje ChatGPT/Claude — NEřešit zužováním
  GDELT dotazu, to zabíjí multijazyčný záběr (poučení z 6/2026).
- **Nové zdroje:** vždy nejdřív proklepnout (funkční feed? čerstvost?
  indexuje ho Google?), pak zařadit do RSS_FEEDS nebo WATCH_SITES se
  správným jazykem.
- Modely (režim A): výchozí `claude-sonnet-5`; levnější
  `claude-haiku-4-5-20251001` (přes `CLAUDE_MODEL`).

## Známé limity / kam to posunout
1. **GDELT je zdegradovaný upstream** (7/2026: i týdenní okno vrací málo) —
   sledovat `gdelt_note` ve feedu; hlavní zátěž nesou Google News + feedy.
2. Souběh dvou runů může kolidovat na push (řeší `git pull --rebase`,
   vzácně může selhat rebase konfliktem na feed souborech).
3. Spící feedy (roma-news.com, romatimes.news, tvroma.sk, kalisara.hr)
   publikují na Facebooku místo webu — FB monitorovat nejde (Meta blokuje);
   nechány napojené, ožijí samy.
4. Režim A: před aktivací vyplnit Secrets (ANTHROPIC_API_KEY, EMAIL_*,
   SMTP_*) a odkomentovat cron v `digest.yml`.

## Pozn. k účtům
Provoz režimu B je **zdarma** (veřejné repo = neomezené Actions minuty,
ChatGPT agent v rámci předplatného). Režim A by volal Anthropic API
(pay-as-you-go klíč z console.anthropic.com).
