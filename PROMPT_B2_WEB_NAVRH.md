# NÁVRH – krok B2 pro zadání denní rutiny (NENASAZENO)

Tento text ještě NENÍ v zadání cloudové rutiny. Až se nasadí, doplní se do
jejího zadání jako nová sekce za „E-mail 1“ – zadání rutiny se NEnahrazuje
celé (kopie platného zadání je v `PROMPT_AMANPOUR.md`).

Před nasazením upravit: rutina běží v cloudu, ne na VPS. Skript si stáhne
z repa (`curl` z raw.githubusercontent.com) a token vezme z proměnné
prostředí rutiny, ne ze souboru `~/.config/…`. Cesty `~/roma-monitor/…`
níže proto ještě nesedí.

---

## B2) Výběr pro web „Romové ve světě“

Zprávy z e-mailu č. 1 se zveřejňují i na webu (česky a anglicky). Než
e-mail č. 1 odešleš, ulož TYTÉŽ zprávy jako JSON a nahraj je skriptem.

**Co na web patří:** všechny zprávy z e-mailu č. 1 (KLÍČOVÉ, střední
i nízká) – KROMĚ zpráv z ČTK. ČTK je licencovaná a nemá veřejný odkaz
na celé znění, na web ji nedávej nikdy. Na web nedávej nic, co v e-mailu
není.

**1. Zapiš soubor** `~/roma-monitor/vyber/vyber-RRRR-MM-DD.json`
(dnešní datum; složku případně vytvoř) v tomto tvaru:

```json
{
  "date": "RRRR-MM-DD",
  "items": [
    {
      "url": "https://…",
      "source": "Le Monde",
      "country": "FR",
      "lang": "fr",
      "published": "RRRR-MM-DD",
      "importance": "high",
      "category": {"cs": "Bydlení", "en": "Housing"},
      "original_title": "titulek v jazyce originálu",
      "title":   {"cs": "…", "en": "…"},
      "summary": {"cs": "…", "en": "…"},
      "image": "https://… (nepovinné)"
    }
  ]
}
```

Pravidla pro jednotlivá pole:

- `date` – dnešní datum běhu.
- `url` – přímá adresa článku, stejná jako v e-mailu.
- `source` – název média, jak se samo jmenuje („Le Monde“, „24.hu“).
- `country` – ISO kód země, KDE SE VĚC STALA, velkými písmeny (FR, HU,
  SK, RO…). Pro instituce EU `EU`, pro mezinárodní věci bez jedné země `INT`.
- `lang` – jazyk článku (ISO kód: fr, hu, en…).
- `published` – OVĚŘENÉ datum vydání (viz A2), ne údaj z feedu.
  Výslovně ohlášená budoucí událost starší než 7 dní: přidej
  `"upcoming_event": true`, jinak ji skript odmítne.
- `importance` – KLÍČOVÉ = `high`, střední = `medium`, nízká = `low`.
- `category` – jedna dvojice z tohoto seznamu (ať je web jednotný):
  Diskriminace/Discrimination · Násilí/Violence · Justice/Justice ·
  Politika/Politics · Bydlení/Housing · Vzdělávání/Education ·
  Zaměstnanost/Employment · Zdraví/Health · Sociální vyloučení/Social
  exclusion · Kultura/Culture · Historie a paměť/History and remembrance ·
  Migrace/Migration · Komunita/Community
- `original_title` – titulek článku v originále, beze jména média.
- `title` – vlastní věcný titulek česky a anglicky, do 120 znaků, bez
  názvu média a bez bulvárních obratů.
- `summary` – 1–2 věty VLASTNÍMI SLOVY česky a anglicky (do 400 znaků).
  Nepřekládej doslova perex článku. Uveď jen to, co článek skutečně říká;
  sporná tvrzení přiřaď („podle policie“, „tvrdí“).
- `image` – adresa hlavní fotky článku, pokud ji vidíš v metadatech
  stránky (`og:image`). Když ne, pole vynech – fotku dohledá web sám.

Angličtinu piš přirozeně pro mezinárodní čtenáře. Používej „Roma“
(slovo „Gypsy“ jen v doslovné citaci).

**2. Nahraj ho:**

```bash
python3 ~/roma-monitor/odeslat_vyber.py ~/roma-monitor/vyber/vyber-RRRR-MM-DD.json
```

- `OK: nahráno …` – hotovo, pokračuj odesláním e-mailu č. 1.
- Návratový kód **2** (chybná data) – skript vypíše, co je špatně. Soubor
  oprav a spusť znovu (nejvýš dvakrát). Zprávu, kterou opravit nejde,
  z výběru vyřaď – v e-mailu ji nech.
- Návratový kód **1** (síť, token) – zkus to za minutu ještě jednou.
- Když se nahrání nepovede ani tak, připiš na konec e-mailu č. 1:
  „⚠️ Výběr se dnes nepodařilo nahrát na web: <poslední řádek chyby>“
  a e-mail normálně odešli.
- Když na web nezbude žádná zpráva (třeba jen ČTK), nic nenahrávej.
