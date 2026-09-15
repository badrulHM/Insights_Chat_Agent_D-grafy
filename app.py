# Demografy Insights Chat Streamlit frontend.

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


# ============================================================
# DEMOGRAFY UI STYLING
# ============================================================

st.markdown(
    """
    <style>

    /* -------------------------------------------------------
       GLOBAL
    ------------------------------------------------------- */

    .stApp {
        background-color: #FFFFFF;
    }

    .block-container {
        max-width: 1100px;
        padding-top: 2rem;
        padding-bottom: 7rem;
    }

    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }

    header {
        visibility: hidden;
    }


    /* -------------------------------------------------------
       SIDEBAR
    ------------------------------------------------------- */

    [data-testid="stSidebar"] {
        background-color: #F7F7FB;
        border-right: 1px solid #E6E4EB;
    }

    [data-testid="stSidebar"] .block-container {
        padding-top: 2rem;
    }


    /* -------------------------------------------------------
       HEADINGS
    ------------------------------------------------------- */

    h1 {
        color: #22222C;
        font-weight: 700;
    }

    h2 {
        color: #282832;
        font-weight: 650;
    }

    h3 {
        color: #30303A;
        font-weight: 650;
    }


    /* -------------------------------------------------------
       PRIMARY BUTTON
    ------------------------------------------------------- */

    div[data-testid="stFormSubmitButton"] button {
        background-color: #6F2DE2;
        color: white;
        border: 1px solid #6F2DE2;
        border-radius: 10px;
        min-height: 44px;
        font-weight: 600;
    }

    div[data-testid="stFormSubmitButton"] button:hover {
        background-color: #5F23C9;
        border-color: #5F23C9;
        color: white;
    }


    /* -------------------------------------------------------
       NORMAL BUTTONS
    ------------------------------------------------------- */

    .stButton button {
        border-radius: 12px;
        min-height: 46px;
        border: 1px solid #DDD8E8;
        background-color: #FFFFFF;
    }

    .stButton button:hover {
        border-color: #6F2DE2;
        color: #6F2DE2;
        background-color: #FAF8FF;
    }


    /* -------------------------------------------------------
       CHAT MESSAGES
    ------------------------------------------------------- */

    [data-testid="stChatMessage"] {
        border-radius: 14px;
        padding: 0.4rem;
        margin-bottom: 0.6rem;
    }

    [data-testid="stChatMessageContent"] {
        font-size: 14px;
        line-height: 1.6;
    }


    /* -------------------------------------------------------
       CHAT INPUT
    ------------------------------------------------------- */

    [data-testid="stChatInput"] {
        border: 1.5px solid #D9D3E6 !important;
        border-radius: 14px !important;
        background-color: #FFFFFF !important;
        box-shadow: 0 2px 8px rgba(40, 30, 70, 0.08);
        transition: all 0.15s ease;
    }

    [data-testid="stChatInput"]:focus-within {
        border-color: #6F2DE2 !important;
        box-shadow: 0 0 0 3px rgba(111, 45, 226, 0.10);
    }

    [data-testid="stChatInput"] textarea {
        background-color: #FFFFFF !important;
        color: #22222C !important;
        font-size: 14px;
    }

    [data-testid="stChatInput"] textarea::placeholder {
        color: #92929C;
    }


    /* -------------------------------------------------------
       METRICS
    ------------------------------------------------------- */

    [data-testid="stMetricValue"] {
        font-size: 1.6rem;
        font-weight: 700;
    }


    /* -------------------------------------------------------
       CONTAINERS
    ------------------------------------------------------- */

    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 16px;
        border-color: #E9E5F1;
    }


    /* -------------------------------------------------------
       DIVIDERS
    ------------------------------------------------------- */

    hr {
        border-color: #ECEAF0;
    }


    /* -------------------------------------------------------
       DATAFRAME / CHART AREA
    ------------------------------------------------------- */

    [data-testid="stDataFrame"] {
        border: 1px solid #E8E4EF;
        border-radius: 12px;
        overflow: hidden;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def reset_session():
    """Clear the current browser session."""

    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.messages = []
    st.session_state.questions_used = 0


def tier_icon(tier):
    """Return a simple tier label."""

    tier = (tier or "free").lower()

    if tier == "pro":
        return "🟣 PRO"

    if tier == "basic":
        return "🟪 BASIC"

    return "⚪ FREE"


# ============================================================
# CHART RENDERING
# ============================================================

def render_chart(chart):
    """
    Render the visual selected by the backend.

    Text remains the primary response.

    If the backend recommends a table, Streamlit renders
    the result as a dataframe.

    Otherwise the ChartSpec is passed to ui_charts.py,
    which builds the Plotly chart.

    A chart failure must never cause the chat answer itself
    to fail.
    """

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

            figure = build_chart(chart)

            st.plotly_chart(
                figure,
                use_container_width=True,
                config={
                    "displayModeBar": False,
                },
            )

    except Exception as exc:

        # Keep the text answer even if the visual fails.
        print(
            "Chart rendering error:",
            exc,
        )

        st.caption(
            "Visualisation unavailable for this result."
        )


# ============================================================
# LOGIN PAGE
# ============================================================

def show_login():

    left, centre, right = st.columns(
        [1.2, 1, 1.2]
    )

    with centre:

        st.write("")
        st.write("")

        st.title("Demografy")

        st.subheader("Insights Chat")

        st.caption(
            "Explore Australian demographic insights "
            "using natural language."
        )

        st.write("")

        with st.container(
            border=True
        ):

            st.markdown(
                "### Sign in"
            )

            st.caption(
                "Enter your Demografy user ID to continue."
            )

            with st.form(
                "login_form"
            ):

                user_id = st.text_input(
                    "User ID",
                    placeholder="Enter your user ID",
                )

                submitted = (
                    st.form_submit_button(
                        "Sign in",
                        use_container_width=True,
                        type="primary",
                    )
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
                    "Signing in..."
                ):

                    result = authenticate(
                        user_id
                    )

                if result.ok:

                    st.session_state.authenticated = True
                    st.session_state.user = result.user
                    st.session_state.messages = []
                    st.session_state.questions_used = 0

                    st.rerun()

                else:

                    st.error(
                        result.error
                        or "Unable to sign in."
                    )


# ============================================================
# SIDEBAR
# ============================================================

def show_sidebar():

    user = st.session_state.user

    quota = check_quota(
        user.tier,
        st.session_state.questions_used,
    )

    with st.sidebar:

        st.title(
            "Demografy"
        )

        st.caption(
            "Insights Chat"
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

        st.markdown(
            tier_icon(
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
                or "Question limit reached."
            )

        st.divider()

        if st.button(
            "Log out",
            use_container_width=True,
        ):

            reset_session()

            st.rerun()

    return quota


# ============================================================
# MAIN HEADER
# ============================================================

def show_header():

    left, right = st.columns(
        [6, 1]
    )

    with left:

        st.title(
            "Insights Chat"
        )

        st.caption(
            "Explore Australian demographic information "
            "by asking questions in everyday language."
        )

    with right:

        user = st.session_state.user

        st.write("")

        st.markdown(
            tier_icon(
                user.tier
            )
        )


# ============================================================
# WHAT THE CHATBOT CAN DO
# ============================================================

def show_capabilities():

    with st.container(
        border=True
    ):

        st.subheader(
            "What can Insights Chat help you with?"
        )

        st.write(
            "Ask questions about Australian demographic data "
            "without needing to understand databases or write SQL."
        )

        st.write("")

        col1, col2 = st.columns(
            2
        )

        with col1:

            st.markdown(
                "**📍 Explore locations**"
            )

            st.caption(
                "Understand demographic characteristics "
                "of Australian suburbs and areas."
            )

        with col2:

            st.markdown(
                "**⚖️ Compare locations**"
            )

            st.caption(
                "Compare demographic indicators "
                "between suburbs, regions or states."
            )

        st.write("")

        col3, col4 = st.columns(
            2
        )

        with col3:

            st.markdown(
                "**📊 Find rankings**"
            )

            st.caption(
                "Find the highest or lowest ranked "
                "locations for a demographic measure."
            )

        with col4:

            st.markdown(
                "**🔎 Explore indicators**"
            )

            st.caption(
                "Explore prosperity, diversity, migration, "
                "education, housing and family indicators."
            )


# ============================================================
# SUGGESTED QUESTIONS
# ============================================================

def show_suggested_prompts():

    st.write("")

    st.subheader(
        "Suggested questions"
    )

    st.caption(
        "Select an example below or type your own question."
    )

    prompts = [

        (
            "💰 Prosperity score for Glenwood",
            "What is the prosperity score for Glenwood?",
        ),

        (
            "🌏 Most diverse suburbs in Victoria",
            "What are the top 5 most diverse suburbs in Victoria?",
        ),

        (
            "⚖️ Compare Glenwood and Karabar",
            "Compare the diversity index of Glenwood and Karabar.",
        ),

        (
            "🎓 State with highest learning level",
            "Which state has the highest average learning level?",
        ),

        (
            "🏠 Affordable rentals in Queensland",
            "What are the most affordable rental suburbs in Queensland?",
        ),

        (
            "📊 Home ownership vs rental access",
            "Compare home ownership and rental access by state.",
        ),
    ]

    for i in range(
        0,
        len(prompts),
        2,
    ):

        col1, col2 = st.columns(
            2
        )

        label_1, question_1 = (
            prompts[i]
        )

        with col1:

            if st.button(
                label_1,
                key=f"prompt_{i}",
                use_container_width=True,
            ):

                process_question(
                    question_1
                )

        if (
            i + 1
            < len(prompts)
        ):

            label_2, question_2 = (
                prompts[
                    i + 1
                ]
            )

            with col2:

                if st.button(
                    label_2,
                    key=f"prompt_{i + 1}",
                    use_container_width=True,
                ):

                    process_question(
                        question_2
                    )


# ============================================================
# CHAT HISTORY
# ============================================================

def show_chat_history():

    if not st.session_state.messages:
        return

    st.write("")

    st.divider()

    st.subheader(
        "Conversation"
    )

    for message in (
        st.session_state.messages
    ):

        role = (
            message["role"]
        )

        if role == "user":
            avatar = "👤"
        else:
            avatar = "💡"

        with st.chat_message(
            role,
            avatar=avatar,
        ):

            st.markdown(
                message["content"]
            )

            # Assistant messages may contain
            # a supplementary ChartSpec.

            if role == "assistant":

                render_chart(
                    message.get(
                        "chart"
                    )
                )


# ============================================================
# PROCESS QUESTION
# ============================================================

def process_question(
    question
):

    question = (
        question
        or ""
    ).strip()

    if not question:
        return

    user = (
        st.session_state.user
    )

    quota = check_quota(
        user.tier,
        st.session_state.questions_used,
    )

    if not quota.allowed:

        st.warning(
            quota.message
            or "Question limit reached."
        )

        return

    # --------------------------------------------------------
    # Add user question
    # --------------------------------------------------------

    st.session_state.messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    # --------------------------------------------------------
    # Call backend
    # --------------------------------------------------------

    try:

        with st.spinner(
            "Searching Demografy data..."
        ):

            result = ask(
                question,
                user_id=user.user_id,
                tier=user.tier,

                # Important:
                # request the result rows and
                # supplementary chart suggestion.
                with_data=True,
            )

        if result.ok:

            answer = (
                result.answer
                or "No answer was returned."
            )

        else:

            answer = (
                result.answer
                or (
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
    # Question quota
    # --------------------------------------------------------

    # Only consume a question when the backend
    # successfully produced an answer.

    if (
        result is not None
        and result.ok
    ):

        st.session_state.questions_used += 1

    # --------------------------------------------------------
    # Store assistant answer and chart
    # --------------------------------------------------------

    chart = None

    if result is not None:
        chart = result.chart

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "chart": chart,
        }
    )

    st.rerun()


# ============================================================
# MAIN CHAT PAGE
# ============================================================

def show_chat():

    quota = show_sidebar()

    show_header()

    # --------------------------------------------------------
    # First-time user guidance
    # --------------------------------------------------------

    if not st.session_state.messages:

        show_capabilities()

        show_suggested_prompts()

    # --------------------------------------------------------
    # Conversation
    # --------------------------------------------------------

    show_chat_history()

    # --------------------------------------------------------
    # Chat input
    # --------------------------------------------------------

    if quota.allowed:

        question = st.chat_input(
            "Ask Demografy a question..."
        )

        if question:

            process_question(
                question
            )

    else:

        st.warning(
            quota.message
            or (
                "You have reached your question "
                "limit for this session."
            )
        )

        st.chat_input(
            "Question limit reached",
            disabled=True,
        )


# ============================================================
# APP START
# ============================================================

if (
    st.session_state.authenticated
    and st.session_state.user
):

    show_chat()

else:

    show_login()