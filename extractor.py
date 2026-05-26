import json
import re
import os
from datetime import datetime
from rss_ingestion import fetch_articles, deduplicate_articles

DEBUG = True
MIN_SCORE = 3
DATASET_FILE = "polis_lse_dataset.json"

def log(msg):
    if DEBUG:
        print(msg)

# =========================================================
# ACTOR REGISTRY — Named presidents only
# =========================================================
ACTOR_REGISTRY = [
    ("tebboune",            "presidential", "Algeria"),
    ("sisi",                "presidential", "Egypt"),
    ("el-sisi",             "presidential", "Egypt"),
    ("menfi",               "presidential", "Libya"),
    ("dbeibah",             "presidential", "Libya"),
    ("mohammed vi",         "presidential", "Morocco"),
    ("king mohammed",       "presidential", "Morocco"),
    ("al-burhan",           "presidential", "Sudan"),
    ("burhan",              "presidential", "Sudan"),
    ("saied",               "presidential", "Tunisia"),
    ("talon",               "presidential", "Benin"),
    ("traore",              "presidential", "Burkina Faso"),
    ("neves",               "presidential", "Cape Verde"),
    ("ouattara",            "presidential", "Cote d Ivoire"),
    ("barrow",              "presidential", "Gambia"),
    ("mahama",              "presidential", "Ghana"),
    ("doumbouya",           "presidential", "Guinea"),
    ("boakai",              "presidential", "Liberia"),
    ("goita",               "presidential", "Mali"),
    ("ghazouani",           "presidential", "Mauritania"),
    ("tchiani",             "presidential", "Niger"),
    ("tinubu",              "presidential", "Nigeria"),
    ("faye",                "presidential", "Senegal"),
    ("bio",                 "presidential", "Sierra Leone"),
    ("gnassingbe",          "presidential", "Togo"),
    ("lourenco",            "presidential", "Angola"),
    ("joao lourenco",       "presidential", "Angola"),
    ("biya",                "presidential", "Cameroon"),
    ("touadera",            "presidential", "Central African Republic"),
    ("deby",                "presidential", "Chad"),
    ("mahamat deby",        "presidential", "Chad"),
    ("tshisekedi",          "presidential", "DRC"),
    ("nguema mbasogo",      "presidential", "Equatorial Guinea"),
    ("oligui nguema",       "presidential", "Gabon"),
    ("sassou nguesso",      "presidential", "Republic of Congo"),
    ("vila nova",           "presidential", "Sao Tome and Principe"),
    ("ndayishimiye",        "presidential", "Burundi"),
    ("assoumani",           "presidential", "Comoros"),
    ("guelleh",             "presidential", "Djibouti"),
    ("afwerki",             "presidential", "Eritrea"),
    ("abiy ahmed",          "presidential", "Ethiopia"),
    ("abiy",                "presidential", "Ethiopia"),
    ("ruto",                "presidential", "Kenya"),
    ("randrianirina",       "presidential", "Madagascar"),
    ("mutharika",           "presidential", "Malawi"),
    ("gokhool",             "presidential", "Mauritius"),
    ("chapo",               "presidential", "Mozambique"),
    ("kagame",              "presidential", "Rwanda"),
    ("ramkalawan",          "presidential", "Seychelles"),
    ("mohamud",             "presidential", "Somalia"),
    ("hassan sheikh",       "presidential", "Somalia"),
    ("salva kiir",          "presidential", "South Sudan"),
    ("kiir",                "presidential", "South Sudan"),
    ("samia",               "presidential", "Tanzania"),
    ("hassan",              "presidential", "Tanzania"),
    ("museveni",            "presidential", "Uganda"),
    ("boko",                "presidential", "Botswana"),
    ("duma boko",           "presidential", "Botswana"),
    ("mswati",              "presidential", "Eswatini"),
    ("letsie",              "presidential", "Lesotho"),
    ("lerotholi",           "presidential", "Lesotho"),
    ("mbumba",              "presidential", "Namibia"),
    ("ramaphosa",           "presidential", "South Africa"),
    ("hichilema",           "presidential", "Zambia"),
    ("mnangagwa",           "presidential", "Zimbabwe"),
    # Specific presidential office phrases only
    ("state house",         "presidential", None),
    ("presidency",          "presidential", None),
    ("president ordered",   "presidential", None),
    ("president directed",  "presidential", None),
    ("president signed",    "presidential", None),
    ("president appointed", "presidential", None),
    ("president dismissed", "presidential", None),
    ("president launched",  "presidential", None),
    ("president declared",  "presidential", None),
    ("president announced", "presidential", None),
    ("president warned",    "presidential", None),
    ("president said",      "presidential", None),
    ("president confirmed", "presidential", None),
    ("president called",    "presidential", None),
    ("president orders",    "presidential", None),
    ("president directs",   "presidential", None),
    ("president hails",     "presidential", None),
    ("president urges",     "presidential", None),
    ("president meets",     "presidential", None),
    ("president visits",    "presidential", None),
    ("president chairs",    "presidential", None),
    ("president presides",  "presidential", None),
]

ACTOR_COUNTRIES = {
    "ramaphosa": "South Africa", "tinubu": "Nigeria", "ruto": "Kenya",
    "mahama": "Ghana", "museveni": "Uganda", "hichilema": "Zambia",
    "mnangagwa": "Zimbabwe", "mbumba": "Namibia", "kagame": "Rwanda",
    "tshisekedi": "DRC", "kiir": "South Sudan", "salva kiir": "South Sudan",
    "hassan": "Tanzania", "samia": "Tanzania", "abiy": "Ethiopia",
    "abiy ahmed": "Ethiopia", "sisi": "Egypt", "el-sisi": "Egypt",
    "barrow": "Gambia", "faye": "Senegal", "chapo": "Mozambique",
    "boko": "Botswana", "duma boko": "Botswana", "talon": "Benin",
    "ouattara": "Cote d Ivoire", "tebboune": "Algeria",
    "menfi": "Libya", "dbeibah": "Libya",
    "mohammed vi": "Morocco", "king mohammed": "Morocco",
    "al-burhan": "Sudan", "burhan": "Sudan", "saied": "Tunisia",
    "traore": "Burkina Faso", "neves": "Cape Verde",
    "doumbouya": "Guinea", "boakai": "Liberia", "goita": "Mali",
    "ghazouani": "Mauritania", "tchiani": "Niger",
    "bio": "Sierra Leone", "gnassingbe": "Togo",
    "lourenco": "Angola", "joao lourenco": "Angola", "biya": "Cameroon",
    "touadera": "Central African Republic", "deby": "Chad",
    "mahamat deby": "Chad", "nguema mbasogo": "Equatorial Guinea",
    "oligui nguema": "Gabon", "sassou nguesso": "Republic of Congo",
    "vila nova": "Sao Tome and Principe", "ndayishimiye": "Burundi",
    "assoumani": "Comoros", "guelleh": "Djibouti", "afwerki": "Eritrea",
    "randrianirina": "Madagascar", "mutharika": "Malawi",
    "gokhool": "Mauritius", "ramkalawan": "Seychelles",
    "mohamud": "Somalia", "hassan sheikh": "Somalia",
    "letsie": "Lesotho", "lerotholi": "Lesotho", "mswati": "Eswatini",
}

COUNTRY_KEYWORDS = {
    "Algeria":    ["algeria","algerian","algiers"],
    "Egypt":      ["egypt","egyptian","cairo"],
    "Libya":      ["libya","libyan","tripoli","benghazi"],
    "Morocco":    ["morocco","moroccan","rabat","casablanca"],
    "Sudan":      ["sudan","sudanese","khartoum"],
    "Tunisia":    ["tunisia","tunisian","tunis"],
    "Benin":      ["benin","beninese","cotonou"],
    "Burkina Faso":["burkina","burkinabe","ouagadougou"],
    "Cape Verde": ["cape verde","cabo verde"],
    "Cote d Ivoire":["ivory coast","cote d'ivoire","abidjan","ivorian"],
    "Gambia":     ["gambia","gambian","banjul"],
    "Ghana":      ["ghana","ghanaian","accra"],
    "Guinea":     ["guinea","guinean","conakry"],
    "Guinea-Bissau":["guinea-bissau","bissau"],
    "Liberia":    ["liberia","liberian","monrovia"],
    "Mali":       ["mali","malian","bamako"],
    "Mauritania": ["mauritania","mauritanian","nouakchott"],
    "Niger":      ["niger","nigerien","niamey"],
    "Nigeria":    ["nigeria","nigerian","abuja","lagos"],
    "Senegal":    ["senegal","senegalese","dakar"],
    "Sierra Leone":["sierra leone","freetown"],
    "Togo":       ["togo","togolese","lome"],
    "Angola":     ["angola","angolan","luanda"],
    "Cameroon":   ["cameroon","cameroonian","yaounde"],
    "Central African Republic":["central african","bangui"],
    "Chad":       ["chad","chadian","ndjamena"],
    "DRC":        ["congo","drc","kinshasa","congolese"],
    "Equatorial Guinea":["equatorial guinea","malabo"],
    "Gabon":      ["gabon","gabonese","libreville"],
    "Republic of Congo":["republic of congo","brazzaville"],
    "Sao Tome and Principe":["sao tome","são tomé"],
    "Burundi":    ["burundi","burundian","bujumbura"],
    "Comoros":    ["comoros","comorian","moroni"],
    "Djibouti":   ["djibouti","djiboutian"],
    "Eritrea":    ["eritrea","eritrean","asmara"],
    "Ethiopia":   ["ethiopia","ethiopian","addis ababa","addis"],
    "Kenya":      ["kenya","kenyan","nairobi"],
    "Madagascar": ["madagascar","malagasy","antananarivo"],
    "Malawi":     ["malawi","malawian","lilongwe"],
    "Mauritius":  ["mauritius","mauritian","port louis"],
    "Mozambique": ["mozambique","mozambican","maputo"],
    "Rwanda":     ["rwanda","rwandan","kigali"],
    "Seychelles": ["seychelles","seychellois","victoria"],
    "Somalia":    ["somalia","somali","mogadishu"],
    "South Sudan":["south sudan","juba"],
    "Tanzania":   ["tanzania","tanzanian","dar es salaam","dodoma"],
    "Uganda":     ["uganda","ugandan","kampala"],
    "Botswana":   ["botswana","batswana","gaborone"],
    "Eswatini":   ["eswatini","swaziland","mbabane"],
    "Lesotho":    ["lesotho","basotho","maseru"],
    "Namibia":    ["namibia","namibian","windhoek"],
    "South Africa":["south africa","south african","pretoria","cape town","johannesburg"],
    "Zambia":     ["zambia","zambian","lusaka"],
    "Zimbabwe":   ["zimbabwe","zimbabwean","harare"],
}

# =========================================================
# FIX 3: MULTILINGUAL KEYWORD EXPANSION
# French and Arabic keywords for domain classification
# =========================================================
MULTILINGUAL_DOMAIN_KEYWORDS = {
    "governance": ["ministre","cabinet","parlement","gouvernement","décret",
                   "nommé","nommer","limoger","démissionner","conseil des ministres",
                   "وزير","حكومة","برلمان","مرسوم","تعيين","إقالة"],
    "economy":    ["économie","budget","investissement","infrastructure","milliard",
                   "اقتصاد","ميزانية","استثمار","بنية تحتية","مليار"],
    "security":   ["sécurité","armée","militaire","terrorisme","conflit",
                   "أمن","جيش","عسكري","إرهاب","نزاع"],
    "diplomacy":  ["sommet","accord","bilatéral","délégation","visite officielle",
                   "قمة","اتفاقية","ثنائي","وفد","زيارة رسمية"],
    "health":     ["santé","hôpital","vaccin","maladie","صحة","مستشفى","لقاح","مرض"],
    "education":  ["éducation","école","université","étudiant","تعليم","مدرسة","جامعة"],
    "community":  ["dialogue","consultation","inclusive","indaba","حوار","تشاور","شامل"],
    "justice":    ["tribunal","justice","corruption","condamné","محكمة","عدالة","فساد"],
}

ACTION_REGISTRY = [
    (r"\bappointed?\b",             "appointment",          3),
    (r"\bnommé\b",                  "appointment",          3),  # French
    (r"\bsworn.in\b",               "appointment",          3),
    (r"\bnominated?\b",             "appointment",          2),
    (r"\bdismissed?\b",             "dismissal",            3),
    (r"\blimoger\b",                "dismissal",            3),  # French
    (r"\bsacked?\b",                "dismissal",            3),
    (r"\bfired?\b",                 "dismissal",            3),
    (r"\bsuspended?\b",             "dismissal",            2),
    (r"\bresigned?\b",              "dismissal",            2),
    (r"\bsigned?\b",                "policy",               2),
    (r"\bapproved?\b",              "policy",               2),
    (r"\blaunched?\b",              "policy",               2),
    (r"\blancé\b",                  "policy",               2),  # French
    (r"\benacted?\b",               "policy",               3),
    (r"\borders?\b",                "policy",               2),
    (r"\bdirected?\b",              "policy",               2),
    (r"\bbanned?\b",                "policy",               2),
    (r"\bpassed?\b",                "policy",               2),
    (r"\ballocated?\b",             "policy",               2),
    (r"\bdeployed?\b",              "policy",               2),
    (r"\bannounced?\b",             "public_statement",     1),
    (r"\bdéclare\b",                "public_statement",     2),  # French
    (r"\bdeclared?\b",              "public_statement",     2),
    (r"\bwarned?\b",                "public_statement",     2),
    (r"\bcalled? for\b",            "public_statement",     2),
    (r"\bsays?\b",                  "public_statement",     1),
    (r"\bconfirmed?\b",             "public_statement",     1),
    (r"\bstatement\b",              "public_statement",     1),
    (r"\baddressed?\b",             "public_statement",     1),
    (r"\bhails?\b",                 "public_statement",     1),
    (r"\burges?\b",                 "public_statement",     1),
    (r"\bruled?\b",                 "judicial_ruling",      3),
    (r"\bverdict\b",                "judicial_ruling",      3),
    (r"\bconvicted?\b",             "judicial_ruling",      3),
    (r"\bsentenced?\b",             "judicial_ruling",      3),
    (r"\bacquitted?\b",             "judicial_ruling",      3),
    (r"\barrested?\b",              "enforcement",          2),
    (r"\bcharged?\b",               "enforcement",          2),
    (r"\binvestigated?\b",          "enforcement",          2),
    (r"\bprosecuted?\b",            "enforcement",          2),
    # Ubuntu signals
    (r"\bdialogue\b",               "community_engagement", 3),
    (r"\bindaba\b",                 "community_engagement", 3),
    (r"\bharambee\b",               "community_engagement", 3),
    (r"\bubuntu\b",                 "community_engagement", 3),
    (r"\bconsultative\b",           "community_engagement", 3),
    (r"\btown.?hall\b",             "community_engagement", 2),
    (r"\binclusive\b",              "community_engagement", 2),
    (r"\bconsulted?\b",             "community_engagement", 2),
    (r"\bparticipat\w+\b",          "community_engagement", 2),
]

COMPILED_ACTIONS = [
    (re.compile(pat, re.IGNORECASE), action_type, weight)
    for pat, action_type, weight in ACTION_REGISTRY
]

NOISE_PATTERNS = [
    re.compile(r"\bfootball\b"),
    re.compile(r"\bafcon\b"),
    re.compile(r"\bworld cup\b"),
    re.compile(r"\bpremier league\b"),
    re.compile(r"\bcar.?crash\b"),
    re.compile(r"\bcar.?ramming\b"),
    re.compile(r"\brape\b"),
    re.compile(r"\bkidnap\w+\b"),
    re.compile(r"\bsowore\b"),
    re.compile(r"\bmacron\b"),
    re.compile(r"\bopposition.{0,20}rallies\b"),
    re.compile(r"\bmust resign\b"),
    re.compile(r"\bfaces call.{0,10}resign\b"),
    re.compile(r"\bcalls.{0,10}resign\b"),
    re.compile(r"\bpressure mounts\b"),
    re.compile(r"\bactivist\b"),
]

NOISE_GLOBAL = [
    "athletics", "formula one", "formula 1", "grand prix",
    "champions league", "nba", "cricket", "wrestling title",
    "trump", "ukraine", "hezbollah", "israel strikes",
    "hormuz", "us warship", "irgc", "iran navy",
    "jordan launches", "china sentences", "china orders",
    "south korean court", "french court", "french appeals",
    "hantavirus", "epstein", "obama offers", "alien visitors",
    "bolivian police", "sebastian coe", "kodak black",
    "baby hippo", "tuna day", "miss youth",
    "opposition coalition rallies", "must resign",
    "faces call to resign", "calls to resign",
]

STATE_CONTROLLED_FEEDS = {
    "https://www.herald.co.zw/feed/",
    "https://www.cameroon-tribune.cm/rss.xml",
    "https://www.crtv.cm/feed/",
    "https://www.angop.ao/noticias/rss.xml",
    "https://www.dailynews.co.tz/feed/",
}

# =========================================================
# FIX 3: EXPANDED DOMAIN MAP WITH MULTILINGUAL SUPPORT
# =========================================================
DOMAIN_MAP = {
    "security":   ["security","army","military","terror","attack","weapon","coup",
                   "insurgent","conflict","defence","defense","boko haram","al-shabaab",
                   "armed forces","ceasefire","peacekeeping","sovereignty","troop",
                   "sécurité","armée","militaire","أمن","جيش"],
    "economy":    ["economy","budget","fund","tax","revenue","inflation","finance",
                   "trade","investment","loan","debt","imf","gdp","infrastructure",
                   "railway","road","energy","power","electricity","gas","oil",
                   "housing","construction","contract","procurement","billion","million",
                   "économie","investissement","milliard","اقتصاد","استثمار","مليار"],
    "justice":    ["court","law","justice","verdict","sentence","ruling","convict",
                   "acquit","tribunal","corruption","fraud","prosecution","impeach",
                   "accountability","anti-corruption","laundering","charges","criminal",
                   "tribunal","justice","corruption","condamné","محكمة","فساد"],
    "health":     ["health","hospital","disease","medical","vaccine","clinic",
                   "pandemic","cholera","malaria","maternal","childbirths",
                   "santé","hôpital","vaccin","صحة","مستشفى","لقاح"],
    "education":  ["education","school","university","student","curriculum","teacher",
                   "scholarship","digitisation","learner","academic",
                   "éducation","école","université","تعليم","مدرسة"],
    "governance": ["minister","appoint","cabinet","dismiss","parliament","senate",
                   "government","presidency","constitution","reform","restructure",
                   "policy","legislation","bill","decree","executive","reshuffle",
                   "ministre","parlement","gouvernement","décret","نomme","وزير","حكومة"],
    "elections":  ["election","vote","ballot","campaign","electoral","polling",
                   "by-election","candidate","gubernatorial"],
    "diplomacy":  ["diplomatic","bilateral","summit","treaty","agreement","foreign",
                   "embassy","delegation","visit","cooperation","ambassador",
                   "partnership","multilateral","african union","ecowas",
                   "sommet","accord","bilatéral","délégation","قمة","اتفاقية"],
    "community":  ["community","citizens","dialogue","consultation","indaba",
                   "harambee","ubuntu","grassroots","participat","town hall",
                   "inclusive","stakeholder","civil society","public engagement",
                   "dialogue","consultation","حوار","تشاور"],
    "media":      ["press freedom","journalist","media","censored","broadcast",
                   "freedom of expression","disinformation"],
}

def detect_domain(text: str) -> str:
    t = text.lower()
    scores = {}
    for domain, keywords in DOMAIN_MAP.items():
        scores[domain] = sum(1 for k in keywords if k in t)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"

FRAMING_MAP = {
    "crisis":         ["crisis","emergency","urgent","threat","collapse","attack",
                       "conflict","war","coup","unrest","protest","crackdown"],
    "reform":         ["reform","restructure","overhaul","new policy","initiative",
                       "transformation","strategy","vision","agenda","revamp"],
    "legitimacy":     ["constitution","legal","ruling","mandate","authority",
                       "sovereign","rights","democracy","impeach"],
    "accountability": ["corruption","arrest","probe","investigate","dismiss",
                       "suspend","sanction","convict","audit","fraud"],
    "development":    ["invest","build","infrastructure","growth","development",
                       "fund","launch","programme","project","railway","road",
                       "housing","electricity","energy"],
    "diplomacy":      ["summit","treaty","bilateral","foreign","delegation",
                       "agreement","visit","cooperation","ambassador"],
    "community":      ["community","citizens","dialogue","consultation","indaba",
                       "harambee","ubuntu","inclusive"],
}

def detect_framing(text: str) -> str:
    t = text.lower()
    scores = {f: sum(1 for k in kws if k in t) for f, kws in FRAMING_MAP.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "neutral"

CURRENT_PRESIDENTS = {
    "Algeria": "Tebboune", "Egypt": "Sisi", "Libya": "Menfi",
    "Morocco": "Mohammed VI", "Sudan": "al-Burhan", "Tunisia": "Saied",
    "Benin": "Talon", "Burkina Faso": "Traore", "Cape Verde": "Neves",
    "Cote d Ivoire": "Ouattara", "Gambia": "Barrow", "Ghana": "Mahama",
    "Guinea": "Doumbouya", "Guinea-Bissau": "Horta", "Liberia": "Boakai",
    "Mali": "Goita", "Mauritania": "Ghazouani", "Niger": "Tchiani",
    "Nigeria": "Tinubu", "Senegal": "Faye", "Sierra Leone": "Bio",
    "Togo": "Gnassingbe", "Angola": "Lourenco", "Cameroon": "Biya",
    "Central African Republic": "Touadera", "Chad": "Deby",
    "DRC": "Tshisekedi", "Equatorial Guinea": "Nguema",
    "Gabon": "Oligui Nguema", "Republic of Congo": "Sassou Nguesso",
    "Sao Tome and Principe": "Vila Nova", "Burundi": "Ndayishimiye",
    "Comoros": "Assoumani", "Djibouti": "Guelleh", "Eritrea": "Afwerki",
    "Ethiopia": "Abiy", "Kenya": "Ruto", "Madagascar": "Randrianirina",
    "Malawi": "Mutharika", "Mauritius": "Gokhool", "Mozambique": "Chapo",
    "Rwanda": "Kagame", "Seychelles": "Ramkalawan", "Somalia": "Mohamud",
    "South Sudan": "Kiir", "Tanzania": "Hassan", "Uganda": "Museveni",
    "Botswana": "Boko", "Eswatini": "Mswati III", "Lesotho": "Lerotholi",
    "Namibia": "Mbumba", "South Africa": "Ramaphosa", "Zambia": "Hichilema",
    "Zimbabwe": "Mnangagwa",
}

# FIX 2: Feed count per country for coverage normalisation
FEED_COUNTS = {
    "Nigeria": 5, "Kenya": 5, "Ghana": 4, "South Africa": 5,
    "Tanzania": 3, "Uganda": 3, "Zambia": 3, "Zimbabwe": 4,
    "Ethiopia": 2, "Morocco": 3, "Egypt": 3, "Gambia": 3,
    "South Sudan": 2, "DRC": 3, "Rwanda": 2, "Mozambique": 2,
    "Algeria": 3, "Senegal": 2, "Malawi": 2, "Namibia": 2,
    "Botswana": 2, "Libya": 1, "Tunisia": 2, "Sudan": 2,
    "Gabon": 2, "Cameroon": 2, "Angola": 2, "Liberia": 2,
    "Mali": 2, "Burkina Faso": 2, "Niger": 2, "Chad": 2,
    "Togo": 2, "Benin": 3, "Mauritania": 2, "Guinea": 2,
    "Sierra Leone": 2, "Cote d Ivoire": 2, "Somalia": 2,
    "Burundi": 1, "Comoros": 1, "Djibouti": 1, "Eritrea": 0,
    "Madagascar": 1, "Mauritius": 2, "Seychelles": 2,
    "Cape Verde": 1, "Guinea-Bissau": 0, "Equatorial Guinea": 0,
    "Republic of Congo": 1, "Sao Tome and Principe": 1,
    "Eswatini": 2, "Lesotho": 2,
}

def resolve_president(country: str) -> str:
    return CURRENT_PRESIDENTS.get(country, "")

def get_feed_count(country: str) -> int:
    return FEED_COUNTS.get(country, 1)

def extract_actor(text: str):
    t = text.lower()
    for phrase, actor_type, country_hint in ACTOR_REGISTRY:
        if re.search(r"\b" + re.escape(phrase) + r"\b", t):
            return phrase, actor_type, country_hint
    return None, None, None

def extract_action(text: str):
    best_type, best_weight = None, 0
    t = text.lower()
    for compiled, action_type, weight in COMPILED_ACTIONS:
        if compiled.search(t) and weight > best_weight:
            best_type, best_weight = action_type, weight
    return best_type, best_weight

def is_noisy(text: str) -> bool:
    t = text.lower()
    if any(p.search(t) for p in NOISE_PATTERNS): return True
    if any(n in t for n in NOISE_GLOBAL): return True
    return False

def country_is_relevant(text: str, country: str, source_tier: str) -> bool:
    if source_tier == "T0": return True
    keywords = COUNTRY_KEYWORDS.get(country, [])
    if not keywords: return True
    return any(k in text.lower() for k in keywords)

def actor_matches_country(actor: str, country: str) -> bool:
    expected = ACTOR_COUNTRIES.get(actor)
    if expected and expected != country:
        return False
    return True

def score_event(text, actor, action_type, action_weight, source_tier, source_bias):
    score = 0
    if actor:          score += 2
    if action_type:    score += 1 + action_weight
    if not is_noisy(text): score += 1
    if source_tier == "T1":  score += 1
    if source_bias == "state": score -= 1
    return score

def parse_date(published: str) -> str:
    for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"]:
        try:
            return datetime.strptime(published.strip(), fmt).strftime("%Y-%m-%d")
        except: continue
    return datetime.today().strftime("%Y-%m-%d")

def get_week(date_str):
    try: return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-W%W")
    except: return "unknown"

def get_month(date_str):
    try: return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m")
    except: return "unknown"

def process_article(article: dict) -> dict:
    raw_text = article.get("title", "") + " " + article.get("summary", "")
    text = raw_text.lower()

    if is_noisy(text):
        return {"is_leadership_event": False}

    actor, actor_type, country_hint = extract_actor(text)
    action_type, action_weight = extract_action(text)
    source_tier  = article.get("source_tier", "T2")
    source_bias  = article.get("source_bias", "independent")
    feed_url     = article.get("source_feed", "")
    country      = article.get("country", country_hint or "")

    if feed_url in STATE_CONTROLLED_FEEDS:
        source_bias = "state"

    if not country_is_relevant(raw_text, country, source_tier):
        log("  [SKIP cross-tag] " + article.get("title","")[:55])
        return {"is_leadership_event": False}

    if not actor or not action_type:
        return {"is_leadership_event": False}

    if not actor_matches_country(actor, country):
        log("  [SKIP actor mismatch] " + actor + " / " + country)
        return {"is_leadership_event": False}

    score = score_event(text, actor, action_type, action_weight, source_tier, source_bias)

    if score < MIN_SCORE:
        return {"is_leadership_event": False}

    import hashlib
    president = resolve_president(country)
    evidence  = article.get("title", "")[:140]
    date_str  = parse_date(article.get("published", ""))
    domain    = detect_domain(evidence)
    framing   = detect_framing(evidence)

    # Stable event_id — consistent with reviewer v3 matching logic
    event_id  = hashlib.sha256(
        (evidence + country).encode("utf-8")
    ).hexdigest()[:16]

    log("  [LSE] " + action_type + " | " + domain
        + " | " + country + " | " + evidence[:45])

    return {
        # --- Identity ---
        "is_leadership_event":  True,
        "event_id":             event_id,
        "date":                 date_str,
        "week":                 get_week(date_str),
        "month":                get_month(date_str),
        # --- Actor ---
        "country":              country,
        "president":            president,
        "actor":                actor,
        "actor_type":           actor_type,
        # --- Action ---
        "action_type":          action_type,
        "domain":               domain,
        "framing":              framing,
        # --- Signal quality ---
        "filter_score":         score,
        "source_tier":          source_tier,
        "source_bias":          source_bias,
        "feed_count":           get_feed_count(country),
        # --- Evidence ---
        "context":              "governance",
        "evidence":             evidence,
        "link":                 article.get("link", ""),
        # --- Dimension scoring (populated by llm_reviewer_v3.py) ---
        "dimensions":           {
            "accountability":        {"score": None, "confidence": None},
            "responsiveness":        {"score": None, "confidence": None},
            "stewardship":           {"score": None, "confidence": None},
            "institutional_integrity": {"score": None, "confidence": None},
            "inclusion":             {"score": None, "confidence": None},
        },
        "rationale":            None,
        "needs_scoring":        True,
    }

def load_existing() -> list:
    if not os.path.exists(DATASET_FILE):
        return []
    with open(DATASET_FILE, "r") as f:
        existing = json.load(f)
    import hashlib
    # Support both flat array (legacy) and metadata-wrapped structure
    if isinstance(existing, dict) and "events" in existing:
        existing = existing["events"]
    events = [e for e in existing if e.get("is_leadership_event")]
    for e in events:
        # Backfill structural fields for legacy events
        if "framing"     not in e: e["framing"]     = detect_framing(e.get("evidence",""))
        if "week"        not in e: e["week"]         = get_week(e.get("date",""))
        if "month"       not in e: e["month"]        = get_month(e.get("date",""))
        if "source_bias" not in e: e["source_bias"]  = "independent"
        if "feed_count"  not in e: e["feed_count"]   = get_feed_count(e.get("country",""))

        # Backfill event_id for legacy events lacking it
        if "event_id" not in e:
            raw = (e.get("evidence","") + e.get("country","")).encode("utf-8")
            e["event_id"] = hashlib.sha256(raw).hexdigest()[:16]

        # Backfill dimension placeholder for legacy events not yet scored
        if "dimensions" not in e:
            e["dimensions"] = {
                "accountability":          {"score": None, "confidence": None},
                "responsiveness":          {"score": None, "confidence": None},
                "stewardship":             {"score": None, "confidence": None},
                "institutional_integrity": {"score": None, "confidence": None},
                "inclusion":               {"score": None, "confidence": None},
            }
            e["needs_scoring"] = True

        # Re-detect domain for events stuck on general
        if e.get("domain") == "general":
            new_domain = detect_domain(e.get("evidence",""))
            if new_domain != "general":
                e["domain"] = new_domain

        # Keep president names current
        correct = resolve_president(e.get("country",""))
        if correct: e["president"] = correct

    return events

def update_metadata(data: dict, combined: list) -> dict:
    """
    Update the metadata block on every run.
    Keeps dataset stats current without manual intervention.
    """
    import hashlib
    from datetime import datetime, timezone

    if not isinstance(data, dict):
        # Legacy flat array — wrap it
        data = {"metadata": {}, "events": data}

    if "metadata" not in data:
        data["metadata"] = {}

    m = data["metadata"]

    # Always update
    m["polis_version"]      = "8.0"
    m["dataset_version"]    = m.get("dataset_version", "1.0")
    m["last_updated"]       = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    m["extractor_version"]  = "v8"
    m["reviewer_version"]   = "v3.0"
    m["scoring_model"]      = "claude-sonnet-4-20250514"

    if "theoretical_framework" not in m:
        m["theoretical_framework"] = {
            "primary":    "Principal-agent theory",
            "supporting": "Public leadership literature",
            "contextual": "Neopatrimonialism (Bratton & van de Walle)"
        }

    if "dimensions" not in m:
        m["dimensions"] = [
            "accountability", "responsiveness", "stewardship",
            "institutional_integrity", "inclusion"
        ]

    if "analytic_tensions" not in m:
        m["analytic_tensions"] = [
            "formal_institutions_vs_informal_power",
            "centralisation_vs_accommodation",
            "visibility_vs_action"
        ]

    # Recompute stats from current dataset
    lse = [e for e in combined if e.get("is_leadership_event")]
    countries = list(set(e.get("country","") for e in lse))
    presidents = list(set(e.get("president","") for e in lse if e.get("president")))
    domains = {}
    for e in lse:
        d = e.get("domain","general")
        domains[d] = domains.get(d,0) + 1
    scored = sum(1 for e in lse if any(
        e.get("dimensions",{}).get(dim,{}).get("score") is not None
        for dim in ["accountability","responsiveness","stewardship",
                    "institutional_integrity","inclusion"]
    ))

    m["geographic_scope"] = {
        "target_countries":   54,
        "covered_countries":  len(countries),
        "regions": ["North Africa","West Africa","Central Africa",
                    "East Africa","Southern Africa"]
    }

    m["dataset_stats"] = {
        "total_events":        len(combined),
        "leadership_events":   len(lse),
        "scored_events":       scored,
        "needs_scoring":       sum(1 for e in lse if e.get("needs_scoring")),
        "countries_with_data": len(countries),
        "presidents_tracked":  len(presidents),
        "domain_distribution": domains
    }

    if "observability_note" not in m:
        m["observability_note"] = (
            "Scores reflect observable signals in reported news events, "
            "not governance outcomes. Absence of signal is not evidence "
            "of absence of behaviour. Countries with fewer than 30 events "
            "should be interpreted with caution."
        )

    if "citation" not in m:
        m["citation"] = (
            "POLIS - Public Leadership Observation & Insight System. "
            "Change-alongside, 2026. https://polis-dashboard.streamlit.app"
        )

    data["metadata"] = m
    return data


def save_cumulative(new_results: list):
    existing       = load_existing()
    existing_links = set(e.get("link","")     for e in existing)
    existing_evid  = set(e.get("evidence","") for e in existing)

    new_events = [
        r for r in new_results
        if r.get("is_leadership_event")
        and r.get("link","")     not in existing_links
        and r.get("evidence","") not in existing_evid
    ]

    combined = existing + new_events
    # Wrap in metadata structure and update stats
    wrapped = update_metadata({"events": combined}, combined)

    with open(DATASET_FILE, "w") as f:
        json.dump(wrapped, f, indent=2, ensure_ascii=False)

    domains  = {}
    needs_scoring = 0
    scored = 0
    for e in combined:
        d = e.get("domain","general")
        domains[d] = domains.get(d,0) + 1
        if e.get("needs_scoring"):
            needs_scoring += 1
        if "dimensions" in e and any(
            e["dimensions"].get(dim,{}).get("score") is not None
            for dim in ["accountability","responsiveness","stewardship",
                        "institutional_integrity","inclusion"]
        ):
            scored += 1

    print("=" * 55)
    print("NEW EVENTS ADDED:   " + str(len(new_events)))
    print("TOTAL IN DATASET:   " + str(len(combined)))
    print("SCORED EVENTS:      " + str(scored))
    print("NEEDS SCORING:      " + str(needs_scoring))
    print("\nDOMAIN BREAKDOWN:")
    for d, c in sorted(domains.items(), key=lambda x: -x[1]):
        print("  {:<15} {:>4}".format(d, c))
    print("\nRun llm_reviewer_v3.py to score pending events.")

def main():
    print("=" * 60)
    print("POLIS EXTRACTOR v8 — DIMENSION SCHEMA · 54 COUNTRIES")
    print("=" * 60)
    articles = fetch_articles()
    articles = deduplicate_articles(articles)
    print("Processing " + str(len(articles)) + " articles...")
    results  = [process_article(a) for a in articles]
    matched  = [r for r in results if r.get("is_leadership_event")]
    print("MATCHED THIS RUN: " + str(len(matched)))
    save_cumulative(results)

if __name__ == "__main__":
    main()