# Profil „cz" – Romové v ČR (druhý feed pro téhož agenta)

Druhý monitoring vedle světového. Sbírá dění v ČR v agendě ROMEA.cz:
Romy jako téma **bez ohledu na obor** (sport, kultura, kriminalita, byznys)
a k tomu témata, která se Romů týkají, i když je článek nezmiňuje
(sociální dávky, bydlení, segregace ve školách, diskriminace, extremismus).

Publikuje `feed-cz/`, čte ho **stejný agent** jako světový feed a posílá z něj
**samostatný e-mail**, ať se obojí neplete dohromady.

## Zdroj dat

| | |
|---|---|
| repozitář | `zdenekrysavy-lang/roma-monitor` |
| větev | `main` |
| soubor | `feed-cz/candidates.json` |

Záložní cesty (viz `chatgpt_task.md`, kde je celá historie ladění doručení):
- HTML stránka: `https://zdenekrysavy-lang.github.io/roma-monitor/feed-cz/`
- JSON přes Pages: `…/roma-monitor/feed-cz/candidates.json`

## Čím se liší od světového profilu

Světový monitor hledá **etnický termín** napříč 15 jazyky. Český hledá
**témata**, protože velká část relevantních zpráv slovo „Rom" vůbec
neobsahuje — namátkou ze skutečné produkce ROMEA:
*„Statisíce domácností začínají dostávat superdávku"*,
*„Segregace dětí ve školách nekončí"*, *„Vnitro vynechalo SPD ze zprávy
o extremismu"*.

Cenou za to je šum (běžné sociální a bytové zpravodajství bez romského
přesahu). **Ten musí vytřídit agent** — pravidlo je v promptu níže.

## Dodatek do promptu naplánovaného úkolu

Přidej k existujícímu úkolu jako druhou část. Pošle se **druhý, samostatný
e-mail**:

---
Poté pomocí konektoru GitHub otevři soubor `feed-cz/candidates.json` ze stejné
větve `main` repozitáře `zdenekrysavy-lang/roma-monitor`. Jde o monitoring dění
v ČR. Zpracuj ho zvlášť a pošli z něj SAMOSTATNÝ e-mail s nadpisem
„Romové v ČR – přehled".

1. Ponech zprávu, jen pokud se týká ROMŮ — a to buď:
   a) výslovně (článek Romy zmiňuje, ať už jde o cokoli: soud, sport, kulturu,
      hudbu, kriminalitu, politiku, komunitní dění), NEBO
   b) fakticky, i když je nezmiňuje — tedy dopadá na romské komunity:
      sociální dávky a superdávka, bydlení a vyloučené lokality, ubytovny,
      obchod s chudobou, segregace ve školách, diskriminace, předsudečné
      násilí, extremismus a nenávistné projevy, policejní zákroky vůči
      menšinám, sterilizace a odškodnění, romský holokaust.
   ZAHOĎ obecné zprávy BEZ romského přesahu: běžné ekonomické a dopravní
   zpravodajství, výstavba bytů jako taková, důchody, kulturní přehledy,
   zahraniční politika, sportovní výsledky bez souvislosti s Romy, výročí
   a historické zajímavosti.
2. U zbylých urči důležitost: KLÍČOVÉ / střední / nízká (klíčové = násilí,
   soudy, legislativa, diskriminace, kroky vlády a úřadů).
3. Ke každé napiš 1–2větné shrnutí v ČEŠTINĚ a přidej odkaz (pole `url`).
4. Seřaď od nejdůležitějších, seskup podle důležitosti.
5. Na konec připoj řádek „Zdroje tohoto běhu:" s počty sources.google_news,
   sources.feeds, sources.watch. Pokud sources.google_news_status není "ok",
   přidej upozornění, že se Google News nenačetly.

Pokud je pole `candidates` prázdné nebo se soubor nepodaří otevřít, napiš mi to
a tenhle druhý e-mail neposílej.
---

## Na co myslet
- **Vlastní články ROMEA jsou z feedu vyloučené** (`EXCLUDE_SOURCES`
  v `config.py`) — redakce je nepotřebuje dostávat zpátky.
- Okno je širší než u světového profilu (`when:3d`, 72 h), protože českých
  zpráv k těmto tématům vychází řádově míň. Opakování hlídá
  `state/seen-cz.json`, takže feed nese jen nové položky.
- Trefnost sběru je zhruba poloviční (měřeno 8/2026) — to je záměr:
  radši širší záběr a přísnější třídění agentem než zmeškaná zpráva.
