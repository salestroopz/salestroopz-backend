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
ALLOWED_SOURCES_DISPLAY = ["File Upload", "Apollo", "CRM", "Manual Entry"]
COMMON_GREETINGS = ["hi", "hello", "hey", "yo", "ok", "okay", "thanks", "thank you", "hi!", "hello!"]

# --- Helper Function to call Backend ---
# ... (Keep as is) ...
def initiate_backend_workflow(icp_data, source_type, source_details=None):
    # ...
    pass

# --- Function to add message (simpler, no duplicate check for now) ---
def add_message(role, content):
    """Adds a message to the chat history."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    st.session_state.messages.append({"role": role, "content": content})


# --- Function to reset chat state ---
def reset_chat():
    """Resets the chat state and displays initial messages."""
    st.session_state.messages = []
    st.session_state.stage = "greeting" # Temporarily set to greeting
    st.session_state.icp_details = {}
    st.session_state.lead_source = None
    st.session_state.processing_initiated = False

    add_message("assistant", "Hi! I'm here to help you set up your SalesTroopz campaign. Let's define your Ideal Customer Profile (ICP). (You can type 'restart' anytime to start over).")
    st.session_state.stage = "ask_industry" # Set stage for the first question
    # Explicitly add the first prompt message right after reset
    add_message("assistant", assistant_prompts[st.session_state.stage])
    # No rerun here needed, let the script run through initially

# --- Define Prompts Dictionary (needs to be defined before reset_chat is potentially called) ---
assistant_prompts = {
    "ask_industry": "What industry are you targeting?",
    "ask_title": "Got it. Now, what specific job title(s) are you looking for?",
    "ask_company_size": "Okay. What company size are you targeting? (e.g., '1-10', '11-50', '51-200', '201-500', '500+')",
    "ask_source": f"Great! Now, where should I get the leads from? Please choose one: {', '.join(ALLOWED_SOURCES_DISPLAY)}.",
    "confirm": lambda state: f"""
Okay, let's confirm:
- **Industry:** {state.get('icp_details', {}).get('industry', '*(Not set)*')}
- **Title(s):** {state.get('icp_details', {}).get('title', '*(Not set)*')}
- **Company Size:** {state.get('icp_details', {}).get('company_size', '*(Not set)*')}
- **Lead Source:** {(lead_source := state.get('lead_source')) and lead_source.replace('_',' ').title() or '*(Not set)*'}

Is this correct? (Please type **Yes** to proceed, or **No** to restart)
""", # Made confirm prompt a function to access state dynamically
    "done": "Setup complete. I've sent the request to the backend. Processing will happen in the background. You can close this window or type 'restart' to begin again."
}

# --- Initialize Session State ---
if "messages" not in st.session_state:
    reset_chat() # Initialize state properly

# --- Display Chat History ---
st.title("SalesTroopz Agent Setup")
for message in st.session_state.get("messages", []):
    with st.chat_message(message["role"]):
        st.markdown(message["content"].replace("\n", "  \n"))

# --- REMOVE OLD Prompt Display Logic ---
# (The logic block that started with "Display Current Prompt Logic" is removed)


# --- Handle User Input ---
if prompt := st.chat_input("Your response...", disabled=st.session_state.get("processing_initiated", False), key="user_input"):
    add_message("user", prompt)
    processed_prompt = prompt.strip()
    next_stage = st.session_state.stage # Start by assuming stage doesn't change

    # --- Global Restart Check ---
    if processed_prompt.lower() in ["restart", "start over", "reset"]:
        add_message("assistant", "Okay, restarting the conversation.")
        reset_chat()
        st.rerun() # Rerun immediately after reset
        st.stop()

    # --- Stage-Specific Input Processing ---
    current_stage = st.session_state.stage

    # --- Process Input and Determine NEXT Stage ---
    if current_stage == "ask_industry":
        if processed_prompt.lower() in COMMON_GREETINGS:
            add_message("assistant", f"{processed_prompt.capitalize()} to you too! Let's get started.")
            next_stage = "ask_industry" # Stay on this stage, prompt will be re-added below
        elif processed_prompt:
            st.session_state.icp_details['industry'] = processed_prompt
            next_stage = "ask_title"
        else:
            add_message("assistant", "Industry cannot be empty. Please tell me the target industry.")
            next_stage = "ask_industry" # Stay on this stage

    elif current_stage == "ask_title":
        if processed_prompt:
            st.session_state.icp_details['title'] = processed_prompt
            next_stage = "ask_company_size"
        else:
            add_message("assistant", "Title cannot be empty. Please provide the target job title(s).")
            next_stage = "ask_title"

    elif current_stage == "ask_company_size":
        if processed_prompt and (re.search(r'\d', processed_prompt) or any(s in processed_prompt.lower() for s in ['small', 'medium', 'large', 'enterprise', '+', '-'])):
            st.session_state.icp_details['company_size'] = processed_prompt
            next_stage = "ask_source"
        elif not processed_prompt:
             add_message("assistant", "Company size cannot be empty. Please provide a target size range (e.g., '11-50', '500+').")
             next_stage = "ask_company_size"
        else:
             add_message("assistant", f"'{prompt}' doesn't look like a standard company size. Please provide a range like '11-50', '500+', or describe it (e.g., 'Large Enterprise'). Let's try that again.")
             next_stage = "ask_company_size"

    elif current_stage == "ask_source":
        source_input = processed_prompt.lower().replace(" ", "_")
        if source_input in ALLOWED_SOURCES:
            st.session_state.lead_source = source_input
            next_stage = "confirm"
        else:
            add_message("assistant", f"Sorry, '{prompt}' is not a valid source. Please choose only from: {', '.join(ALLOWED_SOURCES_DISPLAY)}.")
            next_stage = "ask_source"

    elif current_stage == "confirm":
        if processed_prompt.lower() == 'yes':
            next_stage = "done" # Move to final stage *before* backend call
            with st.spinner("Sending request to backend..."):
                 backend_response = initiate_backend_workflow(
                     st.session_state.icp_details,
                     st.session_state.lead_source
                 )
            if backend_response:
                 add_message("assistant", f"Backend acknowledged! Response details: ```{json.dumps(backend_response, indent=2)}```")
                 st.session_state.processing_initiated = True # Disable input now
            # Error messages are handled by initiate_backend_workflow
        elif processed_prompt.lower() == 'no':
             add_message("assistant", "Okay, discarding current setup. Let's restart.")
             reset_chat()
             st.rerun() # Rerun immediately
             st.stop()
        else:
            add_message("assistant", "Please confirm with 'Yes' or 'No'.")
            next_stage = "confirm" # Stay in confirm stage

    # --- Update Stage and Add Next Prompt ---
    st.session_state.stage = next_stage # Update the stage definitively

    # Add the prompt for the *new* stage, unless we are done
    if next_stage in assistant_prompts and next_stage != "done":
        prompt_content = assistant_prompts[next_stage]
        # Handle the confirmation prompt needing state
        if callable(prompt_content):
             add_message("assistant", prompt_content(st.session_state))
        else:
             add_message("assistant", prompt_content)
    elif next_stage == "done" and st.session_state.processing_initiated: # Only add "done" message if backend call was successful
        add_message("assistant", assistant_prompts["done"])


    # --- Rerun to display updates ---
    st.rerun()
