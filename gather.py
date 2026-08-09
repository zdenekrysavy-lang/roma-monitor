"""Režim B – jen NASBÍRÁ kandidáty a uloží je jako veřejný feed (JSON + Markdown).

Žádná AI, žádný Anthropic API klíč. Třídění, známkování a česká shrnutí
pak dělá TVŮJ agent v ChatGPT, který si tenhle feed stáhne z veřejné URL.

Spuštění:  python gather.py
"""
import os
import json
import datetime as dt
from html import escape as esc

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


def load_archive() -> list:
    try:
        with open(config.ARCHIVE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def update_archive(new_items: list) -> list:
    """Přidá nové položky do archivu a vyhodí starší než ARCHIVE_DAYS.

    Archiv je záchytná síť: feed nese jen novinky, a když je agent nepřečte,
    už se nevrátí. Tady zůstanou dohledatelné po celé okno.
    """
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=config.ARCHIVE_DAYS)
    stamp = now.isoformat(timespec="seconds")

    kept = []
    for rec in load_archive():
        try:
            if dt.datetime.fromisoformat(rec.get("collected_utc", "")) >= cutoff:
                kept.append(rec)
        except ValueError:
            pass

    known = {fetch._norm_url(r.get("url", "")) for r in kept}
    for it in new_items:
        if fetch._norm_url(it.get("url", "")) in known:
            continue
        kept.append({**it, "collected_utc": stamp})

    kept.sort(key=lambda r: r.get("collected_utc", ""), reverse=True)
    os.makedirs(os.path.dirname(config.ARCHIVE_PATH), exist_ok=True)
    with open(config.ARCHIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=0)
    return kept


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

    html_path = write_html(payload)
    return json_path, md_path, html_path


def write_html(payload: dict) -> str:
    """Feed jako obyčejná HTML stránka (feed/index.html).

    ChatGPT agent si přes prohlížení neporadí s odkazem na surový .json soubor
    (vrací 401/403), ale běžnou webovou stránku přečte bez problémů. Publikuje
    se přes GitHub Pages — viz chatgpt_task.md.
    """
    st = payload["sources"]
    rows = []
    for i, it in enumerate(payload["candidates"], 1):
        title = esc(it.get("title", ""))
        url = esc(it.get("url", ""))
        meta = " · ".join(x for x in [esc(it.get("source", "")),
                                      esc((it.get("lang", "") or "").upper()),
                                      esc(it.get("published", ""))] if x)
        snippet = esc(it.get("snippet", ""))
        rows.append(
            f'<article>\n<h2>{i}. <a href="{url}">{title}</a></h2>\n'
            f'<p class="meta">{meta}</p>\n'
            + (f"<p>{snippet}</p>\n" if snippet else "")
            + f'<p class="url">{url}</p>\n</article>'
        )
    body = "\n".join(rows) or "<p>Za sledované období nepřišly žádné nové zprávy.</p>"

    doc = f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kandidáti – Romové ve světě ({payload['count']})</title>
<style>
 body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
      max-width:52rem;margin:0 auto;padding:1.5rem;line-height:1.5;color:#1a1a1a}}
 h1{{font-size:1.4rem;margin:0 0 .3rem}}
 h2{{font-size:1rem;margin:0 0 .2rem;font-weight:600}}
 article{{border-top:1px solid #e5e5e5;padding:.9rem 0}}
 .meta{{font-size:.8rem;color:#666;margin:.1rem 0}}
 .url{{font-size:.75rem;color:#888;word-break:break-all;margin:.2rem 0 0}}
 .head{{font-size:.85rem;color:#555;margin-bottom:1rem}}
 a{{color:#0b5cad}}
</style>
</head>
<body>
<h1>Kandidátské zprávy o Romech ve světě</h1>
<p class="head">
 Vygenerováno (UTC): <strong>{esc(payload['generated_utc'])}</strong><br>
 Počet nových zpráv: <strong>{payload['count']}</strong><br>
 Zdroje tohoto běhu: Google News {st.get('google_news', 0)}
 ({esc(st.get('google_news_status', '?'))}) ·
 GDELT {st.get('gdelt', 0)} ({esc(st.get('gdelt_status', '?'))}) ·
 feedy {st.get('feeds', 0)} · weby {st.get('watch', 0)}
 {('<br>Poznámka ke GDELT: ' + esc(st['gdelt_note'])) if st.get('gdelt_note') else ''}
 <br><a href="archiv.html"><strong>Archiv posledních {config.ARCHIVE_DAYS} dní →</strong></a>
 (vše, i to, co už agent dostal)
</p>
{body}
</body>
</html>
"""
    path = os.path.join(OUT_DIR, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return path


def write_archive_html(records: list) -> str:
    """Záchytná stránka „posledních N dní" – VŠECHNO, bez ohledu na seen."""
    by_day = {}
    for r in records:
        by_day.setdefault(r.get("collected_utc", "")[:10], []).append(r)

    parts = []
    for day in sorted(by_day, reverse=True):
        parts.append(f'<h2 class="day">{esc(day)} '
                     f'<span class="cnt">({len(by_day[day])})</span></h2>')
        for r in by_day[day]:
            url = esc(r.get("url", ""))
            meta = " · ".join(x for x in [esc(r.get("source", "")),
                                          esc((r.get("lang", "") or "").upper())] if x)
            parts.append(
                f'<article><h3><a href="{url}">{esc(r.get("title", ""))}</a></h3>'
                f'<p class="meta">{meta}</p></article>')
    body = "\n".join(parts) or "<p>Archiv je zatím prázdný.</p>"

    doc = f"""<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Archiv {config.ARCHIVE_DAYS} dní ({len(records)})</title>
<style>
 body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
      max-width:52rem;margin:0 auto;padding:1.5rem;line-height:1.5;color:#1a1a1a}}
 h1{{font-size:1.4rem;margin:0 0 .3rem}}
 h2.day{{font-size:1rem;margin:1.6rem 0 .3rem;padding-bottom:.2rem;
        border-bottom:2px solid #0b5cad;color:#0b5cad}}
 .cnt{{color:#888;font-weight:400}}
 h3{{font-size:.95rem;margin:0;font-weight:600}}
 article{{border-top:1px solid #eee;padding:.5rem 0}}
 .meta{{font-size:.78rem;color:#666;margin:.1rem 0 0}}
 .head{{font-size:.85rem;color:#555;margin-bottom:1rem}}
 a{{color:#0b5cad}}
</style>
</head>
<body>
<h1>Archiv – posledních {config.ARCHIVE_DAYS} dní</h1>
<p class="head">
 Všechny nasbírané zprávy bez ohledu na to, zda už byly odeslány agentovi.
 Slouží ke zpětnému dohledání, kdyby některý přehled nedorazil.<br>
 Celkem: <strong>{len(records)}</strong> ·
 <a href="./">zpět na aktuální feed</a>
</p>
{body}
</body>
</html>
"""
    path = os.path.join(OUT_DIR, "archiv.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return path


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
    jp, mp, hp = write_feed(items, stats)
    # seen ukládáme až PO úspěšném zápisu feedu – kdyby zápis spadl,
    # články nesmí zůstat označené jako „viděné", aniž byly publikovány.
    save_seen(seen)
    archive = update_archive(items)
    ap = write_archive_html(archive)
    print(f"Uloženo: {jp}, {mp} a {hp}")
    print(f"Archiv ({config.ARCHIVE_DAYS} dní): {len(archive)} položek → {ap}")


if __name__ == "__main__":
    run()
