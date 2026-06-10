"""Konfigurace pipeline pro monitoring zpráv o Romech ve světě.

Vše citlivé (API klíč, SMTP heslo) se bere z proměnných prostředí,
nikdy se nepíše natvrdo do kódu.
"""
import os

# --- Obecné nastavení ---
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "13"))   # okno; >12 h kvůli překryvu mezi běhy
MAX_CANDIDATES = int(os.getenv("MAX_CANDIDATES", "300"))  # strop kandidátů poslaných k analýze
MAX_PER_FEED   = int(os.getenv("MAX_PER_FEED", "40"))
MAX_PER_QUERY  = int(os.getenv("MAX_PER_QUERY", "12"))    # strop na jeden Google News dotaz, ať jeden jazyk (např. FR) nezaplaví feed

# Romské NGO feedy a weby publikují řídce (i 1× za pár dní). Krátké okno
# LOOKBACK_HOURS by je míjelo, když běh padne na „hluché" období – proto mají
# vlastní, delší okno. Opakování mezi běhy hlídá perzistentní state/seen.json.
FEED_LOOKBACK_HOURS = int(os.getenv("FEED_LOOKBACK_HOURS", "72"))

# Perzistence „už viděných" URL mezi běhy (commituje ji workflow do repa).
SEEN_PATH     = os.getenv("SEEN_PATH", "state/seen.json")
SEEN_TTL_DAYS = int(os.getenv("SEEN_TTL_DAYS", "14"))   # po té době záznam vyprší
CLAUDE_MODEL   = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")  # levnější varianta: claude-haiku-4-5-20251001

# --- Google News RSS: (dotaz, jazyk hl, země gl) ---
# Pro každý jazyk vlastní dotaz s lokálními termíny pro "Romové".
# U angličtiny/italštiny jsou navíc záporné termíny (-football…), aby vypadla
# fotbalová AS Roma a zeměpisné „Roma" (město Řím, ulice Avinguda Roma apod.).
GOOGLE_NEWS_QUERIES = [
    # Pozn.: české zprávy záměrně nesledujeme – domácí dění si ROMEA pokrývá sama,
    # tento monitoring cílí na Romy VE SVĚTĚ.
    ('Rómovia OR "rómska menšina"',                            "sk", "SK"),
    ('"Roma minority" OR "Roma people" OR "Roma community" OR Romani -football -soccer -transfer', "en", "US"),
    ('"Roma minority" OR "Roma community" OR Romani OR "Gypsy community" -football -soccer -transfer', "en", "GB"),
    ('"roma kisebbség" OR cigány',                             "hu", "HU"),
    ('romi OR "minoritatea romă" OR "etnia romă"',             "ro", "RO"),
    ('gitanos OR "pueblo gitano" OR "comunidad gitana"',       "es", "ES"),
    ('Roms OR "gens du voyage" OR Rroms',                      "fr", "FR"),
    ('"Sinti und Roma" OR Antiziganismus OR Romafeindlichkeit OR "Roma-Minderheit"', "de", "DE"),
    ('"rom e sinti" OR "comunità rom" -calcio -"AS Roma"',     "it", "IT"),
    ('Роми OR ромска OR цигани',                               "bg", "BG"),
    ('Ρομά OR τσιγγάνοι OR "μειονότητα Ρομά"',                 "el", "GR"),
    ('Romowie OR "mniejszość romska" OR Cyganie',             "pl", "PL"),
    ('ciganos OR "comunidade cigana"',                        "pt", "PT"),
    ('romer OR "romsk minoritet"',                            "sv", "SE"),
    ('romanit OR "Suomen romanit"',                           "fi", "FI"),
]
# Pozn.: Balkán (srbština, chorvatština, albánština), Ukrajinu a Turecko
# ZÁMĚRNĚ neřešíme rodnými Google dotazy – tamní kořen „rom/Roman" se sráží
# s „Rom-Com", římskými lázněmi, fotbalem apod. Tyhle země pokrývá líp široký
# GDELT (hledá přes překlad podle významu, ne podle matoucího kořene).

# Operátor Google News „when:" – vrátí jen čerstvé články za zadané období.
# Bez něj Google řadí podle relevance a aktuální zprávy propadnou oknem 13 h.
GOOGLE_NEWS_WHEN = os.getenv("GOOGLE_NEWS_WHEN", "1d")

# --- GDELT (globální, vícejazyčný; bez klíče) ---
# Široký kořen (Roma/Romani/Sinti) NAVÁŽE i přeložené články z Balkánu, Ukrajiny,
# Turecka apod. (GDELT Translingual matchuje podle významu). Šum (AS Roma, město
# Řím) řešíme zápornými termíny, NE zúžením – to by zabilo multijazyčný záběr.
# Přidána ethnonyma Gypsy/Gitano/"Irish Travellers" pro globální/anglofonní
# pokrytí; záporné termíny krotí gypsy-šum (Gypsy Rose, gypsy moth, gypsy jazz).
GDELT_QUERY    = ('(Roma OR Romani OR Romanies OR Sinti OR "Roma minority" '
                  'OR Gypsy OR Gitano OR "Irish Travellers") '
                  '-football -soccer -"AS Roma" -calcio -transfer '
                  '-"Gypsy Rose" -"gypsy moth" -"gypsy jazz"')
GDELT_TIMESPAN = os.getenv("GDELT_TIMESPAN", "13h")
GDELT_MAX      = int(os.getenv("GDELT_MAX", "250"))
# GitHub Actions běží na sdílených IP, na které GDELT často vrací 429.
# Víc pokusů s narůstající prodlevou + náhodný rozptyl (ať se netrefíme do
# stejného okna jako ostatní joby). GDELT je „bonus" – když ani tak neprojde,
# sběr pokračuje bez něj.
GDELT_RETRIES  = int(os.getenv("GDELT_RETRIES", "4"))   # celkový počet pokusů
GDELT_BACKOFF  = int(os.getenv("GDELT_BACKOFF", "8"))   # základ prodlevy v s (8, 16, 24…)

# ════════════════════════════════════════════════════════════════════
#  TVOJE ZDROJE  –  sem přidávej, když narazíš na zajímavý web
# ════════════════════════════════════════════════════════════════════
#
# Máš dvě možnosti podle toho, co web nabízí:
#
# 1) RSS_FEEDS – web má vlastní RSS/Atom feed (často URL končí /feed/ nebo /rss).
#    Přidáš celou adresu feedu. Nejspolehlivější, nejrychlejší.
#
# 2) WATCH_SITES – web feed nemá (nebo nevíš). Přidáš jen doménu a pipeline
#    si sama vytvoří dotaz přes Google News omezený na tu doménu + romská
#    klíčová slova. Pohodlné, ale závisí na tom, co Google z webu indexuje.
#
# Když si nejsi jistý, dej web do WATCH_SITES – vždycky to nějak zabere.

RSS_FEEDS = [
    # — Nadnárodní / agregátory —
    "https://rroma.org/feed/",                                  # Rroma Foundation – hutný denní agregátor
    "https://rroma.org/category/news-eastern-europe/feed/",     # Rroma – východní Evropa
    "https://rroma.org/category/news-western-europe/feed/",     # Rroma – západní Evropa
    "https://eriac.org/feed/",                                  # ERIAC – umění, kultura, akce, instituce
    # — Ukrajina —
    "https://chirikli.com.ua/en/news/feed/",                    # Chirikli / Roma Women's Fund (EN)
    # — Srbsko / Balkán —
    "https://rominfomedia.rs/feed/",                            # Rom Info Media (jih Srbska, Leskovac)
    "https://romaworld.rs/feed/",                               # Romaworld (RS)
    "https://roma-news.com/feed/",                              # Roma News Network (RS/balkán) – pozn. obsah nyní starší
    # — Severní Makedonie —
    "https://romatimes.news/index.php/en?format=feed&type=rss", # RomaTimes.News (MK/balkán, EN) – pozn. obsah nyní starší
    # — Slovensko —
    # Pozn.: romatv.sk má vlastní /feed/ PRÁZDNÝ (obsah je ve vlastních typech,
    # REST API blokuje 403) → přesunut do WATCH_SITES (Google News site:).
    "https://romana.tv/feed/",                                  # Romana TV (video/podcast)
    "https://www.tvroma.sk/feed/",                              # TV Roma – pozn. obsah nyní starší
]

WATCH_SITES = [
    # Weby BEZ (použitelného) feedu – pipeline udělá Google News dotaz „site:doména".
    # Formát: (doména, jazyk hl, země gl). JAZYK je klíčový – slovenský/maďarský
    # článek nenajdeš anglickým dotazem.
    # Termínový filtr ZÁMĚRNĚ nepřidáváme: všechny jsou ryze romské organizace,
    # takže každý jejich článek je na téma. Výnos závisí na indexaci Googlem
    # (u malých NGO může být i 0).
    ("errc.org",          "en", "US"),  # European Roma Rights Centre – kauzy, právní kroky
    ("romaforeurope.org", "en", "US"),  # Roma Foundation for Europe – press, kampaně, akce
    ("ergonetwork.org",   "en", "US"),  # ERGO Network – News & Events
    ("romaofukraine.com", "en", "US"),  # Roma of Ukraine / Roma News Ukraine (EN)
    ("arca.org.ua",       "en", "US"),  # ARCA Ukraine – má /en/ sekci
    ("aura-alliance.org", "en", "US"),  # AURA – Ukrainian Roma Advocacy Alliance (/en/)
    ("romnet.hu",         "hu", "HU"),  # RomNet.hu
    ("dikhmedia.hu",      "hu", "HU"),  # DIKH Média
    ("romapage.c3.hu",    "hu", "HU"),  # Roma Press Center (archivní)
    ("romatv.sk",         "sk", "SK"),  # Roma Television – /feed/ prázdný, jdeme přes Google
]

# --- E-mail (SMTP) ---
EMAIL_TO   = [x.strip() for x in os.getenv("EMAIL_TO", "").split(",") if x.strip()]
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
SMTP_HOST  = os.getenv("SMTP_HOST", "")
SMTP_PORT  = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER  = os.getenv("SMTP_USER", "")
SMTP_PASS  = os.getenv("SMTP_PASS", "")
