import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional

# Import utilities and settings
try:
    from app.utils.config import settings
    CONFIG_LOADED = True
except ImportError:
    print("Warning: Could not import settings for email_sender. Using function arguments only.")
    settings = None # type: ignore # Indicate settings are unavailable
    CONFIG_LOADED = False

from app.utils.logger import logger
# Import database functions ONLY if storing/fetching org settings from DB
# This version assumes settings come from global config or arguments for simplicity first
# from app.db import database

# --- Function to get Organization-Specific Email Settings ---
# --- TODO: Replace this with actual DB lookup later ---
def get_org_email_settings(organization_id: int) -> Dict[str, Optional[str]]:
    """
    [NEEDS DB IMPLEMENTATION FOR MULTI-TENANCY]
    Fetches email sending SMTP settings for a specific organization.
    Currently falls back to global settings defined in config/environment.
    """
    if not CONFIG_LOADED:
         logger.error(f"Cannot get email settings for Org {organization_id}: Config not loaded.")
         # Return dictionary with None values to indicate failure clearly
         return {
             "smtp_host": None, "smtp_port": None, "smtp_username": None,
             "smtp_password": None, "sender_address": None, "sender_name": None
         }

    logger.warning(f"Fetching email settings for Org {organization_id}. Currently using GLOBAL settings from config/environment. Implement DB lookup for per-org settings.")

    # In a real multi-tenant app, you would:
    # 1. Have an 'organization_settings' table linked to 'organizations'.
    # 2. Store encrypted SMTP credentials, host, port, sender address/name per org.
    # 3. Call a database function here: db_settings = database.get_settings_for_org(organization_id)
    # 4. Return the fetched settings.

    # --- Fallback to global settings ---
    # Use getattr for safety in case settings object itself failed import slightly differently
    host = getattr(settings, "EMAIL_HOST", None)
    port_str = getattr(settings, "EMAIL_PORT", "587") # Default port
    username = getattr(settings, "EMAIL_USERNAME", None)
    password = getattr(settings, "EMAIL_PASSWORD", None)
    sender_addr = getattr(settings, "EMAIL_SENDER_ADDRESS", None)
    sender_name = getattr(settings, "EMAIL_SENDER_NAME", f"Sales Team Org {organization_id}") # Default name

    # Validate port conversion
    port = None
    try:
        port = int(port_str) if port_str else 587
    except ValueError:
        logger.error(f"Invalid EMAIL_PORT setting: '{port_str}'. Using default 587.")
        port = 587

    # Return dictionary matching expected keys
    return {
        "smtp_host": host,
        "smtp_port": port,
        "smtp_username": username,
        "smtp_password": password,
        "sender_address": sender_addr,
        "sender_name": sender_name
    }


# --- Core Email Sending Function ---
def send_email(
    recipient_email: str,
    subject: str,
    html_body: str,
    # Configuration parameters (passed directly or fetched via get_org_email_settings)
    sender_address: str,
    sender_name: str,
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: str
    ) -> bool:
    """
    Sends an email using SMTP STARTTLS.

    Returns:
        bool: True if sending was successful (or at least didn't raise known errors), False otherwise.
    """
    # Basic validation of inputs
    if not all([recipient_email, subject, html_body, sender_address, sender_name, smtp_host, smtp_port, smtp_username, smtp_password]):
        logger.error("Email sending failed: Missing one or more required parameters (recipient, subject, body, sender, host, port, user, pass).")
        # Log which parameter might be missing if possible
        return False

    if '@' not in recipient_email:
         logger.error(f"Invalid recipient email address: {recipient_email}")
         return False

    # Construct the email message
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{sender_name} <{sender_address}>"
    message["To"] = recipient_email
    # Consider adding Reply-To header?
    # message.add_header('Reply-To', sender_address)

    # Attach HTML body
    # Ensure encoding is handled correctly, default is usually ascii, force utf-8
    try:
        part = MIMEText(html_body, "html", "utf-8")
        message.attach(part)
    except Exception as e:
        logger.error(f"Failed to create email body MIMEText part: {e}")
        return False


    # Connect and send using SMTP_SSL or SMTP with STARTTLS
    server = None # Initialize server variable
    try:
        logger.info(f"Attempting to send email via {smtp_host}:{smtp_port} from {sender_address} to {recipient_email}")
        # Use SMTP_SSL for ports like 465, STARTTLS for 587 (common)
        if smtp_port == 465:
            logger.debug("Connecting using SMTP_SSL...")
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20) # Add timeout
        else: # Assume STARTTLS for other ports like 587, 25
            logger.debug("Connecting using SMTP and STARTTLS...")
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=20)
            server.ehlo()
            server.starttls() # Secure the connection
            server.ehlo() # Re-identify ourselves over TLS connection

        # Login
        logger.debug(f"Logging into SMTP server with username: {smtp_username}")
        server.login(smtp_username, smtp_password)

        # Send Email
        logger.debug(f"Sending email to: {recipient_email} | Subject: {subject}")
        server.sendmail(sender_address, recipient_email, message.as_string())
        logger.info(f"Email successfully sent to: {recipient_email}")
        return True # Indicate success

    except smtplib.SMTPAuthenticationError as e:
         logger.error(f"SMTP Authentication Error (check username/password/app password): {e}", exc_info=True)
    except smtplib.SMTPServerDisconnected as e:
         logger.error(f"SMTP Server Disconnected: {e}", exc_info=True)
    except smtplib.SMTPConnectError as e:
         logger.error(f"SMTP Connection Error (check host/port): {e}", exc_info=True)
    except smtplib.SMTPRecipientsRefused as e:
         logger.error(f"SMTP Recipient Refused for {recipient_email}: {e.recipients}", exc_info=True) # Log refused recipients
    except smtplib.SMTPException as e: # Catch other potential SMTP errors
        logger.error(f"SMTP Error sending email to {recipient_email}: {e}", exc_info=True)
    except OSError as e: # Catch potential network errors (e.g., DNS lookup failure)
         logger.error(f"Network/OS Error sending email: {e}", exc_info=True)
    except Exception as e: # Catch any other unexpected errors during sending
        logger.error(f"Unexpected error sending email to {recipient_email}: {e}", exc_info=True)

    return False # Indicate failure if any exception occurred

    finally:
        # Ensure server connection is closed
        if server:
            try:
                server.quit()
                logger.debug("SMTP connection closed.")
            except smtplib.SMTPServerDisconnected:
                 logger.debug("SMTP server already disconnected.") # Ignore if already closed
            except Exception as e_quit:
                 logger.error(f"Error quitting SMTP connection: {e_quit}")
