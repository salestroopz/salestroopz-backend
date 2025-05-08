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
CAMPAIGNS_ENDPOINT = f"{BACKEND_URL}/api/v1/campaigns" 

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

# --- ADD Offering Specific Helpers ---

def list_offerings(token: str) -> Optional[List[Dict]]:
    """Fetches a list of all offerings for the organization."""
    endpoint = f"{BACKEND_URL}/api/v1/offerings/" # Ensure this endpoint exists in your backend
    response_data = get_authenticated_request(endpoint, token)
    if isinstance(response_data, list):
        return response_data
    else:
        return None

def create_new_offering(offering_payload: Dict[str, Any], token: str) -> Optional[Dict]:
    """Creates a new offering via POST request."""
    endpoint = f"{BACKEND_URL}/api/v1/offerings/" # Ensure POST is on the collection
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.post(endpoint, headers=headers, json=offering_payload, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401: st.error("Authentication failed."); logout_user()
        elif http_err.response.status_code == 422:
             error_detail = f"Failed to create offering: Validation Error"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        else:
             error_detail = f"Failed to create offering: HTTP {http_err.response.status_code}"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        return None
    except requests.exceptions.RequestException as req_err: st.error(f"Failed to create offering: Connection error - {req_err}"); return None
    except Exception as e: st.error(f"Failed to create offering: An unexpected error occurred - {e}"); return None

def update_existing_offering(offering_id: int, offering_payload: Dict[str, Any], token: str) -> Optional[Dict]:
    """Updates an existing offering via PUT request."""
    endpoint = f"{BACKEND_URL}/api/v1/offerings/{offering_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.put(endpoint, headers=headers, json=offering_payload, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401: st.error("Authentication failed."); logout_user()
        elif http_err.response.status_code == 404: st.error(f"Failed to update offering: Not found (ID: {offering_id}).")
        elif http_err.response.status_code == 422:
             error_detail = f"Failed to update offering: Validation Error"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        else:
             error_detail = f"Failed to update offering: HTTP {http_err.response.status_code}"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        return None
    except requests.exceptions.RequestException as req_err: st.error(f"Failed to update offering: Connection error - {req_err}"); return None
    except Exception as e: st.error(f"Failed to update offering: An unexpected error occurred - {e}"); return None

def delete_existing_offering(offering_id: int, token: str) -> bool:
    """Deletes an existing offering via DELETE request."""
    endpoint = f"{BACKEND_URL}/api/v1/offerings/{offering_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.delete(endpoint, headers=headers, timeout=15)
        response.raise_for_status()
        return response.status_code == 204
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401: st.error("Authentication failed."); logout_user()
        elif http_err.response.status_code == 404: st.error(f"Failed to delete offering: Not found (ID: {offering_id}).")
        else:
             error_detail = f"Failed to delete offering: HTTP {http_err.response.status_code}"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        return False
    except requests.exceptions.RequestException as req_err: st.error(f"Failed to delete offering: Connection error - {req_err}"); return False
    except Exception as e: st.error(f"Failed to delete offering: An unexpected error occurred - {e}"); return False

# --- END OF Offering Specific Helpers ---
# --- ADD Email Settings Specific Helpers ---

def get_email_settings(token: str) -> Optional[Dict]:
    """Fetches email settings for the organization."""
    endpoint = f"{BACKEND_URL}/api/v1/email-settings/"
    return get_authenticated_request(endpoint, token)

def save_email_settings(settings_payload: Dict[str, Any], token: str) -> Optional[Dict]:
    """Saves (Creates/Updates) email settings via PUT request."""
    endpoint = f"{BACKEND_URL}/api/v1/email-settings/"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        # Using PUT directly to get the response model back
        response = requests.put(endpoint, headers=headers, json=settings_payload, timeout=20)
        response.raise_for_status()
        return response.json() # Return the saved/updated settings data (EmailSettingsResponse)
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401: st.error("Authentication failed."); logout_user();
        elif http_err.response.status_code == 422:
             error_detail = f"Failed to save email settings: Validation Error"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        else:
             error_detail = f"Failed to save email settings: HTTP {http_err.response.status_code}"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        return None
    except requests.exceptions.RequestException as req_err: st.error(f"Failed to save email settings: Connection error - {req_err}"); return None
    except Exception as e: st.error(f"Failed to save email settings: An unexpected error occurred - {e}"); return None

# --- ADD Lead Specific API Helpers ---

def list_leads(token: str, skip: int = 0, limit: int = 100) -> Optional[List[Dict]]:
    """Fetches a paginated list of leads for the organization."""
    endpoint = f"{BACKEND_URL}/api/v1/leads/"
    params = {"skip": skip, "limit": limit}
    response_data = get_authenticated_request(endpoint, token, params=params)
    if isinstance(response_data, list):
        return response_data
    return None

def create_new_lead(lead_payload: Dict[str, Any], token: str) -> Optional[Dict]:
    """Creates a new lead via POST request."""
    endpoint = f"{BACKEND_URL}/api/v1/leads/"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.post(endpoint, headers=headers, json=lead_payload, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        # ... (similar detailed error handling as in create_new_icp/offering) ...
        st.error(f"Failed to create lead: HTTP {http_err.response.status_code}")
        return None
    except requests.exceptions.RequestException as req_err: st.error(f"Failed to create lead: Connection error - {req_err}"); return None
    except Exception as e: st.error(f"Failed to create lead: An unexpected error occurred - {e}"); return None

def get_lead_details(lead_id: int, token: str) -> Optional[Dict]:
    """Fetches details for a specific lead."""
    endpoint = f"{BACKEND_URL}/api/v1/leads/{lead_id}"
    return get_authenticated_request(endpoint, token)

def update_existing_lead(lead_id: int, lead_payload: Dict[str, Any], token: str) -> Optional[Dict]:
    """Updates an existing lead via PATCH or PUT request."""
    endpoint = f"{BACKEND_URL}/api/v1/leads/{lead_id}" # Assuming PATCH for partial
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.patch(endpoint, headers=headers, json=lead_payload, timeout=20) # Use PATCH
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        # ... (detailed error handling) ...
        st.error(f"Failed to update lead: HTTP {http_err.response.status_code}")
        return None
    except requests.exceptions.RequestException as req_err: st.error(f"Failed to update lead: Connection error - {req_err}"); return None
    except Exception as e: st.error(f"Failed to update lead: An unexpected error occurred - {e}"); return None

def delete_existing_lead(lead_id: int, token: str) -> bool:
    """Deletes an existing lead via DELETE request."""
    endpoint = f"{BACKEND_URL}/api/v1/leads/{lead_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.delete(endpoint, headers=headers, timeout=15)
        response.raise_for_status()
        return response.status_code == 204
    except requests.exceptions.HTTPError as http_err:
        # ... (detailed error handling) ...
        st.error(f"Failed to delete lead: HTTP {http_err.response.status_code}")
        return False
    except requests.exceptions.RequestException as req_err: st.error(f"Failed to delete lead: Connection error - {req_err}"); return False
    except Exception as e: st.error(f"Failed to delete lead: An unexpected error occurred - {e}"); return False

# --- ADD Campaign Specific API Helpers ---

def list_campaigns(token: str, active_only: Optional[bool] = None) -> Optional[List[Dict]]: # Modified
    """Fetches a list of campaigns for the organization."""
    endpoint = f"{CAMPAIGNS_ENDPOINT}/" # Ensure CAMPAIGNS_ENDPOINT is defined
    params = {}
    if active_only is not None:
        params["active_only"] = active_only
    # get_authenticated_request already handles org filtering via token implicitly
    response_data = get_authenticated_request(endpoint, token, params=params)
    if isinstance(response_data, list):
        return response_data
    return None

def create_new_campaign(campaign_payload: Dict[str, Any], token: str) -> Optional[Dict]: # Modified
    """Creates a new campaign via POST request. AI will generate steps."""
    endpoint = f"{CAMPAIGNS_ENDPOINT}/"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.post(endpoint, headers=headers, json=campaign_payload, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401: st.error("Authentication failed."); logout_user()
        elif http_err.response.status_code == 422:
             error_detail = f"Failed to create campaign: Validation Error"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        else:
             error_detail = f"Failed to create campaign: HTTP {http_err.response.status_code}"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        return None
    except requests.exceptions.RequestException as req_err: st.error(f"Failed to create campaign: Connection error - {req_err}"); return None
    except Exception as e: st.error(f"Failed to create campaign: An unexpected error occurred - {e}"); return None

def get_campaign_details(campaign_id: int, token: str) -> Optional[Dict]: # NEW
    """Fetches details for a specific campaign, including its steps."""
    endpoint = f"{CAMPAIGNS_ENDPOINT}/{campaign_id}"
    return get_authenticated_request(endpoint, token)

def update_existing_campaign(campaign_id: int, campaign_payload: Dict[str, Any], token: str) -> Optional[Dict]: # Keep as is for now
    """Updates an existing campaign via PUT request."""
    endpoint = f"{CAMPAIGNS_ENDPOINT}/{campaign_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.put(endpoint, headers=headers, json=campaign_payload, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        # ... (Add detailed error handling similar to create_new_campaign) ...
        st.error(f"Failed to update campaign: HTTP {http_err.response.status_code}")
        return None
    except Exception as e: st.error(f"Failed to update campaign: {e}"); return None


def delete_existing_campaign(campaign_id: int, token: str) -> bool: # Keep as is for now
    """Deletes an existing campaign via DELETE request."""
    endpoint = f"{CAMPAIGNS_ENDPOINT}/{campaign_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.delete(endpoint, headers=headers, timeout=15)
        response.raise_for_status()
        return response.status_code == 204
    except requests.exceptions.HTTPError as http_err:
        # ... (Add detailed error handling) ...
        st.error(f"Failed to delete campaign: HTTP {http_err.response.status_code}")
        return False
    except Exception as e: st.error(f"Failed to delete campaign: {e}"); return False
# Add or ensure update_existing_campaign exists and works for toggling is_active
def update_existing_campaign(campaign_id: int, campaign_payload: Dict[str, Any], token: str) -> Optional[Dict]:
    """Updates an existing campaign via PUT request."""
    endpoint = f"{CAMPAIGNS_ENDPOINT}/{campaign_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        response = requests.put(endpoint, headers=headers, json=campaign_payload, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401: st.error("Authentication failed."); logout_user(); return None
        elif http_err.response.status_code == 404: st.error(f"Failed to update campaign: Not found (ID: {campaign_id})."); return None
        elif http_err.response.status_code == 422:
             error_detail = f"Failed to update campaign: Validation Error"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        else:
             error_detail = f"Failed to update campaign: HTTP {http_err.response.status_code}"
             try: error_detail += f" - {http_err.response.json().get('detail', '')}"
             except: pass
             st.error(error_detail)
        return None
    except requests.exceptions.RequestException as req_err: st.error(f"Failed to update campaign: Connection error - {req_err}"); return None
    except Exception as e: st.error(f"Failed to update campaign: An unexpected error occurred - {e}"); return None

# Helper function specifically for activation toggle for clarity
def activate_deactivate_campaign_in_api(campaign_id: int, is_active_status: bool, token: str) -> bool:
    """Calls the update endpoint to set the is_active status."""
    payload = {"is_active": is_active_status}
    result = update_existing_campaign(campaign_id, payload, token)
    return result is not None # Return True if update was successful (returned data)


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

       # --- Page Content ---
    # ... (Dashboard code) ...

    elif page == "Leads":
        st.header("👤 Leads Management")
        st.caption("View, add, and manage your sales leads.")

        # --- Initialize Session State for Leads Page ---
        st.session_state.setdefault('leads_list', [])
        st.session_state.setdefault('leads_loaded', False)
        st.session_state.setdefault('show_lead_form', False) # Controls add/edit form visibility
        st.session_state.setdefault('lead_form_data', {})   # Data for pre-filling form
        st.session_state.setdefault('lead_being_edited_id', None) # Track if editing or creating
        st.session_state.setdefault('lead_to_delete', None) # Store lead for delete confirmation
        st.session_state.setdefault('lead_to_view_details', None) # Store lead for view details dialog
        st.session_state.setdefault('upload_summary', None) # For storing CSV upload results

        # --- Display Action Messages ---
        if st.session_state.get('lead_action_success', None):
            st.success(st.session_state.lead_action_success)
            del st.session_state['lead_action_success']
        if st.session_state.get('lead_action_error', None):
            st.error(st.session_state.lead_action_error)
            del st.session_state['lead_action_error']

        # --- Bulk CSV Upload Section ---
        st.markdown("---")
        st.subheader("📤 Bulk Import Leads from CSV")
        uploaded_file = st.file_uploader(
            "Choose a CSV file",
            type=["csv"],
            help="Upload a CSV file with columns like Name, Email, Company, Title, Source, etc. 'Email' is required."
        )

        if uploaded_file is not None:
            if st.button("🚀 Process Uploaded CSV"):
                with st.spinner(f"Processing '{uploaded_file.name}'... This may take a moment for large files."):
                    # Ensure upload_leads_csv_file helper function is defined
                    if 'upload_leads_csv_file' in locals() or 'upload_leads_csv_file' in globals():
                         summary = upload_leads_csv_file(uploaded_file, auth_token)
                         st.session_state.upload_summary = summary
                         st.session_state.leads_loaded = False # Force reload of leads list after import
                         st.rerun() # Rerun to display summary and refresh list
                    else:
                         st.error("ERROR: upload_leads_csv_file function not found!")


        # Display upload summary if available
        if st.session_state.get('upload_summary') is not None:
            summary = st.session_state.upload_summary
            st.markdown("---")
            st.markdown("#### CSV Import Summary:")
            st.info(
                f"- Total rows in file: {summary.get('total_rows_in_file', 'N/A')}\n"
                f"- Rows attempted: {summary.get('rows_attempted', 'N/A')}\n"
                f"- Successfully imported/updated: {summary.get('successfully_imported_or_updated', 'N/A')}\n"
                f"- Failed imports: {summary.get('failed_imports', 'N/A')}"
            )
            if summary.get('errors'):
                st.error("Errors encountered during import:")
                for i, err_detail in enumerate(summary['errors'][:5]): # Show max 5 errors
                    row_info = f"Row {err_detail.get('row_number')}: " if err_detail.get('row_number') else ""
                    email_info = f"Email '{err_detail.get('email')}': " if err_detail.get('email') else ""
                    st.markdown(f"- {row_info}{email_info}{err_detail.get('error')}")
                if len(summary['errors']) > 5:
                    st.caption(f"...and {len(summary['errors']) - 5} more errors (check backend logs for full details).")
            # Clear summary after displaying
            del st.session_state.upload_summary
        # --- END Bulk CSV Upload Section ---


        # --- Load Data (for lead list display) ---
        if not st.session_state.leads_loaded:
            with st.spinner("Loading leads..."):
                # Ensure list_leads helper function is defined
                if 'list_leads' in locals() or 'list_leads' in globals():
                     fetched_leads = list_leads(auth_token)
                     if fetched_leads is not None:
                         st.session_state.leads_list = fetched_leads
                     else:
                         st.session_state.leads_list = []
                else:
                     st.error("ERROR: list_leads function not found!")
                     st.session_state.leads_list = [] # Set empty list on error
                st.session_state.leads_loaded = True

        lead_list = st.session_state.get('leads_list', [])

        # --- Actions and Lead List Display ---
        st.markdown("---")
        col_header_lead1, col_header_lead2 = st.columns([3,1])
        with col_header_lead1:
            st.markdown("##### All Leads")
        with col_header_lead2:
            if st.button("✚ Add New Lead", use_container_width=True):
                st.session_state.lead_form_data = {} # Clear form for new lead
                st.session_state.lead_being_edited_id = None
                st.session_state.show_lead_form = True
                st.rerun() # Rerun to show the form

        if not lead_list and st.session_state.leads_loaded:
            st.info("No leads found. Click 'Add New Lead' or upload a CSV to get started.")
        elif lead_list:
            # Display leads
            for lead in lead_list:
                lead_id = lead.get('id')
                if not lead_id: continue # Skip if lead doesn't have an ID for some reason
                with st.container(border=True):
                    col_lead_info, col_lead_actions = st.columns([4,1])
                    with col_lead_info:
                        st.markdown(f"**{lead.get('name', 'N/A')}** ({lead.get('email')})")
                        st.caption(f"Company: {lead.get('company', 'N/A')} | Title: {lead.get('title', 'N/A')} | Source: {lead.get('source', 'N/A')}")
                    with col_lead_actions:
                        sub_col_view, sub_col_edit, sub_col_delete = st.columns(3)
                        with sub_col_view:
                            if st.button("👁️", key=f"view_lead_{lead_id}", help="View Details", use_container_width=True):
                                st.session_state.lead_to_view_details = lead
                                st.rerun()
                        with sub_col_edit:
                            if st.button("✏️", key=f"edit_lead_{lead_id}", help="Edit Lead", use_container_width=True):
                                st.session_state.lead_form_data = lead
                                st.session_state.lead_being_edited_id = lead_id
                                st.session_state.show_lead_form = True
                                st.rerun()
                        with sub_col_delete:
                            if st.button("🗑️", key=f"delete_lead_{lead_id}", help="Delete Lead", use_container_width=True):
                                st.session_state.lead_to_delete = lead
                                st.rerun()
            # --- TODO: Add Pagination UI if list_leads supports it and list is long ---

        st.markdown("---")

        # --- Delete Confirmation Dialog ---
        if st.session_state.get('lead_to_delete') is not None:
            lead_for_deletion = st.session_state.lead_to_delete
            @st.dialog("Confirm Lead Deletion", dismissed=lambda: st.session_state.pop('lead_to_delete', None))
            def show_lead_delete_dialog():
                st.warning(f"Are you sure you want to delete the lead: **{lead_for_deletion.get('name', lead_for_deletion.get('email'))}**?", icon="⚠️")
                col_del_c, col_del_k = st.columns(2)
                with col_del_c:
                    if st.button("Yes, Delete", type="primary", use_container_width=True):
                        # Ensure delete_existing_lead helper exists
                        if 'delete_existing_lead' in locals() or 'delete_existing_lead' in globals():
                            with st.spinner("Deleting lead..."): success = delete_existing_lead(lead_for_deletion['id'], auth_token)
                            if success: st.session_state.lead_action_success = "Lead deleted successfully."; st.session_state.leads_loaded = False
                            else: st.session_state.lead_action_error = "Failed to delete lead."
                        else:
                            st.session_state.lead_action_error = "ERROR: delete_existing_lead function not found!"
                        del st.session_state.lead_to_delete; st.rerun()
                with col_del_k:
                    if st.button("Cancel", use_container_width=True): del st.session_state.lead_to_delete; st.rerun()
            show_lead_delete_dialog()

        # --- View Lead Details Dialog ---
        if st.session_state.get('lead_to_view_details') is not None:
            lead_to_view = st.session_state.lead_to_view_details
            @st.dialog(f"Lead Details: {lead_to_view.get('name', lead_to_view.get('email'))}", dismissed=lambda: st.session_state.pop('lead_to_view_details', None))
            def show_lead_view_dialog():
                # Define order or specific fields to show if desired
                display_fields = ['name', 'email', 'company', 'title', 'source', 'linkedin_profile', 'company_size', 'industry', 'location', 'matched', 'reason', 'crm_status', 'appointment_confirmed', 'created_at', 'updated_at']
                for key in display_fields:
                    value = lead_to_view.get(key)
                    if value is not None: # Only display fields that have a value
                        display_key = key.replace("_", " ").title()
                        if isinstance(value, bool): st.markdown(f"**{display_key}:** {'Yes' if value else 'No'}")
                        elif isinstance(value, str) and ("http" in value or "www" in value): st.markdown(f"**{display_key}:** [{value}]({value})")
                        else: st.markdown(f"**{display_key}:** {value}")
                if st.button("Close", key="close_lead_view_dialog"):
                    del st.session_state.lead_to_view_details; st.rerun()
            show_lead_view_dialog()


        # --- Conditionally Display Lead Add/Edit Form ---
        if st.session_state.get('show_lead_form', False):
            form_title = "Edit Lead" if st.session_state.get('lead_being_edited_id') else "Add New Lead"
            st.markdown(f"#### {form_title}")
            form_data = st.session_state.get('lead_form_data', {})

            with st.form("lead_form"):
                st.text_input("Name:", value=form_data.get("name", ""), key="lead_form_name")
                st.text_input("Email*:", value=form_data.get("email", ""), key="lead_form_email", placeholder="name@company.com")
                st.text_input("Company:", value=form_data.get("company", ""), key="lead_form_company")
                st.text_input("Title:", value=form_data.get("title", ""), key="lead_form_title")
                st.text_input("Source:", value=form_data.get("source", "Manual Entry"), key="lead_form_source")
                st.text_input("LinkedIn Profile:", value=form_data.get("linkedin_profile", ""), key="lead_form_linkedin", placeholder="https://linkedin.com/in/...")
                st.text_input("Company Size:", value=form_data.get("company_size", ""), key="lead_form_company_size", placeholder="e.g., 51-200")
                st.text_input("Industry:", value=form_data.get("industry", ""), key="lead_form_industry")
                st.text_input("Location:", value=form_data.get("location", ""), key="lead_form_location")

                st.divider()
                col_match, col_appt = st.columns(2)
                with col_match: st.checkbox("Matched ICP?", value=bool(form_data.get("matched", False)), key="lead_form_matched")
                with col_appt: st.checkbox("Appointment Confirmed?", value=bool(form_data.get("appointment_confirmed", False)), key="lead_form_appointment")
                st.text_input("Match Reason (if applicable):", value=form_data.get("reason", ""), key="lead_form_reason")
                st.text_input("CRM Status:", value=form_data.get("crm_status", "pending"), key="lead_form_crm_status")


                st.divider()
                submitted = st.form_submit_button("💾 Save Lead")
                cancel_clicked = st.form_submit_button("Cancel", type="secondary")

                if cancel_clicked:
                    st.session_state.show_lead_form = False; st.session_state.lead_form_data = {}; st.session_state.lead_being_edited_id = None; st.rerun()

                if submitted:
                    can_save = True
                    lead_email = st.session_state.lead_form_email.strip()
                    if not lead_email: st.error("Lead Email is required."); can_save = False
                    # Add more validation as needed

                    if can_save:
                        lead_payload = {
                            "name": st.session_state.lead_form_name.strip() or None,
                            "email": lead_email,
                            "company": st.session_state.lead_form_company.strip() or None,
                            "title": st.session_state.lead_form_title.strip() or None,
                            "source": st.session_state.lead_form_source.strip() or None,
                            "linkedin_profile": st.session_state.lead_form_linkedin.strip() or None,
                            "company_size": st.session_state.lead_form_company_size.strip() or None,
                            "industry": st.session_state.lead_form_industry.strip() or None,
                            "location": st.session_state.lead_form_location.strip() or None,
                            "matched": st.session_state.lead_form_matched,
                            "reason": st.session_state.lead_form_reason.strip() or None,
                            "crm_status": st.session_state.lead_form_crm_status.strip() or None,
                            "appointment_confirmed": st.session_state.lead_form_appointment
                        }

                        lead_id_to_update = st.session_state.get('lead_being_edited_id')
                        success = False; result_data = None
                        with st.spinner("Saving lead..."):
                            # Ensure relevant API helpers exist
                            if lead_id_to_update: # Update mode
                                if 'update_existing_lead' in locals() or 'update_existing_lead' in globals():
                                    result_data = update_existing_lead(lead_id_to_update, lead_payload, auth_token)
                                else: st.error("ERROR: update_existing_lead function not defined!"); success = False
                            else: # Create mode
                                if 'create_new_lead' in locals() or 'create_new_lead' in globals():
                                    result_data = create_new_lead(lead_payload, auth_token)
                                else: st.error("ERROR: create_new_lead function not defined!"); success = False
                            # Check if result_data was populated only if no function error occurred
                            if 'result_data' in locals(): success = result_data is not None


                        if success:
                            action = "updated" if lead_id_to_update else "added"
                            st.session_state.lead_action_success = f"Lead '{lead_payload['email']}' {action} successfully!"
                            st.session_state.leads_loaded = False; st.session_state.show_lead_form = False; st.session_state.lead_form_data = {}; st.session_state.lead_being_edited_id = None
                            st.rerun()
                        else:
                            # Only set generic error if specific function error wasn't already shown
                            if not ('create_new_lead' in locals() or 'create_new_lead' in globals()) or not ('update_existing_lead' in locals() or 'update_existing_lead' in globals()):
                                pass # Error about missing function already shown
                            else:
                                st.session_state.lead_action_error = "Failed to save lead."; st.rerun()

    elif page == "Campaigns":
        st.header("📣 Campaign Management (AI-Powered)") # Updated Title
        st.caption("Create AI-generated email outreach campaigns, view progress, and manage settings.")

        # --- Initialize Session State for Campaigns Page ---
        st.session_state.setdefault('campaigns_list', [])
        st.session_state.setdefault('campaigns_loaded', False)
        st.session_state.setdefault('show_campaign_create_form', False) # Renamed for clarity
        # st.session_state.setdefault('campaign_form_data', {}) # Not strictly needed if form clears
        # st.session_state.setdefault('campaign_being_edited_id', None) # For edit functionality later
        st.session_state.setdefault('campaign_to_delete', None)
        st.session_state.setdefault('view_campaign_id', None) # NEW: To store ID of campaign to view details
        
        st.session_state.setdefault('available_icps_for_campaign', [])
        st.session_state.setdefault('available_icps_for_campaign_loaded', False)
        st.session_state.setdefault('available_offerings_for_campaign', [])
        st.session_state.setdefault('available_offerings_for_campaign_loaded', False)

        # --- Display Action Messages ---
        if st.session_state.get('campaign_action_success', None):
            st.success(st.session_state.campaign_action_success)
            del st.session_state['campaign_action_success']
        if st.session_state.get('campaign_action_error', None):
            st.error(st.session_state.campaign_action_error)
            del st.session_state['campaign_action_error']

        # --- Conditionally Display Campaign Details & Steps ---
        if st.session_state.get('view_campaign_id') is not None:
            campaign_id_to_view = st.session_state.view_campaign_id
            st.subheader(f"🔍 Campaign Details & AI-Generated Steps")
        
        # --- Load Data (Campaigns and ICPs for dropdown) ---
        # Load Campaigns
        if not st.session_state.campaigns_loaded:
            with st.spinner(f"Loading details for campaign ID {campaign_id_to_view}..."):
                campaign_details_data = get_campaign_details(campaign_id_to_view, auth_token)
                # Load all campaigns by default (active_only=None or remove param from helper if not needed)
                fetched_campaigns = list_campaigns(auth_token, active_only=None)
                if fetched_campaigns is not None:
                    st.session_state.campaigns_list = fetched_campaigns
                else:
                    st.session_state.campaigns_list = []
                st.session_state.campaigns_loaded = True
        
        if not st.session_state.available_icps_for_campaign_loaded:
            with st.spinner("Loading ICPs..."):
                fetched_icps = list_icps(auth_token) # Your existing helper
                if fetched_icps is not None:
                    st.session_state.available_icps_for_campaign = fetched_icps
                st.session_state.available_icps_for_campaign_loaded = True

        if not st.session_state.available_offerings_for_campaign_loaded:
            with st.spinner("Loading Offerings..."):
                fetched_offerings = list_offerings(auth_token) # Your existing helper
                if fetched_offerings is not None:
                    st.session_state.available_offerings_for_campaign = fetched_offerings
                st.session_state.available_offerings_for_campaign_loaded = True

        campaign_list = st.session_state.get('campaigns_list', [])
        available_icps = st.session_state.get('available_icps_for_campaign', [])
        available_offerings = st.session_state.get('available_offerings_for_campaign', [])

        # --- Create New Campaign Section ---
        st.markdown("---")
        if st.button("🚀 Create New Campaign Goal", key="show_create_campaign_form_button"):
            st.session_state.show_campaign_create_form = not st.session_state.get('show_campaign_create_form', False)
            # Clear view_campaign_id if create form is opened
            if st.session_state.show_campaign_create_form and 'view_campaign_id' in st.session_state:
                del st.session_state.view_campaign_id


        if st.session_state.get('show_campaign_create_form', False):
            st.subheader("Define New Campaign Goal")
            with st.form("create_campaign_form", clear_on_submit=True):
                campaign_name = st.text_input("Campaign Name*", help="A clear, descriptive name for your campaign.")
                campaign_description = st.text_area("Description (Optional)", help="Briefly describe the goal or purpose of this campaign.")

                icp_options = {icp['id']: icp['name'] for icp in available_icps}
                offering_options = {offering['id']: offering['name'] for offering in available_offerings}

                selected_icp_id = st.selectbox(
                    "Select Ideal Customer Profile (ICP) (Optional)", 
                    options=[None] + list(icp_options.keys()),
                    format_func=lambda x: "None" if x is None else icp_options.get(x, "Unknown ICP"),
                    key="create_camp_icp_select"
                )
                selected_offering_id = st.selectbox(
                    "Select Offering (Optional)", 
                    options=[None] + list(offering_options.keys()),
                    format_func=lambda x: "None" if x is None else offering_options.get(x, "Unknown Offering"),
                    key="create_camp_offering_select"
                )
                
                is_active = st.checkbox("Activate campaign after AI generates emails?", value=False, help="Activates the campaign once steps are ready.")

                submitted = st.form_submit_button("Create Campaign & Generate Emails")

                if submitted:
                    if not campaign_name:
                        st.error("Campaign Name is required.")
                    else:
                        campaign_data = {
                            "name": campaign_name,
                            "description": campaign_description or None,
                            "icp_id": selected_icp_id,
                            "offering_id": selected_offering_id,
                            "is_active": is_active
                        }
                        st.info("Creating campaign and triggering AI email generation... This may take a few moments.")
                        created_campaign_response = create_new_campaign(campaign_data, auth_token)
                        if created_campaign_response:
                            st.session_state.campaign_action_success = f"Campaign '{created_campaign_response.get('name')}' created! AI is generating steps."
                            st.session_state.campaigns_loaded = False # Force reload list
                            st.session_state.show_campaign_create_form = False # Hide form
                            st.balloons()
                            st.rerun()
                        else:
                            st.session_state.campaign_action_error = "Failed to create campaign (see error above if any)."
                            # No rerun, so error message from helper stays visible

        # --- Display Campaigns List ---
        st.markdown("---")
        st.subheader("📚 Existing Campaigns")
        if st.button("🔄 Refresh List", key="refresh_campaign_list_button"):
            st.session_state.campaigns_loaded = False
            st.rerun()

        if not campaign_list and st.session_state.campaigns_loaded:
            st.info("No campaigns defined yet. Click 'Create New Campaign Goal' to start.")
        elif campaign_list:
            for campaign in campaign_list:
                camp_id = campaign.get('id')
                if not camp_id: continue
                with st.container(border=True):
                    col_name, col_details, col_status, col_actions = st.columns([3,3,2,2])
                    with col_name:
                        st.markdown(f"**{campaign.get('name', 'Unnamed Campaign')}**")
                        if campaign.get('description'):
                            st.caption(f"{campaign['description'][:60]}{'...' if len(campaign['description']) > 60 else ''}")
                    with col_details:
                        st.caption(f"ICP: `{campaign.get('icp_name', 'None')}`")
                        st.caption(f"Offering: `{campaign.get('offering_name', 'None')}`")
                    with col_status:
                        active_icon = "✅ Active" if campaign.get('is_active') else "⏸️ Inactive"
                        st.markdown(active_icon)
                        
                        ai_status = campaign.get('ai_status', 'unknown').replace('_', ' ').capitalize()
                        ai_status_md = f"AI: `{ai_status}`"
                        if campaign.get('ai_status') == "generating": ai_status_md = f"AI: ⏳ `{ai_status}`"
                        elif campaign.get('ai_status') == "completed": ai_status_md = f"AI: ✔️ `{ai_status}`"
                        elif "failed" in campaign.get('ai_status', ''): ai_status_md = f"AI: ❌ `{ai_status}`"
                        st.markdown(ai_status_md)

                    with col_actions:
                        if st.button("👁️ View", key=f"view_camp_{camp_id}", help="View Details & Steps", use_container_width=True):
                            st.session_state.view_campaign_id = camp_id
                            st.session_state.show_campaign_create_form = False # Hide create form if open
                            st.rerun()
                        # Add Edit/Delete buttons later if needed, linked to backend capabilities
                        # if st.button("✏️", key=f"edit_camp_simple_{camp_id}", help="Edit Basic Info", use_container_width=True):
                        #    st.warning("Edit campaign (basic info) not yet implemented.")
                        # if st.button("🗑️", key=f"del_camp_simple_{camp_id}", help="Delete Campaign", use_container_width=True):
                        #    st.warning("Delete campaign not yet implemented.")
        st.markdown("---")
        
        # --- Conditionally Display Campaign Details & Steps ---
        if st.session_state.get('view_campaign_id') is not None:
            campaign_id_to_view = st.session_state.view_campaign_id
            st.subheader(f"🔍 Campaign Details & AI-Generated Steps")

            with st.spinner(f"Loading details for campaign ID {campaign_id_to_view}..."):
                campaign_details_data = get_campaign_details(campaign_id_to_view, auth_token)

            if campaign_details_data:
                st.markdown(f"#### {campaign_details_data.get('name')}")
                st.caption(f"ID: {campaign_details_data.get('id')} | Status: {'Active' if campaign_details_data.get('is_active') else 'Inactive'} | AI: {campaign_details_data.get('ai_status','N/A').replace('_',' ').capitalize()}")
                st.markdown(f"**Description:** {campaign_details_data.get('description', '_No description_')}")
                st.markdown(f"**Linked ICP:** {campaign_details_data.get('icp_name', '_None_')}")
                st.markdown(f"**Linked Offering:** {campaign_details_data.get('offering_name', '_None_')}")
                               
                created_dt = campaign_details_data.get('created_at')
                if created_dt:
                    try: # Handle potential Z for UTC
                        dt_obj = datetime.fromisoformat(created_dt.replace('Z', '+00:00'))
                        st.caption(f"Created: {dt_obj.strftime('%Y-%m-%d %H:%M %Z') if dt_obj.tzinfo else dt_obj.strftime('%Y-%m-%d %H:%M')}")
                    except ValueError:
                        st.caption(f"Created: {created_dt} (could not parse date)")


                steps = campaign_details_data.get('steps', [])
                if not steps and campaign_details_data.get('ai_status') not in ["generating", "pending", "failed", "failed_llm_empty", "failed_config"]: # Added failure states
                     st.warning("No steps found for this campaign. AI generation might have failed or produced no steps.", icon="⚠️")
                elif not steps and campaign_details_data.get('ai_status') in ["generating", "pending"]:
                     st.info(f"AI is currently {campaign_details_data.get('ai_status')} steps. Please refresh or check back soon.", icon="⏳")
                elif steps:
                    st.markdown("##### ✉️ Email Steps:")
                    for step in sorted(steps, key=lambda x: x.get('step_number', 0)):
                        # ... (Your existing step expander code) ...
                        exp_title = f"Step {step.get('step_number')}: {step.get('subject_template', 'No Subject')}"
                        exp_title += f" (Delay: {step.get('delay_days')} days)"
                        with st.expander(exp_title):
                            st.markdown(f"**Follow-up Angle:** `{step.get('follow_up_angle', 'N/A')}`")
                            st.markdown(f"**Subject Template:**")
                            st.code(step.get('subject_template', ''), language='text')
                            st.markdown(f"**Body Template:**")
                            st.text_area(
                                f"body_display_{campaign_id_to_view}_{step.get('id')}",
                                value=step.get('body_template', ''),
                                height=250,
                                disabled=True,
                                key=f"body_text_display_{campaign_id_to_view}_{step.get('id')}" # Ensure unique key
                            )
                            st.caption(f"Step ID: {step.get('id')} | AI Crafted: {'Yes' if step.get('is_ai_crafted') else 'No'}")

                  # ***** --- INSERT ACTIVATION CONTROLS HERE --- *****
                st.markdown("---") # Separator before controls
                current_is_active = campaign_details_data.get('is_active', False)
                current_ai_status = campaign_details_data.get('ai_status')

                # Conditions for activation: AI completed/partial, not already active, and has steps
                can_activate = current_ai_status in ["completed", "completed_partial"] and not current_is_active and steps

                col1_act, col2_act, col3_act = st.columns([1,1,2]) # Adjust layout as needed

                with col1_act:
                    if can_activate:
                        if st.button("✅ Activate Campaign", key=f"activate_camp_{campaign_id_to_view}", type="primary", help="Make this campaign ready to enroll leads."):
                            with st.spinner("Activating campaign..."):
                                success = activate_deactivate_campaign_in_api(campaign_id_to_view, True, auth_token)
                            if success:
                                st.session_state.campaign_action_success = "Campaign activated successfully!"
                                st.session_state.campaigns_loaded = False
                                # Clear view state after action might be good practice
                                if 'view_campaign_id' in st.session_state: del st.session_state.view_campaign_id
                                st.rerun()
                            else:
                                st.session_state.campaign_action_error = "Failed to activate campaign."
                                st.rerun() # Rerun to show error

                with col2_act:
                    if current_is_active:
                        if st.button("⏸️ Deactivate Campaign", key=f"deactivate_camp_{campaign_id_to_view}", type="secondary", help="Stop this campaign from enrolling new leads."):
                             with st.spinner("Deactivating campaign..."):
                                 success = activate_deactivate_campaign_in_api(campaign_id_to_view, False, auth_token)
                             if success:
                                 st.session_state.campaign_action_success = "Campaign deactivated successfully."
                                 st.session_state.campaigns_loaded = False
                                 if 'view_campaign_id' in st.session_state: del st.session_state.view_campaign_id
                                 st.rerun()
                             else:
                                st.session_state.campaign_action_error = "Failed to deactivate campaign."
                                st.rerun() # Rerun to show error

                # --- Option for AI Regeneration (Simple Version) ---
                # Show if generation is completed or failed
                if current_ai_status in ["completed", "completed_partial", "failed", "failed_llm_empty", "failed_config"]:
                    with col3_act: # Place in the third column
                         if st.button("🔄 Ask AI to Regenerate Steps", key=f"regen_camp_{campaign_id_to_view}", help="Delete current steps and ask AI to generate a new sequence."):
                            # --- TODO: Implement Backend endpoint like POST /campaigns/{id}/regenerate ---
                            st.warning("Regeneration feature is not yet implemented in the backend.")
                            # Example API call (needs backend endpoint first):
                            # if trigger_regeneration_in_api(campaign_id_to_view, auth_token):
                            #    st.info("AI regeneration request sent. Refresh the page in a few moments to see the new status.")
                            #    # Update status locally or wait for refresh
                            # else:
                            #    st.error("Failed to trigger AI regeneration.")


                # --- Close Details Button ---
                st.markdown("---") # Separator before close button
                if st.button("🔙 Close Details", key=f"hide_details_btn_{campaign_id_to_view}"):
                    if 'view_campaign_id' in st.session_state: del st.session_state.view_campaign_id
                    st.rerun()
            # --- Error Handling for Details Fetch ---
            else: # campaign_details_data is None
                st.error(f"Could not load details for campaign ID: {campaign_id_to_view}. It might have been deleted or an error occurred.")
                if st.button("Return to Campaign List", key="return_from_detail_error"):
                    if 'view_campaign_id' in st.session_state: del st.session_state.view_campaign_id
                    st.rerun()

  
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
            st.subheader("💡 Offerings / Value Propositions")
            st.caption("Define the products or services you offer to your target customers.")

            # --- Initialize Session State Flags for this Tab ---
            st.session_state.setdefault('offerings_list', [])
            st.session_state.setdefault('offerings_loaded', False)
            st.session_state.setdefault('show_offering_form', False) # Controls form visibility
            st.session_state.setdefault('offering_form_data', {}) # Data for pre-filling form
            st.session_state.setdefault('offering_being_edited_id', None) # Track if editing or creating
            st.session_state.setdefault('offering_to_delete', None) # Store Offering for delete confirmation

            # --- Display Action Messages ---
            if st.session_state.get('offering_action_success', None):
                st.success(st.session_state.offering_action_success)
                del st.session_state['offering_action_success'] # Clear flag

            if st.session_state.get('offering_action_error', None):
                st.error(st.session_state.offering_action_error)
                del st.session_state['offering_action_error'] # Clear flag

            # --- Load Data ---
            if not st.session_state.offerings_loaded:
                with st.spinner("Loading offerings list..."):
                    fetched_offerings = list_offerings(auth_token) # Call API helper
                    if fetched_offerings is not None:
                        st.session_state['offerings_list'] = fetched_offerings
                    else:
                        st.session_state['offerings_list'] = []
                        # Error displayed by helper if load failed
                    st.session_state.offerings_loaded = True

            # Get current list from session state
            offering_list = st.session_state.get('offerings_list', [])

            # --- Display Offerings List and Actions ---
            st.markdown("---")
            col_offer_header_1, col_offer_header_2 = st.columns([4, 1])
            with col_offer_header_1:
                 st.markdown("##### Defined Offerings")
            with col_offer_header_2:
                 if st.button("✚ Add New Offering", use_container_width=True):
                     st.session_state.offering_form_data = {"is_active": True} # Default to active
                     st.session_state.offering_being_edited_id = None
                     st.session_state.show_offering_form = True
                     st.rerun()

            if not offering_list and st.session_state.offerings_loaded:
                st.info("No offerings defined yet. Click 'Add New Offering' to create one.")
            elif offering_list:
                # Display each offering
                for offering in offering_list:
                    offering_id = offering.get('id')
                    with st.container(border=True):
                        col_off_info, col_off_edit, col_off_delete = st.columns([4, 1, 1])
                        with col_off_info:
                            status_icon = "✅" if offering.get('is_active') else "⏸️"
                            st.markdown(f"{status_icon} **{offering.get('name', 'Unnamed Offering')}** (ID: {offering_id})")
                            if offering.get('description'):
                                st.caption(f"{offering['description'][:100]}{'...' if len(offering['description']) > 100 else ''}")

                        with col_off_edit:
                             edit_key = f"edit_off_{offering_id}"
                             if st.button("Edit", key=edit_key, type="secondary", use_container_width=True):
                                 st.session_state.offering_form_data = offering # Pre-fill
                                 st.session_state.offering_being_edited_id = offering_id # Set ID
                                 st.session_state.show_offering_form = True # Show form
                                 st.rerun()

                        with col_off_delete:
                             delete_key = f"delete_off_{offering_id}"
                             if st.button("Delete", key=delete_key, type="primary", use_container_width=True):
                                 # Check if backend function is implemented
                                 if 'delete_offering' in locals() or 'delete_offering' in globals():
                                     st.session_state.offering_to_delete = offering # Store for confirm
                                     st.rerun()
                                 else:
                                     st.warning("Delete functionality not yet implemented in backend.")


            st.markdown("---")

            # --- Delete Confirmation Dialog ---
            if st.session_state.get('offering_to_delete') is not None:
                offering_for_deletion = st.session_state.offering_to_delete

                @st.dialog("Confirm Offering Deletion", dismissed=lambda: st.session_state.pop('offering_to_delete', None))
                def show_offering_delete_dialog():
                    st.warning(f"Are you sure you want to delete the offering **'{offering_for_deletion.get('name', 'N/A')}'** (ID: {offering_for_deletion.get('id')})?", icon="⚠️")
                    st.caption("This action cannot be undone.")
                    col_del_confirm, col_del_cancel = st.columns(2)
                    with col_del_confirm:
                        if st.button("Yes, Delete Offering", type="primary", use_container_width=True):
                             with st.spinner("Deleting Offering..."):
                                 # Use the actual delete helper function
                                 success = delete_existing_offering(offering_for_deletion['id'], auth_token)

                             if success:
                                 st.session_state.offering_action_success = f"Offering '{offering_for_deletion.get('name')}' deleted."
                                 st.session_state.offerings_loaded = False # Force reload list
                             else:
                                 # Error message handled by delete_existing_offering
                                 st.session_state.offering_action_error = "Failed to delete offering." # Generic fallback
                             # Clear deletion state regardless of success/failure before rerun
                             del st.session_state.offering_to_delete
                             st.rerun()

                    with col_del_cancel:
                        if st.button("Cancel", use_container_width=True):
                            del st.session_state.offering_to_delete # Just remove flag
                            st.rerun()

                show_offering_delete_dialog() # Show the dialog

            # --- Conditionally Display Offering Create/Edit Form ---
            if st.session_state.get('show_offering_form', False):
                form_title = "Edit Offering" if st.session_state.get('offering_being_edited_id') else "Add New Offering"
                st.markdown(f"#### {form_title}")
                form_data = st.session_state.get('offering_form_data', {})

                with st.form("offering_form"):
                    # --- Form Fields ---
                    name = st.text_input("Offering Name:", value=form_data.get("name", ""), key="off_form_name", placeholder="e.g., Cloud Migration Package")
                    description = st.text_area("Description:", value=form_data.get("description", ""), key="off_form_desc", height=100, placeholder="Briefly describe the offering...")
                    key_features = st.text_area("Key Features (one per line):", value="\n".join(form_data.get("key_features", [])), key="off_form_features", height=100, help="List the main components or benefits.")
                    target_pain_points = st.text_area("Target Pain Points (one per line):", value="\n".join(form_data.get("target_pain_points", [])), key="off_form_pains", height=100, help="What problems does this offering solve?")
                    call_to_action = st.text_input("Suggested Call to Action:", value=form_data.get("call_to_action", ""), key="off_form_cta", placeholder="e.g., Book a demo, Download whitepaper")
                    is_active = st.toggle("Active Offering", value=bool(form_data.get("is_active", True)), key="off_form_active", help="Inactive offerings won't be used in new campaigns.")

                    st.divider()

                    # --- Form Buttons ---
                    submitted = st.form_submit_button("💾 Save Offering")
                    cancel_clicked = st.form_submit_button("Cancel", type="secondary")

                    if cancel_clicked:
                        st.session_state.show_offering_form = False
                        st.session_state.offering_form_data = {}
                        st.session_state.offering_being_edited_id = None
                        st.rerun()

                    if submitted:
                        # --- Validation and Saving ---
                        can_save = True
                        offering_name = st.session_state.off_form_name.strip()
                        if not offering_name: st.error("Offering Name cannot be empty."); can_save = False

                        if can_save:
                            # Process list inputs
                            features_list = [f.strip() for f in st.session_state.off_form_features.split('\n') if f.strip()]
                            pains_list = [p.strip() for p in st.session_state.off_form_pains.split('\n') if p.strip()]

                            offering_payload = {
                                "name": offering_name,
                                "description": st.session_state.off_form_desc.strip() or None,
                                "key_features": features_list,
                                "target_pain_points": pains_list,
                                "call_to_action": st.session_state.off_form_cta.strip() or None,
                                "is_active": st.session_state.off_form_active
                            }

                            # --- Call Correct API ---
                            offering_id_to_update = st.session_state.get('offering_being_edited_id')
                            success = False
                            result_data = None
                            with st.spinner("Saving Offering..."):
                                if offering_id_to_update: # UPDATE mode
                                    result_data = update_existing_offering(offering_id_to_update, offering_payload, auth_token)
                                else: # CREATE mode
                                     result_data = create_new_offering(offering_payload, auth_token)
                                success = result_data is not None

                            if success:
                                action = "updated" if offering_id_to_update else "created"
                                st.session_state.offering_action_success = f"Offering '{offering_name}' {action} successfully!"
                                st.session_state.offerings_loaded = False # Force reload list
                                st.session_state.show_offering_form = False # Hide form
                                st.session_state.offering_form_data = {}
                                st.session_state.offering_being_edited_id = None
                                st.rerun()
                            else:
                                 # Specific errors handled by helpers, show generic if needed
                                 st.session_state.offering_action_error = "Failed to save offering."
                                 st.rerun() # Rerun to show error message

        # --- Email Sending Tab ---
        with tab3:
            st.subheader("📧 Email Sending Configuration")
            st.caption("Configure how SalesTroopz will send emails on your behalf.")

            # --- Initialize State ---
            st.session_state.setdefault('email_settings_loaded', False)
            st.session_state.setdefault('current_email_settings', None)

            # --- Display Messages ---
            if st.session_state.get('email_save_success', False):
                st.success("✅ Email settings saved successfully!")
                del st.session_state['email_save_success']
            if st.session_state.get('email_save_error', None):
                st.error(st.session_state.email_save_error)
                del st.session_state['email_save_error']

            # --- Load Data ---
            if not st.session_state.email_settings_loaded:
                with st.spinner("Loading email settings..."):
                    settings_data = get_email_settings(auth_token)
                    st.session_state.current_email_settings = settings_data # Store dict or None
                    st.session_state.email_settings_loaded = True

            current_settings = st.session_state.current_email_settings

            # --- Display Current Status ---
            st.markdown("---")
            if current_settings and current_settings.get('is_configured'):
                st.markdown("##### Current Configuration:")
                st.markdown(f"**Provider:** `{current_settings.get('provider_type', 'N/A').upper()}`")
                st.markdown(f"**Sender Email:** `{current_settings.get('verified_sender_email', 'N/A')}`")
                st.markdown(f"**Sender Name:** `{current_settings.get('sender_name', 'N/A')}`")
                cred_status = "Set" if current_settings.get('credentials_set') else "Not Set / Incomplete"
                st.markdown(f"**Credentials Status:** `{cred_status}`")
            elif current_settings:
                 st.warning("Email sending is not fully configured. Please complete the setup below.", icon="⚠️")
            else:
                 st.info("Email sending is not yet configured. Please select a provider and enter details below.")
            st.markdown("---")

            # --- Configuration Form ---
            st.markdown("#### Configure Email Sending:")
            with st.form("email_settings_form"):
                current_provider = current_settings.get('provider_type') if current_settings else None

                # Provider Selection
                provider_options = ["Not Configured", "SMTP", "AWS_SES"] # Add more later
                provider_display = {"Not Configured": "Not Configured", "SMTP": "Generic SMTP", "AWS_SES": "AWS SES (API Keys)"}
                # Find index for current setting, default to 0 ("Not Configured")
                current_index = 0
                if current_provider and current_provider in provider_options:
                     current_index = provider_options.index(current_provider)

                selected_provider_key = st.selectbox(
                    "Email Provider:",
                    options=provider_options,
                    format_func=lambda x: provider_display.get(x, x),
                    index=current_index,
                    key="email_provider_select",
                    help="Choose your email sending method."
                )

                # Common Fields
                st.text_input(
                    "Verified Sender Email:",
                    value=current_settings.get('verified_sender_email', '') if current_settings else '',
                    key="email_sender_email",
                    placeholder="e.g., sales@yourcompany.com",
                    help="The email address emails will be sent from (must be verified with your provider)."
                )
                st.text_input(
                    "Sender Name:",
                    value=current_settings.get('sender_name', '') if current_settings else '',
                    key="email_sender_name",
                    placeholder="e.g., Sales Team or John Doe",
                    help="The name recipients will see in the 'From' field."
                )

                # --- SMTP Specific Fields ---
                if selected_provider_key == "SMTP":
                    st.divider()
                    st.markdown("**SMTP Server Details**")
                    st.text_input("SMTP Host:", value=current_settings.get('smtp_host', '') if current_settings else '', key="email_smtp_host", placeholder="e.g., smtp.example.com")
                    st.number_input("SMTP Port:", value=current_settings.get('smtp_port', 587) if current_settings else 587, min_value=1, max_value=65535, step=1, key="email_smtp_port", help="Usually 587 (TLS) or 465 (SSL).")
                    st.text_input("SMTP Username:", value=current_settings.get('smtp_username', '') if current_settings else '', key="email_smtp_user")
                    st.text_input("SMTP Password:", type="password", key="email_smtp_pass", help="Leave blank to keep existing password.")

                # --- AWS SES Specific Fields ---
                elif selected_provider_key == "AWS_SES":
                    st.divider()
                    st.markdown("**AWS SES Details (using API Keys)**")
                    st.caption("Ensure the backend service has appropriate AWS permissions or credentials set via environment variables if using IAM roles instead of keys here.")
                    st.text_input("AWS Access Key ID:", type="password", key="email_aws_key_id", help="Leave blank to keep existing key.")
                    st.text_input("AWS Secret Access Key:", type="password", key="email_aws_secret", help="Leave blank to keep existing secret.")
                    st.text_input("AWS Region:", value=current_settings.get('aws_region', '') if current_settings else '', key="email_aws_region", placeholder="e.g., us-east-1", help="The AWS region where your SES is configured.")


                st.divider()
                is_configured_toggle = st.toggle(
                    "Mark as Fully Configured",
                    value=bool(current_settings.get('is_configured', False)) if current_settings else False,
                    key="email_is_configured",
                    help="Enable this only when you believe all necessary settings for the chosen provider are correctly entered."
                )

                submitted = st.form_submit_button("💾 Save Email Settings")

                if submitted:
                    # --- Prepare Payload ---
                    payload = {
                        "provider_type": selected_provider_key if selected_provider_key != "Not Configured" else None,
                        "verified_sender_email": st.session_state.email_sender_email.strip() or None,
                        "sender_name": st.session_state.email_sender_name.strip() or None,
                        "is_configured": is_configured_toggle
                    }

                    # Add provider-specific fields based on selection
                    if selected_provider_key == "SMTP":
                        payload["smtp_host"] = st.session_state.email_smtp_host.strip() or None
                        payload["smtp_port"] = st.session_state.email_smtp_port # Already int
                        payload["smtp_username"] = st.session_state.email_smtp_user.strip() or None
                        # Only include password if user entered something (don't overwrite with blank)
                        if st.session_state.email_smtp_pass:
                            payload["smtp_password"] = st.session_state.email_smtp_pass

                    elif selected_provider_key == "AWS_SES":
                        payload["aws_region"] = st.session_state.email_aws_region.strip() or None
                        # Only include keys if user entered something
                        if st.session_state.email_aws_key_id:
                            payload["aws_access_key_id"] = st.session_state.email_aws_key_id
                        if st.session_state.email_aws_secret:
                            payload["aws_secret_access_key"] = st.session_state.email_aws_secret

                    # --- Basic Validation ---
                    can_save = True
                    if payload["provider_type"] and not payload["verified_sender_email"]:
                        st.error("Verified Sender Email is required when a provider is selected.")
                        can_save = False
                    # Add more provider-specific validation if needed

                    # --- API Call ---
                    if can_save:
                        with st.spinner("Saving email settings..."):
                            result = save_email_settings(payload, auth_token)

                        if result:
                            st.session_state.email_save_success = True
                            st.session_state.email_settings_loaded = False # Force reload
                        else:
                            st.session_state.email_save_error = "Failed to save email settings." # Specific error shown by helper
                        st.rerun()
    # End of Page Content `if/elif/else` block
    else:
        st.error("Page not found.") # Should not be reachable with st.radio
