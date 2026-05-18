import streamlit as st
import pandas as pd
import json
import urllib.request
import os

st.set_page_config(
    page_title="POLIS — African Presidential Leadership",
    layout="wide",
    page_icon="🌍",
    initial_sidebar_state="expanded"
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
    "institutional_integrity": "Institutional Integrity",
    "inclusion":               "Inclusion",
}

DIMENSION_DESCRIPTIONS = {
    "accountability":
        "President enforcing or submitting to institutional oversight — "
        "anti-corruption, judicial enforcement, audit responses.",
    "responsiveness":
        "Actions following stated priorities or public needs — "
        "policy implementation, welfare, crisis response.",
    "stewardship":
        "Investment in long-term public capability — "
        "institutional reform, infrastructure, legislative strengthening.",
    "institutional_integrity":
        "Authority exercised through formal institutions, not bypassing them — "
        "parliamentary routing, judicial independence, procedural compliance.",
    "inclusion":
        "Accommodation of diverse actors and voices — "
        "consultations, dialogues, opposition engagement, community forums.",
}

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

ALL_54 = sorted(CURRENT_PRESIDENTS.keys())
MIN_EVENTS = 30  # Minimum for meaningful dimension interpretation

# =========================================================
# DATA LOADING
# =========================================================
@st.cache_data(ttl=300)
def load_data():
    if not os.path.exists(DATASET_FILE):
        return pd.DataFrame()

    with open(DATASET_FILE, "r") as f:
        raw = json.load(f)

    events = [e for e in raw if e.get("is_leadership_event")]
    if not events:
        return pd.DataFrame()

    df = pd.DataFrame(events).drop_duplicates(subset=["evidence"])

    # Date fields
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "week"  not in df.columns and "date" in df.columns:
        df["week"]  = df["date"].dt.strftime("%Y-W%W")
    if "month" not in df.columns and "date" in df.columns:
        df["month"] = df["date"].dt.strftime("%Y-%m")

    # Backfill optional fields
    for col, default in [
        ("source_bias",  "independent"),
        ("framing",      "neutral"),
        ("feed_count",   1),
        ("filter_score", 0),
        ("needs_scoring", True),
    ]:
        if col not in df.columns:
            df[col] = default

    # Keep president names current
    for country, president in CURRENT_PRESIDENTS.items():
        df.loc[df["country"] == country, "president"] = president

    # Extract dimension scores into flat columns for easy aggregation
    for dim in DIMENSIONS:
        col = "dim_" + dim
        if col not in df.columns:
            df[col] = df["dimensions"].apply(
                lambda d: d.get(dim, {}).get("score")
                if isinstance(d, dict) else None
            ) if "dimensions" in df.columns else None

    return df


def dim_avg(df, dim):
    """Mean score for a dimension, ignoring nulls."""
    col = "dim_" + dim
    if col not in df.columns:
        return None
    vals = df[col].dropna()
    return round(float(vals.mean()), 2) if len(vals) > 0 else None


def dim_coverage(df, dim):
    """Number of events with a non-null score for this dimension."""
    col = "dim_" + dim
    if col not in df.columns:
        return 0
    return int(df[col].notna().sum())


def score_bar(score):
    """Simple ASCII progress representation for tables."""
    if score is None:
        return "—"
    filled = int(score * 10)
    return "|" * filled + "." * (10 - filled) + f"  {score:.2f}"


# =========================================================
# LLM NARRATIVE SYNTHESIS
# =========================================================
def generate_synthesis(country, president, events_df):
    if len(events_df) == 0 or not API_KEY:
        return None

    # Build dimension profile
    dim_profile = {}
    for dim in DIMENSIONS:
        avg = dim_avg(events_df, dim)
        cov = dim_coverage(events_df, dim)
        dim_profile[dim] = {"avg": avg, "coverage": cov}

    event_list = "\n".join([
        "- " + str(row.get("evidence", "")) +
        " [" + str(row.get("action_type", "")) + " | " +
        str(row.get("domain", "")) + "]"
        for _, row in events_df.head(25).iterrows()
    ])

    dim_summary = "\n".join([
        "{}: {} (n={})".format(
            DIMENSION_LABELS[d],
            "{:.2f}".format(v["avg"]) if v["avg"] is not None else "no data",
            v["coverage"]
        )
        for d, v in dim_profile.items()
    ])

    prompt = (
        "You are an analyst for POLIS — the Public Leadership Observation and Insight System. "
        "POLIS tracks observable presidential leadership behaviour across Africa using five "
        "behavioural dimensions: Accountability, Responsiveness, Stewardship, "
        "Institutional Integrity, and Inclusion.\n\n"
        "Write a concise analytical narrative (4-5 sentences) about the governance behaviour "
        "pattern observed for this president. Ground every claim in the dimension scores and "
        "events provided. Note which dimensions are strongest and weakest. "
        "Note any tensions between dimensions. Do not use leadership theory labels. "
        "Use plain, precise language suitable for a governance researcher or journalist.\n\n"
        "Country: {}\nPresident: {}\nTotal events: {}\n\n"
        "Dimension profile:\n{}\n\n"
        "Events sample:\n{}\n\n"
        "Start with: 'Based on {} observable leadership signal events...'. "
        "No bullets. No headers. No theory labels."
    ).format(
        country, president, len(events_df),
        dim_summary, event_list, len(events_df)
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
scored_df = df_all[df_all.get("needs_scoring", pd.Series([True]*len(df_all))) == False] \
    if not df_all.empty else pd.DataFrame()

# =========================================================
# HEADER
# =========================================================
st.title("POLIS — African Presidential Leadership")
st.caption(
    "Public Leadership Observation & Insight System · "
    "54 Countries · 5 Behavioural Dimensions · v8.0  |  "
    "Principal-agent theory · Public leadership · Neopatrimonialism"
)

if df_all.empty:
    st.warning("No data found. Run `python3 extractor.py` to collect events.")
    st.stop()

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.header("Filters")

    sel_country = st.selectbox(
        "Country", ["All"] + sorted(df_all["country"].dropna().unique().tolist())
    )
    sel_region = st.selectbox("Region", ["All"] + list(REGION_MAP.keys()))
    sel_domain = st.selectbox(
        "Domain", ["All"] + sorted(df_all["domain"].dropna().unique().tolist())
    )
    sel_tier   = st.selectbox("Source tier", ["All", "T0", "T1", "T2", "T3"])
    hide_state = st.checkbox("Hide state-controlled sources", value=False)
    only_scored = st.checkbox("Only scored events", value=False)

    st.divider()
    needs = int(df_all.get("needs_scoring", pd.Series([False]*len(df_all))).sum()) \
        if "needs_scoring" in df_all.columns else 0
    st.metric("Pending scoring", needs,
              help="Run llm_reviewer_v3.py to score these events")

# =========================================================
# APPLY FILTERS
# =========================================================
df = df_all.copy()
if sel_country != "All": df = df[df["country"] == sel_country]
if sel_region  != "All": df = df[df["country"].isin(REGION_MAP.get(sel_region, []))]
if sel_domain  != "All": df = df[df["domain"] == sel_domain]
if sel_tier    != "All": df = df[df["source_tier"] == sel_tier]
if hide_state and "source_bias" in df.columns:
    df = df[df["source_bias"] != "state"]
if only_scored and "needs_scoring" in df.columns:
    df = df[df["needs_scoring"] == False]

# =========================================================
# TOP METRICS
# =========================================================
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total events",    len(df))
c2.metric("Countries",       df["country"].nunique())
c3.metric("Presidents",      df["president"].nunique() if "president" in df.columns else "—")
scored_n = int((df["needs_scoring"] == False).sum()) \
    if "needs_scoring" in df.columns else 0
c4.metric("Scored events",   scored_n)
c5.metric("Pending scoring", len(df) - scored_n)

st.divider()

# =========================================================
# SECTION 1 — DIMENSION FRAMEWORK
# =========================================================
st.subheader("Behavioural Dimensions")
st.caption(
    "POLIS measures five observable dimensions of presidential governance behaviour. "
    "Scores are 0.0-1.0. Null = no signal in this event. "
    "Grounded in principal-agent theory, public leadership literature, and neopatrimonialism."
)

dim_cols = st.columns(5)
for i, dim in enumerate(DIMENSIONS):
    avg = dim_avg(df, dim)
    cov = dim_coverage(df, dim)
    label = DIMENSION_LABELS[dim]
    if avg is not None:
        dim_cols[i].metric(
            label,
            "{:.2f}".format(avg),
            delta="{} events".format(cov),
            help=DIMENSION_DESCRIPTIONS[dim]
        )
    else:
        dim_cols[i].metric(label, "—", help=DIMENSION_DESCRIPTIONS[dim])

st.caption(
    "**Observability note:** Scores reflect observable signals in reported news events, "
    "not governance outcomes. Absence of signal is not evidence of absence of behaviour. "
    "Countries with fewer than {} events should be interpreted with caution.".format(MIN_EVENTS)
)

st.divider()

# =========================================================
# SECTION 2 — DIMENSION PROFILES BY COUNTRY
# =========================================================
st.subheader("Dimension Profiles by Country")
st.caption("Average dimension score per country — scored events only")

if not df.empty:
    country_dim_rows = []
    for country in df["country"].dropna().unique():
        cdf = df[df["country"] == country]
        president = CURRENT_PRESIDENTS.get(country, "")
        n = len(cdf)
        row = {
            "Country":   country,
            "President": president,
            "Events":    n,
            "Ready":     "Yes" if n >= MIN_EVENTS else "Low ({})".format(n),
        }
        for dim in DIMENSIONS:
            avg = dim_avg(cdf, dim)
            row[DIMENSION_LABELS[dim]] = "{:.2f}".format(avg) if avg is not None else "—"
        country_dim_rows.append(row)

    if country_dim_rows:
        country_dim_df = pd.DataFrame(country_dim_rows).sort_values("Events", ascending=False)
        st.dataframe(country_dim_df, use_container_width=True)
        st.caption(
            "Low = fewer than {} events. "
            "Interpret with caution. "
            "Score of — means no observable signal for that dimension in this dataset.".format(MIN_EVENTS)
        )

st.divider()

# =========================================================
# SECTION 3 — TEMPORAL DIMENSION TRENDS
# =========================================================
st.subheader("Dimension Trends Over Time")
st.caption("How behavioural signals evolve — requires sufficient scored events")

if "month" in df.columns and scored_n > 0:
    temp_view = st.radio("View by", ["Month", "Week"], horizontal=True)
    time_col  = "month" if temp_view == "Month" else "week"
    sel_dim   = st.selectbox(
        "Dimension",
        DIMENSIONS,
        format_func=lambda x: DIMENSION_LABELS[x]
    )

    col_name = "dim_" + sel_dim
    if col_name in df.columns:
        trend_df = df[df[col_name].notna()].groupby(time_col)[col_name].mean().reset_index()
        trend_df.columns = [time_col, DIMENSION_LABELS[sel_dim]]
        if not trend_df.empty:
            st.line_chart(trend_df.set_index(time_col))
        else:
            st.info("No scored data yet for this dimension.")
else:
    st.info("Temporal trends activate after events are scored. Run llm_reviewer_v3.py.")

st.divider()

# =========================================================
# SECTION 4 — GOVERNANCE DOMAINS
# =========================================================
st.subheader("Governance Domains")
st.caption("Distribution of events by governance domain")

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

# =========================================================
# SECTION 5 — PRESIDENTIAL TRACKER
# =========================================================
st.subheader("Presidential Signal Tracker")
st.caption(
    "Event count and top domain per president. "
    "Dimension scores available after running llm_reviewer_v3.py."
)

if not df.empty and "president" in df.columns:
    tracker_rows = []
    for (country, president), gdf in df.groupby(["country","president"]):
        n = len(gdf)
        top_domain = gdf["domain"].value_counts().idxmax() if not gdf.empty else "—"
        top_action = gdf["action_type"].value_counts().idxmax() if not gdf.empty else "—"
        row = {
            "Country":    country,
            "President":  president,
            "Events":     n,
            "Top domain": top_domain,
            "Top action": top_action,
        }
        for dim in DIMENSIONS:
            avg = dim_avg(gdf, dim)
            row[DIMENSION_LABELS[dim]] = "{:.2f}".format(avg) if avg is not None else "—"
        tracker_rows.append(row)

    if tracker_rows:
        tracker_df = pd.DataFrame(tracker_rows).sort_values("Events", ascending=False)
        st.dataframe(tracker_df, use_container_width=True)

st.divider()

# =========================================================
# SECTION 6 — AI NARRATIVE SYNTHESIS
# =========================================================
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
                c_events  = df[df["country"] == country_sel]
                president = CURRENT_PRESIDENTS.get(country_sel, "")
                n         = len(c_events)

                if n < MIN_EVENTS:
                    st.warning(
                        "{} has {} events — below the {} event threshold. "
                        "Interpret with caution.".format(country_sel, n, MIN_EVENTS)
                    )

                with st.spinner("Generating for {}...".format(country_sel)):
                    narrative = generate_synthesis(country_sel, president, c_events)

                if narrative:
                    st.markdown("**{} — {}**".format(country_sel, president))
                    dim_c = st.columns(5)
                    for i, dim in enumerate(DIMENSIONS):
                        avg = dim_avg(c_events, dim)
                        cov = dim_coverage(c_events, dim)
                        dim_c[i].metric(
                            DIMENSION_LABELS[dim],
                            "{:.2f}".format(avg) if avg is not None else "—",
                            delta="n={}".format(cov)
                        )
                    st.write(narrative)
                    st.caption(
                        "Scored events: {} | Model: claude-sonnet-4-20250514 | "
                        "Source: observable news signals only".format(scored_n)
                    )

st.divider()

# =========================================================
# SECTION 7 — COVERAGE MAP
# =========================================================
st.subheader("Signal Coverage — All 54 Countries")
st.caption("Countries with zero events reflect feed availability gaps, not leadership silence")

coverage_data = []
for country in ALL_54:
    count     = len(df_all[df_all["country"] == country])
    president = CURRENT_PRESIDENTS.get(country, "")
    if count >= MIN_EVENTS:
        status = "Strong"
    elif count >= 10:
        status = "Building"
    elif count > 0:
        status = "Thin"
    else:
        status = "No data"
    coverage_data.append({
        "Country":   country,
        "President": president,
        "Events":    count,
        "Status":    status,
    })

coverage_df = pd.DataFrame(coverage_data).sort_values("Events", ascending=False)
st.dataframe(coverage_df, use_container_width=True)

reg_cols = st.columns(5)
for col, region in zip(reg_cols, REGION_MAP.keys()):
    covered = len(df_all[df_all["country"].isin(REGION_MAP[region])]["country"].unique())
    col.metric(region, "{}/{}".format(covered, len(REGION_MAP[region])))

st.divider()

# =========================================================
# SECTION 8 — SOURCE BIAS AUDIT
# =========================================================
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

# =========================================================
# SECTION 9 — ALL EVENTS
# =========================================================
st.subheader("All Events")

cols_to_show = [
    "date", "country", "president", "actor", "action_type",
    "domain", "framing", "filter_score", "source_tier",
    "dim_accountability", "dim_responsiveness", "dim_stewardship",
    "dim_institutional_integrity", "dim_inclusion",
    "rationale", "evidence"
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

st.caption(
    "POLIS v8.0 · 5 Behavioural Dimensions · 54 Countries · "
    "Principal-agent theory + Public leadership + Neopatrimonialism · "
    "Observable signals only — not a measure of leadership quality"
)
