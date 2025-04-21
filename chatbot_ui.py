# chatbot_ui.py

import streamlit as st
import requests
import json
import time
import re
import csv # For parsing manual input

# --- Configuration ---
BACKEND_URL = "https://salestroopz-backendpython-m-uvicorn-app.onrender.com" # Replace if needed
INITIATE_ENDPOINT = f"{BACKEND_URL}/api/v1/workflow/initiate"
FILE_UPLOAD_ENDPOINT = f"{BACKEND_URL}/api/v1/files/upload"
ALLOWED_SOURCES = ["file_upload", "apollo", "crm", "manual_entry"]
ALLOWED_SOURCES_DISPLAY = ["File Upload", "Apollo", "CRM", "Manual Entry"]
COMMON_GREETINGS = ["hi", "hello", "hey", "yo", "ok", "okay", "thanks", "thank you", "hi!", "hello!"]

# --- Helper Function to call Backend ---
def initiate_backend_workflow(icp_data, source_type, source_details=None):
    """Sends the collected data to the FastAPI backend."""
    payload = {
        "icp": icp_data or {}, # Ensure icp is at least an empty dict
        "source_type": source_type,
        "source_details": source_details or {}
    }
    print(f"DEBUG: Sending payload to backend: {payload}") # Log payload
    try:
        headers = {'Content-Type': 'application/json'}
        # Increased timeout for potentially longer background processing triggers
        response = requests.post(INITIATE_ENDPOINT, headers=headers, data=json.dumps(payload), timeout=60)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.Timeout:
        st.error("Backend request timed out. The process might still be running. Please check results later or type 'restart'.")
        return None
    except requests.exceptions.HTTPError as http_err:
        # Try to get detail from response if possible
        error_detail = f"HTTP error contacting backend: {http_err}"
        try:
            error_detail = http_err.response.json().get("detail", error_detail)
        except: pass # Ignore if response isn't JSON
        st.error(f"{error_detail}. You can type 'restart' to try again.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Network error contacting backend: {e}. You can type 'restart' to try again.")
        return None
    except json.JSONDecodeError:
        st.error(f"Backend returned an unexpected response: {response.text[:200]}... You can type 'restart'.")
        return None
    except Exception as e: # Catch any other unexpected errors
        st.error(f"An unexpected error occurred: {e}. You can type 'restart'.")
        return None


# --- Function to add message to chat history ---
def add_message(role, content):
    """Adds a message to the chat history."""
    # Initialize messages list if it doesn't exist
    if "messages" not in st.session_state:
        st.session_state.messages = []
    # Append new message
    st.session_state.messages.append({"role": role, "content": content})

# --- Define Prompts Dictionary (defined early) ---
# Using lambda for confirm prompt to ensure it gets fresh state
assistant_prompts = {
    "ask_industry": "What industry are you targeting?",
    "ask_title": "Got it. Now, what specific job title(s) are you looking for?",
    "ask_company_size": "Okay. What company size are you targeting? (e.g., '1-10', '11-50', '51-200', '201-500', '500+')",
    "ask_source": f"Great! Now, where should I get the leads from? Please choose one: {', '.join(ALLOWED_SOURCES_DISPLAY)}.",
    "awaiting_upload": "Okay, please upload your CSV or Excel file containing the leads.",
    "ask_manual_leads": """Okay, please enter the lead details below.
Enter one lead per line. Use commas to separate fields: **Email, Name, Company, Title**.
Email is required. Other fields are optional (e.g., `lead@example.com,Lead Name,,Job Title`).""",
    "confirm": lambda state: f"""
Okay, let's confirm:
- **Industry:** {state.get('icp_details', {}).get('industry', '*(Not set)*')}
- **Title(s):** {state.get('icp_details', {}).get('title', '*(Not set)*')}
- **Company Size:** {state.get('icp_details', {}).get('company_size', '*(Not set)*')}
- **Lead Source:** {(lead_source := state.get('lead_source')) and lead_source.replace('_',' ').title() or '*(Not set)*'}
{f"- **Uploaded File:** {state.get('uploaded_file_info',{}).get('original_filename','*Unknown*')}" if state.get('lead_source') == 'file_upload' else ''}
{f"- **Manual Leads Entered:** {len(state.get('manual_leads', []))}" if state.get('lead_source') == 'manual_entry' else ''}

Is this correct? (Please type **Yes** to proceed, or **No** to restart)
""",
    "done": "Setup complete. I've sent the request to the backend. Processing will happen in the background. You can type 'restart' to begin a new setup."
}

# --- Function to reset chat state ---
def reset_chat():
    """Resets the chat state and displays initial greeting + first question."""
    print("DEBUG: Resetting chat state") # Log reset
    st.session_state.messages = []
    st.session_state.stage = "greeting" # Temporarily set to greeting
    st.session_state.icp_details = {}
    st.session_state.lead_source = None
    st.session_state.processing_initiated = False
    st.session_state.uploaded_filename = None
    st.session_state.uploaded_file_info = None
    st.session_state.manual_leads = [] # Clear manual leads

    # Add initial messages
    add_message("assistant", "Hi! I'm here to help you set up your SalesTroopz campaign. Let's define your Ideal Customer Profile (ICP). (You can type 'restart' anytime to start over).")
    st.session_state.stage = "ask_industry" # Set stage for the first question
    # Explicitly add the first prompt message right after reset
    add_message("assistant", assistant_prompts[st.session_state.stage])


# --- Initialize Session State ---
if "messages" not in st.session_state:
    reset_chat()
    st.rerun() # Rerun once after initial reset to ensure first prompt displays

# --- Display Chat History ---
st.title("SalesTroopz Agent Setup")
for message in st.session_state.get("messages", []):
    with st.chat_message(message["role"]):
        # Use markdown with careful newline handling
        st.markdown(message["content"].replace("\n", "  \n"), unsafe_allow_html=True)


# --- Display Stage-Specific Widgets (File Uploader, Text Area) ---
current_stage = st.session_state.get("stage", "greeting")

# File uploader widget shown only when awaiting upload
if current_stage == "awaiting_upload":
    uploaded_file = st.file_uploader(
        "Choose a CSV or XLSX file",
        type=['csv', 'xlsx'],
        key=f"file_uploader_{time.time()}" # Attempt to force reset on rerun if needed
        )
    if uploaded_file is not None:
        # Avoid re-uploading same instance on natural reruns
        if uploaded_file != st.session_state.get("_processed_upload"):
            st.session_state._processed_upload = uploaded_file # Mark as processed for this run
            add_message("user", f"Uploaded file: {uploaded_file.name}")
            with st.spinner(f"Uploading {uploaded_file.name}..."):
                files = {'file': (uploaded_file.name, uploaded_file, uploaded_file.type)}
                # ... (Rest of file upload POST request logic - Keep existing error handling) ...
                upload_error = None; response_json = None
                try:
                    response = requests.post(FILE_UPLOAD_ENDPOINT, files=files, timeout=60)
                    response.raise_for_status(); response_json = response.json()
                    if "filename" not in response_json: upload_error = "Backend missing filename."
                except requests.exceptions.Timeout: upload_error = "Upload timed out."
                except requests.exceptions.RequestException as e: upload_error = f"Upload Error: {e}" # Add more detail below
                except json.JSONDecodeError: upload_error = f"Upload Error: Bad backend response '{response.text[:50]}...'"
                except Exception as e: upload_error = f"Upload Error: {e}"
                # Try get detail from response on RequestException
                if isinstance(e, requests.exceptions.RequestException):
                     try: upload_error = f"Upload Error: {e.response.json().get('detail', str(e))}"
                     except: pass

                if upload_error:
                    add_message("assistant", f"❌ Error: {upload_error}. Please try again.")
                    st.session_state.uploaded_filename = None; st.session_state.uploaded_file_info = None
                else:
                    st.session_state.uploaded_filename = response_json["filename"]
                    st.session_state.uploaded_file_info = {"original_filename": response_json.get("original_filename", uploaded_file.name), "backend_filename": response_json["filename"]}
                    add_message("assistant", f"✅ File '{st.session_state.uploaded_file_info['original_filename']}' uploaded successfully!")
                    st.session_state.lead_source = "file_upload" # Set source
                    st.session_state.stage = "confirm" # Move to confirmation
                    st.rerun() # Rerun to display confirmation

# Manual Lead Input Area (only when asking for manual leads)
elif current_stage == "ask_manual_leads":
    manual_input_text = st.text_area(
        "Enter leads (Email, Name, Company, Title - one per line)",
        height=150,
        key="manual_leads_input"
        )
    if st.button("Submit Manual Leads", key="submit_manual"):
        # Store text temporarily and rerun to process it below
        st.session_state._manual_text_to_process = manual_input_text
        st.rerun()


# --- Process Submitted Manual Leads (if text is stored) ---
if "_manual_text_to_process" in st.session_state:
    input_text = st.session_state.pop("_manual_text_to_process") # Process only once
    parsed_leads = []
    parse_errors = []
    if input_text.strip():
        add_message("user", f"Entered Manual Leads:\n```\n{input_text}\n```")
        lines = input_text.strip().split('\n')
        reader = csv.reader(lines)
        line_num = 0
        for row in reader:
            line_num += 1
            if not row or not any(field.strip() for field in row): continue

            email = row[0].strip() if len(row) > 0 else None
            name = row[1].strip() if len(row) > 1 else None
            company = row[2].strip() if len(row) > 2 else None
            title = row[3].strip() if len(row) > 3 else None

            if not email or '@' not in email or '.' not in email.split('@')[-1]:
                parse_errors.append(f"Line {line_num}: Invalid/missing email ('{email or ''}'). Skipped.")
                continue

            parsed_leads.append({"email": email, "name": name or None, "company": company or None, "title": title or None})

        if parse_errors:
            add_message("assistant", "⚠️ Found issues with some lines:\n" + "\n".join([f"- {e}" for e in parse_errors]))

        if parsed_leads:
            st.session_state.manual_leads = parsed_leads
            st.session_state.lead_source = "manual_entry" # Set source type
            add_message("assistant", f"Successfully parsed {len(parsed_leads)} leads. Please review the confirmation below.")
            st.session_state.stage = "confirm" # Move to confirmation
        elif not parse_errors:
             add_message("assistant", "No valid leads found in the input. Please try entering again (Email, Name, Company, Title).")
             st.session_state.stage = "ask_manual_leads" # Stay here
        # If only errors, stay in this stage as well

    else:
        add_message("assistant", "You didn't enter any leads. Please enter lead details or type 'restart'.")
        st.session_state.stage = "ask_manual_leads" # Stay here

    st.rerun() # Rerun needed to show messages/confirmation


# --- Handle Chat Input (for non-widget stages) ---
if prompt := st.chat_input("Your response...",
                           # Disable if processing done OR if waiting for widget input
                           disabled=(st.session_state.get("processing_initiated", False) or current_stage in ["awaiting_upload", "ask_manual_leads"]),
                           key="user_input"):
    add_message("user", prompt)
    processed_prompt = prompt.strip()
    next_stage = st.session_state.stage # Default to staying in current stage

    # --- Global Restart Check ---
    if processed_prompt.lower() in ["restart", "start over", "reset"]:
        add_message("assistant", "Okay, restarting the conversation.")
        reset_chat()
        st.rerun()
        st.stop() # Stop current script execution after reset

    # --- Stage-Specific Input Processing ---
    current_stage = st.session_state.stage # Re-fetch stage after potential reset

    if current_stage == "ask_industry":
        if processed_prompt.lower() in COMMON_GREETINGS:
            add_message("assistant", f"{processed_prompt.capitalize()} to you too! Let's get started.")
            next_stage = "ask_industry" # Stay here, prompt logic will re-ask
        elif processed_prompt:
            st.session_state.icp_details['industry'] = processed_prompt
            next_stage = "ask_title"
        else:
            add_message("assistant", "Industry cannot be empty. Please tell me the target industry.")
            # next_stage remains "ask_industry"

    elif current_stage == "ask_title":
        if processed_prompt:
            st.session_state.icp_details['title'] = processed_prompt
            next_stage = "ask_company_size"
        else:
            add_message("assistant", "Title cannot be empty. Please provide the target job title(s).")
            # next_stage remains "ask_title"

    elif current_stage == "ask_company_size":
        if processed_prompt and (re.search(r'\d', processed_prompt) or any(s in processed_prompt.lower() for s in ['small', 'medium', 'large', 'enterprise', '+', '-'])):
            st.session_state.icp_details['company_size'] = processed_prompt
            next_stage = "ask_source"
        elif not processed_prompt:
             add_message("assistant", "Company size cannot be empty. Please provide a target size range (e.g., '11-50', '500+').")
             # next_stage remains "ask_company_size"
        else:
             add_message("assistant", f"'{prompt}' doesn't look like a standard company size. Please provide a range like '11-50', '500+', or describe it. Let's try that again.")
             # next_stage remains "ask_company_size"

    elif current_stage == "ask_source":
        source_input = processed_prompt.lower().replace(" ", "_")
        if source_input == "file_upload":
            next_stage = "awaiting_upload" # Transition to upload stage
            st.session_state.uploaded_filename = None # Clear previous upload info
            st.session_state.uploaded_file_info = None
        elif source_input == "manual_entry":
            next_stage = "ask_manual_leads" # Transition to manual entry stage
            st.session_state.manual_leads = [] # Clear previous manual leads
        elif source_input in ALLOWED_SOURCES: # Handle Apollo, CRM (go direct to confirm)
            st.session_state.lead_source = source_input
            next_stage = "confirm"
        else:
            add_message("assistant", f"Sorry, '{prompt}' is not a valid source. Please choose only from: {', '.join(ALLOWED_SOURCES_DISPLAY)}.")
            next_stage = "ask_source" # Stay here

    elif current_stage == "confirm":
        if processed_prompt.lower() == 'yes':
            next_stage = "done" # Tentatively set stage to done
            st.session_state.processing_initiated = True # Indicate processing starts
            source_details_to_send = {}
            is_ready_to_send = True # Flag to check if data is ready

            if st.session_state.lead_source == "file_upload":
                 if st.session_state.get("uploaded_filename"):
                     source_details_to_send["filename"] = st.session_state.uploaded_filename
                 else:
                      add_message("assistant", "❌ Error: No file seems to be uploaded. Please type 'restart'.")
                      st.session_state.processing_initiated = False # Allow restart
                      next_stage = "confirm" # Revert stage
                      is_ready_to_send = False
            elif st.session_state.lead_source == "manual_entry":
                if st.session_state.get("manual_leads"):
                     source_details_to_send["manual_leads"] = st.session_state.manual_leads
                else:
                      add_message("assistant", "❌ Error: No manual leads were entered/parsed. Please type 'restart'.")
                      st.session_state.processing_initiated = False
                      next_stage = "confirm" # Revert stage
                      is_ready_to_send = False
            # Add elif for apollo/crm if they need specific source_details validation

            # Call backend only if data is ready
            if is_ready_to_send:
                with st.spinner("Sending request to backend... Processing may take time."):
                     backend_response = initiate_backend_workflow(
                         st.session_state.icp_details,
                         st.session_state.lead_source,
                         source_details_to_send
                     )
                if backend_response:
                     add_message("assistant", f"✅ Backend acknowledged the request! Response: ```{json.dumps(backend_response, indent=2)}```")
                     # Add the final "done" message below
                else:
                     # Error messages handled by initiate_backend_workflow, but reset state
                     st.session_state.processing_initiated = False
                     next_stage = "confirm" # Revert stage on backend error
                     # Let user decide to restart or try confirm again? Maybe add message.
                     add_message("assistant", "There was an issue sending the request to the backend. You can try confirming again or type 'restart'.")

        elif processed_prompt.lower() == 'no':
             add_message("assistant", "Okay, discarding current setup. Let's restart.")
             reset_chat()
             st.rerun()
             st.stop()
        else:
            add_message("assistant", "Please confirm with 'Yes' or 'No'.")
            next_stage = "confirm" # Stay in confirm stage


    # --- Update Stage & Add Next Prompt ---
    previous_stage = st.session_state.stage
    st.session_state.stage = next_stage

    # Add the prompt for the *new* stage, if stage changed and needs one
    if next_stage != previous_stage and next_stage in assistant_prompts:
        prompt_content = assistant_prompts[next_stage]
        # Dynamically call lambda for confirm prompt
        if callable(prompt_content):
            # Check if stage is 'confirm' before calling lambda to ensure state is ready
            if next_stage == 'confirm':
                add_message("assistant", prompt_content(st.session_state))
        elif next_stage != "done": # Don't add prompt automatically if 'done'
            add_message("assistant", prompt_content)

    # Add final "done" message only if stage is done AND processing was initiated
    if st.session_state.stage == "done" and st.session_state.processing_initiated:
         add_message("assistant", assistant_prompts["done"])


    # --- Rerun to display updates ---
    st.rerun()


    # --- Rerun to display updates ---
    st.rerun()
