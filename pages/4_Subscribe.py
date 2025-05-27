# pages/4_Subscribe.py
import streamlit as st
import os
import time # For potential delays or UX niceties
# requests and json might not be strictly needed here if all API calls are handled by the JS component,
# but good to have if you plan to add direct Python API calls from this page later (e.g., to fetch current sub status).
# import requests 
# import json

# --- Configuration ---
# Use st.secrets for sensitive or environment-specific values in deployed apps
# For local development, os.getenv can fall back to defaults.
# Ensure these secrets/env vars are set correctly in your Streamlit environment (e.g., .streamlit/secrets.toml or Render env vars)
FASTAPI_BACKEND_URL = st.secrets.get("FASTAPI_BACKEND_URL", os.getenv("BACKEND_API_URL", "http://localhost:8000"))
STRIPE_PUBLISHABLE_KEY = st.secrets.get("STRIPE_PUBLISHABLE_KEY", os.getenv("STRIPE_PUBLISHABLE_KEY", "pk_test_YOUR_FALLBACK_PUBLISHABLE_KEY")) # Ensure this is your actual TEST publishable key

# Define your plans and their Stripe Price IDs (for the BASE recurring fee)
PLANS_CONFIG = {
    "launchpad": {
        "name": "Launchpad Plan",
        "display_price": "$199/mo",
        "base_fee_stripe_price_id": "price_YOUR_LAUNCHPAD_MONTHLY_BASE_PRICE_ID", # <<<--- REPLACE THIS
        "description": "Ideal for getting started. Includes 500 leads, 2 ICPs, 3 campaigns.",
        "success_fee_display": "+ $50 / meeting-intent reply",
        "features": ["500 Leads/mo", "2 ICP Definitions", "3 Active Campaigns", "AI Campaign Generation", "Basic Analytics"]
    },
    "scale": {
        "name": "Scale Plan",
        "display_price": "$499/mo",
        "base_fee_stripe_price_id": "price_YOUR_SCALE_MONTHLY_BASE_PRICE_ID", # <<<--- REPLACE THIS
        "description": "For growing teams. Includes 1,500 leads, CRM sync, 5 campaigns.",
        "success_fee_display": "+ $35 / meeting-intent reply",
        "features": ["1,500 Leads/mo", "5 ICP Definitions", "5 Active Campaigns", "AI Campaign Generation", "Advanced Analytics", "CRM Sync (Beta)"]
    },
    "enterprise": { # Example for Enterprise (display only, no direct Stripe component)
        "name": "Enterprise Plan",
        "display_price": "Custom Pricing",
        "base_fee_stripe_price_id": None, # Not directly subscribable via this component
        "description": "Tailored solutions, dedicated support, and custom integrations for large teams.",
        "success_fee_display": "Success fee based on % of qualified pipeline (negotiated).",
        "features": ["All Scale Features", "Custom Limits", "Bespoke Integrations", "Dedicated Support"],
        "cta_button_label": "Contact Sales",
        "cta_action": "contact_sales" # Special action to handle differently
    }
}

def display_subscription_page():
    st.title("🚀 Subscribe to SalesTroopz")
    st.markdown("Choose the plan that best fits your sales outreach needs.")
    st.markdown("---")

    # --- Authentication Check ---
    if 'auth_token' not in st.session_state or not st.session_state.auth_token:
        st.warning("Please log in or sign up to subscribe to a plan.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Go to Login", key="sub_page_login_btn", use_container_width=True):
                st.switch_page("pages/1_Login.py")
        with col2:
            if st.button("Go to Sign Up", key="sub_page_signup_btn", use_container_width=True):
                st.switch_page("pages/2_Signup.py")
        return # Stop further execution if not logged in

    auth_token = st.session_state.auth_token

    # TODO (Future): Fetch current subscription status from backend and display it.
    # current_sub = get_current_subscription_api(auth_token)
    # if current_sub and current_sub.get("status") == "active":
    #     st.success(f"You are currently subscribed to: {current_sub.get('plan_name')}")
    #     # Add link to Stripe Customer Portal or manage subscription page
    #     return # Don't show plan selection if already active

    # --- Plan Selection ---
    st.subheader("Select Your Plan:")
    
    plan_keys = list(PLANS_CONFIG.keys())
    cols = st.columns(len(plan_keys))

    for i, plan_key in enumerate(plan_keys):
        with cols[i]:
            plan = PLANS_CONFIG[plan_key]
            with st.container(border=True): # Use border=True for a card-like effect
                st.header(plan["name"]) # Use header for plan names
                st.markdown(f"## **{plan['display_price']}**")
                st.caption(plan["success_fee_display"])
                st.markdown(f"*{plan['description']}*")
                
                st.markdown("**Key Features:**")
                for feature in plan["features"]:
                    st.markdown(f"- {feature}")
                
                st.markdown("---") # Little separator before button
                
                if plan.get("base_fee_stripe_price_id"): # For Launchpad and Scale
                    if st.button(f"Choose {plan['name']}", key=f"choose_plan_{plan_key}", use_container_width=True, type="primary"):
                        st.session_state.selected_price_id_for_checkout = plan["base_fee_stripe_price_id"]
                        st.session_state.selected_plan_name_for_checkout = plan["name"]
                        if "stripe_checkout_result" in st.session_state: # Clear previous results
                            del st.session_state["stripe_checkout_result"]
                        st.rerun()
                elif plan.get("cta_action") == "contact_sales": # For Enterprise
                    st.link_button(plan["cta_button_label"], "mailto:your_sales_email@example.com?subject=Enterprise Plan Inquiry", use_container_width=True)


    st.markdown("---")

    # --- Payment Form Section (Appears after a plan is selected) ---
    if st.session_state.get("selected_price_id_for_checkout"):
        price_id_to_use = st.session_state.selected_price_id_for_checkout
        plan_name_to_use = st.session_state.selected_plan_name_for_checkout

        st.header(f"💳 Payment for: {plan_name_to_use}") # Use header
        st.caption("Please enter your card details below. Securely processed by Stripe.")

        # --- Display Checkout Result ---
        component_value = st.session_state.get("stripe_checkout_result")
        if component_value:
            if component_value.get("success"):
                st.success(f"Subscription to {plan_name_to_use} successful! Status: {component_value.get('status', 'N/A')}")
                st.balloons()
                if component_value.get("subscription_id"):
                     st.write(f"Your Stripe Subscription ID: {component_value.get('subscription_id')}")
                
                st.session_state.subscription_status = component_value.get('status', 'active') # Update global status
                # Clear selections after success
                del st.session_state["selected_price_id_for_checkout"]
                del st.session_state["stripe_checkout_result"]

                if st.button("🎉 Go to My Dashboard", key="post_sub_dashboard_btn", type="primary"):
                    st.switch_page("pages/0_App.py")
                st.stop() # Stop rendering the payment form further on this run

            elif component_value.get("error"):
                st.error(f"Subscription failed: {component_value.get('error')}")
                if st.button("Try Payment Again?", key="retry_payment_btn"):
                    del st.session_state["stripe_checkout_result"] # Clear error to allow re-render of component
                    st.rerun()
            elif component_value.get("requires_action"):
                st.warning("Your bank requires additional confirmation. Please follow any prompts from Stripe (e.g., 3D Secure). If successful, your subscription will activate.")
            
            if not component_value.get("success"): # If there was an error or requires_action
                if st.button("Change Plan / Cancel", key="cancel_payment_btn"):
                    del st.session_state["selected_price_id_for_checkout"]
                    if "stripe_checkout_result" in st.session_state:
                        del st.session_state["stripe_checkout_result"]
                    st.rerun()

        # Only render the Stripe component if no result is being displayed OR if user clicked retry
        if not component_value or (component_value and component_value.get("error")): # Re-show if there's an error
            try:
                with open("components/stripe_checkout.html", "r") as f:
                    html_template = f.read()
                
                # Ensure all VAR_ placeholders are correctly replaced
                component_html = html_template.replace("VAR_STRIPE_PUBLISHABLE_KEY", STRIPE_PUBLISHABLE_KEY)\
                                              .replace("VAR_FASTAPI_BACKEND_URL", FASTAPI_BACKEND_URL)\
                                              .replace("VAR_AUTH_TOKEN", auth_token)\
                                              .replace("VAR_PRICE_ID", price_id_to_use) 
                
                returned_value = st.components.v1.html(component_html, height=450, scrolling=False, key="stripe_checkout_form_active") # Unique key
                
                if returned_value:
                    st.session_state.stripe_checkout_result = returned_value
                    st.rerun()

            except FileNotFoundError:
                st.error("Critical Error: Stripe payment component (stripe_checkout.html) not found. Please ensure 'components/stripe_checkout.html' exists.")
            except Exception as e:
                st.error(f"An error occurred loading the payment component: {e}")
    else:
        st.info("Select a plan above to proceed to payment.")

# --- Call the main function for this page ---
if __name__ == "__main__":
    # Mock session state for direct testing of this page
    # This part is only for running `streamlit run pages/4_Subscribe.py` directly
    if 'auth_token' not in st.session_state:
        st.session_state.auth_token = "mock_jwt_token_for_subscribe_test" # Replace if needed for direct test
        st.session_state.user_email = "test@example.com"
    display_subscription_page()
else:
    # This is how Streamlit runs it as part of a multi-page app
    display_subscription_page()
