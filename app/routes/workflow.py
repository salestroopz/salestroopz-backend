# app/routes/workflow.py

# --- Existing & Added Imports ---
from fastapi import (
    APIRouter, HTTPException, Depends, BackgroundTasks, status,
    UploadFile, File # Keep UploadFile/File if upload endpoint is here
)
from typing import List, Dict, Any # Keep Dict, Any if used by background task
import shutil # Keep if upload endpoint is here
import uuid   # Keep if upload endpoint is here
from pathlib import Path # Keep if upload endpoint is here
import pandas as pd # Keep if background task reads files here

# Import schemas needed
from app.schemas import (
    ICPRequest, LeadResponse, UserPublic, # Existing
    WorkflowInitiateRequest # Add schema for the new endpoint
)
# Import agents and dependencies
from app.agents.leadworkflow import LeadWorkflowAgent
from app.auth.dependencies import get_current_user # Auth dependency

# Import database module
from app.db import database

# --- Constants and Setup (If Upload Endpoint is Here) ---
UPLOAD_DIR = Path("./temp_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# --- Router Definition ---
# Using the prefix/tags you had defined
router = APIRouter(
    prefix="/api/v1/workflow", # Keep your defined prefix
    tags=["Lead Workflow (Original)"] # Keep your defined tag
)


# === NEW File Upload Endpoint (Keep if managed here) ===
# Consider moving file handling to its own router later for clarity
@router.post("/files/upload", tags=["File Handling"]) # Added tag
async def upload_lead_file(file: UploadFile = File(...)):
    """
    Accepts a lead file (CSV or XLSX), saves it temporarily,
    and returns a unique filename identifier.
    (Does not require auth by default, add if needed)
    """
    # ... (Keep the file saving logic from previous steps) ...
    if not file: raise HTTPException(status_code=400, detail="No file sent.")
    allowed_extensions = {'.csv', '.xlsx'}; file_extension = Path(file.filename).suffix.lower()
    if file_extension not in allowed_extensions: raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: {allowed_extensions}")
    unique_id = uuid.uuid4(); unique_filename = f"{unique_id}{file_extension}"; file_location = UPLOAD_DIR / unique_filename
    try:
        with file_location.open("wb") as buffer: shutil.copyfileobj(file.file, buffer)
        print(f"File '{file.filename}' uploaded as '{unique_filename}'")
    except Exception as e: print(f"Error saving file {unique_filename}: {e}"); raise HTTPException(status_code=500, detail="Could not save file.")
    finally: await file.close()
    return {"filename": unique_filename, "original_filename": file.filename}


# === NEW Chatbot Workflow Initiation Endpoint (Secured) ===
@router.post("/initiate", status_code=status.HTTP_202_ACCEPTED) # Changed path from /workflow/initiate
async def initiate_workflow_from_icp(
    request_data: WorkflowInitiateRequest,
    background_tasks: BackgroundTasks,
    current_user: UserPublic = Depends(get_current_user) # <--- REQUIRE AUTH
):
    """
    Accepts ICP definition and lead source for the CURRENT USER'S ORG,
    initiates lead generation and workflow in the background. Requires authentication.
    """
    # Log user and org performing action
    print(f"Received workflow initiation request for Org ID: {current_user.organization_id} by User: {current_user.email}")
    print(f"  Source Type: {request_data.source_type}, Details: {request_data.source_details}")

    # --- Pass organization_id to background task ---
    background_tasks.add_task(
        process_leads_background, # Background function defined below
        organization_id=current_user.organization_id, # <--- Pass Org ID
        user_email=current_user.email, # Optional for logging
        source_type=request_data.source_type,
        source_details=request_data.source_details or {},
        icp=request_data.icp.dict()
        )

    # Return immediate acknowledgement
    return {
        "message": "Workflow initiation request received. Processing will start in the background.",
        "details_received": {
             "icp": request_data.icp.dict(),
             "source": request_data.source_type,
             "source_details": request_data.source_details
             }
        }


# === Existing /full-cycle endpoint (Now Secured) ===
@router.post("/full-cycle")
async def run_full_cycle_workflow( # Changed to async
    icp: ICPRequest,
    current_user: UserPublic = Depends(get_current_user) # <--- REQUIRE AUTH
):
    """Runs the original full workflow based on ICPRequest FOR THE CURRENT USER'S ORG."""
    # TODO: Update LeadWorkflowAgent.run_full_workflow to accept organization_id
    # TODO: Determine how leads are fetched based on ICP for a specific org.
    print(f"Received request for /full-cycle for Org ID: {current_user.organization_id} by User: {current_user.email}")
    agent = LeadWorkflowAgent() # Consider using Depends(get_agent_instance)
    try:
        # --- Pass organization_id to agent method ---
        result = agent.run_full_workflow(icp, organization_id=current_user.organization_id) # <--- Pass Org ID
        return result
    except TypeError as te:
         if "organization_id" in str(te):
             print(f"ERROR: Agent method run_full_workflow needs update for multi-tenancy: {te}")
             raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Agent logic needs update for multi-tenancy.")
         else: raise te
    except Exception as e:
         print(f"Error in /full-cycle for org {current_user.organization_id}: {e}")
         raise HTTPException(status_code=500, detail="Failed to run full cycle workflow.")


# === CORRECTED Multi-Tenant /leads endpoint (Already Secured) ===
@router.get("/leads", response_model=List[LeadResponse])
def list_tenant_leads(current_user: UserPublic = Depends(get_current_user)):
    """
    Lists leads currently saved in the database FOR THE CURRENT USER'S ORGANIZATION.
    Requires authentication. Uses the multi-tenant database functions.
    """
    print(f"Received request for /leads for org: {current_user.organization_id}")
    try:
        # Use the correct, tenant-aware database function
        leads = database.get_leads_by_organization(organization_id=current_user.organization_id)
        return leads
    except Exception as e:
        print(f"Error fetching leads for org {current_user.organization_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve leads.")


# ============================================================
# --- Background Task Definition (Must be defined/imported) ---
# ============================================================
# Ensure this function is defined here or imported correctly
# if defined in another file (e.g., app.tasks.background)

def process_leads_background(organization_id: int, user_email: str, source_type: str, source_details: dict, icp: dict):
    """
    Background task to fetch/read leads and process them for a specific organization.
    (Includes file reading logic, calls agent.process with org_id)
    """
    print(f"[BG Task Start] Org ID: {organization_id}, User: {user_email}, Source: {source_type}")
    leads_to_process = []
    processed_count = 0
    errors = []
    temp_file_to_delete = None
    agent = None

    try:
        agent = LeadWorkflowAgent() # Instantiate agent for the task
        if not agent: raise ValueError("LeadWorkflowAgent could not be instantiated.")

        # --- Lead Fetching/Reading Logic ---
        if source_type == "file_upload":
            filename = source_details.get("filename")
            if not filename: raise ValueError("Filename missing for file upload")
            file_path = UPLOAD_DIR / filename
            temp_file_to_delete = file_path
            if not file_path.is_file(): raise FileNotFoundError(f"BG Task: File not found {file_path}")

            print(f"[BG Task] Processing file: {file_path}")
            try: # Read file
                if filename.lower().endswith(".csv"):
                    df = pd.read_csv(file_path, on_bad_lines='warn') # Added basic error handling
                elif filename.lower().endswith(".xlsx"):
                    df = pd.read_excel(file_path, engine='openpyxl')
                else: raise ValueError(f"Unsupported file extension: {filename}")

                # --- Column Mapping ---
                # ** ADAPT THIS MAP TO YOUR EXPECTED FILE HEADERS **
                column_map = {
                    'email': ['email', 'email address', 'e-mail', 'emailaddress'],
                    'name': ['name', 'full name', 'contact name', 'contact'],
                    'company': ['company', 'company name', 'organization', 'account name'],
                    'title': ['title', 'job title', 'position'],
                    # Add other relevant columns if present in your files
                }
                df.columns = df.columns.str.lower().str.strip().str.replace('[^A-Za-z0-9_]+', '', regex=True) # Normalize further

                mapped_cols = {}
                for target_key, possible_names in column_map.items():
                    for name in possible_names:
                        normalized_name = name.lower().strip().replace('[^A-Za-z0-9_]+', '', regex=True)
                        if normalized_name in df.columns:
                            mapped_cols[target_key] = normalized_name; break
                    if target_key not in mapped_cols: print(f"[BG Task Warning] Target column '{target_key}' not found.")
                    if target_key == 'email' and target_key not in mapped_cols: raise ValueError("Required 'email' column not found.")

                if 'email' not in mapped_cols: raise ValueError("Could not map an 'email' column.")

                # --- Convert DF to List of Dicts ---
                for index, row in df.iterrows():
                    lead_dict = {}
                    has_essential = True
                    for target_key, source_col in mapped_cols.items():
                        value = row.get(source_col)
                        lead_dict[target_key] = str(value).strip() if pd.notna(value) else None
                        if target_key == 'email' and not lead_dict[target_key]:
                            print(f"[BG Task Warning] Skipping row {index+2} due to missing email.")
                            has_essential = False; break # Stop processing this row
                    if not has_essential: continue # Go to next row

                    lead_dict['source'] = f"file_upload:{filename}" # Add source info
                    leads_to_process.append(lead_dict)

            except Exception as read_err:
                 error_detail = f"Error reading/parsing file {filename}: {read_err}"
                 print(f"[BG Task ERROR] {error_detail}"); errors.append(error_detail)

        elif source_type in ["apollo", "crm", "manual_entry"]:
             msg = f"Source type '{source_type}' processing not yet implemented."
             print(f"[BG Task] {msg}"); errors.append(msg)
             pass
        else:
             msg = f"Unsupported source type: {source_type}"
             print(f"[BG Task ERROR] {msg}"); errors.append(msg)

        # --- Process the extracted leads ---
        if leads_to_process:
            print(f"[BG Task] Submitting {len(leads_to_process)} leads to agent for Org ID: {organization_id}...")
            for lead_dict in leads_to_process:
                try:
                    # --- Pass organization_id to agent.process ---
                    agent.process(lead_dict, organization_id=organization_id)
                    processed_count += 1
                except TypeError as te:
                     if "organization_id" in str(te):
                         err_msg = f"Agent method 'process' needs update for multi-tenancy (org_id). Error: {te}"
                         print(f"[BG Task ERROR] {err_msg}"); errors.append(err_msg)
                         raise HTTPException(status_code=501, detail=err_msg)
                     else: raise te
                except Exception as agent_err:
                    error_detail = f"Agent failed for lead {lead_dict.get('email', 'N/A')}: {agent_err}"
                    print(f"[BG Task ERROR] {error_detail}"); errors.append(error_detail)
        elif not errors:
            msg = f"No valid leads found or extracted from source: {source_type}"
            print(f"[BG Task] {msg}"); errors.append(msg)

    except Exception as bg_err:
         error_detail = f"Critical error in background task for Org ID {organization_id}: {bg_err}"
         print(f"[BG Task ERROR] {error_detail}")
         if not errors: errors.append(error_detail)

    finally:
        # --- Cleanup ---
        if temp_file_to_delete and temp_file_to_delete.is_file():
            try: temp_file_to_delete.unlink(); print(f"[BG Task] Deleted temp file: {temp_file_to_delete}")
            except Exception as del_err: print(f"[BG Task ERROR] Failed to delete temp file {temp_file_to_delete}: {del_err}")

        print(f"[BG Task Finish] Org ID: {organization_id}. Processed: {processed_count}, Errors: {len(errors)}")
        if errors: print(f"[BG Task Errors] Org ID {organization_id}:\n" + "\n".join([f" - {e}" for e in errors]))
    
