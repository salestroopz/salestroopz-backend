# streamlit_app.py
# Main application file for SalesTroopz Streamlit Frontend

import os
import streamlit as st
import requests
import time # json is not explicitly used for parsing if requests.json() is preferred
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta

# --- Page Configuration (Call ONCE at the top) ---
st.set_page_config(
    page_title="SalesTroopz",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Configuration & Constants ---
BACKEND_URL = os.getenv("BACKEND_API_URL")
if not BACKEND_URL:
    st.error("FATAL ERROR: BACKEND_API_URL environment variable is not set. Application cannot connect to the backend.", icon="🚨")
    st.stop()

# API Endpoints
LOGIN_ENDPOINT = f"{BACKEND_URL}/api/v1/auth/token"
REGISTER_ENDPOINT = f"{BACKEND_URL}/api/v1/auth/register"
LEADS_ENDPOINT = f"{BACKEND_URL}/api/v1/leads"
ICPS_ENDPOINT = f"{BACKEND_URL}/api/v1/icps"
OFFERINGS_ENDPOINT = f"{BACKEND_URL}/api/v1/offerings"
CAMPAIGNS_ENDPOINT = f"{BACKEND_URL}/api/v1/campaigns"
EMAIL_SETTINGS_ENDPOINT = f"{BACKEND_URL}/api/v1/email-settings"
ICP_MATCHING_ENDPOINT = f"{BACKEND_URL}/api/v1/icp-matching" # Added for completeness

# Default Timeout for API requests
API_TIMEOUT_SECONDS = 20
LONG_API_TIMEOUT_SECONDS = 120 # For uploads or long processes


# --- Session State Initialization ---
def initialize_session_state():
    """Initializes all necessary session state keys if they don't exist."""
    defaults = {
        "authenticated": False,
        "auth_token": None,
        "user_email": None,
        "view": "Login",  # Controls Login/Sign Up/Main App view
        "nav_radio": "Dashboard",  # For sidebar navigation

        # Leads Page State
        "leads_list": [],
        "leads_loaded": False,
        "show_lead_form": False,
        "lead_form_data": {},
        "lead_being_edited_id": None,
        "lead_to_delete": None,
        "lead_to_view_details": None,
        "upload_summary": None,
        "selected_leads_for_enrollment": {},
        "show_enroll_leads_dialog": False,
        "lead_action_success": None,
        "lead_action_error": None,

        # Campaign Page State
        "campaigns_list": [],
        "campaigns_loaded": False,
        "show_campaign_create_form": False,
        "view_campaign_id": None,
        "available_icps_for_campaign": [],
        "available_icps_for_campaign_loaded": False,
        "available_offerings_for_campaign": [],
        "available_offerings_for_campaign_loaded": False,
        "campaign_action_success": None,
        "campaign_action_error": None,

        # Config Page - ICP Tab State
        "icps_list_config_tab": [],
        "icps_loaded_config_tab": False,
        "show_icp_form_config_tab": False,
        "icp_form_data_config_tab": {},
        "icp_being_edited_id_config_tab": None,
        "icp_to_delete_config_tab": None,
        "icp_action_success_config_tab": None,
        "icp_action_error_config_tab": None,

        # Config Page - Offerings Tab State
        "offerings_list_config_tab": [],
        "offerings_loaded_config_tab": False,
        "show_offering_form_config_tab": False,
        "offering_form_data_config_tab": {},
        "offering_being_edited_id_config_tab": None,
        "offering_to_delete_config_tab": None,
        "offering_action_success_config_tab": None,
        "offering_action_error_config_tab": None,

        # Config Page - Email Settings Tab State
        "email_settings_current_config_tab": None,
        "email_settings_loaded_config_tab": False,
        "email_settings_save_success_config_tab": None,
        "email_settings_save_error_config_tab": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)

initialize_session_state()


# --- Authentication Functions ---
def login_user(email, password) -> Optional[str]:
    try:
        response = requests.post(
            LOGIN_ENDPOINT,
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=API_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            st.error("Login failed: No access token received.")
            return None
        st.session_state.user_email = email # Store user email
        return access_token
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401:
            st.error("Login failed: Incorrect email or password.")
        else:
            try:
                detail = http_err.response.json().get('detail', http_err.response.text)
            except requests.exceptions.JSONDecodeError:
                detail = http_err.response.text
            st.error(f"Login failed: HTTP {http_err.response.status_code} - {detail[:200]}")
        return None
    except Exception as e:
        st.error(f"Login failed: An unexpected error occurred - {e}")
        return None

def register_user(org_name, email, password) -> bool:
    payload = {"email": email, "password": password, "organization_name": org_name}
    try:
        response = requests.post(REGISTER_ENDPOINT, json=payload, timeout=API_TIMEOUT_SECONDS)
        if response.status_code == 201:
            st.success("Registration successful! Please log in.")
            return True
        else:
            try:
                detail = response.json().get('detail', 'Unknown error')
            except requests.exceptions.JSONDecodeError:
                detail = response.text
            st.error(f"Registration failed: {response.status_code} - {detail[:200]}")
            return False
    except Exception as e:
        st.error(f"Registration failed: An unexpected error occurred - {e}")
        return False

def logout_user():
    # More targeted clearing of session state
    keys_to_reset = [
        "authenticated", "auth_token", "user_email",
        "leads_list", "leads_loaded", "campaigns_list", "campaigns_loaded",
        # Add other data-specific keys if they should be cleared on logout
    ]
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key] # Or set to default if preferred

    initialize_session_state() # Re-initialize to defaults, ensures 'view' goes to 'Login'
    st.session_state["authenticated"] = False
    st.session_state["auth_token"] = None
    st.session_state["user_email"] = None
    st.session_state["view"] = "Login"

    st.success("Logged out successfully.")
    time.sleep(0.5)
    st.rerun()

def get_auth_headers() -> Dict[str, str]:
    token = st.session_state.get("auth_token")
    if not token:
        st.error("Authentication token is missing. Please log in again.")
        logout_user() # Force logout
        st.stop() # Stop execution for this request
    return {"Authorization": f"Bearer {token}"}

# --- Generic API Helper Functions ---
def _handle_api_error(e: Exception, action: str = "perform action"):
    """Generic error handler for API calls."""
    if isinstance(e, requests.exceptions.HTTPError):
        if e.response.status_code == 401:
            st.error("Authentication failed or session expired. Please log in again.")
            logout_user() # This will rerun and stop
        else:
            try:
                detail = e.response.json().get('detail', e.response.text)
            except requests.exceptions.JSONDecodeError:
                detail = e.response.text
            st.error(f"Failed to {action}: HTTP {e.response.status_code} - {detail[:250]}")
    elif isinstance(e, requests.exceptions.RequestException):
        st.error(f"Failed to {action}: Connection error - {e}")
    else:
        st.error(f"Failed to {action}: An unexpected error occurred - {e}")

def make_api_request(
    method: str,
    endpoint: str,
    auth_required: bool = True,
    json_payload: Optional[Dict] = None,
    data_payload: Optional[Dict] = None,
    files_payload: Optional[Dict] = None,
    params: Optional[Dict] = None,
    timeout: int = API_TIMEOUT_SECONDS,
    custom_headers: Optional[Dict] = None
) -> Optional[Any]:
    """Makes an authenticated API request."""
    try:
        headers = get_auth_headers() if auth_required else {}
        if custom_headers:
            headers.update(custom_headers)

        response = requests.request(
            method,
            endpoint,
            headers=headers,
            json=json_payload,
            data=data_payload,
            files=files_payload,
            params=params,
            timeout=timeout
        )
        response.raise_for_status()
        if response.status_code == 204:  # No Content
            return True # Indicates success for operations like DELETE
        return response.json()
    except Exception as e:
        action_description = f"{method.lower()} data at {endpoint.replace(BACKEND_URL, '')}"
        _handle_api_error(e, action_description)
        return None

# --- Specific API Service Functions ---

# Leads
def list_leads_api(skip: int = 0, limit: int = 100) -> Optional[List[Dict]]:
    return make_api_request("GET", f"{LEADS_ENDPOINT}/", params={"skip": skip, "limit": limit})

def create_lead_api(payload: Dict) -> Optional[Dict]:
    return make_api_request("POST", f"{LEADS_ENDPOINT}/", json_payload=payload)

def get_lead_details_api(lead_id: int) -> Optional[Dict]: # Added stub
    return make_api_request("GET", f"{LEADS_ENDPOINT}/{lead_id}")

def update_lead_api(lead_id: int, payload: Dict) -> Optional[Dict]:
    return make_api_request("PUT", f"{LEADS_ENDPOINT}/{lead_id}", json_payload=payload)

def delete_lead_api(lead_id: int) -> bool:
    return make_api_request("DELETE", f"{LEADS_ENDPOINT}/{lead_id}") is not None

def upload_leads_csv_api(uploaded_file) -> Optional[Dict[str, Any]]:
    endpoint = f"{LEADS_ENDPOINT}/bulk_upload/" # Ensure this endpoint exists
    files_data = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
    return make_api_request(
        "POST",
        endpoint,
        files_payload=files_data,
        timeout=LONG_API_TIMEOUT_SECONDS
    )

# ICPs
def list_icps_api() -> Optional[List[Dict]]:
    return make_api_request("GET", f"{ICPS_ENDPOINT}/")

def create_icp_api(payload: Dict) -> Optional[Dict]: # Added stub
    return make_api_request("POST", f"{ICPS_ENDPOINT}/", json_payload=payload)

def update_icp_api(icp_id: int, payload: Dict) -> Optional[Dict]: # Added stub
    return make_api_request("PUT", f"{ICPS_ENDPOINT}/{icp_id}", json_payload=payload)

def delete_icp_api(icp_id: int) -> bool: # Added stub
    return make_api_request("DELETE", f"{ICPS_ENDPOINT}/{icp_id}") is not None

# Offerings
def list_offerings_api() -> Optional[List[Dict]]:
    return make_api_request("GET", f"{OFFERINGS_ENDPOINT}/")

def create_offering_api(payload: Dict) -> Optional[Dict]: # Added stub
    return make_api_request("POST", f"{OFFERINGS_ENDPOINT}/", json_payload=payload)

def update_offering_api(offering_id: int, payload: Dict) -> Optional[Dict]: # Added stub
    return make_api_request("PUT", f"{OFFERINGS_ENDPOINT}/{offering_id}", json_payload=payload)

def delete_offering_api(offering_id: int) -> bool: # Added stub
    return make_api_request("DELETE", f"{OFFERINGS_ENDPOINT}/{offering_id}") is not None

# Email Settings
def get_email_settings_api() -> Optional[Dict]:
    return make_api_request("GET", f"{EMAIL_SETTINGS_ENDPOINT}/")

def save_email_settings_api(payload: Dict) -> Optional[Dict]: # Added stub
    return make_api_request("PUT", f"{EMAIL_SETTINGS_ENDPOINT}/", json_payload=payload)


# Campaigns
def list_campaigns_api(active_only: Optional[bool] = None) -> Optional[List[Dict]]:
    params = {}
    if active_only is not None:
        params["active_only"] = active_only
    return make_api_request("GET", f"{CAMPAIGNS_ENDPOINT}/", params=params)

def create_campaign_api(campaign_payload: Dict[str, Any]) -> Optional[Dict]:
    return make_api_request("POST", f"{CAMPAIGNS_ENDPOINT}/", json_payload=campaign_payload)

def get_campaign_details_api(campaign_id: int) -> Optional[Dict]:
    return make_api_request("GET", f"{CAMPAIGNS_ENDPOINT}/{campaign_id}")

def update_campaign_api(campaign_id: int, campaign_payload: Dict[str, Any]) -> Optional[Dict]:
    return make_api_request("PUT", f"{CAMPAIGNS_ENDPOINT}/{campaign_id}", json_payload=campaign_payload)

def activate_deactivate_campaign_api(campaign_id: int, is_active_status: bool) -> bool:
    return update_campaign_api(campaign_id, {"is_active": is_active_status}) is not None

def enroll_leads_in_campaign_api(campaign_id: int, lead_ids: List[int]) -> Optional[Dict]:
    return make_api_request(
        "POST",
        f"{CAMPAIGNS_ENDPOINT}/{campaign_id}/enroll_leads",
        json_payload={"lead_ids": lead_ids},
        timeout=LONG_API_TIMEOUT_SECONDS / 2 # e.g., 60 seconds
    )

def enroll_matched_icp_leads_api(campaign_id: int) -> Optional[Dict]:
    return make_api_request("POST", f"{CAMPAIGNS_ENDPOINT}/{campaign_id}/enroll_matched_icp_leads")

# --- NEW API Helper for Dashboard ---
def get_actionable_replies_api(token: str, limit: int = 50) -> Optional[List[Dict]]:
    """Fetches a list of actionable email replies for the dashboard."""
    endpoint = f"{BACKEND_URL}/api/v1/dashboard/actionable_replies" # Use your defined endpoint
    params = {"limit": limit}
    response_data = get_authenticated_request(endpoint, token, params=params)
    if isinstance(response_data, list):
        return response_data
    return None

# --- UI Helper/Callback Functions for Leads Page ---
# Moved outside the loop for clarity and efficiency
def _set_lead_view_state(lead_data: Dict):
    st.session_state.lead_to_view_details = lead_data
    st.session_state.show_lead_form = False
    st.session_state.show_enroll_leads_dialog = False
    st.rerun()

def _set_lead_edit_state(lead_data: Dict, lead_id: int):
    st.session_state.lead_form_data = lead_data
    st.session_state.lead_being_edited_id = lead_id
    st.session_state.show_lead_form = True
    st.session_state.show_enroll_leads_dialog = False
    st.session_state.lead_to_view_details = None # Clear other views
    st.rerun()

def _set_lead_delete_state(lead_data: Dict):
    st.session_state.lead_to_delete = lead_data
    st.session_state.show_lead_form = False
    st.session_state.show_enroll_leads_dialog = False
    st.rerun()

# --- Page Rendering Functions ---

def render_dashboard_page():
    st.header("📊 Dashboard")
    st.write("Welcome to SalesTroopz! Key metrics and insights will appear here.")
    st.info("Dashboard content (appointment funnel, campaign summaries) to be implemented.")

# --- Section: Actionable Email Replies ---
    st.markdown("---")
    st.subheader("🔥 Actionable Email Replies")
    st.caption("These replies have been AI-classified as needing your attention for follow-up or appointment scheduling.")

    # Initialize/Load Actionable Replies
    # Use a unique session state key for dashboard-specific loading if needed, or just rely on the general one.
    if 'dashboard_actionable_replies_loaded' not in st.session_state or \
       not st.session_state.dashboard_actionable_replies_loaded or \
       st.session_state.get('force_dashboard_refresh', False): # Add a way to force refresh
        
        with st.spinner("Loading actionable replies..."):
            fetched_actionable_replies = get_actionable_replies_api(auth_token) # Use your API helper
            st.session_state.actionable_replies_list_dashboard = fetched_actionable_replies if fetched_actionable_replies is not None else []
            st.session_state.dashboard_actionable_replies_loaded = True
            if 'force_dashboard_refresh' in st.session_state:
                del st.session_state.force_dashboard_refresh

    actionable_replies = st.session_state.get('actionable_replies_list_dashboard', [])

    if st.button("🔄 Refresh Actionable Replies", key="refresh_actionable_replies_dashboard_btn"):
        st.session_state.dashboard_actionable_replies_loaded = False # Force reload on next run
        st.rerun()

    if not actionable_replies and st.session_state.dashboard_actionable_replies_loaded: # Check loaded flag
        st.info("🎉 No new actionable replies to review at this time. Great job, or keep those campaigns running!")
    elif actionable_replies:
        st.markdown(f"You have **{len(actionable_replies)}** AI-flagged replies requiring your action:")
        
        # Using st.columns for a more structured layout
        # Define column headers (optional, but good for clarity)
        # cols_header = st.columns([2, 2, 2, 3, 1.5])
        # with cols_header[0]: st.caption("**Lead Name**")
        # with cols_header[1]: st.caption("**Company**")
        # with cols_header[2]: st.caption("**Campaign**")
        # with cols_header[3]: st.caption("**AI Classification & Summary**")
        # with cols_header[4]: st.caption("**Action**")
        # st.markdown("---")


        for reply_item in actionable_replies:
            # Display the reply item
            # lead_campaign_status_id is the primary key of the lead_campaign_status table
            # latest_reply_id is the primary key of the email_replies table
            # We need lead_id for the perform_lead_campaign_action_api
            
            lcs_id = reply_item.get('lead_campaign_status_id') 
            reply_db_id = reply_item.get('latest_reply_id') # This ID is for the email_replies table
            lead_id_for_action = reply_item.get('lead_id') # Needed for the action API

            if not lcs_id or not lead_id_for_action: 
                logger.warning(f"Dashboard: Skipping actionable reply due to missing lcs_id or lead_id: {reply_item}")
                continue 

            with st.container(border=True):
                col_info, col_summary, col_actions_dash = st.columns([2.5, 3, 1]) # Adjusted for button size
                
                with col_info:
                    st.markdown(f"**Lead:** {reply_item.get('lead_name', 'N/A')}")
                    st.caption(f"Email: {reply_item.get('lead_email', 'N/A')}")
                    st.caption(f"Company: {reply_item.get('lead_company', 'N/A')}")
                    st.markdown(f"**Campaign:** `{reply_item.get('campaign_name', 'N/A')}`")
                    
                    received_at_str = reply_item.get('latest_reply_received_at')
                    if received_at_str:
                        try:
                            received_dt = datetime.fromisoformat(received_at_str.replace('Z', '+00:00'))
                            st.caption(f"Reply Received: {received_dt.strftime('%Y-%m-%d %H:%M')}")
                        except:
                            st.caption(f"Reply Received: {received_at_str}")
                    else:
                        st.caption("Reply Received: N/A")


                with col_summary:
                    classification = str(reply_item.get('latest_reply_ai_classification', 'N/A')).replace('_', ' ').capitalize()
                    classification_icon = "⭐" if "Positive" in classification else \
                                          "❓" if "Question" in classification else \
                                          "⛔" if "Negative" in classification else \
                                          "➡️" # Default for other types
                    st.markdown(f"**AI Classification:** {classification_icon} `{classification}`")
                    st.markdown(f"**AI Summary:**")
                    st.caption(f"{reply_item.get('latest_reply_ai_summary', '_No AI summary available._')}")
                    
                    # Snippet of the actual reply
                    if reply_item.get('latest_reply_snippet'):
                        with st.expander("View Reply Snippet (AI Cleaned)"):
                            st.code(reply_item.get('latest_reply_snippet'), language='text')

                with col_actions_dash:
                    # This button will set session state to show the detailed "Review & Act" dialog
                    # We pass reply_item itself, as the dialog might need multiple fields from it.
                    def set_review_state(item_data):
                        st.session_state.reply_item_to_review = item_data # Store the whole item
                        st.session_state.show_reply_review_dialog = True
                        # No st.rerun() here, dialog will show conditionally in the same script run
                    
                    if st.button("Review & Act", key=f"review_act_dashboard_btn_{reply_db_id if reply_db_id else lcs_id}", type="primary", use_container_width=True):
                        # Store the entire reply_item dict in session_state for the dialog to use
                        st.session_state.reply_item_to_review = reply_item 
                        st.session_state.show_reply_review_dialog = True
                        st.rerun() # Rerun to make the dialog appear immediately

        st.markdown("---")

    # --- Main Dashboard Metrics (Placeholder for now) ---
    st.subheader("📊 Overall Campaign Performance")
    # This section will be populated once you have data from campaign execution and appointment marking
    # Example placeholders:
    # total_appointments = get_total_appointments_api(auth_token) # New API helper needed
    # active_campaign_count = get_active_campaign_count_api(auth_token) # New API helper needed
    
    # st.metric("Total Appointments Set", total_appointments.get('count', 0) if total_appointments else "N/A")
    # st.metric("Active Campaigns", active_campaign_count.get('count', 0) if active_campaign_count else "N/A")
    st.info("Overall performance metrics (e.g., total appointments, campaign success rates) will be displayed here once campaigns are running and responses are processed.")


# --- The "Review & Act" Dialog (MUST be defined globally in streamlit_app.py, not inside a function) ---
# This ensures it can be shown as an overlay regardless of the current page.
# It uses st.session_state.show_reply_review_dialog and st.session_state.reply_item_to_review

if st.session_state.get('show_reply_review_dialog') and st.session_state.get('reply_item_to_review') is not None:
    reply_details_from_dashboard = st.session_state.reply_item_to_review # This dict comes from actionable_replies_list
    auth_token_for_dialog = st.session_state.get("auth_token") # Get token for API calls

    # Extract necessary IDs and info
    lead_id_for_action = reply_details_from_dashboard.get('lead_id')
    # lead_campaign_status_id_for_action = reply_details_from_dashboard.get('lead_campaign_status_id') # This ID is for lead_campaign_status table
    # reply_db_id_for_action = reply_details_from_dashboard.get('latest_reply_id') # This ID is for email_replies table

    # For the dialog title and some displayed info:
    lead_name_for_dialog = reply_details_from_dashboard.get('lead_name', 'N/A')
    campaign_name_for_dialog = reply_details_from_dashboard.get('campaign_name', 'N/A')
    ai_classification_for_dialog = str(reply_details_from_dashboard.get('latest_reply_ai_classification', 'N/A')).replace('_',' ').capitalize()
    ai_summary_for_dialog = reply_details_from_dashboard.get('latest_reply_ai_summary', 'N/A')
    
    # Fetch full cleaned reply text - this might require another API call if snippet is not enough
    # For now, we use the snippet.
    # Ideally: full_cleaned_reply_text = get_full_reply_text_api(reply_db_id_for_action, auth_token_for_dialog)
    cleaned_reply_text_for_dialog = reply_details_from_dashboard.get('latest_reply_snippet', "Full reply text not available in this view. (TODO: Fetch full text).")


    # Using st.dialog if available and suitable, or a custom modal-like container
    # For simplicity, we'll use a conditional container block
    with st.container(border=True): # This will appear as a distinct block on the page
        st.subheader(f"📧 Review & Act on Reply from: {lead_name_for_dialog}")
        st.caption(f"Campaign: `{campaign_name_for_dialog}` | Current AI Classification: `{ai_classification_for_dialog}`")
        st.markdown(f"**AI Summary:** {ai_summary_for_dialog}")
        
        st.markdown("##### Full Reply Text (Cleaned Snippet):")
        st.text_area("Reply Content", value=cleaned_reply_text_for_dialog, height=200, disabled=True, key=f"reply_text_dialog_{lead_id_for_action}")

        st.markdown("---")
        st.markdown("##### **Your Action:**")
        
        with st.form(key=f"reply_action_form_{lead_id_for_action}"):
            action_notes_for_dialog = st.text_area("Your Notes for this action (optional):", key=f"dialog_action_notes_{lead_id_for_action}", height=75)
            
            # Appointment Setting
            st.markdown("**Appointment Management:**")
            appointment_details_for_dialog = st.text_input("Appointment Reference Details (if set manually):", 
                                                           placeholder="e.g., May 25th 2pm via Google Cal, invite sent", 
                                                           key=f"dialog_appt_details_{lead_id_for_action}")
            
            col_appt_set, col_positive_other = st.columns(2)
            with col_appt_set:
                if st.form_submit_button("🗓️ Mark Appointment Set", type="primary", use_container_width=True):
                    if not appointment_details_for_dialog: # Check if input has value
                        st.warning("Please enter appointment details before marking as set.")
                    else:
                        with st.spinner("Marking appointment..."):
                            response = perform_lead_campaign_action_api(
                                lead_id_for_action, LeadCampaignActionType.APPOINTMENT_SET, 
                                action_notes_for_dialog, appointment_details_for_dialog, auth_token_for_dialog
                            )
                        if response: 
                            st.success("Appointment marked. Lead paused in campaign.")
                            st.session_state.show_reply_review_dialog = False; st.session_state.actionable_replies_loaded = False
                            st.rerun()
                        # API helper shows error

            with col_positive_other:
                if st.form_submit_button("⭐ Positive Reply (No Appt Yet)", use_container_width=True):
                    with st.spinner("Marking positive reply..."):
                        response = perform_lead_campaign_action_api(
                            lead_id_for_action, LeadCampaignActionType.POSITIVE_REPLY, 
                            action_notes_for_dialog, None, auth_token_for_dialog
                        )
                    if response: 
                        st.success("Marked as positive reply. Lead paused in campaign for manual follow-up.")
                        st.session_state.show_reply_review_dialog = False; st.session_state.actionable_replies_loaded = False
                        st.rerun()
            
            st.markdown("---")
            st.markdown("**Other Actions:**")
            col_manual, col_unsub, col_ignore = st.columns(3)
            with col_manual:
                if st.form_submit_button("🗣️ Needs Manual Follow-Up", use_container_width=True):
                    with st.spinner("Marking for manual follow-up..."):
                        response = perform_lead_campaign_action_api(lead_id_for_action, LeadCampaignActionType.MANUAL_PAUSE, action_notes_for_dialog, None, auth_token_for_dialog)
                    if response: st.success("Marked for manual follow-up. Campaign paused for this lead."); st.session_state.show_reply_review_dialog = False; st.session_state.actionable_replies_loaded = False; st.rerun()
            
            with col_unsub:
                if st.form_submit_button("🛑 Mark Unsubscribed", type="secondary", use_container_width=True):
                    with st.spinner("Marking unsubscribed..."):
                        response = perform_lead_campaign_action_api(lead_id_for_action, LeadCampaignActionType.MARK_UNSUBSCRIBED, action_notes_for_dialog, None, auth_token_for_dialog)
                    if response: st.success("Marked unsubscribed. Lead removed from sequence."); st.session_state.show_reply_review_dialog = False; st.session_state.actionable_replies_loaded = False; st.rerun()

            with col_ignore: # Placeholder for "Incorrect Classification / Ignore"
                if st.form_submit_button("⚠️ Ignore/Dismiss AI Flag", use_container_width=True):
                    # This action might just mark the email_reply as actioned or change LCS status if AI paused it.
                    # Requires specific backend logic for "ignore" if it means more than just closing this dialog.
                    st.info("Action: 'Ignore AI Flag' - This would typically mark the reply as reviewed.")
                    st.session_state.show_reply_review_dialog = False; st.session_state.actionable_replies_loaded = False
                    st.rerun()
        
        st.markdown("---")
        st.info(f"Reminder: Send calendar invites or reply manually from your configured email account.")
        if st.button("🔙 Close Review Dialog", key="close_review_dialog_main_btn"):
            st.session_state.show_reply_review_dialog = False
            st.session_state.actionable_replies_loaded = False # To refresh dashboard list
            st.rerun()
    elif st.session_state.get('show_reply_review_dialog'): # If flag is true but no data (should not happen)
         st.error("Error: Could not load reply details for review.")
         st.session_state.show_reply_review_dialog = False # Reset
        st.rerun()

def render_leads_page():
    st.header("👤 Leads Management")
    st.caption("View, add, and manage your sales leads. Select leads to enroll them into campaigns.")

    # Display Action Messages
    if st.session_state.get('lead_action_success'):
        st.success(st.session_state.pop('lead_action_success'))
    if st.session_state.get('lead_action_error'): # Should be handled by _handle_api_error mostly
        st.error(st.session_state.pop('lead_action_error'))

    # Bulk CSV Upload Section
    with st.expander("📤 Bulk Import Leads from CSV", expanded=False):
        uploaded_file_leads = st.file_uploader("Choose a CSV file for leads", type=["csv"], key="leads_csv_uploader")
        if uploaded_file_leads:
            if st.button("🚀 Process Leads CSV", key="process_leads_csv_btn"):
                with st.spinner(f"Processing '{uploaded_file_leads.name}'..."):
                    summary = upload_leads_csv_api(uploaded_file_leads)
                    st.session_state.upload_summary = summary
                    st.session_state.leads_loaded = False  # Force reload
                    st.rerun()

    if st.session_state.get('upload_summary'):
        s = st.session_state.pop('upload_summary')
        st.markdown("---")
        st.markdown("#### CSV Import Summary:")
        if s: # Check if summary is not None (API call might have failed)
            st.info(f"- Total: {s.get('total_rows_in_file', 'N/A')}, "
                    f"Attempted: {s.get('rows_attempted', 'N/A')}, "
                    f"Successful: {s.get('successfully_imported_or_updated', 'N/A')}, "
                    f"Failed: {s.get('failed_imports', 'N/A')}")

            errors_list = s.get('errors', [])
            if errors_list:
                with st.expander(f"View {len(errors_list)} Import Errors/Issues"):
                    for i, err in enumerate(errors_list[:15]):
                        st.error(f"Row {err.get('row_number', '?')} "
                                 f"(Email: {err.get('email', '?')}) - Error: {err.get('error')}")
                    if len(errors_list) > 15:
                        st.caption(f"...and {len(errors_list) - 15} more issues.")
        else:
            st.error("Could not retrieve CSV import summary. The upload might have failed.")


    # Load Lead List Data
    if not st.session_state.get('leads_loaded', False):
        with st.spinner("Loading leads..."):
            st.session_state.leads_list = list_leads_api() or []
            st.session_state.leads_loaded = True
    lead_list_data = st.session_state.get('leads_list', [])

    # UI to Trigger Enrollment for Selected Leads
    currently_selected_lead_ids = [
        lead_id for lead_id, is_selected
        in st.session_state.get('selected_leads_for_enrollment', {}).items() if is_selected
    ]
    if currently_selected_lead_ids:
        st.markdown("---")
        col_enroll_btn_ui, _ = st.columns([1, 2])
        with col_enroll_btn_ui:
            if st.button(f"➡️ Enroll {len(currently_selected_lead_ids)} Selected Lead(s) into Campaign", key="enroll_selected_leads_btn", use_container_width=True):
                st.session_state.show_enroll_leads_dialog = True
                st.session_state.show_lead_form = False # Hide other forms
                st.session_state.lead_to_view_details = None
                st.session_state.lead_to_delete = None
                st.rerun()
    elif st.session_state.get('leads_loaded') and lead_list_data:
        st.caption("Select leads using the checkboxes below to enable bulk enrollment.")

    # "All Leads" Section Header & Add New Lead Button
    st.markdown("---")
    col_all_leads_header, col_add_lead_btn = st.columns([3, 1])
    with col_all_leads_header:
        st.markdown("##### All Leads")
    with col_add_lead_btn:
        if st.button("✚ Add New Lead", use_container_width=True, key="add_new_lead_btn"):
            st.session_state.update(lead_form_data={}, lead_being_edited_id=None, show_lead_form=True,
                                    show_enroll_leads_dialog=False, lead_to_view_details=None, lead_to_delete=None)
            st.rerun()

    # Main Lead List Display
    if not lead_list_data and st.session_state.get('leads_loaded'):
        st.info("No leads found. Click 'Add New Lead' or upload a CSV to get started.")
    elif lead_list_data:
        list_header_cols = st.columns([0.6, 4, 1.5])
        with list_header_cols[0]:
            all_selected = len(currently_selected_lead_ids) == len(lead_list_data) if lead_list_data else False
            new_select_all_state = st.checkbox("All", value=all_selected, key="select_all_leads_cb", help="Select/Deselect all leads")
            if new_select_all_state != all_selected:
                for lead_item in lead_list_data:
                    st.session_state.setdefault('selected_leads_for_enrollment', {})[lead_item['id']] = new_select_all_state
                st.rerun()
        with list_header_cols[1]: st.caption("Lead Information")
        with list_header_cols[2]: st.caption("Actions")

        for lead_item in lead_list_data:
            lead_id = lead_item.get("id")
            if not lead_id: continue

            with st.container(border=True):
                item_cols = st.columns([0.5, 4, 1.5])
                with item_cols[0]:
                    is_selected = st.session_state.get('selected_leads_for_enrollment', {}).get(lead_id, False)
                    new_selection = st.checkbox("", value=is_selected, key=f"cb_lead_{lead_id}")
                    if new_selection != is_selected:
                        st.session_state.setdefault('selected_leads_for_enrollment', {})[lead_id] = new_selection
                        st.rerun()
                with item_cols[1]:
                    st.markdown(f"**{lead_item.get('name', 'N/A')}** ({lead_item.get('email')})")
                    st.caption(f"Company: {lead_item.get('company', 'N/A')} | Title: {lead_item.get('title', 'N/A')}")
                    if lead_item.get('matched'):
                        reason = lead_item.get('reason', 'Matched')
                        st.caption(f"✅ ICP: {reason[:30]}{'...' if len(reason) > 30 else ''}")
                with item_cols[2]:
                    action_buttons_cols = st.columns(3)
                    action_buttons_cols[0].button("👁️", key=f"view_l_btn_{lead_id}", on_click=_set_lead_view_state, args=(lead_item,), help="View Details", use_container_width=True)
                    action_buttons_cols[1].button("✏️", key=f"edit_l_btn_{lead_id}", on_click=_set_lead_edit_state, args=(lead_item, lead_id), help="Edit Lead", use_container_width=True)
                    action_buttons_cols[2].button("🗑️", key=f"del_l_btn_{lead_id}", on_click=_set_lead_delete_state, args=(lead_item,), help="Delete Lead", use_container_width=True)

    # Enrollment Dialog
    if st.session_state.get('show_enroll_leads_dialog') and currently_selected_lead_ids:
        with st.container(border=True): # Simulates a modal
            with st.spinner("Loading active & ready campaigns..."):
                all_active_camps = list_campaigns_api(active_only=True)

            ready_campaigns_list = []
            if all_active_camps:
                ready_campaigns_list = [c for c in all_active_camps if c.get('is_active') and c.get('ai_status') in ['completed', 'completed_partial']]

            if not ready_campaigns_list:
                st.warning("No active campaigns with completed AI steps are available for enrollment.")
                if st.button("Close Enrollment", key="close_enroll_dialog_no_camps"):
                    st.session_state.show_enroll_leads_dialog = False; st.rerun()
            else:
                campaign_options_dict = {c['id']: f"{c['name']} (ICP: {c.get('icp_name', 'N/A')})" for c in ready_campaigns_list}
                with st.form("enroll_leads_dialog_form"):
                    st.subheader(f"Enroll {len(currently_selected_lead_ids)} Selected Lead(s)")
                    chosen_campaign_id = st.selectbox("Select Campaign:", options=list(campaign_options_dict.keys()), format_func=lambda x_id: campaign_options_dict.get(x_id, x_id), key="campaign_select_enroll_dialog")

                    form_cols = st.columns(2)
                    submit_enroll = form_cols[0].form_submit_button("✅ Confirm & Enroll", use_container_width=True, type="primary")
                    cancel_enroll = form_cols[1].form_submit_button("✖️ Cancel", use_container_width=True)

                    if cancel_enroll:
                        st.session_state.show_enroll_leads_dialog = False
                        st.session_state.selected_leads_for_enrollment = {} # Clear selection
                        st.rerun()
                    if submit_enroll:
                        if chosen_campaign_id and currently_selected_lead_ids:
                            with st.spinner(f"Enrolling leads into '{campaign_options_dict.get(chosen_campaign_id)}'..."):
                                response = enroll_leads_in_campaign_api(chosen_campaign_id, currently_selected_lead_ids)
                            if response:
                                st.success(f"{response.get('message', 'Done.')} Enrolled: {response.get('successful_enrollments', 0)}, Failed/Skipped: {response.get('failed_enrollments', 0)}.")
                                errors = response.get('details', [])
                                if errors and response.get('failed_enrollments', 0) > 0:
                                    with st.expander("View Enrollment Errors"):
                                        for err in errors: st.error(f"LeadID {err.get('lead_id', '?')}: {err.get('error', '?')}")
                                st.session_state.update(selected_leads_for_enrollment={}, show_enroll_leads_dialog=False, leads_loaded=False)
                                st.rerun()
                            # else: API helper shows error via _handle_api_error
                        elif not chosen_campaign_id:
                            st.error("Please select a campaign.")

    # View Lead Details Dialog
    if st.session_state.get('lead_to_view_details'):
        lead_to_view = st.session_state.lead_to_view_details
        with st.container(border=True): # Simulating a dialog
            st.subheader(f"Lead Details: {lead_to_view.get('name', lead_to_view.get('email'))}")
            display_fields = ['name', 'email', 'company', 'title', 'source', 'linkedin_profile',
                              'company_size', 'industry', 'location', 'matched', 'reason',
                              'crm_status', 'appointment_confirmed', 'icp_match_id', 'created_at', 'updated_at']
            for key in display_fields:
                val = lead_to_view.get(key)
                if val is not None:
                    disp_key = key.replace("_", " ").title()
                    if isinstance(val, bool):
                        st.markdown(f"**{disp_key}:** {'Yes' if val else 'No'}")
                    elif key in ['created_at', 'updated_at'] and isinstance(val, str):
                        try:
                            dt_val = datetime.fromisoformat(val.replace('Z', '+00:00'))
                            st.markdown(f"**{disp_key}:** {dt_val.strftime('%Y-%m-%d %H:%M')}")
                        except ValueError:
                            st.markdown(f"**{disp_key}:** {val}")
                    else:
                        st.markdown(f"**{disp_key}:** {val}")
            if st.button("Close Details", key="close_lead_view_dialog_btn"):
                st.session_state.lead_to_view_details = None
                st.rerun()
        st.markdown("---")

    # Delete Lead Confirmation Dialog
    if st.session_state.get('lead_to_delete'):
        lead_for_deletion = st.session_state.lead_to_delete
        with st.container(border=True):
            st.warning(f"Delete Lead: **{lead_for_deletion.get('name', lead_for_deletion.get('email'))}**?", icon="⚠️")
            del_confirm_cols = st.columns(2)
            if del_confirm_cols[0].button("Yes, Delete Lead", type="primary", key="confirm_delete_lead_dialog_btn"):
                with st.spinner("Deleting..."):
                    success = delete_lead_api(lead_for_deletion['id'])
                if success:
                    st.session_state.lead_action_success = "Lead deleted."
                st.session_state.leads_loaded = False
                st.session_state.lead_to_delete = None
                st.rerun()
            if del_confirm_cols[1].button("Cancel Deletion", key="cancel_delete_lead_dialog_btn"):
                st.session_state.lead_to_delete = None
                st.rerun()
        st.markdown("---")

    # Add/Edit Lead Form
    if st.session_state.get('show_lead_form'):
        form_title = "Edit Lead" if st.session_state.get('lead_being_edited_id') else "Add New Lead"
        st.subheader(form_title)
        form_data = st.session_state.get('lead_form_data', {})
        with st.form("lead_add_edit_form", clear_on_submit=False):
            name = st.text_input("Name:", value=form_data.get("name", ""), key="lead_form_name")
            email = st.text_input("Email*:", value=form_data.get("email", ""), key="lead_form_email")
            company = st.text_input("Company:", value=form_data.get("company", ""), key="lead_form_company")
            title = st.text_input("Title:", value=form_data.get("title", ""), key="lead_form_title")
            source = st.text_input("Source:", value=form_data.get("source", ""), key="lead_form_source")
            linkedin = st.text_input("LinkedIn Profile:", value=form_data.get("linkedin_profile", ""), key="lead_form_linkedin")
            # Add other fields as needed, e.g., company_size, industry, location, crm_status
            matched = st.checkbox("Matched ICP?", value=bool(form_data.get("matched", False)), key="lead_form_matched")
            appointment_confirmed = st.checkbox("Appointment Confirmed?", value=bool(form_data.get("appointment_confirmed", False)), key="lead_form_appt_confirmed")

            form_buttons_cols = st.columns(2)
            submit_btn = form_buttons_cols[0].form_submit_button("💾 Save Lead", use_container_width=True, type="primary")
            if form_buttons_cols[1].form_submit_button("✖️ Cancel", use_container_width=True):
                st.session_state.show_lead_form = False
                st.rerun()

            if submit_btn:
                if not email or not email.strip():
                    st.error("Email is required.")
                else:
                    payload = {
                        "name": name.strip() or None, "email": email.strip(),
                        "company": company.strip() or None, "title": title.strip() or None,
                        "source": source.strip() or None, "linkedin_profile": linkedin.strip() or None,
                        "matched": matched, "appointment_confirmed": appointment_confirmed
                        # Add other fields to payload
                    }
                    with st.spinner("Saving lead..."):
                        lead_id_edit = st.session_state.get('lead_being_edited_id')
                        if lead_id_edit:
                            result = update_lead_api(lead_id_edit, payload)
                        else:
                            result = create_lead_api(payload)

                    if result:
                        action = 'updated' if lead_id_edit else 'added'
                        st.session_state.lead_action_success = f"Lead '{payload['email']}' {action} successfully."
                        st.session_state.leads_loaded = False
                        st.session_state.show_lead_form = False
                        st.session_state.lead_being_edited_id = None
                        st.session_state.lead_form_data = {}
                        st.rerun()
                    # else: error is handled by _handle_api_error

def render_campaigns_page():
    st.header("📣 Campaign Management (AI-Powered)")
    st.caption("Create AI-generated email outreach campaigns, review steps, activate, and enroll leads.")

    if st.session_state.get('campaign_action_success'):
        st.success(st.session_state.pop('campaign_action_success'))
    # Errors are typically handled by _handle_api_error

    # Load Data
    if not st.session_state.get('campaigns_loaded', False):
        with st.spinner("Loading campaigns..."):
            st.session_state.campaigns_list = list_campaigns_api() or []
            st.session_state.campaigns_loaded = True

    if not st.session_state.get('available_icps_for_campaign_loaded', False):
        with st.spinner("Loading ICPs..."):
            st.session_state.available_icps_for_campaign = list_icps_api() or []
            st.session_state.available_icps_for_campaign_loaded = True

    if not st.session_state.get('available_offerings_for_campaign_loaded', False):
        with st.spinner("Loading Offerings..."):
            st.session_state.available_offerings_for_campaign = list_offerings_api() or []
            st.session_state.available_offerings_for_campaign_loaded = True

    campaign_list_data = st.session_state.get('campaigns_list', [])
    available_icps_data = st.session_state.get('available_icps_for_campaign', [])
    available_offerings_data = st.session_state.get('available_offerings_for_campaign', [])

    # Create New Campaign Section
    st.markdown("---")
    if st.button("🚀 Create New Campaign Goal", key="toggle_create_campaign_form_btn"):
        st.session_state.show_campaign_create_form = not st.session_state.get('show_campaign_create_form', False)
        if st.session_state.show_campaign_create_form:
            st.session_state.view_campaign_id = None # Hide details view
        st.rerun()

    if st.session_state.get('show_campaign_create_form', False):
        st.subheader("Define New Campaign Goal")
        with st.form("create_campaign_form", clear_on_submit=True):
            campaign_name = st.text_input("Campaign Name*", help="A clear, descriptive name.")
            campaign_description = st.text_area("Description (Optional)", height=100)

            icp_options_map = {icp['id']: icp['name'] for icp in available_icps_data}
            offering_options_map = {offering['id']: offering['name'] for offering in available_offerings_data}

            selected_icp_id = st.selectbox(
                "Link Ideal Customer Profile (ICP) (Optional)",
                options=[None] + list(icp_options_map.keys()),
                format_func=lambda x_id: "None - Generic" if x_id is None else icp_options_map.get(x_id, f"ID: {x_id}"),
                key="create_campaign_icp_select"
            )
            selected_offering_id = st.selectbox(
                "Link Offering (Optional)",
                options=[None] + list(offering_options_map.keys()),
                format_func=lambda x_id: "None - Generic" if x_id is None else offering_options_map.get(x_id, f"ID: {x_id}"),
                key="create_campaign_offering_select"
            )
            is_active_default = st.checkbox("Set active upon creation?", value=False, key="create_campaign_is_active_cb", help="Activate later after AI review.")

            submitted_create = st.form_submit_button("Create Campaign & Start AI Generation")

            if submitted_create:
                if not campaign_name.strip():
                    st.error("Campaign Name is required.")
                else:
                    payload = {
                        "name": campaign_name.strip(),
                        "description": campaign_description.strip() or None,
                        "icp_id": selected_icp_id,
                        "offering_id": selected_offering_id,
                        "is_active": is_active_default
                    }
                    with st.spinner("Creating campaign and triggering AI..."):
                        response = create_campaign_api(payload)
                    if response:
                        st.session_state.campaign_action_success = f"Campaign '{response.get('name')}' created! AI Status: {response.get('ai_status', 'pending').capitalize()}."
                        st.session_state.campaigns_loaded = False
                        st.session_state.show_campaign_create_form = False
                        st.balloons()
                        st.rerun()

    # Display Campaigns List
    st.markdown("---")
    st.subheader("📚 Existing Campaigns")
    if st.button("🔄 Refresh Campaign List", key="refresh_campaigns_btn"):
        st.session_state.campaigns_loaded = False
        st.rerun()

    if not campaign_list_data and st.session_state.get('campaigns_loaded'):
        st.info("No campaigns found. Click 'Create New Campaign Goal' to start!")
    elif campaign_list_data:
        for campaign_item in campaign_list_data:
            camp_id = campaign_item.get('id')
            if not camp_id: continue
            with st.container(border=True):
                cols = st.columns([3, 3, 2, 2])
                with cols[0]:
                    st.markdown(f"**{campaign_item.get('name', 'Unnamed')}**")
                    desc = campaign_item.get('description', '')
                    st.caption(f"{desc[:60]}{'...' if len(desc) > 60 else ''}")
                with cols[1]:
                    st.caption(f"ICP: `{campaign_item.get('icp_name', 'None')}`")
                    st.caption(f"Offering: `{campaign_item.get('offering_name', 'None')}`")
                with cols[2]:
                    st.markdown("✅ Active" if campaign_item.get('is_active') else "⏸️ Inactive")
                    ai_status = campaign_item.get('ai_status', 'N/A').replace('_', ' ').capitalize()
                    ai_icon = "✔️" if ai_status == "Completed" else "⏳" if ai_status == "Generating" else "⌛" if ai_status == "Pending" else "❌"
                    st.markdown(f"AI: {ai_icon} `{ai_status}`")
                with cols[3]:
                    if st.button("👁️ View/Manage", key=f"view_manage_camp_btn_{camp_id}", use_container_width=True):
                        st.session_state.view_campaign_id = camp_id
                        st.session_state.show_campaign_create_form = False
                        st.rerun()
    st.markdown("---")

    # Campaign Details & Management Section
    if st.session_state.get('view_campaign_id') is not None:
        campaign_id_to_show = st.session_state.view_campaign_id
        st.subheader(f"🔍 Campaign Details & Management (ID: {campaign_id_to_show})")

        with st.spinner(f"Loading details for Campaign ID {campaign_id_to_show}..."):
            details = get_campaign_details_api(campaign_id_to_show)

        if details:
            st.markdown(f"#### {details.get('name', 'N/A')}")
            active_text = "✅ Active" if details.get('is_active') else "⏸️ Inactive"
            ai_text = details.get('ai_status', 'N/A').replace('_', ' ').capitalize()
            st.caption(f"Status: {active_text} | AI: {ai_text}")

            with st.expander("Campaign Metadata", expanded=False):
                st.markdown(f"**Description:** {details.get('description', '_No description_')}")
                st.markdown(f"**Linked ICP:** {details.get('icp_name', '_None_')}")
                st.markdown(f"**Linked Offering:** {details.get('offering_name', '_None_')}")
                created_at = details.get('created_at')
                if created_at:
                    try:
                        dt_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        st.caption(f"Created: {dt_obj.strftime('%Y-%m-%d %H:%M %Z') if dt_obj.tzinfo else dt_obj.strftime('%Y-%m-%d %H:%M')}")
                    except: st.caption(f"Created: {created_at}")


            steps_data = details.get('steps', [])
            has_steps = bool(steps_data)
            ai_ready_for_activation = details.get('ai_status') in ["completed", "completed_partial"]

            if not has_steps and ai_text not in ["Generating", "Pending"]:
                st.warning("No steps found. AI might have failed or steps were deleted.", icon="⚠️")
            elif not has_steps and ai_text in ["Generating", "Pending"]:
                st.info(f"AI is currently {ai_text.lower()} steps. Refresh or check back.", icon="⏳")
            elif has_steps:
                st.markdown("##### ✉️ AI-Generated Email Steps (Review Only):")
                for step in sorted(steps_data, key=lambda x: x.get('step_number', 0)):
                    title = f"Step {step.get('step_number')}: {step.get('subject_template', 'No Subject')}"
                    title += f" (Delay: {step.get('delay_days')} days)"
                    with st.expander(title):
                        st.markdown(f"**Follow-up Angle:** `{step.get('follow_up_angle', 'N/A')}`")
                        st.markdown(f"**Subject Template:**"); st.code(step.get('subject_template', ''), language='text')
                        st.markdown(f"**Body Template:**")
                        st.text_area(f"body_disp_{step.get('id')}", value=step.get('body_template', ''), height=200, disabled=True, key=f"body_text_disp_{step.get('id')}")
                        st.caption(f"Step ID: {step.get('id')} | AI Crafted: {'Yes' if step.get('is_ai_crafted') else 'No'}")

            st.markdown("---")
            st.markdown("##### Manage Campaign:")
            action_cols = st.columns(3)

            with action_cols[0]: # Activation/Deactivation
                is_active = details.get('is_active', False)
                if ai_ready_for_activation and has_steps:
                    if not is_active:
                        if st.button("✅ Activate Campaign", key=f"activate_camp_detail_btn_{campaign_id_to_show}", type="primary", use_container_width=True):
                            with st.spinner("Activating..."):
                                success = activate_deactivate_campaign_api(campaign_id_to_show, True)
                            if success:
                                st.session_state.campaign_action_success = "Campaign activated!"
                                st.session_state.campaigns_loaded = False
                                del st.session_state.view_campaign_id
                                st.rerun()
                    else:
                        if st.button("⏸️ Deactivate Campaign", key=f"deactivate_camp_detail_btn_{campaign_id_to_show}", use_container_width=True):
                            with st.spinner("Deactivating..."):
                                success = activate_deactivate_campaign_api(campaign_id_to_show, False)
                            if success:
                                st.session_state.campaign_action_success = "Campaign deactivated!"
                                st.session_state.campaigns_loaded = False
                                del st.session_state.view_campaign_id
                                st.rerun()
                elif not has_steps and ai_ready_for_activation:
                    st.caption("Cannot activate: AI completed but no steps.")
                elif not ai_ready_for_activation:
                    st.caption(f"AI status: {ai_text}. Activation once steps are 'completed'.")

            with action_cols[1]: # Enroll Matched ICP Leads
                if is_active and details.get('icp_id') and ai_ready_for_activation and has_steps:
                    icp_name = details.get('icp_name', 'Linked ICP')
                    if st.button(f"➕ Enroll Matched ICP Leads", key=f"enroll_icp_leads_detail_btn_{campaign_id_to_show}", help=f"Enroll leads matching '{icp_name}'", use_container_width=True):
                        with st.spinner(f"Triggering enrollment for ICP '{icp_name}'..."):
                            enroll_resp = enroll_matched_icp_leads_api(campaign_id_to_show)
                        if enroll_resp:
                            st.info(f"{enroll_resp.get('message', 'Enrollment process triggered.')} Check logs for details.")
                elif not details.get('icp_id'): st.caption("Link ICP for smart enrollment.")
                elif not is_active: st.caption("Activate campaign to enroll.")
                elif not (ai_ready_for_activation and has_steps): st.caption("Steps must be AI-completed.")

            with action_cols[2]: # AI Regenerate Steps
                if ai_ready_for_activation or "failed" in details.get('ai_status', ''):
                    if st.button("🔄 AI Regenerate Steps", key=f"regenerate_camp_steps_btn_{campaign_id_to_show}", help="Ask AI for new steps (deletes current).", use_container_width=True):
                        st.warning("Backend for AI Regeneration not yet implemented.") # Placeholder

            st.markdown("---")
            if st.button("🔙 Close Campaign Details", key=f"close_camp_details_btn_{campaign_id_to_show}"):
                del st.session_state.view_campaign_id
                st.rerun()
        else:
            st.error(f"Could not load details for Campaign ID: {campaign_id_to_show}.")
            if st.button("Return to Campaigns List", key="return_to_camps_list_error_btn"):
                if 'view_campaign_id' in st.session_state: del st.session_state.view_campaign_id
                st.rerun()

def render_config_page_icp_tab():
    st.subheader("Ideal Customer Profiles (ICPs)")
    st.caption("Define target customer segments for your campaigns.")

    if st.session_state.get('icp_action_success_config_tab'):
        st.success(st.session_state.pop('icp_action_success_config_tab'))

    if not st.session_state.get('icps_loaded_config_tab'):
        with st.spinner("Loading ICPs..."):
            st.session_state.icps_list_config_tab = list_icps_api() or []
        st.session_state.icps_loaded_config_tab = True
    icp_list_cfg = st.session_state.get('icps_list_config_tab', [])

    st.markdown("---")
    col_icp_hdr1, col_icp_hdr2 = st.columns([3, 1])
    col_icp_hdr1.markdown("##### Saved ICPs")
    if col_icp_hdr2.button("✚ Add New ICP", use_container_width=True, key="add_icp_btn_cfg_tab"):
        st.session_state.update(icp_form_data_config_tab={}, icp_being_edited_id_config_tab=None, show_icp_form_config_tab=True)
        st.rerun()

    if not icp_list_cfg and st.session_state.get('icps_loaded_config_tab'):
        st.info("No ICPs defined yet.")
    elif icp_list_cfg:
        for icp in icp_list_cfg:
            icp_id = icp.get('id')
            if not icp_id: continue
            with st.container(border=True):
                cols = st.columns([4, 1, 1])
                cols[0].markdown(f"**{icp.get('name', 'N/A')}** (ID: {icp_id})")
                if cols[1].button("Edit", key=f"edit_icp_cfg_tab_{icp_id}", type="secondary", use_container_width=True):
                    st.session_state.update(icp_form_data_config_tab=icp, icp_being_edited_id_config_tab=icp_id, show_icp_form_config_tab=True)
                    st.rerun()
                if cols[2].button("Delete", key=f"del_icp_cfg_tab_{icp_id}", type="primary", use_container_width=True):
                    st.session_state.icp_to_delete_config_tab = icp
                    st.rerun()
    st.markdown("---")

    if st.session_state.get('icp_to_delete_config_tab'):
        icp_del = st.session_state.icp_to_delete_config_tab
        with st.container(border=True):
            st.warning(f"Delete ICP: **{icp_del.get('name')}**?", icon="⚠️")
            c1, c2 = st.columns(2)
            if c1.button("Yes, Delete", type="primary", key="confirm_del_icp_cfg_tab_btn"):
                with st.spinner("Deleting..."):
                    success = delete_icp_api(icp_del['id'])
                if success:
                    st.session_state.icp_action_success_config_tab = "ICP deleted."
                st.session_state.icps_loaded_config_tab = False
                del st.session_state.icp_to_delete_config_tab
                st.rerun()
            if c2.button("Cancel", key="cancel_del_icp_cfg_tab_btn"):
                del st.session_state.icp_to_delete_config_tab
                st.rerun()

    if st.session_state.get('show_icp_form_config_tab'):
        title = "Edit ICP" if st.session_state.get('icp_being_edited_id_config_tab') else "Add New ICP"
        st.subheader(title)
        data = st.session_state.get('icp_form_data_config_tab', {})
        with st.form("icp_form_cfg_tab", clear_on_submit=False):
            name = st.text_input("ICP Name*", value=data.get("name", ""))
            titles = st.text_area("Titles (one per line)", "\n".join(data.get("title_keywords", [])))
            inds = st.text_area("Industries (one per line)", "\n".join(data.get("industry_keywords", [])))
            locs = st.text_area("Locations (one per line)", "\n".join(data.get("location_keywords", [])))
            size_r = data.get("company_size_rules", {})
            min_s = st.number_input("Min Employees", value=size_r.get("min"), step=1, format="%d", min_value=0)
            max_s = st.number_input("Max Employees", value=size_r.get("max"), step=1, format="%d", min_value=0)
            if min_s is not None and max_s is not None and min_s > max_s and max_s > 0 : st.warning("Min employees cannot be greater than Max employees.")

            s_btn, c_btn = st.columns(2)
            if s_btn.form_submit_button("💾 Save ICP", use_container_width=True, type="primary"):
                if not name.strip():
                    st.error("ICP Name is required.")
                else:
                    payload = {
                        "name": name.strip(),
                        "title_keywords": [t.strip() for t in titles.split('\n') if t.strip()],
                        "industry_keywords": [i.strip() for i in inds.split('\n') if i.strip()],
                        "location_keywords": [l.strip() for l in locs.split('\n') if l.strip()],
                        "company_size_rules": ({k: v for k, v in [("min", min_s if min_s > 0 else None), ("max", max_s if max_s > 0 else None)] if v is not None} or None)
                    }
                    with st.spinner("Saving ICP..."):
                        id_edit = st.session_state.get('icp_being_edited_id_config_tab')
                        res = update_icp_api(id_edit, payload) if id_edit else create_icp_api(payload)
                    if res:
                        st.session_state.icp_action_success_config_tab = f"ICP '{res.get('name')}' {'updated' if id_edit else 'created'}."
                        st.session_state.update(icps_loaded_config_tab=False, show_icp_form_config_tab=False, icp_form_data_config_tab={}, icp_being_edited_id_config_tab=None)
                        # Also refresh ICP list for campaign creation
                        st.session_state.available_icps_for_campaign_loaded = False
                        st.rerun()
            if c_btn.form_submit_button("✖️ Cancel", use_container_width=True):
                st.session_state.show_icp_form_config_tab = False
                st.rerun()

def render_config_page_offerings_tab():
    st.subheader("💡 Offerings / Value Propositions")
    st.caption("Define the products or services you offer.")

    if st.session_state.get('offering_action_success_config_tab'):
        st.success(st.session_state.pop('offering_action_success_config_tab'))

    if not st.session_state.get('offerings_loaded_config_tab'):
        with st.spinner("Loading offerings..."):
            st.session_state.offerings_list_config_tab = list_offerings_api() or []
        st.session_state.offerings_loaded_config_tab = True
    off_list_cfg = st.session_state.get('offerings_list_config_tab', [])

    st.markdown("---")
    hd_off1, hd_off2 = st.columns([3, 1])
    hd_off1.markdown("##### Defined Offerings")
    if hd_off2.button("✚ Add Offering", use_container_width=True, key="add_off_btn_cfg_tab"):
        st.session_state.update(offering_form_data_config_tab={"is_active": True}, offering_being_edited_id_config_tab=None, show_offering_form_config_tab=True)
        st.rerun()

    if not off_list_cfg and st.session_state.get('offerings_loaded_config_tab'):
        st.info("No offerings defined yet.")
    elif off_list_cfg:
        for off in off_list_cfg:
            off_id = off.get('id')
            if not off_id: continue
            with st.container(border=True):
                c = st.columns([4, 1, 1])
                c[0].markdown(f"{'✅' if off.get('is_active') else '⏸️'} **{off.get('name', 'N/A')}** (ID:{off_id})")
                c[0].caption(f"{off.get('description', '')[:70]}...")
                if c[1].button("Edit", key=f"ed_off_cfg_tab_{off_id}", type="secondary", use_container_width=True):
                    st.session_state.update(offering_form_data_config_tab=off, offering_being_edited_id_config_tab=off_id, show_offering_form_config_tab=True)
                    st.rerun()
                if c[2].button("Delete", key=f"del_off_cfg_tab_{off_id}", type="primary", use_container_width=True):
                    st.session_state.offering_to_delete_config_tab = off
                    st.rerun()
    st.markdown("---")

    if st.session_state.get('offering_to_delete_config_tab'):
        off_del = st.session_state.offering_to_delete_config_tab
        with st.container(border=True):
            st.warning(f"Delete Offering: **{off_del.get('name')}**?", icon="⚠️")
            dc1, dc2 = st.columns(2)
            if dc1.button("Yes, Delete Offering", type="primary", key="confirm_del_off_cfg_tab_btn"):
                with st.spinner("Deleting..."):
                    suc = delete_offering_api(off_del['id'])
                if suc:
                    st.session_state.offering_action_success_config_tab = "Offering deleted."
                st.session_state.offerings_loaded_config_tab = False
                del st.session_state.offering_to_delete_config_tab
                st.rerun()
            if dc2.button("Cancel", key="cancel_del_off_cfg_tab_btn"):
                del st.session_state.offering_to_delete_config_tab
                st.rerun()

    if st.session_state.get('show_offering_form_config_tab'):
        tit_off = "Edit Offering" if st.session_state.get('offering_being_edited_id_config_tab') else "Add New Offering"
        st.subheader(tit_off)
        data_off = st.session_state.get('offering_form_data_config_tab', {})
        with st.form("offering_form_cfg_tab", clear_on_submit=False):
            n = st.text_input("Name*", value=data_off.get("name", ""))
            d = st.text_area("Description", value=data_off.get("description", ""))
            kf = st.text_area("Key Features (one per line)", "\n".join(data_off.get("key_features", [])))
            tp = st.text_area("Target Pain Points (one per line)", "\n".join(data_off.get("target_pain_points", [])))
            cta = st.text_input("Call to Action", value=data_off.get("call_to_action", ""))
            is_a = st.toggle("Active", value=bool(data_off.get("is_active", True)))

            sfo, cfo = st.columns(2)
            if sfo.form_submit_button("💾 Save Offering", use_container_width=True, type="primary"):
                if not n.strip():
                    st.error("Offering Name is required.")
                else:
                    pay = {
                        "name": n.strip(), "description": d.strip() or None, "is_active": is_a,
                        "key_features": [x.strip() for x in kf.split('\n') if x.strip()],
                        "target_pain_points": [x.strip() for x in tp.split('\n') if x.strip()],
                        "call_to_action": cta.strip() or None
                    }
                    with st.spinner("Saving offering..."):
                        id_e = st.session_state.get('offering_being_edited_id_config_tab')
                        rs = update_offering_api(id_e, pay) if id_e else create_offering_api(pay)
                    if rs:
                        st.session_state.offering_action_success_config_tab = f"Offering '{rs.get('name')}' {'updated' if id_e else 'created'}."
                        st.session_state.update(offerings_loaded_config_tab=False, show_offering_form_config_tab=False, offering_form_data_config_tab={}, offering_being_edited_id_config_tab=None)
                        # Also refresh offering list for campaign creation
                        st.session_state.available_offerings_for_campaign_loaded = False
                        st.rerun()
            if cfo.form_submit_button("✖️ Cancel", use_container_width=True):
                st.session_state.show_offering_form_config_tab = False
                st.rerun()

def render_config_page_email_tab():
    st.subheader("📧 Email Sending Setup")
    st.caption("Configure how SalesTroopz will send emails.")

    if st.session_state.get('email_settings_save_success_config_tab'):
        st.success(st.session_state.pop('email_settings_save_success_config_tab'))

    if not st.session_state.get('email_settings_loaded_config_tab'):
        with st.spinner("Loading email settings..."):
            st.session_state.email_settings_current_config_tab = get_email_settings_api()
            st.session_state.email_settings_loaded_config_tab = True
    current_email_cfg = st.session_state.get('email_settings_current_config_tab') or {}

    st.markdown("---")
    if current_email_cfg.get('is_configured') and current_email_cfg.get('provider_type'):
        st.markdown("##### Current Configuration:")
        st.info(f"**Provider:** `{current_email_cfg.get('provider_type', 'N/A').upper()}` | "
                f"**Sender:** `{current_email_cfg.get('verified_sender_email', 'N/A')}` "
                f"(`{current_email_cfg.get('sender_name', 'N/A')}`)")
    else:
        st.info("Email sending is not yet fully configured.")
    st.markdown("---")

    with st.form("email_settings_form_cfg_tab"):
        st.markdown("#### Configure Email Provider:")
        providers = ["Not Configured", "SMTP", "AWS_SES"]
        provider_map = {"Not Configured": "Select...", "SMTP": "Generic SMTP", "AWS_SES": "AWS SES (API Keys)"}
        current_prov_idx = providers.index(current_email_cfg.get('provider_type')) if current_email_cfg.get('provider_type') in providers else 0

        sel_provider = st.selectbox("Provider:", providers, format_func=lambda x: provider_map.get(x, x), index=current_prov_idx, key="email_provider_select_cfg")

        sender_email_val = st.text_input("Verified Sender Email*:", value=current_email_cfg.get('verified_sender_email', ''), key="email_sender_addr_cfg")
        sender_name_val = st.text_input("Sender Name* (Display Name):", value=current_email_cfg.get('sender_name', ''), key="email_sender_name_cfg")

        # Placeholders for form values to be accessed on submit
        smtp_host, smtp_port, smtp_user, smtp_pass = "", 587, "", ""
        aws_region, aws_key, aws_secret = "", "", ""

        if sel_provider == "SMTP":
            smtp_host = st.text_input("SMTP Host*:", value=current_email_cfg.get('smtp_host', ''), key="email_smtp_host_cfg")
            smtp_port = st.number_input("SMTP Port*:", value=int(current_email_cfg.get('smtp_port', 587)), min_value=1, max_value=65535, key="email_smtp_port_cfg")
            smtp_user = st.text_input("SMTP Username*:", value=current_email_cfg.get('smtp_username', ''), key="email_smtp_user_cfg")
            smtp_pass = st.text_input("SMTP Password:", type="password", key="email_smtp_pass_cfg", help="Leave blank to keep current if already set.")
        elif sel_provider == "AWS_SES":
            aws_region = st.text_input("AWS Region*:", value=current_email_cfg.get('aws_region', ''), key="email_aws_region_cfg")
            aws_key = st.text_input("AWS Access Key ID:", type="password", key="email_aws_key_cfg", help="Leave blank to keep current if already set.")
            aws_secret = st.text_input("AWS Secret Access Key:", type="password", key="email_aws_secret_cfg", help="Leave blank to keep current if already set.")

        is_cfg_toggle = st.toggle("Mark as Fully Configured & Ready to Send", value=bool(current_email_cfg.get('is_configured', False)), key="email_is_configured_toggle_cfg")

        if st.form_submit_button("💾 Save Email Settings"):
            payload = {
                "provider_type": sel_provider if sel_provider != "Not Configured" else None,
                "verified_sender_email": sender_email_val.strip() or None,
                "sender_name": sender_name_val.strip() or None,
                "is_configured": is_cfg_toggle
            }
            valid_save = True
            if payload["provider_type"] and (not payload["verified_sender_email"] or not payload["sender_name"]):
                st.error("Sender Email and Sender Name are required if a provider is selected.")
                valid_save = False

            if sel_provider == "SMTP":
                payload.update({
                    "smtp_host": smtp_host.strip() or None,
                    "smtp_port": smtp_port,
                    "smtp_username": smtp_user.strip() or None
                })
                if smtp_pass: payload["smtp_password"] = smtp_pass # Only include if provided
                # Check if essential SMTP fields are missing if it's a new SMTP setup or password is not set
                is_new_smtp_or_pass_missing = (
                    not (current_email_cfg.get('provider_type') == "SMTP" and current_email_cfg.get('credentials_set'))
                    and not smtp_pass
                )
                if not all([payload["smtp_host"], payload["smtp_port"], payload["smtp_username"]]) or is_new_smtp_or_pass_missing :
                     st.error("For SMTP, Host, Port, Username are required. Password is required on first setup or if changing.")
                     valid_save = False

            elif sel_provider == "AWS_SES":
                payload["aws_region"] = aws_region.strip() or None
                if aws_key: payload["aws_access_key_id"] = aws_key
                if aws_secret: payload["aws_secret_access_key"] = aws_secret

                is_new_aws_or_keys_missing = (
                    not (current_email_cfg.get('provider_type') == "AWS_SES" and current_email_cfg.get('credentials_set'))
                    and not (aws_key and aws_secret)
                )
                if not payload["aws_region"] or is_new_aws_or_keys_missing:
                    st.error("For AWS SES, Region is required. Access Key and Secret Key are required on first setup or if changing.")
                    valid_save = False

            if valid_save:
                with st.spinner("Saving email settings..."):
                    result = save_email_settings_api(payload)
                if result:
                    st.session_state.email_settings_save_success_config_tab = "Email settings saved."
                    st.session_state.email_settings_loaded_config_tab = False # Force reload
                    st.rerun()
                # else: error handled by API helper

def render_config_page():
    st.header("⚙️ Configuration")
    st.caption("Manage your core sales assets: Ideal Customer Profiles (ICPs), Offerings, and Email Sending settings.")

    tab_titles = ["🎯 ICP Definition", "💡 Offerings", "📧 Email Sending"]
    tab_icp, tab_offering, tab_email = st.tabs(tab_titles)

    with tab_icp:
        render_config_page_icp_tab()
    with tab_offering:
        render_config_page_offerings_tab()
    with tab_email:
        render_config_page_email_tab()

def render_setup_assistant_page():
    st.header("🤖 Setup Assistant")
    st.info("Guided setup and Q&A coming soon!")


# --- Main Application Logic ---
if not st.session_state["authenticated"]:
    st.title("SalesTroopz Portal")
    view_cols = st.columns([1,3,1]) # Centering hack
    with view_cols[1]:
        if st.session_state["view"] == "Login":
            st.subheader("Login")
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                login_button = st.form_submit_button("Login", use_container_width=True, type="primary")
                if login_button:
                    if not email or not password:
                        st.error("Please enter both email and password.")
                    else:
                        token = login_user(email, password)
                        if token:
                            st.session_state["authenticated"] = True
                            st.session_state["auth_token"] = token
                            st.session_state["user_email"] = email # Set on successful login
                            st.session_state["view"] = "App" # Switch to app view
                            st.rerun()
            st.markdown("---")
            if st.button("Don't have an account? Sign Up", key="go_to_signup_btn", use_container_width=True):
                st.session_state["view"] = "Sign Up"
                st.rerun()

        elif st.session_state["view"] == "Sign Up":
            st.subheader("Create Account")
            with st.form("signup_form"):
                org_name = st.text_input("Organization Name")
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                signup_button = st.form_submit_button("Sign Up", use_container_width=True, type="primary")

                if signup_button:
                    if not all([org_name, email, password, confirm_password]):
                        st.error("Please fill in all fields.")
                    elif password != confirm_password:
                        st.error("Passwords do not match.")
                    else:
                        if register_user(org_name, email, password):
                            st.session_state["view"] = "Login" # Go to login after successful registration
                            st.rerun()
            st.markdown("---")
            if st.button("Already have an account? Login", key="go_to_login_btn", use_container_width=True):
                st.session_state["view"] = "Login"
                st.rerun()
else:  # Authenticated User Flow
    with st.sidebar:
        st.image("https://salestroopz.com/wp-content/uploads/2024/01/cropped-SalesTroopz-Logos-1536x515.png", width=200)
        st.write(f"User: {st.session_state.get('user_email', 'N/A')}")
        st.divider()
        page_options = ["Dashboard", "Leads", "Campaigns", "Configuration", "Setup Assistant"]
        # Ensure nav_radio default is one of these options
        st.session_state.nav_radio = st.radio(
            "Navigate", page_options, key="main_nav_radio_sidebar",
            index=page_options.index(st.session_state.get("nav_radio", "Dashboard"))
        )
        st.divider()
        if st.button("Logout", key="logout_button_sidebar", use_container_width=True):
            logout_user() # This will rerun

    current_page_selected = st.session_state.nav_radio

    if current_page_selected == "Dashboard":
        render_dashboard_page()
    elif current_page_selected == "Leads":
        render_leads_page()
    elif current_page_selected == "Campaigns":
        render_campaigns_page()
    elif current_page_selected == "Configuration":
        render_config_page()
    elif current_page_selected == "Setup Assistant":
        render_setup_assistant_page()
    else:
        st.error("Page not found.")
