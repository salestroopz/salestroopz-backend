import streamlit as st
import requests
import json
import time
import re

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
    """Adds a message to the chat history if it's new."""
    # Ensure messages list exists
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Add message only if list is empty or last message content is different
    if not st.session_state.messages or st.session_state.messages[-1]['content'] != content:
        st.session_state.messages.append({"role": role, "content": content})

# --- Function to reset chat state ---
def reset_chat():
    """Resets the chat state to the beginning."""
    st.session_state.messages = []
    st.session_state.stage = "greeting" # Start at greeting stage
    st.session_state.icp_details = {}
    st.session_state.lead_source = None
    st.session_state.processing_initiated = False
    # Add the initial greeting message
    add_message("assistant", "Hi! I'm here to help you set up your SalesTroopz campaign. Let's define your Ideal Customer Profile (ICP). (You can type 'restart' anytime to start over).")
    # Set stage ready for the first question
    st.session_state.stage = "ask_industry"
    # --- ADD RERUN HERE ---
    # Force Streamlit to rerun the script immediately. This ensures the
    # prompt display logic below runs and shows the first question.
    st.rerun()


# --- Initialize Session State ---
if "messages" not in st.session_state:
    reset_chat() # Initialize state properly (will now trigger a rerun)

# --- Display Chat History ---
st.title("SalesTroopz Agent Setup")
for message in st.session_state.get("messages", []):
    with st.chat_message(message["role"]):
        st.markdown(message["content"].replace("\n", "  \n"))

# --- Display Current Prompt Logic (Should now work correctly on first load) ---
assistant_prompts = {
    "ask_industry": "What industry are you targeting?",
    # ... (rest of prompts remain the same) ...
    "ask_title": "Got it. Now, what specific job title(s) are you looking for?",
    "ask_company_size": "Okay. What company size are you targeting? (e.g., '1-10', '11-50', '51-200', '201-500', '500+')",
    "ask_source": f"Great! Now, where should I get the leads from? Please choose one: {', '.join(ALLOWED_SOURCES_DISPLAY)}.",
    "confirm": f"""
Okay, let's confirm:
- **Industry:** {st.session_state.get('icp_details', {}).get('industry', '*(Not set)*')}
- **Title(s):** {st.session_state.get('icp_details', {}).get('title', '*(Not set)*')}
- **Company Size:** {st.session_state.get('icp_details', {}).get('company_size', '*(Not set)*')}
- **Lead Source:** {(lead_source := st.session_state.get('lead_source')) and lead_source.replace('_',' ').title() or '*(Not set)*'}

Is this correct? (Please type **Yes** to proceed, or **No** to restart)
""",
    "done": "Setup complete. I've sent the request to the backend. Processing will happen in the background. You can close this window or type 'restart' to begin again."
}

current_stage = st.session_state.get("stage", "greeting")

should_display_prompt = False
if current_stage in assistant_prompts and not st.session_state.get("processing_initiated", False):
    prompt_text = assistant_prompts[current_stage]
    if not st.session_state.get("messages"):
         should_display_prompt = True
    else:
        last_msg = st.session_state.messages[-1]
        if last_msg['role'] == 'user':
             should_display_prompt = True
        elif last_msg['role'] == 'assistant':
            is_standard_prompt = (last_msg['content'] == prompt_text)
            is_error_reprompt = "Sorry," in last_msg['content'] or "cannot be empty" in last_msg['content'] or "doesn't look like" in last_msg['content'] or "Please confirm" in last_msg['content']

            if not is_standard_prompt and not is_error_reprompt:
                 should_display_prompt = True

if should_display_prompt:
     add_message("assistant", prompt_text)


# --- Handle User Input ---
# ... (rest of the input handling code remains the same) ...
if prompt := st.chat_input("Your response...", disabled=st.session_state.get("processing_initiated", False), key="user_input"):
    # ... (input handling logic) ...
    pass # Placeholder for brevity

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
            rerun_needed = True # Need to rerun to show next prompt
        else:
            add_message("assistant", "Industry cannot be empty. Please tell me the target industry.")
            rerun_needed = True

    elif current_stage == "ask_title":
        if processed_prompt:
            st.session_state.icp_details['title'] = processed_prompt
            st.session_state.stage = "ask_company_size"
            rerun_needed = True
        else:
            add_message("assistant", "Title cannot be empty. Please provide the target job title(s).")
            rerun_needed = True

    elif current_stage == "ask_company_size":
        if processed_prompt and (re.search(r'\d', processed_prompt) or any(s in processed_prompt.lower() for s in ['small', 'medium', 'large', 'enterprise', '+', '-'])):
            st.session_state.icp_details['company_size'] = processed_prompt
            st.session_state.stage = "ask_source"
            rerun_needed = True
        elif not processed_prompt:
             add_message("assistant", "Company size cannot be empty. Please provide a target size range (e.g., '11-50', '500+').")
             rerun_needed = True
        else:
             add_message("assistant", f"'{prompt}' doesn't look like a standard company size. Please provide a range like '11-50', '500+', or describe it (e.g., 'Large Enterprise'). Let's try that again.")
             rerun_needed = True

    elif current_stage == "ask_source":
        source_input = processed_prompt.lower().replace(" ", "_")
        if source_input in ALLOWED_SOURCES:
            st.session_state.lead_source = source_input
            st.session_state.stage = "confirm"
            rerun_needed = True
        else:
            add_message("assistant", f"Sorry, '{prompt}' is not a valid source. Please choose only from: {', '.join(ALLOWED_SOURCES_DISPLAY)}.")
            rerun_needed = True # Rerun needed to show the error message

    elif current_stage == "confirm":
        if processed_prompt.lower() == 'yes':
            st.session_state.stage = "done" # Move to final stage
            with st.spinner("Sending request to backend..."):
                 backend_response = initiate_backend_workflow(
                     st.session_state.icp_details,
                     st.session_state.lead_source
                 )
            if backend_response:
                 add_message("assistant", f"Backend acknowledged! Response details: ```{json.dumps(backend_response, indent=2)}```")
                 st.session_state.processing_initiated = True # Disable input now
            # Error message handled by initiate_backend_workflow
            rerun_needed = True # Rerun to display the "done" message and disable input

        elif processed_prompt.lower() == 'no':
             add_message("assistant", "Okay, discarding current setup. Let's restart.")
             reset_chat()
             st.rerun() # Need immediate rerun after reset
        else:
            add_message("assistant", "Please confirm with 'Yes' or 'No'.")
            rerun_needed = True # Rerun to show this message

    # Only rerun if specifically flagged
    if rerun_needed:
        st.rerun()
