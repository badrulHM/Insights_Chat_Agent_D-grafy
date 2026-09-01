# app.py
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="Demografy | Australian Property Insights",
    page_icon="📊",
    layout="wide"
)

# -------------------------------------------------------------
# Demografy Brand Styling & Open Sauce Typography
# -------------------------------------------------------------
st.markdown("""
    <style>
    @import url('https://fonts.cdnfonts.com/css/open-sauce-one');

    * {
        font-family: 'Open Sauce One', 'Open Sauce', sans-serif !important;
    }
    
    .main-header {
        font-size: 1.8rem;
        font-weight: 700;
        color: #272d2d;
        margin-bottom: 0.1rem;
    }
    
    .brand-gradient-bar {
        height: 3px;
        width: 100%;
        background: linear-gradient(90deg, #8df2ed 0%, #5e17eb 100%);
        border-radius: 2px;
        margin-bottom: 1rem;
    }
    
    .stat-card {
        background-color: #ffffff;
        border: 1px solid #dbdddc;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        text-align: left;
    }
    .stat-title {
        font-size: 0.75rem;
        color: #818585;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .stat-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #272d2d;
    }
    .stat-sub {
        font-size: 0.8rem;
        color: #5e17eb;
        font-weight: 600;
    }
    
    .stButton > button {
        background-color: #9a66ee !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
    }
    .stButton > button:hover {
        background-color: #5e17eb !important;
    }

    /* ---------------------------------------------------------
       FLOATING CIRCULAR CHAT BUTTON (Bottom-Right Floating Widget)
       --------------------------------------------------------- */
    div[data-testid="stPopover"] {
        position: fixed !important;
        bottom: 30px !important;
        right: 30px !important;
        z-index: 999999 !important;
        width: 60px !important;
        height: 60px !important;
    }

    div[data-testid="stPopover"] > button {
        background: #5e17eb !important; /* Ultrasonic Blue */
        color: #ffffff !important;
        border-radius: 50% !important;
        width: 60px !important;
        height: 60px !important;
        box-shadow: 0 4px 14px rgba(94, 23, 235, 0.45) !important;
        font-size: 1.6rem !important;
        border: none !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 0 !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease !important;
    }

    /* Hide Streamlit default chevron/arrow inside the popover button */
    div[data-testid="stPopover"] > button svg {
        display: none !important;
    }

    div[data-testid="stPopover"] > button:hover {
        transform: scale(1.08) !important;
        box-shadow: 0 6px 20px rgba(94, 23, 235, 0.6) !important;
        background: #9a66ee !important;
    }

    /* Floating Popover Chat Modal Layout */
    div[data-testid="stPopoverBody"] {
        width: 380px !important;
        max-width: 90vw !important;
        border-radius: 16px !important;
        border: 1px solid #dbdddc !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.15) !important;
        padding: 1rem 1.2rem !important;
    }
    </style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# Mock Dataset matching demografy.prod_tables.a_master_view
# -------------------------------------------------------------
@st.cache_data
def load_mock_data():
    data = [
        {"sa2_name": "Schofields (West) - Colebee", "state": "NSW", "region_type": "Major Cities", "population": 10011, "kpi_1_val": 65, "kpi_2_val": 0.818, "kpi_3_val": 78.2, "kpi_4_val": 72.1, "kpi_6_val": 84.0},
        {"sa2_name": "Point Cook - South", "state": "VIC", "region_type": "Major Cities", "population": 19091, "kpi_1_val": 58, "kpi_2_val": 0.816, "kpi_3_val": 84.4, "kpi_4_val": 68.4, "kpi_6_val": 79.5},
        {"sa2_name": "Marsden Park - Shanes Park", "state": "NSW", "region_type": "Major Cities", "population": 15524, "kpi_1_val": 62, "kpi_2_val": 0.794, "kpi_3_val": 81.7, "kpi_4_val": 65.9, "kpi_6_val": 81.2},
        {"sa2_name": "Throsby", "state": "ACT", "region_type": "Major Cities", "population": 2405, "kpi_1_val": 65, "kpi_2_val": 0.803, "kpi_3_val": 76.5, "kpi_4_val": 78.0, "kpi_6_val": 88.3},
        {"sa2_name": "Keysborough - South", "state": "VIC", "region_type": "Major Cities", "population": 15093, "kpi_1_val": 53, "kpi_2_val": 0.805, "kpi_3_val": 87.1, "kpi_4_val": 61.2, "kpi_6_val": 75.0},
        {"sa2_name": "Castle Hill - West", "state": "NSW", "region_type": "Major Cities", "population": 5183, "kpi_1_val": 62, "kpi_2_val": 0.841, "kpi_3_val": 73.5, "kpi_4_val": 80.5, "kpi_6_val": 86.4},
        {"sa2_name": "Truganina - South East", "state": "VIC", "region_type": "Major Cities", "population": 9596, "kpi_1_val": 52, "kpi_2_val": 0.776, "kpi_3_val": 89.0, "kpi_4_val": 59.8, "kpi_6_val": 71.3},
        {"sa2_name": "Glenwood", "state": "NSW", "region_type": "Major Cities", "population": 15829, "kpi_1_val": 58, "kpi_2_val": 0.807, "kpi_3_val": 82.0, "kpi_4_val": 74.3, "kpi_6_val": 83.1},
        {"sa2_name": "Kellyville Ridge - The Ponds", "state": "NSW", "region_type": "Major Cities", "population": 21058, "kpi_1_val": 61, "kpi_2_val": 0.808, "kpi_3_val": 79.4, "kpi_4_val": 77.2, "kpi_6_val": 85.0},
        {"sa2_name": "Corowa", "state": "NSW", "region_type": "Regional", "population": 5600, "kpi_1_val": 45, "kpi_2_val": 0.320, "kpi_3_val": 12.5, "kpi_4_val": 42.0, "kpi_6_val": 69.1},
        {"sa2_name": "Fitzroy", "state": "VIC", "region_type": "Inner City", "population": 10500, "kpi_1_val": 68, "kpi_2_val": 0.750, "kpi_3_val": 65.0, "kpi_4_val": 86.2, "kpi_6_val": 48.0},
        {"sa2_name": "Carlton", "state": "VIC", "region_type": "Inner City", "population": 18500, "kpi_1_val": 66, "kpi_2_val": 0.760, "kpi_3_val": 68.0, "kpi_4_val": 84.5, "kpi_6_val": 42.0}
    ]
    return pd.DataFrame(data)

df = load_mock_data()

# -------------------------------------------------------------
# Sidebar: Filters & Controls
# -------------------------------------------------------------
with st.sidebar:
    st.markdown("## **Demografy**")
    st.markdown('<div class="brand-gradient-bar"></div>', unsafe_allow_html=True)
    
    st.markdown("### **FILTERS**")
    
    state_options = ["All States"] + sorted(df["state"].unique().tolist())
    selected_state = st.selectbox("State", state_options)
    
    region_options = ["All Regions"] + sorted(df["region_type"].unique().tolist())
    selected_region = st.selectbox("Region Type", region_options)
    
    min_pop = int(df["population"].min())
    max_pop = int(df["population"].max())
    pop_range = st.slider("Population Range", min_value=0, max_value=25000, value=(1000, 25000), step=500)
    
    st.markdown("---")
    st.markdown("### **KPIS**")
    sort_kpi = st.selectbox(
        "Sort By Primary KPI",
        options=[
            ("Prosperity Score", "kpi_1_val"),
            ("Diversity Index", "kpi_2_val"),
            ("Migration Footprint", "kpi_3_val"),
            ("Learning Level", "kpi_4_val"),
            ("Resident Equity", "kpi_6_val")
        ],
        format_func=lambda x: x[0]
    )
    
    if st.button("Reset Filters"):
        st.rerun()

# -------------------------------------------------------------
# Data Filtering Pipeline
# -------------------------------------------------------------
filtered_df = df.copy()

if selected_state != "All States":
    filtered_df = filtered_df[filtered_df["state"] == selected_state]

if selected_region != "All Regions":
    filtered_df = filtered_df[filtered_df["region_type"] == selected_region]

filtered_df = filtered_df[
    (filtered_df["population"] >= pop_range[0]) & 
    (filtered_df["population"] <= pop_range[1])
]

filtered_df = filtered_df.sort_values(by=sort_kpi[1], ascending=False).reset_index(drop=True)
filtered_df["Rank"] = filtered_df.index + 1

# -------------------------------------------------------------
# Main Content: Header & KPI Summary Cards
# -------------------------------------------------------------
st.markdown('<div class="main-header">Australian Property Insights</div>', unsafe_allow_html=True)
st.caption("Aggregated demographic and suburb-level growth statistics")
st.markdown('<div class="brand-gradient-bar"></div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(f"""
        <div class="stat-card">
            <div class="stat-title">Total Suburbs (SA2)</div>
            <div class="stat-value">{len(filtered_df)}</div>
            <div class="stat-sub">of {len(df)} Loaded</div>
        </div>
    """, unsafe_allow_html=True)

with c2:
    active_filters_count = int(selected_state != "All States") + int(selected_region != "All Regions") + int(pop_range != (1000, 25000))
    st.markdown(f"""
        <div class="stat-card">
            <div class="stat-title">Active Filters</div>
            <div class="stat-value">{active_filters_count}</div>
            <div class="stat-sub">Applied</div>
        </div>
    """, unsafe_allow_html=True)

with c3:
    top_performer = filtered_df.iloc[0]["sa2_name"] if not filtered_df.empty else "N/A"
    st.markdown(f"""
        <div class="stat-card">
            <div class="stat-title">Top Performer ({sort_kpi[0]})</div>
            <div class="stat-value" style="font-size: 1.1rem; padding-top: 5px;">{top_performer}</div>
            <div class="stat-sub">Rank #1</div>
        </div>
    """, unsafe_allow_html=True)

with c4:
    avg_diversity = f"{filtered_df['kpi_2_val'].mean():.3f}" if not filtered_df.empty else "0.0"
    st.markdown(f"""
        <div class="stat-card">
            <div class="stat-title">Avg Diversity Index</div>
            <div class="stat-value">{avg_diversity}</div>
            <div class="stat-sub">Selected Scope</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# -------------------------------------------------------------
# Main Suburb Ranking Table
# -------------------------------------------------------------
st.subheader("Suburb / SA2 Performance Table")

display_df = filtered_df[[
    "Rank", "sa2_name", "state", "population", 
    "kpi_1_val", "kpi_2_val", "kpi_3_val", "kpi_4_val", "kpi_6_val"
]].copy()

display_df.columns = [
    "Rank", "Suburb / SA2", "State", "Population", 
    "Prosperity Score", "Diversity Index", "Migration Footprint (%)", "Learning Level (%)", "Resident Equity (%)"
]

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Rank": st.column_config.NumberColumn(format="#%d", width="small"),
        "Diversity Index": st.column_config.ProgressColumn(
            min_value=0.0,
            max_value=1.0,
            format="%.3f"
        ),
        "Prosperity Score": st.column_config.ProgressColumn(
            min_value=0,
            max_value=100,
            format="%d%%"
        ),
        "Migration Footprint (%)": st.column_config.ProgressColumn(
            min_value=0,
            max_value=100,
            format="%.1f%%"
        ),
        "Population": st.column_config.NumberColumn(format="%d")
    }
)

# -------------------------------------------------------------
# Floating Expandable Insights Engine (Bottom-Right Chat Icon)
# -------------------------------------------------------------
if "insights_chat_history" not in st.session_state:
    st.session_state.insights_chat_history = [
        {
            "role": "assistant",
            "content": "👋 Hi! I'm the **Demografy Insights Engine**. Ask me demographic questions about Australian suburbs."
        }
    ]

# Floating popover button styled purely as a circular chat bubble icon
with st.popover("💬", help="Open Insights Engine"):
    st.markdown("### **Insights Engine** ✨")
    st.caption("Natural Language Suburb & KPI Query Agent")
    st.markdown('<div class="brand-gradient-bar"></div>', unsafe_allow_html=True)

    # Chat history box
    chat_box = st.container(height=300)
    for msg in st.session_state.insights_chat_history:
        with chat_box.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("e.g. Top 3 suburbs in VIC by diversity index", key="insights_floating_chat"):
        st.session_state.insights_chat_history.append({"role": "user", "content": prompt})

        # Mock query response
        response_text = (
            f"**Query Result for:** *\"{prompt}\"*\n\n"
            f"• **Keilor Downs (VIC)** — Diversity Index: `0.841`\n"
            f"• **Delahey (VIC)** — Diversity Index: `0.818`\n"
            f"• **St Albans - North (VIC)** — Diversity Index: `0.805`\n\n"
            f"*Data queried from `demografy.prod_tables.a_master_view`.*"
        )
        st.session_state.insights_chat_history.append({"role": "assistant", "content": response_text})
        st.rerun()