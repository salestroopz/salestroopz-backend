# app/agents/reply_classifier_agent.py
import json
from typing import Dict, Any, Optional, List # Ensure List is imported for categories

from openai import OpenAI, APIError # Import specific errors if desired for more granular handling
# from tenacity import retry, stop_after_attempt, wait_random_exponential # Optional for API calls

from app.utils.logger import logger
from app.utils.config import settings # To get API keys, model names

# Define the categories you want the LLM to use
# Using an Enum can be good for consistency, but a list of strings is fine for the prompt
REPLY_CATEGORIES = [
    "POSITIVE_MEETING_INTEREST",    # Explicitly wants to meet or discuss further.
    "POSITIVE_GENERAL_INTEREST",    # Shows interest, asks for more info, but not a direct meeting request.
    "NEGATIVE_NOT_INTERESTED",      # Clearly states no interest.
    "NEGATIVE_UNSUBSCRIBE",         # Asks to be removed from the list / stop emails.
    "NEGATIVE_WRONG_PERSON",        # Indicates they are not the right contact.
    "QUESTION_PRODUCT_SERVICE",     # Asks specific questions about the product/service.
    "QUESTION_OBJECTION",           # Raises an objection or concern.
    "OUT_OF_OFFICE_AUTO_REPLY",     # Standard OOO message.
    "NEUTRAL_ACKNOWLEDGEMENT",      # e.g., "Thanks", "Got it", "Okay".
    "NEUTRAL_AUTO_REPLY_OTHER",     # Other automated replies (not OOO, e.g., "message received").
    "CANNOT_CLASSIFY_GIBBERISH"     # If the reply is unintelligible or clearly not relevant.
]

class ReplyClassifierAgent:
    def __init__(self, llm_model: Optional[str] = None):
        self.llm_model = llm_model or getattr(settings, "OPENAI_REPLY_CLASSIFICATION_MODEL", "gpt-3.5-turbo") # Default model
        self.openai_api_key = getattr(settings, "OPENAI_API_KEY", None)

        if not self.openai_api_key:
            logger.error("ReplyClassifierAgent: OPENAI_API_KEY not found in settings. Classification will fail.")
            # raise ValueError("OpenAI API Key is required for ReplyClassifierAgent") # Or handle gracefully
            self.client = None
        else:
            try:
                self.client = OpenAI(api_key=self.openai_api_key)
                logger.info(f"ReplyClassifierAgent initialized with OpenAI model: {self.llm_model}")
            except Exception as e:
                logger.error(f"ReplyClassifierAgent: Failed to initialize OpenAI client: {e}", exc_info=True)
                self.client = None

    def _construct_prompt(self, cleaned_reply_text: str, lead_name: Optional[str] = None) -> str:
        lead_name_str = f"from {lead_name}" if lead_name else "from a prospect"
        
        categories_str = ", ".join([f"'{cat}'" for cat in REPLY_CATEGORIES])

        prompt = f"""
        You are an expert assistant tasked with classifying email replies received during a B2B sales outreach campaign.
        The goal is to accurately categorize the intent of the reply and extract key information.

        Reply Text {lead_name_str}:
        ---
        {cleaned_reply_text}
        ---

        Instructions:
        1. Analyze the reply text provided above.
        2. Classify the reply into ONE of the following categories: {categories_str}.
           Choose the category that best represents the primary intent of the reply.
        3. Provide a concise 1-2 sentence summary of the reply's main point.
        4. If the reply contains any specific scheduling suggestions, questions about the product/service, or objections, try to extract them.

        Output Format:
        Respond ONLY with a single valid JSON object containing the following keys:
        - "category": (string) One of the predefined categories listed above. This field is mandatory.
        - "summary": (string) A brief 1-2 sentence summary of the reply. This field is mandatory.
        - "extracted_info": (object, optional) An object containing relevant extracted details. Examples:
            - If POSITIVE_MEETING_INTEREST and a time is suggested: {{"meeting_suggestion": "Tuesday next week around 2 PM"}}
            - If QUESTION_PRODUCT_SERVICE: {{"questions_asked": ["What is the pricing?", "Do you integrate with X?"]}}
            - If NEGATIVE_WRONG_PERSON and a referral is made: {{"referred_to": "john.doe@example.com"}}
            - If no specific entities are extractable for this category, this field can be omitted or be an empty object.
        
        Example of a valid JSON output for a positive reply with a meeting suggestion:
        {{
            "category": "POSITIVE_MEETING_INTEREST",
            "summary": "The prospect is interested and suggested meeting next week.",
            "extracted_info": {{
                "meeting_suggestion": "next week"
            }}
        }}

        Example for a question:
        {{
            "category": "QUESTION_PRODUCT_SERVICE",
            "summary": "The prospect is asking about integration capabilities.",
            "extracted_info": {{
                "questions_asked": ["Does it integrate with Salesforce?"]
            }}
        }}
        
        Example for a simple 'not interested':
        {{
            "category": "NEGATIVE_NOT_INTERESTED",
            "summary": "The prospect has indicated they are not interested at this time.",
            "extracted_info": {{}}
        }}

        Ensure the entire response is only the JSON object.
        """
        return prompt.strip()

    # Consider adding @retry from tenacity for robustness if not handled by OpenAI's SDK v1+ by default for some errors
    def classify_reply_text(self, cleaned_reply_text: str, lead_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.client:
            logger.error("ReplyClassifierAgent: OpenAI client not initialized. Cannot classify reply.")
            return None
        if not cleaned_reply_text or not cleaned_reply_text.strip():
            logger.warning("ReplyClassifierAgent: Received empty or whitespace-only reply text. Cannot classify.")
            return {"category": "CANNOT_CLASSIFY_GIBBERISH", "summary": "Reply was empty.", "extracted_info": {}}

        prompt = self._construct_prompt(cleaned_reply_text, lead_name)
        logger.debug(f"ReplyClassifierAgent: Sending prompt to LLM for classification (length: {len(prompt)}). Reply snippet: {cleaned_reply_text[:100]}...")

        try:
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "You are an intelligent assistant that classifies email replies and extracts information according to specific instructions, outputting valid JSON."}, # System message to guide behavior
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2, # Lower temperature for more deterministic classification
                # max_tokens=300, # Adjust based on expected JSON size
                response_format={"type": "json_object"} # Request JSON output
            )
            
            response_content = response.choices[0].message.content
            logger.debug(f"ReplyClassifierAgent: LLM raw response: {response_content}")

            if not response_content:
                logger.error("ReplyClassifierAgent: LLM returned empty content.")
                return None

            try:
                classification_result = json.loads(response_content)
                # Validate the structure
                if not isinstance(classification_result, dict) or \
                   "category" not in classification_result or \
                   "summary" not in classification_result:
                    logger.error(f"ReplyClassifierAgent: LLM response missing mandatory fields 'category' or 'summary'. Response: {response_content}")
                    return None # Or a default error classification
                
                if classification_result["category"] not in REPLY_CATEGORIES:
                    logger.warning(f"ReplyClassifierAgent: LLM returned an unknown category '{classification_result['category']}'. Defaulting or flagging. Response: {response_content}")
                    # Optionally, remap or handle unknown categories. For now, accept it if LLM hallucinates a new one despite instructions.
                    # Or, be stricter:
                    # return {"category": "CANNOT_CLASSIFY_GIBBERISH", "summary": f"LLM returned unkown category: {classification_result['category']}", "extracted_info": {}}


                # Ensure extracted_info is a dict if present
                if "extracted_info" in classification_result and not isinstance(classification_result["extracted_info"], dict):
                    logger.warning(f"ReplyClassifierAgent: LLM 'extracted_info' is not a dict. Normalizing. Original: {classification_result['extracted_info']}")
                    classification_result["extracted_info"] = {} # Normalize to empty dict

                logger.info(f"ReplyClassifierAgent: Classified reply for lead '{lead_name if lead_name else 'Unknown'}' as '{classification_result.get('category')}'. Summary: '{classification_result.get('summary')}'")
                return classification_result

            except json.JSONDecodeError as e:
                logger.error(f"ReplyClassifierAgent: Failed to parse LLM JSON response: {e}. Response: {response_content}", exc_info=True)
                return None
            except Exception as e_parse: # Catch other potential errors during parsing/validation
                logger.error(f"ReplyClassifierAgent: Error processing LLM response content: {e_parse}. Response: {response_content}", exc_info=True)
                return None


        except APIError as e: # More specific OpenAI errors
            logger.error(f"ReplyClassifierAgent: OpenAI API error: {e.status_code} - {e.message}", exc_info=True)
            return None
        except Exception as e: # Catch-all for other issues like network problems
            logger.error(f"ReplyClassifierAgent: Unexpected error during LLM call: {e}", exc_info=True)
            return None
