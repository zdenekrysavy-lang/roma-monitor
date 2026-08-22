# Briefing pro agenta na VPS

Krátké shrnutí toho, co potřebuje vědět agent, který zpracovává monitoring.
Delší kontext je v `PROMPT_AMANPOUR.md`, technické pozadí v `CLAUDE.md`.

---

Ahoj, tady je co potřebuješ vědět o monitoringu ROMEA.

## 1. Opraveno: odkazy jsou teď přímé

Stěžoval sis, že `url` obsahuje jen wrapper `news.google.com/rss/articles/CBMi…`,
který nejde otevřít. **Vyřešeno u zdroje.** Generátor feedu teď wrappery
rozbaluje sám (cookie SOCS + Google batchexecute), takže `url` je přímá adresa
článku — `ct24.ceskatelevize.cz/clanek/…`, `idnes.cz/…` atd. V testu 100 %
úspěšnost. Když se rozbalit výjimečně nepodaří, položka si ponechá původní
adresu — raději wrapper než ztracená zpráva.

## 2. Kde jsou data

Repozitář `zdenekrysavy-lang/roma-monitor`, větev `main`, je veřejný:

- `feed/candidates.json` — **Romové ve světě** (15 jazyků + GDELT + romské feedy)
- `feed-cz/candidates.json` — **dění v ČR** v agendě ROMEA

Struktura obou: `generated_utc`, `count`, `sources` (statistika běhu),
`candidates` (pole zpráv: title, url, source, lang, snippet, published).

Feed nese **jen NOVÉ položky od minulého běhu** — o dedup se stará
`state/seen.json`, ty ho neřeš. Prázdný feed je normální stav.

Když potřebuješ zpětně dohledat, co už bylo odesláno:
`https://zdenekrysavy-lang.github.io/roma-monitor/feed/archiv.html`
(a `…/feed-cz/archiv.html`) — archiv 7 dní bez ohledu na seen.

## 3. Třetí zdroj: ČTK

V Gmailu zprávy „Fwd: Zpravodajství ČTK" od `romea@romea.cz`. V TĚLE je už
hotový rozbor (Kategorie, Priorita, Proč je relevantní) — vycházej z něj,
přílohu otevírat nemusíš. Text ČTK je licencovaný: **nikdy ho nevkládej celý**,
piš vlastní shrnutí.

## 4. Kadence

**Jednou denně, každý den včetně víkendu, 9:15.** Sběr běží v 8:45 a 8:50,
takže máš data připravená.

## 5. Na co si dát pozor

**Pole `published` NENÍ spolehlivé.** Některé weby protlačují staré články do
Google News s čerstvým datem — ověřený případ: článek hlášený jako 21 hodin
starý byl ve skutečnosti z června 2022. Proto:
- ověř skutečné datum na stránce článku,
- cokoli staršího 7 dní vyřaď (výjimka: pozvánky na budoucí akce),
- u každé zprávy v e-mailu uveď datum,
- odkazy s `/galerie-` nebo `?photo=` vyřaď vždy — to jsou fotogalerie, ne články.

**Sběr je záměrně široký**, takže ve feedu je šum (AS Roma, město Řím, Gypsy
Rose, obecné sociální zpravodajství). Filtrovat je tvoje práce, pravidla jsou
v zadání.

## 6. Výstup

Dva samostatné e-maily: „Romové ve světě – přehled" a „Romové v ČR – přehled".
Zprávy z ČTK zařaď podle místa děje do toho, kam patří. Na konec obou připoj
řádek se statistikou z pole `sources`.
