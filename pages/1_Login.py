# pages/1_Login.py
import streamlit as st
import requests
import os
import time # For simulated delays or toasts
from typing import Optional, Dict 

# --- Configuration & Constants ---
# It's good practice to get this from st.secrets or a shared config module
BACKEND_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000") # Default for local if not set
LOGIN_ENDPOINT = f"{BACKEND_URL}/api/v1/auth/token"

# --- Page specific title (optional, Streamlit uses filename by default) ---
# st.title("🔑 User Login") # You can set a title if you want it different from "Login"

def login_user_api(email, password) -> Optional[str]:
    """Attempts to log in the user via the backend API."""
    try:
        response = requests.post(
            LOGIN_ENDPOINT,
            data={"username": email, "password": password}, # FastAPI's OAuth2PasswordRequestForm expects form data
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15 # Reasonable timeout for login
        )
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get("access_token")
            if not access_token:
                st.error("Login failed: No access token received from server.")
                return None
            return access_token
        elif response.status_code == 401: # Unauthorized by FastAPI due to bad credentials
            st.error("Login failed: Invalid email or password.")
            return None
        else: # Other errors
            error_detail = "Unknown error"
            try:
                error_detail = response.json().get('detail', response.text)
            except requests.exceptions.JSONDecodeError:
                error_detail = response.text
            st.error(f"Login failed (Status {response.status_code}): {error_detail[:200]}")
            return None
    except requests.exceptions.ConnectionError:
        st.error("Login failed: Could not connect to the authentication service. Please try again later.")
        return None
    except requests.exceptions.Timeout:
        st.error("Login failed: The request timed out. Please check your internet connection and try again.")
        return None
    except Exception as e:
        st.error(f"Login failed: An unexpected error occurred - {e}")
        return None

# --- Main Page Logic ---
if st.session_state.get("auth_token"):
    st.success(f"You are already logged in as {st.session_state.user_email}.")
    st.write("Redirecting to your dashboard...")
    time.sleep(1)
    st.switch_page("pages/0_App.py") # Or your main dashboard/app page
else:
    st.header("Welcome Back!")
    st.caption("Please log in to access your SalesTroopz dashboard.")

    with st.form("login_form_page"):
        email = st.text_input("Email", key="login_email_page")
        password = st.text_input("Password", type="password", key="login_password_page")
        submitted = st.form_submit_button("Login", use_container_width=True, type="primary")

        if submitted:
            if not email or not password:
                st.error("Please enter both email and password.")
            else:
                with st.spinner("Logging in..."):
                    token = login_user_api(email, password)
                if token:
                    st.session_state.auth_token = token
                    st.session_state.user_email = email # Store email
                    st.session_state.authenticated = True # You might use this flag
                    st.success("Login successful! Redirecting...")
                    time.sleep(1)
                    st.switch_page("pages/0_App.py") # Navigate to the main app page
                # Errors are handled within login_user_api and displayed using st.error

    st.markdown("---")
    st.write("Don't have an account yet?")
    if st.button("Sign Up Here", key="login_page_signup_button", use_container_width=True):
        st.switch_page("pages/2_Signup.py")
