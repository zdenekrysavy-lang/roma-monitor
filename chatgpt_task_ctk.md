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

## 1) Přeposílání – JE HOTOVO, agent to už dělá

Ověřeno 9. 8. 2026 přímo ve schránce: `zdenek.rysavy@romea.cz` běží na
**Gmailu** (ne na Outlooku) a chodí tam přeposlané ČTK od `romea@romea.cz`.

Klíčové zjištění: **tamní agent přílohu už čte a rozebírá v těle zprávy.**
Předmět „Fwd: Zpravodajství ČTK", tělo obsahuje:

```
**Kategorie:** Redakce Romea.cz / Romano voďi / romská kultura a extremismus
**Priorita:** P1
**Proč je relevantní:** HTML příloha obsahuje dvě zprávy. … Romský Bašavel
2026 (15:00, Centrální park na Pankráci) … náklady německého státu po
žhářském útoku …
**Doporučená akce:** Prověřit Romský Bašavel pro redakční pokrytí …
**Původní odesílatel:** ibmail <ibmail@ctk.cz>
```

Monitorovací agent si tedy vystačí s TĚLEM zprávy – přílohu otevírat nemusí.
(Kdyby ji přesto chtěl, Gmail konektor ji vystavuje jako
`dokument_CTK.html`, `text/html`, včetně ID.)

> **Nezakládej druhé, „holé" přeposílací pravidlo.** Ve schránce se objevily
> oba druhy: rozbor od agenta i syrové přeposlání bez přidané hodnoty. To
> druhé jen duplikuje práci – vypni ho.

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
Kromě obou feedů zkontroluj poštu (Gmail): najdi zprávy s předmětem
„Fwd: Zpravodajství ČTK" od odesílatele romea@romea.cz, které dorazily od
tvého minulého běhu (zhruba za posledních 12 hodin). V TĚLE zprávy je už
hotový rozbor (Kategorie, Priorita, Proč je relevantní, Doporučená akce) –
vycházej z něj, přílohu otevírat nemusíš. Pokud by tělo rozbor neobsahovalo,
otevři přílohu `dokument_CTK.html`.

Kdyby dorazila táž dávka ČTK dvakrát (jednou s rozborem, jednou jako holé
přeposlání), použij tu s rozborem a druhou ignoruj.

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

## Další zdroj, který se u toho našel: NewtonMedia

Ve schránce chodí i profesionální mediální monitoring
(`newtonone@newtonmedia.eu`, předmět „Monitoring - ROMEA, Přehled, N").
Stejnou cestou by šel zapojit taky – zatím to neděláme, ale stojí za zvážení,
až se ČTK v přehledu usadí.
