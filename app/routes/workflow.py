# app/routes/workflow.py

# --- Existing & Added Imports ---
from fastapi import (
    APIRouter, HTTPException, Depends, BackgroundTasks, status,
    UploadFile, File
)
from typing import List, Dict, Any
import shutil
import uuid
from pathlib import Path
import pandas as pd

# Import schemas needed
from app.schemas import (
    LeadResponse, UserPublic, # Keep these
    WorkflowInitiateRequest # Keep this for /initiate endpoint
    # ICPRequest, # <--- REMOVE THIS IMPORT
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
router = APIRouter(
    # Define prefix and tags - SET THESE AS DESIRED
    # Example: If this file ONLY handles /initiate, /files/upload, /leads maybe:
    prefix="/api/v1",
    tags=["Lead Workflow & Data"]
)


# === File Upload Endpoint ===
@router.post("/files/upload", tags=["File Handling"])
async def upload_lead_file(file: UploadFile = File(...)):
    """
    Accepts a lead file (CSV or XLSX), saves it temporarily,
    and returns a unique filename identifier.
    """
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


# === Chatbot Workflow Initiation Endpoint (Secured) ===
@router.post("/workflow/initiate", status_code=status.HTTP_202_ACCEPTED) # Keep specific path if desired
async def initiate_workflow_from_icp(
    request_data: WorkflowInitiateRequest,
    background_tasks: BackgroundTasks,
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Accepts ICP definition and lead source for the CURRENT USER'S ORG,
    initiates lead generation and workflow in the background. Requires authentication.
    """
    print(f"Received workflow initiation request for Org ID: {current_user.organization_id} by User: {current_user.email}")
    # ... (Keep logging source type/details) ...
    background_tasks.add_task(
        process_leads_background,
        organization_id=current_user.organization_id,
        user_email=current_user.email,
        source_type=request_data.source_type,
        source_details=request_data.source_details or {},
        icp=request_data.icp.dict()
        )
    # Return immediate acknowledgement
    return {
        "message": "Workflow initiation request received. Processing will start in the background.",
        # You should include the details received as well for confirmation
        "details_received": {
             "icp": request_data.icp.dict(),
             "source": request_data.source_type,
             "source_details": request_data.source_details # Send back what was received
             }
        } # Close the main dictionary correctly

# === /full-cycle endpoint REMOVED ===
# @router.post("/full-cycle") ...


# === Multi-Tenant /leads endpoint (Secured) ===
@router.get("/leads", response_model=List[LeadResponse])
def list_tenant_leads(current_user: UserPublic = Depends(get_current_user)):
    """
    Lists leads currently saved in the database FOR THE CURRENT USER'S ORGANIZATION.
    Requires authentication.
    """
    print(f"Received request for /leads for org: {current_user.organization_id}")
    try:
        leads = database.get_leads_by_organization(organization_id=current_user.organization_id)
        return leads
    except Exception as e:
        print(f"Error fetching leads for org {current_user.organization_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve leads.")


# ============================================================
# --- Background Task Definition ---
# ============================================================
def process_leads_background(organization_id: int, user_email: str, source_type: str, source_details: dict, icp: dict):
    """
    Background task to fetch/read leads and process them for a specific organization.
    (Includes file reading logic, calls agent.process with org_id)
    """
    print(f"[BG Task Start] Org ID: {organization_id}, User: {user_email}, Source: {source_type}")
    # Initialize variables used throughout the function
    leads_to_process = []
    processed_count = 0
    errors = []
    temp_file_to_delete = None
    agent = None # Initialize agent variable

    # --- Main Try Block for the entire background task ---
    try:
        agent = LeadWorkflowAgent() # Instantiate agent for the task
        if not agent: raise ValueError("LeadWorkflowAgent could not be instantiated.")

        # === Lead Fetching/Reading Logic ===
        if source_type == "file_upload":
            filename = source_details.get("filename")
            if not filename: raise ValueError("Filename missing for file upload")
            file_path = UPLOAD_DIR / filename
            temp_file_to_delete = file_path # Mark for potential deletion
            if not file_path.is_file(): raise FileNotFoundError(f"BG Task: File not found {file_path}")

            print(f"[BG Task] Processing file: {file_path}")
            try: # Inner try specifically for file reading/parsing
                if filename.lower().endswith(".csv"):
                    df = pd.read_csv(file_path, on_bad_lines='warn')
                elif filename.lower().endswith(".xlsx"):
                    df = pd.read_excel(file_path, engine='openpyxl')
                else: raise ValueError(f"Unsupported file extension: {filename}")

                # --- Column Mapping ---
                column_map = { # Adapt this map!
                    'email': ['email', 'email address', 'e-mail', 'emailaddress'],
                    'name': ['name', 'full name', 'contact name', 'contact'],
                    'company': ['company', 'company name', 'organization', 'account name'],
                    'title': ['title', 'job title', 'position'],
                }
                df.columns = df.columns.str.lower().str.strip().str.replace('[^A-Za-z0-9_]+', '', regex=True)

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
                            has_essential = False; break
                    if not has_essential: continue
                    lead_dict['source'] = f"file_upload:{filename}"
                    leads_to_process.append(lead_dict)

            except Exception as read_err:
                 # Handle errors during file reading/parsing specifically
                 error_detail = f"Error reading/parsing file {filename}: {read_err}"
                 print(f"[BG Task ERROR] {error_detail}"); errors.append(error_detail)
                 # Do not proceed further in the 'try' block if file reading failed
                 raise # Re-raise to be caught by the outer except block

        elif source_type == "manual_entry":
            manual_leads_data = source_details.get("manual_leads", [])
            if not isinstance(manual_leads_data, list):
                errors.append("Invalid format for 'manual_leads' (expected list).")
            elif not manual_leads_data:
                 errors.append("No leads provided in 'manual_leads' data.")
            else:
                 print(f"[BG Task] Processing {len(manual_leads_data)} manually entered leads.")
                 valid_manual_leads = []
                 for lead_dict in manual_leads_data:
                     if isinstance(lead_dict, dict) and lead_dict.get('email'):
                         lead_dict.setdefault('source', 'manual_entry')
                         valid_manual_leads.append(lead_dict)
                     else: errors.append(f"Invalid manual lead format skipped: {lead_dict}")
                 leads_to_process = valid_manual_leads

        elif source_type in ["apollo", "crm"]:
             msg = f"Source type '{source_type}' processing not yet implemented."
             print(f"[BG Task] {msg}"); errors.append(msg)
             # No leads added to leads_to_process
        else:
             msg = f"Unsupported source type: {source_type}"
             print(f"[BG Task ERROR] {msg}"); errors.append(msg)
             # No leads added

        # === Process the extracted leads ===
        if leads_to_process:
            print(f"[BG Task] Submitting {len(leads_to_process)} leads to agent for Org ID: {organization_id}...")
            # Loop through leads and process one by one
            for lead_dict in leads_to_process:
                try: # Inner try for processing a single lead by the agent
                    # --- Pass organization_id to agent.process ---
                    # Ensure agent.process exists and accepts organization_id
                    agent.process_single_lead(lead_dict, organization_id=organization_id) # Using the refactored name
                    processed_count += 1
                except TypeError as te:
                    # Handle specific error if agent method signature is wrong
                    if "organization_id" in str(te) or "process_single_lead" in str(te):
                        err_msg = f"Agent method needs update for multi-tenancy/signature. Error: {te}"
                        print(f"[BG Task ERROR] {err_msg}"); errors.append(err_msg)
                        # Consider if you should stop the whole task here
                        break # Stop processing further leads in this batch if agent is broken
                    else:
                        # Handle other unexpected TypeErrors
                        error_detail = f"Type error processing lead {lead_dict.get('email', 'N/A')}: {te}"
                        print(f"[BG Task ERROR] {error_detail}"); errors.append(error_detail)
                except Exception as agent_err:
                    # Handle errors from the agent's processing logic
                    error_detail = f"Agent failed processing lead {lead_dict.get('email', 'N/A')}: {agent_err}"
                    print(f"[BG Task ERROR] {error_detail}"); errors.append(error_detail)
                    # Continue to the next lead even if one fails
        elif not errors: # Only log this if no leads AND no previous errors
            msg = f"No valid leads found or extracted from source: {source_type}"
            print(f"[BG Task] {msg}"); errors.append(msg)

    # --- Outer Except Block (Catches errors from agent init, file finding, critical parsing errors) ---
    except Exception as bg_err:
         error_detail = f"Critical error during background task setup or processing for Org ID {organization_id}: {bg_err}"
         print(f"[BG Task ERROR] {error_detail}")
         # Ensure the error gets logged if 'errors' list was empty
         if not errors: errors.append(error_detail)

    # --- Finally Block (Executes regardless of errors in try block) ---
    finally:
        # Level 1 indent (inside finally)
        print(f"DEBUG: Entering finally block for background task Org {organization_id}")

        # Level 1 indent
        if temp_file_to_delete and temp_file_to_delete.is_file():
            try: # Level 2 indent (inside if)
                temp_file_to_delete.unlink()
                # Level 3 indent (inside try)
                print(f"[BG Task] Deleted temp file: {temp_file_to_delete}")
            except Exception as del_err: # Level 2 indent
                 # Level 3 indent
                print(f"[BG Task ERROR] Failed to delete temp file {temp_file_to_delete}: {del_err}")

        # Level 1 indent (ALIGN WITH 'if temp_file_to_delete...')
        print(f"[BG Task Finish] Org ID: {organization_id}. Processed Count: {processed_count}, Leads Submitted: {len(leads_to_process)}, Errors Logged: {len(errors)}")

        # Level 1 indent
        if errors:
             # Level 2 indent
            print(f"[BG Task Errors Summary] Org ID {organization_id}:\n" + "\n".join([f" - {str(e)[:500]}..." for e in errors])) # Log first 500 chars of each error

# --- End of the process_leads_background function definition --
