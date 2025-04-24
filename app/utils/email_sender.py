# app/utils/email_sender.py

import boto3 # Use AWS SDK
from botocore.exceptions import ClientError, NoCredentialsError # Specific AWS errors
from typing import Dict, Optional

# Import utilities and settings
try:
    from app.utils.config import settings
    CONFIG_LOADED = True
    # Get AWS Region from settings, provide a default
    AWS_REGION = getattr(settings, "AWS_REGION", "us-east-1")
except ImportError:
    print("Warning: Could not import settings for email_sender. AWS region/sender fallback.")
    settings = None
    CONFIG_LOADED = False
    AWS_REGION = "us-east-1" # Default region if settings fail

from app.utils.logger import logger
# Import DB function ONLY when ready to fetch org-specific senders
# from app.db import database

# --- Function to get Organization-Specific Email Settings ---
# --- TODO: Replace this with actual DB lookup for verified sender per org ---
def get_org_email_settings(organization_id: int) -> Dict[str, Optional[str]]:
    """
    [NEEDS DB IMPLEMENTATION FOR MULTI-TENANCY]
    Fetches the VERIFIED SENDER email address and desired sender name for an organization.
    Currently falls back to global settings defined in config/environment.
    """
    sender_address = None
    sender_name = f"Sales Team Org {organization_id}" # Default name

    if CONFIG_LOADED:
        # In future, fetch specific verified sender for the org from DB:
        # db_settings = database.get_email_config_for_org(organization_id)
        # if db_settings and db_settings.get('verified_sender_email'):
        #     sender_address = db_settings['verified_sender_email']
        #     sender_name = db_settings.get('sender_name', sender_name) # Use specific name if set
        # else: # Fallback if no specific setting found for org
        #     logger.warning(f"No specific sender email found for Org {organization_id}, using default.")
        #     sender_address = getattr(settings, "DEFAULT_SENDER_EMAIL", None)
        #     sender_name = getattr(settings, "DEFAULT_SENDER_NAME", sender_name)

        # --- CURRENT IMPLEMENTATION: Fallback to global default ---
        logger.warning(f"Fetching email settings for Org {organization_id}. Using GLOBAL default sender from config/environment. Implement DB lookup.")
        sender_address = getattr(settings, "DEFAULT_SENDER_EMAIL", None)
        sender_name = getattr(settings, "DEFAULT_SENDER_NAME", sender_name)
    else:
         logger.error(f"Cannot get email settings for Org {organization_id}: Config not loaded.")

    if not sender_address:
         logger.error(f"Configuration Error: No sender email address available (checked Org {organization_id} specific and default). Cannot send email.")
         # Return None for sender_address to indicate failure clearly
         return {"sender_address": None, "sender_name": None}

    # Return only the necessary sender info for SES API call structure
    return {
        "sender_address": sender_address, # This MUST be an address/domain verified in your SES account
        "sender_name": sender_name,
    }


# --- Core Email Sending Function (Using AWS SES API) ---
def send_email_ses(
    recipient_email: str,
    subject: str,
    html_body: str,
    sender_address: str, # The verified sender email address
    sender_name: str,
    aws_region: str = AWS_REGION # Use region from config/default
    ) -> bool:
    """
    Sends an email using AWS SES API (boto3).

    Args:
        recipient_email: The recipient's email address.
        subject: The email subject line.
        html_body: The HTML content of the email body.
        sender_address: The SES-verified email address to send from.
        sender_name: The desired display name for the sender.
        aws_region: The AWS region where SES is configured.

    Returns:
        bool: True if the email was successfully accepted by SES API, False otherwise.
    """
    # Basic validation
    if not all([recipient_email, subject, html_body, sender_address, sender_name, aws_region]):
        logger.error("SES Email sending failed: Missing required parameters.")
        return False
    if '@' not in recipient_email:
         logger.error(f"Invalid recipient email address provided: {recipient_email}")
         return False
    if '@' not in sender_address:
         logger.error(f"Invalid sender email address provided: {sender_address}")
         return False

    # Format sender address required by SES API: "Sender Name <email@example.com>"
    source = f"{sender_name} <{sender_address}>"
    charset = "UTF-8" # Standard charset

    # Create SES client
    # Boto3 automatically looks for credentials in standard locations:
    # 1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY) - **RECOMMENDED ON RENDER**
    # 2. Shared credential file (~/.aws/credentials)
    # 3. AWS config file (~/.aws/config)
    # 4. IAM role attached to the instance (if running on EC2/ECS)
    try:
        ses_client = boto3.client('ses', region_name=aws_region)
        logger.debug(f"AWS SES client created for region {aws_region}.")
    except NoCredentialsError:
         logger.error("AWS credentials not found. Ensure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables are set correctly.")
         return False
    except Exception as e:
         logger.error(f"Failed to create AWS SES client in region {aws_region}: {e}", exc_info=True)
         return False

    # Try sending the email via SES API
    try:
        logger.info(f"Attempting to send email via SES from '{source}' to '{recipient_email}'")
        # Use the send_email operation
        response = ses_client.send_email(
            Destination={'ToAddresses': [recipient_email]},
            Message={
                'Body': {
                    'Html': {'Charset': charset, 'Data': html_body},
                    # 'Text': {'Charset': charset, 'Data': "Plain text version here"} # Optional plain text
                },
                'Subject': {'Charset': charset, 'Data': subject},
            },
            Source=source,
            # Optional: Add Reply-To Addresses if different from Source
            # ReplyToAddresses=[ 'reply-to@example.com' ],
            # Optional: Use Configuration Set for event tracking (bounces, complaints, clicks)
            # ConfigurationSetName='YourSESConfigurationSetName',
        )
        # Log the SES Message ID on success
        message_id = response.get('MessageId')
        logger.info(f"Email successfully sent via SES to {recipient_email}. Message ID: {message_id}")
        return True # Indicate successful sending call

    except ClientError as e:
        # Handle specific AWS SES errors
        error_code = e.response.get('Error', {}).get('Code')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        logger.error(f"AWS SES ClientError sending to {recipient_email}: [{error_code}] {error_message}")
        # Specific handling for common issues
        if error_code == 'MessageRejected':
            logger.error("SES Message Rejected. Possible reasons: Email address not verified (if in Sandbox), sending limits exceeded, blacklisted recipient.")
        elif error_code == 'InvalidParameterValue':
             logger.error(f"SES Invalid Parameter. Check formatting of email addresses, source, etc.")
        elif error_code == 'AccessDeniedException':
             logger.error(f"SES Access Denied. Check IAM permissions for the configured AWS credentials.")
        # Add more specific error code handling if needed
        return False # Indicate failure
    except Exception as e:
        # Catch any other unexpected errors during the API call
        logger.error(f"Unexpected error sending email via SES to {recipient_email}: {e}", exc_info=True)
        return False # Indicate failure
