"""Konfigurace pipeline pro monitoring zpráv o Romech ve světě.

Vše citlivé (API klíč, SMTP heslo) se bere z proměnných prostředí,
nikdy se nepíše natvrdo do kódu.
"""
import os

# --- Obecné nastavení ---
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "13"))   # okno; >12 h kvůli překryvu mezi běhy
MAX_CANDIDATES = int(os.getenv("MAX_CANDIDATES", "150"))  # strop kandidátů poslaných k analýze
MAX_PER_FEED   = int(os.getenv("MAX_PER_FEED", "40"))
MAX_PER_QUERY  = int(os.getenv("MAX_PER_QUERY", "12"))    # strop na jeden Google News dotaz, ať jeden jazyk (např. FR) nezaplaví feed
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
GDELT_QUERY    = '(Roma OR Romani OR Romanies OR Sinti OR "Roma minority") -football -soccer -"AS Roma" -calcio -transfer'
GDELT_TIMESPAN = os.getenv("GDELT_TIMESPAN", "13h")
GDELT_MAX      = int(os.getenv("GDELT_MAX", "120"))

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
    "https://romatv.sk/feed/",                                  # Roma Television
    "https://romana.tv/feed/",                                  # Romana TV (video/podcast)
    "https://www.tvroma.sk/feed/",                              # TV Roma – pozn. obsah nyní starší
]

WATCH_SITES = [
    # Weby BEZ feedu – pipeline si udělá Google News dotaz „site:doména".
    # Výnos závisí na tom, co Google z webu indexuje (u malých NGO může být i 0).
    "errc.org",                         # European Roma Rights Centre – kauzy, právní kroky
    "romaforeurope.org",                # Roma Foundation for Europe – press, kampaně, akce
    "ergonetwork.org",                  # ERGO Network – News & Events
    "romaofukraine.com",                # Roma of Ukraine / Roma News Ukraine (Wix, bez feedu)
    "arca.org.ua",                      # ARCA Ukraine – Events, Projects, For the press
    "aura-alliance.org",                # AURA – Ukrainian Roma Advocacy Alliance
    "romnet.hu",                        # RomNet.hu (HU)
    "dikhmedia.hu",                     # DIKH Média (HU)
    "romapage.c3.hu",                   # Roma Press Center (HU) – spíš archivní
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
