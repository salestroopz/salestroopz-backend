# app/agents/icp_matcher.py

from typing import Dict, Any # Use Dict, Any for dictionary processing
from app.utils.logger import logger
import re # For potential parsing later

class ICPMatcherAgent:
    def __init__(self):
        # Define ICP criteria - TODO: Load this dynamically per organization later
        self.icp_criteria = {
            "title_keywords": ["cto", "cio", "head of it", "vp engineering", "director it", "it manager"], # Use lowercase for easier matching
            "min_company_size": 50, # Example minimum employee count
            "industry_keywords": ["financial services", "fintech", "software", "saas"], # Example industries
            # Add other criteria like location keywords, etc.
        }
        logger.info(f"ICPMatcherAgent initialized with ICP: {self.icp_criteria}")

    def match(self, enriched_lead_data: Dict[str, Any], organization_id: int = None) -> float:
        """
        Compares enriched lead data (dictionary) against ICP criteria.
        Returns a match score (0.0 to 1.0).
        'organization_id' is included for future use when loading tenant-specific ICPs.
        """
        email = enriched_lead_data.get('email', 'N/A')
        logger.info(f"Attempting ICP match for: {email} (Org: {organization_id})")

        # TODO: Load ICP specific to organization_id from database here
        # For now, use the criteria defined in __init__
        icp_to_use = self.icp_criteria

        max_possible_score = 0.0
        achieved_score = 0.0
        reasons = [] # Optional: Collect reasons for scoring

        # --- Scoring Logic ---

        # 1. Title Match
        if 'title_keywords' in icp_to_use and enriched_lead_data.get('title'):
            max_possible_score += 1.0 # Assign weight/importance
            lead_title = enriched_lead_data['title'].lower()
            if any(keyword in lead_title for keyword in icp_to_use['title_keywords']):
                achieved_score += 1.0
                reasons.append(f"Title matched ({enriched_lead_data['title']})")
                logger.debug(f" Match: Title '{lead_title}'")

        # 2. Company Size Match (Example using min size)
        if 'min_company_size' in icp_to_use and enriched_lead_data.get('company_size'):
            max_possible_score += 1.0 # Assign weight
            lead_size_str = str(enriched_lead_data['company_size'])
            # Attempt to extract a minimum number from the string (e.g., "51-200" -> 51)
            size_match = re.search(r'\d+', lead_size_str)
            if size_match:
                try:
                    lead_min_size = int(size_match.group(0))
                    if lead_min_size >= icp_to_use['min_company_size']:
                        achieved_score += 1.0
                        reasons.append(f"Company size OK ({lead_size_str})")
                        logger.debug(f" Match: Size '{lead_size_str}' >= {icp_to_use['min_company_size']}")
                except ValueError:
                    logger.warning(f"Could not parse company size '{lead_size_str}' for {email}")

        # 3. Industry Match
        if 'industry_keywords' in icp_to_use and enriched_lead_data.get('industry'):
            max_possible_score += 1.0 # Assign weight
            lead_industry = enriched_lead_data['industry'].lower()
            if any(keyword in lead_industry for keyword in icp_to_use['industry_keywords']):
                achieved_score += 1.0
                reasons.append(f"Industry matched ({enriched_lead_data['industry']})")
                logger.debug(f" Match: Industry '{lead_industry}'")

        # --- Calculate Final Score ---
        final_score = achieved_score / max_possible_score if max_possible_score > 0 else 0.0

        logger.info(f"ICP Match score for {email}: {final_score:.2f} (Score: {achieved_score}/{max_possible_score}, Reasons: {'; '.join(reasons)})")
        # For now, just return the score. The LeadWorkflowAgent will set 'matched' and 'reason'.
        # Optionally, you could return a dictionary: {"score": final_score, "reasons": reasons}
        return final_score
