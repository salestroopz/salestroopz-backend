# streamlit_app.py (Main Entry Point & Landing Page)
import streamlit as st
from PIL import Image # Optional, if you use it for logo or favicon
import os
import time

# --- Page Configuration (MUST BE THE FIRST STREAMLIT COMMAND) ---
# Using your desired title and centered layout for the landing page part
# If your authenticated app part ('0_App.py') needs 'wide', it can set its own layout.
# However, st.set_page_config is global, so the last one called "wins" for layout if
# switching between pages that try to set it differently. It's often best to pick one
# global layout or manage it carefully. For a landing page, "centered" can be nice.
# For the app itself, "wide" is often preferred. Let's keep it centered for the landing.
st.set_page_config(
    page_title="SalesTroopz – AI-Powered Appointment Setter",
    page_icon="assets/salestroopz_logo.png", # Make sure this path is correct
    layout="centered", # As per your content
    initial_sidebar_state="collapsed" # Landing page usually has sidebar collapsed initially
)

# --- Load and Display Logo in Sidebar (Consistent across all pages) ---
try:
    logo_path = "assets/salestroopz_logo.png"
    st.sidebar.image(logo_path, width=150) # Adjusted width for sidebar
    # st.sidebar.title("SalesTroopz") # Title might be redundant if logo is clear
    st.sidebar.markdown("---")
except FileNotFoundError:
    st.sidebar.error("Logo image not found at 'assets/salestroopz_logo.png'")
except Exception as e:
    st.sidebar.error(f"Error loading logo: {e}")

# --- Session State Initialization ---
if 'auth_token' not in st.session_state:
    st.session_state.auth_token = None
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'subscription_status' not in st.session_state:
    st.session_state.subscription_status = None

# --- Sidebar Navigation Links ---
if st.session_state.get("auth_token"):
    st.sidebar.success(f"Logged in as {st.session_state.user_email}")
    st.sidebar.page_link("pages/0_App.py", label="Go to App Dashboard", icon="🚀")
    if st.sidebar.button("Logout", key="sidebar_logout_main_app", use_container_width=True):
        keys_to_clear = ['auth_token', 'user_email', 'subscription_status', 'view', 'nav_radio']
        for key in keys_to_clear:
            if key in st.session_state: del st.session_state[key]
        st.toast("Logged out successfully!", icon="✅")
        time.sleep(0.5)
        st.rerun()
else:
    st.sidebar.page_link("streamlit_app.py", label="Home", icon="🏠") # Link to this landing page
    st.sidebar.page_link("pages/1_Login.py", label="Login", icon="🔑")
    st.sidebar.page_link("pages/2_Signup.py", label="Sign Up", icon="📝")
    # You might want a "Pricing" link here later that goes to pages/4_Subscribe.py
    # st.sidebar.page_link("pages/4_Subscribe.py", label="Pricing", icon="💰")

st.sidebar.markdown("---")
st.sidebar.caption("© 2025 SalesTroopz")


# --- Main Content Area ---
def display_landing_page():
    # Optional: Add your simple logo at the top of the main content for the landing page
    # This is different from the sidebar logo.
    # try:
    #     st.image("assets/salestroopz_logo.png", width=180) # Use a separate path or the same
    # except FileNotFoundError:
    #     pass # Silently fail if main page logo not found, sidebar one is primary

    # Hero Section
    st.markdown("## 🎯 Let Your Sales Reps Sell. We’ll Set the Appointments.")
    st.markdown("**SalesTroopz** is your AI-powered assistant that books meetings, so your reps can focus on closing deals — not chasing leads.")
    # Replace with actual links or Streamlit page_links/switch_page
    # For now, let's assume these are external links or placeholders
    # If "Get Early Access" should go to your signup page:
    # st.page_link("pages/2_Signup.py", label="🚀 Get Early Access")
    # If "Book a Demo" is an external Calendly link:
    # st.markdown("[📅 Book a Demo](https://calendly.com/yourlink)", unsafe_allow_html=True)
    
    col_cta1, col_cta2 = st.columns(2)
    with col_cta1:
        if st.button("🚀 Get Started / Sign Up", type="primary", use_container_width=True, key="hero_signup"):
            st.switch_page("pages/2_Signup.py")
    with col_cta2:
        # Assuming Book a Demo is an external link for now
        st.link_button("📅 Book a Demo", "https://calendly.com/yourlink", use_container_width=True)


    st.markdown("---")

    # Why Section
    st.markdown("### ✅ Why SalesTroopz?")
    cols_why = st.columns(2)
    with cols_why[0]:
        st.markdown("#### ❌ The Old Way:")
        st.markdown("- Sales reps burn 60% of their time prospecting")
        st.markdown("- Tools give data, not outcomes")
        st.markdown("- Manual follow-ups and inefficiency")
    with cols_why[1]:
        st.markdown("#### ✅ The SalesTroopz Way:")
        st.markdown("- **AI does the prospecting, qualifying & scheduling**")
        st.markdown("- **Outcome-based meetings, not leads**")
        st.markdown("- **CRM integration built-in**")

    st.markdown("---")

    # Features Comparison Table
    st.markdown("### 💡 What Makes Us Different?")
    # Using a more Streamlit-native way for tables if complex markdown is an issue,
    # but your markdown table should work.
    # For complex tables, st.dataframe(pd.DataFrame(...)) is also an option.
    st.markdown("""
    | Feature                          | Sales Tools | Appointment Setters | **SalesTroopz** |
    |----------------------------------|-------------|----------------------|-----------------|
    | Automates outreach to booking    | ❌          | ✅                   | ✅ ✅           |
    | Learns ideal customer profile    | ❌          | ❌                   | ✅              |
    | Outcome-based pricing            | ❌          | ❌                   | ✅              |
    | CRM-integrated                   | ❌          | ❌                   | ✅              |
    | Fully AI-driven, no scripts      | ❌          | ✅ (manual)          | ✅              |
    """)

    st.markdown("---")

    # How it Works
    st.markdown("### 🔄 How It Works")
    st.markdown("""
    1.  **🎯 Define Your Ideal Customer** - Tell SalesTroopz who you want to reach.
    2.  **🤖 AI Agents Research & Qualify** - Our AI finds and vets leads based on your ICP.
    3.  **✍️ AI Crafts & Sends Outreach** - Personalized, multi-step email campaigns are generated and executed.
    4.  **💬 Intelligent Reply Handling** - Positive replies and meeting requests are flagged for you.
    5.  **📅 Meetings Booked on Your Calendar** - We aim to get meetings scheduled directly.
    6.  **📈 You Sell. We Scale.** - Your reps focus on closing, we handle the top of the funnel.
    """) # Made it a bit more descriptive

    st.markdown("---")

    # CTA
    st.markdown("### ✨ Ready to See Real Results?")
    st.markdown("Let SalesTroopz handle the outreach. You focus on the close.")
    
    col_cta_bottom1, col_cta_bottom2 = st.columns(2)
    with col_cta_bottom1:
        if st.button("🚀 Get Early Access Now", type="primary", use_container_width=True, key="bottom_signup"):
             st.switch_page("pages/2_Signup.py")
    with col_cta_bottom2:
        st.link_button("📞 Talk to Us / Demo", "https://calendly.com/yourlink", use_container_width=True)


    st.markdown("---")
    # Optional Footer
    st.markdown("<div style='text-align: center; color: #777; font-size: 0.9em;'>© 2025 SalesTroopz. Built with 💡 and Streamlit.</div>", unsafe_allow_html=True)


if not st.session_state.get("auth_token"):
    display_landing_page()
else:
    # User is authenticated, redirect them to the main app page.
    # This ensures that if a logged-in user tries to go to the root URL,
    # they are taken into the app instead of seeing the landing page again.
    st.info("You are logged in. Redirecting to your dashboard...")
    time.sleep(1) # Brief pause for the message
    st.switch_page("pages/0_App.py") # Ensure 'pages/0_App.py' is your main authenticated app page
