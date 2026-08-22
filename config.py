"""Konfigurace pipeline pro monitoring zpráv o Romech.

Dva PROFILY (přepínač MONITOR_PROFILE):
  world — Romové ve světě; hledá ETNICKÝ termín napříč 15 jazyky (výchozí)
  cz    — dění v ČR v agendě ROMEA; hledá TÉMATA (rasismus, bydlení, dávky,
          diskriminace…), protože velká část těch zpráv slovo „Rom" vůbec
          neobsahuje — např. „superdávka", „segregace ve školách".

Zdroje pro každý profil jsou dole v sekci „TVOJE ZDROJE".
Vše citlivé (API klíč, SMTP heslo) se bere z proměnných prostředí,
nikdy se nepíše natvrdo do kódu.
"""
import os

MONITOR_PROFILE = os.getenv("MONITOR_PROFILE", "world")

# --- Obecné nastavení ---
# Okno pro Google News. Sběr běží 1× denně a jen Po–Pá (8/2026 – dvakrát
# denně stálo agenta příliš tokenů), takže PONDĚLÍ musí pokrýt celý víkend:
# 74 h = pátek ráno až pondělí ráno + rezerva. Že se v úterý až pátek nic
# nezopakuje, hlídá state/seen.json.
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "74"))
MAX_CANDIDATES = int(os.getenv("MAX_CANDIDATES", "300"))  # strop kandidátů poslaných k analýze
MAX_PER_FEED   = int(os.getenv("MAX_PER_FEED", "40"))
# Strop na jeden Google News dotaz, ať jeden jazyk (např. FR) nezaplaví feed.
# Uplatňuje se PŘED filtrem seen.json, takže u širokého okna (74 h) by ho jinak
# zaplnily už odeslané položky a vytlačily novinky. Zvednutí nestojí agenta
# žádné tokeny navíc – co už viděl, se do feedu stejně nedostane.
MAX_PER_QUERY  = int(os.getenv("MAX_PER_QUERY", "20"))

# Romské NGO feedy a weby publikují řídce (i 1× za pár dní). Krátké okno
# LOOKBACK_HOURS by je míjelo, když běh padne na „hluché" období – proto mají
# vlastní, delší okno. Opakování mezi běhy hlídá perzistentní state/seen.json.
FEED_LOOKBACK_HOURS = int(os.getenv("FEED_LOOKBACK_HOURS", "72"))

# Perzistence „už viděných" URL mezi běhy (commituje ji workflow do repa).
SEEN_PATH     = os.getenv("SEEN_PATH", "state/seen.json")
SEEN_TTL_DAYS = int(os.getenv("SEEN_TTL_DAYS", "14"))   # po té době záznam vyprší

# Archiv pro záchytnou stránku „posledních 7 dní". Feed nese jen NOVÉ položky,
# takže když je agent nepřečte (výpadek, chyba doručení), zmizí nenávratně –
# seen.json se aktualizuje při sběru, ne při odeslání. Archiv drží všechno
# bez ohledu na seen, aby se dalo zpětně dohledat, co uteklo.
ARCHIVE_PATH = os.getenv("ARCHIVE_PATH", "state/archive.json")
ARCHIVE_DAYS = int(os.getenv("ARCHIVE_DAYS", "7"))
CLAUDE_MODEL   = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")  # levnější varianta: claude-haiku-4-5-20251001

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
GOOGLE_NEWS_WHEN = os.getenv("GOOGLE_NEWS_WHEN", "3d")   # kvůli víkendu, viz LOOKBACK_HOURS

# Zdroje, které se z výsledků zahodí (porovnává se s polem `source`, bez ohledu
# na velikost písmen). POZOR: nedělat to operátorem „-site:" v dotazu – Google
# News ho NEPODPORUJE a místo filtrování začne vracet náhodné zprávy
# (ověřeno 8/2026: dotaz se 4 přesnými zásahy vrátil se „-site:" 100 položek
# balastu typu „zatmění Slunce"). Filtrujeme proto až tady v kódu.
EXCLUDE_SOURCES = []

# Google News rate-limituje rychlé série dotazů (15 jazyků + 10 watch webů
# = 25 požadavků). Pauza mezi dotazy + retry na 429/5xx tomu předchází.
GN_PAUSE   = float(os.getenv("GN_PAUSE", "2"))   # s mezi dotazy

# Rozbalení zabalených adres Google News (news.google.com/rss/articles/CBMi…).
# Bez toho dostane agent jen wrapper, který si z VPS neotevře – Google ho
# v EU přesměruje na souhlasovou zeď. Řeší se cookie SOCS + endpoint
# batchexecute (ověřeno 8/2026, 100% úspěšnost). Bonus: teprve se skutečnou
# adresou jde spolehlivě filtrovat podle domény (romea.cz, galerie deníku…).
RESOLVE_GN_URLS   = os.getenv("RESOLVE_GN_URLS", "1") != "0"
GN_RESOLVE_PAUSE  = float(os.getenv("GN_RESOLVE_PAUSE", "0.6"))  # s mezi rozbaleními
GN_RESOLVE_MAX    = int(os.getenv("GN_RESOLVE_MAX", "200"))      # strop na běh
GN_RETRIES = int(os.getenv("GN_RETRIES", "3"))   # pokusy na jeden dotaz

# --- GDELT (globální, vícejazyčný; bez klíče) ---
# Široký kořen (Roma/Romani/Sinti) NAVÁŽE i přeložené články z Balkánu, Ukrajiny,
# Turecka apod. (GDELT Translingual matchuje podle významu). Šum (AS Roma, město
# Řím) řešíme zápornými termíny, NE zúžením – to by zabilo multijazyčný záběr.
# Přidána ethnonyma Gypsy/Gitano/"Irish Travellers" pro globální/anglofonní
# pokrytí; záporné termíny krotí gypsy-šum (Gypsy Rose, gypsy moth, gypsy jazz).
# Pozn.: GDELT má limit na počet termů v dotazu a při přetížení vrací ne-JSON.
# Držíme dotaz krátký (méně termů = spolehlivější parsování); zbylý gypsy-šum
# (Gypsy Rose, gypsy moth…) dotřídí ChatGPT, na úrovni sběru ho neřešíme.
GDELT_QUERY    = ('(Roma OR Romani OR Romanies OR Sinti OR "Roma minority" '
                  'OR Gypsy OR Gitano OR "Irish Travellers") '
                  '-football -soccer -"AS Roma"')
# GDELT má rozbité/zpožděné zpracování čerstvých dat: okno 13 h často padá do
# díry a vrací 0 (ověřeno 7/2026 – 13h prázdno, 1 týden 9 článků). Širší okno
# to málo, co GDELT má, aspoň vytáhne; duplicity mezi běhy hlídá state/seen.json.
GDELT_TIMESPAN = os.getenv("GDELT_TIMESPAN", "72h")
GDELT_MAX      = int(os.getenv("GDELT_MAX", "250"))
# GitHub Actions běží na sdílených IP, na které GDELT často vrací 429.
# Víc pokusů s narůstající prodlevou + náhodný rozptyl (ať se netrefíme do
# stejného okna jako ostatní joby). GDELT je „bonus" – když ani tak neprojde,
# sběr pokračuje bez něj.
GDELT_RETRIES  = int(os.getenv("GDELT_RETRIES", "6"))   # celkový počet pokusů
GDELT_BACKOFF  = int(os.getenv("GDELT_BACKOFF", "8"))   # základ prodlevy v s (8, 16, 24…)

# ════════════════════════════════════════════════════════════════════
#  TVOJE ZDROJE  –  sem přidávej, když narazíš na zajímavý web
# ════════════════════════════════════════════════════════════════════
#
# Máš dvě možnosti podle toho, co web nabízí:
#
# 1) RSS_FEEDS – web má vlastní RSS/Atom feed (často URL končí /feed/ nebo /rss).
#    Přidáš dvojici (adresa feedu, jazyk obsahu). Nejspolehlivější, nejrychlejší.
#
# 2) WATCH_SITES – web feed nemá (nebo nevíš). Přidáš (doménu, jazyk, zemi)
#    a pipeline si sama vytvoří dotaz přes Google News omezený na tu doménu.
#    Pohodlné, ale závisí na tom, co Google z webu indexuje.
#
# Když si nejsi jistý, dej web do WATCH_SITES – vždycky to nějak zabere.

# Formát: (URL feedu, jazyk obsahu) – jazyk putuje do feedu, ať ChatGPT agent
# ví, v jakém jazyce položka je (dřív měly feedové položky lang prázdný).
RSS_FEEDS = [
    # — Nadnárodní / agregátory —
    ("https://rroma.org/feed/",                                  "en"),  # Rroma Foundation – hutný denní agregátor
    ("https://rroma.org/category/news-eastern-europe/feed/",     "en"),  # Rroma – východní Evropa
    ("https://rroma.org/category/news-western-europe/feed/",     "en"),  # Rroma – západní Evropa
    ("https://eriac.org/feed/",                                  "en"),  # ERIAC – umění, kultura, akce, instituce
    # — Ukrajina —
    ("https://chirikli.com.ua/en/news/feed/",                    "en"),  # Chirikli / Roma Women's Fund (EN sekce)
    # — Srbsko / Balkán —
    ("https://rominfomedia.rs/feed/",                            "sr"),  # Rom Info Media (jih Srbska, Leskovac)
    ("https://romaworld.rs/feed/",                               "sr"),  # Romaworld (RS)
    ("https://roma-news.com/feed/",                              "sr"),  # Roma News Network (RS/balkán) – pozn. obsah nyní starší
    # — Chorvatsko —
    ("https://kalisara.hr/feed/",                                "hr"),  # Kali Sara / SRRH – pozn. obsah nyní starší (poslední 6/2025)
    # — Severní Makedonie —
    ("https://romatimes.news/index.php/en?format=feed&type=rss", "en"),  # RomaTimes.News (MK/balkán, EN) – pozn. obsah nyní starší
    # — Slovensko —
    # Pozn.: romatv.sk má vlastní /feed/ PRÁZDNÝ (obsah je ve vlastních typech,
    # REST API blokuje 403) → přesunut do WATCH_SITES (Google News site:).
    ("https://romanoforum.dennikn.sk/feed/",                     "sk"),  # Romano fórum (Denník N) – aktivní, kvalitní
    ("https://romana.tv/feed/",                                  "sk"),  # Romana TV (video/podcast)
    ("https://www.tvroma.sk/feed/",                              "sk"),  # TV Roma – pozn. obsah nyní starší
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

# Klíčová slova připojená k dotazu na WATCH_SITES. Prázdné = nepřidávat.
# Profil „world" je nepotřebuje (samé romské organizace, každý článek je na téma),
# profil „cz" ano (úřady publikují všechno možné, tam bez filtru utoneš).
WATCH_SITE_TERMS = ""

# GDELT má smysl jen u světového profilu (globální translingual).
GDELT_ENABLED = True


# ════════════════════════════════════════════════════════════════════
#  PROFIL „cz" – dění v ČR v agendě ROMEA
# ════════════════════════════════════════════════════════════════════
# Návrh dotazů vychází z reálné produkce ROMEA.cz (analýza 2/2026–8/2026:
# top tagy Rasismus 109, Extremismus 70, Vláda 66, Diskriminace 35, Soud 35,
# Vzdělávání 32, Sociální vyloučení 31, Bydlení 24, Sociální dávky 12…).
#
# POZOR na klíčový rozdíl proti světovému profilu: velká část relevantních
# zpráv slovo „Rom" NEOBSAHUJE („Statisíce domácností dostávají superdávku",
# „Segregace dětí ve školách nekončí"). Proto se hledají TÉMATA, ne etnonyma.
# Cenou je šum (běžné sociální zpravodajství) – ten dotřídí agent.

CZ_GOOGLE_NEWS_QUERIES = [
    # ── VRSTVA 1: je to o Romech (bez ohledu na téma) ──────────────
    # Jádro monitoringu. Sport, kultura, kriminalita, byznys – cokoli,
    # když je to o Romech. Proto je dotazů víc: každý má vlastní strop
    # MAX_PER_QUERY, takže rozdělením získáme pro romská témata víc místa.
    ('Romové OR Romky OR "romská menšina" OR "romská komunita"',            "cs", "CZ"),
    ('romský OR romská OR romské OR romští',                                "cs", "CZ"),
    ('anticiganismus OR protiromský OR cikáni OR cigáni',                   "cs", "CZ"),
    ('"romské děti" OR "romští žáci" OR "romská rodina" OR "romské rodiny"', "cs", "CZ"),
    ('"romská kultura" OR "romská hudba" OR "romský festival" OR "romské divadlo"', "cs", "CZ"),
    ('"romský holokaust" OR "Lety u Písku" OR "Hodonín u Kunštátu" OR Porajmos', "cs", "CZ"),
    # ── VRSTVA 2: témata, která se Romů týkají i bez zmínky ────────
    # Tady je nutná OPATRNOST: volný jednoslovný dotaz („ubytovna",
    # „chudoba") vrátí balast, který spotřebuje celý strop dotazu a vytlačí
    # skutečné trefy. Proto raději konkrétní víceslovné termíny.
    ('rasismus OR rasistický OR "rasový motiv" OR "rasově motivovaný"',     "cs", "CZ"),
    ('extremismus OR neonacisté OR "krajní pravice" OR "předsudečná nenávist"', "cs", "CZ"),
    ('"podněcování k nenávisti" OR "hanobení rasy" OR "nenávistné projevy"', "cs", "CZ"),
    ('"vyloučená lokalita" OR "vyloučené lokality" OR "sociální vyloučení" OR "obchod s chudobou"', "cs", "CZ"),
    ('superdávka OR "dávky na bydlení" OR "příspěvek na bydlení" OR "hmotná nouze"', "cs", "CZ"),
    ('"sociální bydlení" OR "dostupné bydlení" OR "bytová nouze"',          "cs", "CZ"),
    ('"segregace ve školách" OR "společné vzdělávání" OR segregace žáci',   "cs", "CZ"),
    ('"protiprávní sterilizace" OR sterilizace odškodnění',                 "cs", "CZ"),
    ('diskriminace ombudsman OR "veřejný ochránce práv" OR "rovné zacházení"', "cs", "CZ"),
    ('"zmocněnkyně pro romské záležitosti" OR "Rada vlády pro záležitosti romské menšiny" OR "Agentura pro sociální začleňování"', "cs", "CZ"),
]

# Obsahové farmy publikující česky a vlastní články ROMEA (ty redakce nepotřebuje
# dostávat zpátky). Filtruje se podle pole `source` až po stažení – viz
# EXCLUDE_SOURCES výše, proč to nejde operátorem v dotazu.
CZ_EXCLUDE_SOURCES = ["vietnam.vn", "romea.cz", "romea",
                      "medium.cz", "médium.cz",          # obsahová farma
                      "měšec.cz", "sreality.cz", "kaufland.cz", "lidé.cz",
                      "facebook.com", "kurzy.cz", "zdopravy.cz",
                      # „=" = přesná shoda názvu zdroje. Agregátor Seznam.cz
                      # přebírá cizí obsah včetně článků ROMEA (jen titulek,
                      # perex a diskuze). Vlastní žurnalistika „Seznam Zprávy"
                      # tímhle nepadne.
                      "=Seznam"]

# Jen tematicky vyhraněné zdroje. Obecná média (iRozhlas, Deník N, A2larm,
# Hlídací pes, Investigace) tu SCHVÁLNĚ nejsou – publikují všechno od sportu
# po počasí, feed by utonul. Pokrývají je tematické dotazy Google News výše.
CZ_RSS_FEEDS = [
    ("https://amnesty.cz/feed/",          "cs"),  # Amnesty International ČR
    ("https://socialnibydleni.org/feed",  "cs"),  # Platforma pro sociální bydlení
    ("https://in-ius.cz/feed/",           "cs"),  # In IUSTITIA – předsudečné násilí
    ("https://iqrs.cz/feed/",             "cs"),  # IQ Roma servis
    ("https://osf.cz/feed/",              "cs"),  # Nadace OSF
]

# Úřady a organizace bez použitelného feedu (ověřeno 8/2026). Publikují i spoustu
# nesouvisejícího, proto se k dotazu přidávají CZ_WATCH_SITE_TERMS.
CZ_WATCH_SITES = [
    ("vlada.gov.cz",             "cs", "CZ"),  # Úřad vlády, Rada vlády pro rom. menšinu
    ("ochrance.cz",              "cs", "CZ"),  # Veřejný ochránce práv
    ("socialni-zaclenovani.cz",  "cs", "CZ"),  # Agentura pro sociální začleňování
    ("mpsv.cz",                  "cs", "CZ"),  # MPSV – dávky, sociální politika
    ("mmr.gov.cz",               "cs", "CZ"),  # MMR – bydlení, dotace
    ("nssoud.cz",                "cs", "CZ"),  # Nejvyšší správní soud
    ("usoud.cz",                 "cs", "CZ"),  # Ústavní soud
    ("clovekvtisni.cz",          "cs", "CZ"),  # Člověk v tísni
]

CZ_WATCH_SITE_TERMS = ('Rom OR romský OR diskriminace OR "vyloučená lokalita" '
                       'OR rasismus OR "sociální bydlení" OR dávky')


# ── Přepnutí profilu ────────────────────────────────────────────────
if MONITOR_PROFILE == "cz":
    GOOGLE_NEWS_QUERIES = CZ_GOOGLE_NEWS_QUERIES
    EXCLUDE_SOURCES     = CZ_EXCLUDE_SOURCES
    RSS_FEEDS           = CZ_RSS_FEEDS
    WATCH_SITES         = CZ_WATCH_SITES
    WATCH_SITE_TERMS    = CZ_WATCH_SITE_TERMS
    GDELT_ENABLED       = False   # u domácího zpravodajství nepřidá nic navíc
    MAX_PER_QUERY       = int(os.getenv("MAX_PER_QUERY", "14"))
    # Českých zpráv k těmto tématům vychází řádově míň než u 15 jazyků světového
    # profilu: when:1d vracelo 0–4 položky na dotaz, when:7d desítky (ověřeno
    # 8/2026). Proto širší okno – že se nic nezopakuje, hlídá state/seen.json.
    GOOGLE_NEWS_WHEN    = os.getenv("GOOGLE_NEWS_WHEN", "3d")
    LOOKBACK_HOURS      = int(os.getenv("LOOKBACK_HOURS", "72"))


# --- E-mail (SMTP) ---
EMAIL_TO   = [x.strip() for x in os.getenv("EMAIL_TO", "").split(",") if x.strip()]
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
SMTP_HOST  = os.getenv("SMTP_HOST", "")
SMTP_PORT  = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER  = os.getenv("SMTP_USER", "")
SMTP_PASS  = os.getenv("SMTP_PASS", "")
