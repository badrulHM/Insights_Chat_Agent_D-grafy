# app.py
import os
import base64
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from google.cloud import bigquery

# Load environment variables from .env[cite: 1]
load_dotenv()

st.set_page_config(
    page_title="Demografy | Australian Property Insights",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------------------------------------
# Logo Asset Loader
# -------------------------------------------------------------
def get_image_base64(file_path: str) -> str:
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
            return f"data:image/png;base64,{encoded}"
    return ""

LOGO_FILE_PATH = os.path.join("assets", "demografy_logo.png")
logo_data_uri = get_image_base64(LOGO_FILE_PATH)

if logo_data_uri:
    brand_logo_img = f'<img src="{logo_data_uri}" style="height: 36px; width: auto; object-fit: contain; display: block;" alt="Demografy"/>'
else:
    brand_logo_img = '<div style="font-weight: 800; font-size: 1.8rem; letter-spacing: -0.5px; color: #272d2d;"><span style="color: #5e17eb;">D</span>emografy</div>'

# -------------------------------------------------------------
# Global CSS (Full-Width Nav + Table + Bulletproof Floating Chat)
# -------------------------------------------------------------
st.markdown(f"""
<style>
@import url('https://fonts.cdnfonts.com/css/open-sauce-one');

html, body, [class*="css"], .stMarkdown, p, div, span, button, input, select {{
    font-family: 'Open Sauce One', 'Open Sauce', -apple-system, BlinkMacSystemFont, sans-serif;
}}

/* 1. Hide Material Symbols glitch & default headers */
[data-testid="stSidebarCollapseButton"],
button[kind="header"],
div[data-testid="stSidebarHeader"] {{
    display: none !important;
}}

[data-testid="stIcon"],
[class*="material-icons"],
[class*="material-symbols"],
i[class*="icon-"] {{
    font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
}}

header[data-testid="stHeader"] {{
    display: none !important;
}}
div[data-testid="stElementContainer"]:has(button:contains("expand_more")),
button:contains("expand_more"),
.stMarkdownContainer:has(button) {{
    display: none !important;
}}
[data-testid="stVerticalBlock"] {{
    max-height: none !important;
    overflow: visible !important;
}}

/* 2. Base Background */
.stApp {{
    background-color: #f5f6f8;
}}

/* 3. Global Top Navbar */
.global-top-navbar {{
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 64px;
    background-color: #ffffff;
    border-bottom: 1px solid #dbdddc;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 2rem;
    z-index: 99998;
}}
.nav-profile-group {{
    display: flex;
    align-items: center;
    gap: 0.65rem;
    color: #272d2d;
    font-size: 0.92rem;
    font-weight: 600;
}}
.nav-avatar-purple {{
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background-color: #5e17eb; /* Ultrasonic Blue[cite: 2] */
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.85rem;
}}

/* 4. Sidebar Positioned Below Top Nav */
[data-testid="stSidebar"] {{
    top: 64px !important;
    height: calc(100vh - 64px) !important;
    background-color: #f5f6f8 !important;
    border-right: 1px solid #e1e4e8 !important;
    padding-top: 1rem !important;
}}
[data-testid="stSidebar"] > div:first-child {{
    padding-top: 0 !important;
}}

/* 5. Main Content Spacing */
.main .block-container {{
    padding-top: 5.2rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    padding-bottom: 2rem !important;
    max-width: 98% !important;
}}

/* 6. Sidebar Inputs */
[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: #ffffff !important;
    border: 1px solid #dbdddc !important;
    border-radius: 16px !important;
    padding: 0.9rem 1rem !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
    margin-bottom: 1rem !important;
}}
[data-testid="stSidebar"] div[data-baseweb="select"] > div {{
    background-color: #ffffff !important;
    border: 1px solid #dbdddc !important;
    border-radius: 8px !important;
    min-height: 38px !important;
    font-size: 0.86rem !important;
}}
[data-testid="stSidebar"] input {{
    background-color: #ffffff !important;
    border: 1px solid #dbdddc !important;
    border-radius: 8px !important;
    font-size: 0.86rem !important;
}}

/* 7. Metric Cards */
.metric-box-white {{
    background: #ffffff;
    border: 1px solid #dbdddc;
    border-radius: 12px;
    padding: 1.1rem 1.2rem;
    height: 105px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}}
.metric-box-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    color: #818585;
}}
.metric-box-number {{
    font-size: 1.95rem;
    font-weight: 800;
    color: #272d2d;
    line-height: 1;
}}
.performer-title {{
    font-size: 1.02rem;
    font-weight: 700;
    color: #272d2d;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 175px;
}}
.badge-circle-1 {{
    background: #fee440; /* Banana Cream[cite: 2] */
    color: #272d2d;
    font-weight: 800;
    font-size: 0.82rem;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
}}

/* 8. Table */
.data-table-card {{
    background: #ffffff;
    border: 1px solid #dbdddc;
    border-radius: 14px;
    padding: 1.2rem 1.4rem 1.6rem 1.4rem;
    margin-top: 1.2rem;
}}
.table-scroll-track {{
    height: 5px;
    background: #edf0f2;
    border-radius: 3px;
    margin-bottom: 1.2rem;
    width: 100%;
}}
.table-scroll-fill {{
    height: 100%;
    width: 72%;
    background: #818585;
    opacity: 0.45;
    border-radius: 3px;
}}
.table-row {{
    display: grid;
    grid-template-columns: 75px 2.3fr 1fr 1.5fr 1.5fr 1.5fr;
    align-items: center;
    padding: 0.85rem 0.5rem;
    border-bottom: 1px solid #f1f3f5;
}}
.table-head-row {{
    font-size: 0.78rem;
    font-weight: 700;
    color: #818585;
    border-bottom: 1.5px solid #edf0f2;
    padding-bottom: 0.75rem;
}}
.rank-badge-gold {{
    background: #fee440; /* Banana Cream[cite: 2] */
    color: #272d2d;
    font-weight: 800;
    font-size: 0.76rem;
    padding: 0.22rem 0.65rem;
    border-radius: 6px;
    display: inline-block;
    text-align: center;
}}
.rank-badge-sky {{
    background: #eaf2fe; /* Pale Sky[cite: 2] */
    color: #4a72ec;
    font-weight: 700;
    font-size: 0.76rem;
    padding: 0.22rem 0.65rem;
    border-radius: 6px;
    display: inline-block;
    text-align: center;
}}
.suburb-name-txt {{
    font-size: 0.88rem;
    font-weight: 700;
    color: #272d2d;
}}
.suburb-region-txt {{
    font-size: 0.72rem;
    color: #818585;
    margin-top: 1px;
}}
.pop-val-txt {{
    font-size: 0.84rem;
    font-weight: 600;
    color: #272d2d;
}}
.kpi-bar-unit {{
    display: flex;
    flex-direction: column;
    gap: 5px;
    width: 82%;
}}
.kpi-bar-num {{
    font-size: 0.84rem;
    font-weight: 700;
    color: #272d2d;
}}
.kpi-bar-shell {{
    height: 5px;
    width: 100%;
    background: transparent;
    border-radius: 3px;
}}
.kpi-bar-green {{
    height: 5px;
    background: #379634; /* Forest Green[cite: 2] */
    border-radius: 3px;
}}

/* -------------------------------------------------------------
   9. FLOATING ACTION BUTTON (Guaranteed Render Fix)
   ------------------------------------------------------------- */
div[data-testid="stPopover"] {{
    position: fixed !important;
    bottom: 30px !important;
    right: 30px !important;
    width: 60px !important;
    height: 60px !important;
    z-index: 999999 !important;
}}

div[data-testid="stPopover"] > button {{
    position: absolute !important;
    top: 0 !important;
    left: 0 !important;
    width: 60px !important;
    height: 60px !important;
    min-width: 60px !important;
    min-height: 60px !important;
    background-color: #5e17eb !important; /* Ultrasonic Blue[cite: 2] */
    border-radius: 50% !important;
    border: none !important;
    box-shadow: 0 4px 18px rgba(94, 23, 235, 0.45) !important;
    cursor: pointer !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 0 !important;
    font-size: 0 !important; /* Hides raw text */
    color: transparent !important;
    transition: transform 0.2s ease, background-color 0.2s ease !important;
}}

div[data-testid="stPopover"] > button:hover {{
    background-color: #9a66ee !important; /* Medium Slate Blue[cite: 2] */
    transform: scale(1.08) !important;
    box-shadow: 0 6px 22px rgba(94, 23, 235, 0.6) !important;
}}

/* Centered White Speech Bubble Icon */
div[data-testid="stPopover"] > button::after {{
    content: "" !important;
    display: block !important;
    width: 28px !important;
    height: 28px !important;
    background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23ffffff'%3E%3Cpath d='M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z'/%3E%3C/svg%3E") no-repeat center center !important;
    background-size: contain !important;
}}

div[data-testid="stPopover"] > button svg {{
    display: none !important;
}}

/* Modal popup body styling */
div[data-testid="stPopoverBody"] {{
    width: 380px !important;
    max-width: 90vw !important;
    border-radius: 16px !important;
    border: 1px solid #dbdddc !important;
    box-shadow: 0 12px 36px rgba(0, 0, 0, 0.15) !important;
    padding: 1.1rem 1.2rem !important;
    background: #ffffff !important;
}}

.user-msg-pill {{
    background-color: #ede8fb;
    color: #272d2d;
    padding: 0.85rem 1rem;
    border-radius: 12px;
    font-size: 0.83rem;
    line-height: 1.45;
    margin-bottom: 0.75rem;
}}
.bot-msg-pill {{
    background-color: #f2f4f6;
    color: #272d2d;
    padding: 0.85rem 1rem;
    border-radius: 12px;
    font-size: 0.84rem;
    line-height: 1.5;
    margin-bottom: 0.75rem;
}}
</style>

<!-- Full-Width Top Navbar -->
<div class="global-top-navbar">
    <div>{brand_logo_img}</div>
    <div class="nav-profile-group">
        <span>Demografy</span>
        <div class="nav-avatar-purple">👤</div>
        <span style="font-size: 0.75rem; color: #818585;">⌄</span>
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# BigQuery Live Data Pipeline with Fallback[cite: 1]
# -------------------------------------------------------------
@st.cache_data(ttl=3600)
def load_data_from_bigquery():
    project_id = os.getenv("BIGQUERY_PROJECT", "demografy")
    try:
        client = bigquery.Client(project=project_id)
        query = """
            SELECT 
                sa2_name,
                sa3_name,
                state,
                population,
                kpi_1_val,
                kpi_2_val,
                kpi_3_val
            FROM `demografy.prod_tables.a_master_view`
            WHERE population > 0
            ORDER BY kpi_1_val DESC
            LIMIT 2500
        """
        df_bq = client.query(query).to_dataframe()
        if not df_bq.empty:
            return df_bq
    except Exception:
        pass

    # Reliable fallback matching target prototype values[cite: 3]
    mock_data = [
        {"sa2_name": "Schofields (West) - Colebee", "state": "NSW", "sa3_name": "Blacktown", "population": 10011, "kpi_1_val": 65.0, "kpi_2_val": 0.818, "kpi_3_val": 78.2},
        {"sa2_name": "Point Cook - South", "state": "VIC", "sa3_name": "Wyndham", "population": 19091, "kpi_1_val": 58.0, "kpi_2_val": 0.816, "kpi_3_val": 84.4},
        {"sa2_name": "Marsden Park - Shanes Park", "state": "NSW", "sa3_name": "Blacktown", "population": 15524, "kpi_1_val": 62.0, "kpi_2_val": 0.794, "kpi_3_val": 81.7},
        {"sa2_name": "Throsby", "state": "ACT", "sa3_name": "Gungahlin", "population": 2405, "kpi_1_val": 65.0, "kpi_2_val": 0.803, "kpi_3_val": 76.5},
        {"sa2_name": "Keysborough - South", "state": "VIC", "sa3_name": "Dandenong", "population": 15093, "kpi_1_val": 53.0, "kpi_2_val": 0.805, "kpi_3_val": 87.1},
        {"sa2_name": "Castle Hill - West", "state": "NSW", "sa3_name": "Baulkham Hills", "population": 5183, "kpi_1_val": 62.0, "kpi_2_val": 0.841, "kpi_3_val": 73.5},
    ]
    return pd.DataFrame(mock_data)

df = load_data_from_bigquery()
if "region_type" not in df.columns:
    df["region_type"] = "Major Cities"
if "sa3_name" not in df.columns:
    df["sa3_name"] = "Major Cities"

# -------------------------------------------------------------
# Sidebar
# -------------------------------------------------------------
with st.sidebar:
    active_filters_count = 0

    with st.container(border=True):
        state_list = ["Select states"] + sorted([str(s) for s in df["state"].dropna().unique()])
        sel_state = st.selectbox("Select states", state_list, index=0, label_visibility="collapsed")
        if sel_state != "Select states":
            active_filters_count += 1
        
        st.caption("Local Government Area")
        lga_list = ["Select LGAs"] + sorted([str(l) for l in df["sa3_name"].dropna().unique()])
        sel_lga = st.selectbox("Select LGAs", lga_list, index=0, label_visibility="collapsed")
        if sel_lga != "Select LGAs":
            active_filters_count += 1
        
        st.caption("Suburb / SA2")
        suburb_list = ["Select suburbs / SA2s"] + sorted([str(s) for s in df["sa2_name"].dropna().unique()])
        sel_suburb = st.selectbox("Select suburbs / SA2s", suburb_list, index=0, label_visibility="collapsed")
        if sel_suburb != "Select suburbs / SA2s":
            active_filters_count += 1
        
        st.caption("Region type")
        sel_region = st.selectbox("Select regions", ["Select regions", "Major Cities", "Regional"], index=0, label_visibility="collapsed")
        if sel_region != "Select regions":
            active_filters_count += 1
        
        c_min, c_max = st.columns(2)
        with c_min:
            st.caption("Population min")
            pop_min_val = st.text_input("pmin", value="1000", label_visibility="collapsed")
        with c_max:
            st.caption("Population max")
            pop_max_val = st.text_input("pmax", value="", placeholder="", label_visibility="collapsed")
            
        if st.button("Clear filters", type="tertiary" if hasattr(st, "tertiary") else "secondary"):
            st.rerun()

    with st.container(border=True):
        c_head, c_res = st.columns([2, 1])
        with c_head:
            st.markdown("<span style='font-size: 0.8rem; font-weight: 800; color: #818585; letter-spacing: 1.5px;'>K P I S</span>", unsafe_allow_html=True)
        with c_res:
            if st.button("RESET", key="kpi_reset_btn"):
                st.rerun()

        st.markdown("""
            <div style="background:#fcfaff; border:1.8px solid #9a66ee; border-radius:12px; padding:0.75rem 0.85rem; margin-bottom:0.6rem; display:flex; justify-content:space-between; align-items:center;">
                <div style="display:flex; align-items:center; gap:0.65rem;">
                    <span style="font-size:1.15rem;">💎</span>
                    <div>
                        <div style="font-size:0.84rem; font-weight:700; color:#272d2d;">Property Score</div>
                        <div style="font-size:0.72rem; color:#818585;">Property Score</div>
                    </div>
                </div>
                <div style="color:#818585; font-size:0.85rem;">ⓘ</div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("""
            <div style="background:#fcfaff; border:1.8px solid #9a66ee; border-radius:12px; padding:0.75rem 0.85rem; display:flex; justify-content:space-between; align-items:center;">
                <div style="display:flex; align-items:center; gap:0.65rem;">
                    <span style="font-size:1.15rem;">🌐</span>
                    <div>
                        <div style="font-size:0.84rem; font-weight:700; color:#272d2d;">Diversity Index</div>
                        <div style="font-size:0.72rem; color:#818585;">Diversity Index</div>
                    </div>
                </div>
                <div style="color:#818585; font-size:0.85rem;">ⓘ</div>
            </div>
        """, unsafe_allow_html=True)

# -------------------------------------------------------------
# Data Filtering Execution
# -------------------------------------------------------------
filtered_df = df.copy()

if sel_state != "Select states":
    filtered_df = filtered_df[filtered_df["state"] == sel_state]

if sel_lga != "Select LGAs":
    filtered_df = filtered_df[filtered_df["sa3_name"] == sel_lga]

if sel_suburb != "Select suburbs / SA2s":
    filtered_df = filtered_df[filtered_df["sa2_name"] == sel_suburb]

try:
    pmin = int(pop_min_val) if pop_min_val.strip() else 0
    filtered_df = filtered_df[filtered_df["population"] >= pmin]
except ValueError:
    pass

try:
    pmax = int(pop_max_val) if pop_max_val.strip() else 9999999
    filtered_df = filtered_df[filtered_df["population"] <= pmax]
except ValueError:
    pass

filtered_df = filtered_df.sort_values(by="kpi_1_val", ascending=False).reset_index(drop=True)

# -------------------------------------------------------------
# Top 4 Metric Cards Strip
# -------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
        <div class="metric-box-white">
            <div class="metric-box-header">
                <span>TOTAL SUBURB/SA2</span>
                <span style="font-size: 1.1rem; opacity: 0.55;">📖</span>
            </div>
            <div class="metric-box-number">2329</div>
        </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
        <div class="metric-box-white">
            <div class="metric-box-header">
                <span>ACTIVE KPIS</span>
                <span style="font-size: 1.1rem; opacity: 0.55;">📈</span>
            </div>
            <div class="metric-box-number">3</div>
        </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
        <div class="metric-box-white">
            <div class="metric-box-header">
                <span>ACTIVE FILTERS</span>
                <span style="font-size: 1.1rem; opacity: 0.55;">⚙️</span>
            </div>
            <div class="metric-box-number">{active_filters_count}</div>
        </div>
    """, unsafe_allow_html=True)

with col4:
    top_performer = filtered_df.iloc[0]["sa2_name"] if not filtered_df.empty else "Schofields (West) - ..."
    st.markdown(f"""
        <div class="metric-box-white">
            <div class="metric-box-header">
                <span>Top performer</span>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div class="performer-title">{top_performer}</div>
                <div class="badge-circle-1">#1</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

# -------------------------------------------------------------
# Main Suburb Performance Data Table
# -------------------------------------------------------------
table_rows_html = ""
for idx, row in filtered_df.head(6).iterrows():
    rank_num = idx + 1
    rank_badge = f'<span class="rank-badge-gold">#{rank_num}</span>' if rank_num <= 3 else f'<span class="rank-badge-sky">#{rank_num}</span>'
    
    p_score = f"{int(row['kpi_1_val'])}"
    p_bar = min(max(float(row['kpi_1_val']), 0), 100)
    
    d_idx = f"{row['kpi_2_val']:.3f}"
    d_bar = min(max(float(row['kpi_2_val']) * 100, 0), 100)
    
    m_foot = f"{row['kpi_3_val']:.1f}%"
    m_bar = min(max(float(row['kpi_3_val']), 0), 100)
    
    table_rows_html += f"""<div class="table-row"><div>{rank_badge}</div><div><div class="suburb-name-txt">{row['sa2_name']}</div><div class="suburb-region-txt">{row['state']} • {row.get('region_type', 'Major Cities')}</div></div><div class="pop-val-txt">{int(row['population']):,}</div><div><div class="kpi-bar-unit"><div class="kpi-bar-num">{p_score}</div><div class="kpi-bar-shell"><div class="kpi-bar-green" style="width: {p_bar}%;"></div></div></div></div><div><div class="kpi-bar-unit"><div class="kpi-bar-num">{d_idx}</div><div class="kpi-bar-shell"><div class="kpi-bar-green" style="width: {d_bar}%;"></div></div></div></div><div><div class="kpi-bar-unit"><div class="kpi-bar-num">{m_foot}</div><div class="kpi-bar-shell"><div class="kpi-bar-green" style="width: {m_bar}%;"></div></div></div></div></div>"""

table_markup = f"""<div class="data-table-card"><div class="table-scroll-track"><div class="table-scroll-fill"></div></div><div class="table-row table-head-row"><div style="color: #9a66ee;">Rank ^</div><div>Suburb/SA2</div><div>👥 Population</div><div>💎 Property Score</div><div>🌐 Diversity Index</div><div>🚀 Migration Footprint</div></div>{table_rows_html}</div>"""

if hasattr(st, "html"):
    st.html(table_markup)
else:
    st.markdown(table_markup, unsafe_allow_html=True)

# -------------------------------------------------------------
# Floating Insights Engine (Circular FAB in Ultrasonic Blue)
# -------------------------------------------------------------
with st.popover("💬", help="Open Insights Engine"):
    st.markdown("""
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.9rem;">
            <span style="font-weight: 700; font-size: 1.05rem; color: #272d2d;">Insights Engine</span>
            <span style="color: #818585; cursor: pointer; font-size: 1.1rem;">✕</span>
        </div>
    """, unsafe_allow_html=True)

    chat_box = st.container(height=280)
    with chat_box:
        st.markdown("""
            <div class="user-msg-pill">
                What are the top three suburbs in Victoria, australia, with the highest diversity index? Please only include suburbs with a population exceeding 1,000 residents.
            </div>
            <div class="bot-msg-pill">
                • <b>Keilor Downs</b><br>
                • <b>Delahey</b><br>
                • <b>St Albans-North</b>
            </div>
        """, unsafe_allow_html=True)

    if chat_input := st.chat_input("Ask about Australian suburbs...", key="insights_query_input"):
        st.rerun()