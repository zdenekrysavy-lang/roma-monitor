"""Sběr kandidátských článků z více zdrojů + deduplikace."""
import re
import json
import html
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


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean_snippet(text: str, limit: int = 300) -> str:
    """Odstraní HTML z úryvku.

    Google News cpe do summary celý <a href="…base64…"> odkaz, který se pak
    v úryvku opakuje – balast, který jen nafukuje feed a agentovi nic neříká.
    """
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()[:limit]


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
                "snippet":   _clean_snippet(e.get("summary", "")),
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
            "snippet":   _clean_snippet(e.get("summary", "")),
            "published": e.get("published", ""),
            "lang":      lang,
        })
    return items


# Titulky přehledových/rubrikových stránek – nejsou to články, jen rozcestníky.
_AGG_PATTERNS = re.compile(
    r"veškeré informace o tématu|archiv článků|přehled nejnovějších událostí"
    r"|informace o osobách jménem|kalendárium|^téma\s|^aktuality\b|^akce\s*-",
    re.I)

# Fotogalerie a videoprohlížeče k článkům. Deník.cz je znovu protlačuje do
# Google News s ČERSTVÝM datem, i když obsah je letitý – ověřeno 8/2026:
# „Galerie: VIDEO: Rasismus … Zlínský Jawo“ hlásilo Google News jako 21 h
# staré, ale datePublished na denik.cz byl 28. 6. 2022. Datové okno je proti
# tomu bezmocné, protože filtruje podle data od Googlu. Galerie je navíc jen
# druhotný pohled na článek – když je článek čerstvý, projde i samostatně.
_GALLERY_RE = re.compile(
    r"^(galerie|fotogalerie|videogalerie|obrazem|video dne)\s*:", re.I)


def _strip_source_suffix(title: str) -> str:
    """„Titulek článku - Deník N" → „Titulek článku".

    Google News lepí za titulek jméno zdroje. Bez odstranění projde tentýž
    článek dvakrát, když ho převezme jiný web (syndikace).
    """
    return title.rsplit(" - ", 1)[0].strip() if " - " in title else title.strip()


# Rubrikové předpony, které weby lepí před tentýž titulek („Galerie: …“).
_LABEL_RE = re.compile(
    r"^(galerie|diskuze|diskus[ei]|obrazem|video|foto|komentář|rozhovor|anketa"
    r"|živě|přímý přenos|studio n)\s*:\s*", re.I)


def _dedup_key(title: str) -> str:
    """Klíč pro porovnání titulků – bez zdroje i rubrikové předpony."""
    t = _strip_source_suffix(title)
    prev = None
    while t != prev:                      # „Galerie: OBRAZEM: …“
        prev = t
        t = _LABEL_RE.sub("", t).strip()
    return t.lower()[:120]


def _is_aggregation_page(title: str) -> bool:
    """Pozná rozcestník typu „Romové - Deník N" (stránka tématu, ne článek)."""
    if _AGG_PATTERNS.search(title):
        return True
    # Délkovou heuristiku smí dostat jen Google News (lepí za titulek zdroj).
    # Přímo z RSS chodí i legitimní krátké titulky („Appleby Horse Fair").
    if " - " not in title:
        return False
    return len(_strip_source_suffix(title)) < 26


# ── Rozbalení adres Google News ─────────────────────────────────────
# RSS vrací jen wrapper news.google.com/rss/articles/CBMi… Ten se z EU nedá
# otevřít (Google přesměruje na souhlasovou zeď) a agent tak dostane odkaz,
# který mu je k ničemu. Cookie SOCS zeď obejde a endpoint batchexecute vrátí
# skutečnou adresu článku. Ověřeno 8/2026.
_GN_SOCS = "CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg"
_SG_RE = re.compile(r'data-n-a-sg="([^"]+)"')
_TS_RE = re.compile(r'data-n-a-ts="([^"]+)"')
_RES_RE = re.compile(r'\[\\"garturlres\\",\\"(.*?)\\"')


def _gn_session():
    s = requests.Session()
    s.headers.update(GN_UA)
    s.cookies.set("SOCS", _GN_SOCS, domain=".google.com")
    return s


def _resolve_one(gurl: str, s) -> str:
    """Vrátí skutečnou adresu článku, nebo prázdný řetězec při neúspěchu."""
    try:
        art = gurl.split("/articles/")[1].split("?")[0]
    except IndexError:
        return ""
    try:
        r = s.get(f"https://news.google.com/rss/articles/{art}", timeout=25)
        sg, ts = _SG_RE.search(r.text), _TS_RE.search(r.text)
        if not (sg and ts):
            return ""
        inner = ["garturlreq",
                 [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1,
                   None, None, None, None, None, 0, 1],
                  "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
                 art, int(ts.group(1)), sg.group(1)]
        rr = s.post("https://news.google.com/_/DotsSplashUi/data/batchexecute",
                    data={"f.req": json.dumps([[["Fbv4je", json.dumps(inner),
                                                 None, "generic"]]])},
                    headers={"Content-Type":
                             "application/x-www-form-urlencoded;charset=UTF-8"},
                    timeout=25)
        if rr.status_code != 200:
            return ""
        m = _RES_RE.search(rr.text)
        return _unescape_gn_url(m.group(1)) if m else ""
    except Exception:
        return ""


def _unescape_gn_url(u: str) -> str:
    """Odpaří dvojité JSON escapování (\u003d -> =, \u0026 -> &)."""
    u = u.replace("\\\\", "\\")
    try:
        u = u.encode("utf-8").decode("unicode_escape")
    except Exception:
        pass
    return u.split("\\")[0].strip()


def resolve_google_urls(items: list) -> dict:
    """Přepíše wrappery Google News na skutečné adresy. Vrací statistiku.

    Kdo se rozbalit nedá, zůstane s původní adresou – přijít o položku by
    bylo horší než dát agentovi wrapper.
    """
    if not getattr(config, "RESOLVE_GN_URLS", True):
        return {"tried": 0, "ok": 0}
    targets = [it for it in items if "news.google.com" in it.get("url", "")]
    if not targets:
        return {"tried": 0, "ok": 0}
    s = _gn_session()
    ok = 0
    for i, it in enumerate(targets[:config.GN_RESOLVE_MAX]):
        if i:
            time.sleep(config.GN_RESOLVE_PAUSE)
        real = _resolve_one(it["url"], s)
        if real:
            it["url"] = real
            ok += 1
    tried = min(len(targets), config.GN_RESOLVE_MAX)
    print(f"  Rozbaleno adres Google News: {ok}/{tried}")
    return {"tried": tried, "ok": ok}


def drop_excluded(items: list) -> list:
    """Zahodí nechtěné zdroje a přehledové stránky.

    EXCLUDE_SOURCES: běžná položka = hledá se jako podřetězec ve zdroji i URL;
    položka s „=" na začátku = musí se rovnat celému názvu zdroje (kvůli
    agregátorům typu „Seznam", které přebírají cizí obsah včetně článků ROMEA,
    ale nesmí padnout i „Seznam Zprávy" s vlastní žurnalistikou).
    """
    raw = getattr(config, "EXCLUDE_SOURCES", [])
    exact = {s[1:].strip().lower() for s in raw if s.startswith("=")}
    subs = [s.lower() for s in raw if not s.startswith("=")]
    out = []
    for it in items:
        title = it.get("title", "")
        if not title.strip() or _is_aggregation_page(title):
            continue
        if _GALLERY_RE.match(title.strip()):
            continue
        # Někdy je odkaz rovnou na prohlížeč fotek (…/galerie-…?photo=6).
        url = it.get("url", "")
        if "/galerie-" in url or "photo=" in url:
            continue
        src = (it.get("source", "") or "").strip().lower()
        if src in exact:
            continue
        if subs:
            hay = f"{src} {it.get('url', '')}".lower()
            if any(b in hay for b in subs):
                continue
        out.append(it)
    return out


def dedupe(items: list) -> list:
    seen, out = set(), []
    for it in items:
        if not it.get("url"):
            continue
        key = _norm_url(it["url"])
        # Bez jména zdroje a rubrikové předpony – jinak projde tentýž článek
        # znovu („… - ČT art" vs „… - Seznam", „Galerie: X" vs „X").
        tkey = _dedup_key(it.get("title", "") or "")
        if key in seen or tkey in seen:
            continue
        seen.add(key)
        if tkey:
            seen.add(tkey)
        out.append(it)
    return out


def fetch_watch_sites() -> list:
    """Pro weby bez feedu: dotaz přes Google News omezený na doménu.

    U romských webů (profil „world") stačí `site:doména` ve správném jazyce –
    každý jejich článek je na téma. Úřady v profilu „cz" publikují všechno
    možné, proto se k dotazu přidají WATCH_SITE_TERMS.
    """
    items = []
    terms = getattr(config, "WATCH_SITE_TERMS", "").strip()
    for domain, hl, gl in config.WATCH_SITES:
        time.sleep(config.GN_PAUSE)       # watch jde také přes Google News → rozestupy
        q = f"site:{domain} ({terms})" if terms else f"site:{domain}"
        feed = _parse_gnews(_google_news_url(q, hl, gl))
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
                "snippet":   _clean_snippet(e.get("summary", "")),
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
    if getattr(config, "GDELT_ENABLED", True):
        gd, gd_status, gd_note = fetch_gdelt()
    else:
        gd, gd_status, gd_note = [], "disabled", "GDELT je v tomto profilu vypnutý"
    feed_items = []
    for f, flang in config.RSS_FEEDS:
        feed_items += fetch_feed(f, flang)
    watch = fetch_watch_sites()

    # Pořadí rozhoduje: dedup nechává PRVNÍ výskyt a ořez na MAX_CANDIDATES
    # usekává od konce. Nejdřív tedy vlastní romské feedy a sledované weby
    # (nejvyšší signál, přímé odkazy), pak Google News, nakonec GDELT
    # (největší objem, nejvíc šumu). Dřív to bylo obráceně a při ořezu padaly
    # jako první právě feedy.
    merged = drop_excluded(feed_items + watch + gn + gd)
    items = dedupe(merged)[:config.MAX_CANDIDATES]

    if _GN["failures"] == 0:
        gn_status = "ok"
    elif _GN["failures"] < _GN["queries"]:
        gn_status = "partial"          # část dotazů spadla (typicky 429)
    else:
        gn_status = "blocked"          # všechny dotazy spadly – Google blokuje IP

    global LAST_STATS
    LAST_STATS = {
        "profile": getattr(config, "MONITOR_PROFILE", "world"),
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
