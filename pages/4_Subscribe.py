# pages/4_Subscribe.py
import streamlit as st
import os
import time

# --- Configuration ---
# For Render, environment variables are the primary way.
# os.getenv("ENV_VAR_NAME_ON_RENDER", "fallback_if_not_set")

FASTAPI_BACKEND_URL = os.getenv("BACKEND_API_URL")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")

# Check if the essential variables were loaded from environment
if not FASTAPI_BACKEND_URL:
    st.error("FATAL ERROR: FASTAPI_BACKEND_URL environment variable is not set in the deployment environment.", icon="🚨")
    # For local development convenience ONLY, you might add a fallback here,
    # but the error above should alert you if it's missing in deployment.
    # FASTAPI_BACKEND_URL = "http://localhost:8000" # Example local fallback
    st.stop() # Stop the app if critical config is missing in deployment

if not STRIPE_PUBLISHABLE_KEY:
    st.error("FATAL ERROR: STRIPE_PUBLISHABLE_KEY environment variable is not set in the deployment environment.", icon="🚨")
    # STRIPE_PUBLISHABLE_KEY = "pk_test_YOUR_FALLBACK_KEY_FOR_LOCAL_DEV_ONLY" # Example local fallback
    st.stop() # Stop the app

# Optional: Log that the values were loaded (Streamlit typically prints to console, visible in Render logs)
print(f"INFO (4_Subscribe.py): FASTAPI_BACKEND_URL set to: {BACKEND_API_URL}")
print(f"INFO (4_Subscribe.py): STRIPE_PUBLISHABLE_KEY set to: {STRIPE_PUBLISHABLE_KEY[:15]}...")


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
    "enterprise": {
        "name": "Enterprise Plan",
        "display_price": "Custom Pricing",
        "base_fee_stripe_price_id": None,
        "description": "Tailored solutions, dedicated support, and custom integrations for large teams.",
        "success_fee_display": "Success fee based on % of qualified pipeline (negotiated).",
        "features": ["All Scale Features", "Custom Limits", "Bespoke Integrations", "Dedicated Support"],
        "cta_button_label": "Contact Sales",
        "cta_action": "contact_sales"
    }
}

def display_subscription_page():
    st.title("🚀 Subscribe to SalesTroopz")
    st.markdown("Choose the plan that best fits your sales outreach needs.")
    st.markdown("---")

    if 'auth_token' not in st.session_state or not st.session_state.auth_token:
        st.warning("Please log in or sign up to subscribe to a plan.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Go to Login", key="sub_page_login_btn_alt", use_container_width=True): # Ensure unique key
                st.switch_page("pages/1_Login.py")
        with col2:
            if st.button("Go to Sign Up", key="sub_page_signup_btn_alt", use_container_width=True): # Ensure unique key
                st.switch_page("pages/2_Signup.py")
        return

    auth_token = st.session_state.auth_token

    st.subheader("Select Your Plan:")
    plan_keys = list(PLANS_CONFIG.keys())
    cols = st.columns(len(plan_keys))

    for i, plan_key in enumerate(plan_keys):
        with cols[i]:
            plan = PLANS_CONFIG[plan_key]
            with st.container(border=True):
                st.header(plan["name"])
                st.markdown(f"## **{plan['display_price']}**")
                st.caption(plan["success_fee_display"])
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
                    st.link_button(plan["cta_button_label"], "mailto:your_sales_email@example.com?subject=Enterprise Plan Inquiry", use_container_width=True)
    st.markdown("---")

    if st.session_state.get("selected_price_id_for_checkout"):
        price_id_to_use = st.session_state.selected_price_id_for_checkout
        plan_name_to_use = st.session_state.selected_plan_name_for_checkout
        st.header(f"💳 Payment for: {plan_name_to_use}")
        st.caption("Please enter your card details below. Securely processed by Stripe.")

        component_value = st.session_state.get("stripe_checkout_result")
        if component_value:
            if component_value.get("success"):
                st.success(f"Subscription to {plan_name_to_use} successful! Status: {component_value.get('status', 'N/A')}")
                st.balloons()
                if component_value.get("subscription_id"):
                     st.write(f"Your Stripe Subscription ID: {component_value.get('subscription_id')}")
                st.session_state.subscription_status = component_value.get('status', 'active')
                del st.session_state["selected_price_id_for_checkout"]
                if "stripe_checkout_result" in st.session_state: # Check before deleting
                    del st.session_state["stripe_checkout_result"]
                if st.button("🎉 Go to My Dashboard", key="post_sub_dashboard_btn_unique", type="primary"): # Ensure unique key
                    st.switch_page("pages/0_App.py")
                st.stop()
            elif component_value.get("error"):
                st.error(f"Subscription failed: {component_value.get('error')}")
                if st.button("Try Payment Again?", key="retry_payment_btn_unique"): # Ensure unique key
                    if "stripe_checkout_result" in st.session_state:
                        del st.session_state["stripe_checkout_result"]
                    st.rerun()
            elif component_value.get("requires_action"):
                st.warning("Your bank requires additional confirmation. Please follow prompts from Stripe.")
            
            if not component_value.get("success"):
                if st.button("Change Plan / Cancel", key="cancel_payment_btn_unique"): # Ensure unique key
                    if "selected_price_id_for_checkout" in st.session_state:
                        del st.session_state["selected_price_id_for_checkout"]
                    if "stripe_checkout_result" in st.session_state:
                        del st.session_state["stripe_checkout_result"]
                    st.rerun()

        if not component_value or (component_value and component_value.get("error")):
            try:
                with open("components/stripe_checkout.html", "r") as f:
                    html_template = f.read()
                
                # Ensure STRIPE_PUBLISHABLE_KEY and FASTAPI_BACKEND_URL are valid strings
                if not STRIPE_PUBLISHABLE_KEY or not FASTAPI_BACKEND_URL:
                    st.error("Stripe or Backend URL is not configured. Payment form cannot be loaded.")
                else:
                    component_html = html_template.replace("VAR_STRIPE_PUBLISHABLE_KEY", STRIPE_PUBLISHABLE_KEY)\
                                                  .replace("VAR_BACKEND_API_URL",BACKEND_API_URL)\
                                                  .replace("VAR_AUTH_TOKEN", auth_token)\
                                                  .replace("VAR_PRICE_ID", price_id_to_use) 
                    
                    returned_value = st.components.v1.html(component_html, height=450, scrolling=False, key="stripe_checkout_form_active_subscribe") # Unique key
                    
                    if returned_value:
                        st.session_state.stripe_checkout_result = returned_value
                        st.rerun()
            except FileNotFoundError:
                st.error("Critical Error: Stripe payment component (stripe_checkout.html) not found.")
            except Exception as e:
                st.error(f"An error occurred loading the payment component: {e}")
    else:
        st.info("Select a plan above to proceed to payment.")

if __name__ == "__main__":
    if 'auth_token' not in st.session_state:
        st.session_state.auth_token = "mock_jwt_token_for_subscribe_test"
        st.session_state.user_email = "test@example.com"
    display_subscription_page()
else:
    display_subscription_page()
