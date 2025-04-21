# app/agents/icp_matcher.py

from typing import Dict, Any, List # Added List
from app.utils.logger import logger
import re

# --- Import database module ---
# Make sure database.py is in app/db/ and has get_icp_by_organization_id
from app.db import database

class ICPMatcherAgent:
    def __init__(self):
        # No longer store hardcoded ICP criteria here
        logger.info("ICPMatcherAgent initialized.")
        # Initialization logic if needed (e.g., loading models)
        pass

    def match(self, enriched_lead_data: Dict[str, Any], organization_id: int) -> float: # organization_id is now required
        """
        Compares enriched lead data against the organization's specific ICP fetched from the DB.
        Returns a match score (0.0 to 1.0).
        """
        email = enriched_lead_data.get('email', 'N/A')
        if not organization_id:
            logger.error(f"Organization ID missing for ICP match attempt on {email}. Cannot proceed.")
            return 0.0 # Cannot match without knowing which ICP to use

        logger.info(f"Attempting ICP match for: {email} (Org: {organization_id})")

        # --- Fetch ICP Definition from Database ---
        icp_to_use = database.get_icp_by_organization_id(organization_id)

        if not icp_to_use:
            logger.warning(f"No ICP definition found in DB for Org ID: {organization_id}. Returning 0 match score.")
            return 0.0 # Cannot match if no ICP is defined for this org

        logger.debug(f"Using fetched ICP definition for Org {organization_id}: {icp_to_use}")

        # --- Initialize Scoring ---
        max_possible_score = 0.0
        achieved_score = 0.0
        reasons = []

        # --- Scoring Logic using fetched icp_to_use ---
        # Get lead data safely, converting to lowercase string for comparison
        lead_industry = str(enriched_lead_data.get('industry', '')).lower()
        lead_title = str(enriched_lead_data.get('title', '')).lower()
        lead_size_str = str(enriched_lead_data.get('company_size', ''))
        lead_location = str(enriched_lead_data.get('location', '')).lower()

        # 1. Title Match
        # get() returns None if key missing OR if JSON parsing failed in DB layer
        title_keywords = icp_to_use.get("title_keywords")
        if isinstance(title_keywords, list) and title_keywords and lead_title: # Check type and content
            max_possible_score += 1.0 # Increment max score only if criteria exists and lead has data
            # Ensure keywords in DB list are also compared lowercase
            if any(str(keyword).lower() in lead_title for keyword in title_keywords):
                achieved_score += 1.0; reasons.append("Title Match")
                logger.debug(f" Match: Title '{lead_title}'")

        # 2. Industry Match
        industry_keywords = icp_to_use.get("industry_keywords")
        if isinstance(industry_keywords, list) and industry_keywords and lead_industry:
            max_possible_score += 1.0
            if any(str(keyword).lower() in lead_industry for keyword in industry_keywords):
                achieved_score += 1.0; reasons.append("Industry Match")
                logger.debug(f" Match: Industry '{lead_industry}'")

        # 3. Company Size Match (Adapt based on how 'company_size_rules' is stored)
        size_rules = icp_to_use.get("company_size_rules") # This should be a dict or list after parsing
        if size_rules and lead_size_str: # Check if rules exist AND lead has size info
            max_possible_score += 1.0
            size_matched = False
            try:
                # Example logic if storing rules as {"min": 50, "max": 500}
                if isinstance(size_rules, dict) and "min" in size_rules:
                    size_match_num = re.search(r'\d+', lead_size_str) # Get first number
                    if size_match_num:
                        lead_num = int(size_match_num.group(0))
                        min_ok = lead_num >= int(size_rules["min"])
                        max_val = size_rules.get("max") # Max is optional
                        max_ok = (max_val is None) or (lead_num <= int(max_val))
                        if min_ok and max_ok: size_matched = True
                # Example logic if storing rules as a list of strings ["51-200", "1000+"]
                elif isinstance(size_rules, list):
                     if any(str(target).strip() == lead_size_str.strip() for target in size_rules):
                         size_matched = True
                # Add more complex parsing/comparison logic as needed
            except (ValueError, TypeError, KeyError) as parse_err:
                 logger.warning(f"Could not parse/compare company size rule '{size_rules}' with lead size '{lead_size_str}': {parse_err}")

            if size_matched:
                 achieved_score += 1.0; reasons.append("Company Size Match")
                 logger.debug(f" Match: Size '{lead_size_str}'")

        # 4. Location Match
        location_keywords = icp_to_use.get("location_keywords")
        if isinstance(location_keywords, list) and location_keywords and lead_location:
             max_possible_score += 1.0
             if any(str(keyword).lower() in lead_location for keyword in location_keywords):
                 achieved_score += 1.0; reasons.append("Location Match")
                 logger.debug(f" Match: Location '{lead_location}'")


        # --- Calculate Final Score ---
        final_score = achieved_score / max_possible_score if max_possible_score > 0 else 0.0
        logger.info(f"ICP Match score for {email} (Org {organization_id}): {final_score:.2f} [{'; '.join(reasons)}]")
        return final_score

        logger.info(f"ICP Match score for {email}: {final_score:.2f} (Score: {achieved_score}/{max_possible_score}, Reasons: {'; '.join(reasons)})")
        # For now, just return the score. The LeadWorkflowAgent will set 'matched' and 'reason'.
        # Optionally, you could return a dictionary: {"score": final_score, "reasons": reasons}
        return final_score
