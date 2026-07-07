"""Režim B – jen NASBÍRÁ kandidáty a uloží je jako veřejný feed (JSON + Markdown).

Žádná AI, žádný Anthropic API klíč. Třídění, známkování a česká shrnutí
pak dělá TVŮJ agent v ChatGPT, který si tenhle feed stáhne z veřejné URL.

Spuštění:  python gather.py
"""
import os
import json
import datetime as dt

import config
import fetch

OUT_DIR = os.getenv("FEED_DIR", "feed")


def load_seen() -> dict:
    """Načte mapu {normalizovaná URL: ISO čas prvního spatření}."""
    try:
        with open(config.SEEN_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_seen(seen: dict) -> None:
    os.makedirs(os.path.dirname(config.SEEN_PATH), exist_ok=True)
    with open(config.SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=0)


def filter_unseen(items: list, seen: dict) -> tuple:
    """Vyřadí položky viděné v minulých bězích; nové do `seen` zapíše.

    Zároveň pročistí záznamy starší než SEEN_TTL_DAYS, ať soubor neroste
    donekonečna. Vrací (nové položky, počet přeskočených).
    """
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=config.SEEN_TTL_DAYS)
    pruned = {}
    for url, first in seen.items():
        try:
            if dt.datetime.fromisoformat(first) >= cutoff:
                pruned[url] = first
        except ValueError:
            pass  # nečitelné datum – záznam zahodíme
    seen.clear()
    seen.update(pruned)

    fresh, skipped = [], 0
    for it in items:
        key = fetch._norm_url(it.get("url", ""))
        if key in seen:
            skipped += 1
            continue
        seen[key] = now.isoformat(timespec="seconds")
        fresh.append(it)
    return fresh, skipped


def write_feed(items: list, stats: dict) -> tuple:
    os.makedirs(OUT_DIR, exist_ok=True)
    payload = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "count": len(items),
        "sources": stats,          # rozpad po zdrojích + stav GDELT (ok/rate_limited/error)
        "candidates": items,
    }

    json_path = os.path.join(OUT_DIR, "candidates.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Lidsky čitelná verze (kdyby ses chtěl podívat sám).
    md_path = os.path.join(OUT_DIR, "candidates.md")
    gd = stats.get("gdelt_status", "?")
    lines = [f"# Kandidáti — {payload['generated_utc']} ({len(items)} položek)", ""]
    lines.append(f"_Zdroje: Google News {stats.get('google_news', 0)} · "
                 f"GDELT {stats.get('gdelt', 0)} ({gd}) · "
                 f"feedy {stats.get('feeds', 0)} · watch {stats.get('watch', 0)}_")
    lines.append("")
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
    stats = fetch.LAST_STATS

    # Perzistentní dedup mezi běhy: co už bylo v některém minulém feedu,
    # znovu neposíláme (řídké feedy mají delší okno a překrývaly by se).
    seen = load_seen()
    items, skipped = filter_unseen(items, seen)
    stats["skipped_seen"] = skipped

    print(f"Kandidátů: {len(items)} nových ({skipped} už viděno dřív)  "
          f"(Google News {stats.get('google_news', 0)}, "
          f"GDELT {stats.get('gdelt', 0)}/{stats.get('gdelt_status', '?')}, "
          f"feedy {stats.get('feeds', 0)}, watch {stats.get('watch', 0)})")
    jp, mp = write_feed(items, stats)
    # seen ukládáme až PO úspěšném zápisu feedu – kdyby zápis spadl,
    # články nesmí zůstat označené jako „viděné", aniž byly publikovány.
    save_seen(seen)
    print(f"Uloženo: {jp} a {mp}")


if __name__ == "__main__":
    run()
