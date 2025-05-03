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
        st.divider()
        page = st.radio(
            "Navigate",
            ["Dashboard", "Leads", "Campaigns", "Setup Assistant", "Configuration"],
            key="nav_radio" )
        st.divider()
        if st.button("Logout"): logout_user()

    # --- Page Content ---
    if page == "Dashboard":
        # ... (Dashboard code remains the same) ...
    elif page == "Leads":
        # ... (Leads placeholder remains the same) ...
    elif page == "Campaigns":
        # ... (Campaigns placeholder remains the same) ...
    elif page == "Setup Assistant":
        # ... (Setup Assistant placeholder remains the same) ...
    elif page == "Configuration":
        st.header("⚙️ Configuration")
        tab1, tab2, tab3 = st.tabs(["🎯 ICP Definition", "💡 Offerings", "📧 Email Sending"])

        # --- ICP Definition Tab ---
        with tab1:
            st.subheader("Ideal Customer Profile (ICP)")

            # --- Initialize Session State Flags for this Tab ---
            st.session_state.setdefault('icp_data_loaded', False)
            st.session_state.setdefault('show_icp_edit_form', False)
            st.session_state.setdefault('icp_to_edit', None) # Store data of ICP being edited

            # --- Display Success Message ---
            if st.session_state.get('icp_save_success', False):
                st.success("✅ ICP Definition saved successfully!")
                del st.session_state['icp_save_success'] # Clear the flag

            # --- Load Data ---
            if not st.session_state.icp_data_loaded:
                 with st.spinner("Loading ICP data..."):
                     fetched_icp = get_icp_data(auth_token)
                     # Store fetched data or empty dict if fetch failed or no data exists
                     st.session_state['icp_data'] = fetched_icp if fetched_icp is not None else {}
                     st.session_state.icp_data_loaded = True # Mark as loaded

            # Get current data from session state
            current_icp = st.session_state.get('icp_data', {})

            # --- Display Saved ICP Summary and Actions ---
            if current_icp and current_icp.get("id"): # Check if a valid ICP exists
                st.markdown("---")
                # Use columns for layout
                col_info, col_view, col_edit = st.columns([4, 1, 1]) # Adjust ratios as needed

                with col_info:
                    st.markdown(f"**Current ICP:** `{current_icp.get('name', 'Unnamed ICP')}`")
                    # Optional: Add summary counts
                    summary_parts = []
                    if current_icp.get('title_keywords'): summary_parts.append(f"{len(current_icp['title_keywords'])} Titles")
                    if current_icp.get('industry_keywords'): summary_parts.append(f"{len(current_icp['industry_keywords'])} Industries")
                    if current_icp.get('location_keywords'): summary_parts.append(f"{len(current_icp['location_keywords'])} Locations")
                    if current_icp.get('company_size_rules'): summary_parts.append("Size Rules")
                    if summary_parts:
                         st.caption(f"Criteria: {', '.join(summary_parts)}")
                    else:
                         st.caption("No criteria defined.")

                with col_view:
                     # Unique key based on ICP ID (or name if ID not available)
                     view_key = f"view_icp_{current_icp.get('id', 'current')}"
                     if st.button("View", key=view_key, use_container_width=True):
                         st.session_state['view_icp_details'] = current_icp # Store data to view

                with col_edit:
                     edit_key = f"edit_icp_{current_icp.get('id', 'current')}"
                     if st.button("Edit", key=edit_key, type="secondary", use_container_width=True):
                         st.session_state.icp_to_edit = current_icp # Store data for form
                         st.session_state.show_icp_edit_form = True # Flag to show form
                         st.rerun() # Rerun to ensure form shows immediately

                st.markdown("---")

            elif st.session_state.icp_data_loaded: # Only show if loading finished and no ICP found
                 # Display a button to start defining one if none exists
                 if st.button("✚ Define New ICP"):
                     st.session_state.icp_to_edit = {} # Start with empty data
                     st.session_state.show_icp_edit_form = True
                     st.rerun()

            # --- Display ICP Details Dialog (Modal) ---
            if 'view_icp_details' in st.session_state:
                icp_to_view = st.session_state.view_icp_details

                @st.dialog("ICP Details", dismissed=lambda: st.session_state.pop('view_icp_details', None)) # Use lambda to remove key on dismiss
                def show_icp_view_dialog():
                    st.subheader(f"{icp_to_view.get('name', 'N/A')}")
                    st.markdown("---")

                    st.markdown("**Titles/Keywords:**")
                    title_kws = icp_to_view.get('title_keywords', [])
                    if title_kws: st.markdown("\n".join([f"- `{kw}`" for kw in title_kws]))
                    else: st.caption("None specified.")

                    st.markdown("**Industries/Keywords:**")
                    industry_kws = icp_to_view.get('industry_keywords', [])
                    if industry_kws: st.markdown("\n".join([f"- `{kw}`" for kw in industry_kws]))
                    else: st.caption("None specified.")

                    st.markdown("**Locations/Keywords:**")
                    location_kws = icp_to_view.get('location_keywords', [])
                    if location_kws: st.markdown("\n".join([f"- `{kw}`" for kw in location_kws]))
                    else: st.caption("None specified.")

                    st.markdown("**Company Size Rules:**")
                    size_rules = icp_to_view.get('company_size_rules', {})
                    min_size = size_rules.get('min') if isinstance(size_rules, dict) else None
                    max_size = size_rules.get('max') if isinstance(size_rules, dict) else None
                    if min_size is not None or max_size is not None:
                        st.markdown(f"- Min: `{min_size if min_size is not None else 'Any'}` | Max: `{max_size if max_size is not None else 'Any'}`")
                    else: st.caption("Any size.")

                    st.markdown("---")
                    if st.button("Close", key="close_view_dialog"):
                         # Remove the key to close the dialog and prevent reopening
                         if 'view_icp_details' in st.session_state:
                             del st.session_state['view_icp_details']
                         st.rerun()

                show_icp_view_dialog() # Call the function to display the dialog


            # --- Conditionally Display ICP Edit Form ---
            if st.session_state.get('show_icp_edit_form', False):
                st.markdown("#### Edit ICP Definition:")
                # Get data to pre-fill form (either from clicking 'Edit' or empty for 'New')
                form_data = st.session_state.get('icp_to_edit', {})

                with st.form("icp_edit_form"): # Changed form key
                    # --- Form Fields (populated from form_data) ---
                    st.text_input("ICP Name:", value=form_data.get("name", "Default ICP"), key="icp_edit_name")
                    st.text_area("Titles/Keywords (one per line):", value="\n".join(form_data.get("title_keywords", [])), key="icp_edit_titles", height=100, help="...")
                    st.text_area("Industries/Keywords (one per line):", value="\n".join(form_data.get("industry_keywords", [])), key="icp_edit_industries", height=100, help="...")
                    st.text_area("Locations/Keywords (one per line):", value="\n".join(form_data.get("location_keywords", [])), key="icp_edit_locations", height=100, help="...")

                    st.divider(); st.markdown("**Company Size**")
                    current_size_rules_form = form_data.get("company_size_rules", {})
                    current_min_size_form, current_max_size_form = None, None
                    if isinstance(current_size_rules_form, dict):
                        current_min_size_form = current_size_rules_form.get("min")
                        current_max_size_form = current_size_rules_form.get("max")
                    try: current_min_size_form = int(current_min_size_form) if current_min_size_form is not None else None
                    except: current_min_size_form = None
                    try: current_max_size_form = int(current_max_size_form) if current_max_size_form is not None else None
                    except: current_max_size_form = None

                    col_min_edit, col_max_edit = st.columns(2)
                    with col_min_edit:
                        st.number_input("Min Employees:", min_value=1, value=current_min_size_form, step=1, format="%d", key="icp_edit_min_size", help="...")
                    with col_max_edit:
                        st.number_input("Max Employees:", min_value=1, value=current_max_size_form, step=1, format="%d", key="icp_edit_max_size", help="...")

                    min_val_check = st.session_state.icp_edit_min_size
                    max_val_check = st.session_state.icp_edit_max_size
                    min_int_check = int(min_val_check) if min_val_check is not None else None
                    max_int_check = int(max_val_check) if max_val_check is not None else None
                    if min_int_check is not None and max_int_check is not None and min_int_check > max_int_check:
                        st.warning("Minimum size cannot be greater than maximum size.", icon="⚠️")
                    st.divider()

                    # --- Form Buttons ---
                    submitted = st.form_submit_button("💾 Save Changes")
                    # Add a cancel button
                    cancel_clicked = st.form_submit_button("Cancel", type="secondary")

                    if cancel_clicked:
                        st.session_state.show_icp_edit_form = False
                        st.session_state.icp_to_edit = None # Clear edit data
                        st.rerun()

                    if submitted:
                        # --- Validation and Saving Logic (using _edit keys) ---
                        can_save = True
                        icp_name = st.session_state.icp_edit_name.strip()
                        if not icp_name: st.error("ICP Name cannot be empty."); can_save = False

                        # Use the min/max values already validated for display
                        if min_int_check is not None and max_int_check is not None and min_int_check > max_int_check:
                             st.error("Minimum company size cannot be greater than maximum size. Please correct.")
                             can_save = False

                        if can_save:
                            title_kws = [kw.strip() for kw in st.session_state.icp_edit_titles.split('\n') if kw.strip()]
                            industry_kws = [kw.strip() for kw in st.session_state.icp_edit_industries.split('\n') if kw.strip()]
                            location_kws = [kw.strip() for kw in st.session_state.icp_edit_locations.split('\n') if kw.strip()]
                            size_rules_payload = {}
                            if min_int_check is not None: size_rules_payload["min"] = min_int_check
                            if max_int_check is not None: size_rules_payload["max"] = max_int_check

                            icp_payload = {
                                "name": icp_name, "title_keywords": title_kws, "industry_keywords": industry_kws,
                                "location_keywords": location_kws, "company_size_rules": size_rules_payload if size_rules_payload else None
                            }
                            with st.spinner("Saving ICP definition..."):
                                success = save_icp_data(icp_payload, auth_token)
                            if success:
                                st.session_state.icp_save_success = True
                                st.session_state.icp_data_loaded = False # Force reload
                                st.session_state.show_icp_edit_form = False # Hide form
                                st.session_state.icp_to_edit = None # Clear edit data
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
