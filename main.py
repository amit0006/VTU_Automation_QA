"""
VTU Automation Main Processing Module
This module handles the core automation logic for processing USN lists:
1. Screenshot capture from VTU results website
2. CAPTCHA solving using Gemini AI
3. Mark extraction from screenshots
4. Progress tracking and status updates
"""

import time
import os
import openpyxl
import pandas as pd
import subprocess
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoAlertPresentException, UnexpectedAlertPresentException
from test import preprocess_image
from captcha import save_captcha_from_driver
from PIL import Image
import shutil
import google.generativeai as genai
import json 
import sys 
from dotenv import load_dotenv
from pathlib import Path 

# ==============================================
# GLOBAL MODEL INITIALIZATION
# ==============================================
# Load environment variables from .env file
load_dotenv() 

# Get Google API key for Gemini AI
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    # Use a warning instead of sys.exit(1) if running as a web service
    print("❌ No API key found. Add GOOGLE_API_KEY to your .env file or environment.")
    # Exit is fine if this script is the entry point
    # sys.exit(1) 

# Configure Gemini AI with the API key
genai.configure(api_key=api_key)

# Initialize the Model object globally for CAPTCHA solving and mark extraction
try:
    model = genai.GenerativeModel("gemini-2.5-flash")
    model.generate_content("ping")  # Test connection
    print("✅ Connected to gemini-2.5-flash successfully.")
except Exception as e:
    print(f"❌ Failed to connect to Gemini API: {e}")
    # sys.exit(1) # Uncomment if this script must fail immediately

# Global Variable Declarations
# Known subject names (used for validation/filtering if needed)
KNOWN_SUBJECTS = [
    "MATHEMATICS FOR COMPUTER SCIENCE", "DIGITAL DESIGN & COMPUTER ORGANIZATION",
    "OPERATING SYSTEMS", "DATA STRUCTURES AND APPLICATIONS",
    "DATA STRUCTURES LAB", "SOCIAL CONNECT AND RESPONSIBILITY",
    "YOGA", "OBJECT ORIENTED PROGRAMMING WITH JAVA",
    "DATA VISUALIZATION WITH PYTHON"
]

# Global Selenium WebDriver instance (initialized in run_pipeline)
driver = None

# Global Gemini model instance
model = model

# List of USNs to process (loaded from CSV)
USN_LIST = []

# VTU results URL (set in run_pipeline)
URL = ""

# Folder to store screenshots
SCREENSHOT_FOLDER = "screenshots"

# Job ID for status tracking (optional, set when called from API)
JOB_ID = None

# ==============================================
# HELPER FUNCTIONS
# ==============================================

def update_job_status(total_usns: int = 0, processed_usns: int = 0, current_usn: str = "", 
                      phase: str = "", screenshots_completed: int = 0, marks_extracted: int = 0):
    """
    Update the status file for the current job (if job_id is set).
    This function is called internally to track progress.
    
    Args:
        total_usns: Total number of USNs to process
        processed_usns: Number of USNs processed so far (for backward compatibility)
        current_usn: Currently processing USN
        phase: Current phase ("screenshots" or "extraction")
        screenshots_completed: Number of screenshots completed
        marks_extracted: Number of marks extracted
    """
    global JOB_ID
    if not JOB_ID:
        return  # No status tracking if not called from API
    
    try:
        # Import here to avoid circular dependency
        BASE_DIR = Path(__file__).resolve().parent
        STATUS_DIR = BASE_DIR / "job_status"
        STATUS_DIR.mkdir(exist_ok=True)
        status_file = STATUS_DIR / f"{JOB_ID}.json"
        
        # Calculate overall progress: screenshots (0-50%) + extraction (50-100%)
        # Each phase contributes 50% to total progress
        if total_usns > 0:
            screenshot_progress = (screenshots_completed / total_usns) * 50
            extraction_progress = (marks_extracted / total_usns) * 50
            progress_percentage = int(screenshot_progress + extraction_progress)
        else:
            progress_percentage = 0
        
        status_data = {
            "job_id": JOB_ID,
            "status": "processing",
            "total_usns": total_usns,
            "processed_usns": processed_usns,  # Keep for backward compatibility
            "current_usn": current_usn,
            "error": "",
            "phase": phase,  # Current phase: "screenshots" or "extraction"
            "screenshots_completed": screenshots_completed,
            "marks_extracted": marks_extracted,
            "progress_percentage": progress_percentage
        }
        
        with open(status_file, "w") as f:
            json.dump(status_data, f)
    except Exception as e:
        # Don't fail the main process if status update fails
        print(f"⚠️ Failed to update status: {e}")

def take_full_page_screenshot(usn):
    """
    Takes a full page screenshot using the active Selenium driver instance.
    
    Args:
        usn: University Seat Number (used for filename)
        
    Returns:
        True if screenshot saved successfully, False otherwise
    """
    global driver
    screenshot_path = os.path.join(SCREENSHOT_FOLDER, f"{usn}_result.png")
    
    # Use the native Selenium screenshot method
    # The large window size (1920x1080) ensures most content is captured
    try:
        driver.save_screenshot(screenshot_path) 
        print(f"✅ Screenshot saved at: {screenshot_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to save screenshot: {e}")
        return False

def get_captcha_text():
    """
    Extract CAPTCHA text from the VTU website using Gemini AI vision model.
    
    Process:
    1. Save CAPTCHA image from the webpage
    2. Preprocess the image to remove noise
    3. Use Gemini AI to read the text
    4. Clean and validate the extracted text
    
    Returns:
        CAPTCHA text string (6 characters) or None if extraction fails
    """
    global driver, model
    
    # Step 1: Save CAPTCHA image from the webpage
    saved = save_captcha_from_driver(driver)
    if not saved:
        print("❌ Failed to save CAPTCHA image.")
        return None

    # Step 2: Preprocess image to improve OCR accuracy
    processed_image_path = preprocess_image("captcha.png")
    if not processed_image_path:
        print("❌ Failed to preprocess CAPTCHA image.")
        return None

    try:
        # Step 3: Use Gemini vision model for OCR
        img = Image.open(processed_image_path)
        response = model.generate_content(["Read the text in this CAPTCHA image clearly and return only the text:", img])
        text = response.text.strip().replace(" ", "")
        
        # Step 4: Validate and truncate to expected length (6 characters)
        if len(text) > 6:
            text = text[:6]
            
        print(f"🔍 Gemini Detected CAPTCHA: {text}")
        return text
    except Exception as e:
        print(f"❌ CAPTCHA OCR with Gemini failed: {e}")
        return None

def handle_possible_alert():
    """
    Handle JavaScript alert dialogs that may appear on the page.
    Common alerts: "USN not found", "Invalid CAPTCHA", etc.
    
    Returns:
        Alert text if alert was present and dismissed, None otherwise
    """
    global driver
    try:
        alert = driver.switch_to.alert
        alert_text = alert.text
        alert.accept()  # Dismiss the alert
        print(f"⚠️ Alert Dismissed: {alert_text}")
        return alert_text
    except NoAlertPresentException:
        # No alert present, which is normal
        return None

# ==============================================
# MAIN AUTOMATION LOGIC
# ==============================================

def main():
    """
    Main automation function that processes all USNs in the list.
    
    Process:
    1. For each USN, capture screenshot from VTU results page
    2. Extract marks from screenshots using Gemini AI
    3. Save results to CSV file
    
    The function handles CAPTCHA solving, form submission, and error recovery.
    """
    global driver, USN_LIST, URL, JOB_ID

    results_data = []
    saved_usns = []
    total_usns = len(USN_LIST)
    screenshots_completed = 0
    marks_extracted = 0

    # Update initial status
    update_job_status(total_usns=total_usns, processed_usns=0, current_usn="Starting...", 
                      phase="screenshots", screenshots_completed=0, marks_extracted=0)

    # STEP 1: Save all screenshots
    for idx, usn in enumerate(USN_LIST, 1):
        print(f"\n🎯 Processing USN {idx}/{total_usns}: {usn}")
        
        # Update status with current USN and screenshot progress
        update_job_status(total_usns=total_usns, processed_usns=screenshots_completed, 
                          current_usn=usn, phase="screenshots", 
                          screenshots_completed=screenshots_completed, marks_extracted=0)
        
        attempts = 0
        screenshot_path = os.path.join(SCREENSHOT_FOLDER, f"{usn}_result.png")

        # Skip if screenshot already exists (optimization: avoid re-processing)
        if os.path.exists(screenshot_path):
            print(f"⏭️ Screenshot already exists: {screenshot_path}. Skipping Selenium.")
            saved_usns.append(usn)
            screenshots_completed += 1
            # Update status after skipping
            update_job_status(total_usns=total_usns, processed_usns=screenshots_completed, 
                              current_usn=usn, phase="screenshots", 
                              screenshots_completed=screenshots_completed, marks_extracted=0)
            continue

        # Retry loop: attempt up to 10 times per USN
        while attempts < 10:
            attempts += 1
            print(f"🔁 Attempt {attempts} for {usn}")

            try:
                # Clear cookies and navigate to URL (fresh session for each attempt)
                driver.delete_all_cookies()
                driver.get(URL)

                # Wait for form to load
                wait = WebDriverWait(driver, 10)
                wait.until(EC.presence_of_element_located((By.NAME, "lns")))

                # Extract and solve CAPTCHA
                captcha_text = get_captcha_text()
                if not captcha_text or len(captcha_text) != 6:
                    print("⚠️ Invalid CAPTCHA text length. Retrying...")
                    continue

                # Fill in form fields
                usn_input = driver.find_element(By.NAME, "lns")
                captcha_input = driver.find_element(By.NAME, "captchacode")
                submit_btn = driver.find_element(By.ID, "submit")

                usn_input.clear()
                captcha_input.clear()
                usn_input.send_keys(usn)
                captcha_input.send_keys(captcha_text)
                submit_btn.click()

                # Wait for result page to load
                print("✅ CAPTCHA accepted. Waiting for result page to load...")
                
                # Wait for results table to appear (indicates page loaded)
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "table-bordered")))
                
                # Small sleep for final rendering stability (reduced from longer waits)
                time.sleep(0.5)  # Optimized: reduced from 1 second
                
                # Check for alert after result page load (e.g., USN not found)
                try:
                    WebDriverWait(driver, 2).until(EC.alert_is_present())
                    alert_msg = handle_possible_alert()
                    print(f"❌ Alert after load (e.g., USN invalid): {alert_msg}")
                    continue 
                except TimeoutException:
                    pass  # No alert, which is good

                # Take screenshot of the result page
                print("🖼️ Capturing screenshot directly...")
                if take_full_page_screenshot(usn):
                    saved_usns.append(usn)
                    screenshots_completed += 1
                    # Update status after successful screenshot
                    update_job_status(total_usns=total_usns, processed_usns=screenshots_completed, 
                                      current_usn=usn, phase="screenshots", 
                                      screenshots_completed=screenshots_completed, marks_extracted=0)
                    break  # Success, move to next USN
                else:
                    continue  # Retry if screenshot failed to save

            except TimeoutException as te:
                print(f"❌ Timeout error (page element missing): {te}")
                # Check for alert again just in case the timeout was an alert loop
                handle_possible_alert() 
                continue
            except Exception as e:
                print(f"❌ Unexpected error occurred: {e}")
                continue

        # Check if max attempts reached
        if attempts >= 10:
            print(f"⚠️ Max attempts reached for {usn}. Moving on.")
            results_data.append({"USN": usn, "Result": "❌ Screenshot not saved"})
            screenshots_completed += 1
            # Update status even for failed screenshots
            update_job_status(total_usns=total_usns, processed_usns=screenshots_completed, 
                              current_usn=usn, phase="screenshots", 
                              screenshots_completed=screenshots_completed, marks_extracted=0)
        else:
            results_data.append({"USN": usn, "Result": "✅ Screenshot saved"})

    # Update status: Screenshots complete, starting extraction
    update_job_status(total_usns=total_usns, processed_usns=screenshots_completed, 
                      current_usn="Starting mark extraction...", phase="extraction", 
                      screenshots_completed=screenshots_completed, marks_extracted=0)

    # STEP 2: Extract marks from screenshots
    print("\n📊 Starting marks extraction for all saved screenshots...\n")
    marks_extracted = 0
    total_screenshots = len(saved_usns)
    
    for idx, usn in enumerate(saved_usns, 1):
        screenshot_path = os.path.join(SCREENSHOT_FOLDER, f"{usn}_result.png")
        
        # Update status with current USN being processed for mark extraction
        update_job_status(total_usns=total_usns, processed_usns=screenshots_completed, 
                          current_usn=usn, phase="extraction", 
                          screenshots_completed=screenshots_completed, marks_extracted=marks_extracted)
        
        try:
            # Call marks.py to extract marks using Gemini AI
            subprocess.run(["python", "marks.py", screenshot_path], check=True)
            print(f"✅ Marks extracted for {usn} ({idx}/{total_screenshots})")
            marks_extracted += 1
            
            # Update status after successful mark extraction
            update_job_status(total_usns=total_usns, processed_usns=screenshots_completed, 
                              current_usn=usn, phase="extraction", 
                              screenshots_completed=screenshots_completed, marks_extracted=marks_extracted)
        except Exception as e:
            print(f"❌ Failed to extract marks for {usn}: {e}")
            results_data.append({"USN": usn, "Result": "❌ Failed to extract marks"})
            # Still update status even if extraction failed
            marks_extracted += 1  # Count it as processed
            update_job_status(total_usns=total_usns, processed_usns=screenshots_completed, 
                              current_usn=usn, phase="extraction", 
                              screenshots_completed=screenshots_completed, marks_extracted=marks_extracted)

    # Save summary CSV
    df = pd.DataFrame(results_data)
    df.to_csv("vtu_results.csv", index=False)
    print("\n📁 All results saved to 'vtu_results.csv'")

    # Update status: All processing complete
    # Note: The status will be updated to "completed" by the app.py background task handler
    # But we update the phase to indicate completion
    update_job_status(total_usns=total_usns, processed_usns=screenshots_completed, 
                      current_usn="Processing complete", phase="completed", 
                      screenshots_completed=screenshots_completed, marks_extracted=marks_extracted)

    # Close browser
    driver.quit()


def run_pipeline(usn_csv_path: str, url: str, subject_codes_list: list, 
                 output_path: str = "vtu_results.csv", job_id: str = None): 
    """
    Main pipeline function that orchestrates the entire USN processing workflow.
    
    Process:
    1. Clean up old files and folders
    2. Initialize Selenium WebDriver
    3. Load USN list from CSV
    4. Capture screenshots for each USN
    5. Extract marks from screenshots
    6. Aggregate results into Excel file
    
    Args:
        usn_csv_path: Path to CSV file containing USN list
        url: VTU results website URL
        subject_codes_list: List of subject codes to filter/extract
        output_path: Path for output CSV (legacy, not used for Excel output)
        job_id: Optional job ID for status tracking (used by API)
        
    Returns:
        output_path: Path to the output file
    """
    global USN_LIST, URL, driver, SCREENSHOT_FOLDER, JOB_ID

    # Set job ID for status tracking
    JOB_ID = job_id

    EXCEL_FILE = "vtu_structured_results.xlsx"

    # ==========================================================
    # STEP 0: CLEANUP - Delete and Recreate Screenshots Folder
    # ==========================================================
    # Clean up old screenshots to ensure fresh start
    if os.path.exists(SCREENSHOT_FOLDER):
        try:
            shutil.rmtree(SCREENSHOT_FOLDER)
            print(f"🗑️ Deleted existing folder: {SCREENSHOT_FOLDER}")
        except OSError as e:
            print(f"❌ Error deleting old screenshot folder: {e}. Attempting to continue.")
            
    os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)
    print(f"📘 Created clean folder: {SCREENSHOT_FOLDER}")

    # Clean up old Excel file
    if os.path.exists(EXCEL_FILE):
        os.remove(EXCEL_FILE)
        print(f"🗑️ Deleted old file: {EXCEL_FILE}")

    # Create new Excel workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Results"
    wb.save(EXCEL_FILE)
    print(f"📘 Created new file: {EXCEL_FILE}")

    # ==========================================================
    # STEP 1: SETUP SELENIUM WEBDRIVER
    # ==========================================================
    # Configure Chrome options for headless operation in Docker/container environment
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")  # New headless mode (more stable)
    options.add_argument("--disable-gpu")  # Disable GPU acceleration
    options.add_argument("--no-sandbox")  # Required for Docker
    options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
    options.add_argument("--window-size=1920,1080")  # Large window size for full page capture
    options.add_argument("--display=:99")  # Connect to XVFB virtual display

    # Use explicit path for ChromeDriver (pre-installed in container)
    service = Service(executable_path="/usr/bin/chromedriver") 

    # Enable browser logging for debugging
    caps = webdriver.DesiredCapabilities.CHROME.copy()
    caps['goog:loggingPrefs'] = {'browser': 'ALL'}

    # Initialize Chrome WebDriver
    driver = webdriver.Chrome(service=service, options=options)
    print("✅ Chrome WebDriver initialized")
    
    # ==========================================================
    # STEP 2: LOAD USN LIST FROM CSV
    # ==========================================================
    import pandas as pd 

    # Load USNs from CSV file
    usn_df = pd.read_csv(usn_csv_path)
    USN_LIST = usn_df['USN'].dropna().astype(str).tolist()
    print(f"📋 Loaded {len(USN_LIST)} USNs from CSV")

    # Set URL as global variable for use in main()
    URL = url

    # ==========================================================
    # STEP 3: RUN MAIN AUTOMATION LOGIC
    # ==========================================================
    # This will capture screenshots and extract marks
    main()  

    # ==========================================================
    # STEP 4: AGGREGATE JSON FILES INTO EXCEL
    # ==========================================================
    print("📊 Starting JSON to Excel aggregation...")
    
    # Convert subject codes list to JSON string for subprocess
    subject_codes_json = json.dumps(subject_codes_list)
    
    try:
        # Call json_to_excel.py to aggregate all JSON results into Excel
        subprocess.run(
            ["python", "json_to_excel.py", subject_codes_json],
            check=True
        )
        print("✅ Excel aggregation complete.")
    except Exception as e:
        print(f"❌ Failed to run json_to_excel.py: {e}")

    # Return the output path for download
    return output_path
