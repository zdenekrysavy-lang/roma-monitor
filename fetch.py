"""Sběr kandidátských článků z více zdrojů + deduplikace."""
import time
import random
import urllib.parse

import requests
import feedparser

import config

UA = {"User-Agent": "Mozilla/5.0 (compatible; RomaNewsMonitor/1.0)"}


def _google_news_url(query: str, hl: str, gl: str) -> str:
    when = getattr(config, "GOOGLE_NEWS_WHEN", "").strip()
    if when:
        query = f"{query} when:{when}"   # jen čerstvé články, ať projdou oknem
    q = urllib.parse.quote(query)
    return (f"https://news.google.com/rss/search?q={q}"
            f"&hl={hl}&gl={gl}&ceid={gl}:{hl}")


def _within_window(published_parsed, hours: int) -> bool:
    if not published_parsed:
        return True  # neznámé datum necháme projít, posoudí Claude
    ts = time.mktime(published_parsed)
    return (time.time() - ts) <= hours * 3600


def _norm_url(url: str) -> str:
    """Odstraní query/fragment (utm apod.) pro spolehlivější dedup."""
    p = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, "", ""))


def _entry_source(entry) -> str:
    try:
        src = entry.get("source")
        if isinstance(src, dict):
            return src.get("title", "")
        return str(src) if src else ""
    except Exception:
        return ""


def fetch_google_news() -> list:
    items = []
    for query, hl, gl in config.GOOGLE_NEWS_QUERIES:
        try:
            feed = feedparser.parse(_google_news_url(query, hl, gl))
        except Exception as ex:
            print(f"  Google News chyba ({hl}): {ex}")
            continue
        taken = 0
        for e in feed.entries[:config.MAX_PER_FEED]:
            if taken >= config.MAX_PER_QUERY:
                break  # strop na dotaz – ať jeden jazyk nezaplaví feed
            if not _within_window(getattr(e, "published_parsed", None), config.LOOKBACK_HOURS):
                continue
            items.append({
                "title":     e.get("title", ""),
                "url":       e.get("link", ""),
                "source":    _entry_source(e),
                "snippet":   (e.get("summary", "") or "")[:500],
                "published": e.get("published", ""),
                "lang":      hl,
            })
            taken += 1
    return items


def fetch_gdelt() -> tuple:
    """Vrací (items, status). status: "ok" | "rate_limited" | "error".

    Status pak putuje do feedu, aby ChatGPT agent věděl (a mohl uživateli říct),
    jestli se globální GDELT vrstva tentokrát načetla, nebo ji rate-limit shodil.
    """
    params = {
        "query": config.GDELT_QUERY,
        "mode": "ArtList",
        "format": "json",
        "timespan": config.GDELT_TIMESPAN,
        "maxrecords": str(config.GDELT_MAX),
        "sort": "datedesc",
    }
    # GDELT povoluje ~1 dotaz / 5 s; na sdílených GitHub IP často 429.
    # Víc pokusů s narůstající prodlevou (8, 16, 24…) + náhodný rozptyl,
    # ať se netrefíme do stejného okna jako jiné joby. Když ani tak neprojde,
    # pokračujeme bez něj (GDELT je bonus, ne kritický zdroj).
    attempts = max(1, config.GDELT_RETRIES)
    data = None
    for attempt in range(attempts):
        try:
            r = requests.get("https://api.gdeltproject.org/api/v2/doc/doc",
                             params=params, headers=UA, timeout=30)
        except Exception as ex:
            print(f"  GDELT chyba: {ex}")
            return [], "error"
        if r.status_code == 429:
            if attempt < attempts - 1:
                wait = config.GDELT_BACKOFF * (attempt + 1) + random.uniform(0, 3)
                print(f"  GDELT rate-limit (429), pokus {attempt + 1}/{attempts}, "
                      f"čekám {wait:.0f} s…")
                time.sleep(wait)
                continue
            print(f"  GDELT stále 429 i po {attempts} pokusech, pokračuji bez něj")
            return [], "rate_limited"
        try:
            data = r.json()
        except Exception as ex:
            print(f"  GDELT chyba (ne-JSON odpověď): {ex}")
            return [], "error"
        break
    if data is None:
        return [], "error"
    items = []
    for a in data.get("articles", []):
        items.append({
            "title":     a.get("title", ""),
            "url":       a.get("url", ""),
            "source":    a.get("domain", ""),
            "snippet":   "",
            "published": a.get("seendate", ""),
            "lang":      a.get("language", ""),
        })
    return items, "ok"


def fetch_feed(url: str) -> list:
    items = []
    try:
        feed = feedparser.parse(url)
    except Exception as ex:
        print(f"  Feed chyba ({url}): {ex}")
        return items
    for e in feed.entries[:config.MAX_PER_FEED]:
        # Delší okno než u Google News/GDELT: romské feedy publikují řídce
        # a krátké okno by je míjelo. Duplicity mezi běhy řeší seen.json.
        if not _within_window(getattr(e, "published_parsed", None), config.FEED_LOOKBACK_HOURS):
            continue
        items.append({
            "title":     e.get("title", ""),
            "url":       e.get("link", ""),
            "source":    _entry_source(e) or url,
            "snippet":   (e.get("summary", "") or "")[:500],
            "published": e.get("published", ""),
            "lang":      "",
        })
    return items


def dedupe(items: list) -> list:
    seen, out = set(), []
    for it in items:
        if not it.get("url"):
            continue
        key = _norm_url(it["url"])
        tkey = (it.get("title", "") or "").strip().lower()[:120]
        if key in seen or tkey in seen:
            continue
        seen.add(key)
        if tkey:
            seen.add(tkey)
        out.append(it)
    return out


def fetch_watch_sites() -> list:
    """Pro weby bez feedu: dotaz přes Google News omezený na doménu.

    Web je ryze romský, takže nepřidáváme klíčová slova – jen `site:doména`
    ve správném jazyce. Bez správného locale by se slovenský/maďarský obsah
    nenašel anglickým dotazem.
    """
    items = []
    for domain, hl, gl in config.WATCH_SITES:
        url = _google_news_url(f"site:{domain}", hl, gl)
        try:
            feed = feedparser.parse(url)
        except Exception as ex:
            print(f"  Watch-site chyba ({domain}): {ex}")
            continue
        taken = 0
        for e in feed.entries[:config.MAX_PER_FEED]:
            if taken >= config.MAX_PER_QUERY:
                break
            # Stejně jako u RSS feedů: malé weby publikují řídce → delší okno.
            if not _within_window(getattr(e, "published_parsed", None), config.FEED_LOOKBACK_HOURS):
                continue
            items.append({
                "title":     e.get("title", ""),
                "url":       e.get("link", ""),
                "source":    _entry_source(e) or domain,
                "snippet":   (e.get("summary", "") or "")[:500],
                "published": e.get("published", ""),
                "lang":      hl,
            })
            taken += 1
    return items


# Statistiky posledního běhu collect() – aby je gather.py mohl vložit do feedu
# a ChatGPT agent věděl, co se načetlo (hlavně zda naběhl globální GDELT).
LAST_STATS = {}


def collect() -> list:
    gn = fetch_google_news()
    gd, gd_status = fetch_gdelt()
    feed_items = []
    for f in config.RSS_FEEDS:
        feed_items += fetch_feed(f)
    watch = fetch_watch_sites()

    merged = gn + gd + feed_items + watch
    items = dedupe(merged)[:config.MAX_CANDIDATES]

    global LAST_STATS
    LAST_STATS = {
        "google_news": len(gn),
        "gdelt": len(gd),
        "gdelt_status": gd_status,     # "ok" | "rate_limited" | "error"
        "feeds": len(feed_items),
        "watch": len(watch),
        "before_dedup": len(merged),
        "total": len(items),
    }
    return items
