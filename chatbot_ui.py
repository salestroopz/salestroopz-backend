# chatbot_ui.py
import streamlit as st
import requests
import json

# --- Configuration ---
# Make sure this matches the URL where your FastAPI backend is running
# Use the public Render URL if deploying Streamlit separately
# Use http://127.0.0.1:8000 if running both locally and FastAPI is on port 8000
BACKEND_URL = "https://salestroopz-backendpython-m-uvicorn-app.onrender.com" # Replace with your actual Render URL or local URL
INITIATE_ENDPOINT = f"{BACKEND_URL}/api/v1/workflow/initiate"

# --- Helper Function to call Backend ---
def initiate_backend_workflow(icp_data, source_type, source_details=None):
    """Sends the collected data to the FastAPI backend."""
    payload = {
        "icp": icp_data,
        "source_type": source_type,
        "source_details": source_details or {} # Include details if available
    }
    try:
        headers = {'Content-Type': 'application/json'}
        response = requests.post(INITIATE_ENDPOINT, headers=headers, data=json.dumps(payload))
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error contacting backend: {e}")
        return None
    except json.JSONDecodeError:
        st.error(f"Backend returned non-JSON response: {response.text}")
        return None


# --- Initialize Session State ---
# Keeps track of conversation across reruns
if "messages" not in st.session_state:
    st.session_state.messages = []
if "stage" not in st.session_state:
    st.session_state.stage = "greeting" # Start the conversation flow
if "icp_details" not in st.session_state:
    st.session_state.icp_details = {}
if "lead_source" not in st.session_state:
    st.session_state.lead_source = None
if "processing_complete" not in st.session_state:
    st.session_state.processing_complete = False


# --- Display Chat History ---
st.title("SalesTroopz Agent Setup")
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- Conversation Logic ---

# Function to add message and update state
def add_message(role, content):
    st.session_state.messages.append({"role": role, "content": content})

# Greeting Stage
if st.session_state.stage == "greeting":
    add_message("assistant", "Hi! I'm here to help you set up your SalesTroopz campaign. Let's start by defining your Ideal Customer Profile (ICP). What industry are you targeting?")
    st.session_state.stage = "ask_industry"
    st.rerun() # Rerun to display the greeting immediately

# Ask for Industry Stage
elif st.session_state.stage == "ask_industry":
    # Message was already displayed in the previous step or rerun
    pass # Wait for user input via st.chat_input

# Ask for Title Stage
elif st.session_state.stage == "ask_title":
    if not any(msg['role'] == 'assistant' and 'job title' in msg['content'] for msg in st.session_state.messages[-2:]): # Avoid duplicate prompts on reruns
         add_message("assistant", "Got it. Now, what specific job title(s) are you looking for within that industry?")
         st.rerun()

# Ask for Company Size Stage
elif st.session_state.stage == "ask_company_size":
     if not any(msg['role'] == 'assistant' and 'company size' in msg['content'] for msg in st.session_state.messages[-2:]):
        add_message("assistant", "Okay. What company size are you targeting? (e.g., '1-10', '11-50', '51-200', '201-500', '500+')")
        st.rerun()

# Ask for Lead Source Stage
elif st.session_state.stage == "ask_source":
    if not any(msg['role'] == 'assistant' and 'source of leads' in msg['content'] for msg in st.session_state.messages[-2:]):
        add_message("assistant", "Great! Now, where should I get the leads from? Please choose one: 'File Upload', 'Apollo', 'CRM', or 'Manual Entry'.")
        st.rerun()

# Confirmation Stage
elif st.session_state.stage == "confirm":
    if not any(msg['role'] == 'assistant' and 'Please confirm' in msg['content'] for msg in st.session_state.messages[-2:]):
        confirmation_message = f"""
Okay, let's confirm:
- **Industry:** {st.session_state.icp_details.get('industry', 'Not set')}
- **Title(s):** {st.session_state.icp_details.get('title', 'Not set')}
- **Company Size:** {st.session_state.icp_details.get('company_size', 'Not set')}
- **Lead Source:** {st.session_state.lead_source}

Is this correct? (Please type 'Yes' to proceed)
"""
        add_message("assistant", confirmation_message)
        st.rerun()

# Processing Complete Stage
elif st.session_state.stage == "done":
    if not st.session_state.processing_complete:
         add_message("assistant", "Okay, I've sent the request to the backend to start the process based on your criteria.")
         st.session_state.processing_complete = True # Prevent reprocessing
         st.rerun()


# --- Handle User Input ---
if prompt := st.chat_input("Your response...", disabled=st.session_state.processing_complete):
    add_message("user", prompt) # Display user message

    # Process based on current stage
    if st.session_state.stage == "ask_industry":
        st.session_state.icp_details['industry'] = prompt
        st.session_state.stage = "ask_title"
        st.rerun() # Move to next stage and trigger assistant message

    elif st.session_state.stage == "ask_title":
        st.session_state.icp_details['title'] = prompt
        st.session_state.stage = "ask_company_size"
        st.rerun()

    elif st.session_state.stage == "ask_company_size":
        st.session_state.icp_details['company_size'] = prompt
        st.session_state.stage = "ask_source"
        st.rerun()

    elif st.session_state.stage == "ask_source":
        # Basic validation for source
        allowed_sources = ["file upload", "apollo", "crm", "manual entry"]
        if prompt.lower() in allowed_sources:
            st.session_state.lead_source = prompt.lower().replace(" ", "_") # Standardize source name
            st.session_state.stage = "confirm"
        else:
            add_message("assistant", "Sorry, that's not a valid source. Please choose from 'File Upload', 'Apollo', 'CRM', or 'Manual Entry'.")
        st.rerun()

    elif st.session_state.stage == "confirm":
        if prompt.strip().lower() == 'yes':
            st.session_state.stage = "done"
            # Call the backend API
            with st.spinner("Sending request to backend..."):
                 backend_response = initiate_backend_workflow(
                     st.session_state.icp_details,
                     st.session_state.lead_source
                 )
            if backend_response:
                 add_message("assistant", f"Backend acknowledged! Response: ```{json.dumps(backend_response, indent=2)}```")
                 add_message("assistant", "Further processing (like fetching leads and running sequences) will happen based on this. Check backend logs or status later.")
            # No else needed, error handled in initiate_backend_workflow

        else:
            # If user doesn't confirm, reset to ask again (or ask what to change)
            add_message("assistant", "Okay, let's restart. What industry are you targeting?")
            # Reset state partially or fully
            st.session_state.stage = "ask_industry"
            st.session_state.icp_details = {}
            st.session_state.lead_source = None
        st.rerun()

    elif st.session_state.stage == "done":
        # Conversation is over, maybe offer a reset button later
        add_message("assistant", "The setup process is complete based on the information provided.")
        st.rerun()
