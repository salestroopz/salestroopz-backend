# chatbot_ui.py
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
COMMON_GREETINGS = ["hi", "hello", "hey", "yo", "ok", "okay", "thanks", "thank you", "hi!", "hello!"] # For handling initial greetings

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
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if not st.session_state.messages or st.session_state.messages[-1]['content'] != content:
        st.session_state.messages.append({"role": role, "content": content})

# --- Function to reset chat state ---
def reset_chat():
    """Resets the chat state to the beginning."""
    st.session_state.messages = []
    st.session_state.stage = "greeting"
    st.session_state.icp_details = {}
    st.session_state.lead_source = None
    st.session_state.processing_initiated = False
    add_message("assistant", "Hi! I'm here to help you set up your SalesTroopz campaign. Let's define your Ideal Customer Profile (ICP). (You can type 'restart' anytime to start over).")
    st.session_state.stage = "ask_industry"
    st.rerun()

# --- Initialize Session State ---
if "messages" not in st.session_state:
    reset_chat()

# --- Display Chat History ---
st.title("SalesTroopz Agent Setup")
for message in st.session_state.get("messages", []):
    with st.chat_message(message["role"]):
        st.markdown(message["content"].replace("\n", "  \n"))

# --- Display Current Prompt Logic ---
# ... (This block remains the same as the previous working version) ...
assistant_prompts = {
    "ask_industry": "What industry are you targeting?",
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
# --- End of Display Current Prompt Logic ---


# --- Handle User Input ---
if prompt := st.chat_input("Your response...", disabled=st.session_state.get("processing_initiated", False), key="user_input"):
    add_message("user", prompt) # Display user message first
    processed_prompt = prompt.strip()
    rerun_needed = True

    # --- Global Restart Check ---
    if processed_prompt.lower() in ["restart", "start over", "reset"]:
        add_message("assistant", "Okay, restarting the conversation.")
        reset_chat()
        st.stop()

    # --- Stage-Specific Input Processing ---
    current_stage = st.session_state.stage

    if current_stage == "ask_industry":
        # --- FIX: Simplify greeting response ---
        if processed_prompt.lower() in COMMON_GREETINGS:
            # Just acknowledge, don't re-ask the question here.
            add_message("assistant", f"{processed_prompt.capitalize()} to you too! Let's get started.")
            # Stay in the same stage (ask_industry). The prompt display logic
            # will handle showing the industry question after the rerun.
            rerun_needed = True
        elif processed_prompt:
            st.session_state.icp_details['industry'] = processed_prompt
            st.session_state.stage = "ask_title"
            rerun_needed = True # Rerun needed to move to next prompt
        else:
            add_message("assistant", "Industry cannot be empty. Please tell me the target industry.")
            rerun_needed = True # Rerun needed to show error

    # ... (rest of the elif blocks remain the same) ...
    elif current_stage == "ask_title":
       # ...
       pass # Placeholder for brevity
    elif current_stage == "ask_company_size":
       # ...
       pass
    elif current_stage == "ask_source":
       # ...
       pass
    elif current_stage == "confirm":
       # ...
       pass


    # Only rerun if needed
    if rerun_needed:
        st.rerun()
