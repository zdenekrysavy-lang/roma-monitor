"""Sběr kandidátských článků z více zdrojů + deduplikace."""
import time
import random
import urllib.parse

import requests
import feedparser

import config

UA = {"User-Agent": "Mozilla/5.0 (compatible; RomaNewsMonitor/1.0)"}

# Pro Google News používáme prohlížečový UA – bot UA dostává 429 ochotněji.
GN_UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36")}

# Počítadlo selhání Google News v rámci jednoho collect() – plní LAST_STATS.
_GN = {"queries": 0, "failures": 0}


def _parse_gnews(url: str):
    """Stáhne Google News RSS s explicitní kontrolou HTTP statusu.

    feedparser sám HTTP chyby tiše spolkne (vrátí 0 položek), takže by
    rate-limit Googlu vypadal jako „žádné zprávy". Tady 429/5xx logujeme,
    zkusíme znovu s prodlevou, a selhání počítáme do _GN/LAST_STATS.
    Vrací feedparser objekt, nebo None při selhání.
    """
    _GN["queries"] += 1
    for attempt in range(config.GN_RETRIES):
        try:
            r = requests.get(url, headers=GN_UA, timeout=30)
        except Exception as ex:
            print(f"  Google News chyba: {ex}")
            _GN["failures"] += 1
            return None
        if r.status_code == 200:
            return feedparser.parse(r.content)
        if r.status_code in (429, 503) and attempt < config.GN_RETRIES - 1:
            wait = 15 * (attempt + 1) + random.uniform(0, 5)
            print(f"  Google News HTTP {r.status_code}, pokus {attempt + 1}/"
                  f"{config.GN_RETRIES}, čekám {wait:.0f} s…")
            time.sleep(wait)
            continue
        print(f"  Google News HTTP {r.status_code}: {url[:90]}")
        _GN["failures"] += 1
        return None
    _GN["failures"] += 1
    return None


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
    for i, (query, hl, gl) in enumerate(config.GOOGLE_NEWS_QUERIES):
        if i:
            time.sleep(config.GN_PAUSE)   # rozestup – série 25 dotazů bez pauz = 429
        feed = _parse_gnews(_google_news_url(query, hl, gl))
        if feed is None:
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
    """Vrací (items, status, note). status: "ok" | "rate_limited" | "error".

    status i note (útržek toho, co GDELT reálně vrátil) putují do feedu, aby
    ChatGPT agent i my viděli, PROČ se GDELT nenačetl – ne jen že se nenačetl.
    Retryujeme VŠECHNY přechodné chyby: síť, 429, 5xx i ne-JSON odpověď
    (GDELT je free služba a při přetížení vrací HTML/text místo JSON).
    """
    params = {
        "query": config.GDELT_QUERY,
        "mode": "ArtList",
        "format": "json",
        "timespan": config.GDELT_TIMESPAN,
        "maxrecords": str(config.GDELT_MAX),
        "sort": "datedesc",
    }
    attempts = max(1, config.GDELT_RETRIES)
    last_note = "neznámá chyba"
    for attempt in range(attempts):
        try:
            r = requests.get("https://api.gdeltproject.org/api/v2/doc/doc",
                             params=params, headers=UA, timeout=30)
        except Exception as ex:
            last_note = f"spojení selhalo: {ex}"[:200]
        else:
            if r.status_code == 429:
                last_note = "HTTP 429 (rate-limit)"
            elif r.status_code != 200:
                last_note = f"HTTP {r.status_code}: {r.text.strip()[:150]}"
            else:
                try:
                    data = r.json()
                except Exception:
                    # Ne-JSON = GDELT je přetížený nebo si stěžuje na dotaz.
                    # Zalogujeme TĚLO, ať víme, co se děje (dřív jsme byli slepí).
                    last_note = f"ne-JSON odpověď: {r.text.strip()[:180]}"
                else:
                    items = [{
                        "title":     a.get("title", ""),
                        "url":       a.get("url", ""),
                        "source":    a.get("domain", ""),
                        "snippet":   "",
                        "published": a.get("seendate", ""),
                        "lang":      a.get("language", ""),
                    } for a in data.get("articles", [])]
                    note = "" if items else "GDELT vrátil 0 článků (prázdná odpověď)"
                    return items, "ok", note

        if attempt < attempts - 1:
            wait = config.GDELT_BACKOFF * (attempt + 1) + random.uniform(0, 3)
            print(f"  GDELT selhalo ({last_note[:90]}), pokus {attempt + 1}/"
                  f"{attempts}, čekám {wait:.0f} s…")
            time.sleep(wait)

    print(f"  GDELT se nenačetl ani po {attempts} pokusech: {last_note}")
    status = "rate_limited" if "429" in last_note else "error"
    return [], status, last_note


def fetch_feed(url: str, lang: str = "") -> list:
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
            "lang":      lang,
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
        time.sleep(config.GN_PAUSE)       # watch jde také přes Google News → rozestupy
        feed = _parse_gnews(_google_news_url(f"site:{domain}", hl, gl))
        if feed is None:
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
    _GN["queries"] = _GN["failures"] = 0

    gn = fetch_google_news()
    gd, gd_status, gd_note = fetch_gdelt()
    feed_items = []
    for f, flang in config.RSS_FEEDS:
        feed_items += fetch_feed(f, flang)
    watch = fetch_watch_sites()

    merged = gn + gd + feed_items + watch
    items = dedupe(merged)[:config.MAX_CANDIDATES]

    if _GN["failures"] == 0:
        gn_status = "ok"
    elif _GN["failures"] < _GN["queries"]:
        gn_status = "partial"          # část dotazů spadla (typicky 429)
    else:
        gn_status = "blocked"          # všechny dotazy spadly – Google blokuje IP

    global LAST_STATS
    LAST_STATS = {
        "google_news": len(gn),
        "google_news_status": gn_status,   # "ok" | "partial" | "blocked"
        "gdelt": len(gd),
        "gdelt_status": gd_status,         # "ok" | "rate_limited" | "error"
        "gdelt_note": gd_note,             # diagnostika: co GDELT reálně vrátil
        "feeds": len(feed_items),
        "watch": len(watch),
        "before_dedup": len(merged),
        "total": len(items),
    }
    return items
