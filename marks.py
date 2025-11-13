"""
VTU Marks Extraction Module
This module extracts marks from result page screenshots using Gemini AI vision model.
It processes screenshots and saves structured JSON output for each USN.

Process:
1. Load screenshot image
2. Send to Gemini AI for OCR and mark extraction
3. Parse and validate JSON response
4. Save to JSON file for later aggregation
"""

import sys
import os
import re
import json
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image

# ==============================================
# CONFIGURATION
# ==============================================
# Folder to store JSON output files (one per USN screenshot)
# Use absolute path for production compatibility
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_OUTPUT_FOLDER = os.path.join(BASE_DIR, "gemini_json_results")

# Ensure the output folder exists (creates if it doesn't exist)
os.makedirs(JSON_OUTPUT_FOLDER, exist_ok=True)
print(f"📁 Output directory created/verified: {JSON_OUTPUT_FOLDER}")


# ==============================================
# STEP 0: Load API Key and Initialize Gemini Model
# ==============================================
# Load environment variables from .env file
load_dotenv()

# Get API key from environment (check for API_KEY first, then GOOGLE_API_KEY)
api_key = os.getenv("API_KEY")
if not api_key:
    # Use the same error message logic as your run_pipeline structure
    print("❌ No API key found. Add this line to your .env file:\nAPI_KEY=your_actual_key")
    sys.exit(1)

# Configure Gemini AI with the API key
genai.configure(api_key=api_key)

# Try to initialize Gemini model (prefer lite version for faster processing)
try:
    print("🔹 Trying gemini-2.5-flash-lite ...")
    model = genai.GenerativeModel("gemini-2.5-flash-lite")
    model.generate_content("ping")  # Test connection
    print("✅ Connected to gemini-2.5-flash-lite successfully.")
except Exception as e:
    # Fallback to full flash model if lite is not available
    print(f"⚠️ gemini-2.5-flash-lite not available. Falling back to gemini-2.5-flash. ({e})")
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        model.generate_content("ping")
        print("✅ Connected to gemini-2.5-flash successfully.")
    except Exception as e_pro:
        print(f"❌ Failed to connect to any model. Error: {e_pro}")
        sys.exit(1)


# ==============================================
# STEP 1: Validate CLI Input (image path)
# ==============================================
# This script expects one command-line argument: the screenshot file path
if len(sys.argv) != 2:
    print("❌ Usage: python marks.py <screenshot_path>")
    sys.exit(1)

# Get screenshot path from command line
image_path = sys.argv[1]
if not os.path.exists(image_path):
    print(f"❌ File not found: {image_path}")
    sys.exit(1)

# Generate JSON output filename based on screenshot filename
# Example: "1AY23IS001_result.png" -> "1AY23IS001_result_gemini_output.json"
filename = os.path.basename(image_path)
json_basename = f"{os.path.splitext(filename)[0]}_gemini_output.json"
json_filename = os.path.join(JSON_OUTPUT_FOLDER, json_basename)


# ==============================================
# STEP 2: Send Image to Gemini API (or reuse JSON)
# ==============================================
# Check if JSON output already exists (optimization: avoid re-processing)
json_output = {}

if os.path.exists(json_filename):
    print(f"⏳ Reading Gemini output from existing JSON file: {json_filename}")
    try:
        # Load existing JSON to avoid redundant API calls
        with open(json_filename, "r", encoding="utf-8") as f:
            json_output = json.load(f)
        print("✅ Gemini output loaded from file. Execution complete.")
        sys.exit(0)  # Exit successfully if JSON file already exists
    except json.JSONDecodeError as e:
        # If JSON is corrupted, delete it and re-process
        print(f"❌ Error decoding existing JSON: {e}. Re-running API call.")
        os.remove(json_filename)
        json_output = {}

# If JSON doesn't exist, process the screenshot with Gemini AI
if not json_output:
    print("📤 Sending image to Gemini API...")
    img = Image.open(image_path)

    # Detailed prompt for Gemini AI to extract marks from screenshot
    prompt = """
    You are an OCR model specialized in VTU result extraction.
    Extract ONLY:
      - Student USN
      - Subject code
      - Internal marks
      - External marks
      - Total marks
      - Result (P/F/A)
    Return strictly valid JSON in this exact structure (no markdown, no explanation):

    {
      "USN": "1AY23IS001",
      "Subjects": [
        {"Code": "BCS405A", "Internal": 40, "External": 49, "Total": 89, "Result": "P"}
      ]
    }

    Rules:
    - Each subject must have correct internal and external marks.
    - Ignore footer or SGPA/CGPA rows.
    - Internal/External/Total marks should be integers. Result should be a string ("P", "F", or "A").
    - Be extremely careful to extract the exact subject code from the column header.
    """ 

    try:
        # Send image and prompt to Gemini AI
        response = model.generate_content([prompt, img])
        result_text = response.text.strip()
    except Exception as e:
        print(f"❌ Error during Gemini API call: {e}")
        sys.exit(1)

    # Clean up response: remove markdown code fences if present
    if result_text.startswith("```"):
        result_text = re.sub(r"^```[a-zA-Z]*\n", "", result_text)
        result_text = re.sub(r"\n```$", "", result_text)
    
    # Extract JSON object from response (in case there's extra text)
    match = re.search(r"\{.*\}", result_text, re.DOTALL)
    if match:
        result_text = match.group(0)

    # Parse JSON response
    try:
        json_output = json.loads(result_text)
    except json.JSONDecodeError:
        print("❌ Gemini did not return valid JSON. Raw output below:\n")
        print(result_text)
        sys.exit(1)

    # Save JSON output to file for later aggregation
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(json_output, f, indent=4)
    print(f"✅ Gemini output saved to JSON file: {json_filename}")
    
    # Exit successfully
    sys.exit(0)
