from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
from pathlib import Path

# Import the run_pipeline function from main.py
from main import run_pipeline

BASE_DIR = Path(__file__).resolve().parent

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


@app.get("/", response_class=HTMLResponse)
def serve_index():
    """Serve the project's index.html so frontend and backend share the same origin."""
    index_path = BASE_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>Index not found</h1>", status_code=404)
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.post("/process/")
async def process_file(
    usn_csv: UploadFile = File(...),
    url: str = Form(...),
    subject_codes: str = Form(...),
):
    """Accepts the CSV file, URL and subject codes, runs the pipeline, and returns the Excel file."""

    # Save uploaded CSV to a temp file
    temp_csv_path = f"temp_{usn_csv.filename}"
    with open(temp_csv_path, "wb") as buffer:
        shutil.copyfileobj(usn_csv.file, buffer)

    # Parse subject codes into list
    codes_list = [code.strip().upper() for code in subject_codes.replace(';', ',').split(',') if code.strip()]

    print(f"Received subject codes: {codes_list}")

    # Run the pipeline (Synchronous - only reliable for few USNs)
    try:
        run_pipeline(temp_csv_path, url, codes_list)
    finally:
        # cleanup temp file if exists
        try:
            if os.path.exists(temp_csv_path):
                os.remove(temp_csv_path)
        except Exception:
            pass

    # Return the generated Excel file
    output_file = BASE_DIR / "vtu_structured_results.xlsx"
    if not output_file.exists():
        return {"error": "Result file not found after processing."}

    return FileResponse(
        path=str(output_file),
        filename="vtu_structured_results.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
