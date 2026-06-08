"""Analýza kandidátů přes Claude API:
   - rozhodne o relevanci (vyřadí Řím, AS Roma, film Roma…)
   - určí důležitost
   - napíše české shrnutí + kategorii
"""
import json

import anthropic

import config

client = anthropic.Anthropic()  # bere ANTHROPIC_API_KEY z prostředí

BATCH_SIZE = 40

SYSTEM = """Jsi editor zpravodajství specializovaný na témata romské menšiny ve světě.
Dostaneš JSON seznam kandidátských článků (titulek, zdroj, jazyk, úryvek).

Pro KAŽDÝ článek:
1. Rozhodni, zda SKUTEČNĚ pojednává o Romech / romské menšině jako etnické,
   sociální nebo politické skupině (Roma, Romani, Sinti, cigáni, gitanos,
   gens du voyage, Travellers atd.).
   VYŘAĎ (relevant=false): město Řím (Roma/Roms), fotbalový klub AS Roma,
   film Roma, osobní jméno Roma, a cokoli bez souvislosti s menšinou.
2. U relevantních urči důležitost: "high" (zásadní – násilí, legislativa,
   soudy, mezinárodní dopad), "medium", nebo "low".
3. Napiš stručné shrnutí v ČEŠTINĚ (1–2 věty), o co ve zprávě jde.
4. Přiřaď krátkou kategorii v češtině (např. Diskriminace, Násilí, Politika,
   Justice, Bydlení, Vzdělávání, Kultura, Zdraví, Historie).

Vrať POUZE validní JSON pole, žádný jiný text, žádné markdown bloky. Formát:
[{"index": <int>, "relevant": <bool>, "importance": "high|medium|low",
  "category": "<text>", "summary_cs": "<text>"}]"""


def _strip_fences(t: str) -> str:
    t = t.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.endswith("```"):
            t = t.rsplit("```", 1)[0]
    return t.strip()


def _analyze_batch(items: list, offset: int) -> list:
    payload = [{
        "index":   offset + i,
        "title":   it["title"],
        "source":  it["source"],
        "lang":    it.get("lang", ""),
        "snippet": it.get("snippet", ""),
    } for i, it in enumerate(items)]

    msg = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=4000,
        system=SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    text = "".join(b.text for b in msg.content if b.type == "text")
    try:
        return json.loads(_strip_fences(text))
    except Exception as ex:
        print(f"  JSON parse chyba: {ex}")
        return []


def analyze(items: list) -> list:
    results = []
    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start:start + BATCH_SIZE]
        for r in _analyze_batch(batch, start):
            idx = r.get("index")
            if idx is None or idx >= len(items) or not r.get("relevant"):
                continue
            results.append({
                **items[idx],
                "importance": r.get("importance", "low"),
                "category":   r.get("category", "—"),
                "summary_cs": r.get("summary_cs", ""),
            })
    order = {"high": 0, "medium": 1, "low": 2}
    results.sort(key=lambda x: order.get(x["importance"], 3))
    return results
