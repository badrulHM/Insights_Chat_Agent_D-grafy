# ============================================================
# Demografy Insights Chat | Streamlit Frontend
# ============================================================

import html
import re

import streamlit as st

from agent.service import ask
from auth.rbac import authenticate, check_quota
from ui_charts import build_chart


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Demografy Insights Chat",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# SESSION STATE
# ============================================================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "user" not in st.session_state:
    st.session_state.user = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "questions_used" not in st.session_state:
    st.session_state.questions_used = 0

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# Question waiting for backend processing.
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# Used to let the conversation screen render once before
# starting the slower backend call.
if "processing_armed" not in st.session_state:
    st.session_state.processing_armed = False


# ============================================================
# GLOBAL CSS
# ============================================================

st.html(
    """
    <style>

    /* =======================================================
       PAGE BACKGROUND
    ======================================================= */

    html,
    body {
        background: #FFFFFF;
    }

    .stApp {
        background:
            radial-gradient(
                circle at 25% 86%,
                rgba(238, 144, 253, 0.44) 0%,
                rgba(238, 144, 253, 0.18) 22%,
                transparent 43%
            ),
            radial-gradient(
                circle at 2% 88%,
                rgba(255, 224, 248, 0.78) 0%,
                rgba(255, 238, 252, 0.38) 29%,
                transparent 49%
            ),
            radial-gradient(
                circle at 96% 92%,
                rgba(92, 73, 250, 0.50) 0%,
                rgba(128, 111, 255, 0.22) 27%,
                transparent 49%
            ),
            linear-gradient(
                135deg,
                #FFFFFF 0%,
                #FCFAFF 48%,
                #F3F5FF 100%
            );

        background-attachment: fixed;
    }

    [data-testid="stAppViewContainer"],
    [data-testid="stMain"] {
        background: transparent;
    }


    /* =======================================================
       PAGE LAYOUT
    ======================================================= */

    .block-container {
        max-width: 1450px;
        padding-top: 4.5rem !important;
        padding-bottom: 5rem !important;
    }

    [data-testid="stAppViewBlockContainer"] {
        padding-top: 4.5rem !important;
    }

    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }


    /* =======================================================
       STREAMLIT TOP HEADER
    ======================================================= */

    header[data-testid="stHeader"],
    [data-testid="stHeader"],
    .stAppHeader {
        background:
            rgba(
                255,
                255,
                255,
                0.88
            ) !important;

        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);

        border-bottom:
            1px solid
            rgba(
                139,
                92,
                246,
                0.08
            ) !important;
    }

    [data-testid="stHeader"] > div,
    [data-testid="stToolbar"],
    [data-testid="stStatusWidget"],
    [data-testid="stHeaderActionElements"] {
        background: transparent !important;
    }


    /* =======================================================
       SIDEBAR CONTROLS
       KEEP COLLAPSE AND EXPAND BUTTONS VISIBLE
    ======================================================= */

    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
    }

    [data-testid="stSidebarCollapseButton"] button,
    [data-testid="stSidebarCollapsedControl"] button {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;

        width: 32px !important;
        height: 32px !important;

        border:
            1px solid
            rgba(139, 92, 246, 0.38) !important;

        border-radius: 8px !important;

        background:
            rgba(
                255,
                255,
                255,
                0.94
            ) !important;

        color: #6D28D9 !important;

        transition: all 0.15s ease;
    }

    [data-testid="stSidebarCollapseButton"] button:hover,
    [data-testid="stSidebarCollapsedControl"] button:hover {
        background: #F4EEFF !important;
        border-color: #7C3AED !important;
    }

    [data-testid="stSidebarCollapseButton"] svg,
    [data-testid="stSidebarCollapsedControl"] svg {
        visibility: visible !important;
        opacity: 1 !important;

        color: #6D28D9 !important;
        fill: currentColor !important;
    }


    /* =======================================================
       TYPOGRAPHY
    ======================================================= */

    h1,
    h2,
    h3 {
        color: #17152F;
    }


    /* =======================================================
       DEMOGRAFY WORDMARK
    ======================================================= */

    .demografy-wordmark {
        display: flex;
        align-items: center;

        line-height: 1;

        margin-bottom: 7px;

        letter-spacing: -1.2px;
    }

    .demografy-letter-d {
        color: #8B5CF6;

        font-size: 31px;
        font-weight: 800;
    }

    .demografy-word-rest {
        color: #17152F;

        font-size: 31px;
        font-weight: 760;
    }

    .demografy-chat-label {
        color: #7C3AED;

        font-size: 13px;
        font-weight: 650;

        margin-top: 8px;
        margin-bottom: 12px;
    }

    .brand-d {
        color: #8B5CF6;
        font-weight: 800;
    }


    /* =======================================================
       SIDEBAR
    ======================================================= */

    [data-testid="stSidebar"] {
        background:
            rgba(
                248,
                248,
                252,
                0.94
            ) !important;

        border-right:
            1px solid
            rgba(
                224,
                220,
                232,
                0.90
            );

        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
    }

    [data-testid="stSidebar"] .block-container {
        padding-top: 3rem !important;
    }

    .sidebar-description {
        color: #777181;

        font-size: 12px;
        line-height: 1.55;

        margin-bottom: 8px;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.55rem;
        font-weight: 700;
    }


    /* =======================================================
       TIER
    ======================================================= */

    .tier-badge-wrapper {
        display: flex;
        justify-content: flex-end;
        align-items: center;

        gap: 8px;

        padding-top: 4px;
    }

    .tier-label {
        color: #7E7988;

        font-size: 11px;
        font-weight: 600;
    }

    .tier-badge {
        display: inline-flex;
        align-items: center;

        gap: 7px;

        padding: 6px 11px;

        border:
            1px solid
            #DED8E8;

        border-radius: 999px;

        background:
            rgba(
                255,
                255,
                255,
                0.78
            );

        color: #4E4955;

        font-size: 11px;
        font-weight: 650;

        backdrop-filter: blur(6px);
    }

    .tier-dot {
        width: 9px;
        height: 9px;

        display: inline-block;

        border-radius: 50%;
    }

    .tier-free {
        background: #D2CBDE;
    }

    .tier-basic {
        background: #A67BE8;
    }

    .tier-pro {
        background: #7C3AED;
    }


    /* =======================================================
       LOGIN
    ======================================================= */

    .login-brand {
        margin-bottom: 28px;
    }

    .login-hero {
        min-height: 470px;

        padding: 52px;

        border-radius: 24px;

        box-sizing: border-box;

        background:
            radial-gradient(
                circle at 20% 20%,
                rgba(255,255,255,0.12),
                transparent 40%
            ),
            linear-gradient(
                135deg,
                #5920BA 0%,
                #7C3AED 50%,
                #A46AF2 100%
            );

        color: white;

        display: flex;
        flex-direction: column;
        justify-content: center;

        box-shadow:
            0 22px 55px
            rgba(
                76,
                29,
                149,
                0.20
            );
    }

    .login-kicker {
        display: inline-flex;

        width: fit-content;

        padding: 7px 13px;

        margin-bottom: 22px;

        border-radius: 999px;

        background:
            rgba(
                255,
                255,
                255,
                0.14
            );

        color:
            rgba(
                255,
                255,
                255,
                0.94
            );

        font-size: 11px;
        font-weight: 700;

        letter-spacing: 0.08em;
    }

    .login-hero-title {
        max-width: 580px;

        margin-bottom: 18px;

        color: white;

        font-size: 42px;
        font-weight: 720;

        line-height: 1.14;
    }

    .login-hero-description {
        max-width: 560px;

        margin-bottom: 22px;

        color:
            rgba(
                255,
                255,
                255,
                0.88
            );

        font-size: 16px;

        line-height: 1.65;
    }

    .login-features {
        display: flex;
        flex-direction: column;

        gap: 14px;

        margin-top: 6px;
    }

    .login-feature {
        display: flex;
        align-items: center;

        gap: 12px;

        color:
            rgba(
                255,
                255,
                255,
                0.95
            );

        font-size: 14px;
    }

    .login-feature-icon {
        width: 28px;
        height: 28px;

        display: flex;
        align-items: center;
        justify-content: center;

        flex-shrink: 0;

        border-radius: 8px;

        background:
            rgba(
                255,
                255,
                255,
                0.13
            );
    }

    .login-form-heading {
        color: #262631;

        font-size: 28px;
        font-weight: 720;

        margin-bottom: 6px;
    }

    .login-form-subtitle {
        color: #7E7988;

        font-size: 14px;

        margin-bottom: 18px;
    }

    .login-note {
        color: #92909A;

        font-size: 12px;
        line-height: 1.5;

        margin-top: 14px;
    }


    /* =======================================================
       LOGIN BUTTON
    ======================================================= */

    div[data-testid="stFormSubmitButton"] button {
        width: 100%;

        min-height: 48px;

        border: none !important;

        border-radius: 10px !important;

        background:
            linear-gradient(
                90deg,
                #7C3AED,
                #8B5CF6
            ) !important;

        color: white !important;

        font-weight: 600;
        font-size: 14px;
    }

    div[data-testid="stFormSubmitButton"] button:hover {
        background:
            linear-gradient(
                90deg,
                #6D28D9,
                #7C3AED
            ) !important;

        color: white !important;
    }


    /* =======================================================
       PAGE HEADER
    ======================================================= */

    .chat-page-title {
        color: #17152F;

        font-size: 34px;
        font-weight: 720;

        line-height: 1.2;

        margin-bottom: 6px;
    }

    .chat-page-subtitle {
        color: #7D7787;

        font-size: 13px;

        line-height: 1.5;
    }


    /* =======================================================
       WELCOME
    ======================================================= */

    .welcome-area {
        max-width: 1050px;

        margin:
            2.2rem
            auto
            1.5rem
            auto;

        text-align: center;
    }

    .welcome-title {
        color: #17152F;

        font-size: 31px;
        font-weight: 720;

        line-height: 1.25;

        margin-bottom: 8px;
    }

    .welcome-subtitle {
        color: #817A8A;

        font-size: 14px;

        line-height: 1.55;
    }


    /* =======================================================
       CARDS
    ======================================================= */

    [data-testid="stVerticalBlockBorderWrapper"] {
        background:
            rgba(
                255,
                255,
                255,
                0.80
            ) !important;

        border:
            1px solid
            rgba(
                207,
                200,
                220,
                0.86
            ) !important;

        border-radius: 16px;

        box-shadow:
            0 8px 30px
            rgba(
                66,
                48,
                95,
                0.05
            );

        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
    }


    /* =======================================================
       CAPABILITIES
    ======================================================= */

    .capability-heading {
        color: #17152F;

        font-size: 19px;
        font-weight: 700;

        margin-bottom: 5px;
    }

    .capability-description {
        color: #777181;

        font-size: 12px;

        margin-bottom: 18px;
    }

    .capability-title {
        color: #2C2838;

        font-size: 14px;
        font-weight: 650;

        margin-bottom: 4px;
    }

    .capability-copy {
        color: #8E8797;

        font-size: 11px;

        line-height: 1.5;
    }


    /* =======================================================
       INITIAL SUGGESTIONS
    ======================================================= */

    .initial-suggestion-title {
        color: #2E2A38;

        font-size: 18px;
        font-weight: 680;

        margin-top: 18px;

        margin-bottom: 4px;
    }

    .initial-suggestion-copy {
        color: #847E8C;

        font-size: 12px;

        margin-bottom: 12px;
    }


    /* =======================================================
       QUESTION BUTTONS
    ======================================================= */

    .stButton button {
        border-radius: 999px !important;

        min-height: 42px;

        height: auto;

        padding:
            0.65rem
            1rem;

        border:
            1.6px
            solid
            #B76BF3 !important;

        background:
            rgba(
                255,
                255,
                255,
                0.72
            ) !important;

        color: #51495B;

        font-size: 13px;
        font-weight: 500;

        line-height: 1.35;

        white-space: normal;

        box-shadow:
            0
            3px
            0
            rgba(
                124,
                58,
                237,
                0.06
            ),
            0
            5px
            14px
            rgba(
                80,
                55,
                120,
                0.06
            );

        transition:
            all
            0.15s
            ease;

        backdrop-filter: blur(6px);
    }

    .stButton button:hover {
        background:
            rgba(
                248,
                243,
                255,
                0.96
            ) !important;

        border-color:
            #7C3AED !important;

        color:
            #6D28D9 !important;

        box-shadow:
            0
            0
            0
            3px
            rgba(
                124,
                58,
                237,
                0.08
            );

        transform:
            translateY(-1px);
    }

    .stButton button:disabled {
        opacity: 0.45;
    }


    /* =======================================================
       LOGOUT BUTTON
    ======================================================= */

    .st-key-logout_button button {
        width: 100% !important;

        min-height: 46px !important;

        border: none !important;

        border-radius: 11px !important;

        background:
            linear-gradient(
                90deg,
                #7C3AED 0%,
                #8B5CF6 100%
            ) !important;

        color:
            #FFFFFF !important;

        font-size:
            13px !important;

        font-weight:
            650 !important;

        box-shadow:
            0
            5px
            12px
            rgba(
                124,
                58,
                237,
                0.25
            ) !important;

        transition:
            all
            0.15s
            ease !important;
    }

    .st-key-logout_button button:hover {
        background:
            linear-gradient(
                90deg,
                #6D28D9 0%,
                #7C3AED 100%
            ) !important;

        color:
            #FFFFFF !important;

        transform:
            translateY(-1px);

        box-shadow:
            0
            7px
            16px
            rgba(
                124,
                58,
                237,
                0.32
            ) !important;
    }

    .st-key-logout_button button p {
        color:
            #FFFFFF !important;

        font-weight:
            650 !important;
    }


    /* =======================================================
       CHAT INPUT
    ======================================================= */

    [data-testid="stChatInput"] {
        border:
            1.6px
            solid
            #B76BF3 !important;

        border-radius:
            17px !important;

        background:
            rgba(
                247,
                247,
                251,
                0.96
            ) !important;

        min-height:
            72px;

        box-shadow:
            0
            4px
            0
            rgba(
                124,
                58,
                237,
                0.10
            ),
            0
            8px
            22px
            rgba(
                80,
                55,
                120,
                0.08
            );

        backdrop-filter:
            blur(8px);

        transition:
            border-color
            0.15s
            ease,
            box-shadow
            0.15s
            ease,
            background
            0.15s
            ease;
    }

    [data-testid="stChatInput"]:focus-within {
        border:
            1.8px
            solid
            #7C3AED !important;

        background:
            rgba(
                255,
                255,
                255,
                0.98
            ) !important;

        box-shadow:
            0
            0
            0
            3px
            rgba(
                124,
                58,
                237,
                0.12
            ),
            0
            6px
            20px
            rgba(
                85,
                55,
                135,
                0.10
            );
    }

    [data-testid="stChatInput"] textarea {
        color:
            #282530 !important;

        background:
            transparent !important;

        font-size:
            15px !important;

        line-height:
            1.5 !important;
    }

    [data-testid="stChatInput"] textarea::placeholder {
        color:
            #777080 !important;

        opacity:
            1 !important;
    }

    [data-testid="stChatInput"] button {
        width:
            36px !important;

        height:
            36px !important;

        border-radius:
            10px !important;

        background:
            #ECEAF3 !important;

        color:
            #696274 !important;

        transition:
            all
            0.15s
            ease;
    }

    [data-testid="stChatInput"] button:hover {
        background:
            #7C3AED !important;

        color:
            #FFFFFF !important;
    }


    /* =======================================================
       KEEP CONVERSATION INPUT VISIBLE
    ======================================================= */

    .st-key-conversation_chat_input,
    .st-key-processing_chat_input,
    .st-key-disabled_chat_input {
        position: sticky;

        bottom: 0.75rem;

        z-index: 999;
    }


    /* =======================================================
       RELATED QUESTIONS
    ======================================================= */

    .related-heading {
        color: #2D2938;

        font-size: 18px;
        font-weight: 680;

        margin-bottom: 5px;
    }

    .related-description {
        color: #8C8794;

        font-size: 12px;

        line-height: 1.45;

        margin-bottom: 14px;
    }


    /* =======================================================
       CHAT MESSAGES
    ======================================================= */

    [data-testid="stChatMessage"] {
        margin-bottom: 8px;

        border-radius: 13px;

        background:
            rgba(
                255,
                255,
                255,
                0.66
            );

        backdrop-filter: blur(6px);
    }

    [data-testid="stChatMessageContent"] {
        font-size: 14px;

        line-height: 1.6;
    }


    /* =======================================================
       STATUS MESSAGES ABOVE CHAT INPUT
    ======================================================= */

    .chat-status {
        margin-top: 10px;
        margin-bottom: 8px;

        padding:
            10px
            14px;

        border-radius: 10px;

        font-size: 13px;
        line-height: 1.4;
    }

    .chat-status-processing {
        background:
            rgba(
                139,
                92,
                246,
                0.08
            );

        border:
            1px solid
            rgba(
                139,
                92,
                246,
                0.22
            );

        color:
            #5F45A5;
    }

    .chat-status-limit {
        background:
            rgba(
                245,
                158,
                11,
                0.08
            );

        border:
            1px solid
            rgba(
                245,
                158,
                11,
                0.25
            );

        color:
            #8C6411;
    }


    /* =======================================================
       DATAFRAME
    ======================================================= */

    [data-testid="stDataFrame"] {
        border:
            1px
            solid
            #E8E4EF;

        border-radius:
            12px;

        overflow:
            hidden;
    }


    /* =======================================================
       RESPONSIVE
    ======================================================= */

    @media (max-width: 900px) {

        .login-hero {
            min-height: auto;

            padding:
                35px
                28px;
        }

        .login-hero-title {
            font-size: 32px;
        }

        .welcome-title {
            font-size: 26px;
        }

        .demografy-letter-d,
        .demografy-word-rest {
            font-size: 27px;
        }

    }

    </style>
    """
)


# ============================================================
# DARK MODE CSS
# ============================================================

if st.session_state.dark_mode:

    st.html(
        """
        <style>

        html,
        body {
            background:
                #101218 !important;

            color:
                #ECECF1 !important;
        }

        [data-testid="stAppViewContainer"] {
            background:
                #101218 !important;
        }

        [data-testid="stMain"],
        [data-testid="stMainBlockContainer"] {
            background:
                transparent !important;
        }


        /* ===================================================
           DARK MAIN BACKGROUND
        =================================================== */

        .stApp {
            background:
                radial-gradient(
                    circle at 25% 85%,
                    rgba(136, 67, 170, 0.22) 0%,
                    transparent 38%
                ),
                radial-gradient(
                    circle at 96% 90%,
                    rgba(80, 63, 210, 0.30) 0%,
                    transparent 42%
                ),
                linear-gradient(
                    135deg,
                    #101218 0%,
                    #12141C 55%,
                    #17172A 100%
                ) !important;

            color:
                #ECECF1 !important;
        }


        /* ===================================================
           DARK TOP HEADER
        =================================================== */

        header[data-testid="stHeader"],
        [data-testid="stHeader"],
        .stAppHeader {
            background:
                rgba(
                    16,
                    18,
                    24,
                    0.98
                ) !important;

            border-bottom:
                1px solid
                rgba(
                    139,
                    92,
                    246,
                    0.16
                ) !important;

            color:
                #ECECF1 !important;

            backdrop-filter:
                blur(12px);

            -webkit-backdrop-filter:
                blur(12px);
        }

        [data-testid="stHeader"] > div,
        [data-testid="stToolbar"],
        [data-testid="stStatusWidget"],
        [data-testid="stHeaderActionElements"] {
            background:
                transparent !important;

            color:
                #ECECF1 !important;
        }

        [data-testid="stHeader"] button,
        [data-testid="stToolbar"] button {
            color:
                #C4B5FD !important;

            background:
                transparent !important;
        }

        [data-testid="stHeader"] button:hover,
        [data-testid="stToolbar"] button:hover {
            background:
                rgba(
                    139,
                    92,
                    246,
                    0.12
                ) !important;
        }

        [data-testid="stHeader"] svg,
        [data-testid="stToolbar"] svg {
            color:
                #C4B5FD !important;

            fill:
                currentColor !important;
        }

        [data-testid="stDecoration"] {
            background:
                linear-gradient(
                    90deg,
                    #7C3AED,
                    #8B5CF6
                ) !important;
        }


        /* ===================================================
           DARK SIDEBAR
        =================================================== */

        [data-testid="stSidebar"] {
            background:
                rgba(
                    23,
                    26,
                    34,
                    0.96
                ) !important;

            border-right:
                1px solid
                #2A2E39 !important;
        }


        /* ===================================================
           DARK TEXT
        =================================================== */

        h1,
        h2,
        h3,
        p,
        label {
            color:
                #ECECF1;
        }

        .demografy-letter-d {
            color:
                #A78BFA;
        }

        .demografy-word-rest {
            color:
                #F5F5F8;
        }

        .demografy-chat-label {
            color:
                #B794F6;
        }

        .brand-d {
            color:
                #A78BFA;
        }

        .chat-page-title,
        .welcome-title,
        .capability-heading,
        .capability-title,
        .initial-suggestion-title,
        .related-heading {
            color:
                #F5F5F8;
        }

        .sidebar-description,
        .chat-page-subtitle,
        .welcome-subtitle,
        .capability-description,
        .capability-copy,
        .initial-suggestion-copy,
        .related-description,
        .tier-label {
            color:
                #A7AAB4;
        }


        /* ===================================================
           DARK TIER
        =================================================== */

        .tier-badge {
            background:
                rgba(
                    32,
                    35,
                    44,
                    0.88
                );

            border-color:
                #363A47;

            color:
                #E7E7EB;
        }


        /* ===================================================
           DARK CARDS
        =================================================== */

        [data-testid="stVerticalBlockBorderWrapper"] {
            background:
                rgba(
                    23,
                    26,
                    34,
                    0.84
                ) !important;

            border-color:
                #303440 !important;
        }


        /* ===================================================
           DARK QUESTION BUTTONS
        =================================================== */

        .stButton button {
            background:
                rgba(
                    34,
                    38,
                    49,
                    0.88
                ) !important;

            border-color:
                #8B5CF6 !important;

            color:
                #E5E6EA !important;
        }

        .stButton button:hover {
            background:
                #2E253E !important;

            border-color:
                #A78BFA !important;

            color:
                #D7C4FF !important;
        }


        /* ===================================================
           DARK LOGOUT
        =================================================== */

        .st-key-logout_button button {
            background:
                linear-gradient(
                    90deg,
                    #7C3AED 0%,
                    #8B5CF6 100%
                ) !important;

            border:
                none !important;

            color:
                #FFFFFF !important;
        }

        .st-key-logout_button button:hover {
            background:
                linear-gradient(
                    90deg,
                    #8B5CF6 0%,
                    #A78BFA 100%
                ) !important;

            color:
                #FFFFFF !important;
        }

        .st-key-logout_button button p {
            color:
                #FFFFFF !important;
        }


        /* ===================================================
           DARK CHAT INPUT
        =================================================== */

        [data-testid="stChatInput"] {
            background:
                rgba(
                    25,
                    28,
                    37,
                    0.96
                ) !important;

            border:
                1.6px
                solid
                #8B5CF6 !important;

            box-shadow:
                0
                4px
                0
                rgba(
                    139,
                    92,
                    246,
                    0.15
                ),
                0
                8px
                22px
                rgba(
                    0,
                    0,
                    0,
                    0.20
                );
        }

        [data-testid="stChatInput"]:focus-within {
            border:
                1.8px
                solid
                #A78BFA !important;

            box-shadow:
                0
                0
                0
                3px
                rgba(
                    167,
                    139,
                    250,
                    0.16
                );
        }

        [data-testid="stChatInput"] textarea {
            color:
                #F5F5F7 !important;

            background:
                transparent !important;
        }

        [data-testid="stChatInput"] textarea::placeholder {
            color:
                #A7A3B0 !important;
        }

        [data-testid="stChatInput"] button {
            background:
                #292D38 !important;

            color:
                #B9B5C4 !important;
        }

        [data-testid="stChatInput"] button:hover {
            background:
                #8B5CF6 !important;

            color:
                white !important;
        }


        /* ===================================================
           DARK CHAT MESSAGES
        =================================================== */

        [data-testid="stChatMessage"] {
            background:
                rgba(
                    23,
                    26,
                    34,
                    0.78
                ) !important;
        }


        /* ===================================================
           DARK FORM INPUT
        =================================================== */

        [data-testid="stTextInput"] input {
            background:
                #20232C !important;

            color:
                #F3F3F5 !important;

            border-color:
                #343845 !important;
        }


        /* ===================================================
           DARK STATUS BOXES
        =================================================== */

        .chat-status-processing {
            background:
                rgba(
                    139,
                    92,
                    246,
                    0.14
                );

            border-color:
                rgba(
                    167,
                    139,
                    250,
                    0.30
                );

            color:
                #D6CBFF;
        }

        .chat-status-limit {
            background:
                rgba(
                    245,
                    158,
                    11,
                    0.12
                );

            border-color:
                rgba(
                    245,
                    158,
                    11,
                    0.30
                );

            color:
                #F4CA76;
        }


        /* ===================================================
           DARK SIDEBAR CONTROLS
        =================================================== */

        [data-testid="stSidebarCollapseButton"],
        [data-testid="stSidebarCollapsedControl"] {
            display:
                flex !important;

            visibility:
                visible !important;

            opacity:
                1 !important;
        }

        [data-testid="stSidebarCollapseButton"] button,
        [data-testid="stSidebarCollapsedControl"] button {
            visibility:
                visible !important;

            opacity:
                1 !important;

            background:
                rgba(
                    31,
                    34,
                    44,
                    0.96
                ) !important;

            border-color:
                #8B5CF6 !important;

            color:
                #C4B5FD !important;
        }

        [data-testid="stSidebarCollapseButton"] svg,
        [data-testid="stSidebarCollapsedControl"] svg {
            color:
                #C4B5FD !important;

            fill:
                currentColor !important;

            opacity:
                1 !important;
        }

        hr {
            border-color:
                #2C303A;
        }

        </style>
        """
    )


# ============================================================
# HELPERS
# ============================================================

def reset_session():
    """Reset the authenticated session."""

    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.messages = []
    st.session_state.questions_used = 0
    st.session_state.pending_question = None
    st.session_state.processing_armed = False


def get_display_name(user):
    """Determine the best available friendly first name."""

    for attribute in [
        "first_name",
        "display_name",
        "name",
    ]:

        value = getattr(
            user,
            attribute,
            None,
        )

        if value:

            return (
                str(value)
                .strip()
                .split()[0]
                .title()
            )

    email = getattr(
        user,
        "email",
        None,
    )

    if email and "@" in email:

        local_part = (
            email
            .split("@")[0]
        )

        first_part = re.split(
            r"[._0-9-]+",
            local_part,
        )[0]

        if first_part:

            return (
                first_part
                .strip()
                .title()
            )

    return "there"


def demografy_brand_html():
    """Text-based Demografy wordmark."""

    return """
        <div class="demografy-wordmark">

            <span class="demografy-letter-d">
                D
            </span>

            <span class="demografy-word-rest">
                emografy
            </span>

        </div>

        <div class="demografy-chat-label">
            Insights Chat
        </div>
    """


def tier_badge_html(tier):
    """Build customer tier indicator."""

    tier = (
        tier
        or "free"
    ).lower()

    if tier == "pro":

        css_class = "tier-pro"
        name = "PRO"

    elif tier == "basic":

        css_class = "tier-basic"
        name = "BASIC"

    else:

        css_class = "tier-free"
        name = "FREE"

    return (
        f"""
        <div class="tier-badge-wrapper">

            <span class="tier-label">
                Tier
            </span>

            <div class="tier-badge">

                <span class="tier-dot {css_class}">
                </span>

                {name}

            </div>

        </div>
        """
    )


# ============================================================
# DEFAULT QUESTIONS
# ============================================================

DEFAULT_SUGGESTED_QUESTIONS = [

    "What is the prosperity score for Glenwood?",

    "What are the top 5 most diverse suburbs in Victoria?",

    "Compare the diversity index of Glenwood and Karabar.",

    "Which state has the highest average learning level?",

    "What are the most affordable rental suburbs in Queensland?",
]


# ============================================================
# QUESTION HISTORY
# ============================================================

def get_user_questions():
    """Return questions already submitted this session."""

    return [

        message.get(
            "content",
            "",
        )

        for message
        in st.session_state.messages

        if (
            message.get("role")
            == "user"
        )
    ]


def get_last_user_question():
    """Return latest user question."""

    questions = (
        get_user_questions()
    )

    if questions:

        return questions[-1]

    return ""


# ============================================================
# LOCATION EXTRACTION
# ============================================================

def extract_location(question):
    """Lightweight location extraction for related prompts."""

    if not question:

        return None

    patterns = [

        r"\bfor\s+([A-Z][A-Za-z\s'-]+?)(?:\?|$)",

        r"\bin\s+([A-Z][A-Za-z\s'-]+?)(?:\?|$)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            question,
        )

        if match:

            location = (
                match
                .group(1)
                .strip()
            )

            if (
                len(
                    location.split()
                )
                <= 4
            ):

                return location

    return None


def extract_comparison_locations(question):
    """Extract locations from simple comparison question."""

    if not question:

        return []

    match = re.search(
        (
            r"\bof\s+"
            r"([A-Z][A-Za-z'-]+)"
            r"\s+and\s+"
            r"([A-Z][A-Za-z'-]+)"
        ),
        question,
    )

    if not match:

        return []

    return [

        match.group(1).strip(),

        match.group(2).strip(),
    ]


# ============================================================
# DYNAMIC RELATED QUESTIONS
# ============================================================

def get_related_questions(question):
    """Generate contextual follow-up questions."""

    if not question:

        return (
            DEFAULT_SUGGESTED_QUESTIONS.copy()
        )

    question_lower = (
        question.lower()
    )

    location = (
        extract_location(
            question
        )
    )

    comparison_locations = (
        extract_comparison_locations(
            question
        )
    )

    suggestions = []


    # --------------------------------------------------------
    # PROSPERITY
    # --------------------------------------------------------

    if "prosperity" in question_lower:

        if location:

            suggestions.extend(
                [

                    f"What is the diversity index for {location}?",

                    f"What is the rental access score for {location}?",

                    f"What is the resident equity score for {location}?",

                    f"What is the young family score for {location}?",

                    "Which suburbs have the highest prosperity scores?",
                ]
            )

        else:

            suggestions.extend(
                [

                    "Which suburbs have the highest prosperity scores?",

                    "Which state has the highest average prosperity score?",

                    (
                        "Which suburbs have both high prosperity "
                        "and high diversity scores?"
                    ),

                    "Which suburbs have the lowest prosperity scores?",

                    "Compare prosperity scores by state.",
                ]
            )


    # --------------------------------------------------------
    # DIVERSITY
    # --------------------------------------------------------

    elif (
        "diversity" in question_lower
        or
        "diverse" in question_lower
    ):

        if comparison_locations:

            first_location = (
                comparison_locations[0]
            )

            second_location = (
                comparison_locations[1]
            )

            suggestions.extend(
                [

                    (
                        f"Compare the prosperity scores of "
                        f"{first_location} and {second_location}."
                    ),

                    (
                        f"Compare the rental access scores of "
                        f"{first_location} and {second_location}."
                    ),

                    (
                        f"Compare the young family scores of "
                        f"{first_location} and {second_location}."
                    ),

                    (
                        f"What is the prosperity score "
                        f"for {first_location}?"
                    ),

                    (
                        f"What is the prosperity score "
                        f"for {second_location}?"
                    ),
                ]
            )

        elif location:

            suggestions.extend(
                [

                    f"What is the prosperity score for {location}?",

                    f"What is the rental access score for {location}?",

                    f"What is the resident equity score for {location}?",

                    f"What is the young family score for {location}?",

                    "Which suburbs have the highest diversity index?",
                ]
            )

        else:

            suggestions.extend(
                [

                    "Which suburbs have the highest diversity index?",

                    (
                        "Which states have the highest "
                        "average diversity index?"
                    ),

                    (
                        "Which suburbs have both high diversity "
                        "and high prosperity scores?"
                    ),

                    "Which suburbs have the lowest diversity index?",

                    "Compare average diversity by state.",
                ]
            )


    # --------------------------------------------------------
    # RENTAL / HOUSING
    # --------------------------------------------------------

    elif (
        "rental" in question_lower
        or
        "rent" in question_lower
        or
        "housing" in question_lower
        or
        "home ownership" in question_lower
    ):

        if location:

            suggestions.extend(
                [

                    f"What is the prosperity score for {location}?",

                    f"What is the diversity index for {location}?",

                    f"What is the resident equity score for {location}?",

                    f"What is the young family score for {location}?",

                    "Which suburbs have the highest rental access scores?",
                ]
            )

        else:

            suggestions.extend(
                [

                    "Which suburbs have the highest rental access scores?",

                    "Which suburbs have the lowest rental access scores?",

                    "Compare home ownership and rental access by state.",

                    (
                        "Which state has the highest "
                        "average rental access score?"
                    ),

                    (
                        "Which suburbs have high prosperity "
                        "and high rental access scores?"
                    ),
                ]
            )


    # --------------------------------------------------------
    # LEARNING / EDUCATION
    # --------------------------------------------------------

    elif (
        "learning" in question_lower
        or
        "education" in question_lower
    ):

        suggestions.extend(
            [

                "Which suburbs have the highest learning level?",

                (
                    "Which state has the highest "
                    "average prosperity score?"
                ),

                (
                    "Which state has the highest "
                    "average diversity index?"
                ),

                "Compare average learning levels between states.",

                (
                    "Which suburbs have both high learning "
                    "and prosperity scores?"
                ),
            ]
        )


    # --------------------------------------------------------
    # FAMILY
    # --------------------------------------------------------

    elif "family" in question_lower:

        if location:

            suggestions.extend(
                [

                    f"What is the prosperity score for {location}?",

                    f"What is the diversity index for {location}?",

                    f"What is the rental access score for {location}?",

                    f"What is the resident equity score for {location}?",

                    "Which suburbs have the highest young family scores?",
                ]
            )

        else:

            suggestions.extend(
                [

                    "Which suburbs have the highest young family scores?",

                    (
                        "Which state has the highest "
                        "average young family score?"
                    ),

                    (
                        "Which suburbs have high young family "
                        "and prosperity scores?"
                    ),

                    (
                        "Which suburbs have high young family "
                        "and rental access scores?"
                    ),

                    "Compare average young family scores by state.",
                ]
            )


    # --------------------------------------------------------
    # GENERIC LOCATION
    # --------------------------------------------------------

    elif location:

        suggestions.extend(
            [

                f"What is the prosperity score for {location}?",

                f"What is the diversity index for {location}?",

                f"What is the rental access score for {location}?",

                f"What is the resident equity score for {location}?",

                f"What is the young family score for {location}?",
            ]
        )


    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    else:

        suggestions = (
            DEFAULT_SUGGESTED_QUESTIONS.copy()
        )


    # --------------------------------------------------------
    # REMOVE ALREADY ASKED QUESTIONS
    # --------------------------------------------------------

    asked_questions = {

        question_text
        .strip()
        .lower()
        .rstrip("?")

        for question_text
        in get_user_questions()
    }

    filtered = []

    for suggestion in suggestions:

        normalised = (
            suggestion
            .strip()
            .lower()
            .rstrip("?")
        )

        if (
            normalised
            not in asked_questions
        ):

            filtered.append(
                suggestion
            )

    return filtered[:5]


# ============================================================
# CHART RENDERING
# ============================================================

def render_chart(chart):
    """Render optional result table or chart."""

    if chart is None:

        return

    try:

        st.write("")

        if chart.is_table:

            st.dataframe(
                chart.to_table_frame(),
                use_container_width=True,
                hide_index=True,
            )

        else:

            figure = (
                build_chart(
                    chart
                )
            )

            st.plotly_chart(
                figure,
                use_container_width=True,
                config={
                    "displayModeBar": False,
                },
            )

    except Exception as exc:

        print(
            "Chart rendering error:",
            exc,
        )

        st.caption(
            "Visualisation unavailable for this result."
        )


# ============================================================
# QUEUE QUESTION
# ============================================================

def queue_question(question):
    """
    Queue a question before Streamlit redraws the page.

    The question is immediately added to conversation history.
    The backend call occurs after the conversation page has
    completed its first normal render.
    """

    question = (
        question
        or ""
    ).strip()

    if not question:

        return

    # Ignore duplicate submissions while processing.
    if st.session_state.pending_question:

        return

    user = (
        st.session_state.user
    )

    quota = (
        check_quota(
            user.tier,
            st.session_state.questions_used,
        )
    )

    if not quota.allowed:

        return

    # Immediately show the user's question.
    st.session_state.messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    # Queue backend processing.
    st.session_state.pending_question = question

    # First conversation render has not yet happened.
    st.session_state.processing_armed = False


# ============================================================
# CHAT INPUT CALLBACK
# ============================================================

def queue_chat_input(input_key):
    """Queue text entered through st.chat_input."""

    question = (
        st.session_state.get(
            input_key,
            "",
        )
    )

    if question:

        queue_question(
            question
        )


# ============================================================
# PROCESS PENDING QUESTION
# ============================================================

def process_pending_question():
    """Run the backend request for a queued question."""

    question = (
        st.session_state.pending_question
    )

    if not question:

        return

    user = (
        st.session_state.user
    )

    result = None
    chart = None

    try:

        result = (
            ask(
                question,
                user_id=user.user_id,
                tier=user.tier,
                with_data=True,
            )
        )

        if result.ok:

            answer = (
                result.answer
                or
                "No answer was returned."
            )

        else:

            answer = (
                result.answer
                or
                (
                    "I couldn't answer that question. "
                    "Please try asking it another way."
                )
            )

    except Exception as exc:

        print(
            "Chat processing error:",
            exc,
        )

        answer = (
            "Something went wrong while processing "
            "your question. Please try again."
        )

        result = None

    # --------------------------------------------------------
    # QUOTA
    # --------------------------------------------------------

    if (
        result is not None
        and
        result.ok
    ):

        st.session_state.questions_used += 1

    # --------------------------------------------------------
    # CHART
    # --------------------------------------------------------

    if result is not None:

        chart = getattr(
            result,
            "chart",
            None,
        )

    # --------------------------------------------------------
    # STORE RESPONSE
    # --------------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "chart": chart,
        }
    )

    # Clear processing state.
    st.session_state.pending_question = None
    st.session_state.processing_armed = False

    st.rerun()


# ============================================================
# DELAYED PROCESSOR FRAGMENT
# ============================================================

@st.fragment(
    run_every="1s"
)
def pending_question_processor():
    """
    Allow the conversation screen to complete one normal render
    before starting the slower backend request.

    This avoids leaving the initial page visible in Streamlit's
    faded/stale state while the agent is working.
    """

    if not st.session_state.pending_question:

        return

    # First pass:
    # allow conversation page to finish rendering.
    if not st.session_state.processing_armed:

        st.session_state.processing_armed = True

        return

    # Second fragment pass:
    # run the backend request.
    process_pending_question()


# ============================================================
# LOGIN SIDEBAR
# ============================================================

def show_login_sidebar():
    """Sidebar shown before authentication."""

    with st.sidebar:

        st.html(
            demografy_brand_html()
        )

        st.html(
            """
            <div class="sidebar-description">
                Explore Australian demographic insights.
                Ask questions, compare locations and explore
                key demographic indicators using everyday language.
            </div>
            """
        )

        st.divider()

        st.caption(
            "Sign in to start exploring demographic insights."
        )

        st.divider()

        st.caption(
            "APPEARANCE"
        )

        st.toggle(
            "Dark theme",
            key="dark_mode",
        )


# ============================================================
# LOGIN
# ============================================================

def show_login():
    """Render login page."""

    st.html(
        """
        <div class="login-brand">

            <div class="demografy-wordmark">

                <span class="demografy-letter-d">
                    D
                </span>

                <span class="demografy-word-rest">
                    emografy
                </span>

            </div>

            <div class="demografy-chat-label">
                Insights Chat
            </div>

        </div>
        """
    )

    hero_col, login_col = (
        st.columns(
            [
                1.25,
                0.90,
            ],
            gap="large",
            vertical_alignment="center",
        )
    )

    with hero_col:

        st.html(
            """
            <div class="login-hero">

                <div class="login-kicker">
                    AUSTRALIAN DEMOGRAPHIC INSIGHTS
                </div>

                <div class="login-hero-title">
                    Explore demographic data
                    using everyday language.
                </div>

                <div class="login-hero-description">
                    Ask questions about Australian locations,
                    compare demographic indicators and uncover
                    insights without needing to understand
                    databases or write SQL.
                </div>

                <div class="login-features">

                    <div class="login-feature">

                        <div class="login-feature-icon">
                            📍
                        </div>

                        <div>
                            Explore demographic indicators
                        </div>

                    </div>

                    <div class="login-feature">

                        <div class="login-feature-icon">
                            ⚖️
                        </div>

                        <div>
                            Compare suburbs, regions and states
                        </div>

                    </div>

                    <div class="login-feature">

                        <div class="login-feature-icon">
                            📊
                        </div>

                        <div>
                            Find demographic rankings and patterns
                        </div>

                    </div>

                    <div class="login-feature">

                        <div class="login-feature-icon">
                            💬
                        </div>

                        <div>
                            Ask questions using natural language
                        </div>

                    </div>

                </div>

            </div>
            """
        )

    with login_col:

        with st.container(
            border=True
        ):

            st.html(
                """
                <div class="login-form-heading">
                    Welcome back
                </div>

                <div class="login-form-subtitle">
                    Sign in to access Demografy Insights Chat.
                </div>
                """
            )

            st.write("")

            with st.form(
                "login_form"
            ):

                user_id = (
                    st.text_input(
                        "User ID",
                        placeholder="Enter your Demografy user ID",
                    )
                )

                st.write("")

                submitted = (
                    st.form_submit_button(
                        "Continue to Insights Chat",
                        use_container_width=True,
                        type="primary",
                    )
                )

            st.html(
                """
                <div class="login-note">
                    Your access level and question allowance
                    are determined by your Demografy account.
                </div>
                """
            )

            if submitted:

                user_id = (
                    user_id
                    or ""
                ).strip()

                if not user_id:

                    st.warning(
                        "Please enter your user ID."
                    )

                    return

                with st.spinner(
                    "Signing you in..."
                ):

                    result = (
                        authenticate(
                            user_id
                        )
                    )

                if result.ok:

                    st.session_state.authenticated = True
                    st.session_state.user = result.user
                    st.session_state.messages = []
                    st.session_state.questions_used = 0
                    st.session_state.pending_question = None
                    st.session_state.processing_armed = False

                    st.rerun()

                else:

                    st.error(
                        result.error
                        or
                        "Unable to sign in."
                    )


# ============================================================
# AUTHENTICATED SIDEBAR
# ============================================================

def show_sidebar():
    """Render authenticated sidebar."""

    user = (
        st.session_state.user
    )

    quota = (
        check_quota(
            user.tier,
            st.session_state.questions_used,
        )
    )

    with st.sidebar:

        st.html(
            demografy_brand_html()
        )

        st.html(
            """
            <div class="sidebar-description">
                Explore Australian demographic insights.
                Ask questions, compare locations and explore
                key demographic indicators using everyday language.
            </div>
            """
        )

        st.divider()

        st.markdown(
            f"**{user.user_id}**"
        )

        if getattr(
            user,
            "email",
            None,
        ):

            st.caption(
                user.email
            )

        st.html(
            tier_badge_html(
                user.tier
            )
        )

        st.divider()

        st.caption(
            "QUESTIONS THIS SESSION"
        )

        st.metric(
            label="Usage",
            value=(
                f"{quota.used} / "
                f"{quota.limit}"
            ),
            label_visibility="collapsed",
        )

        if quota.limit > 0:

            progress = (
                quota.used
                / quota.limit
            )

        else:

            progress = 0

        st.progress(
            min(
                max(
                    progress,
                    0,
                ),
                1.0,
            )
        )

        st.caption(
            f"{quota.remaining} "
            "questions remaining"
        )

        if (
            quota.should_warn
            and quota.message
        ):

            st.warning(
                quota.message
            )

        if not quota.allowed:

            st.error(
                quota.message
                or
                "Question limit reached."
            )

        st.divider()

        st.caption(
            "APPEARANCE"
        )

        st.toggle(
            "Dark theme",
            key="dark_mode",
        )

        st.divider()

        if st.button(
            "Log out   →",
            use_container_width=True,
            key="logout_button",
        ):

            reset_session()

            st.rerun()

    return quota


# ============================================================
# MAIN HEADER
# ============================================================

def show_header():
    """Render main page title and tier."""

    user = (
        st.session_state.user
    )

    left, right = (
        st.columns(
            [
                7,
                1.2,
            ]
        )
    )

    with left:

        st.html(
            """
            <div class="chat-page-title">
                <span class="brand-d">D</span>emography Insights Chat
            </div>

            <div class="chat-page-subtitle">
                Ask questions about Australian demographics,
                compare locations and explore key indicators
                using everyday language.
            </div>
            """
        )

    with right:

        st.html(
            tier_badge_html(
                user.tier
            )
        )


# ============================================================
# CAPABILITIES
# ============================================================

def show_capabilities():
    """Show supported product capabilities."""

    with st.container(
        border=True
    ):

        st.html(
            """
            <div class="capability-heading">
                What can Insights Chat help you with?
            </div>

            <div class="capability-description">
                Ask questions about Australian demographic data
                without needing to understand databases or write SQL.
            </div>
            """
        )

        first_col, second_col = (
            st.columns(
                2
            )
        )

        with first_col:

            st.html(
                """
                <div class="capability-title">
                    📍 Explore locations
                </div>

                <div class="capability-copy">
                    Understand demographic characteristics
                    of Australian suburbs and areas.
                </div>
                """
            )

        with second_col:

            st.html(
                """
                <div class="capability-title">
                    ⚖️ Compare locations
                </div>

                <div class="capability-copy">
                    Compare demographic indicators between
                    suburbs, regions or states.
                </div>
                """
            )

        st.write("")

        third_col, fourth_col = (
            st.columns(
                2
            )
        )

        with third_col:

            st.html(
                """
                <div class="capability-title">
                    📊 Find rankings
                </div>

                <div class="capability-copy">
                    Find the highest or lowest ranked locations
                    for a demographic measure.
                </div>
                """
            )

        with fourth_col:

            st.html(
                """
                <div class="capability-title">
                    🔎 Explore indicators
                </div>

                <div class="capability-copy">
                    Explore prosperity, diversity, migration,
                    education, housing and family indicators.
                </div>
                """
            )


# ============================================================
# INITIAL QUESTION BUTTONS
# ============================================================

def show_initial_question_chips(
    quota_allowed=True,
):
    """Render initial suggested questions."""

    questions = (
        DEFAULT_SUGGESTED_QUESTIONS
    )

    processing = bool(
        st.session_state.pending_question
    )

    first_row = (
        st.columns(
            [
                1,
                1,
                1,
            ],
            gap="small",
        )
    )

    for index in range(
        3
    ):

        with first_row[index]:

            question = (
                questions[index]
            )

            st.button(
                question,
                key=f"initial_question_{index}",
                use_container_width=True,
                disabled=(
                    not quota_allowed
                    or
                    processing
                ),
                on_click=queue_question,
                args=(
                    question,
                ),
            )

    st.write("")

    left_space, fourth, fifth, right_space = (
        st.columns(
            [
                0.35,
                1,
                1,
                0.35,
            ],
            gap="small",
        )
    )

    with fourth:

        st.button(
            questions[3],
            key="initial_question_3",
            use_container_width=True,
            disabled=(
                not quota_allowed
                or
                processing
            ),
            on_click=queue_question,
            args=(
                questions[3],
            ),
        )

    with fifth:

        st.button(
            questions[4],
            key="initial_question_4",
            use_container_width=True,
            disabled=(
                not quota_allowed
                or
                processing
            ),
            on_click=queue_question,
            args=(
                questions[4],
            ),
        )


# ============================================================
# RELATED QUESTIONS
# ============================================================

def show_related_questions(
    questions,
    quota_allowed=True,
):
    """Render contextual related questions."""

    processing = bool(
        st.session_state.pending_question
    )

    with st.container(
        border=True
    ):

        st.html(
            """
            <div class="related-heading">
                💡 Related questions
            </div>

            <div class="related-description">
                Continue exploring based on
                your latest question.
            </div>
            """
        )

        for index, question in enumerate(
            questions
        ):

            st.button(
                question,
                key=f"related_question_{index}",
                use_container_width=True,
                disabled=(
                    not quota_allowed
                    or
                    processing
                ),
                on_click=queue_question,
                args=(
                    question,
                ),
            )


# ============================================================
# CHAT HISTORY
# ============================================================

def show_chat_history():
    """Render previous messages."""

    if not (
        st.session_state.messages
    ):

        return

    st.markdown(
        "### Conversation"
    )

    for message in (
        st.session_state.messages
    ):

        role = (
            message["role"]
        )

        avatar = (
            "👤"
            if role == "user"
            else "💡"
        )

        with st.chat_message(
            role,
            avatar=avatar,
        ):

            st.markdown(
                message["content"]
            )

            if role == "assistant":

                render_chart(
                    message.get(
                        "chart"
                    )
                )


# ============================================================
# INITIAL HOME
# ============================================================

def show_initial_home(
    quota,
):
    """Initial signed-in page."""

    user = (
        st.session_state.user
    )

    display_name = (
        html.escape(
            get_display_name(
                user
            )
        )
    )

    show_header()

    st.divider()

    # --------------------------------------------------------
    # WELCOME
    # --------------------------------------------------------

    st.html(
        f"""
        <div class="welcome-area">

            <div class="welcome-title">
                Nice to see you, {display_name}.
                What would you like to explore?
            </div>

            <div class="welcome-subtitle">
                Explore Australian demographic insights
                or choose one of the suggested questions below.
            </div>

        </div>
        """
    )

    # --------------------------------------------------------
    # CAPABILITIES
    # --------------------------------------------------------

    capability_left, capability_centre, capability_right = (
        st.columns(
            [
                0.35,
                6,
                0.35,
            ]
        )
    )

    with capability_centre:

        show_capabilities()

    # --------------------------------------------------------
    # SUGGESTED QUESTIONS
    # --------------------------------------------------------

    st.write("")

    suggestion_left, suggestion_centre, suggestion_right = (
        st.columns(
            [
                0.35,
                6,
                0.35,
            ]
        )
    )

    with suggestion_centre:

        st.html(
            """
            <div class="initial-suggestion-title">
                Suggested questions
            </div>

            <div class="initial-suggestion-copy">
                Select a question below or type your own question.
            </div>
            """
        )

        show_initial_question_chips(
            quota_allowed=(
                quota.allowed
            )
        )

    # --------------------------------------------------------
    # INITIAL CHAT INPUT
    # --------------------------------------------------------

    st.write("")
    st.write("")

    input_left, input_centre, input_right = (
        st.columns(
            [
                0.35,
                6,
                0.35,
            ]
        )
    )

    with input_centre:

        st.chat_input(
            "Ask Demografy a question...",
            key="initial_chat_input",
            disabled=(
                not quota.allowed
                or
                bool(
                    st.session_state.pending_question
                )
            ),
            on_submit=queue_chat_input,
            args=(
                "initial_chat_input",
            ),
        )


# ============================================================
# CONVERSATION SCREEN
# ============================================================

def show_conversation(
    quota,
):
    """
    Conversation screen.

    The question input deliberately sits outside the columns.
    """

    show_header()

    st.divider()

    is_processing = bool(
        st.session_state.pending_question
    )

    # --------------------------------------------------------
    # CONVERSATION + RELATED QUESTIONS
    # --------------------------------------------------------

    chat_col, related_col = (
        st.columns(
            [
                3.2,
                1.15,
            ],
            gap="large",
        )
    )

    # --------------------------------------------------------
    # CHAT HISTORY
    # --------------------------------------------------------

    with chat_col:

        show_chat_history()

    # --------------------------------------------------------
    # RELATED QUESTIONS
    # --------------------------------------------------------

    with related_col:

        latest_question = (
            get_last_user_question()
        )

        related_questions = (
            get_related_questions(
                latest_question
            )
        )

        show_related_questions(
            related_questions,
            quota_allowed=(
                quota.allowed
                and
                not is_processing
            ),
        )

    # ========================================================
    # INPUT AREA
    # ========================================================

    st.write("")

    # --------------------------------------------------------
    # PROCESSING STATE
    # --------------------------------------------------------

    if is_processing:

        st.html(
            """
            <div class="
                chat-status
                chat-status-processing
            ">
                ⏳ Your question is being processed.
                Please wait.
            </div>
            """
        )

        # Keep the normal prompt visible.
        # Do not put the status message inside the input.
        st.chat_input(
            "Ask Demografy a question...",
            key="processing_chat_input",
            disabled=True,
        )

    # --------------------------------------------------------
    # NORMAL INPUT
    # --------------------------------------------------------

    elif quota.allowed:

        st.chat_input(
            "Ask Demografy a question...",
            key="conversation_chat_input",
            on_submit=queue_chat_input,
            args=(
                "conversation_chat_input",
            ),
        )

    # --------------------------------------------------------
    # QUOTA REACHED
    # --------------------------------------------------------

    else:

        limit_message = (
            quota.message
            or
            (
                "You have reached your question limit. "
                "Please upgrade your plan to continue."
            )
        )

        st.html(
            f"""
            <div class="
                chat-status
                chat-status-limit
            ">
                ⚠️ {html.escape(limit_message)}
            </div>
            """
        )

        # Input remains visually normal but disabled.
        st.chat_input(
            "Ask Demografy a question...",
            key="disabled_chat_input",
            disabled=True,
        )

    # ========================================================
    # DELAYED BACKEND PROCESSOR
    # ========================================================

    pending_question_processor()


# ============================================================
# AUTHENTICATED APP
# ============================================================

def show_chat():
    """Render authenticated application."""

    quota = (
        show_sidebar()
    )

    if not get_user_questions():

        show_initial_home(
            quota
        )

    else:

        show_conversation(
            quota
        )


# ============================================================
# APPLICATION ENTRY
# ============================================================

if (
    st.session_state.authenticated
    and
    st.session_state.user
):

    show_chat()

else:

    show_login_sidebar()

    show_login()