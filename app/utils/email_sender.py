# app/utils/email_sender.py

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional

# Import logger
from app.utils.logger import logger
# --- Import the DB function to get settings ---
try:
    from app.db.database import get_org_email_settings_from_db
except ImportError:
    logger.critical("FATAL: Could not import database function 'get_org_email_settings_from_db'. Email sending will fail.")
    # Define a dummy function to prevent NameErrors later, but log critical failure
    def get_org_email_settings_from_db(org_id: int) -> Optional[Dict]:
        logger.error("Dummy get_org_email_settings_from_db called - DB module import failed!")
        return None

# --- Main Sending Function ---
def send_email(
    recipient_email: str,
    subject: str,
    html_body: str,
    organization_id: int # Required to fetch settings
    ) -> bool:
    """
    Fetches organization-specific email settings from the database
    and sends the email via the configured provider type.
    """
    logger.info(f"Initiating email send for Org {organization_id} to {recipient_email}")

    # 1. Get Organization's specific email settings from DB
    # This function should return decrypted credentials
    email_config = get_org_email_settings_from_db(organization_id)

    # 2. Validate Configuration
    if not email_config:
        logger.error(f"Email sending failed: Settings not found in DB for Org {organization_id}.")
        return False
    if not email_config.get("is_configured"):
        logger.error(f"Email sending failed: Settings not marked as configured for Org {organization_id}.")
        return False

    provider = email_config.get("provider_type")
    sender_address = email_config.get("verified_sender_email")
    sender_name = email_config.get("sender_name", f"Org {organization_id} Team") # Default name

    if not sender_address:
         logger.error(f"Email sending failed: Verified sender address missing in settings for Org {organization_id}.")
         return False
    if not provider:
         logger.error(f"Email sending failed: Provider type missing in settings for Org {organization_id}.")
         return False

    # Basic validation of core inputs
    if not all([recipient_email, subject, html_body]):
        logger.error(f"Email sending failed for Org {organization_id}: Missing recipient, subject, or body.")
        return False
    if '@' not in recipient_email:
         logger.error(f"Invalid recipient email address: {recipient_email}")
         return False
    if '@' not in sender_address:
         logger.error(f"Invalid sender email address from org settings: {sender_address}")
         return False


    # 3. Route to Provider-Specific Sending Function
    logger.info(f"Routing email for Org {organization_id} via provider: {provider}")
    if provider == 'smtp':
        # Pass only the necessary parts of the config to the SMTP function
        return _send_with_smtp(
            recipient_email=recipient_email,
            subject=subject,
            html_body=html_body,
            sender_address=sender_address,
            sender_name=sender_name,
            smtp_config=email_config # Contains host, port, user, decrypted pass
        )
    elif provider == 'ses_api': # Example if you add AWS SES API later
        return _send_with_ses_api(
            recipient_email=recipient_email,
            subject=subject,
            html_body=html_body,
            sender_address=sender_address,
            sender_name=sender_name,
            # SES API might use IAM keys from env vars, not stored per-org initially
            # aws_config=email_config # Pass if needed
        )
    # Add elif for 'google_oauth', 'm365_oauth', 'sendgrid_api', etc.
    else:
        logger.error(f"Unsupported email provider type '{provider}' configured for Org {organization_id}.")
        return False


# --- SMTP Sending Logic ---
def _send_with_smtp(recipient_email: str, subject: str, html_body: str, sender_address: str, sender_name: str, smtp_config: dict) -> bool:
    """Handles sending via standard SMTP using decrypted credentials from smtp_config."""

    host = smtp_config.get("smtp_host")
    port = smtp_config.get("smtp_port") # Should be int
    username = smtp_config.get("smtp_username")
    password = smtp_config.get("smtp_password") # This is the DECRYPTED password/app password

    if not all([host, port, username, password]):
         logger.error(f"SMTP configuration incomplete for sender {sender_address} via {host}. Required: host, port, username, password.")
         return False

    logger.info(f"Attempting SMTP send via {host}:{port} from {sender_address} to {recipient_email}")

    # Construct message
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{sender_name} <{sender_address}>"
    message["To"] = recipient_email
    try:
        part = MIMEText(html_body, "html", "utf-8")
        message.attach(part)
    except Exception as e:
        logger.error(f"Failed to create SMTP email body MIMEText part: {e}")
        return False

    # Send via SMTP
    server = None
    try:
        # Handle potential non-integer port from DB retrieval if not validated earlier
        smtp_port_int = int(port)
        if smtp_port_int == 465:
            server = smtplib.SMTP_SSL(host, smtp_port_int, timeout=20)
        else: # Assume STARTTLS for 587 or others
            server = smtplib.SMTP(host, smtp_port_int, timeout=20)
            server.starttls()
        server.login(username, password)
        server.sendmail(sender_address, recipient_email, message.as_string())
        logger.info(f"Email successfully sent via SMTP to: {recipient_email}")
        return True
    except smtplib.SMTPAuthenticationError as e: logger.error(f"SMTP Auth Error for {username} on {host}: {e}", exc_info=False) # Don't log password details
    except smtplib.SMTPConnectError as e: logger.error(f"SMTP Connection Error to {host}:{port}: {e}", exc_info=True)
    except smtplib.SMTPSenderRefused as e: logger.error(f"SMTP Sender Refused: {sender_address}. Error: {e}", exc_info=True)
    except smtplib.SMTPRecipientsRefused as e: logger.error(f"SMTP Recipient Refused: {recipient_email}. Error: {e.recipients}", exc_info=True)
    except smtplib.SMTPException as e: logger.error(f"SMTP Error sending to {recipient_email}: {e}", exc_info=True)
    except ValueError as e: logger.error(f"SMTP Config Error (invalid port? {port}): {e}", exc_info=True)
    except OSError as e: logger.error(f"Network/OS Error during SMTP connection: {e}", exc_info=True)
    except Exception as e: logger.error(f"Unexpected SMTP error sending to {recipient_email}: {e}", exc_info=True)
    finally:
        if server:
             try: server.quit()
             except: pass
    return False


# --- Placeholder for AWS SES API Sending Logic ---
def _send_with_ses_api(recipient_email: str, subject: str, html_body: str, sender_address: str, sender_name: str, **kwargs) -> bool:
    """[Placeholder] Handles sending via AWS SES API using Boto3."""
    logger.warning("SES API sending (_send_with_ses_api) not fully implemented yet.")
    # Add Boto3 imports and logic here if/when needed
    # import boto3
    # from botocore.exceptions import ClientError, NoCredentialsError
    # try:
    #    ses_client = boto3.client('ses', region_name=...) # Get region
    #    source = f"{sender_name} <{sender_address}>"
    #    response = ses_client.send_email(...)
    #    return True
    # except NoCredentialsError: logger.error("AWS Credentials not found for SES.")
    # except ClientError as e: logger.error(f"AWS SES ClientError: {e}")
    # except Exception as e: logger.error(f"Unexpected SES error: {e}")
    return False # Return False until implemented

# --- Add placeholders for other providers as needed ---
# def _send_with_google_oauth(...) -> bool: ...
# def _send_with_sendgrid(...) -> bool: ...
