"""
VTU Marks Extraction Module
This module extracts marks from result page screenshots using a Hugging Face vision-capable
chat model (via huggingface_hub InferenceClient).

It processes screenshots and saves structured JSON output for each USN.

Process:
1. Load screenshot image
2. Send to Hugging Face Inference API with an image + strict-JSON prompt
3. Parse and validate JSON response
4. Save to JSON file for later aggregation
"""

import sys
import os
import re
import json
import base64
from pathlib import Path
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

# ==============================================
# CONFIGURATION
# ==============================================
# Folder to store JSON output files (one per USN screenshot)
JSON_OUTPUT_FOLDER = "gemini_json_results"

# Ensure the output folder exists (creates if it doesn't exist)
os.makedirs(JSON_OUTPUT_FOLDER, exist_ok=True)
print(f"[info] Output directory created/verified: {JSON_OUTPUT_FOLDER}")


# ==============================================
# STEP 0: Load HF Token and Initialize Hugging Face Client
# ==============================================
def _load_env() -> None:
    """
    Load env vars from the current working directory .env file.
    """
    cwd_env_path = Path(os.getcwd()) / ".env"
    if cwd_env_path.exists():
        load_dotenv(dotenv_path=cwd_env_path)
    else:
        print(f"[warn] No .env file found in CWD: {cwd_env_path}")

_load_env()

HF_TOKEN = os.getenv("HF_TOKEN")
if not HF_TOKEN:
    print("ERROR: No HF token found. Add this to your CWD .env file:\nHF_TOKEN=your_huggingface_token")
    sys.exit(1)

HF_MODEL_ID = os.getenv("HF_MODEL_ID", "meta-llama/Llama-4-Scout-17B-16E-Instruct")

try:
    client = InferenceClient(
        model=HF_MODEL_ID,
        token=HF_TOKEN,
        base_url="https://router.huggingface.co"
    )

    print(f"[ok] Hugging Face client initialized: {HF_MODEL_ID}")
except Exception as e:
    print(f"ERROR: Failed to initialize Hugging Face client: {e}")
    sys.exit(1)


def _image_to_data_url(image_path: str) -> str:
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(image_path)[1].lower().lstrip(".") or "png"
    if ext == "jpg":
        ext = "jpeg"
    return f"data:image/{ext};base64,{b64}"


def _extract_marks_hf(image_path: str) -> dict:
    image_url = _image_to_data_url(image_path)

    prompt = """
You are an OCR + information extraction model specialized in VTU result screenshots.

Extract ONLY:
  - Student USN
  - Subject code
  - Internal marks
  - External marks
  - Total marks
  - Result (P/F/A)

Return ONLY strictly valid JSON (no markdown, no explanation) in this exact structure:
{
  "USN": "1AY23IS001",
  "Subjects": [
    {"Code": "BCS405A", "Internal": 40, "External": 49, "Total": 89, "Result": "P"}
  ]
}

Rules:
- Ignore footer or SGPA/CGPA rows.
- Internal/External/Total must be integers (not strings).
- Result must be one of: "P", "F", "A".
- Be extremely careful to extract the exact subject code from the column header.
"""

    resp = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        max_tokens=2048,
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    json_text = resp.choices[0].message.content

    # Some providers may still wrap; keep a defensive extractor.
    if isinstance(json_text, str):
        txt = json_text.strip()
        if txt.startswith("```"):
            txt = re.sub(r"^```[a-zA-Z]*\n", "", txt)
            txt = re.sub(r"\n```$", "", txt)
        match = re.search(r"\{.*\}", txt, re.DOTALL)
        if match:
            txt = match.group(0)
        return json.loads(txt)
    # If SDK returns already-parsed JSON (rare), accept it.
    return json_text


# ==============================================
# STEP 1: Validate CLI Input (image path)
# ==============================================
# This script expects one command-line argument: the screenshot file path
if len(sys.argv) != 2:
    print("Usage: python marks.py <screenshot_path>")
    sys.exit(1)

# Get screenshot path from command line
image_path = sys.argv[1]
if not os.path.exists(image_path):
    print(f"ERROR: File not found: {image_path}")
    sys.exit(1)

# Generate JSON output filename based on screenshot filename
# Example: "1AY23IS001_result.png" -> "1AY23IS001_result_gemini_output.json"
filename = os.path.basename(image_path)
json_basename = f"{os.path.splitext(filename)[0]}_gemini_output.json"
json_filename = os.path.join(JSON_OUTPUT_FOLDER, json_basename)


# ==============================================
# STEP 2: Send Image to Hugging Face API (or reuse JSON)
# ==============================================
# Check if JSON output already exists (optimization: avoid re-processing)
json_output = {}

if os.path.exists(json_filename):
    print(f"[info] Reading extracted output from existing JSON file: {json_filename}")
    try:
        # Load existing JSON to avoid redundant API calls
        with open(json_filename, "r", encoding="utf-8") as f:
            json_output = json.load(f)
        print("[ok] Output loaded from file. Execution complete.")
        sys.exit(0)  # Exit successfully if JSON file already exists
    except json.JSONDecodeError as e:
        # If JSON is corrupted, delete it and re-process
        print(f"ERROR: Error decoding existing JSON: {e}. Re-running API call.")
        os.remove(json_filename)
        json_output = {}

# If JSON doesn't exist, process the screenshot with Hugging Face
if not json_output:
    try:
        print("[info] Sending image to Hugging Face model...")
        json_output = _extract_marks_hf(image_path)
    except Exception as e:
        print(f"ERROR: Error during Hugging Face API call: {e}")
        sys.exit(1)

    # Save JSON output to file for later aggregation
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(json_output, f, indent=4)
    print(f"[ok] Output saved to JSON file: {json_filename}")
    
    # Exit successfully
    sys.exit(0)
