# Třetí zdroj: e-mailový servis ČTK

Vedle dvou feedů (`feed/` svět, `feed-cz/` Česko) čte agent i **tematické
výběry ČTK**, které chodí na `romea@romea.cz` jako HTML příloha.

Do pipeline se ČTK **záměrně nezapojuje** – viz „Proč ne přes feed" níže.
Řeší se čistě na úrovni agenta v ChatGPT.

## Jak to funguje

```
ČTK e-mail (8:55, 14:55)  →  romea@romea.cz
        ↓ pravidlo pro přeposlání
   schránka, ke které má agent konektor
        ↓
   agent to přečte spolu s oběma feedy a zařadí do přehledu
```

## 1) Nastav přeposílání

V `romea@romea.cz` vytvoř pravidlo: e-maily s předmětem obsahujícím
„E-mail servis ČTK" (nebo od odesílatele ČTK) přeposílat do schránky, ke které
má agent konektor (např. `zdenek.rysavy@romea.cz`).

## 2) Načasování – čemu dát pozor

| | čas |
|---|---|
| ČTK posílá | 8:55 a 14:55 |
| agent čte | 8:00 a 18:00 |

Při současném nastavení **ranní přehled (8:00) žádné ČTK neobsahuje** – ranní
dávka dorazí až po něm. Večerní běh v 18:00 pak pobere obě dávky najednou.

Chceš-li ČTK i v ranním přehledu, posuň ranní běh agenta na **9:15**. Sběr
feedů (7:35) tomu nevadí, ten běží nezávisle.

## 3) Dodatek do promptu

Přidej k úkolu jako třetí část, PŘED odesláním obou e-mailů:

---
Kromě obou feedů zkontroluj poštu: najdi e-maily „E-mail servis ČTK", které
dorazily od tvého minulého běhu (tj. za posledních zhruba 12 hodin), a otevři
jejich HTML přílohu. Každá obsahuje seznam zpráv – u každé je titulek, datum,
klíčová slova a plný text.

Se zprávami z ČTK nalož stejně jako s položkami z feedů:
- Použij stejné pravidlo relevance (týká se to Romů – výslovně, nebo fakticky?).
- Zařaď je do TOHO z obou přehledů, kam patří podle místa děje:
  domácí zprávy do „Romové v ČR", zahraniční do „Romové ve světě".
- U každé takové položky uveď jako zdroj „ČTK" a datum vydání.
- Shrnutí piš vlastními slovy (1–2 věty česky), NEVKLÁDEJ do e-mailu celý
  text ČTK – je licencovaný.
- Pokud ČTK zprávu duplikuje něco z feedů, ponech ji jen jednou.

Pokud žádný nový e-mail od ČTK nedorazil, nic nehlas a pokračuj běžně.
---

## Proč ne přes feed (a ne do repozitáře)

Obsah ČTK je licencovaný (`©Česká tisková kancelář`). Náš repozitář je
**veřejný** a navíc publikovaný přes GitHub Pages, takže uložit tam plné texty
by znamenalo je fakticky znovu zveřejnit – to by licenci porušovalo.

Cesta přes poštu je proto nejen nejjednodušší, ale i právně nejčistší:
zprávy se nikam neukládají, agent si je přečte a použije jen vlastní shrnutí.

## Co ověřit při prvním běhu

ČTK chodí jako **příloha**, ne jako tělo e-mailu. Ne každý e-mailový konektor
umí přílohy otevřít. Když agent nahlásí, že přílohu nepřečte, řešení jsou:
- přeposílat s volbou „vložit do těla zprávy" (pokud to poštovní klient umí),
- nebo nechat mailového agenta v `romea@romea.cz` obsah přílohy vypsat do těla
  přeposílané zprávy.
