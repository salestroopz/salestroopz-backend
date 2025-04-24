# app/agents/emailcampaign.py

import json
from typing import Dict, Any, Optional, List
import openai # Use the official OpenAI library
from tenacity import retry, stop_after_attempt, wait_random_exponential # For retrying API calls

# Import utilities and settings
from app.utils.logger import logger
try:
    from app.utils.config import settings
    # Ensure OPENAI_API_KEY is loaded
    if not hasattr(settings, 'OPENAI_API_KEY') or settings.OPENAI_API_KEY == "ENV_VAR_NOT_SET" or not settings.OPENAI_API_KEY:
         logger.warning("OpenAI API Key not configured in settings. Email crafting will fail.")
         openai.api_key = None # Ensure it's None if not set
         # raise ValueError("OpenAI API Key is not configured.") # Or raise error
    else:
         openai.api_key = settings.OPENAI_API_KEY
except ImportError:
    logger.error("Could not import settings. OpenAI API Key cannot be set.")
    settings = None
    openai.api_key = None
except Exception as e:
    logger.error(f"Error setting OpenAI API key: {e}")
    openai.api_key = None


class EmailCraftingAgent:
    """
    Agent responsible for crafting personalized email content using OpenAI.
    """
    def __init__(self, model: str = "gpt-3.5-turbo"): # Default to GPT-3.5 Turbo
        if not openai.api_key:
            logger.error("EmailCraftingAgent cannot initialize: OpenAI API Key is missing.")
            # Prevent instantiation if key is missing to avoid errors later
            raise ValueError("OpenAI API Key required for EmailCraftingAgent but is not configured.")
        self.model = model
        logger.info(f"EmailCraftingAgent initialized with model: {self.model}")

    @retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(3))
    def _call_openai_api(self, prompt: str) -> Optional[Dict[str, str]]:
        """
        Makes the API call to OpenAI with retry logic.
        Parses the expected JSON response. Returns dict or None.
        """
        logger.debug(f"Calling OpenAI API with model {self.model}. Prompt length: {len(prompt)}")
        if not openai.api_key: # Redundant check, but safe
             logger.error("Cannot call OpenAI: API Key is missing.")
             return None
        try:
            # Using the chat completions endpoint
            response = openai.chat.completions.create(
                model=self.model,
                messages=[
                    # System message helps set the context for the AI assistant
                    {"role": "system", "content": "You are an expert B2B sales assistant specialized in writing concise, personalized cold outreach emails."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7, # Adjust for creativity/focus balance
                max_tokens=500,  # Limit response length to control cost/verbosity
                # Request JSON output format
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            logger.debug(f"OpenAI Raw Response Content: {content}")

            # Parse the JSON response string
            try:
                 email_content = json.loads(content)
                 if isinstance(email_content, dict) and "subject" in email_content and "body" in email_content:
                      # Basic validation: ensure subject/body are strings
                      if isinstance(email_content["subject"], str) and isinstance(email_content["body"], str):
                           return email_content
                      else:
                           logger.error(f"OpenAI response JSON values are not strings: {email_content}")
                           return None
                 else:
                      logger.error(f"OpenAI response JSON is missing 'subject' or 'body': {content}")
                      return None
            except json.JSONDecodeError as json_err:
                logger.error(f"Failed to parse OpenAI JSON response: {json_err}. Response: {content}")
                return None # Indicate failure

        # Handle specific OpenAI errors (requires openai library >= 1.0)
        except openai.APIError as e: logger.error(f"OpenAI API Error: {e}")
        except openai.AuthenticationError as e: logger.error(f"OpenAI Auth Error (check API key): {e}")
        except openai.RateLimitError as e: logger.error(f"OpenAI Rate Limit Exceeded: {e}")
        except openai.APIConnectionError as e: logger.error(f"OpenAI Connection Error: {e}")
        except openai.APITimeoutError as e: logger.error(f"OpenAI Request Timed Out: {e}")
        except Exception as e: logger.error(f"Unexpected error during OpenAI API call: {e}", exc_info=True)

        return None # Return None if any exception occurred


    def craft_initial_email(
        self,
        lead_data: Dict[str, Any],
        offering_data: Dict[str, Any],
        icp_data: Optional[Dict[str, Any]], # ICP might be None
        organization_name: str = "our company" # Sender's org name
        ) -> Optional[Dict[str, str]]:
        """
        Crafts a personalized initial outreach email using OpenAI.
        """
        lead_email = lead_data.get('email', 'N/A') # Use email for logging
        logger.info(f"Crafting initial email for lead: {lead_email}")

        if not offering_data:
            logger.error(f"Cannot craft email for {lead_email}: Offering data is missing.")
            return None

        # --- Build the Prompt ---
        prompt_parts = []
        prompt_parts.append("You are an expert B2B sales assistant writing a personalized cold outreach email.")
        prompt_parts.append("Goal: Intrigue the prospect about a solution relevant to their potential pain points and encourage them to accept a brief introductory meeting.")
        prompt_parts.append("Constraints: Keep the email concise (under 150 words), professional, helpful, and focused on the prospect's potential needs. Avoid sounding generic or overly pushy. Do not use emojis.")
        prompt_parts.append(f"Your Company Name: {organization_name}")

        # Recipient Context
        recipient_name = lead_data.get('name', '').split(' ')[0] or "there" # Use first name or fallback
        recipient_title = lead_data.get('title')
        recipient_company = lead_data.get('company')
        prompt_parts.append("\nRecipient Context:")
        prompt_parts.append(f"- Name: {recipient_name}")
        if recipient_title: prompt_parts.append(f"- Title: {recipient_title}")
        if recipient_company: prompt_parts.append(f"- Company: {recipient_company}")

        # Offering Context
        offering_name = offering_data.get('name')
        offering_desc = offering_data.get('description')
        # Ensure features/pain points are lists before joining
        offering_features = offering_data.get('key_features') if isinstance(offering_data.get('key_features'), list) else []
        offering_pain_points = offering_data.get('target_pain_points') if isinstance(offering_data.get('target_pain_points'), list) else []
        offering_cta = offering_data.get('call_to_action')
        prompt_parts.append("\nYour Offering Context:")
        if offering_name: prompt_parts.append(f"- Offering: {offering_name}")
        if offering_desc: prompt_parts.append(f"- Description: {offering_desc}")
        if offering_features: prompt_parts.append(f"- Key Features: {', '.join(offering_features)}")
        if offering_pain_points: prompt_parts.append(f"- Solves Pain Points Like: {', '.join(offering_pain_points)}")

        # Personalization Angle
        prompt_parts.append("\nPersonalization Angle:")
        prompt_parts.append("Based on the recipient's title and company (and potentially their industry/location if available in lead data), briefly mention ONE relevant pain point (from the 'Solves Pain Points Like' list) that someone in their role likely faces.")
        prompt_parts.append("Connect how ONE or TWO key features of your offering specifically address that pain point.")
        prompt_parts.append("Keep the connection brief and benefit-oriented.")

        # Call to Action
        prompt_parts.append("\nCall To Action:")
        prompt_parts.append(f"End the email with a clear, low-friction call to action. Suggest '{offering_cta or 'a brief 15-minute chat to explore further'}'. Make it easy to say yes.")

        # Output Format Instruction
        prompt_parts.append('\nOutput Format:')
        prompt_parts.append('Respond ONLY with a valid JSON object containing exactly two keys: "subject" (string, concise and compelling email subject) and "body" (string, the plain text email body). Do not include any other text, greetings, or explanations outside the JSON structure.')
        prompt_parts.append('Example: {"subject": "Idea for [Company Name]", "body": "Hi [Name],\\n\\nNoticed you\'re the [Title] at [Company Name]..."}')

        final_prompt = "\n".join(prompt_parts)

        # --- Call OpenAI API ---
        email_content = self._call_openai_api(final_prompt)

        if email_content:
            logger.info(f"Successfully crafted email for {lead_email}. Subject: {email_content.get('subject')}")
            return email_content
        else:
            logger.error(f"Failed to craft email content for {lead_email}")
            return None
