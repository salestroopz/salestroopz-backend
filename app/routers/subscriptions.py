# app/routers/subscriptions.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import stripe # Ensure stripe is imported

from app.schemas import CreateSubscriptionRequest, CreateSubscriptionResponse, UserPublic, SubscriptionCreate
from app.db.database import get_db
from app.db import database as db_ops # Using db_ops as alias for your database module
from app.auth.dependencies import get_current_user
from app.utils.logger import logger
from app.utils.config import settings # For Stripe keys if not set globally on stripe module

router = APIRouter(
    prefix="/api/v1/subscriptions",
    tags=["Subscriptions"]
)

@router.post("/create-subscription", response_model=CreateSubscriptionResponse)
async def create_subscription_endpoint(
    request_data: CreateSubscriptionRequest,
    db: Session = Depends(get_db),
    current_user: UserPublic = Depends(get_current_user)
):
    organization_id = current_user.organization_id
    logger.info(f"Attempting to create subscription for Org ID: {organization_id}, Price ID: {request_data.price_id}")

    try:
        org = db_ops.get_organization_by_id(db=db, organization_id=organization_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        stripe_customer_id = org.stripe_customer_id

        if not stripe_customer_id:
            logger.info(f"No Stripe Customer ID found for Org {organization_id}. Creating new Stripe Customer.")
            customer = stripe.Customer.create(
                email=current_user.email, # Assuming user email is org contact
                name=org.name,
                payment_method=request_data.payment_method_id,
                invoice_settings={'default_payment_method': request_data.payment_method_id}
            )
            stripe_customer_id = customer.id
            db_ops.update_organization_stripe_customer_id(db=db, organization_id=organization_id, stripe_customer_id=stripe_customer_id)
            logger.info(f"Created Stripe Customer {stripe_customer_id} for Org {organization_id}")
        else:
            logger.info(f"Using existing Stripe Customer {stripe_customer_id} for Org {organization_id}")
            # Attach the new payment method and set as default
            try:
                stripe.PaymentMethod.attach(request_data.payment_method_id, customer=stripe_customer_id)
                stripe.Customer.modify(stripe_customer_id, invoice_settings={'default_payment_method': request_data.payment_method_id})
                logger.info(f"Attached PaymentMethod {request_data.payment_method_id} to Customer {stripe_customer_id}")
            except stripe.error.StripeError as e:
                logger.error(f"Stripe error attaching PM to existing customer {stripe_customer_id}: {e.user_message or str(e)}")
                raise HTTPException(status_code=400, detail=f"Could not update payment method: {e.user_message or str(e)}")


        logger.info(f"Creating Stripe subscription for Customer {stripe_customer_id} with Price {request_data.price_id}")
        subscription = stripe.Subscription.create(
            customer=stripe_customer_id,
            items=[{'price': request_data.price_id}],
            payment_behavior='default_incomplete_if_authentication_required',
            expand=['latest_invoice.payment_intent', 'pending_setup_intent'] # expand setup_intent for trial with no upfront payment
        )
        logger.info(f"Stripe subscription {subscription.id} created with status {subscription.status}")

        # Prepare data for your DB
        sub_data_for_db = SubscriptionCreate(
            organization_id=organization_id,
            stripe_subscription_id=subscription.id,
            stripe_customer_id=stripe_customer_id,
            stripe_price_id=request_data.price_id, # Could also get from subscription.items.data[0].price.id
            stripe_product_id=subscription.items.data[0].price.product if subscription.items.data else None,
            status=subscription.status,
            current_period_start=datetime.fromtimestamp(subscription.current_period_start, tz=timezone.utc) if subscription.current_period_start else None,
            current_period_end=datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc) if subscription.current_period_end else None,
            cancel_at_period_end=subscription.cancel_at_period_end,
            trial_end_at=datetime.fromtimestamp(subscription.trial_end, tz=timezone.utc) if subscription.trial_end else None,
        )
        db_ops.create_or_update_subscription(db=db, sub_in=sub_data_for_db)

        client_secret = None
        if subscription.status == 'incomplete' and subscription.latest_invoice and subscription.latest_invoice.payment_intent:
            client_secret = subscription.latest_invoice.payment_intent.client_secret
            logger.info(f"Subscription {subscription.id} requires action. Client secret for PaymentIntent provided.")
        elif subscription.status == 'trialing' and subscription.pending_setup_intent: # For trials that need card setup confirmation
             client_secret = subscription.pending_setup_intent.client_secret
             logger.info(f"Subscription {subscription.id} is trialing and requires setup intent confirmation.")


        return CreateSubscriptionResponse(
            subscription_id=subscription.id,
            status=subscription.status,
            client_secret=client_secret
        )

    except stripe.error.CardError as e:
        logger.warning(f"Stripe Card Error for Org {organization_id}: {e.user_message or str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.user_message or "Card error.")
    except stripe.error.StripeError as e:
        logger.error(f"General Stripe Error for Org {organization_id}: {e.user_message or str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Payment provider error.")
    except Exception as e:
        logger.error(f"Unexpected error creating subscription for Org {organization_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An internal error occurred.")
