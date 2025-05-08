# app/agents/campaign_generator.py

import time
import json
import os
from openai import OpenAI, APIError, AuthenticationError, RateLimitError, APIConnectionError, APITimeoutError # Import specific errors
from tenacity import retry, stop_after_attempt, wait_random_exponential # For retrying API calls

# Assuming your database CRUD functions are in app.db.database
from app.db.database import (
    get_campaign_by_id,
    get_icp_by_id as db_get_icp_by_id,
    get_offering_by_id as db_get_offering_by_id,
    create_campaign_step,
    update_campaign_ai_status,
    get_steps_for_campaign,
    delete_campaign_step
)

# Assuming you have a logger configured
try:
    from app.utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')

# --- Agent Configuration ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

DEFAULT_NUM_STEPS = 9
SIMULATE_LLM_CALL = False
LLM_MODEL = "gpt-4-turbo-preview"
# LLM_MODEL = "gpt-3.5-turbo-0125" # Cheaper/faster for iteration
LLM_SIMULATION_DELAY = 3

# Initialize OpenAI client
client = None
if not SIMULATE_LLM_CALL:
    if OPENAI_API_KEY:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            logger.info("OpenAI client initialized successfully for campaign generation.")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
            client = None # Ensure client is None if init fails
    else:
        logger.error("OPENAI_API_KEY environment variable not set. Real LLM calls for campaign generation will fail.")

# --- Helper Functions ---

def _construct_llm_prompt(campaign_data: dict, icp_details: dict, offering_details: dict, num_steps: int) -> str:
    # ... (This function remains the same as provided in the previous consolidated version)
    campaign_name = campaign_data.get('name', 'the campaign')
    campaign_description = campaign_data.get('description', '')

    icp_summary = "Generic B2B Professional." # Default if no ICP
    if icp_details:
        icp_name = icp_details.get('name', 'the target audience')
        icp_title_keywords = icp_details.get('title_keywords', [])
        icp_industry_keywords = icp_details.get('industry_keywords', [])
        icp_summary = f"The Ideal Customer Profile (ICP) is '{icp_name}'. "
        if icp_title_keywords:
            icp_summary += f"They likely hold titles such as: {', '.join(icp_title_keywords)}. "
        if icp_industry_keywords:
            icp_summary += f"They operate in industries like: {', '.join(icp_industry_keywords)}. "
        icp_summary += "Focus on understanding their potential pain points, business goals, and what triggers would make them consider a solution like ours."

    offering_summary = "Our valuable solution." # Default if no offering
    if offering_details:
        offering_name = offering_details.get('name', 'our product/service')
        offering_desc = offering_details.get('description', 'a solution that provides significant value.')
        key_features = offering_details.get('key_features', [])
        pain_points_solved = offering_details.get('target_pain_points', [])
        cta = offering_details.get('call_to_action', 'explore a potential fit')

        offering_summary = f"The offering is '{offering_name}'. Description: {offering_desc}. "
        if key_features:
            offering_summary += f"Key features include: {', '.join(key_features)}. "
        if pain_points_solved:
            offering_summary += f"It's designed to solve common pain points such as: {', '.join(pain_points_solved)}. "
        offering_summary += f"The ultimate goal of this sequence is to invite them to '{cta}' if there's a mutual fit, or to get a clear 'no' if not."

    prompt = f"""
    You are an expert Sales Development Representative (SDR) trained in the Sandler Selling System.
    Your mission is to craft a highly effective {num_steps}-step email outreach sequence for the campaign titled "{campaign_name}".
    {f"The campaign aims to: {campaign_description}" if campaign_description else ""}

    Target Audience (ICP):
    {icp_summary}

    Offering to Introduce:
    {offering_summary}

    Key Principles for this Sandler-Inspired Sequence:
    - Focus on Pain: Uncover and gently agitate relevant pain points. Don't lead with your solution immediately.
    - Build Rapport & Trust: Be human, empathetic, and curious. Your tone should be professional yet approachable.
    - Qualification: Each step should subtly qualify their interest and determine if they experience the pains your offering solves.
    - Mutual Agreement: Emails should aim for small agreements or clear next steps (even if it's a "no").
    - Upfront Contract (implied): Be clear about the purpose of the outreach without being demanding or pushy.
    - Posture: Confident, consultative, and a peer. You are not needy; you are exploring if there's a way to help them achieve their goals or solve their problems.

    Sequence Structure ({num_steps} steps):
    1.  **Step 1 (Day 0): The "Pattern Interrupt" & Pain Hypothesis.**
        *   Subject: Intriguing, short, personalized. Avoid generic marketing language.
        *   Body: Briefly reference something specific about their company/role (use placeholders like {{{{company_name}}}}, {{{{lead_name}}}}, {{{{title}}}}). State a common pain point relevant to their ICP and your offering. Ask a simple, open-ended question related to that pain. Keep it very short.
        *   Follow-up Angle: Pattern Interrupt / Initial Pain Probe
    2.  **Step 2 (Delay ~2-3 days): Elaborate on Pain & Hint at Solution.**
        *   Subject: Reference previous email or a related pain point.
        *   Body: Expand slightly on the pain or introduce a related one. Briefly hint that there are ways to address it (without detailing your solution yet). Another qualifying question.
        *   Follow-up Angle: Pain Deepening / Solution Tease
    3.  **Step 3 (Delay ~2-3 days): Gentle Introduction of Company/Offering.**
        *   Subject: Connect your company to solving the discussed pain.
        *   Body: Briefly introduce your company and ONE core benefit of your offering that directly addresses the pain. Offer a very low-friction next step (e.g., a short article, a quick example, a relevant statistic).
        *   Follow-up Angle: Gentle Introduction / Value Snippet
    4.  **Step 4 (Delay ~3-4 days): Social Proof / Credibility.**
        *   Subject: Highlight a result or a type of client you help.
        *   Body: Share a brief, anonymous example or compelling statistic of how you've helped similar companies overcome the pain. Keep it concise and benefit-oriented.
        *   Follow-up Angle: Credibility Build / Social Proof
    5.  **Step 5 (Delay ~3-4 days): Focus on a Different Angle/Benefit or "What If".**
        *   Subject: New angle or thought-provoking question.
        *   Body: Touch on a secondary pain point or benefit, or pose a "what if" scenario related to solving their problems. Ask if this resonates or is a priority.
        *   Follow-up Angle: Alternative Value / Re-engagement
    6.  **Step 6 (Delay ~3-4 days): The "No-Pressure" Meeting Ask.**
        *   Subject: Clear, but low-pressure call to action.
        *   Body: Acknowledge they are busy. Propose a brief, specific timeframe for a quick exploratory call to see if there's a mutual fit – emphasize "exploratory," "mutual fit," and "no obligation."
        *   Follow-up Angle: Low-Pressure Meeting Invitation
    7.  **Step 7 (Delay ~4-5 days): The "Should I Stay or Should I Go?" (Polite Check-in).**
        *   Subject: Simple check-in, e.g., "Following up - {{{{lead_name}}}}" or "Quick check-in".
        *   Body: Politely ask if they've had a chance to consider your previous messages or if their priorities lie elsewhere. Reiterate you don't want to waste their time.
        *   Follow_up_Angle: Priority Check / Respectful Nudge
    8.  **Step 8 (Delay ~4-5 days): The "Referral or Right Contact" (If applicable & no negative reply).**
        *   Subject: Question about best contact, e.g., "Right person for [topic] at {{{{company_name}}}}?"
        *   Body: If no response, politely ask if they are the right person to discuss [topic related to offering] or if they could point you to a colleague who handles such matters.
        *   Follow-up Angle: Right Contact / Referral Request
    9.  **Step 9 (Delay ~5-7 days): The "Polite Breakup" (Closing the Loop).**
        *   Subject: Closing the loop, e.g., "One last try on this" or "Moving on for now, {{{{lead_name}}}}".
        *   Body: State that you assume now isn't the right time or they aren't interested in discussing further. Mention you'll stop active outreach on this specific topic for now, but wish them well. Keep it professional and leave a positive final impression.
        *   Follow-up Angle: Polite Breakup / Closing Loop

    Output Requirements:
    - Provide the output as a single, valid JSON list of objects. Do not include any explanatory text before or after the JSON list itself.
    - Each object must represent an email step and have the following string keys: "step_number" (as int), "delay_days" (as int), "subject_template", "body_template", "follow_up_angle".
    - Ensure subject_template and body_template use placeholders like {{{{lead_name}}}}, {{{{company_name}}}}, {{{{title}}}}, {{{{industry}}}}. You can introduce other relevant placeholders if they naturally fit (e.g., {{{{pain_point_example}}}}).
    - Body templates should be well-formatted with newlines (use \\n for JSON string).

    Example of a single step object structure (DO NOT just repeat this example, generate unique content):
    {{
        "step_number": 1,
        "delay_days": 0,
        "subject_template": "Question about {{{{company_name}}}}'s approach to [Pain Area]",
        "body_template": "Hi {{{{lead_name}}}},\\n\\nNoticed {{{{company_name}}}} is a leader in the {{{{industry}}}} space. Often, companies like yours face challenges with [Specific Pain Point related to ICP/Offering].\\n\\nIs this something your team is currently exploring solutions for?\\n\\nBest regards,\\n[Your Name]",
        "follow_up_angle": "Pattern Interrupt / Initial Pain Probe"
    }}
    ---
    GENERATE THE FULL {num_steps}-STEP EMAIL SEQUENCE JSON NOW:
    """
    return prompt.strip()

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(3))
def _call_llm_api_with_retry(prompt: str, campaign_id: int) -> str:
    """
    Calls the LLM API with retry logic.
    This adapts the retry logic from your EmailCraftingAgent.
    """
    if SIMULATE_LLM_CALL:
        logger.info(f"AI AGENT (LLM SIM): Simulation mode ON for campaign {campaign_id}. Returning simulated data.")
        time.sleep(LLM_SIMULATION_DELAY)
        # ... (Simplified simulation for brevity, use your more detailed one if preferred)
        return json.dumps([{"step_number": 1, "delay_days": 0, "subject_template": "Sim", "body_template": "Sim", "follow_up_angle": "Sim"}])

    logger.debug(f"AI AGENT (LLM REAL): Calling OpenAI API for campaign {campaign_id} with model {LLM_MODEL}. Retryable. Prompt length: {len(prompt)}")
    if not client:
        logger.error("AI AGENT (LLM REAL): OpenAI client not initialized. Cannot make API call.")
        # This will cause tenacity to retry if it's a transient issue,
        # but if client is permanently None, it will eventually fail after retries.
        raise ConnectionError("OpenAI client not initialized. API key might be missing.")

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert B2B sales assistant specialized in writing concise, personalized cold outreach email sequences following the Sandler Selling System principles."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
            # response_format={"type": "json_object"}, # Enable if prompt is robust for JSON
            # max_tokens=3500 # Optional: to control output length/cost
        )
        llm_output_str = response.choices[0].message.content
        logger.info(f"AI AGENT (LLM REAL): Raw LLM response (first 300 chars): {llm_output_str[:300]}...")
        
        # Clean up potential markdown
        if llm_output_str:
            cleaned_output = llm_output_str.strip()
            if cleaned_output.startswith("```json"):
                cleaned_output = cleaned_output[7:].strip()
                if cleaned_output.endswith("```"):
                    cleaned_output = cleaned_output[:-3].strip()
                llm_output_str = cleaned_output
            elif cleaned_output.startswith("```"):
                 cleaned_output = cleaned_output[3:].strip()
                 if cleaned_output.endswith("```"):
                    cleaned_output = cleaned_output[:-3].strip()
                 llm_output_str = cleaned_output
        
        logger.info(f"AI AGENT (LLM REAL): Cleaned LLM response (first 300 chars): {llm_output_str[:300]}...")
        if not llm_output_str: # If response becomes empty after stripping
            logger.warning(f"AI AGENT (LLM REAL): LLM returned an empty content string for campaign {campaign_id}.")
            # Return empty JSON list string to be handled by parser as "no valid steps"
            return "[]"
        return llm_output_str

    except AuthenticationError as e: logger.error(f"OpenAI Auth Error (check API key): {e}"); raise
    except RateLimitError as e: logger.error(f"OpenAI Rate Limit Exceeded: {e}"); raise # Tenacity will retry
    except APIConnectionError as e: logger.error(f"OpenAI Connection Error: {e}"); raise # Tenacity will retry
    except APITimeoutError as e: logger.error(f"OpenAI Request Timed Out: {e}"); raise # Tenacity will retry
    except APIError as e: logger.error(f"OpenAI API Error (non-transient): {e}"); raise # May or may not retry depending on status code
    except Exception as e: # Catch any other unexpected errors during the API call
        logger.error(f"Unexpected error during OpenAI API call for campaign {campaign_id}: {e}", exc_info=True)
        raise # Re-raise to be handled by the main try-except in generate_campaign_steps

def _parse_llm_response(response_str: str, campaign_id: int) -> list:
    # ... (This function remains the same as provided in the previous consolidated version)
    if not response_str:
        logger.error(f"AI AGENT: LLM response string is empty for campaign {campaign_id}.")
        return []
    try:
        # Attempt to load the JSON. It might be an empty list string "[]".
        parsed_json = json.loads(response_str)

        if isinstance(parsed_json, dict) and "steps" in parsed_json and isinstance(parsed_json["steps"], list) :
            step_list = parsed_json["steps"]
        elif isinstance(parsed_json, list):
            step_list = parsed_json
        else:
            logger.error(f"AI AGENT: LLM response for campaign {campaign_id} is not a list or a dict with a 'steps' list. Response: {response_str[:500]}")
            return []

        validated_steps = []
        # Make follow_up_angle optional from LLM, but ensure it exists for DB
        required_keys = {"step_number", "delay_days", "subject_template", "body_template"}
        
        for i, step_data in enumerate(step_list):
            if not isinstance(step_data, dict):
                logger.warning(f"AI AGENT: Step {i+1} in LLM response for campaign {campaign_id} is not a dictionary. Skipping. Data: {step_data}")
                continue
            
            missing_keys = required_keys - set(step_data.keys())
            if missing_keys:
                logger.warning(f"AI AGENT: Step {i+1} for campaign {campaign_id} is missing required keys: {missing_keys}. Skipping. Step data: {step_data}")
                continue
            
            try:
                step_data["step_number"] = int(step_data["step_number"])
                step_data["delay_days"] = int(step_data["delay_days"])
                if not isinstance(step_data["subject_template"], str) or not isinstance(step_data["body_template"], str):
                    raise ValueError("Subject or body template is not a string.")
                
                # Handle follow_up_angle: make it optional from LLM, default if not present
                if "follow_up_angle" not in step_data or not step_data["follow_up_angle"]: # Check if key exists and is not empty
                    step_data["follow_up_angle"] = f"AI Generated Step {step_data['step_number']}" # Default angle
                elif not isinstance(step_data["follow_up_angle"], str):
                    step_data["follow_up_angle"] = str(step_data["follow_up_angle"])


            except ValueError as ve:
                logger.warning(f"AI AGENT: Step {i+1} for campaign {campaign_id} has invalid data types ({ve}). Skipping. Step data: {step_data}")
                continue

            validated_steps.append(step_data)
        
        if not validated_steps and step_list:
             logger.error(f"AI AGENT: No valid steps found after parsing LLM response for campaign {campaign_id}, though LLM provided data.")
        elif validated_steps and len(validated_steps) < len(step_list):
             logger.warning(f"AI AGENT: Some steps were invalid and skipped during LLM response parsing for campaign {campaign_id}.")

        return validated_steps
        
    except json.JSONDecodeError as e:
        logger.error(f"AI AGENT: Failed to parse LLM JSON response for campaign {campaign_id}: {e}. Response snippet: {response_str[:500]}")
        return []
    except Exception as e:
        logger.error(f"AI AGENT: Unexpected error parsing LLM response for campaign {campaign_id}: {e}", exc_info=True)
        return []


def _clear_existing_steps(campaign_id: int, organization_id: int):
    # ... (This function remains the same)
    existing_steps = get_steps_for_campaign(campaign_id, organization_id)
    if existing_steps:
        logger.info(f"AI AGENT: Clearing {len(existing_steps)} existing steps for campaign {campaign_id} before regeneration.")
        all_deleted = True
        for step in existing_steps:
            if not delete_campaign_step(step['id'], organization_id):
                all_deleted = False
                logger.error(f"AI AGENT: Failed to delete step ID {step['id']} for campaign {campaign_id}.")
        if not all_deleted: # This is more of a warning, as cascade might still work or some steps might be stuck
            logger.warning(f"AI AGENT: Attempted to delete existing steps for campaign {campaign_id}, some deletions may have failed at DB function level.")


def generate_campaign_steps(campaign_id: int, organization_id: int, force_regeneration: bool = False):
    # ... (This function remains largely the same, but calls _call_llm_api_with_retry)
    logger.info(f"AI AGENT: Task received for campaign_id: {campaign_id}, org_id: {organization_id}, force_regeneration: {force_regeneration}")

    campaign_data = get_campaign_by_id(campaign_id=campaign_id, organization_id=organization_id)
    if not campaign_data:
        logger.error(f"AI AGENT: Campaign {campaign_id} not found for org {organization_id}. Aborting generation.")
        return

    if not force_regeneration:
        current_ai_status = campaign_data.get("ai_status")
        if current_ai_status == "completed":
            existing_steps = get_steps_for_campaign(campaign_id, organization_id)
            if existing_steps:
                logger.info(f"AI AGENT: Campaign {campaign_id} steps already 'completed'. Skipping generation unless forced.")
                return
            else: # Status is completed but no steps, unusual, so proceed
                logger.warning(f"AI AGENT: Campaign {campaign_id} 'completed' but no steps found. Proceeding with generation.")
        elif current_ai_status == "generating": # Avoid race conditions
            logger.warning(f"AI AGENT: Campaign {campaign_id} generation already 'generating'. Skipping duplicate task.")
            return
    
    if force_regeneration:
        _clear_existing_steps(campaign_id, organization_id)

    if not SIMULATE_LLM_CALL and not client: # Check again before critical operation
        logger.error(f"AI AGENT: OpenAI client not available. Cannot generate steps for campaign {campaign_id}.")
        update_campaign_ai_status(campaign_id=campaign_id, organization_id=organization_id, ai_status="failed_config")
        return

    # Set status to generating
    if not update_campaign_ai_status(campaign_id=campaign_id, organization_id=organization_id, ai_status="generating"):
        logger.error(f"AI AGENT: Failed to update campaign {campaign_id} status to 'generating'. Aborting.")
        return

    try:
        icp_details = None
        if campaign_data.get("icp_id"):
            icp_details = db_get_icp_by_id(icp_id=campaign_data["icp_id"], organization_id=organization_id)
            if not icp_details: logger.warning(f"AI AGENT: ICP {campaign_data['icp_id']} not found. Using generic ICP profile for prompt.")
        
        offering_details = None
        if campaign_data.get("offering_id"):
            offering_details = db_get_offering_by_id(offering_id=campaign_data["offering_id"], organization_id=organization_id)
            if not offering_details: logger.warning(f"AI AGENT: Offering {campaign_data['offering_id']} not found. Using generic offering profile for prompt.")

        num_steps_to_generate = DEFAULT_NUM_STEPS # Could be made dynamic later from campaign_data
        prompt = _construct_llm_prompt(campaign_data, icp_details, offering_details, num_steps_to_generate)
        
        # Call LLM with retry
        llm_response_str = _call_llm_api_with_retry(prompt, campaign_id) # MODIFIED CALL
        
        if not llm_response_str: # Should not happen if retry exhausted and raised, but good check
            raise ValueError("LLM API call (with retries) returned an empty or failed response.")

        generated_steps_data = _parse_llm_response(llm_response_str, campaign_id)
        if not generated_steps_data:
            # If LLM consistently returns bad format or empty content after retries, this will be hit
            raise ValueError(f"Failed to parse any valid steps from LLM response after retries for campaign {campaign_id}.")
        
        logger.info(f"AI AGENT: LLM processed and parsed {len(generated_steps_data)} valid steps for campaign {campaign_id}.")

        steps_saved_count = 0
        for step_data in generated_steps_data:
            created_step = create_campaign_step(
                campaign_id=campaign_id, organization_id=organization_id,
                step_number=step_data["step_number"], delay_days=step_data["delay_days"],
                subject_template=step_data["subject_template"], body_template=step_data["body_template"],
                follow_up_angle=step_data.get("follow_up_angle", f"AI Step {step_data['step_number']}"),
                is_ai_crafted=True
            )
            if created_step:
                steps_saved_count += 1
            else: # This is critical if a validated step fails to save
                logger.error(f"AI AGENT: CRITICAL - Failed to save validated step data to DB: {step_data} for campaign {campaign_id}.")
        
        if steps_saved_count == 0 and len(generated_steps_data) > 0:
            # This means LLM gave data, parsing was ok, but DB save failed for all.
            raise ValueError("No steps were saved to DB despite LLM generating valid data.")
        
        final_status = "completed"
        if steps_saved_count < len(generated_steps_data) and steps_saved_count > 0 :
            final_status = "completed_partial"
            logger.warning(f"AI AGENT: Saved {steps_saved_count}/{len(generated_steps_data)} steps for campaign {campaign_id}.")
        elif steps_saved_count == len(generated_steps_data) and steps_saved_count > 0: # All steps saved
             logger.info(f"AI AGENT: Successfully generated and saved all {steps_saved_count} steps for campaign {campaign_id}.")
        elif steps_saved_count == 0 and not generated_steps_data: # No steps from LLM
            logger.warning(f"AI AGENT: LLM did not return any parsable steps for campaign {campaign_id}. Marking as failed.")
            final_status = "failed_llm_empty" # More specific status
        
        update_campaign_ai_status(campaign_id=campaign_id, organization_id=organization_id, ai_status=final_status)

    except Exception as e: # This catches errors from _call_llm_api_with_retry if all retries fail
        logger.error(f"AI AGENT: Unhandled error or retry exhaustion during step generation for campaign_id {campaign_id}: {e}", exc_info=True)
        update_campaign_ai_status(campaign_id=campaign_id, organization_id=organization_id, ai_status="failed")
