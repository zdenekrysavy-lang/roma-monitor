"""Režim B – jen NASBÍRÁ kandidáty a uloží je jako veřejný feed (JSON + Markdown).

Žádná AI, žádný Anthropic API klíč. Třídění, známkování a česká shrnutí
pak dělá TVŮJ agent v ChatGPT, který si tenhle feed stáhne z veřejné URL.

Spuštění:  python gather.py
"""
import os
import json
import datetime as dt

import fetch

OUT_DIR = os.getenv("FEED_DIR", "feed")


def write_feed(items: list) -> tuple:
    os.makedirs(OUT_DIR, exist_ok=True)
    payload = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "count": len(items),
        "candidates": items,
    }

    json_path = os.path.join(OUT_DIR, "candidates.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Lidsky čitelná verze (kdyby ses chtěl podívat sám).
    md_path = os.path.join(OUT_DIR, "candidates.md")
    lines = [f"# Kandidáti — {payload['generated_utc']} ({len(items)} položek)", ""]
    for i, it in enumerate(items, 1):
        lines.append(f"{i}. **{it.get('title','')}** — {it.get('source','')} [{it.get('lang','')}]")
        lines.append(f"   {it.get('url','')}")
        if it.get("snippet"):
            lines.append(f"   {it['snippet'][:200]}")
        lines.append("")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return json_path, md_path


def run() -> None:
    print("Sbírám kandidáty (bez AI)…")
    items = fetch.collect()
    print(f"Kandidátů: {len(items)}")
    jp, mp = write_feed(items)
    print(f"Uloženo: {jp} a {mp}")


if __name__ == "__main__":
    run()
