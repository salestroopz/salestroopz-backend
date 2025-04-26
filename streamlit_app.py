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
ICP_ENDPOINT = f"{BACKEND_URL}/api/v1/icp"

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

# --- NEW: GET ICP Data ---
def get_icp_data(token: str) -> Optional[Dict[str, Any]]:
    """Fetches the ICP definition for the authenticated user's org."""
    return get_authenticated_request(ICP_ENDPOINT, token) # Use the generic helper

# --- NEW: Save/Update ICP Data ---
def save_icp_data(icp_input_dict: Dict[str, Any], token: str) -> bool:
    """Saves (Creates/Updates) the ICP definition via PUT request."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.put(ICP_ENDPOINT, headers=headers, json=icp_input_dict, timeout=20)
        response.raise_for_status() # Check for HTTP errors
        st.success("ICP definition saved successfully!")
        return True
    except requests.exceptions.HTTPError as http_err:
        error_detail = f"Failed to save ICP: HTTP {http_err.response.status_code}"
        try: error_detail += f" - {http_err.response.json().get('detail', '')}"
        except: pass
        st.error(error_detail)
        return False
    except requests.exceptions.RequestException as req_err:
        st.error(f"Failed to save ICP: Connection error - {req_err}")
        return False
    except Exception as e:
        st.error(f"Failed to save ICP: An unexpected error occurred - {e}")
        return False

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
elif st.session_state["authenticated"]: # Use elif for clarity
    auth_token = st.session_state.get("auth_token") # Get token once
else:
    # --- Sidebar Navigation ---
    with st.sidebar:
        st.title("SalesTroopz")
        st.write(f"User: {st.session_state.get('user_email', 'N/A')}")
        # st.write(f"Org: {st.session_state.get('user_org_name', 'N/A')}") # Add when user details are fetched
        st.divider()

        page = st.radio(
            "Navigate",
            ["Dashboard", "Leads", "Campaigns", "Setup Assistant", "Configuration"], # Removed separator for now
            key="nav_radio" # Add a key
        )
        st.divider()
        if st.button("Logout"): logout_user()

        # Page selection
        page = st.radio(...) # Keep your page navigation
        st.divider()
        if st.button("Logout"):
            logout_user()

    # --- Page Content ---
    # ... (Keep your existing page content logic for Dashboard, Leads, etc.) ...
    if page == "Dashboard":
        # ... (keep dashboard content) ...
        pass

    elif page == "Leads":
        # ... (keep leads placeholder) ...
        pass

    elif page == "Campaigns":
        # ... (keep campaigns placeholder) ...
        pass

    elif page == "Setup Assistant":
        # ... (keep setup assistant placeholder) ...
        pass
# --- === NEW: Configuration Page Implementation === ---
    elif page == "Configuration":
        st.header("⚙️ Configuration")

        # Use tabs for different configuration sections
        tab1, tab2, tab3 = st.tabs(["🎯 ICP Definition", "💡 Offerings", "📧 Email Sending"])

        with tab1:
            st.subheader("Ideal Customer Profile (ICP)")
            st.markdown("Define the criteria for your ideal customers.")

            # Fetch current ICP data on page load
            # Use a flag in session state to fetch only once per login or refresh
            if 'icp_data' not in st.session_state:
                 with st.spinner("Loading ICP data..."):
                     st.session_state['icp_data'] = get_icp_data(auth_token) if auth_token else None

            current_icp = st.session_state.get('icp_data') # Can be None

            if current_icp is None and auth_token:
                 # Handle case where fetch failed or no ICP exists yet
                 st.info("No ICP defined yet. Use the form below to create one.")
                 # Initialize with empty defaults for the form
                 current_icp = {"name": "Default ICP", "title_keywords": [], "industry_keywords": [], "company_size_rules": {}, "location_keywords": []}
            elif not auth_token:
                 st.error("Cannot load ICP data - not authenticated.")
                 st.stop() # Stop execution for this tab if not authenticated

            # Use a form for editing/saving
            with st.form("icp_form"):
                st.text_input(
                    "ICP Name:",
                    value=current_icp.get("name", "Default ICP"),
                    key="icp_name",
                    help="Give your ICP a descriptive name."
                )

                # Use text_area for keywords, instructing user on format
                st.text_area(
                    "Target Titles/Keywords (one per line):",
                    value="\n".join(current_icp.get("title_keywords", [])), # Display as lines
                    key="icp_titles",
                    height=100,
                    help="Enter job titles or keywords (e.g., VP Marketing, Head of Sales)."
                )
                st.text_area(
                    "Target Industries/Keywords (one per line):",
                    value="\n".join(current_icp.get("industry_keywords", [])),
                    key="icp_industries",
                    height=100,
                    help="Enter target industries (e.g., SaaS, Fintech, E-commerce)."
                )
                st.text_area(
                    "Target Locations/Keywords (one per line):",
                    value="\n".join(current_icp.get("location_keywords", [])),
                    key="icp_locations",
                     height=100,
                    help="Enter target regions, countries, or cities (e.g., North America, UK, London)."
                )

                # Company size needs careful handling depending on stored format
                # Simple approach: Use text input for now, explain format in help text
                # TODO: Improve this with better structured input if needed later
                st.text_input(
                    "Company Size Rules (Text):",
                    # Display stored JSON as string, or empty if not set correctly
                    value=json.dumps(current_icp.get("company_size_rules", {})) if isinstance(current_icp.get("company_size_rules"), dict) else str(current_icp.get("company_size_rules", "")),
                    key="icp_size_rules_text",
                    help='Enter rules as JSON (e.g., {"min": 50, "max": 500}) or specific ranges (e.g., "51-200"). Needs backend parsing.'
                )

                # Add other ICP fields here if needed

                submitted = st.form_submit_button("Save ICP Definition")

                if submitted:
                    # --- Process form data ---
                    # Convert keyword text areas back to lists
                    title_kws = [kw.strip() for kw in st.session_state.icp_titles.split('\n') if kw.strip()]
                    industry_kws = [kw.strip() for kw in st.session_state.icp_industries.split('\n') if kw.strip()]
                    location_kws = [kw.strip() for kw in st.session_state.icp_locations.split('\n') if kw.strip()]

                    # Attempt to parse company size JSON, default to empty dict on error
                    size_rules_dict = {}
                    try:
                        parsed_rules = json.loads(st.session_state.icp_size_rules_text)
                        if isinstance(parsed_rules, dict): # Or check for list if allowing that format
                            size_rules_dict = parsed_rules
                        else: # Store as string if not dict? Or raise validation error?
                             st.warning("Company size rules not saved as JSON dict, storing as text.")
                             size_rules_dict = {} # Or maybe keep the string? Needs backend alignment
                    except json.JSONDecodeError:
                         st.warning("Could not parse Company Size Rules as JSON. Please use valid JSON format like {\"min\": 50} or leave blank.")
                         # Decide: prevent save or save empty/as text? Prevent for now.
                         st.stop() # Stop processing if JSON is invalid


                    # Prepare payload matching ICPInput schema
                    icp_payload = {
                        "name": st.session_state.icp_name,
                        "title_keywords": title_kws,
                        "industry_keywords": industry_kws,
                        "location_keywords": location_kws,
                        "company_size_rules": size_rules_dict,
                         # Add other fields...
                    }

                    with st.spinner("Saving ICP..."):
                        success = save_icp_data(icp_payload, auth_token)

                    if success:
                        # Clear cached data to force refetch on next load
                        if 'icp_data' in st.session_state:
                            del st.session_state['icp_data']
                        # Rerun is good practice after successful save to show updated state
                        st.rerun()


        with tab2:
            st.subheader("Offerings")
            st.info("Offering management UI coming soon.")
            # TODO: Implement UI for GET/POST/PUT/DELETE /api/v1/offerings

        with tab3:
            st.subheader("Email Sending Configuration")
            st.info("Email setup UI coming soon.")
            # TODO: Implement UI for PUT /api/v1/settings/email

    # ... (Keep elif for other pages) ...
    else:
        st.error("Page not found.")
        
        # ...
    # ... etc ...
