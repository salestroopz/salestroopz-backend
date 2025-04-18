# chatbot_ui.py
import streamlit as st
import requests
import json
import time # Added for potential delays

# --- Configuration ---
BACKEND_URL = "https://salestroopz-backendpython-m-uvicorn-app.onrender.com" # Replace if needed
INITIATE_ENDPOINT = f"{BACKEND_URL}/api/v1/workflow/initiate"

# --- Helper Function to call Backend ---
def initiate_backend_workflow(icp_data, source_type, source_details=None):
    """Sends the collected data to the FastAPI backend."""
    payload = {
        "icp": icp_data,
        "source_type": source_type,
        "source_details": source_details or {}
    }
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.post(INITIATE_ENDPOINT, headers=headers, data=json.dumps(payload), timeout=30) # Added timeout
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        st.error("Backend request timed out. Please try again later.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error contacting backend: {e}")
        return None
    except json.JSONDecodeError:
        st.error(f"Backend returned non-JSON response: {response.text}")
        return None

# --- Initialize Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "stage" not in st.session_state:
    st.session_state.stage = "greeting"
if "icp_details" not in st.session_state:
    st.session_state.icp_details = {}
if "lead_source" not in st.session_state:
    st.session_state.lead_source = None
if "processing_initiated" not in st.session_state: # Renamed for clarity
    st.session_state.processing_initiated = False

# --- Function to add message (avoids duplicates slightly better) ---
def add_message(role, content):
    # Add message only if it's different from the last one from the same role
    if not st.session_state.messages or \
       st.session_state.messages[-1]['role'] != role or \
       st.session_state.messages[-1]['content'] != content:
        st.session_state.messages.append({"role": role, "content": content})

# --- Display Chat History ---
st.title("SalesTroopz Agent Setup")
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Conversation Logic & Prompt Display ---
# This section now focuses ONLY on displaying the correct prompt based on the stage
if st.session_state.stage == "greeting":
    add_message("assistant", "Hi! I'm here to help you set up your SalesTroopz campaign. Let's start by defining your Ideal Customer Profile (ICP). What industry are you targeting?")
    st.session_state.stage = "ask_industry"
    st.rerun() # Rerun needed here to show prompt before input

elif st.session_state.stage == "ask_industry":
    # Prompt was shown in the previous step. Wait for input.
    pass

elif st.session_state.stage == "ask_title":
    add_message("assistant", "Got it. Now, what specific job title(s) are you looking for within that industry?")
    # No rerun here, wait for input

elif st.session_state.stage == "ask_company_size":
    add_message("assistant", "Okay. What company size are you targeting? (e.g., '1-10', '11-50', '51-200', '201-500', '500+')")
    # No rerun here

elif st.session_state.stage == "ask_source":
    add_message("assistant", "Great! Now, where should I get the leads from? Please choose one: 'File Upload', 'Apollo', 'CRM', or 'Manual Entry'.")
    # No rerun here - THIS SHOULD FIX THE LOOP

elif st.session_state.stage == "confirm":
    confirmation_message = f"""
Okay, let's confirm:
- **Industry:** {st.session_state.icp_details.get('industry', 'Not set')}
- **Title(s):** {st.session_state.icp_details.get('title', 'Not set')}
- **Company Size:** {st.session_state.icp_details.get('company_size', 'Not set')}
- **Lead Source:** {st.session_state.lead_source}

Is this correct? (Please type 'Yes' to proceed, or 'No' to restart)
"""
    add_message("assistant", confirmation_message)
    # No rerun here

elif st.session_state.stage == "done":
    if not st.session_state.processing_initiated: # Check flag before adding message
        add_message("assistant", "Okay, I've sent the request to the backend to start the process based on your criteria. Check backend logs or status later.")
        st.session_state.processing_initiated = True # Set flag
    # No rerun here

# --- Handle User Input ---
# Input is disabled once processing is initiated
if prompt := st.chat_input("Your response...", disabled=st.session_state.processing_initiated):
    add_message("user", prompt) # Display user message first

    rerun_needed = False # Flag to check if we need to rerun after processing input

    # Process based on current stage
    if st.session_state.stage == "ask_industry":
        if prompt.strip(): # Basic Validation: Check if not empty
            st.session_state.icp_details['industry'] = prompt.strip()
            st.session_state.stage = "ask_title" # Move to next stage
        else:
            add_message("assistant", "Industry cannot be empty. Please tell me the target industry.")
            rerun_needed = True # Need to rerun to show error prompt

    elif st.session_state.stage == "ask_title":
        if prompt.strip(): # Basic Validation
            st.session_state.icp_details['title'] = prompt.strip()
            st.session_state.stage = "ask_company_size"
        else:
            add_message("assistant", "Title cannot be empty. Please provide the target job title(s).")
            rerun_needed = True

    elif st.session_state.stage == "ask_company_size":
        if prompt.strip(): # Basic Validation
            st.session_state.icp_details['company_size'] = prompt.strip()
            st.session_state.stage = "ask_source"
        else:
            add_message("assistant", "Company size cannot be empty. Please provide a target size range.")
            rerun_needed = True

    elif st.session_state.stage == "ask_source":
        allowed_sources = ["file upload", "apollo", "crm", "manual entry"]
        processed_prompt = prompt.strip().lower()
        if processed_prompt in allowed_sources:
            st.session_state.lead_source = processed_prompt.replace(" ", "_") # Standardize
            st.session_state.stage = "confirm" # Move to confirmation
        else:
            add_message("assistant", f"Sorry, '{prompt}' is not a valid source. Please choose only from 'File Upload', 'Apollo', 'CRM', or 'Manual Entry'.")
            rerun_needed = True # Re-ask the source question

    elif st.session_state.stage == "confirm":
        if prompt.strip().lower() == 'yes':
            st.session_state.stage = "done" # Move to final stage
            # Call the backend API
            with st.spinner("Sending request to backend..."):
                 backend_response = initiate_backend_workflow(
                     st.session_state.icp_details,
                     st.session_state.lead_source
                 )
            if backend_response:
                 add_message("assistant", f"Backend acknowledged! Response: ```{json.dumps(backend_response, indent=2)}```")
                 # Message indicating completion will be handled by the 'done' stage logic
            # No else needed, error handled in initiate_backend_workflow
            rerun_needed = True # Rerun to display the "done" message and disable input

        elif prompt.strip().lower() == 'no':
             add_message("assistant", "Okay, let's restart the process.")
             # Reset state
             st.session_state.stage = "greeting"
             st.session_state.messages = [] # Clear history for restart
             st.session_state.icp_details = {}
             st.session_state.lead_source = None
             st.session_state.processing_initiated = False
             rerun_needed = True # Rerun to start from greeting
        else:
            add_message("assistant", "Please confirm with 'Yes' to proceed or 'No' to restart.")
            rerun_needed = True # Rerun to show error prompt

    # Only rerun if needed (e.g., after showing an error or moving to next stage)
    if rerun_needed:
        st.rerun()
    
