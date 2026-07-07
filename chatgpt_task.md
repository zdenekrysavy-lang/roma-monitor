# Režim B – napojení na ChatGPT agenta

Aplikace (`gather.py` + workflow `gather.yml`) 2× denně publikuje seznam
kandidátských zpráv do `feed/candidates.json`. Agent v ChatGPT si soubor
stáhne a udělá chytrou část — bez poplatků za Anthropic API.

## Veřejná adresa feedu (NASAZENO)

```
https://raw.githubusercontent.com/zdenekrysavy-lang/roma-monitor/main/feed/candidates.json
```

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
Stáhni JSON z https://raw.githubusercontent.com/zdenekrysavy-lang/roma-monitor/main/feed/candidates.json
Obsahuje pole `candidates` se zprávami (title, url, source, lang, snippet)
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

Pokud je pole `candidates` prázdné nebo se feed nepodaří stáhnout, napiš mi to
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
