# streamlit_app.py

import streamlit as st
import requests
from typing import Dict, Any, Optional
import time # Needed for logout delay

# --- Configuration ---
BACKEND_URL = "https://salestroopz-backendpython-m-uvicorn-app.onrender.com" # Replace if needed
LOGIN_ENDPOINT = f"{BACKEND_URL}/api/v1/auth/token"
REGISTER_ENDPOINT = f"{BACKEND_URL}/api/v1/auth/register" # <--- Add Register Endpoint
LEADS_ENDPOINT = f"{BACKEND_URL}/api/v1/leads"

# --- Authentication Functions ---

def login_user(email, password) -> Optional[str]:
    """Attempts to log in user via API, returns token string or None."""
    try:
        response = requests.post(
            LOGIN_ENDPOINT,
            data={"username": email, "password": password}, # Form data
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15
        )
        response.raise_for_status()
        token_data = response.json()
        return token_data.get("access_token")
    # ... (keep existing error handling for login) ...
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401: st.error("Login failed: Incorrect email or password.")
        else:
            error_detail = f"Login failed: HTTP {http_err.response.status_code}";
            try: error_detail += f" - {http_err.response.json().get('detail', '')}"
            except: pass; st.error(error_detail)
        return None
    except requests.exceptions.RequestException as req_err: st.error(f"Login failed: Connection error - {req_err}"); return None
    except Exception as e: st.error(f"Login failed: An unexpected error occurred - {e}"); return None


# --- NEW Registration Function ---
def register_user(org_name, email, password) -> bool:
    """Attempts to register user via API, returns True on success."""
    payload = {
        "email": email,
        "password": password,
        "organization_name": org_name
    }
    try:
        response = requests.post(REGISTER_ENDPOINT, json=payload, timeout=15) # Send JSON payload
        # Check for successful creation (201) or potential conflicts (400/409)
        if response.status_code == 201:
            st.success("Registration successful! Please log in.")
            return True
        else:
            # Show specific error from API if possible
            error_detail = f"Registration failed: {response.status_code}"
            try: error_detail += f" - {response.json().get('detail', 'Unknown error')}"
            except: pass # Ignore if response isn't JSON
            st.error(error_detail)
            return False
    except requests.exceptions.RequestException as e:
        st.error(f"Registration failed: Connection error - {e}")
        return False
    except Exception as e:
         st.error(f"Registration failed: An unexpected error occurred - {e}")
         return False


def logout_user():
    """Clears authentication state."""
    # ... (Keep existing logout implementation) ...
    keys_to_delete = ['auth_token', 'authenticated', 'user_email', 'view'] # Clear view state too
    for key in keys_to_delete:
        if key in st.session_state: del st.session_state[key]
    st.success("Logged out successfully."); time.sleep(0.5); st.rerun()

# --- API Helper Function ---
def get_authenticated_request(endpoint: str, token: str) -> Optional[Dict[str, Any]]:
    # ... (Keep existing implementation) ...
    pass

# --- Main App Logic ---

# Initialize session state keys
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "auth_token" not in st.session_state: st.session_state["auth_token"] = None
if "user_email" not in st.session_state: st.session_state["user_email"] = None
if "view" not in st.session_state: st.session_state["view"] = "Login" # Default view


st.set_page_config(page_title="SalesTroopz", layout="wide")

# --- Authentication Section (Login / Sign Up) ---
if not st.session_state["authenticated"]:

    # View selection logic
    if st.session_state["view"] == "Login":
        st.title("SalesTroopz Login")
        st.markdown("Please log in to access the platform.")

        with st.form("login_form"):
            email = st.text_input("Email", key="login_email_input") # Unique key
            password = st.text_input("Password", type="password", key="login_password_input") # Unique key
            submitted = st.form_submit_button("Login")

            if submitted:
                if not email or not password:
                    st.warning("Please enter both email and password.")
                else:
                    with st.spinner("Attempting login..."):
                        token = login_user(email, password)
                    if token:
                        st.session_state["authenticated"] = True
                        st.session_state["auth_token"] = token
                        st.session_state["user_email"] = email
                        st.success("Login Successful!")
                        st.rerun() # Refresh to show main app

        st.divider()
        st.markdown("Don't have an account?")
        if st.button("Sign Up Here", key="go_to_signup"):
            st.session_state["view"] = "Sign Up"
            st.rerun() # Switch view

    elif st.session_state["view"] == "Sign Up":
        st.title("Create Your SalesTroopz Account")

        with st.form("signup_form"):
            org_name = st.text_input("Organization Name", key="signup_org")
            email = st.text_input("Email Address", key="signup_email")
            password = st.text_input("Create Password", type="password", key="signup_pw1")
            confirm_password = st.text_input("Confirm Password", type="password", key="signup_pw2")
            submitted = st.form_submit_button("Sign Up")

            if submitted:
                if not all([org_name, email, password, confirm_password]):
                    st.warning("Please fill in all fields.")
                elif password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    # Call the registration helper function
                    with st.spinner("Creating account..."):
                        success = register_user(org_name, email, password)
                    if success:
                        # The success message and switch to login view
                        # is handled inside register_user after successful API call
                        # We just need to ensure the state is updated for the next rerun
                        st.session_state['view'] = 'Login' # Set state back to login
                        # The rerun inside register_user will handle the display change
                        pass # No explicit rerun needed here if register_user does it

        st.divider()
        st.markdown("Already have an account?")
        if st.button("Login Here", key="go_to_login"):
            st.session_state["view"] = "Login"
            st.rerun() # Switch view

# --- Main Application Logic (Shown Only After Login) ---
else:
    # --- Sidebar Navigation ---
    with st.sidebar:
        st.title("SalesTroopz")
        st.write(f"User: {st.session_state.get('user_email', 'N/A')}")
        # st.write(f"Org: {st.session_state.get('user_org_name', 'N/A')}") # Add when user details are fetched
        st.divider()

        # Page selection
        page = st.radio(...) # Keep your page navigation
        st.divider()
        if st.button("Logout"):
            logout_user()

    # --- Page Content ---
    # ... (Keep your existing page content logic for Dashboard, Leads, etc.) ...
    if page == "Dashboard":
        st.header("Dashboard")
        # ...
    # ... etc ...
