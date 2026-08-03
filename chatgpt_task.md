# Režim B – napojení na ChatGPT agenta

Aplikace (`gather.py` + workflow `gather.yml`) 2× denně publikuje seznam
kandidátských zpráv do `feed/candidates.json`. Agent v ChatGPT si soubor
stáhne a udělá chytrou část — bez poplatků za Anthropic API.

## Jak agent feed čte (pořadí podle spolehlivosti)

### 1) Konektor GitHub (DOPORUČENO)
V ChatGPT připoj **GitHub konektor v režimu jen pro čtení** a nech agenta
načíst soubor přímo z repozitáře:

| | |
|---|---|
| repozitář | `zdenekrysavy-lang/roma-monitor` |
| větev | `main` |
| soubor | `feed/candidates.json` |

Čte se přes GitHub API, takže to obchází obojí, na čem ostatní cesty selhaly
(403 z CDN, 401 z webového prohlížení). V promptu pak **nepoužívej slova
„stáhni" ani „po stažení"** — sveden by zkusil HTTP a zase narazil.

### 2) HTML stránka přes GitHub Pages (záloha)
Feed se publikuje i jako obyčejná webová stránka, kterou prohlížecí nástroj
přečte bez potíží (na rozdíl od surového `.json`):

```
https://zdenekrysavy-lang.github.io/roma-monitor/feed/
```

Vyžaduje jednorázově zapnout Pages: *Settings → Pages → Source: Deploy from
a branch → Branch: `main` / `(root)` → Save*.

### 3) Přímé adresy JSON (pro tebe, ne pro agenta)
```
https://cdn.jsdelivr.net/gh/zdenekrysavy-lang/roma-monitor@main/feed/candidates.json
https://raw.githubusercontent.com/zdenekrysavy-lang/roma-monitor/main/feed/candidates.json
```
Obě fungují z prohlížeče i z příkazové řádky (ověřeno HTTP 200 i pro UA
`ChatGPT-User`), ale nástroje ChatGPT na nich selhávají — viz níže.

> **Historie ladění (8/2026), ať se to znovu nehledá:**
> - `raw.githubusercontent.com` → agent hlásil **403**. Příčina: stahoval to
>   spouštěním kódu, a sandbox ChatGPT nemá přístup k internetu.
> - `cdn.jsdelivr.net` → totéž **403** ze stejného důvodu.
> - webové prohlížení na `.json` → **401 Unauthorized**; prohlížecí nástroj je
>   stavěný na stránky, ne na surové soubory.
> - **Hosting je přitom v pořádku:** obě adresy vrací HTTP 200 i pro oficiální
>   UA `ChatGPT-User` a `OAI-SearchBot`, `robots.txt` nikde není.
>
> Proto se čte přes GitHub konektor (varianta 1), případně HTML stránku (2).
>
> CDN drží obsah 12 h, proto workflow po každé publikaci volá
> `purge.jsdelivr.net` — agent tak vždy dostane čerstvý feed.
>
> Původní adresa `https://raw.githubusercontent.com/zdenekrysavy-lang/roma-monitor/main/feed/candidates.json`
> funguje dál (např. z prohlížeče), jen na ni nespoléhej u automatů.

Feed obsahuje:
- `candidates` — pole zpráv (title, url, source, lang, snippet, published).
  Jsou to jen **NOVÉ zprávy od minulého běhu** (opakování hlídá `state/seen.json`).
- `sources` — statistika sběru: počty z Google News / GDELT / feedů / watch
  webů + stavy `gdelt_status`, `google_news_status` a diagnostika `gdelt_note`.
- `generated_utc`, `count`.

Prázdný feed (`count: 0`) je normální stav = od minulého běhu nic nového.

## Naplánovaný úkol v ChatGPT (Tasks / Scheduled)

Kadence „každý den 7:00 a 17:00". Aktuálně nasazený prompt:

---
Pomocí konektoru GitHub otevři soubor `feed/candidates.json` z větve `main`
repozitáře `zdenekrysavy-lang/roma-monitor`. Je to veřejný repozitář, stačí
přístup jen pro čtení. Nepoužívej k tomu webové prohlížení ani spouštění kódu.

Soubor obsahuje pole `candidates` se zprávami (title, url, source, lang, snippet)
a pole `sources` se statistikou sběru. Je to SUROVÝ sběr napříč jazyky —
obsahuje šum, který musíš odfiltrovat. Udělej tohle:

1. Vyřaď vše, co NEpojednává o Romech / romské menšině jako etnické, sociální
   nebo politické skupině (Roma, Romani, Sinti, cigáni, gitanos, Travellers,
   francouzské „gens du voyage"…). ZAHOĎ jako šum: fotbalovou AS Roma i fotbal
   obecně (Mourinho, Casillas, přestupy), město Řím a ulice/náměstí „Roma",
   film Roma, osoby jménem Roman/Romulo, letiště, koncerty a volební
   zpravodajství jen náhodně obsahující „Roma/gitano", příjmení „Roma…" bez
   vazby na menšinu, a gypsy-šum: Gypsy Rose / Gypsy Rose Blanchard (krimi),
   „gypsy moth" (motýl), gypsy jazz / Gipsy Kings (hudba), gypsy cab — obecně
   „gypsy/cigán" tam, kde nejde o etnickou skupinu.
2. U zbylých urči důležitost: KLÍČOVÉ / střední / nízká (klíčové = násilí,
   legislativa, soudy, diskriminace, mezinárodní dopad).
3. Ke každé napiš 1–2větné shrnutí v ČEŠTINĚ a přidej odkaz na zdroj (pole `url`).
4. Seřaď od nejdůležitějších, seskup podle důležitosti.
5. Pošli mi to e-mailem jako přehledný seznam s nadpisem „Romové ve světě – přehled".
6. Na konec e-mailu připoj řádek „Zdroje tohoto běhu:" s počty
   sources.google_news, sources.gdelt, sources.feeds, sources.watch.
   - Pokud sources.gdelt_status NENÍ "ok", přidej: „⚠️ Globální vrstva GDELT
     se tentokrát nenačetla – přehled může být užší, hlavně o neevropské
     a méně obvyklé jazyky."
   - Pokud sources.google_news_status NENÍ "ok", přidej: „⚠️ Google News se
     tentokrát nenačetly (rate-limit) – přehled je postaven hlavně z GDELT
     a romských feedů."

Pokud je pole `candidates` prázdné nebo se soubor nepodaří otevřít, napiš mi to
a nic neposílej.
---

## Na co myslet
- Každý běh agenta se počítá do měsíčního limitu zpráv ChatGPT.
- Odkazy v `url` jsou často přesměrovací adresy Google News — po kliknutí
  vedou na originální článek, to je v pořádku.
- Třídění dělá ChatGPT pokaždé znovu, takže kvalita/rozsah kolísá víc než
  u kódového třídění (režim A). Zato pracuje z KOMPLETNÍHO seznamu, který
  posbírala aplikace – ne z vlastního mělkého prohledávání webu.
- Chceš-li to pevně v ruce (přesný formát, stabilní třídění), je lepší režim A.
