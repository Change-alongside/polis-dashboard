import streamlit as st
import pandas as pd
import json
import urllib.request
import os
import streamlit.components.v1 as components
from datetime import datetime

st.set_page_config(
    page_title="POLIS — African Presidential Leadership",
    layout="wide",
    page_icon="🌍",
    initial_sidebar_state="collapsed"
)




# =========================================================
# CONSTANTS
# =========================================================
DATASET_FILE = "polis_lse_dataset.json"
API_KEY      = os.environ.get("ANTHROPIC_API_KEY", "").strip()

DIMENSIONS = [
    "accountability",
    "responsiveness",
    "stewardship",
    "institutional_integrity",
    "inclusion",
]

DIMENSION_LABELS = {
    "accountability":          "Accountability",
    "responsiveness":          "Responsiveness",
    "stewardship":             "Stewardship",
    "institutional_integrity": "Inst. Integrity",
    "inclusion":               "Inclusion",
}

DIMENSION_DESCRIPTIONS = {
    "accountability":
        "Observable signals that the president is enforcing or submitting to "
        "institutional oversight — anti-corruption actions, judicial enforcement, "
        "audit responses, prosecutions of officials.",
    "responsiveness":
        "Actions following stated priorities or public needs — policy implementation, "
        "welfare delivery, crisis response, citizen-directed resource allocation.",
    "stewardship":
        "Investment in long-term public capability — institutional reform, "
        "infrastructure, legislative strengthening, capacity building.",
    "institutional_integrity":
        "Authority exercised through formal institutions rather than bypassing them — "
        "parliamentary routing, judicial independence respected, procedural compliance.",
    "inclusion":
        "Observable accommodation of diverse actors and voices — consultations, "
        "dialogues, opposition engagement, community forums, coalition behaviour.",
}

DIMENSION_ROOTS = {
    "accountability":          "Principal-agent theory",
    "responsiveness":          "Principal-agent + Public leadership",
    "stewardship":             "Public leadership literature",
    "institutional_integrity": "Neopatrimonialism (Bratton & van de Walle)",
    "inclusion":               "Principal-agent + Public leadership",
}

CURRENT_PRESIDENTS = {
    "Algeria":"Tebboune","Egypt":"Sisi","Libya":"Menfi",
    "Morocco":"Mohammed VI","Sudan":"al-Burhan","Tunisia":"Saied",
    "Benin":"Talon","Burkina Faso":"Traore","Cape Verde":"Neves",
    "Cote d Ivoire":"Ouattara","Gambia":"Barrow","Ghana":"Mahama",
    "Guinea":"Doumbouya","Guinea-Bissau":"Horta","Liberia":"Boakai",
    "Mali":"Goita","Mauritania":"Ghazouani","Niger":"Tchiani",
    "Nigeria":"Tinubu","Senegal":"Faye","Sierra Leone":"Bio",
    "Togo":"Gnassingbe","Angola":"Lourenco","Cameroon":"Biya",
    "Central African Republic":"Touadera","Chad":"Deby",
    "DRC":"Tshisekedi","Equatorial Guinea":"Nguema",
    "Gabon":"Oligui Nguema","Republic of Congo":"Sassou Nguesso",
    "Sao Tome and Principe":"Vila Nova","Burundi":"Ndayishimiye",
    "Comoros":"Assoumani","Djibouti":"Guelleh","Eritrea":"Afwerki",
    "Ethiopia":"Abiy","Kenya":"Ruto","Madagascar":"Randrianirina",
    "Malawi":"Mutharika","Mauritius":"Gokhool","Mozambique":"Chapo",
    "Rwanda":"Kagame","Seychelles":"Ramkalawan","Somalia":"Mohamud",
    "South Sudan":"Kiir","Tanzania":"Hassan","Uganda":"Museveni",
    "Botswana":"Boko","Eswatini":"Mswati III","Lesotho":"Lerotholi",
    "Namibia":"Mbumba","South Africa":"Ramaphosa","Zambia":"Hichilema",
    "Zimbabwe":"Mnangagwa",
}

REGION_MAP = {
    "North Africa":    ["Algeria","Egypt","Libya","Morocco","Sudan","Tunisia"],
    "West Africa":     ["Benin","Burkina Faso","Cape Verde","Cote d Ivoire","Gambia",
                        "Ghana","Guinea","Guinea-Bissau","Liberia","Mali","Mauritania",
                        "Niger","Nigeria","Senegal","Sierra Leone","Togo"],
    "Central Africa":  ["Angola","Cameroon","Central African Republic","Chad","DRC",
                        "Equatorial Guinea","Gabon","Republic of Congo","Sao Tome and Principe"],
    "East Africa":     ["Burundi","Comoros","Djibouti","Eritrea","Ethiopia","Kenya",
                        "Madagascar","Malawi","Mauritius","Mozambique","Rwanda",
                        "Seychelles","Somalia","South Sudan","Tanzania","Uganda"],
    "Southern Africa": ["Botswana","Eswatini","Lesotho","Namibia","South Africa","Zambia","Zimbabwe"],
}

ALL_54    = sorted(CURRENT_PRESIDENTS.keys())
MIN_EVENTS = 30

# =========================================================
# HELPERS
# =========================================================
def dim_avg(df, dim):
    col = "dim_" + dim
    if col not in df.columns:
        return None
    vals = df[col].dropna()
    return round(float(vals.mean()), 2) if len(vals) > 0 else None

def dim_n(df, dim):
    col = "dim_" + dim
    if col not in df.columns:
        return 0
    return int(df[col].notna().sum())

def score_class(s):
    if s is None: return "sn", ""
    if s >= 0.70: return "sh", str(s)
    if s >= 0.50: return "sm", str(s)
    return "sl", str(s)

def fill_class(s):
    if s is None: return "", 0
    if s >= 0.70: return "fh", int(s * 100)
    if s >= 0.50: return "fm", int(s * 100)
    return "fl", int(s * 100)


# =========================================================
# DATA LOADING
# =========================================================
@st.cache_data(ttl=300)
def load_data():
    if not os.path.exists(DATASET_FILE):
        return pd.DataFrame()
    with open(DATASET_FILE, "r") as f:
        raw = json.load(f)
    if isinstance(raw, dict) and "events" in raw:
        raw = raw["events"]
    events = [e for e in raw if isinstance(e, dict) and e.get("is_leadership_event")]
    if not events:
        return pd.DataFrame()
    df = pd.DataFrame(events).drop_duplicates(subset=["evidence"])
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col, default in [("source_bias","independent"),("framing","neutral"),("feed_count",1)]:
        if col not in df.columns:
            df[col] = default
    if "week" not in df.columns and "date" in df.columns:
        df["week"]  = df["date"].dt.strftime("%Y-W%W")
    if "month" not in df.columns and "date" in df.columns:
        df["month"] = df["date"].dt.strftime("%Y-%m")
    # Extract dimension scores into flat columns
    for dim in DIMENSIONS:
        col = "dim_" + dim
        if col not in df.columns and "dimensions" in df.columns:
            df[col] = df["dimensions"].apply(
                lambda d: d.get(dim, {}).get("score")
                if isinstance(d, dict) else None
            )
    for country, president in CURRENT_PRESIDENTS.items():
        df.loc[df["country"] == country, "president"] = president
    return df

# =========================================================
# INTELLIGENCE BRIEF HTML BUILDER
# =========================================================
def build_president_card(pid, name, country, p_df, is_first=False):
    n = len(p_df)
    caution_note = (
        f'<div class="caution-note">Note: {n} events — below the 30-event confidence threshold. Interpret with caution.</div>'
        if n < MIN_EVENTS else ""
    )
    domain_counts = p_df["domain"].value_counts() if "domain" in p_df.columns else pd.Series()
    top_domains   = list(domain_counts.index[:5]) if len(domain_counts) > 0 else []
    active_3      = list(domain_counts[domain_counts > 1].index[:3]) if len(domain_counts) > 0 else []
    pills_html    = "".join(
        f'<span class="pill {"on" if d in active_3 else ""}">{d}</span>'
        for d in top_domains
    )
    dim_cells = ""
    for dim in DIMENSIONS:
        s        = dim_avg(p_df, dim)
        sc, val  = score_class(s)
        fc, pct  = fill_class(s)
        display  = val if val else "—"
        dim_cells += f"""
        <div class="dc">
          <div class="dname">{DIMENSION_LABELS[dim]}</div>
          <div class="dscore {sc}">{display}</div>
          <div class="dbar"><div class="dbf {fc}" style="width:{pct}%"></div></div>
        </div>"""
    display_style = "block" if is_first else "none"
    last_name     = name.split()[-1] if " " in name else name
    return f"""
    <div id="{pid}" class="card" style="display:{display_style}">
      <div class="card-hdr">
        <div><div class="pname">{name}</div><div class="pcountry">{country}</div></div>
        <div class="ecount">Events on record<b>{n}</b></div>
      </div>
      {caution_note}
      <div class="dgrid">{dim_cells}</div>
      <div class="signal-hdr">Active governance domains</div>
      <div class="pills">{pills_html}</div>
      <div class="narr-wrap">
        <div class="narr-label">Governance behaviour signal</div>
        <div class="narr"><p>Based on {n} observable leadership signal events for {last_name}. Open the Analysis tab for full LLM-generated narrative synthesis of this governance behaviour pattern.</p></div>
      </div>
      <button class="meth-toggle" onclick="toggleMeth('m-{pid}',this)">What these dimensions measure <span>+</span></button>
      <div id="m-{pid}" class="meth-panel">
        <div class="meth-row"><div class="meth-dim">Accountability</div><div class="meth-def">Observable signals that the president is enforcing or submitting to institutional oversight — anti-corruption actions, judicial enforcement, audit responses, prosecutions of officials.</div><div class="meth-root">Root: Principal-agent theory</div></div>
        <div class="meth-row"><div class="meth-dim">Responsiveness</div><div class="meth-def">Actions following stated priorities or public needs — policy implementation, welfare delivery, crisis response, citizen-directed resource allocation.</div><div class="meth-root">Root: Principal-agent + Public leadership</div></div>
        <div class="meth-row"><div class="meth-dim">Stewardship</div><div class="meth-def">Investment in long-term public capability — institutional reform, infrastructure, legislative strengthening, capacity building.</div><div class="meth-root">Root: Public leadership literature</div></div>
        <div class="meth-row"><div class="meth-dim">Institutional Integrity</div><div class="meth-def">Authority exercised through formal institutions rather than bypassing them — parliamentary routing, judicial independence respected, procedural compliance.</div><div class="meth-root">Root: Neopatrimonialism (Bratton &amp; van de Walle)</div></div>
        <div class="meth-row"><div class="meth-dim">Inclusion</div><div class="meth-def">Observable accommodation of diverse actors and voices — consultations, dialogues, opposition engagement, community forums, coalition behaviour.</div><div class="meth-root">Root: Principal-agent + Public leadership</div></div>
        <div class="meth-note">Scores are 0.0–1.0. Null (—) means no observable signal in this event window, not an absence of behaviour. Grounded in principal-agent theory, public leadership literature, and neopatrimonialism.</div>
      </div>
    </div>"""


def render_intelligence_brief(df):
    today       = datetime.now().strftime("%d %b %Y")
    total       = len(df)
    countries_n = df["country"].nunique() if "country" in df.columns else 0

    if "president" in df.columns and "country" in df.columns:
        top = (df.groupby(["country","president"]).size()
               .reset_index(name="n")
               .sort_values("n", ascending=False)
               .head(8))
    else:
        top = pd.DataFrame()

    tabs_html  = ""
    cards_html = ""
    pids       = []
    for idx, row in enumerate(top.itertuples()):
        pid    = f"p{idx}"
        pids.append(pid)
        on     = "on" if idx == 0 else ""
        label  = f"{row.country} · {row.president}"
        tabs_html  += f'<button class="tab {on}" onclick="show(\'{pid}\',this)">{label}</button>'
        p_df        = df[(df["country"] == row.country) & (df["president"] == row.president)]
        cards_html += build_president_card(pid, row.president, row.country, p_df, idx == 0)

    avg_cells = ""
    for dim in DIMENSIONS:
        s   = dim_avg(df, dim)
        n   = dim_n(df, dim)
        sc, val = score_class(s)
        display = val if val else "—"
        color_style = "color:#c87040;" if (dim == "inclusion" and s and s < 0.55) else ""
        avg_cells += f"""
        <div class="cac">
          <div class="cavg-name">{DIMENSION_LABELS[dim]}</div>
          <div class="av {sc}" style="{color_style}">{display}</div>
          <div class="nn">n = {n}</div>
        </div>"""

    pids_js = str(pids).replace("'", '"')

    html = f"""<!DOCTYPE html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
:root{{--ink:#0a0a0f;--paper:#f0ebe0;--gold:#c9a84c;--gold-light:#e0c070;--dim:#9a9088;--dimmer:#7a7068;--line:rgba(201,168,76,0.22);--warn:#c87040}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--ink);color:var(--paper);font-family:'IBM Plex Sans',sans-serif;padding:2rem 1.75rem 1.5rem;position:relative}}
body::before{{content:'';position:fixed;top:0;left:0;right:0;height:3px;background:var(--gold);z-index:100}}
.hdr{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:1.75rem;padding-bottom:1.25rem;border-bottom:0.5px solid var(--line)}}
.mark{{font-family:'Playfair Display',serif;font-size:28px;font-weight:600;color:var(--gold);letter-spacing:0.06em}}
.sub{{font-size:11px;color:var(--dim);letter-spacing:0.14em;text-transform:uppercase;margin-top:5px;font-family:'IBM Plex Mono',monospace}}
.meta{{text-align:right;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--dim);line-height:2}}
.meta em{{color:var(--gold-light);font-style:normal;font-size:10px}}
.slabel{{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:var(--gold);margin-bottom:1rem}}
.tabs{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:1.25rem}}
.tab{{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:0.08em;text-transform:uppercase;padding:7px 13px;border-radius:2px;cursor:pointer;border:0.5px solid rgba(201,168,76,0.25);background:transparent;color:var(--dim);transition:all 0.2s;white-space:nowrap}}
.tab:hover{{color:var(--gold-light);border-color:rgba(201,168,76,0.5)}}
.tab.on{{background:rgba(201,168,76,0.12);border-color:var(--gold);color:var(--gold-light);font-weight:500}}
.card{{background:rgba(255,255,255,0.025);border:0.5px solid rgba(201,168,76,0.18);border-left:2px solid var(--gold);border-radius:2px;padding:1.5rem}}
.card-hdr{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:1.75rem}}
.pname{{font-family:'Playfair Display',serif;font-size:24px;font-weight:600;color:var(--paper);line-height:1.1}}
.pcountry{{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--gold-light);letter-spacing:0.12em;text-transform:uppercase;margin-top:6px}}
.ecount{{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--dim);text-align:right;line-height:1.6}}
.ecount b{{display:block;font-family:'Playfair Display',serif;font-size:26px;font-weight:400;color:var(--paper);font-style:normal;line-height:1}}
.caution-note{{font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--warn);border:0.5px solid rgba(200,112,64,0.3);padding:6px 10px;border-radius:2px;margin-bottom:1.25rem}}
.dgrid{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:1.5rem}}
.dc{{text-align:center}}
.dname{{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:0.06em;text-transform:uppercase;color:var(--dim);margin-bottom:10px;line-height:1.4;min-height:30px;display:flex;align-items:center;justify-content:center}}
.dscore{{font-family:'Playfair Display',serif;font-size:28px;font-weight:400;line-height:1}}
.dbar{{height:3px;background:rgba(255,255,255,0.08);margin-top:10px;border-radius:2px;overflow:hidden}}
.dbf{{height:100%;border-radius:2px}}
.sh{{color:var(--gold-light)}}.sm{{color:#c8aa6a}}.sl{{color:#c87040}}.sn{{color:var(--dimmer)}}
.fh{{background:var(--gold-light)}}.fm{{background:#c8aa6a}}.fl{{background:#c87040}}
.signal-hdr{{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;color:var(--dim);margin-bottom:0.5rem}}
.pills{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:1.5rem}}
.pill{{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:0.08em;text-transform:uppercase;padding:4px 10px;border-radius:2px;border:0.5px solid rgba(122,112,104,0.4);color:var(--dimmer)}}
.pill.on{{border-color:rgba(201,168,76,0.45);color:var(--gold-light);background:rgba(201,168,76,0.07)}}
.narr-wrap{{margin-bottom:1.5rem}}
.narr-label{{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;color:var(--gold);margin-bottom:0.75rem}}
.narr{{border-left:2px solid rgba(201,168,76,0.4);padding-left:1.25rem}}
.narr p{{font-size:14px;color:rgba(240,235,224,0.88);line-height:1.8;font-style:italic}}
.meth-toggle{{width:100%;background:transparent;border:0.5px solid var(--line);border-radius:2px;padding:10px 14px;color:var(--dim);font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:0.12em;text-transform:uppercase;cursor:pointer;text-align:left;display:flex;justify-content:space-between;align-items:center;transition:all 0.2s;margin-top:0.5rem}}
.meth-toggle:hover{{border-color:var(--gold);color:var(--gold-light)}}
.meth-panel{{display:none;margin-top:1rem;padding:1.25rem;background:rgba(255,255,255,0.02);border:0.5px solid var(--line);border-radius:2px}}
.meth-panel.open{{display:block}}
.meth-row{{margin-bottom:1.25rem}}
.meth-row:last-child{{margin-bottom:0}}
.meth-dim{{font-family:'Playfair Display',serif;font-size:16px;color:var(--gold-light);margin-bottom:4px}}
.meth-def{{font-size:13px;color:rgba(240,235,224,0.78);line-height:1.7;margin-bottom:4px}}
.meth-root{{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--dimmer);letter-spacing:0.06em}}
.meth-note{{margin-top:1.25rem;padding-top:1rem;border-top:0.5px solid var(--line);font-size:12px;color:rgba(240,235,224,0.45);line-height:1.7;font-style:italic}}
.divider{{height:0.5px;background:var(--line);margin:1.75rem 0}}
.cavg{{display:grid;grid-template-columns:repeat(5,1fr);gap:10px}}
.cac{{text-align:center}}
.cavg-name{{font-family:'IBM Plex Mono',monospace;font-size:11px;letter-spacing:0.06em;text-transform:uppercase;color:var(--dim);margin-bottom:8px}}
.av{{font-family:'Playfair Display',serif;font-size:22px;font-weight:400}}
.nn{{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--dimmer);margin-top:4px}}
.foot{{display:flex;justify-content:space-between;align-items:center;font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--dim);margin-top:2rem;padding-top:1rem;border-top:0.5px solid var(--line);flex-wrap:wrap;gap:8px}}
.stamp{{letter-spacing:0.16em;color:#d4884a;border:0.5px solid rgba(212,136,74,0.45);padding:3px 10px;border-radius:2px;text-transform:uppercase;font-size:10px;font-weight:500}}
@media(max-width:520px){{
.dgrid{{grid-template-columns:1fr 1fr 1fr}}
.cavg{{grid-template-columns:1fr 1fr}}
.hdr{{flex-direction:column;gap:1rem}}
.meta{{text-align:left}}
.foot{{flex-direction:column;gap:6px}}
.tab{{font-size:10px;padding:6px 10px}}
}}
</style></head><body>
<div class="hdr">
  <div>
    <div class="mark">POLIS</div>
    <div class="sub">Public Leadership Observation &amp; Insight System</div>
    <div class="sub" style="margin-top:4px;opacity:0.55">54 Countries · Africa · v8.0</div>
  </div>
  <div class="meta">
    <div>{today}</div>
    <div>{total} events on record</div>
    <div>{countries_n} countries covered</div>
    <div><em>model · claude-sonnet-4-20250514</em></div>
  </div>
</div>
<div class="slabel">Presidential Scorecards</div>
<div class="tabs" id="ptabs">{tabs_html}</div>
{cards_html}
<div class="divider"></div>
<div class="slabel">Continental averages · {total} events · {countries_n} countries</div>
<div class="cavg" style="margin-top:1rem">{avg_cells}</div>
<div class="foot">
  <div>polis-dashboard.streamlit.app</div>
  <div class="stamp">Observable signals only — not a measure of leadership quality</div>
  <div>Principal-agent · Public leadership · Neopatrimonialism</div>
</div>
<script>
var pids={pids_js};
function show(id,btn){{
  pids.forEach(function(p){{var el=document.getElementById(p);if(el)el.style.display=p===id?'block':'none';}});
  document.querySelectorAll('#ptabs .tab').forEach(function(t){{t.classList.remove('on')}});
  if(btn)btn.classList.add('on');
}}
function toggleMeth(id,btn){{
  var panel=document.getElementById(id);
  var open=panel.classList.toggle('open');
  btn.querySelector('span').textContent=open?'−':'+';
}}
</script>
</body></html>"""
    components.html(html, height=1200, scrolling=True)


# =========================================================
# NARRATIVE SYNTHESIS
# =========================================================
def generate_synthesis(country, president, p_df):
    if len(p_df) == 0 or not API_KEY:
        return None
    dim_summary = "\n".join([
        "{}: {} (n={})".format(
            DIMENSION_LABELS[d],
            "{:.2f}".format(dim_avg(p_df, d)) if dim_avg(p_df, d) is not None else "no data",
            dim_n(p_df, d)
        )
        for d in DIMENSIONS
    ])
    event_list = "\n".join([
        "- {} [{} | {}]".format(
            str(row.get("evidence", "")),
            str(row.get("action_type", "")),
            str(row.get("domain", ""))
        )
        for _, row in p_df.head(25).iterrows()
    ])
    prompt = (
        "You are an analyst for POLIS. Write a concise analytical narrative (4-5 sentences) "
        "about the governance behaviour pattern observed for this president. "
        "Ground every claim in the dimension scores and events provided. "
        "Note which dimensions are strongest and weakest. "
        "Note any tensions between dimensions. "
        "Do not use leadership theory labels. "
        "Use plain, precise language suitable for a governance researcher or journalist.\n\n"
        f"Country: {country}\nPresident: {president}\nTotal events: {len(p_df)}\n\n"
        f"Dimension profile:\n{dim_summary}\n\n"
        f"Events sample:\n{event_list}\n\n"
        f"Start with: 'Based on {len(p_df)} observable leadership signal events...'. "
        "No bullets. No headers. No theory labels."
    )
    try:
        payload = json.dumps({
            "model":      "claude-sonnet-4-20250514",
            "max_tokens": 500,
            "messages":   [{"role": "user", "content": prompt}]
        }, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type":      "application/json",
                "x-api-key":         API_KEY,
                "anthropic-version": "2023-06-01"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["content"][0]["text"].strip()
    except Exception:
        return None


# =========================================================
# LOAD DATA
# =========================================================
df_all = load_data()

if df_all.empty:
    st.warning("No data found. Run python3 extractor.py to collect events.")
    st.stop()

# =========================================================
# SIDEBAR — shared across all tabs
# =========================================================
with st.sidebar:
    st.markdown("### POLIS Filters")
    sel_country = st.selectbox("Country", ["All"] + sorted(df_all["country"].dropna().unique().tolist()))
    sel_region  = st.selectbox("Region",  ["All"] + list(REGION_MAP.keys()))
    sel_domain  = st.selectbox("Domain",  ["All"] + sorted(df_all["domain"].dropna().unique().tolist()))
    sel_tier    = st.selectbox("Source tier", ["All","T0","T1","T2","T3"])
    hide_state  = st.checkbox("Hide state-controlled sources", value=False)
    only_scored = st.checkbox("Only scored events", value=False)
    st.divider()
    needs = int((df_all["needs_scoring"] == True).sum()) if "needs_scoring" in df_all.columns else 0
    st.metric("Pending scoring", needs, help="Run llm_reviewer_v3.py to score these events")

# Apply filters
df = df_all.copy()
if sel_country != "All": df = df[df["country"] == sel_country]
if sel_region  != "All": df = df[df["country"].isin(REGION_MAP.get(sel_region, []))]
if sel_domain  != "All": df = df[df["domain"] == sel_domain]
if sel_tier    != "All": df = df[df["source_tier"] == sel_tier]
if hide_state  and "source_bias" in df.columns: df = df[df["source_bias"] != "state"]
if only_scored and "needs_scoring" in df.columns: df = df[df["needs_scoring"] == False]

# =========================================================
# HEADER
# =========================================================

# =========================================================
# THREE TABS
# =========================================================
tab1, tab2, tab3 = st.tabs([
    "Intelligence Brief",
    "Analysis",
    "Methodology"
])

# =========================================================
# TAB 1 — INTELLIGENCE BRIEF
# =========================================================
with tab1:
    render_intelligence_brief(df)

# =========================================================
# TAB 2 — ANALYSIS
# =========================================================
with tab2:

    # Top metrics
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total events",    len(df))
    c2.metric("Countries",       df["country"].nunique())
    c3.metric("Presidents",      df["president"].nunique() if "president" in df.columns else "—")
    scored_n = int((df["needs_scoring"] == False).sum()) if "needs_scoring" in df.columns else len(df)
    c4.metric("Scored events",   scored_n)
    c5.metric("Pending scoring", len(df) - scored_n)

    st.divider()

    # Dimension averages
    st.subheader("Behavioural Dimensions")
    st.caption(
        "Five observable dimensions of presidential governance behaviour. "
        "Scores are 0.0–1.0. Null = no signal in this event."
    )
    dim_cols = st.columns(5)
    for i, dim in enumerate(DIMENSIONS):
        avg = dim_avg(df, dim)
        cov = dim_n(df, dim)
        if avg is not None:
            dim_cols[i].metric(DIMENSION_LABELS[dim], "{:.2f}".format(avg), delta="{} events".format(cov))
        else:
            dim_cols[i].metric(DIMENSION_LABELS[dim], "—")
    st.caption(
        "Scores reflect observable signals in reported news events, not governance outcomes. "
        "Absence of signal is not evidence of absence of behaviour. "
        "Countries with fewer than {} events should be interpreted with caution.".format(MIN_EVENTS)
    )

    st.divider()

    # Dimension profiles by country
    st.subheader("Dimension Profiles by Country")
    if not df.empty:
        rows = []
        for country in df["country"].dropna().unique():
            cdf  = df[df["country"] == country]
            pres = CURRENT_PRESIDENTS.get(country, "")
            n    = len(cdf)
            row  = {
                "Country":   country,
                "President": pres,
                "Events":    n,
                "Ready":     "Yes" if n >= MIN_EVENTS else "Low ({})".format(n),
            }
            for dim in DIMENSIONS:
                avg = dim_avg(cdf, dim)
                row[DIMENSION_LABELS[dim]] = "{:.2f}".format(avg) if avg is not None else "—"
            rows.append(row)
        if rows:
            st.dataframe(
                pd.DataFrame(rows).sort_values("Events", ascending=False),
                use_container_width=True
            )

    st.divider()

    # Temporal trends
    st.subheader("Dimension Trends Over Time")
    if "month" in df.columns and scored_n > 0:
        temp_view = st.radio("View by", ["Month", "Week"], horizontal=True)
        time_col  = "month" if temp_view == "Month" else "week"
        sel_dim   = st.selectbox("Dimension", DIMENSIONS, format_func=lambda x: DIMENSION_LABELS[x])
        col_name  = "dim_" + sel_dim
        if col_name in df.columns:
            trend_df = df[df[col_name].notna()].groupby(time_col)[col_name].mean().reset_index()
            trend_df.columns = [time_col, DIMENSION_LABELS[sel_dim]]
            if not trend_df.empty:
                st.line_chart(trend_df.set_index(time_col))
    else:
        st.info("Temporal trends activate after events are scored. Run llm_reviewer_v3.py.")

    st.divider()

    # Governance domains
    st.subheader("Governance Domains")
    d1, d2 = st.columns(2)
    domain_counts = df["domain"].value_counts().reset_index()
    domain_counts.columns = ["domain", "count"]
    d1.bar_chart(domain_counts.set_index("domain"))
    if "month" in df.columns:
        domain_time = df.groupby(["month","domain"]).size().unstack(fill_value=0)
        if not domain_time.empty:
            d2.caption("Domain signals over time")
            d2.line_chart(domain_time)

    st.divider()

    # Presidential tracker
    st.subheader("Presidential Signal Tracker")
    if not df.empty and "president" in df.columns:
        tracker_rows = []
        for (country, president), gdf in df.groupby(["country","president"]):
            n          = len(gdf)
            top_domain = gdf["domain"].value_counts().idxmax() if not gdf.empty else "—"
            top_action = gdf["action_type"].value_counts().idxmax() if not gdf.empty else "—"
            row = {
                "Country":   country,
                "President": president,
                "Events":    n,
                "Top domain": top_domain,
                "Top action": top_action,
            }
            for dim in DIMENSIONS:
                avg = dim_avg(gdf, dim)
                row[DIMENSION_LABELS[dim]] = "{:.2f}".format(avg) if avg is not None else "—"
            tracker_rows.append(row)
        if tracker_rows:
            st.dataframe(
                pd.DataFrame(tracker_rows).sort_values("Events", ascending=False),
                use_container_width=True
            )

    st.divider()

    # Narrative synthesis
    st.subheader("Governance Behaviour Narrative")
    st.caption(
        "LLM-generated interpretation based on dimension scores and event patterns. "
        "Grounded in observable signals only — no leadership theory labels."
    )
    if not API_KEY:
        st.warning("Set ANTHROPIC_API_KEY environment variable to enable narrative synthesis.")
    else:
        active = (
            df.groupby(["country","president"]).size()
            .reset_index(name="events")
            .query("events >= 3")
            .sort_values("events", ascending=False)
        )
        if active.empty:
            st.info("Not enough events. Run the extractor to collect more data.")
        else:
            country_sel = st.selectbox(
                "Generate narrative for:",
                ["Select a country"] + active["country"].tolist()
            )
            if country_sel != "Select a country":
                if st.button("Generate narrative"):
                    p_df      = df[df["country"] == country_sel]
                    president = CURRENT_PRESIDENTS.get(country_sel, "")
                    n         = len(p_df)
                    if n < MIN_EVENTS:
                        st.warning(
                            "{} has {} events — below the {} event threshold. "
                            "Interpret with caution.".format(country_sel, n, MIN_EVENTS)
                        )
                    with st.spinner("Generating for {}...".format(country_sel)):
                        narrative = generate_synthesis(country_sel, president, p_df)
                    if narrative:
                        st.markdown("**{} — {}**".format(country_sel, president))
                        dim_c = st.columns(5)
                        for i, dim in enumerate(DIMENSIONS):
                            avg = dim_avg(p_df, dim)
                            cov = dim_n(p_df, dim)
                            dim_c[i].metric(
                                DIMENSION_LABELS[dim],
                                "{:.2f}".format(avg) if avg is not None else "—",
                                delta="n={}".format(cov)
                            )
                        st.write(narrative)
                        st.caption(
                            "Model: claude-sonnet-4-20250514 | "
                            "Source: observable news signals only"
                        )

    st.divider()

    # Coverage map
    st.subheader("Signal Coverage — All 54 Countries")
    st.caption("Countries with zero events reflect feed availability gaps, not leadership silence")
    coverage_data = []
    for country in ALL_54:
        count     = len(df_all[df_all["country"] == country])
        president = CURRENT_PRESIDENTS.get(country, "")
        if count >= MIN_EVENTS:   status = "Strong"
        elif count >= 10:         status = "Building"
        elif count > 0:           status = "Thin"
        else:                     status = "No data"
        coverage_data.append({
            "Country":   country,
            "President": president,
            "Events":    count,
            "Status":    status,
        })
    st.dataframe(
        pd.DataFrame(coverage_data).sort_values("Events", ascending=False),
        use_container_width=True
    )
    reg_cols = st.columns(5)
    for col, region in zip(reg_cols, REGION_MAP.keys()):
        covered = len(df_all[df_all["country"].isin(REGION_MAP[region])]["country"].unique())
        col.metric(region, "{}/{}".format(covered, len(REGION_MAP[region])))

    st.divider()

    # Source bias audit
    st.subheader("Source Bias Audit")
    st.caption("State-controlled sources are down-weighted in filter scoring")
    if "source_bias" in df.columns:
        b1, b2 = st.columns(2)
        bias_counts = df["source_bias"].value_counts().reset_index()
        bias_counts.columns = ["source_bias", "count"]
        b1.bar_chart(bias_counts.set_index("source_bias"))
        state_events = df[df["source_bias"] == "state"]
        if not state_events.empty:
            b2.caption("Countries most affected by state-sourced events:")
            b2.dataframe(
                state_events.groupby("country").size()
                .reset_index(name="state_events")
                .sort_values("state_events", ascending=False),
                use_container_width=True
            )

    st.divider()

    # All events
    st.subheader("All Events")
    cols_to_show = [
        "date","country","president","actor","action_type","domain","framing",
        "filter_score","source_tier",
        "dim_accountability","dim_responsiveness","dim_stewardship",
        "dim_institutional_integrity","dim_inclusion",
        "rationale","evidence"
    ]
    available = [c for c in cols_to_show if c in df.columns]
    st.dataframe(
        df[available].sort_values("date", ascending=False),
        use_container_width=True
    )
    st.divider()
    dl1, dl2 = st.columns(2)
    dl1.download_button(
        "Download filtered dataset",
        df.to_json(orient="records", indent=2),
        "polis_filtered.json",
        "application/json"
    )
    dl2.download_button(
        "Download full dataset",
        df_all.to_json(orient="records", indent=2),
        "polis_full.json",
        "application/json"
    )

# =========================================================
# TAB 3 — METHODOLOGY
# =========================================================
with tab3:

    st.markdown("### What POLIS Measures")
    st.markdown(
        "POLIS is a computational instrument for tracking observable presidential leadership "
        "behaviour across all 54 African countries. It records governance signals derived from "
        "news media. It does not measure leadership quality, intention, or outcomes. "
        "News-based event data was selected as the primary source because it provides systematic, "
        "reproducible, real-time coverage of observable presidential behaviour at continental scale, "
        "consistent with established practice in computational political science."
    )

    st.divider()
    st.markdown("### The Five Dimensions")
    st.markdown(
        "Each dimension is grounded in the theoretical literature and operationalised as a set "
        "of observable governance signals detectable from news-based event data. The dimensions "
        "are not exhaustive of presidential leadership behaviour. They represent the subset of "
        "theoretically significant behaviours that are systematically observable through public "
        "reporting. Together they constitute a behavioural signal profile rather than a "
        "comprehensive leadership assessment."
    )

    with st.expander("Accountability"):
        st.markdown(
            "Accountability measures the degree to which observable presidential behaviour reflects "
            "submission to or enforcement of institutional oversight mechanisms. In principal-agent "
            "theory, accountability is the primary instrument by which principals constrain agent "
            "behaviour and correct for agency dilemmas (Lane, 2005). In the African governance context, "
            "accountability signals are particularly significant because formal oversight institutions - "
            "anti-corruption agencies, independent judiciaries, parliamentary committees - frequently "
            "operate under political pressure and their activation represents a meaningful governance "
            "signal in itself.\n\n"
            "Observable signals include: anti-corruption enforcement actions; prosecutions of public "
            "officials; responses to audit findings; activation of judicial accountability processes; "
            "and public acknowledgement of institutional findings. Low accountability scores indicate "
            "an absence of observable oversight activity - either because oversight institutions are "
            "inactive, because enforcement is selective rather than systemic, or because such actions "
            "are not publicly reported. The direction of accountability matters: a president who "
            "prosecutes political opponents while shielding allies produces a different governance "
            "pattern from one who applies enforcement consistently, and POLIS scores reflect this "
            "asymmetry where evidence is present.\n\n"
            "Theoretical root: Principal-agent theory (Jensen and Meckling, 1976; Lane, 2005)"
        )

    with st.expander("Responsiveness"):
        st.markdown(
            "Responsiveness measures the degree to which observable presidential actions follow stated "
            "priorities or demonstrated public needs. It operationalises the core principal-agent "
            "obligation of the agent to serve the principal's interests - in this context, the "
            "obligation of the president to govern in ways that address citizen welfare and deliver on "
            "public commitments. Hartley and Benington (2010) extend this beyond mere compliance with "
            "citizen preferences to encompass active orientation toward public value creation, "
            "distinguishing between presidents who respond to immediate political pressures and those "
            "who pursue longer-term citizen welfare objectives.\n\n"
            "Observable signals include: policy implementation actions following public announcements; "
            "welfare and social service delivery decisions; crisis response actions; citizen-directed "
            "resource allocation; and legislative or executive actions that address identified public "
            "needs. The responsiveness dimension is particularly sensitive to the visibility-action "
            "tension identified in the neopatrimonialism literature - high volumes of public statements "
            "about citizen welfare that are unaccompanied by corresponding implementation signals "
            "produce lower responsiveness scores than quieter governance accompanied by tangible "
            "delivery actions.\n\n"
            "Theoretical root: Principal-agent theory and Public leadership literature (Hartley and Benington, 2010)"
        )

    with st.expander("Stewardship"):
        st.markdown(
            "Stewardship measures the degree to which observable presidential behaviour reflects "
            "investment in long-term public institutional capability. The concept draws on Hartley "
            "and Benington's (2010) public value framework and on the broader public administration "
            "literature's emphasis on the custodial obligations of public leaders - the responsibility "
            "to maintain and strengthen the institutional infrastructure of the state for future "
            "generations, not merely to respond to current political demands. In the African context, "
            "where state institutional capacity is frequently fragile and the temptation to personalise "
            "or weaken independent institutions for short-term political gain is structurally strong, "
            "stewardship signals carry particular diagnostic weight.\n\n"
            "Observable signals include: institutional reform initiatives; investment in judicial, "
            "legislative, or civil service capacity; infrastructure development with long-term public "
            "benefit; public service appointments oriented toward capability rather than loyalty; and "
            "legislative actions that strengthen rather than circumvent institutional frameworks. "
            "Stewardship is analytically distinct from institutional integrity: a president may invest "
            "in institutions while simultaneously using informal channels to control them, producing "
            "high stewardship and low institutional integrity scores simultaneously. This combination "
            "is a meaningful governance pattern in the neopatrimonialism literature, associated with "
            "what Bratton and van de Walle (1997) term institutional capture.\n\n"
            "Theoretical root: Public leadership literature (Hartley and Benington, 2010; 't Hart and Uhr, 2008)"
        )

    with st.expander("Institutional Integrity"):
        st.markdown(
            "Institutional integrity measures the degree to which presidential authority is exercised "
            "through formal constitutional channels rather than through personalised, informal, or "
            "bypass mechanisms. It is the dimension most directly derived from the neopatrimonialism "
            "framework, operationalising Bratton and van de Walle's (1997) central analytical concern "
            "with the gap between the formal-legal register of African governance and its "
            "informal-patrimonial reality. A president who consistently routes decisions through "
            "parliament, respects judicial independence, and operates within procedural constraints "
            "signals a governance orientation toward formal institutionalism; a president who routinely "
            "issues executive decrees that bypass legislative processes, dismisses independent "
            "institutional actors, or uses security services for domestic political purposes signals "
            "the opposite.\n\n"
            "Observable signals include: parliamentary routing of major policy decisions; respect for "
            "judicial rulings including those that constrain executive power; procedural compliance in "
            "appointments and dismissals; absence of executive override of independent institutional "
            "processes; and engagement with constitutional constraints rather than circumvention of "
            "them. Low institutional integrity scores do not necessarily indicate authoritarianism - "
            "they may reflect governance contexts where formal institutions are genuinely weak and "
            "informal mechanisms are the only functional channels available.\n\n"
            "Theoretical root: Neopatrimonialism (Bratton and van de Walle, 1997; Chabal and Daloz, 1999)"
        )

    with st.expander("Inclusion"):
        st.markdown(
            "Inclusion measures the degree to which observable presidential behaviour reflects "
            "accommodation of diverse actors, voices, and interests in governance processes. It draws "
            "on the principal-agent framework's concern with the scope of the principal - whose "
            "interests the agent is actually serving - and extends it through the public leadership "
            "literature's emphasis on participatory and relational governance (Hartley and Benington, "
            "2010). In the African context, inclusion carries additional theoretical weight through "
            "the ubuntu tradition of relational governance, which frames leadership not as individual "
            "authority but as collective responsibility embedded in community relationships (Bolden "
            "and Kirk, 2009). However, given the observability constraints of news-based data "
            "collection, POLIS measures the procedural and institutional dimensions of inclusion "
            "rather than its relational quality.\n\n"
            "Observable signals include: public consultations and national dialogues; cross-party "
            "engagement and opposition dialogue; community-level forums and civic engagement; "
            "coalition-building behaviour; appointments that reflect diversity across regional, "
            "ethnic, or political lines; and policy processes that incorporate civil society input. "
            "Inclusion is consistently the weakest dimension in the current dataset, a pattern that "
            "warrants careful interpretation: it may reflect genuine exclusionary governance, the "
            "structural under-reporting of community-level engagement in national news media, or both.\n\n"
            "Theoretical root: Principal-agent theory, Public leadership literature, and Ubuntu/relational governance (Bolden and Kirk, 2009)"
        )

    st.divider()
    st.markdown("### Theoretical Framework")
    st.markdown(
        "POLIS is grounded in three complementary theoretical traditions, each selected for its "
        "explanatory purchase on different dimensions of African presidential leadership behaviour. "
        "Together they provide a multi-layered analytical architecture that moves beyond "
        "single-framework approaches to governance measurement."
    )

    st.markdown("**Primary - Principal-Agent Theory**")
    st.markdown(
        "Principal-agent theory provides the foundational logic of the POLIS measurement "
        "architecture. The framework, originally developed in the context of organisational "
        "economics (Jensen and Meckling, 1976), models the relationship between a principal - "
        "the party who delegates authority - and an agent - the party entrusted to act on the "
        "principal's behalf. In the public governance context, citizens are the collective principal "
        "and the president is the agent entrusted with executive authority (Lane, 2005; Strom, 2000). "
        "The central analytical problem is the agency dilemma: agents may pursue their own interests "
        "rather than those of the principal, particularly where accountability mechanisms are weak, "
        "information is asymmetric, or institutional constraints are insufficient to discipline "
        "behaviour.\n\n"
        "In the African context, this dilemma is acute. The structural conditions for effective "
        "principal-agent accountability - competitive elections, independent judiciaries, free media, "
        "active civil society - are present in varying and often compromised forms across the "
        "continent. POLIS does not assume their presence; rather, it uses observable signals to "
        "measure the degree to which presidential behaviour reflects agent accountability to citizens. "
        "The dimensions of accountability, responsiveness, and inclusion are direct "
        "operationalisations of principal-agent theory: accountability measures whether the agent "
        "submits to oversight; responsiveness measures whether the agent acts in the principal's "
        "interests; inclusion measures whether the agent governs on behalf of the full principal "
        "population rather than a narrow coalition."
    )

    st.markdown("**Supporting - Public Leadership Literature**")
    st.markdown(
        "Public leadership theory extends the principal-agent framework by foregrounding the "
        "distinctive character of leadership in public institutional contexts (Hartley and Benington, "
        "2010; 't Hart and Uhr, 2008). Where principal-agent theory emphasises the control and "
        "accountability relationship between citizen and leader, public leadership theory emphasises "
        "the stewardship relationship - the obligation of leaders to maintain, strengthen, and pass "
        "on the public institutions and capabilities they inherit. Hartley and Benington (2010) argue "
        "that public value creation - the generation of outcomes that serve the long-term public "
        "interest - is the defining purpose of public leadership and cannot be reduced to simple "
        "responsiveness to current citizen preferences.\n\n"
        "This tradition produces the stewardship dimension in POLIS - the observable commitment of a "
        "president to investing in institutional capability that outlasts their administration. It also "
        "deepens the responsiveness dimension beyond simple policy compliance, framing it as an active "
        "orientation toward citizen welfare rather than merely reactive behaviour. In the African "
        "context, where institutional fragility is a persistent governance challenge, stewardship "
        "signals carry particular analytical weight as indicators of a developmental rather than "
        "extractive leadership orientation."
    )

    st.markdown("**Contextual - Neopatrimonialism**")
    st.markdown(
        "Neopatrimonialism, as developed principally by Bratton and van de Walle (1997) and extended "
        "by Chabal and Daloz (1999), provides the essential contextual framework for interpreting "
        "African presidential governance. The concept captures the empirical reality that most African "
        "states operate simultaneously across two registers: the formal-legal register of "
        "constitutional governance, with its official institutions, procedures, and accountability "
        "mechanisms; and the informal-patrimonial register of personal rule, clientelism, and "
        "network-based authority. Presidents occupy both registers simultaneously, using the formal "
        "apparatus of the state to satisfy donor requirements and constitutional obligations while "
        "exercising real power through informal networks of personal loyalty, ethnic solidarity, and "
        "resource distribution.\n\n"
        "This dual-register character of African governance has profound implications for measurement. "
        "Formal governance indicators - legislative output, judicial appointments, budget allocations "
        "- may present a misleading picture of institutional health if they are disconnected from the "
        "informal power dynamics that actually determine governance outcomes. POLIS addresses this "
        "directly through the institutional integrity dimension, which measures not simply whether "
        "formal institutions are used, but whether they are used as the primary mechanism of "
        "governance or as a facade behind which informal authority operates."
    )

    st.divider()
    st.markdown("### Analytic Tensions")
    st.markdown(
        "Three structural tensions derived from the African governance literature underpin the "
        "classification logic (Bratton and van de Walle, 1997; Herbst, 2000; Chabal and Daloz, 1999)."
    )

    st.markdown("**Formal institutions versus informal power**")
    st.markdown(
        "African presidents routinely operate across two registers simultaneously - the formal "
        "constitutional apparatus of the state and informal networks of personal loyalty, patronage, "
        "and ethnic solidarity. Bratton and van de Walle (1997) identify this duality as the defining "
        "feature of neopatrimonial governance. POLIS tracks which register dominates observable "
        "behaviour in a given period, using institutional integrity signals as the primary indicator."
    )

    st.markdown("**Centralisation versus accommodation**")
    st.markdown(
        "The distribution or concentration of power is a fundamental axis of African presidential "
        "governance (Herbst, 2000). Presidents who centralise - through executive decrees, dismissals "
        "of independent institutional actors, or security deployments against political competitors "
        "- produce measurably different signal patterns from those who accommodate competing centres "
        "of power through appointments, dialogue, and coalition building. This tension drives the "
        "accountability and inclusion dimensions."
    )

    st.markdown("**Visibility versus action**")
    st.markdown(
        "Chabal and Daloz (1999) observe that African political leadership is frequently performative "
        "- sophisticated governance rhetoric directed at international audiences while domestic "
        "behaviour follows different logics. POLIS is specifically designed to detect this divergence "
        "by measuring whether public statement events are followed by corresponding policy or "
        "enforcement actions, or whether high communication density coexists with low delivery signals."
    )

    st.divider()
    st.markdown("### Scoring")
    st.markdown(
        "Each event is scored independently by an LLM classifier against the five dimensions using "
        "the evidence text, action type, and governance domain. Scores range from 0.0 to 1.0. "
        "Country-level dimension profiles aggregate individual event scores across the observation window.\n\n"
        "**Null** indicates no observable signal for that dimension. It is not evidence of absence of behaviour.\n\n"
        "**0.0** indicates clear evidence of absence or active violation of the dimension.\n\n"
        "**1.0** indicates a strong, unambiguous positive signal for that dimension.\n\n"
        "Countries with fewer than 30 events should be interpreted with caution. "
        "Countries with fewer than 10 events are insufficient for pattern-level claims."
    )

    st.divider()
    st.markdown("### Dimension Development")
    st.markdown(
        "The five dimensions were derived through a review of the principal-agent, public leadership, "
        "and neopatrimonialism literatures for relevant indicators demonstrating leadership qualities "
        "that are observable through news-based event data. Formal validation against human-coded "
        "ground truth has not yet been conducted and is identified as a priority for future "
        "development of the instrument."
    )

    st.divider()
    st.markdown("### Observability Limits")
    st.info(
        "POLIS observes what is reported in news feeds, not what happens in closed governance spaces. "
        "Absence of signal is not evidence of absence of behaviour. Presidents who govern quietly "
        "will produce fewer signals than those who govern publicly. State-controlled sources are "
        "flagged and down-weighted in the scoring pipeline. Coverage varies significantly by country "
        "depending on feed availability, and cross-country comparisons should account for this "
        "structural asymmetry. The dimensions were designed around what is observable through public "
        "reporting - a methodological choice grounded in what presidential leadership looks like "
        "from the outside, which is what citizens, journalists, and policy actors experience. The pipeline has a structural positive bias: it captures observable governance actions more reliably than inaction, failure to deliver, or governance harm. Scores should be read as a floor, not a ceiling."
    )

    st.divider()
    st.markdown("### Data Collection")
    st.markdown(
        "Events are ingested daily from RSS feeds across presidential websites, independent domestic "
        "media, regional outlets, and international sources across all 54 African countries. Sources "
        "are classified by tier (T0 official; T1 independent domestic; T2 regional; T3 international) "
        "and bias (state-controlled or independent). Systematic daily collection commenced May 2026. "
        "The dataset contains events dating from June 2024 to present, reflecting the retrospective "
        "coverage of some feed sources."
    )

    st.divider()
    st.markdown("### References")
    st.markdown(
        "Bolden, R. and Kirk, P. (2009). African leadership: Surfacing new understandings through "
        "leadership development. *International Journal of Cross Cultural Management, 9*(1), 69-86.\n\n"
        "Bratton, M. and van de Walle, N. (1997). *Democratic Experiments in Africa.* Cambridge University Press.\n\n"
        "Chabal, P. and Daloz, J-P. (1999). *Africa Works: Disorder as Political Instrument.* James Currey.\n\n"
        "Hartley, J. and Benington, J. (2010). *Public Value: Theory and Practice.* Open University Press.\n\n"
        "Herbst, J. (2000). *States and Power in Africa.* Princeton University Press.\n\n"
        "Jensen, M. and Meckling, W. (1976). Theory of the firm: Managerial behaviour, agency costs "
        "and ownership structure. *Journal of Financial Economics, 3*(4), 305-360.\n\n"
        "Lane, J-E. (2005). *Public Administration and Public Management.* Routledge.\n\n"
        "Strom, K. (2000). Delegation and accountability in parliamentary democracies. "
        "*European Journal of Political Research, 37*(3), 261-289.\n\n"
        "'t Hart, P. and Uhr, J. (2008). *Public Leadership Perspectives and Practices.* ANU Press."
    )

    st.divider()
    st.markdown("### Citation")
    st.code(
        "POLIS - Public Leadership Observation and Insight System. "
        "Change-alongside, 2026. https://polis-dashboard.streamlit.app",
        language=None
    )
    st.caption(
        "Dataset version: 1.0 · Extractor: v8 · Reviewer: v3.0 · "
        "Model: claude-sonnet-4-20250514 · "
        "Principal-agent theory + Public leadership + Neopatrimonialism"
    )