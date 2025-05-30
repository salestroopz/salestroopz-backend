# pages/4_Subscribe.py
import streamlit as st
import os
import time
from typing import Optional, Dict, Any # Ensure Dict and Any are imported from typing

# --- Configuration (ensure these are correctly loaded from environment on Render) ---
FASTAPI_BACKEND_URL = os.getenv("BACKEND_API_URL")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")

if not FASTAPI_BACKEND_URL:
    st.error("FATAL ERROR: BACKEND_API_URL environment variable is not set.", icon="🚨")
    st.stop()
if not STRIPE_PUBLISHABLE_KEY:
    st.error("FATAL ERROR: STRIPE_PUBLISHABLE_KEY environment variable is not set.", icon="🚨")
    st.stop()

print(f"INFO (4_Subscribe.py): FASTAPI_BACKEND_URL set to: {FASTAPI_BACKEND_URL}")
print(f"INFO (4_Subscribe.py): STRIPE_PUBLISHABLE_KEY (prefix): {STRIPE_PUBLISHABLE_KEY[:15] if STRIPE_PUBLISHABLE_KEY else 'None'}...")

# --- PLANS_CONFIG (ensure Price IDs are correct) ---
PLANS_CONFIG = {
    "launchpad": {
        "name": "Launchpad Plan", "display_price": "$199/mo",
        "base_fee_stripe_price_id": "price_YOUR_LAUNCHPAD_ID", # REPLACE!
        "description": "Ideal for getting started.", "success_fee_display": "+ $50 / reply",
        "features": ["500 Leads/mo", "2 ICPs", "3 Campaigns"]
    },
    "scale": {
        "name": "Scale Plan", "display_price": "$499/mo",
        "base_fee_stripe_price_id": "price_YOUR_SCALE_ID", # REPLACE!
        "description": "For growing teams.", "success_fee_display": "+ $35 / reply",
        "features": ["1,500 Leads/mo", "5 ICPs", "CRM Sync"]
    },
    "enterprise": {
        "name": "Enterprise Plan", "display_price": "Custom", "base_fee_stripe_price_id": None,
        "description": "Tailored solutions for large teams.", "success_fee_display": "Negotiated",
        "features": ["All Scale Features", "Custom Limits"], "cta_button_label": "Contact Sales",
        "cta_action": "contact_sales"
    }
}

def display_subscription_page():
    st.title("🚀 Subscribe to SalesTroopz")
    st.markdown("Choose the plan that best fits your sales outreach needs.")
    st.markdown("---")

    if not st.session_state.get("auth_token"):
        st.warning("Please log in or sign up to subscribe.")
        # ... login/signup buttons ...
        return
    auth_token = st.session_state.auth_token

    # ... Plan selection logic (displaying plan cards) ...
    # (This part seemed okay, ensure keys for buttons are unique)
    st.subheader("Select Your Plan:")
    plan_keys = list(PLANS_CONFIG.keys())
    cols = st.columns(len(plan_keys))

    for i, plan_key in enumerate(plan_keys):
        with cols[i]:
            plan = PLANS_CONFIG[plan_key]
            with st.container(border=True):
                st.header(plan["name"])
                st.markdown(f"## **{plan['display_price']}**")
                st.caption(plan.get("success_fee_display",""))
                st.markdown(f"*{plan['description']}*")
                with st.expander("View Features"):
                    for feature in plan["features"]:
                        st.markdown(f"- {feature}")
                st.markdown("---")
                if plan.get("base_fee_stripe_price_id"):
                    if st.button(f"Choose {plan['name']}", key=f"choose_plan_{plan_key}", use_container_width=True, type="primary"):
                        st.session_state.selected_price_id_for_checkout = plan["base_fee_stripe_price_id"]
                        st.session_state.selected_plan_name_for_checkout = plan["name"]
                        if "stripe_checkout_result" in st.session_state:
                            del st.session_state["stripe_checkout_result"]
                        st.rerun()
                elif plan.get("cta_action") == "contact_sales":
                    st.link_button(plan["cta_button_label"], "mailto:sales@example.com?subject=Enterprise Plan Inquiry", use_container_width=True) # Replace email
    st.markdown("---")


    # --- Payment Form Section ---
    if st.session_state.get("selected_price_id_for_checkout"):
        price_id_to_use = st.session_state.selected_price_id_for_checkout
        plan_name_to_use = st.session_state.selected_plan_name_for_checkout
        st.header(f"💳 Payment for: {plan_name_to_use}")
        st.caption("Please enter your card details below. Securely processed by Stripe.")

        component_value: Optional[Dict[str, Any]] = st.session_state.get("stripe_checkout_result")
        show_payment_form = True # Default to showing the form

        if component_value is not None: # Only process if there's a result from the component
            if not isinstance(component_value, dict):
                st.error("Internal error: Payment component returned unexpected data type.")
                # Potentially clear component_value here or handle as a severe error
                del st.session_state["stripe_checkout_result"] # Clear bad data
                show_payment_form = True # Allow retry
            else:
                # Now we know component_value is a dictionary
                if component_value.get("success"):
                    st.success(f"Subscription to {plan_name_to_use} successful! Status: {component_value.get('status', 'N/A')}")
                    st.balloons()
                    if component_value.get("subscription_id"):
                        st.write(f"Your Stripe Subscription ID: {component_value.get('subscription_id')}")
                    st.session_state.subscription_status = component_value.get('status', 'active')
                    
                    # Clear checkout state as we are done with this transaction
                    if "selected_price_id_for_checkout" in st.session_state:
                        del st.session_state["selected_price_id_for_checkout"]
                    if "selected_plan_name_for_checkout" in st.session_state:
                        del st.session_state["selected_plan_name_for_checkout"]
                    if "stripe_checkout_result" in st.session_state:
                        del st.session_state["stripe_checkout_result"]
                    
                    if st.button("🎉 Go to My Dashboard", key="post_sub_dashboard_btn_final_v3", type="primary"):
                        st.switch_page("pages/0_App.py")
                    show_payment_form = False # Do not show form after success
                    st.stop() # Stop to prevent re-rendering form on this successful run

                elif component_value.get("error"):
                    st.error(f"Subscription failed: {component_value.get('error')}")
                    if st.button("Try Payment Again?", key="retry_payment_btn_final_v3"):
                        del st.session_state["stripe_checkout_result"]
                        st.rerun() # Will make component_value None, so form shows
                    show_payment_form = False # Keep showing error and retry, don't overlay with form unless retried

                elif component_value.get("requires_action"):
                    st.warning("Your bank requires additional confirmation. Please follow prompts from Stripe.")
                    show_payment_form = False # Keep showing this message

                # "Change Plan / Cancel" button if there was an error or requires_action
                if not component_value.get("success") and show_payment_form == False : # Only show if not successful AND form not already showing
                    if st.button("Change Plan / Cancel Payment", key="cancel_payment_btn_final_v3"):
                        if "selected_price_id_for_checkout" in st.session_state:
                            del st.session_state["selected_price_id_for_checkout"]
                        if "selected_plan_name_for_checkout" in st.session_state:
                            del st.session_state["selected_plan_name_for_checkout"]
                        if "stripe_checkout_result" in st.session_state:
                            del st.session_state["stripe_checkout_result"]
                        st.rerun() # Go back to plan selection state

        # Render the HTML component based on the show_payment_form flag
        if show_payment_form:
            try:
                with open("components/stripe_checkout.html", "r") as f:
                    html_template = f.read()

                if not STRIPE_PUBLISHABLE_KEY or not FASTAPI_BACKEND_URL:
                    st.error("Stripe or Backend URL is not configured. Payment form cannot be loaded.")
                else:
                    component_html = html_template.replace("VAR_STRIPE_PUBLISHABLE_KEY", STRIPE_PUBLISHABLE_KEY)\
                                                  .replace("VAR_FASTAPI_BACKEND_URL", FASTAPI_BACKEND_URL)\
                                                  .replace("VAR_AUTH_TOKEN", auth_token)\
                                                  .replace("VAR_PRICE_ID", price_id_to_use)
                    
                    returned_value = st.components.v1.html(component_html, height=450, scrolling=False)
                    
                    if returned_value: # This means JS called Streamlit.setComponentValue
                        st.session_state.stripe_checkout_result = returned_value
                        st.rerun() # Rerun to process the result immediately
            except FileNotFoundError:
                st.error("Critical Error: Stripe payment component (stripe_checkout.html) not found.")
            except Exception as e:
                st.error(f"An error occurred loading the payment component: {e}")
    else:
        st.info("Select a plan above to proceed to payment.")

# --- Call the main function ---
if 'auth_token' not in st.session_state: # Initialize if running file directly
    st.session_state.auth_token = None # For direct run test

if __name__ == "__main__": # Allows testing this page standalone
    if st.session_state.auth_token is None: # Mock login for standalone test
        st.session_state.auth_token = "mock_test_token_subscribe"
        st.session_state.user_email = "test@example.com"
    display_subscription_page()
else: # When run as part of MPA
    display_subscription_page()
