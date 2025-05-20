# app/agents/campaign_generator.py

import time
import json
import os
from openai import OpenAI, APIError, AuthenticationError, RateLimitError, APIConnectionError, APITimeoutError
from tenacity import retry, stop_after_attempt, wait_random_exponential
from sqlalchemy.orm import Session # <--- IMPORTED Session

# Assuming your database CRUD functions are in app.db.database
# These functions will need to be updated to accept 'db: Session' as their first argument
from app.db.database import (
    get_campaign_by_id,
    get_icp_by_id as db_get_icp_by_id,
    get_offering_by_id as db_get_offering_by_id,
    create_campaign_step,
    update_campaign_ai_status,
    get_steps_for_campaign,
    delete_campaign_step # Ensure this function's signature is (db, step_id, organization_id)
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
SIMULATE_LLM_CALL = os.environ.get("SIMULATE_LLM_CALL", "False").lower() == "true"
LLM_MODEL = os.environ.get("CAMPAIGN_LLM_MODEL", "gpt-4-turbo-preview")
LLM_SIMULATION_DELAY = int(os.environ.get("LLM_SIMULATION_DELAY", 3))

# Initialize OpenAI client
client = None
if not SIMULATE_LLM_CALL:
    if OPENAI_API_KEY:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            logger.info("OpenAI client initialized successfully for campaign generation.")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
            client = None
    else:
        logger.error("OPENAI_API_KEY environment variable not set. Real LLM calls for campaign generation will fail.")

# --- Helper Functions ---

def _construct_llm_prompt(campaign_data: dict, icp_details: dict, offering_details: dict, num_steps: int) -> str:
    campaign_name = campaign_data.get('name', 'the campaign')
    campaign_description = campaign_data.get('description', '')

    icp_summary = "Generic B2B Professional."
    if icp_details:
        icp_name = icp_details.get('name', 'the target audience')
        icp_title_keywords = icp_details.get('title_keywords', [])
        icp_industry_keywords = icp_details.get('industry_keywords', [])
        icp_summary = f"The Ideal Customer Profile (ICP) is '{icp_name}'. "
        if icp_title_keywords: icp_summary += f"They likely hold titles such as: {', '.join(icp_title_keywords)}. "
        if icp_industry_keywords: icp_summary += f"They operate in industries like: {', '.join(icp_industry_keywords)}. "
        icp_summary += "Focus on their potential pain points, goals, and triggers."

    offering_summary = "Our valuable solution."
    if offering_details:
        offering_name = offering_details.get('name', 'our product/service')
        offering_desc = offering_details.get('description', 'a solution that provides significant value.')
        key_features = offering_details.get('key_features', [])
        pain_points_solved = offering_details.get('target_pain_points', [])
        cta = offering_details.get('call_to_action', 'explore a potential fit')

        offering_summary = f"The offering is '{offering_name}'. Description: {offering_desc}. "
        if key_features: offering_summary += f"Key features include: {', '.join(key_features)}. "
        if pain_points_solved: offering_summary += f"It solves pain points such as: {', '.join(pain_points_solved)}. "
        offering_summary += f"The goal is to invite them to '{cta}' if there's a mutual fit."

    prompt = f"""
    You are an expert Sales Development Representative (SDR) trained in the Sandler Selling System.
    Your mission is to craft a highly effective {num_steps}-step email outreach sequence for the campaign titled "{campaign_name}".
    {f"The campaign aims to: {campaign_description}" if campaign_description else ""}

    Target Audience (ICP): {icp_summary}
    Offering to Introduce: {offering_summary}

    Key Principles for this Sandler-Inspired Sequence: Focus on Pain, Build Rapport & Trust, Qualification, Mutual Agreement, Upfront Contract (implied), Confident Posture.

    Sequence Structure ({num_steps} steps):
    1.  Step 1 (Day 0): "Pattern Interrupt" & Pain Hypothesis. Subject: Intriguing, short, personalized. Body: Reference company/role (use {{{{company_name}}}}, {{{{lead_name}}}}, {{{{title}}}}). State common pain. Ask open-ended question. Keep short. Follow-up Angle: Pattern Interrupt / Initial Pain Probe
    2.  Step 2 (Delay ~2-3 days): Elaborate on Pain & Hint at Solution. Subject: Reference previous email or related pain. Body: Expand on pain or introduce related one. Briefly hint at solutions. Qualifying question. Follow-up Angle: Pain Deepening / Solution Tease
    3.  Step 3 (Delay ~2-3 days): Gentle Introduction of Company/Offering. Subject: Connect company to solving pain. Body: Briefly intro company and ONE core benefit for the pain. Offer low-friction next step. Follow-up Angle: Gentle Introduction / Value Snippet
    4.  Step 4 (Delay ~3-4 days): Social Proof / Credibility. Subject: Highlight result or client type. Body: Share brief, anonymous example or compelling statistic. Benefit-oriented. Follow-up Angle: Credibility Build / Social Proof
    5.  Step 5 (Delay ~3-4 days): Focus on a Different Angle/Benefit or "What If". Subject: New angle or thought-provoking question. Body: Touch on secondary pain/benefit, or "what if" scenario. Ask if it resonates. Follow-up Angle: Alternative Value / Re-engagement
    6.  Step 6 (Delay ~3-4 days): The "No-Pressure" Meeting Ask. Subject: Clear, low-pressure CTA. Body: Acknowledge they're busy. Propose brief, specific timeframe for exploratory call (emphasize "exploratory," "mutual fit," "no obligation"). Follow-up Angle: Low-Pressure Meeting Invitation
    7.  Step 7 (Delay ~4-5 days): "Should I Stay or Should I Go?" (Polite Check-in). Subject: Simple check-in. Body: Politely ask if they've considered previous messages or if priorities changed. Reiterate not wasting time. Follow-up Angle: Priority Check / Respectful Nudge
    8.  Step 8 (Delay ~4-5 days): "Referral or Right Contact" (If no negative reply). Subject: Question about best contact. Body: Politely ask if they're the right person or for a referral. Follow-up Angle: Right Contact / Referral Request
    9.  Step 9 (Delay ~5-7 days): "Polite Breakup" (Closing the Loop). Subject: Closing loop. Body: Assume now isn't right time. Stop active outreach for now. Wish them well. Positive final impression. Follow-up Angle: Polite Breakup / Closing Loop

    Output Requirements:
    - Provide output as a single, valid JSON list of objects. No explanatory text before or after.
    - Each object must have keys: "step_number" (int), "delay_days" (int), "subject_template" (str), "body_template" (str), "follow_up_angle" (str).
    - Use placeholders like {{{{lead_name}}}}, {{{{company_name}}}}, {{{{title}}}}, {{{{industry}}}}. Newlines in body_template as \\n.

    Example (DO NOT just repeat this example):
    {{
        "step_number": 1, "delay_days": 0,
        "subject_template": "Question about {{{{company_name}}}}'s approach to [Pain Area]",
        "body_template": "Hi {{{{lead_name}}},\\n\\nNoticed {{{{company_name}}}} is a leader in {{{{industry}}}}. Often, companies like yours face challenges with [Specific Pain Point].\\n\\nIs this something your team is currently exploring?\\n\\nBest,\\n[Your Name]",
        "follow_up_angle": "Pattern Interrupt / Initial Pain Probe"
    }}
    ---
    GENERATE THE FULL {num_steps}-STEP EMAIL SEQUENCE JSON NOW:
    """
    return prompt.strip()


@retry(wait=wait_random_exponential(min=1, max=30), stop=stop_after_attempt(3)) # Reduced max wait
def _call_llm_api_with_retry(prompt: str, campaign_id: int) -> str:
    if SIMULATE_LLM_CALL:
        logger.info(f"AI AGENT (LLM SIM): Simulation ON for campaign {campaign_id}.")
        time.sleep(LLM_SIMULATION_DELAY)
        sim_steps = []
        for i in range(1, DEFAULT_NUM_STEPS + 1):
            sim_steps.append({
                "step_number": i, "delay_days": i,
                "subject_template": f"Simulated Subject {i} for {{{{lead_name}}}} at {{{{company_name}}}}",
                "body_template": f"Simulated body {i} for {{{{lead_name}}}},\\nThis is a test.\\nThanks.",
                "follow_up_angle": f"Simulated Angle {i}"
            })
        return json.dumps(sim_steps)

    logger.info(f"AI AGENT (LLM REAL): Calling OpenAI API for campaign {campaign_id} with model {LLM_MODEL}.")
    if not client:
        logger.error("AI AGENT (LLM REAL): OpenAI client not initialized. Cannot make API call.")
        raise ConnectionError("OpenAI client not initialized. API key might be missing or invalid.")

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert B2B sales assistant specialized in writing concise, personalized cold outreach email sequences following the Sandler Selling System principles."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
        )
        llm_output_str = response.choices[0].message.content
        logger.debug(f"AI AGENT (LLM REAL): Raw LLM response received for campaign {campaign_id}.")
        
        cleaned_output = llm_output_str.strip() if llm_output_str else ""
        if cleaned_output.startswith("```json"): cleaned_output = cleaned_output[7:]
        if cleaned_output.startswith("```"): cleaned_output = cleaned_output[3:]
        if cleaned_output.endswith("```"): cleaned_output = cleaned_output[:-3]
        llm_output_str = cleaned_output.strip()
        
        logger.info(f"AI AGENT (LLM REAL): Cleaned LLM response (first 300 chars): {llm_output_str[:300]}...")
        if not llm_output_str:
            logger.warning(f"AI AGENT (LLM REAL): LLM returned empty content for campaign {campaign_id}.")
            return "[]"
        return llm_output_str

    except AuthenticationError as e: logger.error(f"OpenAI Auth Error: {e}"); raise
    except RateLimitError as e: logger.warning(f"OpenAI Rate Limit Exceeded, will retry: {e}"); raise
    except APIConnectionError as e: logger.warning(f"OpenAI Connection Error, will retry: {e}"); raise
    except APITimeoutError as e: logger.warning(f"OpenAI Request Timed Out, will retry: {e}"); raise
    except APIError as e: logger.error(f"OpenAI API Error (status {e.status_code}): {e.message}"); raise
    except Exception as e:
        logger.error(f"Unexpected error during OpenAI API call for campaign {campaign_id}: {e}", exc_info=True)
        raise


def _parse_llm_response(response_str: str, campaign_id: int) -> list:
    if not response_str:
        logger.error(f"AI AGENT: LLM response string is empty for campaign {campaign_id}.")
        return []
    try:
        parsed_json = json.loads(response_str)
        step_list = parsed_json if isinstance(parsed_json, list) else (parsed_json.get("steps") if isinstance(parsed_json.get("steps"), list) else None)

        if step_list is None:
            logger.error(f"AI AGENT: LLM response for campaign {campaign_id} is not a list or dict with 'steps' list. Response: {response_str[:500]}")
            return []

        validated_steps = []
        required_keys = {"step_number", "delay_days", "subject_template", "body_template"}
        
        for i, step_data in enumerate(step_list):
            if not isinstance(step_data, dict):
                logger.warning(f"AI AGENT: Step {i+1} (LLM Index) for campaign {campaign_id} is not a dictionary. Skipping. Data: {step_data}")
                continue
            
            if not required_keys.issubset(step_data.keys()):
                logger.warning(f"AI AGENT: Step {i+1} for campaign {campaign_id} missing keys: {required_keys - set(step_data.keys())}. Skipping. Data: {step_data}")
                continue
            
            try:
                step_data["step_number"] = int(step_data["step_number"])
                step_data["delay_days"] = int(step_data["delay_days"])
                if not all(isinstance(step_data[k], str) for k in ["subject_template", "body_template"]):
                    raise ValueError("Subject or body template is not a string.")
                step_data["follow_up_angle"] = str(step_data.get("follow_up_angle", f"AI Step {step_data['step_number']}")).strip()
                if not step_data["follow_up_angle"]: step_data["follow_up_angle"] = f"AI Step {step_data['step_number']}" # Ensure not empty

            except (ValueError, TypeError) as ve:
                logger.warning(f"AI AGENT: Step {i+1} for campaign {campaign_id} has invalid data types ({ve}). Skipping. Data: {step_data}")
                continue
            validated_steps.append(step_data)
        
        if not validated_steps and step_list: logger.error(f"AI AGENT: No valid steps found after parsing for campaign {campaign_id}.")
        elif validated_steps and len(validated_steps) < len(step_list): logger.warning(f"AI AGENT: Some steps invalid/skipped for campaign {campaign_id}.")
        return validated_steps
        
    except json.JSONDecodeError as e:
        logger.error(f"AI AGENT: Failed to parse LLM JSON for campaign {campaign_id}: {e}. Response: {response_str[:500]}")
        return []
    except Exception as e:
        logger.error(f"AI AGENT: Unexpected error parsing LLM response for campaign {campaign_id}: {e}", exc_info=True)
        return []


def _clear_existing_steps(db: Session, campaign_id: int, organization_id: int):
    """Clears existing steps for a campaign. Assumes db session is provided."""
    existing_steps = get_steps_for_campaign(db=db, campaign_id=campaign_id, organization_id=organization_id)
    if existing_steps:
        logger.info(f"AI AGENT: Clearing {len(existing_steps)} existing steps for campaign {campaign_id}.")
        for step in existing_steps:
            # Ensure delete_campaign_step signature is (db, step_id, organization_id)
            if not delete_campaign_step(db=db, step_id=step['id'], organization_id=organization_id):
                logger.error(f"AI AGENT: Failed to delete step ID {step['id']} for campaign {campaign_id}.")
                # Decide if you want to raise an error here or just log and continue


def generate_campaign_steps(db_session_factory, campaign_id: int, organization_id: int, force_regeneration: bool = False):
    """
    Generates email steps for a given campaign using an LLM.
    Manages its own database session via db_session_factory.
    """
    db: Optional[Session] = None # Initialize db to None
    try:
        db = next(db_session_factory()) # Get a new session
        logger.info(f"AI AGENT: Task received for campaign_id: {campaign_id}, org_id: {organization_id}, force: {force_regeneration} with DB session.")

        campaign_data = get_campaign_by_id(db=db, campaign_id=campaign_id, organization_id=organization_id)
        if not campaign_data:
            logger.error(f"AI AGENT: Campaign {campaign_id} not found for org {organization_id}. Aborting.")
            return

        if not force_regeneration and campaign_data.get("ai_status") == "completed":
            existing_steps = get_steps_for_campaign(db=db, campaign_id=campaign_id, organization_id=organization_id)
            if existing_steps:
                logger.info(f"AI AGENT: Campaign {campaign_id} 'completed' with steps. Skipping unless forced.")
                return
            logger.warning(f"AI AGENT: Campaign {campaign_id} 'completed' but no steps found. Regenerating.")
        
        if campaign_data.get("ai_status") == "generating" and not force_regeneration:
            logger.warning(f"AI AGENT: Campaign {campaign_id} already 'generating'. Skipping duplicate task.")
            return
        
        if force_regeneration:
            _clear_existing_steps(db=db, campaign_id=campaign_id, organization_id=organization_id)
            # db.commit() might be needed here if _clear_existing_steps doesn't commit deletions

        if not SIMULATE_LLM_CALL and not client:
            logger.error(f"AI AGENT: OpenAI client not available. Cannot generate for campaign {campaign_id}.")
            update_campaign_ai_status(db=db, campaign_id=campaign_id, organization_id=organization_id, ai_status="failed_config")
            db.commit()
            return

        update_campaign_ai_status(db=db, campaign_id=campaign_id, organization_id=organization_id, ai_status="generating")
        db.commit() # Commit 'generating' status immediately

        # --- Main generation logic ---
        try:
            icp_details = db_get_icp_by_id(db=db, icp_id=campaign_data["icp_id"], organization_id=organization_id) if campaign_data.get("icp_id") else None
            if campaign_data.get("icp_id") and not icp_details: logger.warning(f"AI AGENT: ICP {campaign_data['icp_id']} not found.")
            
            offering_details = db_get_offering_by_id(db=db, offering_id=campaign_data["offering_id"], organization_id=organization_id) if campaign_data.get("offering_id") else None
            if campaign_data.get("offering_id") and not offering_details: logger.warning(f"AI AGENT: Offering {campaign_data['offering_id']} not found.")

            prompt = _construct_llm_prompt(campaign_data, icp_details or {}, offering_details or {}, DEFAULT_NUM_STEPS)
            llm_response_str = _call_llm_api_with_retry(prompt, campaign_id)
            
            generated_steps_data = _parse_llm_response(llm_response_str, campaign_id)
            if not generated_steps_data:
                raise ValueError(f"No valid steps parsed from LLM for campaign {campaign_id}.")
            
            logger.info(f"AI AGENT: LLM processed {len(generated_steps_data)} valid steps for campaign {campaign_id}.")
            steps_saved_count = 0
            for step_data in generated_steps_data:
                if create_campaign_step(
                    db=db, campaign_id=campaign_id, organization_id=organization_id,
                    step_number=step_data["step_number"], delay_days=step_data["delay_days"],
                    subject_template=step_data["subject_template"], body_template=step_data["body_template"],
                    follow_up_angle=step_data["follow_up_angle"], is_ai_crafted=True
                ): steps_saved_count += 1
                else: logger.error(f"AI AGENT: CRITICAL - Failed to save step data to DB: {step_data} for campaign {campaign_id}.")
            
            if steps_saved_count == 0 and generated_steps_data:
                raise ValueError("No steps saved to DB despite LLM generating valid data.")
            
            final_status = "completed"
            if steps_saved_count < len(generated_steps_data) and steps_saved_count > 0: final_status = "completed_partial"
            elif steps_saved_count == 0: final_status = "failed_llm_empty" # Or failed_db_save
            
            logger.info(f"AI AGENT: Final status for campaign {campaign_id}: {final_status}. Saved {steps_saved_count} steps.")
            update_campaign_ai_status(db=db, campaign_id=campaign_id, organization_id=organization_id, ai_status=final_status)
            db.commit() # Commit all steps and final status

        except Exception as generation_error: # Catch errors from LLM call, parsing, or DB saving steps
            logger.error(f"AI AGENT: Error during LLM/DB step processing for campaign {campaign_id}: {generation_error}", exc_info=True)
            db.rollback() # Rollback any partial step creations
            update_campaign_ai_status(db=db, campaign_id=campaign_id, organization_id=organization_id, ai_status="failed")
            db.commit() # Commit 'failed' status

    except Exception as outer_error: # Catch any other unexpected errors (e.g., DB session issue)
        logger.error(f"AI AGENT: Top-level unhandled error in generate_campaign_steps for campaign {campaign_id}: {outer_error}", exc_info=True)
        if db and db.is_active: # Check if db is valid and session is active
            db.rollback() # Rollback any pending changes if an error occurred before commit
            # Consider if status update is possible/safe here
    finally:
        if db: # Check if db was successfully initialized
            db.close()
            logger.debug(f"AI AGENT: DB session closed for campaign {campaign_id} task.")
