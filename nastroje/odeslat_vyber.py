#!/usr/bin/env python3
"""Nahraje denní výběr agenta pro web „Romové ve světě“ do repozitáře.

ZATÍM NENASAZENO (viz CLAUDE.md, „Web Romové ve světě“). Použití:

    python3 ~/roma-monitor/odeslat_vyber.py ~/roma-monitor/vyber/vyber-2026-11-25.json
    python3 ~/roma-monitor/odeslat_vyber.py soubor.json --zkouska   # jen kontrola

Co dělá:
  1. zkontroluje, že soubor odpovídá formátu webu (viz build_web.py);
     chyby vypíše a NIC nenahraje – agent soubor opraví a spustí znovu
  2. přes GitHub API ho zapíše jako web/data/<date>.json ve větvi main
     (opravný běh téhož dne soubor přepíše)

Token: fine-grained PAT jen na repo roma-monitor s oprávněním
Contents: Read and write. Čte se ze souboru ~/.config/roma-monitor/github-token
(cestu jde změnit proměnnou ROMA_TOKEN_FILE). Skript ho nikdy nevypisuje.

Návratové kódy: 0 = nahráno (nebo prázdný výběr), 1 = chyba sítě/tokenu,
                2 = chybná data v souboru.
Jen standardní knihovna Pythonu, nic se neinstaluje.
"""
import base64
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse

REPO       = "zdenekrysavy-lang/roma-monitor"
BRANCH     = "main"
TARGET_DIR = "web/data"
TOKEN_FILE = os.path.expanduser(
    os.getenv("ROMA_TOKEN_FILE") or "~/.config/roma-monitor/github-token")

IMPORTANCE   = {"high", "medium", "low"}
MAX_ITEMS    = 60
MAX_AGE_DAYS = 7          # stejné pravidlo jako v e-mailu
SUMMARY_MAX  = 420        # znaků; shrnutí má mít 1–2 věty
TITLE_MAX    = 160
# ČTK je licencovaná a nemá veřejný odkaz na plné znění – na web nepatří
BANNED_HOSTS = ("ctk.cz", "ctk.eu", "mail.google.com", "news.google.com")


def is_http(u) -> bool:
    return isinstance(u, str) and urlparse(u).scheme in ("http", "https") \
        and bool(urlparse(u).hostname)


def iso_date(s):
    if not isinstance(s, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return None
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return None


def both_langs(it: dict, key: str, limit: int, errors: list, where: str) -> None:
    v = it.get(key)
    if not isinstance(v, dict):
        errors.append(f"{where}: `{key}` musí být objekt {{\"cs\": …, \"en\": …}}")
        return
    for lang in ("cs", "en"):
        s = v.get(lang)
        if not isinstance(s, str) or not s.strip():
            errors.append(f"{where}: chybí `{key}.{lang}`")
        elif len(s) > limit:
            errors.append(f"{where}: `{key}.{lang}` je moc dlouhé ({len(s)} > {limit} znaků)")


def validate(data) -> list:
    errors = []
    if not isinstance(data, dict):
        return ["kořen souboru musí být objekt s poli `date` a `items`"]
    day = iso_date(data.get("date"))
    if not day:
        errors.append("`date` musí být datum běhu ve tvaru RRRR-MM-DD")
    today = dt.date.today()
    if day and abs((day - today).days) > 1:
        errors.append(f"`date` {day} neodpovídá dnešku ({today})")
    if data.get("sample"):
        errors.append("`sample` patří jen ukázkovým datům, ve výběru agenta být nesmí")
    items = data.get("items")
    if not isinstance(items, list):
        return errors + ["`items` musí být pole zpráv"]
    if len(items) > MAX_ITEMS:
        errors.append(f"příliš mnoho zpráv ({len(items)} > {MAX_ITEMS})")

    seen = set()
    for n, it in enumerate(items, 1):
        where = f"zpráva {n}"
        if not isinstance(it, dict):
            errors.append(f"{where}: musí být objekt")
            continue
        url = it.get("url")
        if not is_http(url):
            errors.append(f"{where}: `url` není platná adresa http(s)")
        else:
            where = f"zpráva {n} ({urlparse(url).hostname})"
            host = urlparse(url).hostname.lower()
            if any(host == b or host.endswith("." + b) for b in BANNED_HOSTS):
                errors.append(f"{where}: odkaz na {host} na web nepatří "
                              "(ČTK je licencovaná, Google News/Gmail nejsou zdroj)")
            if url in seen:
                errors.append(f"{where}: duplicitní `url`")
            seen.add(url)
        for key in ("source", "lang", "original_title"):
            if not isinstance(it.get(key), str) or not it[key].strip():
                errors.append(f"{where}: chybí `{key}`")
        cc = it.get("country")
        if not isinstance(cc, str) or not re.fullmatch(r"[A-Z]{2}|INT", cc):
            errors.append(f"{where}: `country` musí být ISO kód velkými písmeny "
                          "(FR, HU…), EU, nebo INT")
        pub = iso_date(it.get("published"))
        if not pub:
            errors.append(f"{where}: `published` musí být ověřené datum RRRR-MM-DD")
        elif day:
            if pub > day + dt.timedelta(days=1):
                errors.append(f"{where}: `published` {pub} je v budoucnosti")
            elif (day - pub).days > MAX_AGE_DAYS and not it.get("upcoming_event"):
                errors.append(f"{where}: článek z {pub} je starší než {MAX_AGE_DAYS} dní")
        if it.get("importance") not in IMPORTANCE:
            errors.append(f"{where}: `importance` musí být high, medium nebo low")
        both_langs(it, "title", TITLE_MAX, errors, where)
        both_langs(it, "summary", SUMMARY_MAX, errors, where)
        both_langs(it, "category", 40, errors, where)
        if "image" in it and it["image"] not in (None, "") and not is_http(it["image"]):
            errors.append(f"{where}: `image` musí být adresa http(s), nebo pole vynech")
    return errors


def api(method: str, path: str, token: str, body=None):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "roma-monitor-vyber"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"{}")


def upload(day: str, content: bytes) -> str:
    try:
        with open(TOKEN_FILE, encoding="utf-8") as fh:
            token = fh.read().strip()
    except OSError:
        raise SystemExit(f"CHYBA: token nenalezen ({TOKEN_FILE}). Výběr NEBYL nahrán.")
    path = f"contents/{TARGET_DIR}/{day}.json"
    sha = None
    try:
        sha = api("GET", f"{path}?ref={BRANCH}", token).get("sha")
    except urllib.error.HTTPError as ex:
        if ex.code != 404:
            raise
    body = {"message": f"Výběr pro web {day}",
            "content": base64.b64encode(content).decode(),
            "branch": BRANCH}
    if sha:
        body["sha"] = sha
    res = api("PUT", path, token, body)
    return res.get("commit", {}).get("sha", "?")[:7] + (" (přepsán)" if sha else "")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--zkouska" in sys.argv
    if len(args) != 1:
        print(__doc__)
        return 2
    try:
        with open(args[0], encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as ex:
        print(f"CHYBA: soubor nejde přečíst jako JSON: {ex}")
        return 2

    errors = validate(data)
    if errors:
        print(f"CHYBA: výběr má {len(errors)} problémů, NIC nebylo nahráno:")
        for e in errors:
            print(f"  - {e}")
        return 2
    n = len(data["items"])
    if n == 0:
        print("Výběr je prázdný – na web není co nahrát (to je v pořádku).")
        return 0
    content = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if dry:
        print(f"OK: {n} zpráv prošlo kontrolou (zkouška, nic nenahráno).")
        return 0

    for attempt in (1, 2):
        try:
            commit = upload(data["date"], content)
            print(f"OK: nahráno {n} zpráv do {TARGET_DIR}/{data['date']}.json, commit {commit}")
            return 0
        except urllib.error.HTTPError as ex:
            msg = {401: "token je neplatný nebo vypršel",
                   403: "token nemá oprávnění Contents: Read and write",
                   404: "repozitář nenalezen – token nemá přístup k roma-monitor",
                   409: "souběh s jiným zápisem",
                   422: "GitHub odmítl data"}.get(ex.code, "")
            print(f"CHYBA {ex.code} při nahrávání: {msg} (pokus {attempt}/2)")
            if ex.code not in (409, 500, 502, 503):
                break
        except (urllib.error.URLError, TimeoutError) as ex:
            print(f"CHYBA sítě: {ex} (pokus {attempt}/2)")
    print("Výběr NEBYL nahrán.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
