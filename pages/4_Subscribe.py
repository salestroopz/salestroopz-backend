# pages/4_Subscribe.py
import streamlit as st
import os
import time
import requests # For direct API calls if you ever need them from Python (though JS component handles payment)
import json

# --- Configuration ---
# It's good practice to get this from st.secrets or a shared config module
FASTAPI_BACKEND_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "pk_test_YOUR_STRIPE_TEST_PUBLISHABLE_KEY_HERE") # Replace default

# Define your plans and their Stripe Price IDs (for the BASE recurring fee)
# The metered item for success fee is added on the backend when the base subscription is created.
PLANS = {
    "Launchpad": {
        "name": "Launchpad Plan",
        "price_display": "$199/mo",
        "base_price_id": "price_YOUR_LAUNCHPAD_MONTHLY_BASE_PRICE_ID", # Replace!
        "description": "Ideal for getting started. Includes 500 leads, 2 ICPs, 3 campaigns.",
        "success_fee_info": "+ $50 per qualified meeting-intent reply.",
        "features": [
            "AI-Powered Campaign Generation",
            "Intelligent Reply Classification",
            "Basic Performance Analytics",
            "500 Leads/Month",
            "2 ICP Definitions",
            "3 Active Campaigns"
        ]
    },
    "Scale": {
        "name": "Scale Plan",
        "price_display": "$499/mo",
        "base_price_id": "price_YOUR_SCALE_MONTHLY_BASE_PRICE_ID", # Replace!
        "description": "For growing teams needing more volume and CRM integration.",
        "success_fee_info": "+ $35 per qualified meeting-intent reply.",
        "features": [
            "All Launchpad Features",
            "CRM Synchronization",
            "Advanced Performance Analytics",
            "1,500 Leads/Month",
            "5 ICP Definitions",
            "10 Active Campaigns"
        ]
    },
    "Enterprise": {
        "name": "Enterprise Plan",
        "price_display": "Custom Pricing",
        "base_price_id": None, # Handled manually
        "description": "Tailored solutions, dedicated support, and custom integrations for large teams.",
        "success_fee_info": "Success fee based on % of qualified pipeline (negotiated).",
        "features": [
            "All Scale Features",
            "Custom Lead Limits & Campaign Caps",
            "Bespoke Integrations",
            "Dedicated Account Manager",
            "Premium Support"
        ],
        "cta_label": "Contact Us for Enterprise",
        "cta_link": "mailto:sales@salestroopz.com" # Or your contact page
    }
}

def display_subscription_page():
    st.title("🚀 Subscribe to SalesTroopz")

    if not st.session_state.get("auth_token"):
        st.warning("Please log in or sign up to subscribe to a plan.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Login", use_container_width=True):
                st.switch_page("pages/1_Login.py")
        with col2:
            if st.button("Sign Up", use_container_width=True):
                st.switch_page("pages/2_Signup.py")
        st.stop() # Stop further execution of this page if not logged in

    auth_token = st.session_state.auth_token
    user_email = st.session_state.get("user_email", "User")

    # --- Display Current Subscription Status (Optional but good) ---
    # You would fetch this from yourExcellent! Login and signup working well is a huge step forward. Now, let's tackle the subscription page (`pages/4_Subscribe.py`) where users can select a plan and go through the Stripe payment backend if you have an endpoint for it
    # For now, we can use a placeholder or update it after subscription
    current_sub_status = st.session_state.get("subscription_status", "Not Subscribed")
    if current_sub_status == "active":
        st.success(f"You are currently subscribed to a plan! ({st.session_state.get('subscribed_plan_name', 'Active Plan')})")
        # TODO: Add link to manage subscription (e.g., Stripe Customer Portal)
        # if st.button("Manage Subscription"):
            # Call backend to get Stripe Portal link, then st.link_button or st.markdown flow.


# **Assumptions:**

# 1.  **FastAPI Backend Ready:** Your `/api/v1/subscriptions/create-subscription` endpoint is implemented, tested (e.g., with Postman), link
        return # Don't show plan selection if already active (or show upgrade options)
    elif current_sub_status != "Not Subscribed": # e.g., past_due, canceled
        st.warning(f"Your current subscription status: {current_sub_status.replace('_', ' ').capitalize()}")


    st.markdown("Choose the plan that's right for your sales team's needs and start automating your outreach today!")
    st.markdown("---")

    # --- Plan Selection UI ---
    # Create columns for plans
    plan_keys = list(PLANS.keys())
    cols = st.columns(len(plan_keys))

    selected_price_id_for_checkout = None
    selected_plan_name_for_checkout = None

    for i, plan and working correctly (creates Stripe Customer, Stripe Subscription, adds metered item, saves to your DB, handles SCA).
# 2.  **Stripe Setup:**
    *   You have your Stripe **Publishable Key** (Test mode).
    *   You have **Price IDs** (Test mode) for your "Launchpad" and "Scale" base plans (e.g., `price_LMNmonthlyBase`, `price_XYZmonthlyBase`).
    *   You have **Price IDs** for your metered "meeting-intent reply" fees for each plan (e.g., `price_LMNmeteredReply`, `price_XYZmeteredReply`).
#3.  **Streamlit Authentication:** `st.session_state.auth_token` is populated after a user logs in.
# 4.  **File Structure:** You have:
    *   `pages/4_Subscribe.py`
    *   `components/stripe_checkout.html`

---

**Step 1: Refine `pages/4_Subscribe.py`**

This Streamlit page will:
*   Ensure the user is logged in.
*   Display your pricing plans.
*   Allow the user to select a plan.
*   Once a plan is selected, render the `stripe_checkout.html` component, passing the necessary data to it (auth token, selected base plan's Price ID, backend URL, Stripe publishable key).
*   Receive and display the outcome from the Stripe checkout component.

```python
# pages/4_Subscribe.py
_key in enumerate(plan_keys):
        with cols[i]:
            plan = PLANS[plan_key]
            with st.container(border=True):
                st.subheader(plan["name"])
                st.markdown(f"**{plan['price_display']}**")
                if plan.get("success_fee_info"):
                    st.caption(plan["success_fee_info"])
                st.markdown(plan["description"])
                with st.expander("View Features"):
                    for feature in plan["features"]:
                        st.markdown(f"- {feature}")
                
                if plan["base_price_id"]: # For Launchpad and Scale
                    if st.button(f"Choose {plan['name']}", key=f"chooseimport streamlit as st
import os
import time # For potential delays or UX niceties

# --- Configuration ---
# Use st.secrets for sensitive or environment-specific values in deployed apps
# For local development, os.getenv can fall back to defaults.
FASTAPI_BACKEND_URL = st.secrets.get("FASTAPI_BACKEND_URL", os.getenv("BACKEND_API_URL", "http://localhost:8000"))
STRIPE_PUBLISHABLE_KEY = st.secrets.get("STRIPE_PUBLISHABLE_KEY", os.getenv("STRIPE_PUBLISHABLE_KEY", "pk_test_YOUR_FALLBACK_PUBLISHABLE_KEY"))

# Define your plans and their Stripe Price IDs (for the BASE recurring fee)
# The metered item Price IDs will be handled on the backend when the subscription is created.
PLANS_CONFIG = {
    "launchpad": { # Use a consistent key, e.g., lowercase plan name
        "name": "Launchpad Plan",
        "display_price": "$199/mo",
        "base_fee_stripe_price_id": "price_YOUR_LAUNCHPAD_MONTHLY_BASE_PRICE_ID", # Replace!
        "description": "Ideal for getting started. Includes 500 leads, 2 ICPs, 3 campaigns.",
        "success_fee_display": "+ $50 / meeting-intent reply",
        "features": ["500 Leads/mo", "2 ICP Definitions", "3 Active Campaigns", "AI Campaign Generation", "Basic Analytics"]
    },
    "scale": {
        "name": "Scale Plan",
        "display_price": "$499/mo",
        "base_fee_stripe_price_id": "price_YOUR_SCALE_MONTHLY_BASE_PRICE_ID", # Replace!
        "description": "For growing teams. Includes 1,500 leads, CRM sync, 5 campaigns.",
        "success_fee_display": "+ $35 / meeting-intent reply",
        "features": ["1,500 Leads/mo", "5 ICP Definitions", "5 Active Campaigns", "AI Campaign Generation", "Advanced Analytics", "CRM Sync (Beta)"]
    }
    # Add "Enterprise" here if you want to display it, with a "Contact Us" button
}

def display_subscription_page():
    st.title("🚀 Subscribe to SalesTroopz")
    st.markdown_{plan_key}", use_container_width=True, type="primary"):
                        st.session_state.selected_price_id = plan["base_price_id"]
                        st.session_state.selected_plan_name = plan["name"]
                        # We don't rerun here; the Stripe component will be displayed below
                        # based on this session state.
                elif plan.get("cta_link"): # For Enterprise
                    st.link_button(plan["cta_label"], plan["cta_link"], use_container_width=True)


    # --- Stripe Checkout Component Section ---
    if st.session_state.get("selected_price_id"):
        st.markdown("---")
        st.subheader(f"Complete Your Subscription: {st.session_state.selected_plan_name}")
        st.markdown("Please enter your payment details below. Securely processed by Stripe.")

        # Get the component value from the previous run (if any)
        component_result = st.session_state.get("stripe_checkout_result")

        if component_result:
            if component_result.get("success"):
                st.success(f"Subscription successful! Status: {component_result.get('status', 'N/A')}")
                st.balloons()
                if component_result.get("subscription_id"):
                     st.write(f"Your Subscription ID: {component_result.get('subscription_id')}")
                # Update session state to reflect active subscription
                st.session_state.subscription_status = "active" # Or the status from response
                st.session_state.subscribed_plan_name = st.session_state.selected_plan_name
                # Clear selection and result to avoid re-processing
                del st.session_state["selected_price_id"]
                del st.session_state["stripe_checkout_result"]
                if st.button("Go to Dashboard"):
                    st.switch_page("pages/0_App.py")
                st.stop() # Stop further rendering of payment form on this run
            elif component_result.get("error"):
                st.error(f"Subscription failed: {component_result.get('error')}")
            elif component_result.get("requires_action"):
                st.warning("Subscription requires further action.("Choose the plan that best fits your sales outreach needs.")
    st.markdown("---")

    # --- Authentication Check ---
    if 'auth_token' not in st.session_state or not st.session_state.auth_token:
        st.warning("Please log in to manage your subscription or choose a plan.")
        if st.button("Go to Login", key="sub_page_login_btn"):
            st.switch_page("pages/1_Login.py")
        return

    auth_token = st.session_state.auth_token

    # TODO: Check current subscription status from backend
    # For now, we'll assume they are choosing a new plan or upgrading.
    # current_sub_status = get_current_subscription_status_api(auth_token) # You'd need this API
    # if current_sub_status and current_sub_status.get("status") == "active":
    #     st.success(f"You are currently subscribed to the {current_sub_status.get('plan_name', 'current')} plan.")
    #     st.write("To change your plan or manage billing, please visit your account settings (link to Stripe Customer Portal).")
    #     # Add button for Stripe Customer Portal here
    #     return


    # --- Plan Selection ---
    st.subheader("Select Your Plan:")
    
    # Using columns for a nicer layout of plan cards
    plan_keys = list(PLANS_CONFIG.keys())
    cols = st.columns(len(plan_keys))

    selected_price_id_for_checkout = None

    for i, plan_key in enumerate(plan_keys):
        with cols[i]:
            plan = PLANS_CONFIG[plan_key]
            with st.container(border=True):
                st.subheader(plan["name"])
                st.markdown(f"**{plan['display_price']}**")
                st.caption(plan["success_fee_display"])
                st.markdown(f"*{plan['description']}*")
                with st.expander("View Features"):
                    for feature in plan["features"]:
                        st.markdown(f"- {feature}")
                
                if st.button(f"Choose {plan['name']}", key=f"choose_plan_{plan_key}", use_container_width=True, type="primary"):
                    st.session_state.selected_price_id_for_checkout = plan["base_fee_stripe_price_id"]
                    st.session_state.selected_plan_name_for_checkout = plan["name"]
                    # Clear previous checkout results when a new plan is chosen before payment attempt
                    if "stripe_checkout_result" in st.session_state:
                        del st.session_state["stripe_checkout_result"]
                    st.rerun() # Rerun to show the payment form for the selected plan

    st.markdown("---")

    # --- Payment Form Section (Appears after a plan is selected) ---
    if "selected_price_id_for_checkout" in st.session_state and st.session_state.selected_price_id_for_checkout:
        price_id_to_use = st.session_state.selected_price_id_for_checkout
        plan_name_to_use = st.session_state.selected_plan_name_for_checkout

        st.subheader(f"Payment for: {plan_name_to_use}")
        st.caption("Please enter your card details below. Securely processed by Stripe.")

        # --- Display Checkout Result ---
        component_value = st.session_state.get("stripe_checkout_result")
        if component_value:
            if component_value.get("success"):
                st.success(f"Subscription to {plan_name_to_use} successful! Status: {component_value.get('status', 'N/A')}")
                st.balloons()
                if component_value.get("subscription_id"):
                     st.write(f"Your Stripe Subscription ID: {component_value.get('subscription_id')}")
                # TODO: Update st.session_state.subscription_status with the new status
                # TODO: Potentially navigate to a dashboard or thank you page
                if st.button("Go to My Dashboard", key="post_sub_dashboard_btn"):
                    st.switch_page("pages/0_App.py")

            elif component_value.get("error"):
                st.error(f"Subscription failed: {component_value.get('error')}")
                # Allow user to try again by re-rendering the component or showing a retry button
                if st.button("Try Payment Again?", key="retry_payment_btn"):
                    if "stripe_checkout_result" in st.session_state: # Clear previous error
                        del st.session_state["stripe_checkout_result"]
                    st.rerun()

            elif component_value.get("requires_action"):
                st.warning("Your bank requires additional confirmation for this subscription. Please follow any prompts that appeared from Stripe (e.g., 3D Secure). If successful, your subscription will activate.")
            
            # Offer a way to change plan if payment failed or they want to reconsider
            if not component_value.get("success"):
                if st.button("Change Plan / Cancel Payment", key="cancel_payment_btn"):
                    del st.session_state["selected_price_id_for_checkout"]
                    if "stripe_checkout_result" in st.session_state:
                        del st.session_state["stripe_checkout_result"]
                    st.rerun()


        # --- Load and Render Stripe Checkout Component HTML ---
        # Only render if we don't have a fresh success/error message to display
        # or if the user explicitly wants to retry/change.
        if not component_value or (component_value and component_value.get("error") and "retry_payment_btn_clicked_state" in st.session_state):
            # A bit complex state management here for retry, might need refinement.
            # For simplicity, just always show the component if a plan is selected and no definitive success.
            if "retry_payment_btn_clicked_state" in st.session_state:
                del st.session_state["retry_payment_btn_clicked_state"]


            try:
                # Ensure this path is correct from the root of where streamlit runs
                with open("components/stripe_checkout.html", "r") as f:
                    html_template = f.read()
                
                component_html = html_template.replace("VAR_STRIPE_PUBLISHABLE_KEY", STRIPE_PUBLISHABLE_KEY)\
                                              .replace("VAR_FASTAPI_BACKEND_URL", FASTAPI_BACKEND_URL)\
 Please follow the prompts from Stripe if any appear (e.g., for 3D Secure).")
            
            # Option to clear result if user wants to try again without full page reload
            if "stripe_checkout_result" in st.session_state and st.button("Try again with different card/details?", key="clear_stripe_result"):
                del st.session_state["stripe_checkout_result"]
                st.rerun()

        # Load and display the Stripe HTML/JS component
        try:
            # Make sure the path to stripe_checkout.html is correct from the perspective of where
            # `streamlit run` is executed (usually the project root).
            with open("components/stripe_checkout.html", "r") as f:
                html_template = f.read()
            
            component_html = html_template.replace("VAR_STRIPE_PUBLISHABLE_KEY", STRIPE_PUBLISHABLE_KEY)\
                                          .replace("VAR_FASTAPI_BACKEND_URL", FASTAPI_BACKEND_URL)\
                                          .replace("VAR_AUTH_TOKEN", auth_token)\
                                          .replace("VAR_PRICE_ID", st.session_state.selected_price_id) # Use selected
            
            # key="stripe_checkout_result" allows JS to send data back
            # This component will use the VAR_PRICE_ID set above.
            # If the user clicks a different plan, this page will rerun,
            # st.session_state.selected_price_id will update, and the component
            # will re-render with the new price_id.
            returned_value = st.components.v1.html(component_html, height=450, scrolling=False, key="stripe_checkout_form")
            
            if returned_value: # This is how Streamlit.setComponentValue is received in Python
                st.session_state.stripe_checkout_result = returned_value
                # Rerun immediately to process the result at the top of this section
                # This also helps in clearing the component or showing success/error message cleanly
                st.rerun()

        except FileNotFoundError:
            st.error("Critical Error: Stripe payment component (stripe_checkout.html) not found.")
        except Exception as e:
            st.error(f"An error occurred loading the payment component: {e}")
    else:
        st.info("Select a plan above to proceed to payment.")

# --- Ensure this function is called to render the page ---
if __name__ == "__main__": # Allows testing this page directly if needed
    # Mock session state for direct testing of this page
    if 'auth_token' not in st.session_state:
        st.session_state.auth_token = "your_test_jwt_for_subscribe_page_direct_run" # Replace for actual testing
        st.session_state.user_email = "test_user@example.com"
    display_subscription_page()
else:
    # This is how it will run when navigated to via Streamlit's multi-page app mechanism
    display_subscription_page()
