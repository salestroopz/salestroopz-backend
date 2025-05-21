# app/routers/leads.py
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query # Added Query
from typing import List, Optional
import pandas as pd
import io
from pydantic import EmailStr, ValidationError
from sqlalchemy.orm import Session # <--- IMPORTED Session

# Import your project schemas, database, get_current_user, logger
from app.schemas import ( # <--- EXPLICIT SCHEMA IMPORTS
    LeadResponse, LeadInput, BulkImportSummary, BulkImportErrorDetail, UserPublic
)
# from app.db import database # Your CRUD/DB functions
from app.db.database import get_db
from app.auth.dependencies import get_current_user # Assuming this provides UserPublic
from app.crud import lead as lead_crud # <--- EXAMPLE: Assuming app/crud/lead.py
from app.utils.logger import logger

router = APIRouter(
    prefix="/api/v1/leads", # Set prefix for all routes in this router
    tags=["Lead Management"]
)

# Corrected GET /leads endpoint
@router.get("/", response_model=List[LeadResponse]) # Path is now relative to router prefix
async def read_leads(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500), # Added Query for pagination
    db: Session = Depends(get_db),
    current_user: UserPublic = Depends(get_current_user) # Use get_current_user for consistency
):
    logger.info(f"API: Fetching leads for Org ID: {current_user.organization_id}, skip: {skip}, limit: {limit}")
    leads = lead_crud.get_leads_by_organization(
        db=db,
        organization_id=current_user.organization_id,
        skip=skip,
        limit=limit
    )
    # Pydantic will automatically convert list of ORM objects to List[LeadResponse]
    return leads

@router.post(
    "/upload-csv/",
    response_model=BulkImportSummary, # Use direct name after import
    summary="Bulk Import Leads from CSV",
    description="Uploads a CSV file to bulk import/update leads for the current user's organization."
)
async def upload_leads_csv(
    file: UploadFile = File(..., description="CSV file with leads. Columns: Name, Email, Company, etc."),
    db: Session = Depends(get_db), # <--- ADDED db session
    current_user: UserPublic = Depends(get_current_user) # Use direct name
):
    org_id = current_user.organization_id
    logger.info(f"API: CSV upload '{file.filename}' for lead import, Org ID: {org_id}")

    if not file.filename.lower().endswith('.csv'):
        logger.warning(f"API: Invalid file type uploaded for Org ID {org_id}: {file.filename}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file type. Please upload a CSV file.")

    contents = await file.read()
    buffer = io.BytesIO(contents)

    summary = BulkImportSummary( # Use direct name
        total_rows_in_file=0, rows_attempted=0,
        successfully_imported_or_updated=0, failed_imports=0, errors=[]
    )

    try:
        df = pd.read_csv(buffer, na_filter=False, dtype=str)
        summary.total_rows_in_file = len(df)
        logger.info(f"API: Processing {len(df)} data rows from CSV for Org ID: {org_id}")

        df.columns = [str(col).lower().replace(' ', '_').replace('-', '_') for col in df.columns]
        
        required_csv_cols = {'email'}
        if not required_csv_cols.issubset(set(df.columns)):
            missing = list(required_csv_cols - set(df.columns))
            err_msg = f"CSV missing required columns: {', '.join(missing)}"
            logger.error(f"API: CSV for Org ID {org_id} error: {err_msg}")
            summary.errors.append(BulkImportErrorDetail(error=err_msg)) # Use direct name
            summary.failed_imports = summary.total_rows_in_file
            return summary # Or raise HTTPException

        for index, row_series in df.iterrows():
            row = row_series.to_dict() # Convert Series to dict for .get()
            summary.rows_attempted += 1
            
            lead_data_dict = {
                'email': str(row.get('email', '')).strip(),
                'name': str(row.get('name', '')).strip() or None,
                'company': str(row.get('company', '')).strip() or None,
                'title': str(row.get('title', '')).strip() or None,
                'source': str(row.get('source', '')).strip() or "CSV Import",
                'linkedin_profile': str(row.get('linkedin_profile', '')).strip() or None,
                'company_size': str(row.get('company_size', '')).strip() or None,
                'industry': str(row.get('industry', '')).strip() or None,
                'location': str(row.get('location', '')).strip() or None,
            }

            if not lead_data_dict['email']:
                logger.warning(f"API: Row {index + 2} Org {org_id} skipped: Email missing.")
                summary.errors.append(BulkImportErrorDetail(row_number=index + 2, error="Email is missing."))
                summary.failed_imports += 1
                continue

            try:
                # Attempt to parse into LeadInput to leverage Pydantic validation
                lead_input_obj = LeadInput(**lead_data_dict) # Use direct name
            except ValidationError as e:
                logger.warning(f"API: Row {index + 2} Org {org_id} invalid data: {e.errors()}")
                summary.errors.append(BulkImportErrorDetail(row_number=index + 2, email=lead_data_dict['email'], error=str(e.errors())))
                summary.failed_imports += 1
                continue

            # Assuming lead_crud.save_lead (upsert) takes db, organization_id, and lead_data (Pydantic model or dict)
            saved_lead = lead_crud.save_lead(
                db=db,
                organization_id=org_id,
                lead_in=lead_input_obj # Pass validated Pydantic model
            )
            if saved_lead:
                summary.successfully_imported_or_updated += 1
            else:
                logger.error(f"API: Row {index + 2} Org {org_id}, Email {lead_input_obj.email} failed DB save.")
                summary.errors.append(BulkImportErrorDetail(row_number=index + 2, email=lead_input_obj.email, error="Database save failed."))
                summary.failed_imports += 1
        
        logger.info(f"API: CSV import complete Org ID {org_id}. Summary: {summary.model_dump_json(indent=2)}") # Pydantic v2

    except pd.errors.EmptyDataError:
        logger.warning(f"API: Uploaded CSV Org ID {org_id} empty.")
        summary.errors.append(BulkImportErrorDetail(error="Uploaded CSV file is empty."))
        if summary.total_rows_in_file > 0 and summary.rows_attempted == 0:
             summary.failed_imports = summary.total_rows_in_file
    except Exception as e:
        logger.error(f"API: Error processing CSV Org ID {org_id}: {e}", exc_info=True)
        summary.errors.append(BulkImportErrorDetail(error=f"Unexpected error: {str(e)}"))
        summary.failed_imports = summary.rows_attempted - summary.successfully_imported_or_updated
    finally:
         buffer.close()
         await file.close()

    return summary
