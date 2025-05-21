# app/routers/leads.py
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import List, Optional # Keep other imports as needed
import pandas as pd
import io # For reading file in memory as bytes
from pydantic import EmailStr, ValidationError # For validating email within the loop

# Import your project schemas, database, get_current_user, logger
from app import schemas # Assuming your BulkImportSummary and LeadInput are in schemas
from app.db import database
from app.db.database import get_db # Adjust path as needed
from app.schemas import UserPublic # For current_user
from app.auth.dependencies import get_current_user
from app.utils.logger import logger

router = APIRouter(
    prefix="/api/v1/leads",
    tags=["Lead Management"]
)

@router.get("/api/v1/leads", ...) # Or whatever the path is
async def read_leads(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db), # <--- IMPORTANT
    current_user: UserPublic = Depends(get_current_active_user) # <--- IMPORTANT
):
    # ...
    leads = crud.get_leads_by_organization(db, organization_id=current_user.organization_id, skip=skip, limit=limit) # <--- Pass db
    # ...
    return leads

@router.post(
    "/upload-csv/",
    response_model=schemas.BulkImportSummary,
    summary="Bulk Import Leads from CSV",
    description="Uploads a CSV file to bulk import/update leads for the current user's organization."
)
async def upload_leads_csv( # Use async because of await file.read()
    file: UploadFile = File(..., description="CSV file containing leads. Expected columns: Name, Email, Company, Title, Source, etc."),
    current_user: schemas.UserPublic = Depends(get_current_user)
):
    org_id = current_user.organization_id
    logger.info(f"API: Received CSV upload '{file.filename}' for lead import for Org ID: {org_id}")

    if not file.filename.lower().endswith('.csv'):
        logger.warning(f"API: Invalid file type uploaded for Org ID {org_id}: {file.filename}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file type. Please upload a CSV file.")

    contents = await file.read()
    buffer = io.BytesIO(contents) # pandas can read from a BytesIO buffer

    summary = schemas.BulkImportSummary(
        total_rows_in_file=0,
        rows_attempted=0,
        successfully_imported_or_updated=0,
        failed_imports=0,
        errors=[]
    )

    try:
        # Read CSV into pandas DataFrame. na_filter=False keeps empty strings as '', not NaN.
        # dtype=str reads all columns as strings initially to avoid type errors.
        df = pd.read_csv(buffer, na_filter=False, dtype=str)
        summary.total_rows_in_file = len(df) # Actual number of data rows (excluding header if pandas skips it)
        logger.info(f"API: Processing {len(df)} data rows from CSV for Org ID: {org_id}")

        # Normalize column names: lowercase and replace spaces/hyphens with underscores
        # This makes matching more robust
        original_columns = list(df.columns)
        df.columns = [str(col).lower().replace(' ', '_').replace('-', '_') for col in df.columns]
        
        # Define expected columns based on your LeadInput schema (or a subset for import)
        # Ensure 'email' is a required column for processing.
        required_csv_cols = {'email'}
        actual_csv_cols = set(df.columns)

        if not required_csv_cols.issubset(actual_csv_cols):
            missing = list(required_csv_cols - actual_csv_cols)
            logger.error(f"API: CSV for Org ID {org_id} missing required columns: {missing}")
            summary.errors.append(schemas.BulkImportErrorDetail(error=f"CSV is missing required columns: {', '.join(missing)}"))
            summary.failed_imports = summary.total_rows_in_file # All rows fail if header is bad
            # Return 400 Bad Request if essential columns are missing
            # raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"CSV missing required columns: {', '.join(missing)}")
            # Or, if you want to report it in the summary, proceed carefully
            return summary # Or raise HTTP Exception


        for index, row in df.iterrows():
            summary.rows_attempted += 1
            lead_data_dict = {}
            
            # Map CSV columns to your LeadInput schema fields (adjust as needed)
            # Use .get() with a default of None for optional fields
            lead_data_dict['email'] = row.get('email', '').strip()
            lead_data_dict['name'] = row.get('name', '').strip() or None
            lead_data_dict['company'] = row.get('company', '').strip() or None
            lead_data_dict['title'] = row.get('title', '').strip() or None
            lead_data_dict['source'] = row.get('source', '').strip() or "CSV Import" # Default source
            lead_data_dict['linkedin_profile'] = row.get('linkedin_profile', '').strip() or None
            lead_data_dict['company_size'] = row.get('company_size', '').strip() or None
            lead_data_dict['industry'] = row.get('industry', '').strip() or None
            lead_data_dict['location'] = row.get('location', '').strip() or None
            
            # Optional: Handle boolean fields from CSV (e.g., 'true'/'false', '1'/'0')
            # matched_str = str(row.get('matched', 'false')).lower()
            # lead_data_dict['matched'] = matched_str in ['true', '1', 'yes']
            # appointment_confirmed_str = str(row.get('appointment_confirmed', 'false')).lower()
            # lead_data_dict['appointment_confirmed'] = appointment_confirmed_str in ['true', '1', 'yes']


            # Basic validation (Email is crucial)
            if not lead_data_dict['email']:
                logger.warning(f"API: Row {index + 2} for Org {org_id} skipped: Email is missing.")
                summary.errors.append(schemas.BulkImportErrorDetail(row_number=index + 2, error="Email is missing."))
                summary.failed_imports += 1
                continue

            try:
                # Validate with Pydantic EmailStr (or a subset of LeadInput)
                schemas.LeadInput(**{"email": lead_data_dict['email'], "name": lead_data_dict.get('name')}) # Minimal validation example
            except ValidationError as e:
                logger.warning(f"API: Row {index + 2} for Org {org_id} has invalid data: {e.errors()}")
                summary.errors.append(schemas.BulkImportErrorDetail(row_number=index + 2, email=lead_data_dict['email'], error=str(e.errors())))
                summary.failed_imports += 1
                continue

            # Call database.save_lead (which is an upsert)
            saved_lead = database.save_lead(lead_data=lead_data_dict, organization_id=org_id)
            if saved_lead:
                summary.successfully_imported_or_updated += 1
            else:
                # This case means database.save_lead itself returned None (logged an error)
                logger.error(f"API: Row {index + 2} for Org {org_id}, Email {lead_data_dict['email']} failed to save in DB.")
                summary.errors.append(schemas.BulkImportErrorDetail(row_number=index + 2, email=lead_data_dict['email'], error="Database save operation failed."))
                summary.failed_imports += 1
        
        logger.info(f"API: CSV import complete for Org ID {org_id}. Summary: {summary.dict()}")

    except pd.errors.EmptyDataError:
        logger.warning(f"API: Uploaded CSV for Org ID {org_id} is empty or has no data rows.")
        summary.errors.append(schemas.BulkImportErrorDetail(error="Uploaded CSV file is empty or contains no data rows."))
        # No rows attempted, all failed if file had rows but pandas couldn't read them.
        if summary.total_rows_in_file > 0 and summary.rows_attempted == 0:
             summary.failed_imports = summary.total_rows_in_file

    except Exception as e:
        logger.error(f"API: Error processing CSV for Org ID {org_id}: {e}", exc_info=True)
        # If a general error occurs, assume all attempted rows might have failed
        summary.errors.append(schemas.BulkImportErrorDetail(error=f"An unexpected error occurred during CSV processing: {str(e)}"))
        # Adjust counts if possible, or mark all as failed.
        # This is a simplification; better error tracking could isolate how many failed before the exception.
        summary.failed_imports = summary.rows_attempted - summary.successfully_imported_or_updated
        # Consider returning HTTP 500 if it's an unhandled server-side processing error
        # For now, return summary
        
    finally:
         buffer.close() # Important to close the buffer
         await file.close()

    return summary
