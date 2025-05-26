# pages/2_Signup.py
import streamlit as st
import requests
import os
import time

# --- Configuration & Constants ---
BACKEND_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")
REGISTER_ENDPOINT = f"{BACKEND_URL}/api/v1/auth/users/" # Assuming this is your user creation endpoint

# --- Page specific title (optional) ---
# st.title("📝 Create Your Account")

def register_user_api(email: str, password: str, full_name: str, organization_name: str) -> bool:
    """Attempts to register a new user via the backend API."""
    payload = {
        "email": email,
        "password": password,
        "full_name": full_name,
        "organization_name": organization_name
    }
    try:
        response = requests.post(REGISTER_ENDPOINT, json=payload, timeout=15)
        if response.status_code == 200 or response.status_code == 201: # User created (201 often preferred)
            st.success("Account created successfully! Please proceed to login.")
            return True
        else:
            error_detail = "Unknown error during registration."
            try:
                error_detail = response.json().get('detail', response.text)
            except requests.exceptions.JSONDecodeError:
                error_detail = response.text
            st.error(f"Registration failed (Status {response.status_code}): {error_detail[:200]}")
            return False
    except requests.exceptions.ConnectionError:
        st.error("Registration failed: Could not connect to the service. Please try again later.")
        return False
    except requests.exceptions.Timeout:
        st.error("Registration failed: The request timed out. Please check your connection and try again.")
        return False
    except Exception as e:
        st.error(f"Registration failed: An unexpected error occurred - {e}")
        return False

# --- Main Page Logic ---
if st.session_state.get("auth_token"):
    st.success(f"You are already logged in as {st.session_state.user_email}.")
    st.write("Redirecting to your dashboard...")
    time.sleep(1)
    st.switch_page("pages/0_App.py")
else:
    st.header("Join SalesTroopz")
    st.caption("Create an account to start automating your sales outreach.")

    with st.form("signup_form_page"):
        full_name = st.text_input("Full Name", key="signup_fullname_page")
        organization_name = st.text_input("Organization Name", key="signup_orgname_page")
        email = st.text_input("Email Address", key="signup_email_page")
        password = st.text_input("Create Password", type="password", key="signup_password_page")
        confirm_password = st.text_input("Confirm Password", type="password", key="signup_confirmpass_page")
        
        submitted = st.form_submit_button("Create Account", use_container_width=True, type="primary")

        if submitted:
            if not all([full_name, organization_name, email, password, confirm_password]):
                st.error("Please fill in all fields.")
            elif password != confirm_password:
                st.error("Passwords do not match.")
            elif len(password) < 8: # Basic password length validation
                st.error("Password must be at least 8 characters long.")
            else:
                with st.spinner("Creating account..."):
                    success = register_user_api(email, password, full_name, organization_name)
                if success:
                    st.info("Please check your email if verification is required, then log in.")
                    time.sleep(2) # Give time to read message
                    st.switch_page("pages/1_Login.py") # Redirect to login after successful signup
                # Errors are handled within register_user_api

    st.markdown("---")
    st.write("Already have an account?")
    if st.button("Login Here", key="signup_page_login_button", use_container_width=True):
        st.switch_page("pages/1_Login.py")
