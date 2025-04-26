# streamlit_app.py

import streamlit as st
import requests
from typing import Dict, Any, Optional
import time
import json # Import json for ICP form

# --- Configuration ---
# Ensure this points to your deployed backend API
BACKEND_URL = "https://salestroopz-backendpython-m-uvicorn-app.onrender.com" # Replace if needed
LOGIN_ENDPOINT = f"{BACKEND_URL}/api/v1/auth/token"
REGISTER_ENDPOINT = f"{BACKEND_URL}/api/v1/auth/register"
LEADS_ENDPOINT = f"{BACKEND_URL}/api/v1/leads"
ICP_ENDPOINT = f"{BACKEND_URL}/api/v1/icp"
OFFERINGS_ENDPOINT = f"{BACKEND_URL}/api/v1/offerings" # Add offerings endpoint
CAMPAIGNS_ENDPOINT = f"{BACKEND_URL}/api/v1/campaigns" # Add campaigns endpoint

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
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401: st.error("Login failed: Incorrect email or password.")
        else:
            error_detail = f"Login failed: HTTP {http_err.response.status_code}"
            try: error_detail += f" - {http_err.response.json().get('detail', '')}"
            except: pass
            st.error(error_detail)
        return None
    except requests.exceptions.RequestException as req_err: st.error(f"Login failed: Connection error - {req_err}"); return None
    except Exception as e: st.error(f"Login failed: An unexpected error occurred - {e}"); return None

def register_user(org_name, email, password) -> bool:
    """Attempts to register user via API, returns True on success."""
    payload = {"email": email, "password": password, "organization_name": org_name}
    try:
        response = requests.post(REGISTER_ENDPOINT, json=payload, timeout=15)
        if response.status_code == 201:
            st.success("Registration successful! Please log in.")
            return True
        else:
            error_detail = f"Registration failed: {response.status_code}"
            try: error_detail += f" - {response.json().get('detail', 'Unknown error')}"
            except: pass
            st.error(error_detail)
            return False
    except requests.exceptions.RequestException as e: st.error(f"Registration failed: Connection error - {e}"); return False
    except Exception as e: st.error(f"Registration failed: An unexpected error occurred - {e}"); return False

def logout_user():
    """Clears authentication state."""
    keys_to_delete = ['auth_token', 'authenticated', 'user_email', 'view', 'icp_data', '_processed_upload'] # Clear relevant states
    for key in keys_to_delete:
        if key in st.session_state: del st.session_state[key]
    st.success("Logged out successfully."); time.sleep(0.5); st.rerun()

Okay, here is the complete `streamlit_app.py` code with the corrected indentation within the login form, the debug print added, and the actual state update logic restored on successful login.

```python
# streamlit_app.py

import streamlit as st
import requests
from typing import Dict, Any, Optional
import time
import json # Import json for ICP form

# --- Configuration ---
BACKEND_URL = "https://salestroopz-backendpython-m-uvicorn-app.onrender.com" # Replace if needed
LOGIN_ENDPOINT = f"{BACKEND_URL}/api/v1/auth/token"
REGISTER_ENDPOINT = f"{BACKEND_URL}/api/v1/auth/register"
LEADS_ENDPOINT = f"{BACKEND_URL}/api/v1/leads"
ICP_ENDPOINT = f"{BACKEND_URL}/api/v1/icp"
# Add endpoints for Offerings and other sections as you build them
OFFERINGS_ENDPOINT = f"{BACKEND_URL}/api/v1/offerings"

# --- Authentication Functions ---

def login_user(email# --- API Helper Functions ---
def get_authenticated_request(endpoint: str, token: str) -> Optional[Dict[str, Any]]:
    """Makes an authenticated GET request, handles common errors, returns JSON dict or None."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(endpoint, headers=headers, timeout=15)
        response.raise_for_status() # Check for 4xx/5xx errors
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401:
             st.error("Authentication failed or session expired. Please log in again.")
             logout_user() # Force logout on 401
        else:
             error_detail = f"Error fetching data ({endpoint}): HTTP {http_err.response.status_code}"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        return None
    except requests.exceptions.RequestException as req_err: st.error(f"Error fetching data ({endpoint}): Connection error - {req_err}"); return None
    except Exception as e: st.error(f"An unexpected error occurred fetching data ({endpoint}): {e}"); return None

def put_authenticated_request(endpoint: str, token: str, data: Dict[str, Any]) -> bool:
    """Makes an authenticated PUT request, handles errors, returns True on success."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.put(endpoint, headers=headers, json=data, timeout=20)
        response.raise_for_status()
        st.success("Data saved successfully!") # Generic success message
        return True
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401:
             st.error("Authentication failed or session expired. Please log in again."); logout_user()
        else:
             error_detail = f"Failed to save data ({endpoint}): HTTP {http_err.response.status_code}"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        return False
    except requests.exceptions.RequestException as req_err: st.error(f"Failed to save data ({endpoint}): Connection error - {req_err}"); return False
    except Exception as e: st.error(f"Failed to save data ({endpoint}): An unexpected error occurred - {e}"); return False

# --- ICP Specific Helpers ---
def get_icp_data(token: str) -> Optional[Dict[str, Any]]:
    """Fetches the ICP definition for the authenticated user's org."""
    return get_authenticated_request(ICP_ENDPOINT, token)

def save_icp_data(icp_input_dict: Dict[str, Any], token: str) -> bool:
    """Saves (Creates/Updates) the ICP definition via PUT request."""
    return put_authenticated_request(ICP_ENDPOINT, token, icp_input_dict)

# --- Main App Logic ---

# Initialize session state keys
if "authenticated" not in st.session_state: st.session_state["authenticated"] = False
if "auth_token" not in st.session_state: st.session_state["auth_token"] = None
if "user_email" not in st.session_state: st.session_state["user_email"] = None
if "view" not in st.session_state: st.session_state["view"] = "Login"
if 'icp_data' not in st.session_state: st.session_state['icp_data'] = None

st.set_page_config(page_title="SalesTroopz", layout="wide")

# --- Authentication Section (Login / Sign Up) ---
if not st.session_state["authenticated"]:

    # View selection logic
    if st.session_state["view"] == "Login":
        st.title("SalesTroopz Login")
        st.markdown("Please log in to access the platform.")

        with st.form("login_form"):
            email = st.text_input("Email", key="login_email_input")
            password = st.text_input("Password", type="password", key="login_password_input")
            submitted = st.form_submit_button("Login")

            if submitted: # This block executes ONLY when the form is submitted
                st.write("DEBUG: Login Form Submitted!") # <-- DEBUG LINE ADDED

                if not email or not password:
                    st.warning("Please enter both email and password.")
                else:
                    with st.spinner("Attempting login..."):
                        token = login_user(email, password) # Call login function
                    if token:
                        # Store auth state
                        st.session_state["authenticated"] = True
                        st.session_state["auth_token"] = token
                        st.session_state["user_email"] = email
                        
    """Attempts to log in user via API, returns token string or None."""
    try:
        response = requests.post(
            LOGIN_ENDPOINT,
            data={"username": email, "password": password}, # Form data
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15
        )
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        token_data = response.json()
        return token_data.get("access_token")
    except requests.exceptions.HTTPError as http_err:
        # Handle specific 401 Unauthorized error
        if http_err.response.status_code == 401:
            st.error("Login failed: Incorrect email or password.")
        else:
            # Try to get more detail from the response body for other HTTP errors
            error_detail = f"Login failed: HTTP {http_err.response.status_code}"
            try:
                error_detail += f" - {http_err.response.json().get('detail', '(No detail provided)')}"
            except: # Handle cases where response is not JSON
                error_detail += f" - Response: {http_err.response.text[:100]}..." # Show beginning of text response
            st.error(error_detail)
        return None
    except requests.exceptions.RequestException as req_err:
        # Handle connection errors, timeouts, etc.
        st.error(f"Login failed: Connection error - {req_err}")
        return None
    except Exception as e:
        # Catch any other unexpected errors during the login process
        st.error(f"Login failed: An unexpected error occurred - {e}")
        return None

def register_user(org_name, email, password) -> bool:
    """Attempts to register user via API, returns True on success."""
    payload = {
        "email": email,
        "password": password,
        "organization_name": org_name
    }
    try:
        response = requests.post(REGISTER_ENDPOINT, json=payload, timeout=15)
        if response.status_code == 201: # Created successfully
            st.success("Registration successful! Please log in.")
            return True
        else:
            # Show specific error from API response if possible
            error_detail = f"Registration failed: {response.status_code}"
            try:
                error_detail += f" - {response.json().get('detail', 'Unknown error')}"
            except: pass
            st.error(error_detail)
            return False
    except requests.exceptions.RequestException as e:
        st.error(f"Registration failed: Connection error - {e}")
        return False
    except Exception as e:
         st.error(f"Registration failed: An unexpected error occurred - {e}")
         return False

def logout_user():
    """Clears authentication state and reruns the app."""
    keys_to_delete = ['auth_token', 'authenticated', 'user_email', 'view', 'icp_data'] # Clear relevant state
    for key in keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]
    # Set view back to login explicitly before success message
    st.session_state['view'] = 'Login'
    st.success("Logged out successfully.")
    time.sleep(1) # Pause briefly so user sees message
    st.rerun() # Rerun to show the login page

# --- API Helper Functions ---
def get_authenticated_request(endpoint: str, token: str, params: Optional[Dict] = None) -> Optional[Any]:
    """Makes an authenticated GET request, returns JSON response data or None on error."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.get(endpoint, headers=headers, params=params, timeout=15)
        response.raise_for_status() # Raise HTTPError for bad responses
        return response.json() # Return parsed JSON
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401:
             st.error("Authentication failed or session expired. Please log in again.")
             logout_user() # Force logout on 401
        else:
            error_detail = f"Error fetching data: HTTP {http_err.response.status_code}"
            try: error_detail += f" - {http_err.response.json().get('detail', '')view") = "Login" # Ensure view is reset
                        st.session_state['icp_data'] = None # Clear ICP cache on new login
                        st.success("Login Successful!")
                        time.sleep(1) # Brief pause
                        st.rerun() # Refresh page to show main app view
                    # Else: login_user function displays the error via st.error

        st.divider()
        st.markdown("Don't have an account?")
        if st.button("Sign Up Here", key="go_to_signup"):
            st.session_state["view"] = "Sign Up"
            st.rerun()

    elif st.session_state["view"] == "Sign Up":
        st.title("Create Your SalesTroopz Account")
        with st.form("signup_form"):
            org_name = st.text_input("Organization Name", key="signup_org")
            email = st.text_input("Email Address", key="signup_email")
            password = st.text_input("Create Password", type="password", key="signup_pw1")
            confirm_password = st.text_input("Confirm Password", type="password", key="signup_pw2")
            submitted = st.form_submit_button("Sign Up")

            if submitted:
                st.write("DEBUG: Signup Form Submitted!") # Debug

                if not all([org_name, email, password, confirm_password]):
                    st.warning("Please fill in all fields.")
                elif password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    with st.spinner("Creating account..."):
                        success = register_user(org_name, email, password)
                    if success:
                        # Switch view back to login after successful registration
                        st.session_state['view'] = 'Login'
                        # Brief pause needed to see success message before rerun potentially hides it
                        time.sleep(2)
                        st.rerun()
                    # Else: register_user function displays the error

        st.divider()
        st.markdown("Already have an account?")
        if st.button("Login Here", key="go_to_login"):
            st.session_state["view"] = "Login"
            st.rerun()

# --- Main Application Logic (Shown Only After Login) ---
else:
    auth_token = st.session_state.get("auth_token")
    if not auth_token:
        st.warning("Authentication token missing. Logging out.")
        logout_user(); st.stop()

    # --- Sidebar ---
    with st.sidebar:
        st.title("SalesTroopz")
        st.write(f"User: {st.session_state.get('user_email', 'N/A')}")
        st.divider()
        page = st.radio(
            "Navigate",
            ["Dashboard", "Leads", "Campaigns", "Setup Assistant", "Configuration"],
            key="nav_radio"
        )
        st.divider()
        if st.button("Logout"): logout_user()

    # --- Main Area Page Content ---
    if page == "Dashboard":
        st.header("Dashboard")
        st.write("Welcome to SalesTroopz!")
        if st.button("Fetch My Leads (Test)"):
            with st.spinner("Fetching leads..."): leads_data = get_authenticated_request(LEADS_ENDPOINT, auth_token)
            if leads_data is not None: st.success(f"Fetched {len(leads_data)} leads."); st.dataframe(leads_data)

    elif page == "Leads":
        st.header("Leads Management"); st.info("Lead table coming soon.")
    elif page == "Campaigns":
        st.header("Campaign Management"); st.info("Campaign/Step definition coming soon.")
    elif page == "Setup Assistant":
        st.header("Setup Assistant (Chatbot)"); st.info("Chatbot integration coming soon.")
    elif page == "Configuration":
        st.header("⚙️ Configuration")
        tab1, tab2, tab3 = st.tabs(["🎯 ICP Definition", "💡 Offerings", "📧 Email Sending"])

        with tab1: # ICP Definition Tab
            st.subheader("Ideal Customer Profile (ICP)")
            # Load data or initialize empty structure
            if st.session_state.get('icp_data') is None:
                 with st.spinner("Loading ICP data..."): st.session_state['icp_data'] = get_icp_data(auth_token) or {}
            current_icp = st.session_state.get('icp_data', {})

            with st.form("icp_form"):
                # Form fields using values from current_icp dict
                st.text_input("ICP Name:", value=current_icp.get("name", "Default ICP"), key="icp_name")
                st.text_area("Titles/Keywords (one per line):", value="\n".join(current_icp.get("title_keywords", [])), key="icp_titles", height=100)
                st.text_area("Industries/Keywords (one per line):", value="\n".join(current_icp.get("industry_keywords", [])), key="icp_industries", height=100)
                st.text_area("Locations/Keywords (one per line):", value="\n".join(current_icp.get("location_keywords", [])), key="icp_locations", height=100)
                st.text_input("Company Size Rules (JSON Text):", value=json.dumps(current_icp.get("company_size_rules", {})), key="icp_size_rules_text")

                submitted = st.form_submit_button("Save ICP Definition")
                if submitted:
                    st.write("DEBUG: ICP Form Submitted!") # Debug
                    # Process form data into payload dict
                    title_kws = [kw.strip() for kw in st.session_state.icp_titles.split('\n') if kw.strip()]
                    industry_kws = [kw.strip() for kw in st.session_state.icp_industries.split('\n') if kw.strip()]
                    location_kws = [kw.strip() for kw in st.session_state.icp_locations.split('\n') if kw.strip()]
                    size_rules_dict = {}; error_parsing_json = False
                    try:
                        parsed = json.loads(st.session_state.icp_size_rules_text or '{}'); size_rules_dict = parsed if isinstance(parsed, dict) else {}
                    except json.JSONDecodeError: st.warning("Invalid JSON for Company Size Rules. Saving as empty."); error_parsing_json = True

                    if not error_parsing_json: # Only save if JSON was valid or empty
                        icp_payload = { "name": st.session_state.icp_name, "title_keywords": title_kws, "industry_keywords": industry_kws, "location_keywords": location_kws, "company_size_rules": size_rules_dict }
                        with st.spinner("Saving ICP..."): success = save_icp_data(icp_payload, auth_token}"
            except: pass
            st.error(error_detail)
        return None
    except requests.exceptions.RequestException as req_err:
        st.error(f"Error fetching data: Connection error - {req_err}")
        return None
    except Exception as e:
         st.error(f"An unexpected error occurred fetching data: {e}")
         return None

def save_icp_data(icp_input_dict: Dict[str, Any], token: str) -> bool:
    """Saves (Creates/Updates) the ICP definition via PUT request."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.put(ICP_ENDPOINT, headers=headers, json=icp_input_dict, timeout=20)
        response.raise_for_status()
        st.success("ICP definition saved successfully!")
        return True
    except requests.exceptions.HTTPError as http_err:
        error_detail = f"Failed to save ICP: HTTP {http_err.response.status_code}"
        try: error_detail += f" - {http_err.response.json().get('detail', '')}"
        except: pass
        st.error(error_detail)
        return False
    except requests.exceptions.RequestException as req_err: st.error(f"Failed to save ICP: Connection error - {req_err}"); return False
    except Exception as e: st.error(f"Failed to save ICP: An unexpected error occurred - {e}"); return False

# --- Main App Logic ---

# Initialize session state keys only if they don't exist
st.session_state.setdefault("authenticated", False)
st.session_state.setdefault("auth_token", None)
st.session_state.setdefault("user_email", None)
st.session_state.setdefault("view", "Login")
st.session_state.setdefault("icp_data", None) # Use None initially, fetch on demand

st.set_page_config(page_title="SalesTroopz", layout="wide")

# --- Authentication Section (Login / Sign Up) ---
if not st.session_state["authenticated"]:

    # --- Login View ---
    if st.session_state["view"] == "Login":
        st.title("SalesTroopz Login")
        st.markdown("Please log in to access the platform.")

        with st.form("login_form"):
             email = st.text_input("Email", key="login_email_input")
             password = st.text_input("Password", type="password", key="login_password_input")
             submitted = st.form_submit_button("Login")

             if submitted:
                 # Correct Indentation
                 st.write("DEBUG: Login Form Submitted!") # Keep for debugging if needed

                 # Correct Indentation
                 if not email or not password:
                     # Indent further
                     st.warning("Please enter both email and password.")
                 # Correct Indentation
                 else:
                     # Indent further
                     with st.spinner("Attempting login..."):
                         token = login_user(email, password)
                     # Indent further
                     if token:
                         # Indent even further
                         st.session_state["authenticated"] = True
                         st.session_state["auth_token"] = token
                         st.session_state["user_email"] = email
                         st.session_state['icp_data'] = None # Clear ICP cache on new login
                         st.success("Login Successful!")
                         time.sleep(1) # Brief pause
                         st.rerun() # Refresh to show main app

        # Switch to Sign Up (Correctly indented relative to 'if view == "Login"')
        st.divider(); st.markdown("Don't have an account?")
        if st.button("Sign Up Here", key="go_to_signup"):
            st.session_state["view"] = "Sign Up"; st.rerun()

    # --- Sign Up View ---
    elif st.session_state["view"] == "Sign Up":
        st.title("Create Your SalesTroopz Account")

        with st.form("signup_form"):
             org_name = st.text_input("Organization Name", key="signup_org")
             email = st.text_input("Email Address", key="signup_email")
             password = st.text_input("Create Password", type="password", key="signup_pw1")
             confirm_password = st.text_input("Confirm Password", type="password", key="signup_pw2")
             submitted = st.form_submit_button("Sign Up")

             if submitted:
                 # Correct Indentation
                 if not all([org_name, email, password, confirm_password]):
                     st.warning("Please fill in all fields.")
                 elif password != confirm_password:
                     st.error("Passwords do not match.")
                 else:
                     with st.spinner("Creating account..."):
                         success = register_user(org_name, email, password)
                     if success:
                         # Registration successful, switch back to login view
                         st.session_state['view'] = 'Login'
                         # Give time to see success message before rerun potentially clears it
                         time.sleep(2)
                         st.rerun() # Rerun to show login form

        # Switch to Login (Correctly indented relative to 'elif view == "Sign Up"')
        st.divider(); st.markdown("Already have an account?")
        if st.button("Login Here", key="go_to_login"):
            st.session_state["view"] = "Login"; st.rerun()

# --- Main Application Logic (Shown Only After Login) ---
else: # Authenticated
    auth_token = st.session_state.get("auth_token")
    if not auth_token: # Safety check
        st.warning("Authentication token missing. Logging out.")
        logout_user(); st.stop()

    # --- Sidebar ---
    with st.sidebar:
        st.title("SalesTroopz")
        st.write(f"User: {st.session_state.get('user_email', 'N/A')}")
        st.divider()
        page = st.radio(
            "Navigate",
            ["Dashboard", "Leads", "Campaigns", "Setup Assistant", "Configuration"],
            key="nav_radio" )
        st.divider()
        if st.button("Logout"): logout_user()

    # --- Page Content ---
    if page == "Dashboard":
        st.header("Dashboard")
        st.write("Welcome to SalesTroopz!")
        st.info("Dashboard widgets and stats coming soon.")
        if st.button("Fetch My Leads (Test)"):
            with st.spinner("Fetching leads..."):
                leads_data = get_authenticated_request(LEADS_ENDPOINT, auth_token)
            if leads_data is not None:
                st.success(f"Fetched {len(leads_data)} leads.")
                st.dataframe(leads_data)

    elif page == "Leads":
        st.header("Leads Management")
        st.info("Lead table, filtering, and actions coming soon.")

    elif page == "Campaigns":
        st.header("Campaign Management")
        st.info("Campaign/Step definition and monitoring coming soon.")

    elif page == "Setup Assistant":
        st.header("Setup Assistant (Chatbot)")
        st.info("Chatbot interface integration coming soon.")

    elif page == "Configuration":
        st.header("⚙️ Configuration")
        tab1, tab2, tab3 = st.tabs(["🎯 ICP Definition", "💡 Offerings", "📧 Email Sending"])

        with tab1:
            st.subheader("Ideal Customer Profile (ICP)")
            # --- ICP Form Logic ---
            # Fetch data only if not already in state
            if st.session_state.get('icp_data') is None:
                 with st.spinner("Loading ICP data..."):
                     fetched_icp = get_icp_data(auth_token)
                     st.session_state['icp_data'] = fetched_icp if fetched_icp else {} # Use empty dict if None

            current_icp = st.session_state.get('icp_data', {}) # Should be a dict now

            with st.form("icp_form"):
                st.text_input("ICP Name:", value=current_icp.get("name", "Default ICP"), key="icp_name")
                st.text_area("Target Titles/Keywords (one per line):", value="\n".join(current_icp.get("title_keywords", [])), key="icp_titles", height=100)
                st.text_area("Target Industries/Keywords (one per line):", value="\n".join(current_icp.get("industry_keywords", [])), key="icp_industries", height=100)
                st.text_area("Target Locations/Keywords (one per line):", value="\n".join(current_icp.get("location_keywords", [])), key="icp_locations", height=100)
                st.)
                        if success: st.session_state['icp_data'] = None; st.rerun() # Clear cache & rerun on success

        with tab2: # Offerings Tab
            st.subheader("Offerings"); st.info("Offering management UI coming soon.")
        with tab3: # Email Sending Tab
            st.subheader("Email Sending Configuration"); st.info("Email setup UI coming soon.")

    else:
        st.error("Page not found.")
