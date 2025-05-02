import os
import psycopg2
import ssl
from streamlit.web import cli as stcli

# streamlit_app.py

import streamlit as st
import requests
from typing import Dict, Any, Optional, List # Ensure List is imported if needed elsewhere
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
# CAMPAIGNS_ENDPOINT = f"{BACKEND_URL}/api/v1/campaigns" # Add campaigns endpoint later

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
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401:
             st.error("Authentication failed or session expired. Please log in again.")
             logout_user()
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
        # Success message moved to the specific helper (save_icp_data) for context
        # st.success("Data saved successfully!")
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
    success = put_authenticated_request(ICP_ENDPOINT, token, icp_input_dict)
    if success:
        st.success("ICP definition saved successfully!") # Show success here
    # Error shown by put_authenticated_request
    return success

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
                 # st.write("DEBUG: Login Form Submitted!") # Optional debug

                 if not email or not password:
                     st.warning("Please enter both email and password.")
                 else:
                     with st.spinner("Attempting login..."):
                         token = login_user(email, password)
                     if token:
                         st.session_state["authenticated"] = True
                         st.session_state["auth_token"] = token
                         st.session_state["user_email"] = email
                         st.session_state['icp_data'] = None # Clear ICP cache on new login
                         # Don't show success here, rerun will show main app
                         time.sleep(0.5) # Brief pause before rerun
                         st.rerun()

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
                 # st.write("DEBUG: Signup Form Submitted!") # Optional debug
                 if not all([org_name, email, password, confirm_password]):
                     st.warning("Please fill in all fields.")
                 elif password != confirm_password:
                     st.error("Passwords do not match.")
                 else:
                     with st.spinner("Creating account..."):
                         success = register_user(org_name, email, password)
                     if success:
                         st.session_state['view'] = 'Login'
                         time.sleep(2) # Time to read success message
                         st.rerun()

        st.divider(); st.markdown("Already have an account?")
        if st.button("Login Here", key="go_to_login"):
            st.session_state["view"] = "Login"; st.rerun()

# --- Main Application Logic (Shown Only After Login) ---
else:
    auth_token = st.session_state.get("auth_token")
    if not auth_token:
        st.warning("Authentication token missing. Logging out."); logout_user(); st.stop()

    # --- Sidebar ---
    with st.sidebar:
        st.title("SalesTroopz")
        st.write(f"User: {st.session_state.get('user_email', 'N/A')}")
        # TODO: Fetch and display Org Name
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
        # Example button - replace with actual dashboard content
        if st.button("Fetch My Leads (Test)"):
            with st.spinner("Fetching leads..."):
                leads_data = get_authenticated_request(LEADS_ENDPOINT, auth_token)
            if leads_data is not None:
                st.success(f"Fetched {len(leads_data)} leads.")
                st.dataframe(leads_data)
            # Handle case where leads_data is None (error occurred) if needed

    elif page == "Leads":
        st.header("Leads Management")
        st.info("Lead table and management features coming soon.") # Placeholder
    elif page == "Campaigns":
        st.header("Campaign Management")
        st.info("Campaign creation, step definition, and monitoring coming soon.") # Placeholder
    elif page == "Setup Assistant":
        st.header("Setup Assistant (Chatbot)")
        st.info("Chatbot integration for guided setup coming soon.") # Placeholder
    elif page == "Configuration":
        st.header("⚙️ Configuration")
        tab1, tab2, tab3 = st.tabs(["🎯 ICP Definition", "💡 Offerings", "📧 Email Sending"])

        # --- ICP Definition Tab ---
      with tab1:
            st.subheader("Ideal Customer Profile (ICP)")

            # --- Display Success Message (if applicable) ---
            if st.session_state.get('icp_save_success', False):
                st.success("✅ ICP Definition saved successfully!")
                del st.session_state['icp_save_success'] # Clear the flag

            # Load data only if not already in state
            if st.session_state.get('icp_data_loaded', False) is False:
                 with st.spinner("Loading ICP data..."):
                     fetched_icp = get_icp_data(auth_token)
                     st.session_state['icp_data'] = fetched_icp if fetched_icp is not None else {}
                     st.session_state['icp_data_loaded'] = True

            # Get current data from session state
            current_icp = st.session_state.get('icp_data', {})

   # ==========================================
            # NEW: Display Current ICP Definition
            # ==========================================
            if current_icp and current_icp.get("name"): # Only display if data exists and has a name
                st.markdown("---") # Divider
                st.markdown("#### Currently Saved ICP:")
                with st.container(border=True):
                    st.markdown(f"**Name:** {current_icp.get('name', 'N/A')}")

                    # Display Keywords nicely
                    st.markdown("##### Titles/Keywords:")
                    title_kws = current_icp.get('title_keywords', [])
                    if title_kws:
                        st.markdown("\n".join([f"- `{kw}`" for kw in title_kws]))
                    else:
                        st.caption("None specified.")

                    st.markdown("##### Industries/Keywords:")
                    industry_kws = current_icp.get('industry_keywords', [])
                    if industry_kws:
                         st.markdown("\n".join([f"- `{kw}`" for kw in industry_kws]))
                    else:
                        st.caption("None specified.")

                    st.markdown("##### Locations/Keywords:")
                    location_kws = current_icp.get('location_keywords', [])
                    if location_kws:
                         st.markdown("\n".join([f"- `{kw}`" for kw in location_kws]))
                    else:
                        st.caption("None specified.")

                    # Display Company Size nicely
                    st.markdown("##### Company Size:")
                    size_rules = current_icp.get('company_size_rules', {})
                    min_size = size_rules.get('min') if isinstance(size_rules, dict) else None
                    max_size = size_rules.get('max') if isinstance(size_rules, dict) else None

                    if min_size is not None and max_size is not None:
                        st.markdown(f"- Min Employees: `{min_size}`")
                        st.markdown(f"- Max Employees: `{max_size}`")
                    elif min_size is not None:
                        st.markdown(f"- Min Employees: `{min_size}`")
                        st.markdown(f"- Max Employees: Not specified")
                    elif max_size is not None:
                        st.markdown(f"- Min Employees: Not specified")
                        st.markdown(f"- Max Employees: `{max_size}`")
                    else:
                        st.caption("Any size.")

            else: # Handle case where no ICP is saved yet
                 if st.session_state.get('icp_data_loaded'): # Only show if loading finished
                      st.info("No ICP definition found. Please create one using the form below.")

            st.markdown("---") # Divider
            st.markdown("#### Edit ICP Definition:")
          
                # --- ICP Form ---
            with st.form("icp_form"):
                # Input fields populated from current_icp data
                st.text_input(
                    "ICP Name:",
                    value=current_icp.get("name", "Default ICP"),
                    key="icp_name",
                    help="Give your ICP a recognizable name."
                )
                st.text_area(
                    "Titles/Keywords (one per line):",
                    value="\n".join(current_icp.get("title_keywords", [])),
                    key="icp_titles", height=100,
                    help="Enter job titles or role keywords (e.g., VP of Sales, Marketing Manager, Founder)."
                )
                st.text_area(
                    "Industries/Keywords (one per line):",
                    value="\n".join(current_icp.get("industry_keywords", [])),
                    key="icp_industries", height=100,
                    help="Enter target industries (e.g., SaaS, E-commerce, Financial Services)."
                )
                st.text_area(
                    "Locations/Keywords (one per line):",
                    value="\n".join(current_icp.get("location_keywords", [])),
                    key="icp_locations", height=100,
                    help="Enter target geographic locations (e.g., California, London, United States)."
                )

                st.divider()
                st.markdown("**Company Size**")

                # Extract current min/max from the loaded data for the form
                current_size_rules_for_form = current_icp.get("company_size_rules", {})
                current_min_size_form = None
                current_max_size_form = None
                if isinstance(current_size_rules_for_form, dict):
                    current_min_size_form = current_size_rules_for_form.get("min")
                    current_max_size_form = current_size_rules_for_form.get("max")
                try: current_min_size_form = int(current_min_size_form) if current_min_size_form is not None else None
                except (ValueError, TypeError): current_min_size_form = None
                try: current_max_size_form = int(current_max_size_form) if current_max_size_form is not None else None
                except (ValueError, TypeError): current_max_size_form = None


                col_min, col_max = st.columns(2)
                with col_min:
                    min_size_input = st.number_input( # Renamed variable to avoid conflict
                        "Min Employees:",
                        min_value=1,
                        value=current_min_size_form,
                        step=1,
                        format="%d",
                        key="icp_min_size",
                        help="Minimum number of employees (inclusive). Leave blank if no minimum."
                    )
                with col_max:
                    max_size_input = st.number_input( # Renamed variable to avoid conflict
                        "Max Employees:",
                        min_value=1,
                        value=current_max_size_form,
                        step=1,
                        format="%d",
                        key="icp_max_size",
                        help="Maximum number of employees (inclusive). Leave blank if no maximum."
                    )

                # Display warning directly in form if min > max
                min_val_check = st.session_state.icp_min_size
                max_val_check = st.session_state.icp_max_size
                min_int_check = int(min_val_check) if min_val_check is not None else None
                max_int_check = int(max_val_check) if max_val_check is not None else None
                if min_int_check is not None and max_int_check is not None and min_int_check > max_int_check:
                    st.warning("Minimum size cannot be greater than maximum size.", icon="⚠️")

                st.divider()

                # Form submission button
                submitted = st.form_submit_button("💾 Save ICP Definition")

                if submitted:
                    can_save = True # Flag to control saving

                    # Basic Validation
                    icp_name = st.session_state.icp_name.strip()
                    if not icp_name:
                        st.error("ICP Name cannot be empty.")
                        can_save = False

                    # Data Processing
                    title_kws = [kw.strip() for kw in st.session_state.icp_titles.split('\n') if kw.strip()]
                    industry_kws = [kw.strip() for kw in st.session_state.icp_industries.split('\n') if kw.strip()]
                    location_kws = [kw.strip() for kw in st.session_state.icp_locations.split('\n') if kw.strip()]

                    # Process Company Size Inputs
                    size_rules_payload = {}
                    # Use the check variables calculated above for validation display
                    if min_int_check is not None and max_int_check is not None and min_int_check > max_int_check:
                         st.error("Minimum company size cannot be greater than maximum size. Please correct.")
                         can_save = False
                    else:
                         if min_int_check is not None: size_rules_payload["min"] = min_int_check
                         if max_int_check is not None: size_rules_payload["max"] = max_int_check

                    # API Call
                    if can_save:
                        icp_payload = {
                            "name": icp_name, "title_keywords": title_kws, "industry_keywords": industry_kws,
                            "location_keywords": location_kws, "company_size_rules": size_rules_payload if size_rules_payload else None
                        }
                        with st.spinner("Saving ICP definition..."):
                            success = save_icp_data(icp_payload, auth_token)
                        if success:
                            st.session_state['icp_save_success'] = True
                            st.session_state['icp_data_loaded'] = False
                            st.rerun()
                        # Errors handled in save_icp_data

                   
        # --- Offerings Tab ---
        with tab2:
            st.subheader("💡 Offerings")
            st.info("Offering management UI coming soon.") # Placeholder

        # --- Email Sending Tab ---
        with tab3:
            st.subheader("📧 Email Sending Configuration")
            st.info("Email setup UI coming soon.") # Placeholder

    else:
        st.error("Page not found.")
