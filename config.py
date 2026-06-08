"""Konfigurace pipeline pro monitoring zpráv o Romech ve světě.

Vše citlivé (API klíč, SMTP heslo) se bere z proměnných prostředí,
nikdy se nepíše natvrdo do kódu.
"""
import os

# --- Obecné nastavení ---
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "13"))   # okno; >12 h kvůli překryvu mezi běhy
MAX_CANDIDATES = int(os.getenv("MAX_CANDIDATES", "150"))  # strop kandidátů poslaných k analýze
MAX_PER_FEED   = int(os.getenv("MAX_PER_FEED", "40"))
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
]

# Operátor Google News „when:" – vrátí jen čerstvé články za zadané období.
# Bez něj Google řadí podle relevance a aktuální zprávy propadnou oknem 13 h.
GOOGLE_NEWS_WHEN = os.getenv("GOOGLE_NEWS_WHEN", "1d")

# --- GDELT (globální, vícejazyčný; bez klíče) ---
# Vyžadujeme menšinový/etnický kontext a odřízneme fotbal, ať nelezou
# AS Roma a město Řím napříč exotickými jazyky (thajština, čínština…).
GDELT_QUERY    = '("Roma minority" OR "Roma people" OR "Roma community" OR Romani OR Sinti) -soccer -football'
GDELT_TIMESPAN = os.getenv("GDELT_TIMESPAN", "13h")
GDELT_MAX      = int(os.getenv("GDELT_MAX", "75"))

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
    "https://rroma.org/feed/",          # Rroma Foundation – hutný denní agregátor
    # "https://nejaky-web.cz/rss",      # <- přidej svůj feed sem
]

WATCH_SITES = [
    "errc.org",                         # European Roma Rights Centre (vlastní CMS, bez feedu)
    # "romea.cz",                       # <- přidej doménu sem
]

# Klíčová slova připojená k dotazu na WATCH_SITES (kvůli relevanci u obecných webů).
WATCH_SITE_TERMS = "Roma OR Romani OR Sinti OR Romové"

# --- E-mail (SMTP) ---
EMAIL_TO   = [x.strip() for x in os.getenv("EMAIL_TO", "").split(",") if x.strip()]
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
SMTP_HOST  = os.getenv("SMTP_HOST", "")
SMTP_PORT  = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER  = os.getenv("SMTP_USER", "")
SMTP_PASS  = os.getenv("SMTP_PASS", "")
