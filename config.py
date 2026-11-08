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
# Okno pro Google News. Sběr běží 1× denně, každý den. 50 h = dvojnásobek
# kadence, takže se nic neztratí, ani když jeden běh vypadne (GitHub měl
# 8/2026 výpadek Actions). Že se nic nezopakuje, hlídá state/seen.json.
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", "50"))
MAX_CANDIDATES = int(os.getenv("MAX_CANDIDATES", "500"))  # strop kandidátů poslaných k analýze
MAX_PER_FEED   = int(os.getenv("MAX_PER_FEED", "40"))
# Obecná zpravodajská média (NEWS_FEEDS) mají feedy delší než romské –
# 50 položek je běžných – a filtr klíčovými slovy z nich stejně většinu
# zahodí, takže se vyplatí projít jich víc.
MAX_PER_NEWS_FEED = int(os.getenv("MAX_PER_NEWS_FEED", "60"))
# Výchozí stav: obecná média čte jen profil cz (viz CZ_NEWS_FEEDS níže).
# Světový profil je má prázdné – tam nese zátěž Google News + GDELT.
NEWS_FEEDS = []
FEED_TERMS = []
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

# Pojistka proti dvojímu běhu. Workflow má dva crony (hlavní + záloha),
# protože GitHub plánované běhy zpožďuje o 5–10 h. Když ale doběhnou oba,
# druhý přepíše feed a položky z prvního se ztratí – v seen.json zůstanou
# zapsané, ale agent je nikdy neuvidí. Proto se běh přeskočí, pokud je
# existující feed mladší než tahle doba. Nula = guard vypnutý.
#
# Hodnota musí sedět do rozpětí, které vymezuje rozptyl zpoždění (5,2–9,8 h):
#   dolní mez 8,1 h = odstup hlavního a záložního cronu (3,5 h) + rozptyl,
#                     pod ní by si dva běhy téže noci navzájem přepsaly feed;
#   horní mez 19,4 h = 24 h mezi dny mínus rozptyl, nad ní by guard zablokoval
#                     i legitimní běh dalšího dne.
# 12 h leží uprostřed; 18 h (původní volba) projde v nejhorším případě
# o 1,4 h a spoléhalo by se pak na záložní cron.
FEED_MIN_AGE_HOURS = float(os.getenv("FEED_MIN_AGE_HOURS") or "12")

# Ranní spouštění z VPS (11/2026). GitHub plánované běhy zakládá o 5–10 h
# později, ruční workflow_dispatch ale startuje do minuty – proto sběr
# spouští cron na VPS (kde běží agent) v 8:40 Praha přes GitHub API.
# Noční crony v Actions zůstávají jako záloha pro případ, že VPS selže.
#
# Aby se ranní běh nepral s nočním, feed se SLUČUJE: obsahuje všechno, co
# přibylo od posledního ranního (publikačního) běhu – nové položky + ty,
# které nasbíral noční běh a agent je ještě neviděl. Bez toho by ranní běh
# noční feed přepsal a jeho položky by zmizely (v seen.json zapsané, agent
# by je nikdy nedostal).
#
# PUBLISH_RUN = 1 jen u spuštění z VPS (workflow input source=vps). Jen ten
#   posouvá začátek okna. Ruční spuštění z webu okno nemění, jinak by se
#   zprávy mezi ranním čtením a ručním testem do zítřka nedostaly.
# CUTOFF_PATH – kde je uložen čas posledního publikačního běhu.
# FEED_WINDOW_MAX_HOURS – strop, jak daleko zpět feed sahá. Když VPS
#   vypadne, feed by jinak rostl donekonečna; při výpadku agent dostane
#   radši pár zpráv dvakrát než žádné.
PUBLISH_RUN           = os.getenv("PUBLISH_RUN", "0") == "1"
CUTOFF_PATH           = os.getenv("CUTOFF_PATH", "state/cutoff.json")
FEED_WINDOW_MAX_HOURS = float(os.getenv("FEED_WINDOW_MAX_HOURS") or "48")
# Když poslední publikační běh proběhl před víc než touto dobou, ranní
# spuštění z VPS zřejmě vypadlo – feed to hlásí v sources.vps_trigger.
VPS_MISSED_HOURS      = float(os.getenv("VPS_MISSED_HOURS") or "30")

CLAUDE_MODEL   = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")  # levnější varianta: claude-haiku-4-5-20251001

# --- Google News RSS: (dotaz, jazyk hl, země gl) ---
# Pro každý jazyk vlastní dotaz s lokálními termíny pro "Romové".
# U angličtiny/italštiny jsou navíc záporné termíny (-football…), aby vypadla
# fotbalová AS Roma a zeměpisné „Roma" (město Řím, ulice Avinguda Roma apod.).
GOOGLE_NEWS_QUERIES = [
    # Pozn.: české zprávy záměrně nesledujeme – domácí dění si ROMEA pokrývá sama,
    # tento monitoring cílí na Romy VE SVĚTĚ.
    #
    # POZOR: Google News NESKLOŇUJE – hledá přesný tvar slova. U ohebných
    # jazyků proto nestačí základní tvar. Naměřeno 11/2026 (okno 3 dny):
    #   pl  „Romowie"            →  2 zprávy  |  s pádovými tvary → 15
    #   hu  „roma kisebbség…"    → 15         |  s pádovými tvary → 21
    #   ro  „romi OR…"           →  7         |  s pádovými tvary → 20
    #   es  „gitanos OR…"        →  8         |  s rodovými tvary → 26
    # Celkem 70 → 112 zpráv. U neohebných jazyků (en, fr, de) rozšíření nic
    # nepřidalo, termíny navíc jsou tam jen jako pojistka.
    #
    # Maďarské holé „roma" NEPOUŽÍVAT: znamená i Řím a AS Roma, přitáhlo
    # 9 fotbalových zpráv z 26. Tvary „romák…" jsou jednoznačné.
    ('Rómovia OR Rómov OR Rómom OR Rómami OR rómsky OR rómska OR rómske OR rómskych OR Cigáni OR Cigánov', "sk", "SK"),
    ('"Roma minority" OR "Roma people" OR "Roma community" OR "Roma families" OR Romani OR Romanies OR antigypsyism -football -soccer -transfer -Serie', "en", "US"),
    ('"Roma minority" OR "Roma community" OR "Gypsy community" OR Romani OR Romanies OR antigypsyism -football -soccer -transfer -Serie', "en", "GB"),
    ('romák OR romákat OR romáknak OR romákkal OR romákról OR cigány OR cigányok OR cigányokat OR cigányság OR "roma kisebbség" OR "roma közösség"', "hu", "HU"),
    ('romi OR romii OR romilor OR romă OR rome OR ţigani OR ţiganii OR ţiganilor OR "minoritatea romă"', "ro", "RO"),
    ('gitanos OR gitanas OR gitano OR gitana OR "pueblo gitano" OR "comunidad gitana" OR antigitanismo', "es", "ES"),
    ('Roms OR Rroms OR tsiganes OR tziganes OR manouches OR "gens du voyage" OR antitsiganisme', "fr", "FR"),
    ('"Sinti und Roma" OR Antiziganismus OR Romafeindlichkeit OR "Roma-Minderheit" OR "Roma-Familien" OR Sinteza', "de", "DE"),
    ('"rom e sinti" OR "comunità rom" OR "comunità romanì" OR zingari OR antiziganismo -calcio -"AS Roma" -serie', "it", "IT"),
    ('роми OR ромите OR ромски OR ромска OR ромско OR ромските OR цигани OR циганите', "bg", "BG"),
    ('Ρομά OR τσιγγάνοι OR τσιγγάνων OR τσιγγάνους OR γύφτοι OR "μειονότητα Ρομά"', "el", "GR"),
    ('Romowie OR Romów OR Romom OR Romami OR Romach OR romski OR romska OR romskie OR romskich OR Cyganie OR Cyganów', "pl", "PL"),
    ('ciganos OR ciganas OR cigano OR cigana OR "comunidade cigana" OR anticiganismo', "pt", "PT"),
    ('romer OR romerna OR romsk OR romska OR romernas OR zigenare', "sv", "SE"),
    ('romanit OR romaneja OR romanien OR romaneille OR romaniväestö OR mustalaiset', "fi", "FI"),
]
# Pozn.: Balkán (srbština, chorvatština, albánština), Ukrajinu a Turecko
# ZÁMĚRNĚ neřešíme rodnými Google dotazy – tamní kořen „rom/Roman" se sráží
# s „Rom-Com", římskými lázněmi, fotbalem apod. Tyhle země pokrývá líp široký
# GDELT (hledá přes překlad podle významu, ne podle matoucího kořene).

# Operátor Google News „when:" – vrátí jen čerstvé články za zadané období.
# Bez něj Google řadí podle relevance a aktuální zprávy propadnou oknem 13 h.
GOOGLE_NEWS_WHEN = os.getenv("GOOGLE_NEWS_WHEN", "2d")   # rezerva na vynechaný běh, viz LOOKBACK_HOURS

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
    # — Bulharsko —
    ("https://romalo.bg/feed/",                                  "bg"),  # Romalo.bg – aktivní, ~1–2 články týdně
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
    # když je to o Romech.
    #
    # POZOR, TOHLE STÁLO POKRYTÍ (11/2026): Google News NESKLOŇUJE. Hledá
    # přesný tvar slova, takže dotaz „romský OR romská OR romské OR romští"
    # mine „romským", „romského", „romských"… Ověřeno: článek Seznam Zpráv
    # „Romským školám odzvonilo" nenašel původní dotaz vůbec, jen tvar
    # „romským". Čeština má u přídavného jména ~11 tvarů, původní dotaz
    # pokrýval čtyři. Doplnění pádů zvedlo týdenní úlovek ze 44 na 67 zpráv.
    # Každý dotaz má vlastní strop MAX_PER_QUERY, takže rozdělením podle
    # slovního druhu získáme pro romská témata víc místa.
    ('Romové OR Romů OR Romům OR Romy OR Romech OR Romem OR Romovi', "cs", "CZ"),
    ('Romka OR Romky OR Romek OR Romkám OR Romkami OR Romkou',      "cs", "CZ"),
    ('romský OR romského OR romskému OR romském OR romským',        "cs", "CZ"),
    ('romská OR romské OR romskou OR romských OR romskými',         "cs", "CZ"),
    ('romští OR romština OR romštiny OR romštině OR romsky',        "cs", "CZ"),
    ('anticiganismus OR anticikanismus OR protiromský OR cikáni OR cigáni OR cikánů OR cigánů', "cs", "CZ"),
    ('"romská menšina" OR "romské menšiny" OR "romská komunita" OR "romské komunity" OR "romské rodiny" OR "romské děti" OR "romští žáci"', "cs", "CZ"),
    ('"romský holokaust" OR "romského holokaustu" OR "Lety u Písku" OR "Hodonín u Kunštátu" OR Porajmos', "cs", "CZ"),
    # ── VRSTVA 2: témata, která se Romů týkají i bez zmínky ────────
    # Tady je nutná OPATRNOST: volný jednoslovný dotaz („ubytovna",
    # „chudoba") vrátí balast, který spotřebuje celý strop dotazu a vytlačí
    # skutečné trefy. Proto raději konkrétní víceslovné termíny – ale
    # i u nich se musí doplnit pádové tvary, jinak platí totéž co výše.
    # Fráze v uvozovkách hledají PŘESNÉ znění: „segregace ve školách"
    # vracelo 0, protože média píší „segregované školy". Proto u frází
    # raději víc variant, nebo jednoslovný základ.
    ('rasismus OR rasistický OR rasistické OR "rasově motivovaný" OR "rasový motiv"', "cs", "CZ"),
    ('extremismus OR extremisté OR neonacisté OR neonacistický OR "krajní pravice"', "cs", "CZ"),
    ('"předsudečná nenávist" OR "podněcování k nenávisti" OR "hanobení rasy" OR "nenávistné projevy" OR "nenávistných projevů"', "cs", "CZ"),
    ('"vyloučená lokalita" OR "vyloučené lokality" OR "vyloučených lokalit" OR "sociální vyloučení" OR "obchod s chudobou"', "cs", "CZ"),
    ('superdávka OR superdávky OR superdávce OR "dávky na bydlení" OR "příspěvek na bydlení" OR "hmotná nouze"', "cs", "CZ"),
    ('"sociální bydlení" OR "dostupné bydlení" OR "bytová nouze" OR ubytovny OR ubytovnách', "cs", "CZ"),
    ('segregace OR segregované OR segregovaných OR "společné vzdělávání" OR inkluze', "cs", "CZ"),
    ('sterilizační OR "protiprávní sterilizace" OR "sterilizovaných žen" OR "odškodnění sterilizací"', "cs", "CZ"),
    ('diskriminace OR diskriminační OR antidiskriminační',          "cs", "CZ"),
    ('"veřejný ochránce práv" OR ombudsmanka OR ombudsman OR "rovné zacházení"', "cs", "CZ"),
    ('"zmocněnkyně pro romské záležitosti" OR "Rada vlády pro záležitosti romské menšiny" OR "Agentura pro sociální začleňování" OR "Muzeum romské kultury"', "cs", "CZ"),
]

# Obsahové farmy publikující česky a vlastní články ROMEA (ty redakce nepotřebuje
# dostávat zpátky). Filtruje se podle pole `source` až po stažení – viz
# EXCLUDE_SOURCES výše, proč to nejde operátorem v dotazu.
CZ_EXCLUDE_SOURCES = ["vietnam.vn", "romea.cz", "romea",
                      "medium.cz", "médium.cz",          # obsahová farma
                      "měšec.cz", "sreality.cz", "kaufland.cz", "lidé.cz",
                      "facebook.com", "kurzy.cz", "zdopravy.cz",
                      # Agregátor Seznam.cz přebírá cizí obsah včetně článků
                      # ROMEA (jen titulek, perex a diskuze). Filtruje se podle
                      # DOMÉNY, ne názvu zdroje: Google News hlásí zdroj jako
                      # „Seznam – najdu tam, co neznám", takže dřívější přesná
                      # shoda „=Seznam" nikdy nesedla. Doména netrefí
                      # seznamzpravy.cz ani novinky.cz – vlastní redakce
                      # Seznamu tímhle nepadnou. Funguje až po rozbalení adres
                      # Google News (RESOLVE_GN_URLS), kdy je známá skutečná
                      # doména; drop_excluded se proto v gather.py pouští znovu.
                      "www.seznam.cz"]

# ── Obecná zpravodajská média: celý feed + filtr klíčovými slovy ──────
# Doplněk Google News, ne náhrada. Důvod (měřeno 11/2026): GN pro češtinu
# NESKLOŇUJE a některé zprávy nemá vůbec – „Vláda zpochybňuje rozsudek ESLP
# v případu Stanislava Tomáše" ani obvinění 18 lidí po útoku na demonstraci
# ve Frýdku-Místku nenašel GN ani na jméno. Čtení RSS přímo od vydavatele
# tuhle díru zalepí a filtruje se KMENEM slova, takže pády neřeší.
#
# Hloubka feedů kolísá (naměřeno 11/2026): ČT24 59 h, Deník N 58 h, ČTK 79 h,
# A2larm 227 h, Info.cz 123 h – ty denní běh pokryjí. Naopak iRozhlas 4,6 h,
# Novinky 5,9 h, iDNES 6 h, Seznam Zprávy 9,3 h zachytí jen poslední hodiny;
# zbytek jejich produkce musí dohnat Google News. Proto jsou tu obojí.
#
# Echo24 a Deník Referendum na /rss ani /feed nic nevracejí; u Deníku
# Referendum funguje /rss.xml, Echo24 použitelný feed nemá.
CZ_NEWS_FEEDS = [
    ("https://ct24.ceskatelevize.cz/rss/hlavni-zpravy",      "cs"),
    ("https://www.irozhlas.cz/rss/irozhlas",                 "cs"),
    ("https://www.novinky.cz/rss",                           "cs"),
    ("https://servis.idnes.cz/rss.aspx?c=zpravodaj",         "cs"),
    ("https://www.aktualne.cz/rss/",                         "cs"),
    ("https://www.seznamzpravy.cz/rss",                      "cs"),
    ("https://denikn.cz/feed/",                              "cs"),
    ("https://www.ceskenoviny.cz/sluzby/rss/cr.php",         "cs"),  # ČTK
    ("https://www.denik.cz/rss/zpravy.html",                 "cs"),
    ("https://a2larm.cz/feed/",                              "cs"),
    ("https://www.forum24.cz/feed/",                         "cs"),
    ("https://denikreferendum.cz/rss.xml",                   "cs"),
    ("https://hlidacipes.org/feed/",                         "cs"),
    ("https://www.blesk.cz/rss",                             "cs"),
    ("https://www.e15.cz/rss",                               "cs"),
    ("https://www.info.cz/rss",                              "cs"),
]

# KMENY slov, ne celá slova: „romsk" chytí romský/romská/romských/romským…
# Tohle je výhoda proti Google News, který umí jen přesné tvary.
# POZOR na krátké kmeny: holé „rom" by chytalo Roman, román i romantický,
# proto jsou tu jen tvary, které nejdou splést (ověřeno testem).
CZ_FEED_TERMS = [
    # vrstva 1 – je to o Romech
    "romov", "romsk", "romštin", "romští", "romů", "romům", "romy",
    "romech", "romem", "romovi", "romk", "cikán", "cigán",
    "anticiganis", "anticikanis",
    # vrstva 2 – témata, která se Romů týkají i bez zmínky
    "segregac", "segregovan", "superdávk", "ubytovn", "rasis", "neonacis",
    "extremis", "holokaust", "steriliz", "předsudečn", "ghett", "inkluz",
    "vyloučená lokalit", "vyloučené lokalit", "vyloučených lokalit",
    "sociální vyloučen", "sociální bydlen", "bytová nouz", "hmotné nouzi",
    "hmotná nouze", "hanobení rasy", "podněcování k nenávisti",
    "obchod s chudobou", "rasově motivovan",
]

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
    NEWS_FEEDS          = CZ_NEWS_FEEDS
    FEED_TERMS          = CZ_FEED_TERMS
    WATCH_SITES         = CZ_WATCH_SITES
    WATCH_SITE_TERMS    = CZ_WATCH_SITE_TERMS
    GDELT_ENABLED       = False   # u domácího zpravodajství nepřidá nic navíc
    # Strop 14 uřezával relevantní zprávy, jakmile se dotazy rozšířily
    # o pádové tvary: u „extremismus…" padaly pod stůl 4 položky a mezi nimi
    # zpráva ČT24 o střelbě v Krakově. 20 dá prostor i dotazům, kde se vedle
    # trefy sveze balast (ten dotřídí agent, viz zásada recall > precision).
    MAX_PER_QUERY       = int(os.getenv("MAX_PER_QUERY", "20"))
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
