"""
VTU Automation FastAPI Application
This module provides the REST API endpoints for processing USN lists and generating result Excel files.
It handles file uploads, background processing, and status tracking for long-running tasks.
"""

from fastapi import FastAPI, File, UploadFile, Form, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import json
import uuid
from pathlib import Path
from typing import Dict

# Import the run_pipeline function from main.py
from main import run_pipeline

BASE_DIR = Path(__file__).resolve().parent

# Status file directory for tracking job progress
STATUS_DIR = BASE_DIR / "job_status"
STATUS_DIR.mkdir(exist_ok=True)

app = FastAPI()

# Allow CORS for local development. Restrict this in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (serve index.html, script.js, style.css, etc.) under /static
app.mount("/static", StaticFiles(directory=str(BASE_DIR)), name="static")


def get_status_file_path(job_id: str) -> Path:
    """Get the path to the status file for a given job ID."""
    return STATUS_DIR / f"{job_id}.json"


def update_status(job_id: str, status: str, total_usns: int = 0, processed_usns: int = 0, 
                  current_usn: str = "", error: str = "", phase: str = "", 
                  screenshots_completed: int = 0, marks_extracted: int = 0):
    """
    Update the status file for a job.
    
    Args:
        job_id: Unique identifier for the job
        status: Current status (pending, processing, completed, failed)
        total_usns: Total number of USNs to process
        processed_usns: Number of USNs processed so far (for backward compatibility)
        current_usn: Currently processing USN
        error: Error message if any
        phase: Current phase ("screenshots" or "extraction")
        screenshots_completed: Number of screenshots completed
        marks_extracted: Number of marks extracted
    """
    # Calculate overall progress: screenshots (0-50%) + extraction (50-100%)
    # Each phase contributes 50% to total progress
    if total_usns > 0:
        screenshot_progress = (screenshots_completed / total_usns) * 50
        extraction_progress = (marks_extracted / total_usns) * 50
        progress_percentage = int(screenshot_progress + extraction_progress)
    else:
        progress_percentage = 0
    
    status_data = {
        "job_id": job_id,
        "status": status,
        "total_usns": total_usns,
        "processed_usns": processed_usns,  # Keep for backward compatibility
        "current_usn": current_usn,
        "error": error,
        "phase": phase,  # Current phase: "screenshots" or "extraction"
        "screenshots_completed": screenshots_completed,
        "marks_extracted": marks_extracted,
        "progress_percentage": progress_percentage
    }
    status_file = get_status_file_path(job_id)
    with open(status_file, "w") as f:
        json.dump(status_data, f)


def process_usns_background(job_id: str, temp_csv_path: str, url: str, codes_list: list):
    """
    Background task to process USNs.
    This function runs the pipeline and updates status periodically.
    
    Args:
        job_id: Unique identifier for the job
        temp_csv_path: Path to the temporary CSV file with USNs
        url: VTU results URL
        codes_list: List of subject codes to filter
    """
    try:
        # Update status to processing (initial state)
        update_status(job_id, "processing", total_usns=0, processed_usns=0, 
                     current_usn="Initializing...", phase="screenshots", 
                     screenshots_completed=0, marks_extracted=0)
        
        # Run the pipeline (this will internally update status with progress)
        run_pipeline(temp_csv_path, url, codes_list, job_id=job_id)
        
        # Mark as completed - get final counts from status file
        try:
            status_file = get_status_file_path(job_id)
            if status_file.exists():
                with open(status_file, "r") as f:
                    final_status = json.load(f)
                # Update to completed status
                update_status(job_id, "completed", 
                            total_usns=final_status.get("total_usns", 0),
                            processed_usns=final_status.get("screenshots_completed", 0),
                            current_usn="",
                            phase="completed",
                            screenshots_completed=final_status.get("screenshots_completed", 0),
                            marks_extracted=final_status.get("marks_extracted", 0))
        except Exception as e:
            print(f"⚠️ Could not update final status: {e}")
            # Fallback: mark as completed with basic info
            update_status(job_id, "completed", phase="completed")
        
    except Exception as e:
        # Mark as failed with error message
        update_status(job_id, "failed", error=str(e), phase="failed")
        print(f"❌ Error in background task: {e}")
    finally:
        # Cleanup temp file if exists
        try:
            if os.path.exists(temp_csv_path):
                os.remove(temp_csv_path)
        except Exception:
            pass


@app.get("/", response_class=HTMLResponse)
def serve_index():
    """Serve the project's index.html so frontend and backend share the same origin."""
    index_path = BASE_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>Index not found</h1>", status_code=404)
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.post("/process/")
async def process_file(
    background_tasks: BackgroundTasks,
    usn_csv: UploadFile = File(...),
    url: str = Form(...),
    subject_codes: str = Form(...),
):
    """
    Accepts the CSV file, URL and subject codes, starts background processing, and returns a job ID.
    The frontend should poll /status/{job_id} to check progress.
    """

    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Save uploaded CSV to a temp file
    temp_csv_path = f"temp_{job_id}_{usn_csv.filename}"
    with open(temp_csv_path, "wb") as buffer:
        shutil.copyfileobj(usn_csv.file, buffer)

    # Parse subject codes into list
    codes_list = [code.strip().upper() for code in subject_codes.replace(';', ',').split(',') if code.strip()]

    print(f"Received subject codes: {codes_list}")
    print(f"Job ID: {job_id}")

    # Initialize status as pending
    update_status(job_id, "pending", total_usns=0, processed_usns=0, 
                 current_usn="Starting...", phase="screenshots", 
                 screenshots_completed=0, marks_extracted=0)

    # Add background task to process USNs
    background_tasks.add_task(process_usns_background, job_id, temp_csv_path, url, codes_list)

    # Return job ID immediately so frontend can poll for status
    return {"job_id": job_id, "message": "Processing started. Please poll /status/{job_id} for progress."}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """
    Get the current status of a processing job.
    
    Args:
        job_id: Unique identifier for the job
        
    Returns:
        JSON with status information including progress
    """
    status_file = get_status_file_path(job_id)
    
    if not status_file.exists():
        return JSONResponse(
            {"error": "Job not found"},
            status_code=404
        )
    
    try:
        with open(status_file, "r") as f:
            status_data = json.load(f)
        
        # If completed (by status or phase), check if file exists
        if status_data.get("status") == "completed" or status_data.get("phase") == "completed":
            output_file = BASE_DIR / "vtu_structured_results.xlsx"
            if output_file.exists():
                status_data["file_ready"] = True
                # Ensure status is set to completed if phase is completed
                if status_data.get("phase") == "completed" and status_data.get("status") != "completed":
                    status_data["status"] = "completed"
            else:
                status_data["file_ready"] = False
        else:
            status_data["file_ready"] = False
        
        return status_data
    except Exception as e:
        return JSONResponse(
            {"error": f"Error reading status: {str(e)}"},
            status_code=500
        )


@app.get("/download/{job_id}")
async def download_file(job_id: str):
    """
    Download the generated Excel file for a completed job.
    
    Args:
        job_id: Unique identifier for the job
        
    Returns:
        Excel file if job is completed, error otherwise
    """
    status_file = get_status_file_path(job_id)
    
    if not status_file.exists():
        return JSONResponse(
            {"error": "Job not found"},
            status_code=404
        )
    
    try:
        with open(status_file, "r") as f:
            status_data = json.load(f)
        
        if status_data.get("status") != "completed":
            return JSONResponse(
                {"error": f"Job not completed. Current status: {status_data.get('status')}"},
                status_code=400
            )
        
        # Return the generated Excel file
        output_file = BASE_DIR / "vtu_structured_results.xlsx"
        if not output_file.exists():
            return JSONResponse(
                {"error": "Result file not found after processing."},
                status_code=404
            )

        return FileResponse(
            path=str(output_file),
            filename="vtu_structured_results.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        return JSONResponse(
            {"error": f"Error: {str(e)}"},
            status_code=500
        )
