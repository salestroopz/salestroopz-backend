# streamlit_app.py
# Main application file for SalesTroopz Streamlit Frontend

import os
import streamlit as st
import requests
import json # If used for manual parsing, though requests.json() is preferred
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta # Ensure all are imported

# --- Page Configuration (Call ONCE at the top) ---
st.set_page_config(
    page_title="SalesTroopz",
    layout="wide",
    initial_sidebar_state="expanded" # Good default
)

# --- Configuration ---
BACKEND_URL = os.getenv("BACKEND_API_URL")
if not BACKEND_URL:
    st.error("FATAL ERROR: BACKEND_API_URL environment variable is not set. Application cannot connect to the backend.", icon="🚨")
    st.stop()

# Define API endpoints (ensure these are correct and comprehensive)
LOGIN_ENDPOINT = f"{BACKEND_URL}/api/v1/auth/token"
REGISTER_ENDPOINT = f"{BACKEND_URL}/api/v1/auth/register"
LEADS_ENDPOINT = f"{BACKEND_URL}/api/v1/leads"
ICPS_ENDPOINT = f"{BACKEND_URL}/api/v1/icps"
OFFERINGS_ENDPOINT = f"{BACKEND_URL}/api/v1/offerings"
CAMPAIGNS_ENDPOINT = f"{BACKEND_URL}/api/v1/campaigns"
EMAIL_SETTINGS_ENDPOINT = f"{BACKEND_URL}/api/v1/email-settings"
# Add other endpoints if you have them, e.g., for ICP Matching router
ICP_MATCHING_ENDPOINT = f"{BACKEND_URL}/api/v1/icp-matching"


# --- Authentication Functions ---
def login_user(email, password) -> Optional[str]:
    try:
        response = requests.post(LOGIN_ENDPOINT, data={"username": email, "password": password}, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=15)
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data.get("access_token")
        if not access_token: st.error("Login failed: No access token received."); return None
        return access_token
    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401: st.error("Login failed: Incorrect email or password.")
        else:
            try: detail = http_err.response.json().get('detail', http_err.response.text)
            except: detail = http_err.response.text
            st.error(f"Login failed: HTTP {http_err.response.status_code} - {detail[:200]}")
        return None
    except Exception as e: st.error(f"Login failed: An unexpected error occurred - {e}"); return None

def register_user(org_name, email, password) -> bool:
    payload = {"email": email, "password": password, "organization_name": org_name}
    try:
        response = requests.post(REGISTER_ENDPOINT, json=payload, timeout=15)
        if response.status_code == 201: st.success("Registration successful! Please log in."); return True
        else:
            try: detail = response.json().get('detail', 'Unknown error')
            except: detail = response.text
            st.error(f"Registration failed: {response.status_code} - {detail[:200]}"); return False
    except Exception as e: st.error(f"Registration failed: An unexpected error occurred - {e}"); return False

def logout_user():
    keys_to_clear = list(st.session_state.keys())
    for key in keys_to_clear:
        if key not in ['view']: # Example: keep 'view' if it controls login/signup visibility
            del st.session_state[key]
    st.session_state["authenticated"] = False # Explicitly set core auth flags
    st.session_state["auth_token"] = None
    st.session_state["user_email"] = None
    st.session_state['view'] = 'Login' # Ensure view resets to login
    st.success("Logged out successfully.")
    time.sleep(0.5) # Brief pause
    st.rerun()

# --- API Helper Functions ---
def get_auth_headers(token: Optional[str]) -> Dict[str, str]:
    if not token:
        st.error("Authentication token is missing. Please log in again.")
        logout_user() # Force logout
        st.stop() # Stop execution for this request
    return {"Authorization": f"Bearer {token}"}

def _handle_api_error(e: Exception, action: str = "perform action"):
    """Generic error handler for API calls."""
    if isinstance(e, requests.exceptions.HTTPError):
        if e.response.status_code == 401:
            st.error("Authentication failed or session expired. Please log in again.")
            logout_user()
        else:
            try: detail = e.response.json().get('detail', e.response.text)
            except: detail = e.response.text
            st.error(f"Failed to {action}: HTTP {e.response.status_code} - {detail[:250]}")
    elif isinstance(e, requests.exceptions.RequestException):
        st.error(f"Failed to {action}: Connection error - {e}")
    else:
        st.error(f"Failed to {action}: An unexpected error occurred - {e}")

def get_authenticated_request(endpoint: str, token: str, params: Optional[Dict] = None) -> Optional[Any]:
    try:
        response = requests.get(endpoint, headers=get_auth_headers(token), params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        _handle_api_error(e, f"fetch data from {endpoint.split('/')[-2] if '/' in endpoint else endpoint}")
        return None

# --- ICP API Helpers ---
def list_icps(token: str) -> Optional[List[Dict]]:
    return get_authenticated_request(f"{ICPS_ENDPOINT}/", token)
# ... Add create_new_icp, update_existing_icp, delete_existing_icp if not already defined ...

# --- Offering API Helpers ---
def list_offerings(token: str) -> Optional[List[Dict]]:
    return get_authenticated_request(f"{OFFERINGS_ENDPOINT}/", token)
# ... Add create_new_offering, update_existing_offering, delete_existing_offering ...

# --- Email Settings Helpers ---
def get_email_settings(token: str) -> Optional[Dict]:
    return get_authenticated_request(f"{EMAIL_SETTINGS_ENDPOINT}/", token)
# ... Add save_email_settings ...

# --- Lead API Helpers ---
def list_leads(token: str, skip: int = 0, limit: int = 100) -> Optional[List[Dict]]:
    return get_authenticated_request(f"{LEADS_ENDPOINT}/", token, params={"skip": skip, "limit": limit})
# ... Add create_new_lead, get_lead_details, update_existing_lead, delete_existing_lead ...

# Placeholder for CSV Upload function
def upload_leads_csv_file(uploaded_file, token: str) -> Dict[str, Any]:
    st.warning("CSV Upload backend functionality placeholder. Implement `upload_leads_csv_file` to call a bulk upload endpoint.")
    # Example:
    # endpoint = f"{LEADS_ENDPOINT}/bulk_upload/" # Ensure this endpoint exists and handles CSV
    # files_data = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
    # try:
    #     response = requests.post(endpoint, files=files_data, headers=get_auth_headers(token), timeout=120) # Longer timeout for uploads
    #     response.raise_for_status()
    #     return response.json()
    # except Exception as e:
    #     _handle_api_error(e, "upload CSV")
    #     return {"total_rows_in_file": 0, "rows_attempted": 0, "successfully_imported_or_updated": 0, "failed_imports": 0, "errors": [{"error": str(e)}]}
    return {"total_rows_in_file": 0, "rows_attempted": 0, "successfully_imported_or_updated": 0, "failed_imports": 0, "errors": []}


# --- Campaign API Helpers ---
def list_campaigns_api(token: str, active_only: Optional[bool] = None) -> Optional[List[Dict]]:
    params = {}
    if active_only is not None: params["active_only"] = active_only
    return get_authenticated_request(f"{CAMPAIGNS_ENDPOINT}/", token, params=params)

def create_campaign_api(campaign_payload: Dict[str, Any], token: str) -> Optional[Dict]:
    endpoint = f"{CAMPAIGNS_ENDPOINT}/"
    try:
        response = requests.post(endpoint, headers=get_auth_headers(token), json=campaign_payload, timeout=20)
        response.raise_for_status(); return response.json()
    except Exception as e: _handle_api_error(e, "create campaign"); return None

def get_campaign_details_api(campaign_id: int, token: str) -> Optional[Dict]:
    return get_authenticated_request(f"{CAMPAIGNS_ENDPOINT}/{campaign_id}", token)

def update_campaign_api(campaign_id: int, campaign_payload: Dict[str, Any], token: str) -> Optional[Dict]:
    endpoint = f"{CAMPAIGNS_ENDPOINT}/{campaign_id}"
    try:
        response = requests.put(endpoint, headers=get_auth_headers(token), json=campaign_payload, timeout=20)
        response.raise_for_status(); return response.json()
    except Exception as e: _handle_api_error(e, f"update campaign {campaign_id}"); return None

def activate_deactivate_campaign_api(campaign_id: int, is_active_status: bool, token: str) -> bool:
    return update_campaign_api(campaign_id, {"is_active": is_active_status}, token) is not None

def enroll_leads_in_campaign_api(campaign_id: int, lead_ids: List[int], token: str) -> Optional[Dict]:
    endpoint = f"{CAMPAIGNS_ENDPOINT}/{campaign_id}/enroll_leads"
    try:
        response = requests.post(endpoint, headers=get_auth_headers(token), json={"lead_ids": lead_ids}, timeout=45)
        response.raise_for_status(); return response.json()
    except Exception as e: _handle_api_error(e, "enroll leads"); return None

def enroll_matched_icp_leads_api(campaign_id: int, token: str) -> Optional[Dict]:
    endpoint = f"{CAMPAIGNS_ENDPOINT}/{campaign_id}/enroll_matched_icp_leads"
    try:
        response = requests.post(endpoint, headers=get_auth_headers(token), timeout=20)
        response.raise_for_status(); return response.json()
    except Exception as e: _handle_api_error(e, "enroll ICP matched leads"); return None

# --- Main App Logic ---
# Initialize session state keys (add any new ones here)
st.session_state.setdefault("authenticated", False)
st.session_state.setdefault("auth_token", None)
st.session_state.setdefault("user_email", None)
st.session_state.setdefault("view", "Login")
st.session_state.setdefault('nav_radio', "Dashboard") # For sidebar navigation

# Lead Page State
st.session_state.setdefault('leads_list', [])
st.session_state.setdefault('leads_loaded', False)
st.session_state.setdefault('show_lead_form', False)
st.session_state.setdefault('lead_form_data', {})
st.session_state.setdefault('lead_being_edited_id', None)
st.session_state.setdefault('lead_to_delete', None)
st.session_state.setdefault('lead_to_view_details', None)
st.session_state.setdefault('upload_summary', None)
st.session_state.setdefault('selected_leads_for_enrollment', {})
st.session_state.setdefault('show_enroll_leads_dialog', False)

# Campaign Page State
st.session_state.setdefault('campaigns_list', [])
st.session_state.setdefault('campaigns_loaded', False)
st.session_state.setdefault('show_campaign_create_form', False)
st.session_state.setdefault('view_campaign_id', None)
st.session_state.setdefault('available_icps_for_campaign', [])
st.session_state.setdefault('available_icps_for_campaign_loaded', False)
st.session_state.setdefault('available_offerings_for_campaign', [])
st.session_state.setdefault('available_offerings_for_campaign_loaded', False)
st.session_state.setdefault('campaign_action_success', None)
st.session_state.setdefault('campaign_action_error', None)

# Config Page State (ICP Tab example)
st.session_state.setdefault('icps_list_config_tab', []) # Use different key if data is different from campaign dropdown
st.session_state.setdefault('icps_loaded_config_tab', False)
st.session_state.setdefault('show_icp_form_config_tab', False)
st.session_state.setdefault('icp_form_data_config_tab', {})
st.session_state.setdefault('icp_being_edited_id_config_tab', None)
st.session_state.setdefault('icp_to_delete_config_tab', None)

# Config Page - Offerings Tab State
st.session_state.setdefault('offerings_list_config_tab', [])
st.session_state.setdefault('offerings_loaded_config_tab', False)
st.session_state.setdefault('show_offering_form_config_tab', False)
st.session_state.setdefault('offering_form_data_config_tab', {})
st.session_state.setdefault('offering_being_edited_id_config_tab', None)
st.session_state.setdefault('offering_to_delete_config_tab', None)
st.session_state.setdefault('offering_action_success_config_tab', None) # Tab-specific messages
st.session_state.setdefault('offering_action_error_config_tab', None)

# Config Page - Email Settings Tab State
st.session_state.setdefault('email_settings_current_config_tab', None) # Store fetched settings
st.session_state.setdefault('email_settings_loaded_config_tab', False)
st.session_state.setdefault('email_settings_save_success_config_tab', None)
st.session_state.setdefault('email_settings_save_error_config_tab', None)




if not st.session_state["authenticated"]:
    # --- Login / Sign Up UI ---
    # ... (Your existing login/signup UI - it looked fine) ...
    # Make sure any st.rerun() calls are appropriate.
    if st.session_state["view"] == "Login":
        # ... login form ...
        pass
    elif st.session_state["view"] == "Sign Up":
        # ... signup form ...
        pass
else: # Authenticated User Flow
    auth_token = st.session_state.get("auth_token")
    if not auth_token: logout_user(); st.stop() # Should not happen if authenticated is True

    with st.sidebar:
        st.image("https://salestroopz.com/wp-content/uploads/2024/01/cropped-SalesTroopz-Logos-1536x515.png", width=200) # Example logo
        st.write(f"User: {st.session_state.get('user_email', 'N/A')}")
        st.divider()
        page_options = ["Dashboard", "Leads", "Campaigns", "Configuration", "Setup Assistant"]
        # Ensure nav_radio default is one of these options
        st.session_state.nav_radio = st.radio(
            "Navigate", page_options, key="main_nav_radio",
            index=page_options.index(st.session_state.get("nav_radio", "Dashboard")) # Persist selection
        )
        st.divider()
        if st.button("Logout", key="logout_button_sidebar"):
            logout_user()

    current_page = st.session_state.nav_radio

    # --- Page Content Routing ---
    if current_page == "Dashboard":
        st.header("📊 Dashboard")
        st.write("Welcome to SalesTroopz! Key metrics and insights will appear here.")
        st.info("Dashboard content (appointment funnel, campaign summaries) to be implemented.")

    elif current_page == "Leads":
        st.header("👤 Leads Management")
        st.caption("View, add, and manage your sales leads. Select leads to enroll them into campaigns.")

        # --- Initialize Session State (ensure all relevant keys are present) ---
        st.session_state.setdefault('leads_list', [])
        st.session_state.setdefault('leads_loaded', False)
        st.session_state.setdefault('show_lead_form', False) 
        st.session_state.setdefault('lead_form_data', {})   
        st.session_state.setdefault('lead_being_edited_id', None) 
        st.session_state.setdefault('lead_to_delete', None) 
        st.session_state.setdefault('lead_to_view_details', None) 
        st.session_state.setdefault('upload_summary', None) 
        st.session_state.setdefault('selected_leads_for_enrollment', {}) # {lead_id: bool}
        st.session_state.setdefault('show_enroll_leads_dialog', False)

        auth_token = st.session_state.get("auth_token")
        if not auth_token:
            st.error("Authentication error. Please log in again.")
            logout_user(); st.stop()

        # --- Display Action Messages (Success/Error for lead operations) ---
        if st.session_state.get('lead_action_success'):
            st.success(st.session_state.pop('lead_action_success'))
        if st.session_state.get('lead_action_error'):
            st.error(st.session_state.pop('lead_action_error'))

        # --- Bulk CSV Upload Section ---
        with st.expander("📤 Bulk Import Leads from CSV", expanded=False):
            uploaded_file_leads = st.file_uploader("Choose a CSV file for leads", type=["csv"], key="leads_csv_file_uploader_main")
            if uploaded_file_leads:
                if st.button("🚀 Process Leads CSV", key="process_leads_csv_button_main"):
                    with st.spinner(f"Processing '{uploaded_file_leads.name}'..."):
                        summary = upload_leads_csv_file(uploaded_file_leads, auth_token) # Ensure this helper is robust
                        st.session_state.upload_summary = summary
                        st.session_state.leads_loaded = False; st.rerun()
        if st.session_state.get('upload_summary'):
            s = st.session_state.pop('upload_summary') 
            st.markdown("---"); st.markdown("#### CSV Import Summary:")
            st.info(f"- Total: {s.get('total_rows_in_file','N/A')}, Attempted: {s.get('rows_attempted','N/A')}, Successful: {s.get('successfully_imported_or_updated','N/A')}, Failed: {s.get('failed_imports','N/A')}")
            
            errors_list = s.get('errors', []) # Get the errors list
        if errors_list:
                        with st.expander(f"View {len(errors_list)} Import Errors/Issues"):
                            for i, err in enumerate(errors_list[:15]): 
                                st.error(f"Row {err.get('row_number','?')} (Email: {err.get('email','?')}) - Error: {err.get('error')}")
                            if len(errors_list) > 15: 
                                st.caption(f"...and {len(errors_list)-15} more issues.")
        
        # --- Load Lead List Data ---
        if not st.session_state.get('leads_loaded', False):
            with st.spinner("Loading leads..."):
                st.session_state.leads_list = list_leads(auth_token) or [] # Ensure list_leads exists and is called
                st.session_state.leads_loaded = True
        lead_list_data = st.session_state.get('leads_list', [])
       
        # --- UI to Trigger Enrollment for Selected Leads ---
        currently_selected_lead_ids = [
            lead_id for lead_id, is_selected 
            in st.session_state.get('selected_leads_for_enrollment', {}).items() if is_selected
        ]
        if currently_selected_lead_ids:
            st.markdown("---")
            col_enroll_btn_ui, _ = st.columns([1, 2]) # Button | Spacer
            with col_enroll_btn_ui:
                if st.button(f"➡️ Enroll {len(currently_selected_lead_ids)} Selected Lead(s) into Campaign", key="enroll_selected_leads_button_page", use_container_width=True):
                    st.session_state.show_enroll_leads_dialog = True
                    # Hide other forms/dialogs if they might be open
                    st.session_state.show_lead_form = False
                    st.session_state.lead_to_view_details = None
                    st.session_state.lead_to_delete = None
                    st.rerun() # Rerun to display the enrollment dialog
        elif st.session_state.get('leads_loaded') and lead_list_data : # Only show caption if leads are loaded and exist
             st.caption("Select leads using the checkboxes below to enable bulk enrollment.")
        
        # --- "All Leads" Section Header & Add New Lead Button ---
        st.markdown("---")
        col_all_leads_header_ui, col_add_lead_btn_ui = st.columns([3,1])
        with col_all_leads_header_ui: st.markdown("##### All Leads")
        with col_add_lead_btn_ui:
            if st.button("✚ Add New Lead", use_container_width=True, key="add_new_lead_button_page_main_key"):
                st.session_state.update(lead_form_data={}, lead_being_edited_id=None, show_lead_form=True, 
                                        show_enroll_leads_dialog=False, lead_to_view_details=None, lead_to_delete=None)
                st.rerun()

        # --- Main Lead List Display ---
        if not lead_list_data and st.session_state.get('leads_loaded'):
            st.info("No leads found. Click 'Add New Lead' or upload a CSV to get started.")
        elif lead_list_data:
            # Optional: Select/Deselect All Checkbox
            list_header_cols_ui = st.columns([0.6, 4, 1.5]) 
            with list_header_cols_ui[0]:
                all_currently_selected = False
                if currently_selected_lead_ids and len(currently_selected_lead_ids) == len(lead_list_data):
                     all_currently_selected = True
                new_select_all_state = st.checkbox("All", value=all_currently_selected, key="select_all_leads_master_cb_ui_key", help="Select/Deselect all leads in the list")
                if new_select_all_state != all_currently_selected:
                    for lead_item_sa in lead_list_data: st.session_state.setdefault('selected_leads_for_enrollment', {})[lead_item_sa['id']] = new_select_all_state
                    st.rerun()
            with list_header_cols_ui[1]: st.caption("Lead Information")
            with list_header_cols_ui[2]: st.caption("Actions")


            for lead_item_data in lead_list_data:
                lead_id = lead_item_data.get("id") # First statement
                if not lead_id: # Second statement 
                    continue
                with st.container(border=True):
                    item_cols_ui = st.columns([0.5, 4, 1.5]) 
                    with item_cols_ui[0]: 
                        current_sel_state = st.session_state.get('selected_leads_for_enrollment',{}).get(lead_id,False)
                        new_sel_state = st.checkbox("", value=current_sel_state, key=f"cb_lead_item_ui_{lead_id}")
                        if new_sel_state != current_sel_state:
                            st.session_state.setdefault('selected_leads_for_enrollment',{})[lead_id] = new_sel_state
                            st.rerun()
                    with item_cols_ui[1]: 
                        st.markdown(f"**{lead_item_data.get('name','N/A')}** ({lead_item_data.get('email')})")
                        st.caption(f"Company: {lead_item_data.get('company','N/A')} | Title: {lead_item_data.get('title','N/A')}")
                        if lead_item_data.get('matched'): 
                            reason = lead_item_data.get('reason','Matched')
                            st.caption(f"✅ ICP: {reason[:30]}{'...' if len(reason) > 30 else ''}")
                    with item_cols_ui[2]: 
                        action_buttons_cols_ui = st.columns(3)
                        def _set_view_lead_st(ld): st.session_state.update({'lead_to_view_details':ld, 'show_lead_form':False, 'show_enroll_leads_dialog':False}); st.rerun()
                        def _set_edit_lead_st(ld, l_id): st.session_state.update({'lead_form_data':ld, 'lead_being_edited_id':l_id, 'show_lead_form':True, 'show_enroll_leads_dialog':False}); st.rerun()
                        def _set_delete_lead_st(ld): st.session_state.update({'lead_to_delete':ld, 'show_lead_form':False, 'show_enroll_leads_dialog':False}); st.rerun()
                        
                        with action_buttons_cols_ui[0]: st.button("👁️",key=f"view_l_btn_{lead_id}",on_click=_set_view_lead_st,args=(lead_item_data,),help="View Details", use_container_width=True)
                        with action_buttons_cols_ui[1]: st.button("✏️",key=f"edit_l_btn_{lead_id}",on_click=_set_edit_lead_st,args=(lead_item_data,lead_id),help="Edit Lead", use_container_width=True)
                        with action_buttons_cols_ui[2]: st.button("🗑️",key=f"del_l_btn_{lead_id}",on_click=_set_delete_lead_st,args=(lead_item_data,),help="Delete Lead", use_container_width=True)
        
        # --- Enrollment Dialog ---
        if st.session_state.get('show_enroll_leads_dialog') and currently_selected_lead_ids:
            with st.container(border=True): # Simulates a modal
                with st.spinner("Loading active & ready campaigns..."):
                    all_active_camps = list_campaigns_api(auth_token, active_only=True)
                
                ready_campaigns_list = []
                if all_active_camps:
                    ready_campaigns_list = [c for c in all_active_camps if c.get('is_active') and c.get('ai_status') in ['completed', 'completed_partial']]

                if not ready_campaigns_list:
                    st.warning("No active campaigns with completed AI steps are available for enrollment.")
                    if st.button("Close Enrollment", key="close_enroll_dialog_no_camps_key"):
                        st.session_state.show_enroll_leads_dialog = False; st.rerun()
                else:
                    campaign_options_dict = {c['id']: f"{c['name']} (ICP: {c.get('icp_name','N/A')})" for c in ready_campaigns_list}
                    with st.form("enroll_leads_dialog_form_key"):
                        st.subheader(f"Enroll {len(currently_selected_lead_ids)} Selected Lead(s)")
                        chosen_campaign_id_enroll = st.selectbox("Select Campaign to Enroll In:", options=list(campaign_options_dict.keys()), format_func=lambda x_id: campaign_options_dict.get(x_id,x_id), key="campaign_select_in_dialog_key")
                        
                        form_cols = st.columns(2)
                        submit_clicked = form_cols[0].form_submit_button("✅ Confirm & Enroll", use_container_width=True, type="primary")
                        cancel_clicked = form_cols[1].form_submit_button("✖️ Cancel", use_container_width=True)

                        if cancel_clicked:
                            st.session_state.show_enroll_leads_dialog = False
                            st.session_state.selected_leads_for_enrollment = {} # Clear selection on cancel
                            st.rerun()
                        if submit_clicked:
                            if chosen_campaign_id_enroll and currently_selected_lead_ids:
                                with st.spinner(f"Enrolling leads into '{campaign_options_dict.get(chosen_campaign_id_enroll)}'..."):
                                    response = enroll_leads_in_campaign_api(chosen_campaign_id_enroll, currently_selected_lead_ids, auth_token)
                                if response:
                                    st.success(f"{response.get('message','Done.')} Enrolled: {response.get('successful_enrollments',0)}, Failed/Skipped: {response.get('failed_enrollments',0)}.")
                                    errors = response.get('details',[])
                                    if errors and response.get('failed_enrollments',0) > 0:
                                        with st.expander("View Enrollment Errors"): [st.error(f"LeadID {err.get('lead_id','?')}: {err.get('error','?')}") for err in errors]
                                    st.session_state.update(selected_leads_for_enrollment={}, show_enroll_leads_dialog=False, leads_loaded=False); st.rerun()
                                # else: API helper shows error
                            elif not chosen_campaign_id_enroll: st.error("Please select a campaign.")
        
        # --- View Lead Details Dialog ---
        if st.session_state.get('lead_to_view_details'):
            lead_to_view = st.session_state.lead_to_view_details
            # @st.dialog(...) # If using Streamlit's native dialog
            with st.container(border=True): # Simulating a dialog
                st.subheader(f"Lead Details: {lead_to_view.get('name', lead_to_view.get('email'))}")
                display_fields = ['name', 'email', 'company', 'title', 'source', 'linkedin_profile', 
                                  'company_size', 'industry', 'location', 'matched', 'reason', 
                                  'crm_status', 'appointment_confirmed', 'icp_match_id', 'created_at', 'updated_at']
                for key in display_fields:
                    val = lead_to_view.get(key)
                    if val is not None:
                        disp_key = key.replace("_", " ").title()
                        if isinstance(val, bool): st.markdown(f"**{disp_key}:** {'Yes' if val else 'No'}")
                        elif key in ['created_at', 'updated_at'] and isinstance(val, str):
                            try: dt_val = datetime.fromisoformat(val.replace('Z', '+00:00')); st.markdown(f"**{disp_key}:** {dt_val.strftime('%Y-%m-%d %H:%M')}")
                            except: st.markdown(f"**{disp_key}:** {val}")
                        else: st.markdown(f"**{disp_key}:** {val}")
                if st.button("Close Details", key="close_lead_view_details_dialog_btn"):
                    st.session_state.lead_to_view_details = None; st.rerun()
            st.markdown("---")


        # --- Delete Lead Confirmation Dialog ---
        if st.session_state.get('lead_to_delete'):
            lead_for_deletion = st.session_state.lead_to_delete
            # @st.dialog(...)
            with st.container(border=True):
                st.warning(f"Delete Lead: **{lead_for_deletion.get('name', lead_for_deletion.get('email'))}**?", icon="⚠️")
                del_confirm_cols = st.columns(2)
                if del_confirm_cols[0].button("Yes, Delete Lead", type="primary", key="confirm_delete_lead_btn"):
                    with st.spinner("Deleting..."): success = delete_existing_lead(lead_for_deletion['id'], auth_token)
                    if success: st.session_state.lead_action_success = "Lead deleted."
                    # else: API helper shows error
                    st.session_state.leads_loaded = False; st.session_state.lead_to_delete = None; st.rerun()
                if del_confirm_cols[1].button("Cancel Deletion", key="cancel_delete_lead_btn"):
                    st.session_state.lead_to_delete = None; st.rerun()
            st.markdown("---")

        # --- Add/Edit Lead Form ---
        if st.session_state.get('show_lead_form'):
            form_title = "Edit Lead" if st.session_state.get('lead_being_edited_id') else "Add New Lead"
            st.subheader(form_title)
            form_data = st.session_state.get('lead_form_data', {})
            with st.form("lead_add_edit_form_main", clear_on_submit=False):
                # Define form fields using st.session_state for prefill if needed, or bind to new keys
                name = st.text_input("Name:", value=form_data.get("name", ""), key="lead_f_name")
                email = st.text_input("Email*:", value=form_data.get("email", ""), key="lead_f_email")
                # ... (all your other lead form fields: company, title, source, etc.) ...
                company = st.text_input("Company:", value=form_data.get("company", ""), key="lead_f_company")
                title = st.text_input("Title:", value=form_data.get("title", ""), key="lead_f_title")
                # ... continue with all other fields ...
                matched = st.checkbox("Matched ICP?", value=bool(form_data.get("matched",False)), key="lead_f_matched")
                appointment_confirmed = st.checkbox("Appointment Confirmed?", value=bool(form_data.get("appointment_confirmed",False)), key="lead_f_appt")


                submit_btn = st.form_submit_button("💾 Save Lead")
                if st.form_submit_button("✖️ Cancel", type="secondary"):
                    st.session_state.show_lead_form = False; st.rerun()
                
                if submit_btn:
                    if not email: st.error("Email is required.")
                    else:
                        payload = {
                            "name": name.strip() or None, "email": email.strip(),
                            "company": company.strip() or None, "title": title.strip() or None,
                            # ... (gather all other fields into payload) ...
                            "matched": matched, "appointment_confirmed": appointment_confirmed
                        }
                        with st.spinner("Saving lead..."):
                            lead_id_edit = st.session_state.get('lead_being_edited_id')
                            if lead_id_edit: result = update_existing_lead(lead_id_edit, payload, auth_token)
                            else: result = create_new_lead(payload, auth_token)
                        
                        if result:
                            st.session_state.lead_action_success = f"Lead {payload['email']} {'updated' if lead_id_edit else 'added'}."
                            st.session_state.leads_loaded = False; st.session_state.show_lead_form = False
                            st.rerun()
        
        exec(Path("streamlit_pages/leads_page.py").read_text()) # Example if you modularize

    elif current_page == "Campaigns":
        st.header("📣 Campaign Management (AI-Powered)")
        st.caption("Create AI-generated email outreach campaigns, review steps, activate, and enroll leads.")
       
        auth_token = st.session_state.get("auth_token") # Ensure auth_token is available

        # --- Display Action Messages ---
        if st.session_state.get('campaign_action_success'):
            st.success(st.session_state.pop('campaign_action_success'))
        if st.session_state.get('campaign_action_error'):
            st.error(st.session_state.pop('campaign_action_error'))

        # --- Load Data needed for the Page (Campaign list, ICPs/Offerings for create form) ---
        if not st.session_state.get('campaigns_loaded', False):
            with st.spinner("Loading campaigns list..."):
                st.session_state.campaigns_list = list_campaigns_api(auth_token, active_only=None) or []
                st.session_state.campaigns_loaded = True
        
        if not st.session_state.get('available_icps_for_campaign_loaded', False):
            with st.spinner("Loading ICPs for campaign creation..."):
                st.session_state.available_icps_for_campaign = list_icps(auth_token) or []
                st.session_state.available_icps_for_campaign_loaded = True

        if not st.session_state.get('available_offerings_for_campaign_loaded', False):
            with st.spinner("Loading Offerings for campaign creation..."):
                st.session_state.available_offerings_for_campaign = list_offerings(auth_token) or []
                st.session_state.available_offerings_for_campaign_loaded = True
        
        campaign_list_data = st.session_state.get('campaigns_list', [])
        available_icps_data = st.session_state.get('available_icps_for_campaign', [])
        available_offerings_data = st.session_state.get('available_offerings_for_campaign', [])

        # --- Create New Campaign Section ---
        st.markdown("---")
        # Toggle button for create form
        if st.button("🚀 Create New Campaign Goal", key="toggle_create_campaign_form_button_campaigns_page"):
            st.session_state.show_campaign_create_form = not st.session_state.get('show_campaign_create_form', False)
            if st.session_state.show_campaign_create_form: # If form is now shown
                st.session_state.view_campaign_id = None # Hide details view
            st.rerun() # Rerun to reflect visibility change

        if st.session_state.get('show_campaign_create_form', False):
            st.subheader("Define New Campaign Goal")
            with st.form("create_campaign_form_main_ui", clear_on_submit=True): # Unique key
                campaign_name = st.text_input("Campaign Name*", help="A clear, descriptive name for your campaign.")
                campaign_description = st.text_area("Description (Optional)", height=100, help="Briefly describe the goal or purpose.")

                icp_options_map = {icp['id']: icp['name'] for icp in available_icps_data}
                offering_options_map = {offering['id']: offering['name'] for offering in available_offerings_data}

                selected_icp_id = st.selectbox(
                    "Link Ideal Customer Profile (ICP) (Optional)", 
                    options=[None] + list(icp_options_map.keys()),
                    format_func=lambda x_id: "None - Generic" if x_id is None else icp_options_map.get(x_id, f"ID: {x_id}"),
                    key="create_campaign_icp_select_ui_key"
                )
                selected_offering_id = st.selectbox(
                    "Link Offering (Optional)", 
                    options=[None] + list(offering_options_map.keys()),
                    format_func=lambda x_id: "None - Generic" if x_id is None else offering_options_map.get(x_id, f"ID: {x_id}"),
                    key="create_campaign_offering_select_ui_key"
                )
                is_active_default = st.checkbox("Set campaign as active by default upon creation?", value=False, key="create_campaign_is_active_cb", help="You can activate/deactivate it later after reviewing AI steps.")

                submitted_create_campaign = st.form_submit_button("Create Campaign & Start AI Generation")

                if submitted_create_campaign:
                    if not campaign_name.strip():
                        st.error("Campaign Name is required.")
                    else:
                        campaign_payload = {
                            "name": campaign_name.strip(), 
                            "description": campaign_description.strip() or None,
                            "icp_id": selected_icp_id, 
                            "offering_id": selected_offering_id,
                            "is_active": is_active_default 
                        }
                        with st.spinner("Creating campaign and triggering AI email generation..."):
                            response = create_campaign_api(campaign_payload, auth_token)
                        
                        if response:
                            st.session_state.campaign_action_success = f"Campaign '{response.get('name')}' created! AI Status: {response.get('ai_status','pending').capitalize()}. Refresh list to see updates."
                            st.session_state.campaigns_loaded = False # Force reload of campaign list
                            st.session_state.show_campaign_create_form = False # Hide the form
                            st.balloons()
                            st.rerun()
                        # else: API helper should show error

        # --- Display Campaigns List ---
        st.markdown("---")
        st.subheader("📚 Existing Campaigns")
        if st.button("🔄 Refresh Campaign List", key="refresh_campaigns_button_main_page"):
            st.session_state.campaigns_loaded = False
            st.rerun()

        if not campaign_list_data and st.session_state.get('campaigns_loaded'):
            st.info("No campaigns found yet. Click 'Create New Campaign Goal' to get started with AI!")
        elif campaign_list_data:
            for campaign_item in campaign_list_data:
                camp_item_id = campaign_item.get('id')
                if not camp_item_id: continue
                with st.container(border=True):
                    list_cols = st.columns([3, 3, 2, 2]) # Name, Details, Status, Actions
                    with list_cols[0]:
                        st.markdown(f"**{campaign_item.get('name', 'Unnamed Campaign')}**")
                        desc = campaign_item.get('description', '')
                        st.caption(f"{desc[:60]}{'...' if len(desc) > 60 else ''}")
                    with list_cols[1]:
                        st.caption(f"ICP: `{campaign_item.get('icp_name', 'None')}`")
                        st.caption(f"Offering: `{campaign_item.get('offering_name', 'None')}`")
                    with list_cols[2]:
                        st.markdown("✅ Active" if campaign_item.get('is_active') else "⏸️ Inactive")
                        ai_s_val = campaign_item.get('ai_status', 'N/A').replace('_',' ').capitalize()
                        ai_icon_val = "✔️" if ai_s_val=="Completed" else "⏳" if ai_s_val=="Generating" else "⌛" if ai_s_val=="Pending" else "❌"
                        st.markdown(f"AI: {ai_icon_val} `{ai_s_val}`")
                    with list_cols[3]:
                        if st.button("👁️ View/Manage", key=f"view_manage_campaign_btn_{camp_item_id}", help="View details, steps, and manage campaign.", use_container_width=True):
                            st.session_state.view_campaign_id = camp_item_id
                            st.session_state.show_campaign_create_form = False # Hide create form if open
                            st.rerun()
        st.markdown("---")
        
        # --- Conditionally Display Campaign Details & Management Section ---
        if st.session_state.get('view_campaign_id') is not None:
            campaign_id_to_show_details = st.session_state.view_campaign_id 
            st.subheader(f"🔍 Campaign Details & Management")

            with st.spinner(f"Loading details for Campaign ID {campaign_id_to_show_details}..."):
                campaign_details = get_campaign_details_api(campaign_id_to_show_details, auth_token)

            if campaign_details:
                st.markdown(f"#### {campaign_details.get('name', 'N/A')}")
                active_stat_text = "✅ Active" if campaign_details.get('is_active') else "⏸️ Inactive"
                ai_stat_text = campaign_details.get('ai_status','N/A').replace('_',' ').capitalize()
                st.caption(f"ID: {campaign_details.get('id')} | Status: {active_stat_text} | AI: {ai_stat_text}")
                
                with st.expander("Campaign Metadata", expanded=False):
                    st.markdown(f"**Description:** {campaign_details.get('description', '_No description_')}")
                    st.markdown(f"**Linked ICP:** {campaign_details.get('icp_name', '_None_')}")
                    st.markdown(f"**Linked Offering:** {campaign_details.get('offering_name', '_None_')}")
                    created_at_str = campaign_details.get('created_at')
                    if created_at_str:
                        try: dt_obj_created = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        except: dt_obj_created = None
                        st.caption(f"Created: {dt_obj_created.strftime('%Y-%m-%d %H:%M %Z') if dt_obj_created and dt_obj_created.tzinfo else dt_obj_created.strftime('%Y-%m-%d %H:%M') if dt_obj_created else created_at_str}")

                # Display Steps
                campaign_steps_data = campaign_details.get('steps', [])
                campaign_has_actual_steps = bool(campaign_steps_data)

                if not campaign_has_actual_steps and ai_stat_text not in ["Generating", "Pending"]:
                     st.warning("No steps found. AI might have failed, produced no steps, or steps were deleted.", icon="⚠️")
                elif not campaign_has_actual_steps and ai_stat_text in ["Generating", "Pending"]:
                     st.info(f"AI is currently {ai_stat_text.lower()} steps. Refresh or check back soon.", icon="⏳")
                elif campaign_has_actual_steps:
                    st.markdown("##### ✉️ AI-Generated Email Steps (Review Only):")
                    for step_item in sorted(campaign_steps_data, key=lambda x: x.get('step_number', 0)):
                        exp_title = f"Step {step_item.get('step_number')}: {step_item.get('subject_template', 'No Subject')}"
                        exp_title += f" (Delay: {step_item.get('delay_days')} days)"
                        with st.expander(exp_title):
                            st.markdown(f"**Follow-up Angle:** `{step_item.get('follow_up_angle', 'N/A')}`")
                            st.markdown(f"**Subject Template:**"); st.code(step_item.get('subject_template', ''), language='text')
                            st.markdown(f"**Body Template:**")
                            st.text_area(f"body_display_campaign_detail_{step_item.get('id')}", value=step_item.get('body_template', ''), height=200, disabled=True, key=f"body_text_display_campaign_detail_{step_item.get('id')}")
                            st.caption(f"Step ID: {step_item.get('id')} | AI Crafted: {'Yes' if step_item.get('is_ai_crafted') else 'No'}")
                
                # --- Action Buttons for the Viewed Campaign ---
                st.markdown("---") 
                st.markdown("##### Manage Campaign:")
                action_buttons_cols = st.columns(3)
                
                # Activation/Deactivation Button
                with action_buttons_cols[0]:
                    is_camp_active = campaign_details.get('is_active', False)
                    ai_is_ready_for_activation = campaign_details.get('ai_status') in ["completed", "completed_partial"]
                    
                    if ai_is_ready_for_activation and campaign_has_actual_steps:
                        if not is_camp_active:
                            if st.button("✅ Activate Campaign", key=f"activate_campaign_detail_btn_{campaign_id_to_show_details}", type="primary", use_container_width=True):
                                with st.spinner("Activating..."): success_act = activate_deactivate_campaign_api(campaign_id_to_show_details, True, auth_token)
                                if success_act: st.session_state.campaign_action_success = "Campaign activated!"; st.session_state.campaigns_loaded=False; del st.session_state.view_campaign_id; st.rerun()
                                # else: error shown by helper
                        else: # Campaign is active
                            if st.button("⏸️ Deactivate Campaign", key=f"deactivate_campaign_detail_btn_{campaign_id_to_show_details}", use_container_width=True):
                                with st.spinner("Deactivating..."): success_deact = activate_deactivate_campaign_api(campaign_id_to_show_details, False, auth_token)
                                if success_deact: st.session_state.campaign_action_success = "Campaign deactivated!"; st.session_state.campaigns_loaded=False; del st.session_state.view_campaign_id; st.rerun()
                                # else: error shown by helper
                    elif not campaign_has_actual_steps and ai_is_ready_for_activation:
                        st.caption("Cannot activate: AI completed but no steps found.")
                    elif not ai_is_ready_for_activation:
                         st.caption(f"AI status: {ai_stat_text}. Activation available once steps are 'completed'.")

                # Enroll Matched ICP Leads Button
                with action_buttons_cols[1]:
                    if is_camp_active and campaign_details.get('icp_id') and ai_is_ready_for_activation and campaign_has_actual_steps:
                        icp_name_for_btn = campaign_details.get('icp_name', 'Linked ICP')
                        if st.button(f"➕ Enroll Matched ICP Leads", key=f"enroll_icp_leads_detail_btn_{campaign_id_to_show_details}", help=f"Enroll leads matching '{icp_name_for_btn}'", use_container_width=True):
                            with st.spinner(f"Triggering enrollment for ICP '{icp_name_for_btn}'..."):
                                enroll_api_resp = enroll_matched_icp_leads_api(campaign_id_to_show_details, auth_token)
                            if enroll_api_resp:
                                st.info(f"{enroll_api_resp.get('message','Enrollment process triggered.')} Check logs for details.")
                                # This is a background task on API, so success here means task was triggered.
                                # User might need to refresh later to see impact on lead counts.
                            # else: error shown by helper
                    elif not campaign_details.get('icp_id'): st.caption("Link ICP to campaign for smart enrollment.")
                    elif not is_camp_active: st.caption("Activate campaign to enroll leads.")
                    elif not (ai_is_ready_for_activation and campaign_has_actual_steps) : st.caption("Steps must be AI-completed to enroll leads.")

                # AI Regenerate Steps Button (Placeholder)
                with action_buttons_cols[2]:
                    if ai_is_ready_for_activation or "failed" in campaign_details.get('ai_status',''):
                         if st.button("🔄 AI Regenerate Steps", key=f"regenerate_campaign_steps_btn_{campaign_id_to_show_details}", help="Ask AI to generate a new set of steps (deletes current steps).", use_container_width=True):
                            # TODO: Requires backend endpoint: POST /campaigns/{id}/regenerate
                            # This endpoint would call agent.generate_campaign_steps(..., force_regeneration=True)
                            st.warning("Backend for AI Regeneration not yet implemented.")

                st.markdown("---")
                if st.button("🔙 Close Campaign Details", key=f"close_campaign_details_page_btn_{campaign_id_to_show_details}"):
                    del st.session_state.view_campaign_id
                    st.rerun()
            else: # campaign_details_data is None
                st.error(f"Could not load details for Campaign ID: {campaign_id_to_show_details}. It might have been deleted or an error occurred.")
                if st.button("Return to Campaigns List", key="return_to_campaign_list_from_error_btn"):
                    if 'view_campaign_id' in st.session_state: del st.session_state.view_campaign_id
                    st.rerun()
        
        exec(Path("streamlit_pages/campaigns_page.py").read_text()) # Example if you modularize

    elif current_page == "Configuration":
        st.header("⚙️ Configuration")
        st.caption("Manage your core sales assets: Ideal Customer Profiles (ICPs), Offerings, and Email Sending settings.")

        auth_token = st.session_state.get("auth_token")
        if not auth_token: # Should be caught earlier, but good check
            st.error("Authentication token not found."); logout_user(); st.stop()
        # exec(Path("streamlit_pages/config_email_tab.py").read_text())
tab_icp, tab_offering, tab_email = st.tabs(["🎯 ICP Definition", "💡 Offerings", "📧 Email Sending"])

        # --- ICP Definition Tab ---
with tab_icp:
            st.subheader("Ideal Customer Profiles (ICPs)")
            st.caption("Define different target customer segments for your campaigns.")

            if st.session_state.get('icp_action_success_config_tab'): st.success(st.session_state.pop('icp_action_success_config_tab'))
            if st.session_state.get('icp_action_error_config_tab'): st.error(st.session_state.pop('icp_action_error_config_tab'))

            if not st.session_state.get('icps_loaded_config_tab'):
                with st.spinner("Loading ICPs..."): st.session_state.icps_list_config_tab = list_icps(auth_token) or []
                st.session_state.icps_loaded_config_tab = True
            icp_list_cfg = st.session_state.get('icps_list_config_tab', [])

            st.markdown("---")
            col_icp_hdr1, col_icp_hdr2 = st.columns([3,1])
            col_icp_hdr1.markdown("##### Saved ICPs")
            if col_icp_hdr2.button("✚ Add New ICP", use_container_width=True, key="add_icp_btn_cfg"):
                st.session_state.update(icp_form_data_config_tab={}, icp_being_edited_id_config_tab=None, show_icp_form_config_tab=True); st.rerun()

            if not icp_list_cfg and st.session_state.get('icps_loaded_config_tab'): st.info("No ICPs defined yet.")
            elif icp_list_cfg:
                for icp in icp_list_cfg:
                    icp_id = icp.get('id')
                    if not icp_id:
                        continue
                    with st.container(border=True):
                        cols = st.columns([4,1,1]); cols[0].markdown(f"**{icp.get('name','N/A')}** (ID: {icp_id})")
                        # Add more summary here if desired (e.g., count of keywords)
                        if cols[1].button("Edit", key=f"edit_icp_cfg_{icp_id}", type="secondary", use_container_width=True):
                            st.session_state.update(icp_form_data_config_tab=icp, icp_being_edited_id_config_tab=icp_id, show_icp_form_config_tab=True); st.rerun()
                        if cols[2].button("Delete", key=f"del_icp_cfg_{icp_id}", type="primary", use_container_width=True):
                            st.session_state.icp_to_delete_config_tab = icp; st.rerun()
            st.markdown("---")

            if st.session_state.get('icp_to_delete_config_tab'):
                icp_del = st.session_state.icp_to_delete_config_tab
                with st.container(border=True): # Simulate dialog
                    st.warning(f"Delete ICP: **{icp_del.get('name')}**?", icon="⚠️")
                    c1,c2=st.columns(2)
                    if c1.button("Yes, Delete",type="primary",key="conf_del_icp_cfg"):
                        with st.spinner("Deleting..."): success = delete_existing_icp(icp_del['id'],auth_token)
                        if success: st.session_state.icp_action_success_config_tab="ICP deleted."
                        st.session_state.icps_loaded_config_tab=False; del st.session_state.icp_to_delete_config_tab; st.rerun()
                    if c2.button("Cancel",key="canc_del_icp_cfg"): del st.session_state.icp_to_delete_config_tab; st.rerun()
            
            if st.session_state.get('show_icp_form_config_tab'):
                title = "Edit ICP" if st.session_state.get('icp_being_edited_id_config_tab') else "Add New ICP"
                st.subheader(title)
                data = st.session_state.get('icp_form_data_config_tab',{})
                with st.form("icp_form_ui_cfg", clear_on_submit=False):
                    name=st.text_input("ICP Name*",value=data.get("name",""))
                    titles=st.text_area("Titles (one per line)", "\n".join(data.get("title_keywords",[])))
                    inds=st.text_area("Industries (one per line)", "\n".join(data.get("industry_keywords",[])))
                    locs=st.text_area("Locations (one per line)", "\n".join(data.get("location_keywords",[])))
                    size_r=data.get("company_size_rules",{})
                    min_s=st.number_input("Min Employees",value=size_r.get("min"),step=1,format="%d")
                    max_s=st.number_input("Max Employees",value=size_r.get("max"),step=1,format="%d")
                    if min_s and max_s and min_s > max_s: st.warning("Min size > Max size.")
                    
                    s_btn,c_btn=st.columns(2)
                    if s_btn.form_submit_button("💾 Save ICP"):
                        if not name.strip(): st.error("Name required.")
                        else:
                            payload={"name":name.strip(), 
                                     "title_keywords":[t.strip() for t in titles.split('\n') if t.strip()],
                                     "industry_keywords":[i.strip() for i in inds.split('\n') if i.strip()],
                                     "location_keywords":[l.strip() for l in locs.split('\n') if l.strip()],
                                     "company_size_rules": ({k:v for k,v in [("min",min_s),("max",max_s)] if v is not None} or None)}
                            with st.spinner("Saving..."):
                                id_edit = st.session_state.get('icp_being_edited_id_config_tab')
                                res = update_existing_icp(id_edit,payload,auth_token) if id_edit else create_new_icp(payload,auth_token)
                            if res: 
                                st.session_state.icp_action_success_config_tab=f"ICP '{res.get('name')}' {'updated' if id_edit else 'created'}."
                                st.session_state.update(icps_loaded_config_tab=False,show_icp_form_config_tab=False,icp_form_data_config_tab={},icp_being_edited_id_config_tab=None)
                                st.rerun()
                    if c_btn.form_submit_button("✖️ Cancel",type="secondary"): st.session_state.show_icp_form_config_tab=False; st.rerun()

        # --- Offerings Tab ---
with tab_offering:
            # ... (Full Offerings Tab Logic - This was provided completely in the previous response) ...
            # Ensure it uses session state variables with '_config_tab' suffix.
            # Example: st.session_state.offerings_list_config_tab, show_offering_form_config_tab etc.
            st.subheader("💡 Offerings / Value Propositions")
            st.caption("Define the products or services you offer.")

            if st.session_state.get('offering_action_success_config_tab'): st.success(st.session_state.pop('offering_action_success_config_tab'))
            if st.session_state.get('offering_action_error_config_tab'): st.error(st.session_state.pop('offering_action_error_config_tab'))

            if not st.session_state.get('offerings_loaded_config_tab'):
                with st.spinner("Loading offerings..."): st.session_state.offerings_list_config_tab = list_offerings(auth_token) or []
                st.session_state.offerings_loaded_config_tab = True
            off_list_cfg = st.session_state.get('offerings_list_config_tab', [])
            
            st.markdown("---"); hd_off1,hd_off2=st.columns([3,1]); hd_off1.markdown("##### Defined Offerings")
            if hd_off2.button("✚ Add Offering",use_container_width=True,key="add_off_btn_cfg"):
                st.session_state.update(offering_form_data_config_tab={"is_active":True},offering_being_edited_id_config_tab=None,show_offering_form_config_tab=True);st.rerun()

            if not off_list_cfg and st.session_state.get('offerings_loaded_config_tab'): st.info("No offerings defined.")
            elif off_list_cfg:
                for off in off_list_cfg:
                    off_id=off.get('id');
                    if not off_id:
                        continue
                    with st.container(border=True):
                        c=st.columns([4,1,1]); c[0].markdown(f"{'✅' if off.get('is_active') else '⏸️'} **{off.get('name','N/A')}** (ID:{off_id})"); c[0].caption(f"{off.get('description','')[:70]}...")
                        if c[1].button("Edit",key=f"ed_off_{off_id}",type="secondary",use_container_width=True): st.session_state.update(offering_form_data_config_tab=off,offering_being_edited_id_config_tab=off_id,show_offering_form_config_tab=True);st.rerun()
                        if c[2].button("Delete",key=f"del_off_{off_id}",type="primary",use_container_width=True): st.session_state.offering_to_delete_config_tab=off;st.rerun()
            st.markdown("---")

            if st.session_state.get('offering_to_delete_config_tab'):
                off_del=st.session_state.offering_to_delete_config_tab
                with st.container(border=True):
                    st.warning(f"Delete Offering: **{off_del.get('name')}**?",icon="⚠️")
                    dc1,dc2=st.columns(2)
                    if dc1.button("Yes, Delete Offering",type="primary",key="conf_del_off_cfg_btn"):
                        with st.spinner("Deleting..."): suc=delete_existing_offering(off_del['id'],auth_token)
                        if suc: st.session_state.offering_action_success_config_tab="Offering deleted."
                        st.session_state.offerings_loaded_config_tab=False;del st.session_state.offering_to_delete_config_tab;st.rerun()
                    if dc2.button("Cancel",key="canc_del_off_cfg_btn"): del st.session_state.offering_to_delete_config_tab;st.rerun()
            
            if st.session_state.get('show_offering_form_config_tab'):
                tit_off="Edit Offering" if st.session_state.get('offering_being_edited_id_config_tab') else "Add New Offering"
                st.subheader(tit_off); data_off=st.session_state.get('offering_form_data_config_tab',{})
                with st.form("offering_form_cfg_ui",clear_on_submit=False):
                    n=st.text_input("Name*",value=data_off.get("name",""))
                    d=st.text_area("Description",value=data_off.get("description",""))
                    kf=st.text_area("Key Features (one/line)", "\n".join(data_off.get("key_features",[])))
                    tp=st.text_area("Target Pain Points (one/line)", "\n".join(data_off.get("target_pain_points",[])))
                    cta=st.text_input("Call to Action", value=data_off.get("call_to_action",""))
                    is_a=st.toggle("Active", value=bool(data_off.get("is_active",True)))
                    sfo,cfo=st.columns(2)
                    if sfo.form_submit_button("💾 Save Offering"):
                        if not n.strip(): st.error("Name required.")
                        else:
                            pay={"name":n.strip(),"description":d.strip() or None,"is_active":is_a,
                                 "key_features":[x.strip() for x in kf.split('\n') if x.strip()],
                                 "target_pain_points":[x.strip() for x in tp.split('\n') if x.strip()],
                                 "call_to_action":cta.strip() or None}
                            with st.spinner("Saving..."):
                                id_e=st.session_state.get('offering_being_edited_id_config_tab')
                                rs=update_existing_offering(id_e,pay,auth_token) if id_e else create_new_offering(pay,auth_token)
                            if rs:
                                st.session_state.offering_action_success_config_tab=f"Offering '{rs.get('name')}' {'updated' if id_e else 'created'}."
                                st.session_state.update(offerings_loaded_config_tab=False,show_offering_form_config_tab=False,offering_form_data_config_tab={},offering_being_edited_id_config_tab=None);st.rerun()
                    if cfo.form_submit_button("✖️ Cancel",type="secondary"): st.session_state.show_offering_form_config_tab=False;st.rerun()


        # --- Email Sending Tab ---
with tab_email:
            st.subheader("📧 Email Sending Setup")
            st.caption("Configure how SalesTroopz will send emails.")

            if st.session_state.get('email_settings_save_success_config_tab'): st.success(st.session_state.pop('email_settings_save_success_config_tab'))
            if st.session_state.get('email_settings_save_error_config_tab'): st.error(st.session_state.pop('email_settings_save_error_config_tab'))

            if not st.session_state.get('email_settings_loaded_config_tab'):
                with st.spinner("Loading email settings..."):
                    st.session_state.email_settings_current_config_tab = get_email_settings(auth_token) # Can be None
                    st.session_state.email_settings_loaded_config_tab = True
            
            current_email_cfg = st.session_state.get('email_settings_current_config_tab') or {}

            st.markdown("---")
            if current_email_cfg.get('is_configured') and current_email_cfg.get('provider_type'):
                st.markdown("##### Current Configuration:")
                st.info(f"**Provider:** `{current_email_cfg.get('provider_type','N/A').upper()}` | **Sender:** `{current_email_cfg.get('verified_sender_email','N/A')}` (`{current_email_cfg.get('sender_name','N/A')}`)")
            else: st.info("Email sending is not yet fully configured.")
            st.markdown("---")

            with st.form("email_settings_form_cfg_ui"):
                st.markdown("#### Configure Email Provider:")
                providers = ["Not Configured", "SMTP", "AWS_SES"]
                provider_map = {"Not Configured":"Select...", "SMTP":"Generic SMTP", "AWS_SES":"AWS SES (API Keys)"}
                current_prov_idx = providers.index(current_email_cfg.get('provider_type')) if current_email_cfg.get('provider_type') in providers else 0
                
                sel_provider = st.selectbox("Provider:", providers, format_func=lambda x:provider_map.get(x,x), index=current_prov_idx, key="email_prov_sel_cfg")
                
                sender_email_val = st.text_input("Verified Sender Email*:", value=current_email_cfg.get('verified_sender_email',''), key="email_addr_cfg")
                sender_name_val = st.text_input("Sender Name* (Display Name):", value=current_email_cfg.get('sender_name',''), key="email_name_cfg")

                if sel_provider == "SMTP":
                    st.text_input("SMTP Host*:", value=current_email_cfg.get('smtp_host',''), key="email_smtp_host_val_cfg")
                    st.number_input("SMTP Port*:", value=int(current_email_cfg.get('smtp_port',587)), min_value=1, max_value=65535, key="email_smtp_port_val_cfg")
                    st.text_input("SMTP Username*:", value=current_email_cfg.get('smtp_username',''), key="email_smtp_user_val_cfg")
                    smtp_pass_val = st.text_input("SMTP Password:", type="password", key="email_smtp_pass_val_cfg", help="Leave blank to keep current.")
                elif sel_provider == "AWS_SES":
                    st.text_input("AWS Region*:", value=current_email_cfg.get('aws_region',''), key="email_aws_region_val_cfg")
                    aws_key_val = st.text_input("AWS Access Key ID:", type="password", key="email_aws_id_val_cfg", help="Leave blank to keep current.")
                    aws_secret_val = st.text_input("AWS Secret Access Key:", type="password", key="email_aws_secret_val_cfg", help="Leave blank to keep current.")
                
                is_cfg_toggle = st.toggle("Mark as Fully Configured & Ready to Send", value=bool(current_email_cfg.get('is_configured',False)), key="email_is_configured_toggle_cfg")
                
                if st.form_submit_button("💾 Save Email Settings"):
                    payload = {"provider_type": sel_provider if sel_provider != "Not Configured" else None,
                               "verified_sender_email": sender_email_val.strip() or None,
                               "sender_name": sender_name_val.strip() or None,
                               "is_configured": is_cfg_toggle}
                    valid_save = True
                    if payload["provider_type"] and (not payload["verified_sender_email"] or not payload["sender_name"]):
                        st.error("Sender Email and Sender Name are required if a provider is selected."); valid_save = False
                    
                    if sel_provider == "SMTP":
                        payload.update({"smtp_host":st.session_state.email_smtp_host_val_cfg.strip() or None, 
                                        "smtp_port":st.session_state.email_smtp_port_val_cfg, 
                                        "smtp_username":st.session_state.email_smtp_user_val_cfg.strip() or None})
                        if smtp_pass_val: payload["smtp_password"] = smtp_pass_val
                        if not all([payload["smtp_host"], payload["smtp_port"], payload["smtp_username"]]): # Basic check for SMTP
                             if not smtp_pass_val and not (current_email_cfg.get('provider_type') == "SMTP" and current_email_cfg.get('credentials_set')): # Allow saving without password if previously set
                                 pass # User might be updating other fields
                             elif not smtp_pass_val and (current_email_cfg.get('provider_type') != "SMTP" or not current_email_cfg.get('credentials_set')):
                                 st.error("For SMTP, Host, Port, Username, and Password (on first setup) are required."); valid_save=False
                    
                    elif sel_provider == "AWS_SES":
                        payload["aws_region"] = st.session_state.email_aws_region_val_cfg.strip() or None
                        if aws_key_val: payload["aws_access_key_id"] = aws_key_val
                        if aws_secret_val: payload["aws_secret_access_key"] = aws_secret_val
                        if not payload["aws_region"]: # Basic check for AWS
                            st.error("For AWS SES, Region is required."); valid_save=False
                        # Add check for keys if not previously set
                        if not (aws_key_val or aws_secret_val) and not (current_email_cfg.get('provider_type') == "AWS_SES" and current_email_cfg.get('credentials_set')):
                            st.error("For AWS SES, Access Key and Secret Key are required on first setup."); valid_save=False


                    if valid_save:
                        with st.spinner("Saving..."): result = save_email_settings(payload, auth_token)
                        if result: 
                            st.session_state.email_settings_save_success_config_tab = "Email settings saved."
                            st.session_state.email_settings_loaded_config_tab = False
                        # else: error handled by API helper
                        st.rerun()

#    elif current_page_selected == "Setup Assistant" :
 #      st.header("🤖 Setup Assistant")
  #     st.info("Guided setup and Q&A coming soon!")

  #  else:
   #    st.error("Page not found.")
