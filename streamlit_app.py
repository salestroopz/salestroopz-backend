# streamlit_app.py (Main Entry Point & Landing Page)
import streamlit as st
from PIL import Image # Optional

# --- Page Configuration (MUST BE THE FIRST STREAMLIT COMMAND) ---
st.set_page_config(
    page_title="SalesTroopz - Automate Your Outreach",
    page_icon="assets/salestroopz_logo.png", # Path to your small icon for browser tab
    layout="wide",
    initial_sidebar_state="auto" # Let Streamlit decide or use "expanded"
)

# --- Load and Display Logo in Sidebar (Consistent across all pages) ---
try:
    logo_path = "assets/salestroopz_logo.png"
    st.sidebar.image(logo_path, use_column_width='auto', width=180) # Adjust width
    # st.sidebar.title("SalesTroopz") # Title can be part of the logo or main page
    st.sidebar.markdown("---")
except FileNotFoundError:
    st.sidebar.error("Logo image not found. Ensure 'assets/salestroopz_logo.png' exists.")
except Exception as e:
    st.sidebar.error(f"Error loading logo: {e}")

# --- Session State Initialization (Minimal needed here, most is in 0_App.py) ---
if 'auth_token' not in st.session_state:
    st.session_state.auth_token = None
# if 'user_email' not in st.session_state: # This will be set upon login
#    st.session_state.user_email = None


# --- Landing Page Content Function ---
def display_main_landing_page():
    st.markdown(
        """
        <style>
            .hero-section { text-align: center; padding: 3rem 1rem; }
            .hero-section h1 { font-size: 3.0rem; font-weight: 700; margin-bottom: 1rem; line-height: 1.2; color: #2A3B4D; }
            .hero-section .subtitle { font-size: 1.2rem; color: #5A6A7B; max-width: 700px; margin: 0 auto 2.5rem auto; }
        </style>
        <div class="hero-section">
            <h1>Automate Your Outreach. Close More Deals.</h1>
            <p class="subtitle">
                SalesTroopz empowers your sales team with AI-driven campaign generation,
                intelligent lead engagement, and automated reply handling.
                Focus on conversations that matter.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    cols_cta = st.columns([0.2, 0.3, 0.2, 0.3, 0.2])
    with cols_cta[1]:
        if st.button("🚀 Get Started", use_container_width=True, type="primary", key="landing_get_started_main"):
            st.switch_page("pages/2_Signup.py") # Go to Signup page
    with cols_cta[3]:
        if st.button("View Pricing", use_container_width=True, key="landing_view_pricing_main"):
            st.switch_page("pages/4_Subscribe.py") # Go to Subscribe/Pricing page

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.header("✨ Why SalesTroopz?")
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("🎯 AI-Powered Campaigns")
        st.write("Generate personalized multi-step email sequences in minutes.")
    with col2:
        st.subheader("🧠 Intelligent Reply Handling")
        st.write("Automatically classify incoming replies and get summaries.")
    with col3:
        st.subheader("📈 Performance Analytics")
        st.write("Track campaign performance and optimize your strategies.")
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("© 2024 SalesTroopz. All rights reserved.")


# --- Sidebar Navigation & Main Logic ---
# Streamlit automatically creates navigation from files in the `pages/` directory.
# This main streamlit_app.py will effectively be the "Home" page.

if st.session_state.get("auth_token"):
    # If the user is already logged in and somehow lands on streamlit_app.py,
    # redirect them to the main app/dashboard.
    st.info("Redirecting to your dashboard...")
    time.sleep(0.5) # Brief pause for the message to be seen
    st.switch_page("pages/0_App.py") # Assuming 0_App.py is your main authenticated view
else:
    # Show landing page content if not logged in
    display_main_landing_page()
    # Add login/signup links to the sidebar for unauthenticated users
    st.sidebar.page_link("pages/1_Login.py", label="Login", icon="🔑")
    st.sidebar.page_link("pages/2_Signup.py", label="Sign Up", icon="📝")

# Note: If a user is logged in, the pages defined in `pages/` directory
# will still be available in the sidebar. The `0_App.py` page
# will be where they primarily interact with the authenticated parts of your application.
