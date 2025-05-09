# app/agents/icp_matcher.py
from typing import Dict, Any, List, Optional
from app.utils.logger import logger
import re
from app.db import database # Assuming your database functions are accessible

class ICPMatcherAgent:
    def __init__(self):
        logger.info("ICPMatcherAgent initialized.")

    def _parse_lead_company_size(self, lead_size_str: str) -> Optional[int]:
        # ... (same as previously suggested _parse_lead_company_size) ...
        if not lead_size_str: return None
        match = re.search(r'\d+', lead_size_str)
        if match:
            try: return int(match.group(0))
            except ValueError: return None
        return None

    def _score_single_lead_against_single_icp(
        self,
        lead_data_dict: Dict[str, Any], # Lead data as dict
        icp_definition: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Scores a single lead against a single ICP definition.
        Internal helper method.
        """
        email = lead_data_dict.get('email', 'N/A')
        icp_name = icp_definition.get('name', 'Unknown ICP')
        
        max_possible_score = 0.0
        achieved_score = 0.0
        match_reasons = []
        matched_criteria_count = 0
        total_criteria_considered = 0

        lead_industry = str(lead_data_dict.get('industry', '')).lower().strip()
        lead_title = str(lead_data_dict.get('title', '')).lower().strip()
        lead_company_size_str = str(lead_data_dict.get('company_size', '')).strip()
        lead_location = str(lead_data_dict.get('location', '')).lower().strip()

        # Title Match
        title_keywords = icp_definition.get("title_keywords")
        if isinstance(title_keywords, list) and title_keywords:
            total_criteria_considered +=1
            if lead_title:
                max_possible_score += 1.0
                if any(str(kw).lower().strip() in lead_title for kw in title_keywords if kw):
                    achieved_score += 1.0; match_reasons.append("Title"); matched_criteria_count +=1
        
        # Industry Match
        industry_keywords = icp_definition.get("industry_keywords")
        if isinstance(industry_keywords, list) and industry_keywords:
            total_criteria_considered +=1
            if lead_industry:
                max_possible_score += 1.0
                if any(str(kw).lower().strip() in lead_industry for kw in industry_keywords if kw):
                    achieved_score += 1.0; match_reasons.append("Industry"); matched_criteria_count +=1

        # Company Size Match
        size_rules = icp_definition.get("company_size_rules")
        if isinstance(size_rules, dict) and ("min" in size_rules or "max" in size_rules):
            total_criteria_considered +=1
            lead_numerical_size = self._parse_lead_company_size(lead_company_size_str)
            if lead_numerical_size is not None:
                max_possible_score += 1.0
                min_ok = (size_rules.get("min") is None) or (lead_numerical_size >= int(size_rules["min"]))
                max_ok = (size_rules.get("max") is None) or (lead_numerical_size <= int(size_rules["max"]))
                if min_ok and max_ok:
                    achieved_score += 1.0; match_reasons.append("Company Size"); matched_criteria_count +=1
        
        # Location Match
        location_keywords = icp_definition.get("location_keywords")
        if isinstance(location_keywords, list) and location_keywords:
            total_criteria_considered +=1
            if lead_location:
                max_possible_score += 1.0
                if any(str(kw).lower().strip() in lead_location for kw in location_keywords if kw):
                    achieved_score += 1.0; match_reasons.append("Location"); matched_criteria_count +=1
        
        final_score_percentage = (achieved_score / max_possible_score * 100) if max_possible_score > 0 else 0.0
        
        MATCH_THRESHOLD_PERCENTAGE = 50.0
        MIN_CRITERIA_MATCHED = 1 # For a simple definition of "is_match"
        is_match = (max_possible_score > 0 and 
                    final_score_percentage >= MATCH_THRESHOLD_PERCENTAGE and 
                    matched_criteria_count >= MIN_CRITERIA_MATCHED)
            
        return {
            "score_percentage": round(final_score_percentage, 2),
            "is_match": is_match,
            "reasons": match_reasons,
            "matched_icp_id": icp_definition.get("id"),
            "matched_icp_name": icp_name,
            "lead_email": email # For easier identification in results
        }

    def match_leads_against_org_icps(
        self,
        leads_input: List[Dict[str, Any]], # Expect list of lead dicts (converted from LeadInput)
        organization_id: int
    ) -> List[Dict[str, Any]]:
        """
        Matches a list of leads against all ICPs of a given organization.
        Returns a list of leads, each with their best ICP match info or indication of no match.
        This method does NOT update the database.
        """
        logger.info(f"Matching {len(leads_input)} leads for organization_id: {organization_id}")
        
        org_icps = database.get_icps_by_organization_id(organization_id)
        if not org_icps:
            logger.warning(f"No ICPs found for organization {organization_id}. Cannot perform matching.")
            # Return leads with no match info
            return [{**lead, "icp_match_result": {"is_match": False, "message": "No ICPs defined for organization."}} for lead in leads_input]

        processed_leads_with_match_info = []
        for lead_data_dict in leads_input:
            best_match_for_this_lead = {"is_match": False, "score_percentage": -1.0} # Initialize with a non-match

            for icp_def in org_icps:
                current_match_details = self._score_single_lead_against_single_icp(lead_data_dict, icp_def)
                
                if current_match_details["is_match"]:
                    if current_match_details["score_percentage"] > best_match_for_this_lead["score_percentage"]:
                        best_match_for_this_lead = current_match_details
            
            # Add original lead data along with the best match result
            processed_leads_with_match_info.append({
                "original_lead_data": lead_data_dict, # Or just specific fields like lead_id/email
                "icp_match_result": best_match_for_this_lead
            })
            logger.debug(f"Lead {lead_data_dict.get('email', 'N/A')} best match: {best_match_for_this_lead.get('matched_icp_name', 'None')}")

        return processed_leads_with_match_info

        logger.info(f"ICP Match score for {email}: {final_score:.2f} (Score: {achieved_score}/{max_possible_score}, Reasons: {'; '.join(reasons)})")
        # For now, just return the score. The LeadWorkflowAgent will set 'matched' and 'reason'.
        # Optionally, you could return a dictionary: {"score": final_score, "reasons": reasons}
        return final_score
