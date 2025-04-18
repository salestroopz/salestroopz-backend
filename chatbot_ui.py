# chatbot_ui.py
import streamlit as st
import requests
import json
import time
import re # Import regex for slightly better validation

# --- Configuration ---
BACKEND_URL = "https://salestroopz-backendpython-m-uvicorn-app.onrender.com" # Replace if needed
INITIATE_ENDPOINT = f"{BACKEND_URL}/api/v1/workflow/initiate"
ALLOWED_SOURCES = ["file_upload", "apollo", "crm", "manual_entry"]
ALLOWED_SOURCES_DISPLAY = ["File Upload", "Apollo", "CRM", "Manual Entry"] # For display

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
        response = requests.post(INITIATE_ENDPOINT, headers=headers, data=json.dumps(payload), timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        st.error("Backend request timed out. Please try again later or type 'restart'.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Error contacting backend: {e}. You can type 'restart' to try again.")
        return None
    except json.JSONDecodeError:
        st.error(f"Backend returned non-JSON response: {response.text}. You can type 'restart'.")
        return None

# --- Function to add message (basic duplicate check) ---
def add_message(role, content):
    if not st.session_state.messages or st.session_state.messages[-1]['content'] != content:
        st.session_state.messages.append({"role": role, "content": content})

# --- Function to reset chat state ---
def reset_chat():
    st.session_state.messages = []
    st.session_state.stage = "greeting"
    st.session_state.icp_details = {}
    st.session_state.lead_source = None
    st.session_state.processing_initiated = False
    # Add initial greeting message after reset
    add_message("assistant", "Hi! I'm here to help you set up your SalesTroopz campaign. Let's start by defining your Ideal Customer Profile (ICP). What industry are you targeting? (You can type 'restart' anytime to start over).")
    st.session_state.stage = "ask_industry" # Set stage for next input


# --- Initialize Session State ---
if "messages" not in st.session_state:
    reset_chat() # Initialize state properly


# --- Display Chat History ---
st.title("SalesTroopz Agent Setup")
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"].replace("\n", "  \n")) # Ensure markdown newlines render

# --- Display Current Prompt (based on stage, only if needed) ---
# This logic tries to avoid re-prompting immediately after an error message was just added.
assistant_prompts = {
    "ask_industry": "What industry are you targeting? (You can type 'restart' anytime to start over).",
    "ask_title": "Got it. Now, what specific job title(s) are you looking for?",
    "ask_company_size": "Okay. What company size are you targeting? (e.g., '1-10', '11-50', '51-200', '201-500', '500+')",
    "ask_source": f"Great! Now, where should I get the leads from? Please choose one: {', '.join(ALLOWED_SOURCES_DISPLAY)}.",
    "confirm": f"""
Okay, let's confirm:
- **Industry:** {st.session_state.icp_details.get('industry', '*(Not set)*')}
- **Title(s):** {st.session_state.icp_details.get('title', '*(Not set)*')}
- **Company Size:** {st.session_state.icp_details.get('company_size', '*(Not set)*')}
- **Lead Source:** {st.session_state.lead_source.replace('_',' ').title() if st.session_state.lead_source else '*(Not set)*'}

Is this correct? (Please type **Yes** to proceed, or **No** to restart)
""",
    "done": "Setup complete. I've sent the request to the backend. Processing will happen in the background."
}

current_stage = st.session_state.get("stage", "greeting")
# Display prompt only if conversation is ongoing and the last message wasn't already this prompt
if current_stage in assistant_prompts and not st.session_state.processing_initiated:
    prompt_text = assistant_prompts[current_stage]
    # Check if the last message is from the assistant and is different from the current prompt
    if not st.session_state.messages or \
       (st.session_state.messages[-1]['role'] == 'user') or \
       (st.session_state.messages[-1]['role'] == 'assistant' and st.session_state.messages[-1]['content'] != prompt_text):
        add_message("assistant", prompt_text)


# --- Handle User Input ---
if prompt := st.chat_input("Your response...", disabled=st.session_state.processing_initiated):
    add_message("user", prompt) # Display user message first
    processed_prompt = prompt.strip()
    rerun_needed = True # Assume a rerun is needed unless handled otherwise

    # --- Global Restart Check ---
    if processed_prompt.lower() in ["restart", "start over", "reset"]:
        add_message("assistant", "Okay, restarting the conversation.")
        reset_chat()
        st.rerun() # Force immediate rerun after reset

    # --- Stage-Specific Input Processing ---
    current_stage = st.session_state.stage # Get current stage again after potential reset

    if current_stage == "ask_industry":
        if processed_prompt:
            st.session_state.icp_details['industry'] = processed_prompt
            st.session_state.stage = "ask_title"
        else:
            add_message("assistant", "Industry cannot be empty. Please tell me the target industry.")

    elif current_stage == "ask_title":
        if processed_prompt:
            st.session_state.icp_details['title'] = processed_prompt
            st.session_state.stage = "ask_company_size"
        else:
            add_message("assistant", "Title cannot be empty. Please provide the target job title(s).")

    elif current_stage == "ask_company_size":
         # Basic check: contains numbers or typical size ranges/words
        if processed_prompt and (re.search(r'\d', processed_prompt) or any(s in processed_prompt.lower() for s in ['small', 'medium', 'large', 'enterprise', '+', '-'])):
            st.session_state.icp_details['company_size'] = processed_prompt
            st.session_state.stage = "ask_source"
        elif not processed_prompt:
             add_message("assistant", "Company size cannot be empty. Please provide a target size range (e.g., '11-50', '500+').")
        else:
             add_message("assistant", f"'{prompt}' doesn't look like a standard company size. Please provide a range like '11-50', '500+', or describe it (e.g., 'Large Enterprise'). Let's try that again.")
             # Stay in the same stage, error message added

    elif current_stage == "ask_source":
        source_input = processed_prompt.lower().replace(" ", "_")
        if source_input in ALLOWED_SOURCES:
            st.session_state.lead_source = source_input
            st.session_state.stage = "confirm"
        else:
            # Stay in the same stage, show error
            add_message("assistant", f"Sorry, '{prompt}' is not a valid source. Please choose only from: {', '.join(ALLOWED_SOURCES_DISPLAY)}.")

    elif current_stage == "confirm":
        if processed_prompt.lower() == 'yes':
            st.session_state.stage = "done" # Move to final stage
            with st.spinner("Sending request to backend..."):
                 backend_response = initiate_backend_workflow(
                     st.session_state.icp_details,
                     st.session_state.lead_source
                 )
            if backend_response:
                 # Add backend message, final "done" message will be shown by prompt logic
                 add_message("assistant", f"Backend acknowledged! Response details: ```{json.dumps(backend_response, indent=2)}```")
                 st.session_state.processing_initiated = True # Disable input now
            # No else needed, error handled in initiate_backend_workflow which adds message
        elif processed_prompt.lower() == 'no':
             add_message("assistant", "Okay, discarding current setup. Let's restart.")
             reset_chat()
        else:
            add_message("assistant", "Please confirm with 'Yes' or 'No'.")
            # Stay in confirm stage

    # Rerun Streamlit to reflect state changes, display new prompts/messages
    st.rerun()
    
