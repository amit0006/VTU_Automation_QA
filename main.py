# # URL = "https://results.vtu.ac.in/JJEcbcs25/index.php"
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
# REMOVED: from webdriver_manager.chrome import ChromeDriverManager
from test import preprocess_image
from captcha import save_captcha_from_driver
from PIL import Image
import shutil
import google.generativeai as genai
import json 
import sys 
from dotenv import load_dotenv 

# ==============================================
# GLOBAL MODEL INITIALIZATION
# ==============================================
load_dotenv() 

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    # Use a warning instead of sys.exit(1) if running as a web service
    print("❌ No API key found. Add GOOGLE_API_KEY to your .env file or environment.")
    # Exit is fine if this script is the entry point
    # sys.exit(1) 

genai.configure(api_key=api_key)

# Initialize the Model object globally
try:
    model = genai.GenerativeModel("gemini-2.5-flash")
    model.generate_content("ping") 
    print("✅ Connected to gemini-2.5-flash successfully.")
except Exception as e:
    print(f"❌ Failed to connect to Gemini API: {e}")
    # sys.exit(1) # Uncomment if this script must fail immediately

# Global Variable Declarations
KNOWN_SUBJECTS = [
    "MATHEMATICS FOR COMPUTER SCIENCE", "DIGITAL DESIGN & COMPUTER ORGANIZATION",
    "OPERATING SYSTEMS", "DATA STRUCTURES AND APPLICATIONS",
    "DATA STRUCTURES LAB", "SOCIAL CONNECT AND RESPONSIBILITY",
    "YOGA", "OBJECT ORIENTED PROGRAMMING WITH JAVA",
    "DATA VISUALIZATION WITH PYTHON"
]
driver = None
model = model # Use the globally initialized model
USN_LIST = []
URL = ""
SCREENSHOT_FOLDER = "screenshots" # Defined here for global use

# ==============================================
# HELPER FUNCTIONS
# ==============================================

def take_full_page_screenshot(usn):
    """Takes a full page screenshot using the active driver instance."""
    global driver
    screenshot_path = os.path.join(SCREENSHOT_FOLDER, f"{usn}_result.png")
    
    # CRITICAL: Use the native Selenium full-page screenshot
    try:
        # driver.get_screenshot_as_file is usually sufficient, but get_full_page...
        # ...is more reliable for scrolling content if supported by the driver.
        driver.save_screenshot(screenshot_path) 
        # For full-page, you might need Javascript scrolling if the site is complex.
        # However, we rely on the large --window-size and the display being loaded correctly.
        print(f"✅ Screenshot saved at: {screenshot_path}")
        return True
    except Exception as e:
        print(f"❌ Failed to save screenshot: {e}")
        return False

def get_captcha_text():
    """Extract CAPTCHA text using Gemini model (rest of function unchanged)"""
    global driver, model
    # ... (function body remains the same as your input) ...
    saved = save_captcha_from_driver(driver)
    if not saved:
        print("❌ Failed to save CAPTCHA image.")
        return None

    processed_image_path = preprocess_image("captcha.png")
    if not processed_image_path:
        print("❌ Failed to preprocess CAPTCHA image.")
        return None

    try:
        img = Image.open(processed_image_path)
        # Use Gemini vision model for OCR
        response = model.generate_content(["Read the text in this CAPTCHA image clearly and return only the text:", img])
        text = response.text.strip().replace(" ", "")
        
        # Ensure it meets the expected length
        if len(text) > 6:
            text = text[:6]
            
        print(f"🔍 Gemini Detected CAPTCHA: {text}")
        return text
    except Exception as e:
        print(f"❌ CAPTCHA OCR with Gemini failed: {e}")
        return None

def handle_possible_alert():
    """Handle alert if present."""
    global driver
    try:
        alert = driver.switch_to.alert
        alert_text = alert.text
        alert.accept()
        print(f"⚠️ Alert Dismissed: {alert_text}")
        return alert_text
    except NoAlertPresentException:
        return None

# ==============================================
# MAIN AUTOMATION LOGIC
# ==============================================

def main():
    global driver, USN_LIST, URL

    results_data = []
    saved_usns = []

    # STEP 1: Save all screenshots
    for usn in USN_LIST:
        print(f"\n🎯 Processing USN: {usn}")
        attempts = 0
        screenshot_path = os.path.join(SCREENSHOT_FOLDER, f"{usn}_result.png")

        if os.path.exists(screenshot_path):
            print(f"⏭️ Screenshot already exists: {screenshot_path}. Skipping Selenium.")
            saved_usns.append(usn)
            continue

        while attempts < 10:
            attempts += 1
            print(f"🔁 Attempt {attempts} for {usn}")

            try:
                driver.delete_all_cookies()
                driver.get(URL)

                wait = WebDriverWait(driver, 10)
                wait.until(EC.presence_of_element_located((By.NAME, "lns")))

                captcha_text = get_captcha_text()
                if not captcha_text or len(captcha_text) != 6:
                    print("⚠️ Invalid CAPTCHA text length. Retrying...")
                    continue

                # Fill in form
                usn_input = driver.find_element(By.NAME, "lns")
                captcha_input = driver.find_element(By.NAME, "captchacode")
                submit_btn = driver.find_element(By.ID, "submit")

                usn_input.clear()
                captcha_input.clear()
                usn_input.send_keys(usn)
                captcha_input.send_keys(captcha_text)
                submit_btn.click()

                # --- NEW RELIABLE WAIT ---
                print("✅ CAPTCHA accepted. Waiting for result page to load...")
                
                # Wait until a critical element (like the results table) is present
                # Replace "table-bordered" with the specific class/ID/XPath of the marks table if known
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "table-bordered")))
                
                # Small sleep for final rendering stability
                time.sleep(1) 
                
                # Check for alert after result page load (e.g., USN not found)
                try:
                    WebDriverWait(driver, 2).until(EC.alert_is_present())
                    alert_msg = handle_possible_alert()
                    print(f"❌ Alert after load (e.g., USN invalid): {alert_msg}")
                    continue 
                except TimeoutException:
                    pass 

                # Take screenshot directly using the active driver
                print("🖼️ Capturing screenshot directly...")
                if take_full_page_screenshot(usn):
                    saved_usns.append(usn)
                    break
                else:
                    continue # Retry if screenshot failed to save

            except TimeoutException as te:
                print(f"❌ Timeout error (page element missing): {te}")
                # Check for alert again just in case the timeout was an alert loop
                handle_possible_alert() 
                continue
            except Exception as e:
                print(f"❌ Unexpected error occurred: {e}")
                continue

        if attempts >= 10:
            print(f"⚠️ Max attempts reached for {usn}. Moving on.")
            results_data.append({"USN": usn, "Result": "❌ Screenshot not saved"})
        else:
            results_data.append({"USN": usn, "Result": "✅ Screenshot saved"})

    # STEP 2: Extract marks from screenshots
    print("\n📊 Starting marks extraction for all saved screenshots...\n")
    # This loop is retained, assuming marks.py and json_to_excel.py are correct
    for usn in saved_usns:
        screenshot_path = os.path.join(SCREENSHOT_FOLDER, f"{usn}_result.png")
        try:
            # Note: You may need to wrap this in xvfb-run if marks.py uses pyautogui/gnome_screenshot
            # However, marks.py likely uses the Gemini API, so a direct call should be fine.
            subprocess.run(["python", "marks.py", screenshot_path], check=True)
            print(f"✅ Marks extracted for {usn}")
        except Exception as e:
            print(f"❌ Failed to extract marks for {usn}: {e}")
            results_data.append({"USN": usn, "Result": "❌ Failed to extract marks"})

    # Save summary
    df = pd.DataFrame(results_data)
    df.to_csv("vtu_results.csv", index=False)
    print("\n📁 All results saved to 'vtu_results.csv'")

    driver.quit()


def run_pipeline(usn_csv_path: str, url: str, subject_codes_list: list, output_path: str = "vtu_results.csv"): 

    global USN_LIST, URL, driver, SCREENSHOT_FOLDER

    EXCEL_FILE = "vtu_structured_results.xlsx"

    # ==========================================================
    # CRITICAL CLEANUP: Delete and Recreate Screenshots Folder
    # ==========================================================
    if os.path.exists(SCREENSHOT_FOLDER):
        try:
            shutil.rmtree(SCREENSHOT_FOLDER)
            print(f"🗑️ Deleted existing folder: {SCREENSHOT_FOLDER}")
        except OSError as e:
            print(f"❌ Error deleting old screenshot folder: {e}. Attempting to continue.")
            
    os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)
    print(f"📘 Created clean folder: {SCREENSHOT_FOLDER}")

    if os.path.exists(EXCEL_FILE):
        os.remove(EXCEL_FILE)
        print(f"🗑️ Deleted old file: {EXCEL_FILE}")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Results"
    wb.save(EXCEL_FILE)
    print(f"📘 Created new file: {EXCEL_FILE}")

    # Setup Chrome options (using the correct configuration for the container)
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080") # Ensure large screen size
    options.add_argument("--display=:99") # Explicitly connect to the XVFB virtual display

    # CRITICAL FIX: Use the explicit path for the pre-installed ChromeDriver
    service = Service(executable_path="/usr/bin/chromedriver") 

    caps = webdriver.DesiredCapabilities.CHROME.copy()
    caps['goog:loggingPrefs'] = {'browser': 'ALL'}

    # Initialize driver
    driver = webdriver.Chrome(service=service, options=options)
    
    import pandas as pd 

    # load USNs from passed file
    usn_df = pd.read_csv(usn_csv_path)
    USN_LIST = usn_df['USN'].dropna().astype(str).tolist()

    # make URL global so main() can use it
    URL = url

    # run your existing logic
    main()  

    # STEP 3: Aggregate JSON files into Excel
    print("📊 Starting JSON to Excel aggregation...")
    
    subject_codes_json = json.dumps(subject_codes_list)
    
    try:
        subprocess.run(
            ["python", "json_to_excel.py", subject_codes_json],
            check=True
        )
        print("✅ Excel aggregation complete.")
    except Exception as e:
        print(f"❌ Failed to run json_to_excel.py: {e}")

    # return the output path for download
    return output_path
