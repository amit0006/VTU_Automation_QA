"""
VTU Marks Extraction Runner Module
This module processes all screenshots in the screenshots folder and extracts marks using marks.py.

This is a batch processing script that:
1. Iterates through all screenshot files
2. Calls marks.py for each screenshot to extract marks
3. Tracks failures and saves them to a CSV file

Note: This script is called from main.py as part of the automation pipeline.
"""

import os
import subprocess
import pandas as pd
import certifi

# Set SSL certificate file for secure connections (required for some environments)
os.environ['SSL_CERT_FILE'] = certifi.where()

# Configuration: Folder containing screenshots
screenshots_dir = "screenshots"

# List to store failed extractions
results_data = []

print("\n📊 Starting marks extraction for all screenshots...\n")

# Loop through all files in the screenshots folder
for filename in os.listdir(screenshots_dir):
    # Process only files ending with "_result.png" (screenshot files)
    if filename.endswith("_result.png"):
        screenshot_path = os.path.join(screenshots_dir, filename)
        # Extract USN from filename (remove "_result.png" suffix)
        usn = filename.replace("_result.png", "")
        
        try:
            # Call marks.py to extract marks from the screenshot
            # marks.py uses Gemini AI to extract marks and save to JSON
            subprocess.run(["python", "marks.py", screenshot_path], check=True)
            print(f"✅ Marks extracted for {usn}")
        except Exception as e:
            # Track failed extractions
            print(f"❌ Failed to extract marks for {usn}: {e}")
            results_data.append({"USN": usn, "Result": "❌ Failed to extract marks"})

# Save summary of failures to CSV file (if any failures occurred)
if results_data:
    df = pd.DataFrame(results_data)
    df.to_csv("vtu_results.csv", index=False)
    print("\n📁 All failures saved to 'vtu_results.csv'")
else:
    print("\n✅ All screenshots processed successfully. No failures.")
