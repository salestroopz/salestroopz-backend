# app/agents/icp_matcher.py
from typing import Dict, Any, List, Optional
from app.utils.logger import logger
import re
from app.db import database # For fetching ICPs within the agent

class ICPMatcherAgent:
    def __init__(self):
        logger.info("ICPMatcherAgent initialized.")

    def _parse_lead_company_size(self, lead_size_str: str) -> Optional[int]:
        if not lead_size_str: return None
        match = re.search(r'\d+', lead_size_str)
        if match:
            try: return int(match.group(0))
            except ValueError: return None
        return None

    def _score_single_lead_against_single_icp(
        self,
        lead_data_dict: Dict[str, Any],
        icp_definition: Dict[str, Any]
    ) -> Dict[str, Any]:
        email = lead_data_dict.get('email', 'N/A')
        icp_name = icp_definition.get('name', 'Unknown ICP')
        
        max_possible_score = 0.0
        achieved_score = 0.0
        match_reasons = []
        matched_criteria_count = 0
        # total_criteria_considered = 0 # Not strictly needed for this refined version

        lead_industry = str(lead_data_dict.get('industry', '')).lower().strip()
        lead_title = str(lead_data_dict.get('title', '')).lower().strip()
        lead_company_size_str = str(lead_data_dict.get('company_size', '')).strip()
        lead_location = str(lead_data_dict.get('location', '')).lower().strip()

        # Title Match
        title_keywords = icp_definition.get("title_keywords")
        if isinstance(title_keywords, list) and title_keywords:
            # total_criteria_considered +=1 (Uncomment if tracking this level of detail)
            if lead_title:
                max_possible_score += 1.0
                if any(str(kw).lower().strip() in lead_title for kw in title_keywords if kw):
                    achieved_score += 1.0; match_reasons.append("Title"); matched_criteria_count +=1
        
        # Industry Match
        industry_keywords = icp_definition.get("industry_keywords")
        if isinstance(industry_keywords, list) and industry_keywords:
            # total_criteria_considered +=1
            if lead_industry:
                max_possible_score += 1.0
                if any(str(kw).lower().strip() in lead_industry for kw in industry_keywords if kw):
                    achieved_score += 1.0; match_reasons.append("Industry"); matched_criteria_count +=1

        # Company Size Match
        size_rules = icp_definition.get("company_size_rules")
        if isinstance(size_rules, dict) and ("min" in size_rules or "max" in size_rules):
            # total_criteria_considered +=1
            lead_numerical_size = self._parse_lead_company_size(lead_company_size_str)
            if lead_numerical_size is not None:
                max_possible_score += 1.0
                min_val = size_rules.get("min")
                max_val = size_rules.get("max")
                min_ok = (min_val is None) or (lead_numerical_size >= int(min_val))
                max_ok = (max_val is None) or (lead_numerical_size <= int(max_val))
                if min_ok and max_ok:
                    achieved_score += 1.0; match_reasons.append("Company Size"); matched_criteria_count +=1
        
        # Location Match
        location_keywords = icp_definition.get("location_keywords")
        if isinstance(location_keywords, list) and location_keywords:
            # total_criteria_considered +=1
            if lead_location:
                max_possible_score += 1.0
                if any(str(kw).lower().strip() in lead_location for kw in location_keywords if kw):
                    achieved_score += 1.0; match_reasons.append("Location"); matched_criteria_count +=1
        
        final_score_percentage = (achieved_score / max_possible_score * 100) if max_possible_score > 0 else 0.0
        
        MATCH_THRESHOLD_PERCENTAGE = 50.0 
        MIN_CRITERIA_MATCHED = 1
        is_match = (max_possible_score > 0 and 
                    final_score_percentage >= MATCH_THRESHOLD_PERCENTAGE and 
                    matched_criteria_count >= MIN_CRITERIA_MATCHED)
            
        return {
            "score_percentage": round(final_score_percentage, 2),
            "is_match": is_match,
            "reasons": match_reasons,
            "matched_icp_id": icp_definition.get("id"),
            "matched_icp_name": icp_name,
            "lead_email": email # For logging/identification
        }

    def process_leads_for_icp_matching( # Renamed for clarity
        self,
        leads_input_dicts: List[Dict[str, Any]], 
        organization_id: int
    ) -> List[Dict[str, Any]]:
        """
        Processes a list of lead dictionaries against all ICPs of a given organization.
        Returns a list, each item containing original lead data and its best ICP match info.
        This method does NOT update the database.
        """
        logger.info(f"Processing {len(leads_input_dicts)} leads for ICP matching for organization_id: {organization_id}")
        
        org_icps = database.get_icps_by_organization_id(organization_id) # Fetches ICPs for the org
        if not org_icps:
            logger.warning(f"No ICPs found for organization {organization_id}. Cannot perform matching.")
            return [{
                "original_lead_data": lead, 
                "icp_match_result": {
                    "is_match": False, 
                    "message": "No ICPs defined for organization."
                    }
                } for lead in leads_input_dicts]

        results_for_all_leads = []
        for lead_data_dict in leads_input_dicts:
            best_match_for_this_lead = {
                "is_match": False, 
                "score_percentage": -1.0, # Ensures any valid score is higher
                "matched_icp_id": None,
                "matched_icp_name": "None",
                "reasons": [],
                "lead_email": lead_data_dict.get("email", "N/A")
            }

            for icp_def in org_icps:
                current_match_details = self._score_single_lead_against_single_icp(lead_data_dict, icp_def)
                
                if current_match_details["is_match"]:
                    if current_match_details["score_percentage"] > best_match_for_this_lead["score_percentage"]:
                        best_match_for_this_lead = current_match_details # Update best match
            
            results_for_all_leads.append({
                "original_lead_data": lead_data_dict, 
                "icp_match_result": best_match_for_this_lead
            })
        
        logger.info(f"Finished processing {len(leads_input_dicts)} leads for org {organization_id}. Found matches for some leads.")
        return results_for_all_leads
