import streamlit as st
import requests
from typing import Dict, Any # For type hinting

# --- Configuration ---
# Ensure this points to your deployed backend API
BACKEND_URL = "https://salestroopz-backendpython-m-uvicorn-app.onrender.com" # Replace if needed
LOGIN_ENDPOINT = f"{BACKEND_URL}/api/v1/auth/token"
# Add other endpoints as needed later
LEADS_ENDPOINT = f"{BACKEND_URL}/api/v1/leads" # Example

# --- Authentication Functions ---

def login_user(email, password) -> Optional[str]:
    """Attempts to log in user via API, returns token string or None."""
    try:
        response = requests.post(
            LOGIN_ENDPOINT,
            # IMPORTANT: OAuth2PasswordRequestForm expects form data, not JSON
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15 # Add timeout
        )
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        token_data = response.json()
        return token_data.get("access_token")
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401:
            st.error("Login failed: Incorrect email or password.")
        else:
            # Try to get detail from response
            error_detail = f"Login failed: HTTP {http_err.response.status_code}"
            try: error_detail += f" - {http_err.response.json().get('detail', '')}"
            except: pass
            st.error(error_detail)
        return None
    except requests.exceptions.RequestException as req_err:
        st.error(f"Login failed: Connection error - {req_err}")
        return None
    except Exception as e:
        st.error(f"Login failed: An unexpected error occurred - {e}")
        return None

def logout_user():
    """Clears authentication state."""
    keys_to_delete = ['auth_token', 'authenticated', 'user_email', 'user_org_id', 'user_org_name']
    for key in keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]
    st.success("Logged out successfully.")
    # Use rerun to immediately show the logged-out state (login form)
    # Add a small delay if needed for user to see the success message
    time.sleep(0.5)
    st.rerun()

# --- API Helper Function (Example for authenticated requests) ---
def get_authenticated_request(endpoint: str, token: str) -> Optional[Dict[str, Any]]:
    """Makes a GET request with the authentication token."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(endpoint, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401:
             st.error("Authentication failed or session expired. Please log in again.")
             # Log out the user if token is invalid
             logout_user()
        else:
            st.error(f"Error fetching data: HTTP {http_err.response.status_code}")
        return None
    except requests.exceptions.RequestException as req_err:
        st.error(f"Error fetching data: Connection error - {req_err}")
        return None
    except Exception as e:
         st.error(f"An unexpected error occurred fetching data: {e}")
         return None


# --- Main App Logic ---

# Initialize session state keys if they don't exist
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "auth_token" not in st.session_state:
    st.session_state["auth_token"] = None
# Add others as needed later: user_email, user_org_id, user_org_name

st.set_page_config(page_title="SalesTroopz", layout="wide") # Use wide layout

# --- Login Page Logic ---
if not st.session_state["authenticated"]:
    st.title("SalesTroopz Login")
    st.markdown("Please log in to access the platform.")

    with st.form("login_form"):
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
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
                    st.session_state["user_email"] = email # Store email for display if needed
                    # TODO: Ideally, fetch user details after login to store org_id/name
                    # user_details = get_authenticated_request(f"{BACKEND_URL}/api/v1/users/me", token) # Need a /users/me endpoint
                    # if user_details:
                    #    st.session_state["user_org_id"] = user_details.get("organization_id")
                    #    st.session_state["user_org_name"] = user_details.get("organization_name")
                    st.success("Login Successful!")
                    # Rerun to hide login form and show main app
                    st.rerun()
                # Error messages are handled within login_user

# --- Main Application Logic (Shown Only After Login) ---
else:
    # --- Sidebar Navigation ---
    with st.sidebar:
        st.title("SalesTroopz")
        st.write(f"Logged in as: {st.session_state.get('user_email', 'Unknown User')}")
        st.divider()

        # TODO: Implement actual page navigation using st.radio or other methods
        page = st.radio(
            "Navigate",
            ["Dashboard", "Leads", "Campaigns", "Setup Assistant", "Configuration", "---"], # Add separator
            index=0 # Default to Dashboard
        )
        st.divider()
        if st.button("Logout"):
            logout_user()

    # --- Page Content ---
    if page == "Dashboard":
        st.header("Dashboard")
        st.write("Welcome to SalesTroopz!")
        st.info("Dashboard widgets and stats coming soon.")
        # Example: Button to test fetching leads
        if st.button("Fetch My Leads (Test)"):
            with st.spinner("Fetching leads..."):
                leads_data = get_authenticated_request(LEADS_ENDPOINT, st.session_state["auth_token"])
            if leads_data:
                st.success(f"Fetched {len(leads_data)} leads.")
                st.dataframe(leads_data)
            # Errors handled by get_authenticated_request

    elif page == "Leads":
        st.header("Leads Management")
        st.info("Lead table, filtering, and actions coming soon.")
        # TODO: Implement lead display table using get_authenticated_request

    elif page == "Campaigns":
        st.header("Campaign Management")
        st.info("Campaign/Step definition and monitoring coming soon.")
        # TODO: Implement campaign UI

    elif page == "Setup Assistant":
        st.header("Setup Assistant (Chatbot)")
        st.info("Chatbot interface integration coming soon.")
        # TODO: Integrate chatbot_ui.py logic here or as a separate page function

    elif page == "Configuration":
        st.header("Configuration")
        st.info("Settings for ICP, Offerings, Email Sending coming soon.")
        # TODO: Implement configuration UI sections

    # Handle the separator or potential future pages
    elif page == "---":
        st.sidebar.info("More features coming soon!")
    else:
        st.error("Page not found.")
