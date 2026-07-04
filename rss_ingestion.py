import feedparser
import re
import urllib.request
from typing import List, Dict

# =============================================================================
# POLIS RSS INGESTION v3.2
# Fixes: Angola duplicate, k=6 cap removed, score threshold added,
#        T0 authority/independence separated, full article text fetching
# =============================================================================

HARD_EXCLUDE = [
    # Iran/Middle East
    'hormuz', 'iran navy', 'us warship', 'iranian claim', 'irgc',
    'iran says', 'iran claims', 'us forces destroy', 'iran army chief',
    # Israel/Global conflict  
    'israel unveils', 'israeli strikes', 'jordan launches',
    'thirteen killed in israeli', 'photo shows israeli',
    # Crime/accidents not presidential
    'shoots motorcyclist', 'men drug and rape', 'lorry ferrying',
    'church goers rams', 'gang groups', 'kidnapper in adamawa',
    'police bust fake', 'police raid black spot',
    'police gun down bandit', 'five arrested as police',
    'police arrest protester', 'police arrest man over viral',
    # Elections noise
    'aspirants', 'guber race', 'nomination form', 'declares for pdp',
    'stand as mp', 'nomination fee',
    # Other global noise
    'sarkozy', 'taiwan lai', 'obama offers', 'kodak black',
    'formula one', 'car-ramming', 'car crash in germany',
    'hantavirus', 'epstein', 'two die after car',

    # Sports
    "football", "match", "league", "sport", "athletics", "champions league",
    "nba", "cricket", "formula 1", "grand prix", "transfer", "afcon",
    "world cup", "premier league", "wrestling title", "tuna day",
    # Entertainment
    "celebrity", "movie", "entertainment", "baby hippo", "rapper",
    # Global noise
    "trump", "ukraine", "hezbollah", "israel strikes", "iran navy",
    "hormuz", "us forces", "us warship", "iranian claim", "irgc",
    "jordan launches airstrikes", "china sentences", "china orders",
    "south korean court", "french court", "french appeals",
    "hantavirus", "epstein", "obama offers", "alien visitors",
    "bolivian police", "car-ramming", "car crash in germany",
    "sebastian coe", "formula one", "kodak black",
    # Crime noise
    "motorbike theft", "jailed for rape", "kidnapper nabbed",
    "shoots motorcyclist", "drug trafficking charges",
    "baby stolen", "couple jailed", "gold mine collapse",
]

HIGH_IMPACT_TERMS = [
    "constitution", "state of emergency", "media shutdown", "election commission",
    "supreme court", "military deployment", "anti-corruption", "coup",
    "press freedom", "detained journalist", "dissolved parliament",
    "suspended constitution", "martial law", "mass arrest", "crackdown",
    "impeached", "indaba", "harambee", "ubuntu", "consultative forum",
]

def is_noise(text: str) -> bool:
    t = text.lower()
    return any(x in t for x in HARD_EXCLUDE)

def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", text.lower())

def token_set(text: str) -> set:
    return set(norm(text).split())

ACTOR_SIGNALS = [
    "president", "minister", "governor", "prime minister", "cabinet",
    "government", "state house", "presidency", "ministry", "court",
    "police", "army", "electoral commission", "central bank", "agency",
    "parliament", "senate", "national assembly", "vice president",
    "deputy president", "attorney general", "efcc", "icpc", "dss",
]

ACTION_SIGNALS = [
    "arrest", "detain", "charge", "investigate", "appoint", "dismiss",
    "suspend", "approve", "launch", "announce", "sign", "reject", "pass",
    "order", "direct", "ban", "rule", "sentence", "verdict", "deploy",
    "enact", "convict", "acquit", "probe", "raid", "prosecute", "summon",
    "nominated", "sworn", "fired", "sacked", "resigned", "dialogue",
    "consult", "convene", "crackdown", "shutdown", "censored",
]

def signal_score(text: str) -> float:
    t = norm(text)
    actor_hits  = sum(1 for a in ACTOR_SIGNALS  if a in t)
    action_hits = sum(1 for a in ACTION_SIGNALS if a in t)
    score = (actor_hits * 2.0) + (action_hits * 2.5)
    if actor_hits > 0 and action_hits > 0:
        score += 3
    # High-impact bonus
    impact_hits = sum(1 for h in HIGH_IMPACT_TERMS if h in text.lower())
    score += impact_hits * 2.0
    length_penalty = min(len(token_set(t)) / 50, 1.2)
    return score / length_penalty if length_penalty > 0 else score

SIGNAL_THRESHOLD = 5.5  # Replaces k=6 — keeps all above threshold

# President name keywords per country for T2/T3 validation
PRESIDENT_KEYWORDS = {
    "Algeria":                  ["tebboune", "abdelmadjid"],
    "Egypt":                    ["sisi", "el-sisi", "al-sisi"],
    "Libya":                    ["menfi", "dbeibah", "al-menfi"],
    "Morocco":                  ["mohammed vi", "king mohammed", "royal palace", "maroc.ma"],
    "Sudan":                    ["al-burhan", "burhan", "sudanese president"],
    "Tunisia":                  ["saied", "kais saied"],
    "Benin":                    ["talon", "patrice talon"],
    "Burkina Faso":             ["traore", "ibrahim traore", "capitaine traore"],
    "Cape Verde":               ["neves", "jose neves"],
    "Cote d Ivoire":            ["ouattara", "alassane"],
    "Gambia":                   ["barrow", "adama barrow"],
    "Ghana":                    ["mahama", "john mahama"],
    "Guinea":                   ["doumbouya", "mamady"],
    "Guinea-Bissau":            ["embalo", "umaro", "sissoco"],
    "Liberia":                  ["boakai", "joseph boakai"],
    "Mali":                     ["goita", "assimi"],
    "Mauritania":               ["ghazouani", "ould ghazouani"],
    "Niger":                    ["tchiani", "abdourahamane"],
    "Nigeria":                  ["tinubu", "bola tinubu"],
    "Senegal":                  ["faye", "diomaye", "bassirou"],
    "Sierra Leone":             ["bio", "julius bio", "maada bio"],
    "Togo":                     ["gnassingbe", "faure"],
    "Angola":                   ["lourenco", "joao lourenco"],
    "Cameroon":                 ["biya", "paul biya"],
    "Central African Republic": ["touadera", "faustin"],
    "Chad":                     ["deby", "mahamat deby"],
    "DRC":                      ["tshisekedi", "felix tshisekedi"],
    "Equatorial Guinea":        ["nguema", "obiang", "teodoro"],
    "Gabon":                    ["oligui", "brice oligui"],
    "Republic of Congo":        ["sassou", "nguesso", "denis sassou"],
    "Sao Tome and Principe":    ["vila nova", "carlos vila"],
    "Burundi":                  ["ndayishimiye", "evariste"],
    "Comoros":                  ["assoumani", "azali"],
    "Djibouti":                 ["guelleh", "ismail omar"],
    "Eritrea":                  ["afwerki", "isaias"],
    "Ethiopia":                 ["abiy", "abiy ahmed", "prime minister abiy"],
    "Kenya":                    ["ruto", "william ruto", "state house kenya"],
    "Madagascar":               ["randrianirina", "michael randrianirina"],
    "Malawi":                   ["mutharika", "peter mutharika"],
    "Mauritius":                ["gokhool", "dharam gokhool"],
    "Mozambique":               ["chapo", "daniel chapo"],
    "Rwanda":                   ["kagame", "paul kagame", "urugwiro", "rwandan president"],
    "Seychelles":               ["ramkalawan", "wavel"],
    "Somalia":                  ["mohamud", "hassan sheikh"],
    "South Sudan":              ["kiir", "salva kiir"],
    "Tanzania":                 ["samia", "hassan", "samia suluhu"],
    "Uganda":                   ["museveni", "yoweri", "state house uganda"],
    "Botswana":                 ["boko", "duma boko"],
    "Eswatini":                 ["mswati", "king mswati"],
    "Lesotho":                  ["lerotholi", "samuela lerotholi"],
    "Namibia":                  ["mbumba", "nangolo"],
    "South Africa":             ["ramaphosa", "cyril ramaphosa", "presidency south africa"],
    "Zambia":                   ["hichilema", "hakainde", "state house zambia"],
    "Zimbabwe":                 ["mnangagwa", "emmerson"],
}

def article_mentions_president(text: str, country: str) -> bool:
    """Check if president name appears in article text."""
    t = text.lower()
    names = PRESIDENT_KEYWORDS.get(country, [])
    return any(n in t for n in names)

def filter_articles(articles: list) -> list:
    """
    Threshold-based filtering with president name validation for T2/T3.
    T0/T1: keep all above threshold (trust the feed).
    T2/T3: must mention president name OR country keyword to pass.
    """
    scored = []
    for a in articles:
        text = a.get("title", "") + " " + a.get("summary", "")
        tier = a.get("source_tier", "T3")
        country = a.get("country", "")

        if is_noise(text):
            continue

        # T1/T2/T3: require president name in text
        if tier != "T0":
            if not article_mentions_president(text, country):
                continue

        s = signal_score(text)
        scored.append((s, a))

    above = [(s, a) for s, a in scored if s >= SIGNAL_THRESHOLD]

    if above:
        return [a for _, a in sorted(above, key=lambda x: -x[0])]
    elif scored:
        return [a for _, a in sorted(scored, key=lambda x: -x[0])[:3]]
    return []

# =============================================================================
# STATE-CONTROLLED + SOURCE METADATA
# T0 = official (high authority, LOW independence)
# T1 = domestic independent
# T2 = regional
# T3 = international
# =============================================================================

STATE_CONTROLLED_SOURCES = {
    "https://www.herald.co.zw/feed/",
    "https://www.cameroon-tribune.cm/rss.xml",
    "https://www.crtv.cm/feed/",
    "https://www.angop.ao/noticias/rss.xml",
    "https://www.dailynews.co.tz/feed/",
    "https://www.ethiopiaobserver.com/feed/",
    "https://www.ezega.com/News/RssFeed",
    "https://www.pmo.gov.et/feed/",
    "https://www.president.go.ke/feed/",
    "https://www.statehouse.go.ug/feed/",
    "https://statehouse.gov.ng/feed/",
    "https://www.thepresidency.gov.za/feed/",
    "https://www.statehouse.gov.zm/feed/",
    "https://www.presidency.gov.rw/feed/",
    "https://presidency.gov.gh/feed/",
    "https://statehouse.gov.gm/feed/",
}

# T0 feeds = official/presidency — high authority, not independent
T0_OFFICIAL_FEEDS = {
    "https://statehouse.gov.ng/feed/",
    "https://www.president.go.ke/feed/",
    "https://www.statehouse.go.ug/feed/",
    "https://www.thepresidency.gov.za/feed/",
    "https://www.statehouse.gov.zm/feed/",
    "https://www.presidency.gov.rw/feed/",
    "https://presidency.gov.gh/feed/",
    "https://statehouse.gov.gm/feed/",
    "https://www.pmo.gov.et/feed/",
    "https://www.maroc.ma/en/rss.xml",
}

def get_source_metadata(feed_url: str, tier: str) -> dict:
    is_state = feed_url in STATE_CONTROLLED_SOURCES
    is_official = feed_url in T0_OFFICIAL_FEEDS
    return {
        "source_bias":          "state" if is_state else "independent",
        "source_authority":     "official" if is_official else "media",
        "source_independence":  "low" if is_state else "high",
    }

# =============================================================================
# ARTICLE TEXT FETCHER
# Fetches 2-3 paragraphs from source URL for richer analysis
# =============================================================================

def fetch_article_text(url: str, timeout: int = 8) -> str:
    """
    Attempts to fetch and extract plain text from article URL.
    Returns empty string on failure — never blocks pipeline.
    """
    if not url:
        return ""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; POLIS/3.2)"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        # Strip tags, extract text
        text = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>",  " ", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        # Return first 1500 chars — enough for framing without memory issues
        return text[:1500]
    except Exception:
        return ""

# =============================================================================
# RSS FEEDS — 54 COUNTRIES (Angola duplicate fixed)
# =============================================================================

RSS_FEEDS = {

    # ---- NORTH AFRICA ----
    "Algeria": {
        "president": "Tebboune", "president_full": "Abdelmadjid Tebboune",
        "since": "2019", "state_house_url": "https://www.el-mouradia.dz/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.algerie360.com/feed/", "https://www.tsa-algerie.com/feed/", "https://www.aps.dz/en/rss/all"],
        "tier2": ["https://www.jeuneafrique.com/feed/"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://www.aljazeera.com/xml/rss/all.xml"],
    },
    "Egypt": {
        "president": "Sisi", "president_full": "Abdel Fattah el-Sisi",
        "since": "2014", "state_house_url": "https://www.presidency.eg/",
        "social_x": "@Presidency_EG", "social_facebook": "@Presidency.eg",
        "tier0": ["https://www.presidency.eg/en/feed/"],
        "tier1": ["https://www.egyptindependent.com/feed/", "https://english.ahram.org.eg/rss/", "https://egypttoday.com/Rss/Feed"],
        "tier2": ["https://www.africanews.com/feed/rss"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://www.aljazeera.com/xml/rss/all.xml", "https://semafor.com/rss/africa"],
    },
    "Libya": {
        "president": "Menfi", "president_full": "Mohamed al-Menfi",
        "since": "2021", "state_house_url": "https://pm.gov.ly/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.libyaherald.com/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://www.aljazeera.com/xml/rss/all.xml"],
    },
    "Morocco": {
        "president": "Mohammed VI", "president_full": "King Mohammed VI",
        "since": "1999", "state_house_url": "https://www.maroc.ma/",
        "social_x": "@ChefGov_ma", "social_facebook": "@Maroc.ma.Officiel",
        "tier0": ["https://www.maroc.ma/en/rss.xml"],
        "tier1": ["https://www.lematin.ma/rss/", "https://www.hespress.com/feed/", "https://www.medias24.com/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://www.rfi.fr/fr/afrique/rss"],
    },
    "Sudan": {
        "president": "al-Burhan", "president_full": "Abdel Fattah al-Burhan",
        "since": "2019", "state_house_url": "https://www.presidency.gov.sd/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.sudantribune.com/spip.php?page=backend", "https://www.dabangasudan.org/en/feed"],
        "tier2": ["https://www.africanews.com/feed/rss"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://www.aljazeera.com/xml/rss/all.xml", "https://semafor.com/rss/africa"],
    },
    "Tunisia": {
        "president": "Saied", "president_full": "Kais Saied",
        "since": "2019", "state_house_url": "https://www.presidence.tn/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.tap.info.tn/en/feed", "https://www.businessnews.com.tn/rss"],
        "tier2": ["https://www.jeuneafrique.com/feed/"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://www.rfi.fr/fr/afrique/rss"],
    },

    # ---- WEST AFRICA ----
    "Benin": {
        "president": "Talon", "president_full": "Patrice Talon",
        "since": "2016", "state_house_url": "https://presidence.bj/",
        "social_x": "@PresidenceBenin", "social_facebook": "@PresidenceBenin",
        "tier0": [],
        "tier1": ["https://www.banouto.info/feed/", "https://lanation.bj/feed/", "https://24haubenin.info/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Burkina Faso": {
        "president": "Traore", "president_full": "Ibrahim Traoré",
        "since": "2022", "state_house_url": "https://www.presidencedufaso.bf/",
        "social_x": "@Presidence_BF", "social_facebook": "@PresidenceduFaso",
        "tier0": [],
        "tier1": ["https://lefaso.net/spip.php?page=backend", "https://www.wakatsera.com/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Cape Verde": {
        "president": "Neves", "president_full": "José Maria Neves",
        "since": "2021", "state_house_url": "https://www.presidencia.cv/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.inforpress.cv/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Cote d Ivoire": {
        "president": "Ouattara", "president_full": "Alassane Ouattara",
        "since": "2010", "state_house_url": "https://www.presidence.ci/",
        "social_x": "@Presidenceci", "social_facebook": "@Presidenceci",
        "tier0": [],
        "tier1": ["https://www.fratmat.info/feed/", "https://www.koaci.com/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Gambia": {
        "president": "Barrow", "president_full": "Adama Barrow",
        "since": "2017", "state_house_url": "https://statehouse.gov.gm/",
        "social_x": "@Presidency_GMB", "social_facebook": "@PresidencyGambia",
        "tier0": ["https://statehouse.gov.gm/feed/"],
        "tier1": ["https://thepoint.gm/africa/gambia/feed", "https://foroyaa.net/feed/"],
        "tier2": ["https://www.africanews.com/feed/rss"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Ghana": {
        "president": "Mahama", "president_full": "John Mahama",
        "since": "2025", "state_house_url": "https://presidency.gov.gh/",
        "social_x": "@PresidencyGhana", "social_facebook": "@PresidencyGhana",
        "tier0": ["https://presidency.gov.gh/feed/"],
        "tier1": ["https://www.myjoyonline.com/feed/", "https://www.ghanaweb.com/GhanaHomePage/RSS/RSS.php", "https://citifmonline.com/feed/"],
        "tier2": ["https://www.africanews.com/feed/rss", "https://allafrica.com/tools/headlines/rdf/ghana/headlines.rdf"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://semafor.com/rss/africa"],
    },
    "Guinea": {
        "president": "Doumbouya", "president_full": "Mamady Doumbouya",
        "since": "2021", "state_house_url": "https://www.presidence.gov.gn/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.guineenews.org/feed/", "https://www.africaguinee.com/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Guinea-Bissau": {
        "president": "Horta", "president_full": "Umaro Sissoco Embaló",
        "since": "2020", "state_house_url": "https://www.presidenciagb.gw/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": [],
        "tier2": ["https://www.jeuneafrique.com/feed/"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Liberia": {
        "president": "Boakai", "president_full": "Joseph Boakai",
        "since": "2024", "state_house_url": "https://www.emansion.gov.lr/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.liberianobserver.com/feed/", "https://frontpageafricaonline.com/feed/"],
        "tier2": ["https://www.africanews.com/feed/rss"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://semafor.com/rss/africa"],
    },
    "Mali": {
        "president": "Goita", "president_full": "Assimi Goïta",
        "since": "2021", "state_house_url": "https://www.koulouba.ml/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.maliweb.net/feed/", "https://www.malijet.com/feed"],
        "tier2": ["https://www.jeuneafrique.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Mauritania": {
        "president": "Ghazouani", "president_full": "Mohamed Ould Ghazouani",
        "since": "2019", "state_house_url": "https://www.presidence.mr/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.cridem.org/feed/", "https://alakhbar.info/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Niger": {
        "president": "Tchiani", "president_full": "Abdourahamane Tchiani",
        "since": "2023", "state_house_url": "https://www.presidence.ne/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.tamtaminfo.com/feed/", "https://www.nigerdiaspora.net/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Nigeria": {
        "president": "Tinubu", "president_full": "Bola Ahmed Tinubu",
        "since": "2023", "state_house_url": "https://statehouse.gov.ng/",
        "social_x": "@NGRPresident", "social_facebook": "@NGRPresident",
        "tier0": ["https://statehouse.gov.ng/feed/"],
        "tier1": [  "https://www.premiumtimesng.com/feed/", "https://guardian.ng/feed/", "https://www.dailytrust.com/feed/", "https://thenationonlineng.net/feed/"],
        "tier2": ["https://www.africanews.com/feed/rss", "https://allafrica.com/tools/headlines/rdf/nigeria/headlines.rdf", "https://news24.com/feed/"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://semafor.com/rss/africa"],
    },
    "Senegal": {
        "president": "Faye", "president_full": "Bassirou Diomaye Faye",
        "since": "2024", "state_house_url": "https://www.presidence.sn/",
        "social_x": "@PR_Senegal", "social_facebook": "@PresidenceduSenegal",
        "tier0": [],
        "tier1": ["https://www.seneweb.com/news/rss.php", "https://www.pressafrik.com/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://semafor.com/rss/africa"],
    },
    "Sierra Leone": {
        "president": "Bio", "president_full": "Julius Maada Bio",
        "since": "2018", "state_house_url": "https://statehouse.gov.sl/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.sierraexpressmedia.com/?feed=rss2", "https://awoko.org/feed/"],
        "tier2": ["https://www.africanews.com/feed/rss"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Togo": {
        "president": "Gnassingbe", "president_full": "Faure Gnassingbé",
        "since": "2005", "state_house_url": "https://www.gouv.tg/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.togofirst.com/feed/", "https://www.icilome.com/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },

    # ---- CENTRAL AFRICA ----
    "Cameroon": {
        "president": "Biya", "president_full": "Paul Biya",
        "since": "1982", "state_house_url": "https://www.prc.cm/",
        "social_x": "@PR_Cameroon", "social_facebook": "@PresidenceduCameroun",
        "tier0": [],
        "tier1": ["https://www.cameroon-tribune.cm/rss.xml", "https://actucameroun.com/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Central African Republic": {
        "president": "Touadera", "president_full": "Faustin-Archange Touadéra",
        "since": "2016", "state_house_url": "https://www.presidence.cf/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.radiondekeluka.org/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Chad": {
        "president": "Deby", "president_full": "Mahamat Déby",
        "since": "2021", "state_house_url": "https://www.presidence.td/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://tchadinfos.com/feed/", "https://www.alwihdainfo.com/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "DRC": {
        "president": "Tshisekedi", "president_full": "Félix Tshisekedi",
        "since": "2019", "state_house_url": "https://www.presidence.cd/",
        "social_x": "@Presidence_RDC", "social_facebook": "@PresidenceRDC",
        "tier0": [],
        "tier1": ["https://www.radiookapi.net/rss.xml", "https://actualite.cd/feed", "https://www.7sur7.cd/feed"],
        "tier2": ["https://www.jeuneafrique.com/feed/", "https://www.africanews.com/feed/rss", "https://allafrica.com/tools/headlines/rdf/drc/headlines.rdf"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://semafor.com/rss/africa"],
    },
    "Equatorial Guinea": {
        "president": "Nguema", "president_full": "Teodoro Obiang Nguema Mbasogo",
        "since": "1979", "state_house_url": "https://www.presidencia-ge.org/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": [],
        "tier2": ["https://www.jeuneafrique.com/feed/"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Gabon": {
        "president": "Oligui Nguema", "president_full": "Brice Clotaire Oligui Nguema",
        "since": "2023", "state_house_url": "https://www.presidence.ga/",
        "social_x": "@PresidenceGabon", "social_facebook": "@PresidenceduGabon",
        "tier0": [],
        "tier1": ["https://www.gabonactu.com/feed/", "https://www.gabonreview.com/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Republic of Congo": {
        "president": "Sassou Nguesso", "president_full": "Denis Sassou Nguesso",
        "since": "1997", "state_house_url": "https://www.presidence.cg/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.adiac-congo.com/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Sao Tome and Principe": {
        "president": "Vila Nova", "president_full": "Carlos Manuel Vila Nova",
        "since": "2021", "state_house_url": "https://www.presidencia.st/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.telanon.info/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    # Angola listed ONCE here (duplicate removed)
    "Angola": {
        "president": "Lourenco", "president_full": "João Lourenço",
        "since": "2017", "state_house_url": "https://www.presidente.ao/",
        "social_x": "@Presidencia_AO", "social_facebook": "@PresidenciaAngola",
        "tier0": [],
        "tier1": ["https://www.angop.ao/noticias/rss.xml", "https://www.jornaldeangola.ao/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://semafor.com/rss/africa"],
    },

    # ---- EAST AFRICA ----
    "Burundi": {
        "president": "Ndayishimiye", "president_full": "Évariste Ndayishimiye",
        "since": "2020", "state_house_url": "https://www.presidence.gov.bi/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.iwacu-burundi.org/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Comoros": {
        "president": "Assoumani", "president_full": "Azali Assoumani",
        "since": "2019", "state_house_url": "https://www.beit-salam.km/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.alwatwan.net/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Djibouti": {
        "president": "Guelleh", "president_full": "Ismaïl Omar Guelleh",
        "since": "1999", "state_house_url": "https://www.presidence.dj/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.lanationdj.com/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://www.aljazeera.com/xml/rss/all.xml"],
    },
    "Eritrea": {
        "president": "Afwerki", "president_full": "Isaias Afwerki",
        "since": "1993", "state_house_url": "https://www.shabait.com/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": [],
        "tier2": ["https://www.africanews.com/feed/rss"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://www.aljazeera.com/xml/rss/all.xml"],
    },
    "Ethiopia": {
        "president": "Abiy", "president_full": "Abiy Ahmed (PM)",
        "since": "2018", "state_house_url": "https://www.president.gov.et/",
        "social_x": "@PMEthiopia", "social_facebook": "@AbiyAhmedAli",
        "tier0": ["https://www.pmo.gov.et/feed/"],
        "tier1": ["https://addisstandard.com/feed/"],
        "tier2": ["https://www.africanews.com/feed/rss", "https://allafrica.com/tools/headlines/rdf/ethiopia/headlines.rdf"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://semafor.com/rss/africa", "https://www.aljazeera.com/xml/rss/all.xml"],
    },
    "Kenya": {
        "president": "Ruto", "president_full": "William Ruto",
        "since": "2022", "state_house_url": "https://www.president.go.ke/",
        "social_x": "@StateHouseKenya", "social_facebook": "@StateHouseKenya",
        "tier0": ["https://www.president.go.ke/feed/"],
        "tier1": ["https://nation.africa/kenya/rss.xml", "https://www.standardmedia.co.ke/rss/politics.xml", "https://www.the-star.co.ke/rss/", "https://www.kbc.co.ke/feed/"],
        "tier2": ["https://www.africanews.com/feed/rss", "https://allafrica.com/tools/headlines/rdf/kenya/headlines.rdf", "https://news24.com/feed/"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://semafor.com/rss/africa"],
    },
    "Madagascar": {
        "president": "Randrianirina", "president_full": "Michael Randrianirina (transitional)",
        "since": "2025", "state_house_url": "https://www.presidence.gov.mg/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.madagascar-tribune.com/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://www.rfi.fr/fr/afrique/rss", "https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Malawi": {
        "president": "Mutharika", "president_full": "Peter Mutharika",
        "since": "2025", "state_house_url": "https://www.opc.gov.mw/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.nyasatimes.com/feed/", "https://malawilive.com/feed/"],
        "tier2": ["https://www.africanews.com/feed/rss"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://semafor.com/rss/africa"],
    },
    "Mauritius": {
        "president": "Gokhool", "president_full": "Dharam Gokhool",
        "since": "2024", "state_house_url": "https://www.govmu.org/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.lexpress.mu/feed/", "https://defimedia.info/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Mozambique": {
        "president": "Chapo", "president_full": "Daniel Chapo",
        "since": "2025", "state_house_url": "https://www.presidencia.gov.mz/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.clubofmozambique.com/feed/", "https://www.verdade.co.mz/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://semafor.com/rss/africa"],
    },
    "Rwanda": {
        "president": "Kagame", "president_full": "Paul Kagame",
        "since": "2000", "state_house_url": "https://www.presidency.gov.rw/",
        "social_x": "@UrugwiroVillage", "social_facebook": "@PresidencyRwanda",
        "tier0": ["https://www.presidency.gov.rw/feed/"],
        "tier1": ["https://www.newtimes.co.rw/feed/", "https://www.ktpress.rw/feed/"],
        "tier2": ["https://www.jeuneafrique.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://semafor.com/rss/africa"],
    },
    "Seychelles": {
        "president": "Ramkalawan", "president_full": "Wavel Ramkalawan",
        "since": "2020", "state_house_url": "https://www.statehouse.gov.sc/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.nation.sc/feed/", "https://seychellesnewsagency.com/feed/"],
        "tier2": ["https://www.africanews.com/feed/rss"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Somalia": {
        "president": "Mohamud", "president_full": "Hassan Sheikh Mohamud",
        "since": "2022", "state_house_url": "https://www.villa-somalia.gov.so/",
        "social_x": "@TheVillaSomalia", "social_facebook": "@VillaSomalia",
        "tier0": [],
        "tier1": ["https://www.garoweonline.com/en/feed/", "https://www.hiiraan.com/feed/"],
        "tier2": ["https://www.africanews.com/feed/rss"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://www.aljazeera.com/xml/rss/all.xml"],
    },
    "South Sudan": {
        "president": "Kiir", "president_full": "Salva Kiir Mayardit",
        "since": "2011", "state_house_url": "https://www.presidency.gov.ss/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.radiotamazuj.org/en/feed", "https://sudanspost.com/feed/"],
        "tier2": ["https://www.africanews.com/feed/rss"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://www.aljazeera.com/xml/rss/all.xml", "https://semafor.com/rss/africa"],
    },
    "Tanzania": {
        "president": "Hassan", "president_full": "Samia Suluhu Hassan",
        "since": "2021", "state_house_url": "https://www.ikulu.go.tz/",
        "social_x": "@ikulumawasliano", "social_facebook": "@ikulu_tanzania",
        "tier0": [],
        "tier1": ["https://www.thecitizen.co.tz/feed/", "https://dailynews.co.tz/feed/", "https://www.ippmedia.com/feed/"],
        "tier2": ["https://www.africanews.com/feed/rss", "https://allafrica.com/tools/headlines/rdf/tanzania/headlines.rdf"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://semafor.com/rss/africa"],
    },
    "Uganda": {
        "president": "Museveni", "president_full": "Yoweri Museveni",
        "since": "1986", "state_house_url": "https://www.statehouse.go.ug/",
        "social_x": "@StateHouseUg", "social_facebook": "@StateHouseUganda",
        "tier0": ["https://www.statehouse.go.ug/feed/"],
        "tier1": ["https://www.monitor.co.ug/feed/", "https://www.newvision.co.ug/feed/", "https://www.independent.co.ug/feed/"],
        "tier2": ["https://www.africanews.com/feed/rss", "https://allafrica.com/tools/headlines/rdf/uganda/headlines.rdf"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://semafor.com/rss/africa", "https://www.aljazeera.com/xml/rss/all.xml"],
    },

    # ---- SOUTHERN AFRICA ----
    "Botswana": {
        "president": "Boko", "president_full": "Duma Boko",
        "since": "2024", "state_house_url": "https://www.gov.bw/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.sundaystandard.info/feed/", "https://www.mmegi.bw/feed/"],
        "tier2": ["https://www.africanews.com/feed/rss", "https://news24.com/feed/"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://semafor.com/rss/africa"],
    },
    "Eswatini": {
        "president": "Mswati III", "president_full": "King Mswati III",
        "since": "1986", "state_house_url": "https://www.gov.sz/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.times.co.sz/feed/", "https://www.observer.org.sz/feed/"],
        "tier2": ["https://news24.com/feed/"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Lesotho": {
        "president": "Lerotholi", "president_full": "PM Samuela Lerotholi",
        "since": "2024", "state_house_url": "https://www.gov.ls/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://lestimes.com/feed/", "https://www.thepost.co.ls/feed/"],
        "tier2": ["https://news24.com/feed/"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml"],
    },
    "Namibia": {
        "president": "Mbumba", "president_full": "Nangolo Mbumba",
        "since": "2024", "state_house_url": "https://www.op.gov.na/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.namibian.com.na/feed/", "https://neweralive.na/feed/"],
        "tier2": ["https://news24.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://semafor.com/rss/africa"],
    },
    "South Africa": {
        "president": "Ramaphosa", "president_full": "Cyril Ramaphosa",
        "since": "2018", "state_house_url": "https://www.thepresidency.gov.za/",
        "social_x": "@PresidencyZA", "social_facebook": "@PresidencyZA",
        "tier0": ["https://www.thepresidency.gov.za/feed/"],
        "tier1": ["https://mg.co.za/feed/", "https://www.dailymaverick.co.za/feed/", "https://ewn.co.za/RSS", "https://www.sabcnews.com/sabcnews/feed/", "https://news24.com/feed/"],
        "tier2": ["https://www.africanews.com/feed/rss", "https://allafrica.com/tools/headlines/rdf/southafrica/headlines.rdf"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://semafor.com/rss/africa", "https://www.aljazeera.com/xml/rss/all.xml"],
    },
    "Zambia": {
        "president": "Hichilema", "president_full": "Hakainde Hichilema",
        "since": "2021", "state_house_url": "https://www.statehouse.gov.zm/",
        "social_x": "@PresidencyZM", "social_facebook": "@StateHouseZambia",
        "tier0": ["https://www.statehouse.gov.zm/feed/"],
        "tier1": ["https://www.lusakatimes.com/feed/", "https://www.daily-mail.co.zm/feed/", "https://zambianobserver.com/feed/"],
        "tier2": ["https://news24.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://semafor.com/rss/africa"],
    },
    "Zimbabwe": {
        "president": "Mnangagwa", "president_full": "Emmerson Mnangagwa",
        "since": "2017", "state_house_url": "https://www.presidency.gov.zw/",
        "social_x": "", "social_facebook": "",
        "tier0": [],
        "tier1": ["https://www.newzimbabwe.com/feed/", "https://www.herald.co.zw/feed/", "https://www.newsday.co.zw/feed/", "https://www.thezimbabwean.co/feed/"],
        "tier2": ["https://news24.com/feed/", "https://www.africanews.com/feed/rss"],
        "tier3": ["https://feeds.bbci.co.uk/news/world/africa/rss.xml", "https://semafor.com/rss/africa"],
    },
}

# Validate no duplicates — critical check
assert len(RSS_FEEDS) == 54, f"Expected 53 unique countries, got {len(RSS_FEEDS)}. Check for duplicates."

# =============================================================================
# FETCH + DEDUPLICATE
# =============================================================================

FETCH_ARTICLE_TEXT = False  # Set True when ready for full-text pipeline

def fetch_feed(feed_url: str) -> list:
    try:
        feed = feedparser.parse(feed_url)
        articles = []
        for entry in feed.entries:
            articles.append({
                "title":     getattr(entry, "title", ""),
                "summary":   getattr(entry, "summary", ""),
                "link":      getattr(entry, "link", ""),
                "published": getattr(entry, "published", ""),
            })
        return articles
    except Exception as e:
        print("  Feed error [" + feed_url + "]: " + str(e))
        return []


def fetch_articles() -> list:
    all_articles = []
    print("Fetching articles across " + str(len(RSS_FEEDS)) + " countries...")

    for country, config in RSS_FEEDS.items():
        president = config.get("president", "")
        print("  " + country + " (" + president + ")")

        tier_map = [("tier0", "T0"), ("tier1", "T1"), ("tier2", "T2"), ("tier3", "T3")]
        country_articles = []

        for tier_key, tier_label in tier_map:
            for feed_url in config.get(tier_key, []):
                meta = get_source_metadata(feed_url, tier_label)
                articles = fetch_feed(feed_url)
                for a in articles:
                    a["country"]            = country
                    a["president"]          = president
                    a["president_full"]     = config.get("president_full", president)
                    a["source_tier"]        = tier_label
                    a["source_feed"]        = feed_url
                    a["source_bias"]        = meta["source_bias"]
                    a["source_authority"]   = meta["source_authority"]
                    a["source_independence"]= meta["source_independence"]
                    a["state_house_url"]    = config.get("state_house_url", "")
                    a["social_x"]           = config.get("social_x", "")
                    country_articles.append(a)

        filtered = filter_articles(country_articles)

        # Optional: fetch full article text for top results
        if FETCH_ARTICLE_TEXT:
            for a in filtered:
                a["article_text"] = fetch_article_text(a.get("link", ""))

        all_articles.extend(filtered)

    print("RAW AFTER FILTERING: " + str(len(all_articles)))
    return all_articles


def deduplicate_articles(articles: list) -> list:
    seen = set()
    unique = []
    for a in articles:
        link = a.get("link", "").strip()
        if link and link not in seen:
            seen.add(link)
            unique.append(a)
        elif not link:
            key = (a["title"].strip().lower(), a["country"])
            if key not in seen:
                seen.add(key)
                unique.append(a)
    print("UNIQUE ARTICLES: " + str(len(unique)))
    return unique


def get_coverage_summary() -> None:
    print("\n=== POLIS COVERAGE v3.2 — " + str(len(RSS_FEEDS)) + " COUNTRIES ===")
    for country, config in sorted(RSS_FEEDS.items()):
        t0 = len(config.get("tier0", []))
        t1 = len(config.get("tier1", []))
        social = "📱" if config.get("social_x") else "  "
        gap = " ⚠ NO T1" if t1 == 0 else ""
        print(f"  {social} {country:<30} {config.get('president',''):<25} T0:{t0} T1:{t1}{gap}")


if __name__ == "__main__":
    get_coverage_summary()
    articles = fetch_articles()
    articles = deduplicate_articles(articles)
    if articles:
        print("\nSample:", articles[0])