# streamlit_app.py

import streamlit as st
import requests
from typing import Dict, Any, Optional
import time
import json # Import json for ICP form

# --- Configuration ---
# ... (Keep endpoint URLs) ...
BACKEND_URL = "https://salestroopz-backendpython-m-uvicorn-app.onrender.com"
LOGIN_ENDPOINT = f"{BACKEND_URL}/api/v1/auth/token"
REGISTER_ENDPOINT = f"{BACKEND_URL}/api/v1/auth/register"
LEADS_ENDPOINT = f"{BACKEND_URL}/api/v1/leads"
ICP_ENDPOINT = f"{BACKEND_URL}/api/v1/icp"

# --- Authentication Functions ---
# ... (Keep login_user, register_user, logout_user) ...
def login_user(email, password) -> Optional[str]: pass
def register_user(org_name, email, password) -> bool: pass
def logout_user(): pass

# --- API Helper Functions ---
# ... (Keep get_authenticated_request, get_icp_data, save_icp_data) ...
def get_authenticated_request(endpoint: str, token: str) -> Optional[Dict[str, Any]]: pass
def get_icp_data(token: str) -> Optional[Dict[str, Any]]: pass
def save_icp_data(icp_input_dict: Dict[str, Any], token: str) -> bool: pass

# --- Main App Logic ---

# Initialize session state keys
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "auth_token" not in st.session_state: st.session_state["auth_token"] = None
if "user_email" not in st.session_state: st.session_state["user_email"] = None
if "view" not in st.session_state: st.session_state["view"] = "Login"
# Initialize icp_data cache flag
if 'icp_data' not in st.session_state: st.session_state['icp_data'] = None # Use None initially

st.set_page_config(page_title="SalesTroopz", layout="wide")

# --- Authentication Section (Login / Sign Up) ---
if not st.session_state["authenticated"]:
    # --- Login View ---
    if st.session_state["view"] == "Login":
        st.title("SalesTroopz Login")
        st.markdown("Please log in to access the platform.")
        # ... (Keep login form and logic) ...
        with st.form("login_form"):
             email = st.text_input("Email", key="login_email_input")
             password = st.text_input("Password", type="password", key="login_password_input")
             submitted = st.form_submit_button("Login")
             if submitted:
             if not email or not password:
                st.warning("Please enter both email and password.")
            else:
                # --- THIS IS WHERE LOGIN HAPPENS ---
                with st.spinner("Attempting login..."):
                    token = login_user(email, password)
                if token:
                 # ... login call logic ...
                 pass # Placeholder
        # Switch to Sign Up
        st.divider(); st.markdown("Don't have an account?")
        if st.button("Sign Up Here", key="go_to_signup"): st.session_state["view"] = "Sign Up"; st.rerun()

    # --- Sign Up View ---
    elif st.session_state["view"] == "Sign Up":
        st.title("Create Your SalesTroopz Account")
        # ... (Keep signup form and logic) ...
        with st.form("signup_form"):
             org_name = st.text_input("Organization Name", key="signup_org")
             email = st.text_input("Email Address", key="signup_email")
             password = st.text_input("Create Password", type="password", key="signup_pw1")
             confirm_password = st.text_input("Confirm Password", type="password", key="signup_pw2")
             submitted = st.form_submit_button("Sign Up")
             if submitted:
                 # ... validation and register_user call ...
                 pass # Placeholder
        # Switch to Login
        st.divider(); st.markdown("Already have an account?")
        if st.button("Login Here", key="go_to_login"): st.session_state["view"] = "Login"; st.rerun()

# --- Main Application Logic (Shown Only After Login) ---
else: # This 'else' corresponds to 'if not st.session_state["authenticated"]'
    # Ensure token exists if authenticated flag is true
    auth_token = st.session_state.get("auth_token")
    if not auth_token:
        st.warning("Authentication token missing. Logging out.")
        logout_user() # Force logout if state is inconsistent
        st.stop()

    # --- Sidebar Navigation (Defined ONCE) ---
    with st.sidebar:
        st.title("SalesTroopz")
        st.write(f"User: {st.session_state.get('user_email', 'N/A')}")
        # TODO: Fetch and display Org Name from user details
        # st.write(f"Org: {st.session_state.get('user_org_name', 'N/A')}")
        st.divider()

        page = st.radio(
            "Navigate",
            ["Dashboard", "Leads", "Campaigns", "Setup Assistant", "Configuration"],
            key="nav_radio" # Consistent key
        )
        st.divider()
        if st.button("Logout"):
            logout_user() # Call logout function


    # --- === Page Content (Correctly Indented) === ---
    if page == "Dashboard":
        st.header("Dashboard")
        st.write("Welcome to SalesTroopz!")
        st.info("Dashboard widgets and stats coming soon.")
        # Example: Button to test fetching leads
        if st.button("Fetch My Leads (Test)"):
            with st.spinner("Fetching leads..."):
                leads_data = get_authenticated_request(LEADS_ENDPOINT, auth_token) # Pass token
            if leads_data is not None: # Check for None on error
                st.success(f"Fetched {len(leads_data)} leads.")
                st.dataframe(leads_data)
            # Error messages displayed by helper function

    elif page == "Leads":
        st.header("Leads Management")
        st.info("Lead table, filtering, and actions coming soon.")
        # TODO: Implement lead display

    elif page == "Campaigns":
        st.header("Campaign Management")
        st.info("Campaign/Step definition and monitoring coming soon.")
        # TODO: Implement campaign UI

    elif page == "Setup Assistant":
        st.header("Setup Assistant (Chatbot)")
        st.info("Chatbot interface integration coming soon.")
        # TODO: Integrate chatbot_ui.py logic

    elif page == "Configuration":
        st.header("⚙️ Configuration")
        tab1, tab2, tab3 = st.tabs(["🎯 ICP Definition", "💡 Offerings", "📧 Email Sending"])

        with tab1:
            st.subheader("Ideal Customer Profile (ICP)")
            # --- Start of ICP Form Logic ---
            # Only try to load data if it hasn't been loaded or needs refresh
            if st.session_state.get('icp_data') is None: # Check if cache is empty
                 with st.spinner("Loading ICP data..."):
                     st.session_state['icp_data'] = get_icp_data(auth_token) or {} # Use empty dict if None returned

            # Use the cached or newly fetched data (guaranteed to be a dict now)
            current_icp = st.session_state.get('icp_data', {})

            # ICP Form
            with st.form("icp_form"):
                st.text_input("ICP Name:", value=current_icp.get("name", "Default ICP"), key="icp_name", help="...")
                st.text_area("Target Titles/Keywords (one per line):", value="\n".join(current_icp.get("title_keywords", [])), key="icp_titles", height=100, help="...")
                st.text_area("Target Industries/Keywords (one per line):", value="\n".join(current_icp.get("industry_keywords", [])), key="icp_industries", height=100, help="...")
                st.text_area("Target Locations/Keywords (one per line):", value="\n".join(current_icp.get("location_keywords", [])), key="icp_locations", height=100, help="...")
                st.text_input("Company Size Rules (JSON Text):", value=json.dumps(current_icp.get("company_size_rules", {})), key="icp_size_rules_text", help='e.g., {"min": 50, "max": 500}')

                submitted = st.form_submit_button("Save ICP Definition")

                if submitted:
                    # ... (Keep form processing logic: read state, parse, build payload) ...
                    title_kws = [kw.strip() for kw in st.session_state.icp_titles.split('\n') if kw.strip()]
                    # ... (parse other text areas) ...
                    size_rules_dict = {}
                    try: parsed_rules = json.loads(st.session_state.icp_size_rules_text); size_rules_dict = parsed_rules if isinstance(parsed_rules, dict) else {}
                    except json.JSONDecodeError: st.warning("Invalid JSON for Company Size Rules."); size_rules_dict = {} # Keep empty on error

                    icp_payload = { "name": st.session_state.icp_name, "title_keywords": title_kws, "industry_keywords": industry_kws, "location_keywords": location_kws, "company_size_rules": size_rules_dict }
                    # ... (end build payload) ...

                    with st.spinner("Saving ICP..."):
                        success = save_icp_data(icp_payload, auth_token) # Pass token
                    if success:
                        st.session_state['icp_data'] = None # Clear cache to force reload
                        st.rerun() # Rerun to show updated data (or success message persistence)
            # --- End of ICP Form Logic ---

        with tab2:
            st.subheader("Offerings")
            st.info("Offering management UI coming soon.")
            # TODO: Implement Offerings UI

        with tab3:
            st.subheader("Email Sending Configuration")
            st.info("Email setup UI coming soon.")
            # TODO: Implement Email Sending UI

    else:
        # Fallback for unknown page selection
        st.error("Page not found.")
