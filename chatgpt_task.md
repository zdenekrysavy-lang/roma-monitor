# Režim B – napojení na ChatGPT agenta

Aplikace (`gather.py` + workflow `gather.yml`) 2× denně publikuje seznam
kandidátských zpráv do souboru `feed/candidates.json`. Tvůj agent v ChatGPT
si ten soubor stáhne a udělá chytrou část — bez poplatků za Anthropic API.

## 1) Zpřístupni feed veřejně
ChatGPT musí na soubor dosáhnout přes veřejnou HTTPS adresu. Data jsou jen
veřejné titulky zpráv, takže to nic citlivého neodhaluje. Možnosti:

- **Veřejný repozitář** → adresa bude:
  `https://raw.githubusercontent.com/<ucet>/<repo>/main/feed/candidates.json`
- **GitHub Pages** (i z jinak privátního obsahu) → `https://<ucet>.github.io/<repo>/feed/candidates.json`
- **Veřejný Gist** aktualizovaný workflow (repo zůstane privátní).

> Pokud necháš repo privátní, `raw.githubusercontent.com` bez tokenu nefunguje
> a ChatGPT si feed nestáhne. Pro tenhle režim zvol jednu z veřejných variant.

## 2) Vytvoř naplánovaný úkol v ChatGPT
Potřebuješ placený plán (Plus/Pro/Team). V ChatGPT zapni Tasks / Scheduled
a vytvoř úkol s kadencí „každý den 7:00 a 17:00" a tímto promptem
(`<URL_FEEDU>` nahraď adresou z kroku 1):

---
Stáhni JSON z `<URL_FEEDU>`. Obsahuje pole `candidates` se zprávami
(title, url, source, lang, snippet). Udělej s nimi tohle:

1. Vyřaď vše, co NEpojednává o Romech / romské menšině jako etnické, sociální
   nebo politické skupině (Roma, Romani, Sinti, cigáni, gitanos, Travellers…).
   ZAHOĎ: město Řím / AS Roma / film Roma / fotbalisty jménem Romulo / příjmení
   typu „Roma…" bez souvislosti s menšinou.
2. U zbylých urči důležitost: KLÍČOVÉ / střední / nízká (klíčové = násilí,
   legislativa, soudy, mezinárodní dopad).
3. Ke každé napiš 1–2větné shrnutí v ČEŠTINĚ a přidej odkaz na zdroj.
4. Seřaď od nejdůležitějších, seskup podle důležitosti.
5. Pošli mi to e-mailem jako přehledný seznam s nadpisem
   „Romové ve světě – přehled".
Pokud je pole prázdné nebo se feed nepodaří stáhnout, napiš to a nic neposílej.
---

## Na co myslet
- Každý běh agenta se počítá do měsíčního limitu zpráv ChatGPT.
- Třídění dělá ChatGPT pokaždé znovu, takže kvalita/rozsah kolísá víc než
  u kódového třídění (režim A). Zato pracuje z KOMPLETNÍHO seznamu, který
  posbírala aplikace – ne z vlastního mělkého prohledávání webu.
- Chceš-li to pevně v ruce (přesný formát, dedup mezi běhy), je lepší režim A.
