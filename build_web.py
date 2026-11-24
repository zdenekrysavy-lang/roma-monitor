"""Generátor webu „Romové ve světě“ z výběru AI agenta.

Vstup:  web/data/AAAA-MM-DD.json – jeden soubor za každý běh agenta.
        Agent do něj zapisuje TY SAMÉ zprávy, které poslal e-mailem
        „Romové ve světě – přehled“. Formát:

        {
          "date": "2026-11-08",            # den běhu agenta
          "items": [{
            "url":        "https://…",     # přímá adresa článku (povinné)
            "source":     "Le Monde",      # název média
            "country":    "FR",            # ISO kód země děje (2 písmena)
            "lang":       "fr",            # jazyk článku
            "published":  "2026-11-08",    # OVĚŘENÉ datum vydání
            "importance": "high|medium|low",
            "category":   {"cs": "Bydlení", "en": "Housing"},
            "original_title": "…",         # titulek v originále
            "title":      {"cs": "…", "en": "…"},   # povinné aspoň cs
            "summary":    {"cs": "…", "en": "…"},   # vlastní slova, 1–2 věty
            "image":      "https://…"      # nepovinné – jinak se dohledá
          }]
        }

Výstup: web/index.html (cs), web/en/index.html (en), archiv a stránky dnů.

Fotky: když agent `image` nevyplní, skript vytáhne og:image ze stránky
článku. Obrázek se NEKOPÍRUJE, jen se na něj odkazuje (zůstává na serveru
vydavatele). Výsledek se pamatuje v web/cache/images.json, ať se stránky
nestahují při každém sestavení znovu.

Spuštění:  python build_web.py            # s dohledáním fotek
           python build_web.py --offline  # bez síťových požadavků
"""
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT  = Path(__file__).resolve().parent
WEB   = ROOT / "web"
DATA  = WEB / "data"
CACHE = WEB / "cache" / "images.json"

HOME_DAYS = 7                 # kolik posledních běhů ukazuje titulní stránka
ROBOTS    = "noindex, nofollow, noarchive"   # do ostrého spuštění
IMG_TRIES = 3                 # kolikrát zkusit dohledat fotku, než to vzdáme
IMG_RETRY_HOURS = 20          # pauza mezi pokusy

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

IMPORTANCE_ORDER = {"high": 0, "medium": 1, "low": 2}

# ---------------------------------------------------------------- texty
T = {
    "cs": {
        "site":      "Romové ve světě",
        "tagline":   "Denní výběr zpráv o Romech ze zahraničních médií",
        "latest":    "Aktuálně",
        "archive":   "Archiv",
        "high":      "Klíčové",
        "more":      "Celé znění na {d}",
        "items":     {1: "zpráva", 2: "zprávy", 5: "zpráv"},
        "day_title": "Výběr z {d}",
        "older":     "Starší výběry najdete v archivu",
        "empty":     "Zatím tu nejsou žádné zprávy.",
        "arch_head": "Archiv výběrů",
        "sample":    "Prototyp s ukázkovými daty – výběr ani texty nejsou finální.",
        "about":     ("Zprávy každé ráno vybírá AI agent z médií v patnácti "
                      "jazycích. Titulky a shrnutí jsou vlastní, fotografie "
                      "a plná znění patří vydavatelům a otevírají se na "
                      "jejich webech."),
        "switch":    "English",
    },
    "en": {
        "site":      "Roma in the World",
        "tagline":   "A daily selection of news about Roma from the international press",
        "latest":    "Latest",
        "archive":   "Archive",
        "high":      "Key story",
        "more":      "Read in full at {d}",
        "items":     {1: "story", 2: "stories", 5: "stories"},
        "day_title": "Selection of {d}",
        "older":     "Older selections are in the archive",
        "empty":     "No stories yet.",
        "arch_head": "Archive",
        "sample":    "Prototype with sample data – selection and texts are not final.",
        "about":     ("Every morning an AI agent selects these stories from "
                      "media in fifteen languages. Headlines and summaries are "
                      "our own; photos and full texts belong to the publishers "
                      "and open on their websites."),
        "switch":    "Česky",
    },
}

MONTHS_CS = ["ledna", "února", "března", "dubna", "května", "června",
             "července", "srpna", "září", "října", "listopadu", "prosince"]
DAYS_CS   = ["pondělí", "úterý", "středa", "čtvrtek", "pátek", "sobota", "neděle"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]
DAYS_EN   = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]

COUNTRIES = {
    "AL": ("Albánie", "Albania"),        "AT": ("Rakousko", "Austria"),
    "BA": ("Bosna a Hercegovina", "Bosnia and Herzegovina"),
    "BE": ("Belgie", "Belgium"),         "BG": ("Bulharsko", "Bulgaria"),
    "BR": ("Brazílie", "Brazil"),        "CA": ("Kanada", "Canada"),
    "CH": ("Švýcarsko", "Switzerland"),  "CZ": ("Česko", "Czechia"),
    "DE": ("Německo", "Germany"),        "DK": ("Dánsko", "Denmark"),
    "EE": ("Estonsko", "Estonia"),       "ES": ("Španělsko", "Spain"),
    "EU": ("Evropská unie", "European Union"),
    "FI": ("Finsko", "Finland"),         "FR": ("Francie", "France"),
    "GB": ("Spojené království", "United Kingdom"),
    "GR": ("Řecko", "Greece"),           "HR": ("Chorvatsko", "Croatia"),
    "HU": ("Maďarsko", "Hungary"),       "IE": ("Irsko", "Ireland"),
    "IT": ("Itálie", "Italy"),           "LT": ("Litva", "Lithuania"),
    "LV": ("Lotyšsko", "Latvia"),        "MD": ("Moldavsko", "Moldova"),
    "ME": ("Černá Hora", "Montenegro"),  "MK": ("Severní Makedonie", "North Macedonia"),
    "NL": ("Nizozemsko", "Netherlands"), "NO": ("Norsko", "Norway"),
    "PL": ("Polsko", "Poland"),          "PT": ("Portugalsko", "Portugal"),
    "RO": ("Rumunsko", "Romania"),       "RS": ("Srbsko", "Serbia"),
    "RU": ("Rusko", "Russia"),           "SE": ("Švédsko", "Sweden"),
    "SI": ("Slovinsko", "Slovenia"),     "SK": ("Slovensko", "Slovakia"),
    "TR": ("Turecko", "Turkey"),         "UA": ("Ukrajina", "Ukraine"),
    "US": ("USA", "United States"),      "XK": ("Kosovo", "Kosovo"),
    "INT": ("Mezinárodní", "International"),
}

# ---------------------------------------------------------------- pomocné
e = lambda s: html.escape(str(s or ""), quote=True)


def plural(lang: str, n: int) -> str:
    forms = T[lang]["items"]
    if lang == "cs":
        return forms[1] if n == 1 else forms[2] if 2 <= n <= 4 else forms[5]
    return forms[1] if n == 1 else forms[2]


def fmt_day(d: dt.date, lang: str, weekday=True) -> str:
    if lang == "cs":
        s = f"{d.day}. {MONTHS_CS[d.month - 1]} {d.year}"
        return f"{DAYS_CS[d.weekday()].capitalize()} {s}" if weekday else s
    s = f"{d.day} {MONTHS_EN[d.month - 1]} {d.year}"
    return f"{DAYS_EN[d.weekday()]}, {s}" if weekday else s


def fmt_short(d: dt.date, lang: str) -> str:
    # anglicky slovem – 08/11 by Američan četl jako 11. srpna
    return (f"{d.day}. {d.month}. {d.year}" if lang == "cs"
            else f"{d.day} {MONTHS_EN[d.month - 1][:3]} {d.year}")


def domain(url: str) -> str:
    h = urlparse(url).hostname or ""
    return h[4:] if h.startswith("www.") else h


def is_http(url) -> bool:
    return isinstance(url, str) and urlparse(url).scheme in ("http", "https")


def pick(v, lang):
    """Text v daném jazyce, jinak druhý jazyk (lepší než prázdné místo)."""
    if isinstance(v, dict):
        return (v.get(lang) or v.get("cs") or v.get("en") or "").strip()
    return (v or "").strip()


def parse_date(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


# ---------------------------------------------------------------- data
def load_days() -> list:
    days = []
    for f in sorted(DATA.glob("*.json"), reverse=True):
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as ex:
            print(f"  ! {f.name}: nečitelný JSON ({ex}), přeskakuji")
            continue
        date = parse_date(raw.get("date") or f.stem)
        if not date:
            print(f"  ! {f.name}: chybí platné datum, přeskakuji")
            continue
        items, seen = [], set()
        for it in raw.get("items") or []:
            url = it.get("url")
            if not is_http(url) or url in seen or not pick(it.get("title"), "cs"):
                print(f"  ! {f.name}: neúplná nebo duplicitní položka vynechána")
                continue
            seen.add(url)
            it["_published"] = parse_date(it.get("published"))
            items.append(it)
        items.sort(key=lambda it: (IMPORTANCE_ORDER.get(it.get("importance"), 3),
                                   -(it["_published"] or dt.date.min).toordinal()))
        days.append({"date": date, "items": items, "sample": bool(raw.get("sample"))})
    # víc souborů na tentýž den (opravný běh) – bereme novější soubor
    out, have = [], set()
    for d in days:
        if d["date"] not in have:
            have.add(d["date"])
            out.append(d)
    return out


# ---------------------------------------------------------------- fotky
META_RE = r'<meta\s[^>]*?(?:property|name)\s*=\s*["\']{k}["\'][^>]*>'
CONTENT_RE = re.compile(r'content\s*=\s*["\']([^"\']+)["\']', re.I)


def find_image(page: str, base: str):
    head = page[:300_000]
    for k in ("og:image:secure_url", "og:image", "og:image:url",
              "twitter:image", "twitter:image:src"):
        for tag in re.findall(META_RE.format(k=re.escape(k)), head, re.I):
            m = CONTENT_RE.search(tag)
            if m:
                url = urljoin(base, html.unescape(m.group(1).strip()))
                if is_http(url):
                    return url
    m = re.search(r'<link\s[^>]*rel=["\']image_src["\'][^>]*href=["\']([^"\']+)', head, re.I)
    if m and is_http(urljoin(base, m.group(1))):
        return urljoin(base, m.group(1))
    return None


def enrich_images(days: list, offline: bool) -> None:
    cache = {}
    if CACHE.exists():
        try:
            cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except ValueError:
            cache = {}
    now = dt.datetime.now(dt.timezone.utc)
    session = None
    changed = False
    for day in days:
        for it in day["items"]:
            if is_http(it.get("image")):
                continue
            url = it["url"]
            c = cache.get(url, {})
            if c.get("image"):
                it["image"] = c["image"]
                continue
            if offline or c.get("tries", 0) >= IMG_TRIES:
                continue
            last = c.get("checked")
            if last and now - dt.datetime.fromisoformat(last) < dt.timedelta(hours=IMG_RETRY_HOURS):
                continue
            if session is None:
                import requests
                session = requests.Session()
                session.headers.update({"User-Agent": UA,
                                        "Accept-Language": "en;q=0.9,*;q=0.5"})
            img, note = None, ""
            try:
                r = session.get(url, timeout=15)
                note = f"HTTP {r.status_code}"
                if r.ok:
                    img = find_image(r.text, r.url)
                    note = "ok" if img else "bez og:image"
            except Exception as ex:          # zdroj nesmí shodit sestavení
                note = type(ex).__name__
            print(f"  foto {'✓' if img else '✗'} {domain(url)} ({note})")
            cache[url] = {"image": img, "tries": c.get("tries", 0) + 1,
                          "checked": now.isoformat(timespec="seconds"), "note": note}
            if img:
                it["image"] = img
            changed = True
    if changed:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(cache, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write("\n")


# ---------------------------------------------------------------- HTML
def card(it: dict, lang: str, lead=False) -> str:
    t = T[lang]
    url = it["url"]
    dom = domain(url)
    title = pick(it.get("title"), lang)
    summary = pick(it.get("summary"), lang)
    cat = pick(it.get("category"), lang)
    cc = (it.get("country") or "").upper()
    country = COUNTRIES.get(cc, (cc, cc))[0 if lang == "cs" else 1] if cc else ""
    pub = it["_published"]
    high = it.get("importance") == "high"
    orig = it.get("original_title") or ""

    img = it.get("image")
    if is_http(img):
        media = (f'<img src="{e(img)}" alt="" loading="{"eager" if lead else "lazy"}" '
                 f'decoding="async" referrerpolicy="no-referrer" '
                 f'onerror="this.parentNode.classList.add(\'noimg\');this.remove()">')
        cls = "media"
    else:
        media, cls = "", "media noimg"

    kicker = []
    if high:
        kicker.append(f'<span class="badge">{e(t["high"])}</span>')
    if country:
        kicker.append(f'<span class="country">{e(country)}</span>')
    if cat:
        kicker.append(f'<span class="cat">{e(cat)}</span>')

    meta = []
    if pub:
        meta.append(f'<time datetime="{pub.isoformat()}">{fmt_short(pub, lang)}</time>')
    if it.get("source"):
        meta.append(f'<span>{e(it["source"])}</span>')

    return f"""<article class="card{' lead' if lead else ''}{' is-high' if high else ''}">
  <a class="{cls}" href="{e(url)}" target="_blank" rel="noopener" tabindex="-1" aria-hidden="true">{media}<span class="ph">{e(dom)}</span></a>
  <div class="body">
    <p class="kicker">{''.join(kicker)}</p>
    <h3><a href="{e(url)}" target="_blank" rel="noopener"{f' title="{e(orig)}"' if orig else ''}>{e(title)}</a></h3>
    <p class="perex">{e(summary)}</p>
    <p class="meta">{' · '.join(meta)}</p>
    <a class="more" href="{e(url)}" target="_blank" rel="noopener">{e(t['more'].format(d=dom))} <span aria-hidden="true">↗</span></a>
  </div>
</article>"""


def day_section(day: dict, lang: str, with_lead: bool, link: str | None) -> str:
    items = day["items"]
    n = len(items)
    head = e(fmt_day(day["date"], lang))
    if link:
        head = f'<a href="{e(link)}">{head}</a>'
    parts = [f'<section class="day"><header class="day-head"><h2>{head}</h2>'
             f'<span class="count">{n} {plural(lang, n)}</span></header>']
    rest = items
    highs = [i for i in items if i.get("importance") == "high"]
    if with_lead and highs:
        # hlavní zpráva = první klíčová s fotkou (velká plocha bez fotky
        # vypadá jako chyba), jinak první klíčová
        lead = next((i for i in highs if is_http(i.get("image"))), highs[0])
        parts.append(card(lead, lang, lead=True))
        rest = [i for i in items if i is not lead]
    if rest:
        parts.append('<div class="grid">' + "\n".join(card(i, lang) for i in rest) + "</div>")
    parts.append("</section>")
    return "\n".join(parts)


# Cesty: cs v kořeni web/, en v web/en/. Stránky dnů v den/ resp. en/day/.
def paths(lang: str):
    if lang == "cs":
        return {"home": "index.html", "archive": "archiv.html", "day": "den/{d}.html"}
    return {"home": "en/index.html", "archive": "en/archive.html", "day": "en/day/{d}.html"}


def rel(from_path: str, to_path: str) -> str:
    depth = from_path.count("/")
    return "../" * depth + to_path


def page(lang: str, path: str, other_path: str, title: str, body: str,
         sample: bool, active: str) -> str:
    t = T[lang]
    other = "en" if lang == "cs" else "cs"
    p = paths(lang)
    nav = (f'<a href="{rel(path, p["home"])}"{" aria-current=page" if active == "home" else ""}>{e(t["latest"])}</a>'
           f'<a href="{rel(path, p["archive"])}"{" aria-current=page" if active == "archive" else ""}>{e(t["archive"])}</a>')
    banner = f'<div class="sample">{e(t["sample"])}</div>' if sample else ""
    full_title = f"{title} – {t['site']}" if title != t["site"] else t["site"]
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="{ROBOTS}">
<meta name="description" content="{e(t['tagline'])}">
<title>{e(full_title)}</title>
<link rel="alternate" hreflang="{other}" href="{rel(path, other_path)}">
<link rel="stylesheet" href="{rel(path, 'assets/style.css')}">
</head>
<body>
{banner}
<header class="site">
  <div class="wrap top">
    <a class="brand" href="{rel(path, p['home'])}">
      <span class="mark" aria-hidden="true"></span>
      <span><strong>{e(t['site'])}</strong><small>{e(t['tagline'])}</small></span>
    </a>
    <a class="lang" href="{rel(path, other_path)}" hreflang="{other}" lang="{other}">{e(t['switch'])}</a>
  </div>
  <nav class="wrap nav">{nav}</nav>
</header>
<main class="wrap">
{body}
</main>
<footer class="site">
  <div class="wrap"><p>{e(t['about'])}</p></div>
</footer>
</body>
</html>
"""


def write(path: str, content: str) -> None:
    f = WEB / path
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


def build(offline=False) -> None:
    days = load_days()
    print(f"Načteno {len(days)} dnů, {sum(len(d['items']) for d in days)} zpráv.")
    enrich_images(days, offline)
    sample = any(d["sample"] for d in days)
    written = 0
    for lang in ("cs", "en"):
        t = T[lang]
        p, o = paths(lang), paths("en" if lang == "cs" else "cs")

        # titulní stránka
        home_days = days[:HOME_DAYS]
        body = "\n".join(day_section(d, lang, i == 0, None) for i, d in enumerate(home_days))
        if not body:
            body = f'<p class="empty">{e(t["empty"])}</p>'
        if len(days) > HOME_DAYS:
            body += f'\n<p class="older"><a href="{rel(p["home"], p["archive"])}">{e(t["older"])} →</a></p>'
        write(p["home"], page(lang, p["home"], o["home"], t["site"], body, sample, "home"))
        written += 1

        # stránky jednotlivých dnů
        for d in days:
            dp = p["day"].format(d=d["date"].isoformat())
            op = o["day"].format(d=d["date"].isoformat())
            title = t["day_title"].format(d=fmt_day(d["date"], lang, weekday=False))
            write(dp, page(lang, dp, op, title, day_section(d, lang, True, None),
                           d["sample"], ""))
            written += 1

        # archiv
        rows = []
        for d in days:
            dp = p["day"].format(d=d["date"].isoformat())
            n = len(d["items"])
            heads = " · ".join(e(pick(i.get("title"), lang)) for i in d["items"][:3])
            rows.append(f'<li><a href="{rel(p["archive"], dp)}">{e(fmt_day(d["date"], lang))}</a>'
                        f' <span class="count">{n} {plural(lang, n)}</span>'
                        f'<p>{heads}</p></li>')
        body = (f'<h1 class="page-title">{e(t["arch_head"])}</h1>'
                f'<ul class="archive">{"".join(rows)}</ul>')
        write(p["archive"], page(lang, p["archive"], o["archive"], t["arch_head"],
                                 body, sample, "archive"))
        written += 1
    print(f"Hotovo: {written} stránek ve {WEB.relative_to(ROOT)}/")


if __name__ == "__main__":
    build(offline="--offline" in sys.argv)
