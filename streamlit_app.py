# streamlit_app.py
# Main application file for SalesTroopz Streamlit Frontend

import os
import streamlit as st
import requests
import json
import time
from typing import Dict, Any, Optional, List

# --- Page Configuration (Call ONCE at the top) ---
st.set_page_config(
    page_title="SalesTroopz",
    layout="wide"
)

# --- Configuration ---
# Fetch backend URL from environment variable for flexibility
# Set BACKEND_API_URL in your Render service environment variables.
BACKEND_URL = os.getenv("BACKEND_API_URL", None) # Default to None if not set

# Check if Backend URL is configured
if not BACKEND_URL:
    st.error("FATAL ERROR: BACKEND_API_URL environment variable is not set. Application cannot connect to the backend.", icon="🚨")
    st.stop() # Stop execution if backend URL is missing

# Define API endpoints
LOGIN_ENDPOINT = f"{BACKEND_URL}/api/v1/auth/token"
REGISTER_ENDPOINT = f"{BACKEND_URL}/api/v1/auth/register"
LEADS_ENDPOINT = f"{BACKEND_URL}/api/v1/leads"
ICP_ENDPOINT = f"{BACKEND_URL}/api/v1/icp"
OFFERINGS_ENDPOINT = f"{BACKEND_URL}/api/v1/offerings"
# CAMPAIGNS_ENDPOINT = f"{BACKEND_URL}/api/v1/campaigns" # Add later

# --- Authentication Functions ---

def login_user(email, password) -> Optional[str]:
    """Attempts to log in user via API, returns token string or None."""
    try:
        response = requests.post(
            LOGIN_ENDPOINT,
            data={"username": email, "password": password}, # Form data
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15 # Increased timeout slightly
        )
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        token_data = response.json()
        access_token = token_data.get("access_token")
        if not access_token:
             st.error("Login failed: No access token received from backend.")
             return None
        return access_token
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401:
            st.error("Login failed: Incorrect email or password.")
        else:
            error_detail = f"Login failed: HTTP {http_err.response.status_code}"
            try: error_detail += f" - {http_err.response.json().get('detail', '(No detail provided)')}"
            except: error_detail += f" - Response: {http_err.response.text[:100]}..."
            st.error(error_detail)
        return None
    except requests.exceptions.RequestException as req_err:
        st.error(f"Login failed: Connection error to backend ({LOGIN_ENDPOINT}) - {req_err}")
        return None
    except Exception as e:
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
            error_detail = f"Registration failed: {response.status_code}"
            try: error_detail += f" - {response.json().get('detail', 'Unknown error')}"
            except: pass
            st.error(error_detail)
            return False
    except requests.exceptions.RequestException as e:
        st.error(f"Registration failed: Connection error to backend ({REGISTER_ENDPOINT}) - {e}")
        return False
    except Exception as e:
         st.error(f"Registration failed: An unexpected error occurred - {e}")
         return False

def logout_user():
    """Clears authentication state and reruns the app."""
    keys_to_delete = ['auth_token', 'authenticated', 'user_email', 'view', 'icp_data', 'icp_data_loaded', 'show_icp_edit_form', 'icp_to_edit', 'icp_save_success', 'view_icp_details'] # Clear ALL relevant state
    for key in keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state['view'] = 'Login' # Ensure view resets to login
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
             logout_user() # Force logout on 401
        else:
            error_detail = f"Error fetching data ({endpoint}): HTTP {http_err.response.status_code}"
            try: error_detail += f" - {http_err.response.json().get('detail', '')}"
            except: pass
            st.error(error_detail)
        return None
    except requests.exceptions.RequestException as req_err:
        st.error(f"Error fetching data ({endpoint}): Connection error - {req_err}")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred fetching data ({endpoint}): {e}")
        return None

def put_authenticated_request(endpoint: str, token: str, data: Dict[str, Any]) -> bool:
    """Makes an authenticated PUT request, handles errors, returns True on success."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.put(endpoint, headers=headers, json=data, timeout=20)
        response.raise_for_status()
        # Let the calling function handle success message
        return True
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401:
             st.error("Authentication failed or session expired. Please log in again.")
             logout_user() # Force logout on 401
        else:
             error_detail = f"Failed to save data ({endpoint}): HTTP {http_err.response.status_code}"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        return False
    except requests.exceptions.RequestException as req_err:
        st.error(f"Failed to save data ({endpoint}): Connection error - {req_err}")
        return False
    except Exception as e:
        st.error(f"Failed to save data ({endpoint}): An unexpected error occurred - {e}")
        return False

# --- ICP Specific Helpers (NEW - for Multiple ICPs) --

def list_icps(token: str) -> Optional[List[Dict]]:
    """Fetches a list of all ICPs for the organization."""
    endpoint = f"{BACKEND_URL}/api/v1/icps/" # Plural endpoint
    # Reuse the existing GET helper function
    response_data = get_authenticated_request(endpoint, token)
    # Ensure it returns a list, handling potential None from error
    if isinstance(response_data, list):
        return response_data
    else:
        # get_authenticated_request should have already shown an error in the UI
        return None # Return None to indicate failure to load list

def create_new_icp(icp_payload: Dict[str, Any], token: str) -> Optional[Dict]:
    """Creates a new ICP via POST request."""
    endpoint = f"{BACKEND_URL}/api/v1/icps/" # Plural endpoint
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.post(endpoint, headers=headers, json=icp_payload, timeout=20)
        response.raise_for_status()
        return response.json() # Return the created ICP data
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401:
             st.error("Authentication failed or session expired. Please log in again."); logout_user()
        # Add specific handling for 422 Validation Error if backend provides details
        elif http_err.response.status_code == 422:
             error_detail = f"Failed to create ICP: Validation Error (HTTP {http_err.response.status_code})"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        else:
             error_detail = f"Failed to create ICP: HTTP {http_err.response.status_code}"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        return None
    except requests.exceptions.RequestException as req_err:
        st.error(f"Failed to create ICP: Connection error - {req_err}")
        return None
    except Exception as e:
        st.error(f"Failed to create ICP: An unexpected error occurred - {e}")
        return None

def update_existing_icp(icp_id: int, icp_payload: Dict[str, Any], token: str) -> Optional[Dict]:
    """Updates an existing ICP via PUT request."""
    endpoint = f"{BACKEND_URL}/api/v1/icps/{icp_id}" # Specific ICP ID endpoint
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        # Use requests.put directly to get response data easily
        response = requests.put(endpoint, headers=headers, json=icp_payload, timeout=20)
        response.raise_for_status()
        return response.json() # Return updated ICP data from backend
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401:
             st.error("Authentication failed or session expired. Please log in again."); logout_user()
        elif http_err.response.status_code == 404:
             st.error(f"Failed to update ICP: Not found (ID: {icp_id}).")
        elif http_err.response.status_code == 422:
             error_detail = f"Failed to update ICP: Validation Error (HTTP {http_err.response.status_code})"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        else:
             error_detail = f"Failed to update ICP: HTTP {http_err.response.status_code}"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        return None
    except requests.exceptions.RequestException as req_err:
        st.error(f"Failed to update ICP: Connection error - {req_err}")
        return None
    except Exception as e:
        st.error(f"Failed to update ICP: An unexpected error occurred - {e}")
        return None

def delete_existing_icp(icp_id: int, token: str) -> bool:
    """Deletes an existing ICP via DELETE request."""
    endpoint = f"{BACKEND_URL}/api/v1/icps/{icp_id}" # Specific ICP ID endpoint
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.delete(endpoint, headers=headers, timeout=15)
        response.raise_for_status() # Raises error for 4xx/5xx
        # Status code 204 means success for DELETE with no content
        return response.status_code == 204
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401:
             st.error("Authentication failed or session expired. Please log in again."); logout_user()
        elif http_err.response.status_code == 404:
             st.error(f"Failed to delete ICP: Not found (ID: {icp_id}).")
        else:
             error_detail = f"Failed to delete ICP: HTTP {http_err.response.status_code}"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        return False
    except requests.exceptions.RequestException as req_err:
        st.error(f"Failed to delete ICP: Connection error - {req_err}")
        return False
    except Exception as e:
        st.error(f"Failed to delete ICP: An unexpected error occurred - {e}")
        return False

# --- Main App Logic ---

# Initialize session state keys reliably
st.session_state.setdefault("authenticated", False)
st.session_state.setdefault("auth_token", None)
st.session_state.setdefault("user_email", None)
st.session_state.setdefault("view", "Login") # Default view
st.session_state.setdefault('icp_data_loaded', False)
st.session_state.setdefault('show_icp_edit_form', False)
st.session_state.setdefault('icp_to_edit', None)

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
                if not email or not password:
                    st.warning("Please enter both email and password.")
                else:
                    with st.spinner("Attempting login..."):
                        token = login_user(email, password)
                    if token:
                        st.session_state["authenticated"] = True
                        st.session_state["auth_token"] = token
                        st.session_state["user_email"] = email
                        st.session_state['icp_data_loaded'] = False # Reset load flag on new login
                        st.session_state['show_icp_edit_form'] = False # Ensure form is hidden
                        st.rerun() # Rerun to show main app

        st.divider()
        st.markdown("Don't have an account?")
        if st.button("Sign Up Here", key="go_to_signup"):
            st.session_state["view"] = "Sign Up"
            st.rerun()

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
                if not all([org_name, email, password, confirm_password]):
                    st.warning("Please fill in all fields.")
                elif password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    with st.spinner("Creating account..."):
                        success = register_user(org_name, email, password)
                    if success:
                        st.session_state['view'] = 'Login' # Go back to login after successful signup
                        time.sleep(2) # Time to read success message
                        st.rerun()

        st.divider()
        st.markdown("Already have an account?")
        if st.button("Login Here", key="go_to_login"):
            st.session_state["view"] = "Login"
            st.rerun()
    # End of Authentication Section

# --- Main Application Logic (Shown Only After Login) ---
else:
    auth_token = st.session_state.get("auth_token")
    if not auth_token:
        # This should ideally not happen if authenticated is True, but as a safeguard:
        st.warning("Authentication error. Please log in again.")
        logout_user()
        st.stop() # Stop further execution

    # --- Sidebar ---
    with st.sidebar:
        st.title("SalesTroopz")
        st.write(f"User: {st.session_state.get('user_email', 'N/A')}")
        # TODO: Fetch and display Org Name (requires an API endpoint)
        st.divider()
        # Use session state to preserve selection if needed, otherwise radio default works
        page = st.radio(
            "Navigate",
            ["Dashboard", "Leads", "Campaigns", "Setup Assistant", "Configuration"],
            key="nav_radio",
            index=0 # Default to Dashboard
        )
        st.divider()
        if st.button("Logout"):
            logout_user()

    # --- Page Content ---
    if page == "Dashboard":
        st.header("Dashboard")
        st.write("Welcome to SalesTroopz!")
        # Example button - replace with actual dashboard content
        if st.button("Fetch My Leads (Test)"):
            with st.spinner("Fetching leads..."):
                # Assuming LEADS_ENDPOINT is defined
                leads_data = get_authenticated_request(LEADS_ENDPOINT, auth_token)
            if leads_data is not None:
                st.success(f"Fetched {len(leads_data)} leads.")
                st.dataframe(leads_data)
            # Errors handled in get_authenticated_request

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
            st.subheader("🎯 Ideal Customer Profiles (ICP)")
            st.caption("Define different target customer segments for your campaigns.")

            # --- Initialize Session State Flags for this Tab ---
            st.session_state.setdefault('icps_list', [])
            st.session_state.setdefault('icps_loaded', False)
            st.session_state.setdefault('show_icp_form', False) # Controls form visibility
            st.session_state.setdefault('icp_form_data', {}) # Data for pre-filling form
            st.session_state.setdefault('icp_being_edited_id', None) # Track if editing or creating
            st.session_state.setdefault('icp_to_delete', None) # Store ICP for delete confirmation

            # --- Display Action Messages ---
            if st.session_state.get('icp_action_success', None):
                st.success(st.session_state.icp_action_success)
                del st.session_state['icp_action_success'] # Clear flag

            if st.session_state.get('icp_action_error', None):
                st.error(st.session_state.icp_action_error)
                del st.session_state['icp_action_error'] # Clear flag


            # --- Load Data ---
            if not st.session_state.icps_loaded:
                with st.spinner("Loading ICP list..."):
                    fetched_icps = list_icps(auth_token) # Call API to get list
                    if fetched_icps is not None:
                        st.session_state['icps_list'] = fetched_icps
                    else:
                        st.session_state['icps_list'] = [] # Set empty list on error
                        st.warning("Could not load ICP list from the backend.") # Show warning
                    st.session_state.icps_loaded = True

            # Get current list from session state
            icp_list = st.session_state.get('icps_list', [])

            # --- Display ICP List and Actions ---
            st.markdown("---")
            col_header_1, col_header_2 = st.columns([4, 1])
            with col_header_1:
                 st.markdown("##### Saved ICP Definitions")
            with col_header_2:
                 if st.button("✚ Add New ICP", use_container_width=True):
                     st.session_state.icp_form_data = {} # Clear form data
                     st.session_state.icp_being_edited_id = None # Ensure it's None for create mode
                     st.session_state.show_icp_form = True # Show the form
                     st.rerun()

            if not icp_list and st.session_state.icps_loaded:
                st.info("No ICPs defined yet. Click 'Add New ICP' to create one.")
            elif icp_list:
                # Display each ICP in a row with buttons
                for icp in icp_list:
                    icp_id = icp.get('id')
                    with st.container(border=True):
                        col_info, col_edit, col_delete = st.columns([4, 1, 1])
                        with col_info:
                            st.markdown(f"**{icp.get('name', 'Unnamed ICP')}** (ID: {icp_id})")
                            # Add a brief summary if desired
                            summary_parts = []
                            if icp.get('title_keywords'): summary_parts.append(f"{len(icp['title_keywords'])} Titles")
                            if icp.get('industry_keywords'): summary_parts.append(f"{len(icp['industry_keywords'])} Industries")
                            # Add more summary parts if needed
                            if summary_parts: st.caption(f"Criteria: {', '.join(summary_parts)}")
                            else: st.caption("No criteria defined.")

                        with col_edit:
                             edit_key = f"edit_icp_{icp_id}"
                             if st.button("Edit", key=edit_key, type="secondary", use_container_width=True):
                                 st.session_state.icp_form_data = icp # Pre-fill form with this ICP's data
                                 st.session_state.icp_being_edited_id = icp_id # Set ID for update mode
                                 st.session_state.show_icp_form = True # Show form
                                 st.rerun()

                        with col_delete:
                             delete_key = f"delete_icp_{icp_id}"
                             if st.button("Delete", key=delete_key, type="primary", use_container_width=True):
                                 st.session_state.icp_to_delete = icp # Store ICP data for confirmation dialog
                                 st.rerun() # Rerun to show confirmation dialog

            st.markdown("---")


            # --- Delete Confirmation Dialog ---
            if st.session_state.get('icp_to_delete') is not None:
                icp_for_deletion = st.session_state.icp_to_delete

                @st.dialog(f"Confirm Deletion", dismissed=lambda: st.session_state.pop('icp_to_delete', None))
                def show_delete_dialog():
                    st.warning(f"Are you sure you want to delete the ICP named **'{icp_for_deletion.get('name', 'N/A')}'** (ID: {icp_for_deletion.get('id')})?", icon="⚠️")
                    st.caption("This action cannot be undone. Campaigns linked to this ICP might be affected (icp_id set to NULL).")
                    col_confirm, col_cancel = st.columns(2)
                    with col_confirm:
                        if st.button("Yes, Delete ICP", type="primary", use_container_width=True):
                             with st.spinner("Deleting ICP..."):
                                 success = delete_existing_icp(icp_for_deletion['id'], auth_token)
                             if success:
                                 st.session_state.icp_action_success = f"ICP '{icp_for_deletion.get('name')}' deleted successfully."
                                 st.session_state.icps_loaded = False # Force reload list
                             else:
                                 # Error message handled by delete_existing_icp
                                 st.session_state.icp_action_error = "Failed to delete ICP."
                             # Clear deletion state regardless of success/failure before rerun
                             del st.session_state.icp_to_delete
                             st.rerun()

                    with col_cancel:
                        if st.button("Cancel", use_container_width=True):
                            del st.session_state.icp_to_delete # Just remove flag
                            st.rerun()

                show_delete_dialog() # Show the dialog

            # --- Conditionally Display ICP Create/Edit Form ---
            if st.session_state.get('show_icp_form', False):
                form_title = "Edit ICP Definition" if st.session_state.get('icp_being_edited_id') else "Define New ICP"
                st.markdown(f"#### {form_title}")
                form_data = st.session_state.get('icp_form_data', {})

                with st.form("icp_form"): # Keep one form key, but pre-fill differently
                    st.text_input("ICP Name:", value=form_data.get("name", ""), key="icp_form_name", placeholder="e.g., Mid-Market SaaS")
                    st.text_area("Titles/Keywords (one per line):", value="\n".join(form_data.get("title_keywords", [])), key="icp_form_titles", height=100, help="...")
                    st.text_area("Industries/Keywords (one per line):", value="\n".join(form_data.get("industry_keywords", [])), key="icp_form_industries", height=100, help="...")
                    st.text_area("Locations/Keywords (one per line):", value="\n".join(form_data.get("location_keywords", [])), key="icp_form_locations", height=100, help="...")

                    st.divider(); st.markdown("**Company Size (Optional)**")
                    current_size_rules_form = form_data.get("company_size_rules", {})
                    current_min_size_form, current_max_size_form = None, None
                    if isinstance(current_size_rules_form, dict):
                        current_min_size_form = current_size_rules_form.get("min"); current_max_size_form = current_size_rules_form.get("max")
                    try: current_min_size_form = int(current_min_size_form) if current_min_size_form is not None else None
                    except: current_min_size_form = None
                    try: current_max_size_form = int(current_max_size_form) if current_max_size_form is not None else None
                    except: current_max_size_form = None

                    col_min_edit, col_max_edit = st.columns(2)
                    with col_min_edit: st.number_input("Min Employees:", min_value=1, value=current_min_size_form, step=1, format="%d", key="icp_form_min_size", help="...")
                    with col_max_edit: st.number_input("Max Employees:", min_value=1, value=current_max_size_form, step=1, format="%d", key="icp_form_max_size", help="...")

                    min_v_check = st.session_state.icp_form_min_size
                    max_v_check = st.session_state.icp_form_max_size
                    if min_v_check is not None and max_v_check is not None and int(min_v_check) > int(max_v_check):
                        st.warning("Minimum cannot be greater than maximum.", icon="⚠️")
                    st.divider()

                    # --- Form Buttons ---
                    submitted = st.form_submit_button("💾 Save ICP")
                    cancel_clicked = st.form_submit_button("Cancel", type="secondary")

                    if cancel_clicked:
                        st.session_state.show_icp_form = False
                        st.session_state.icp_form_data = {}
                        st.session_state.icp_being_edited_id = None
                        st.rerun()

                    if submitted:
                        # --- Validation and Saving ---
                        can_save = True
                        icp_name = st.session_state.icp_form_name.strip()
                        if not icp_name: st.error("ICP Name cannot be empty."); can_save = False

                        min_int_val = int(min_v_check) if min_v_check is not None else None
                        max_int_val = int(max_v_check) if max_v_check is not None else None
                        if min_int_val is not None and max_int_val is not None and min_int_val > max_int_val:
                             st.error("Minimum company size cannot be greater than maximum size."); can_save = False

                        if can_save:
                            title_kws = [kw.strip() for kw in st.session_state.icp_form_titles.split('\n') if kw.strip()]
                            industry_kws = [kw.strip() for kw in st.session_state.icp_form_industries.split('\n') if kw.strip()]
                            location_kws = [kw.strip() for kw in st.session_state.icp_form_locations.split('\n') if kw.strip()]
                            size_rules_payload = {}
                            if min_int_val is not None: size_rules_payload["min"] = min_int_val
                            if max_int_val is not None: size_rules_payload["max"] = max_int_val

                            icp_payload = { "name": icp_name, "title_keywords": title_kws, "industry_keywords": industry_kws, "location_keywords": location_kws, "company_size_rules": size_rules_payload if size_rules_payload else None }

                            # --- Call Correct API ---
                            icp_id_to_update = st.session_state.get('icp_being_edited_id')
                            success = False
                            result_data = None
                            with st.spinner("Saving ICP definition..."):
                                if icp_id_to_update: # UPDATE mode
                                    result_data = update_existing_icp(icp_id_to_update, icp_payload, auth_token)
                                else: # CREATE mode
                                     result_data = create_new_icp(icp_payload, auth_token)
                                success = result_data is not None

                            if success:
                                action = "updated" if icp_id_to_update else "created"
                                st.session_state.icp_action_success = f"ICP '{icp_name}' {action} successfully!"
                                st.session_state.icps_loaded = False # Force reload list
                                st.session_state.show_icp_form = False # Hide form
                                st.session_state.icp_form_data = {} # Clear form data
                                st.session_state.icp_being_edited_id = None # Clear edit ID
                                st.rerun()
                            else:
                                 st.session_state.icp_action_error = "Failed to save ICP." # Generic, specific error shown by helper
                                 st.rerun() # Rerun to show error message at top

        # --- Offerings Tab ---
        with tab2:
            st.subheader("💡 Offerings")
            st.info("Offering management UI coming soon.") # Placeholder

        # --- Email Sending Tab ---
        with tab3:
            st.subheader("📧 Email Sending Configuration")
            st.info("Email setup UI coming soon.") # Placeholder

    # End of Page Content `if/elif/else` block
    else:
        st.error("Page not found.") # Should not be reachable with st.radio
