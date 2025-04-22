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
    """
    # ... (Keep the full implementation of the background task as provided before) ...
    print(f"[BG Task Start] Org ID: {organization_id}, User: {user_email}, Source: {source_type}")
    # ... try ... except ... finally ...
    pass # Placeholder for the full function body

        print(f"[BG Task Finish] Org ID: {organization_id}. Processed: {processed_count}, Errors: {len(errors)}")
        if errors: print(f"[BG Task Errors] Org ID {organization_id}:\n" + "\n".join([f" - {e}" for e in errors]))
    
