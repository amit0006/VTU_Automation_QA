"""
VTU Result Page Screenshot Capture Module (Legacy)
This module captures full-page screenshots of VTU result pages using pyautogui.

NOTE: This is a legacy script that uses pyautogui for screenshot capture.
The main automation pipeline (main.py) uses Selenium's native screenshot capability instead.

This script:
1. Waits for user to open the result page in browser
2. Captures multiple screenshots while scrolling
3. Stitches screenshots together into one full-page image
4. Saves the combined image to screenshots folder

Process:
1. Scroll through the page and capture screenshots at each position
2. Compare screenshots to detect when scrolling has reached the bottom
3. Stitch all screenshots vertically into one image
4. Save the final image with USN as filename
"""

import time
import pyautogui
import os
import sys
from PIL import Image

# ==============================================
# CONFIGURATION
# ==============================================
WAIT_TIME = 1        # Time (in seconds) to wait for user to open browser window
SCROLL_PIXELS = 400  # Number of pixels to scroll per attempt
MAX_ATTEMPTS = 10    # Maximum number of scroll/capture attempts
IMAGE_WIDTH, IMAGE_HEIGHT = pyautogui.size()  # Get screen resolution

# ==============================================
# VALIDATE COMMAND LINE ARGUMENT
# ==============================================
# Get USN from command line argument
if len(sys.argv) < 2:
    print("❌ USN not provided.")
    sys.exit(1)

usn = sys.argv[1]

# ==============================================
# SETUP OUTPUT DIRECTORY
# ==============================================
# Ensure screenshots folder exists
output_dir = os.path.join(os.getcwd(), "screenshots")
os.makedirs(output_dir, exist_ok=True)

# ==============================================
# CAPTURE SCREENSHOTS
# ==============================================
print(f"⏳ You have {WAIT_TIME} seconds to open the result page for {usn}...")
time.sleep(WAIT_TIME)

print("📸 Capturing full page screenshots...")

# List to store all captured screenshots
screenshots = []
prev_screenshot = None  # Previous screenshot for comparison
attempts = 0  # Attempt counter

# Scroll and capture loop
while attempts < MAX_ATTEMPTS:
    attempts += 1
    
    # Step 1: Capture current view (before scrolling)
    current_screenshot = pyautogui.screenshot()
    
    # Step 2: Add screenshot to list
    screenshots.append(current_screenshot)

    # Step 3: Stop condition check
    # Compare current screenshot with previous screenshot
    # If they are identical, scrolling has reached the bottom
    if prev_screenshot and current_screenshot.tobytes() == prev_screenshot.tobytes():
        print(f"🛑 Stopping capture: Scroll detected no change on attempt {attempts}.")
        # Remove the duplicate screenshot before breaking
        screenshots.pop() 
        break
    
    # Step 4: Scroll down to capture next section
    pyautogui.scroll(-SCROLL_PIXELS)
    time.sleep(0.5)  # Wait for page to render after scroll
    
    # Step 5: Save current screenshot as previous for next comparison
    prev_screenshot = current_screenshot
    
    # Safety break: Stop if max attempts reached
    if attempts == MAX_ATTEMPTS:
        print(f"⚠️ Reached Max Attempts ({MAX_ATTEMPTS}). Stopping capture.")

print(f"✅ Captured {len(screenshots)} unique sections for stitching.")

# ==============================================
# STITCH SCREENSHOTS TOGETHER
# ==============================================
# Validate that screenshots were captured
if not screenshots:
    print("❌ Error: No screenshots were captured. Exiting.")
    sys.exit(1)
    
# Calculate dimensions for combined image
IMAGE_WIDTH = screenshots[0].width  # Width of first screenshot
combined_height = IMAGE_HEIGHT * len(screenshots)  # Total height = screen height * number of screenshots

# Create new image with calculated dimensions
combined_image = Image.new('RGB', (IMAGE_WIDTH, combined_height))

# Paste each screenshot into the combined image (vertically stacked)
for idx, shot in enumerate(screenshots):
    # Calculate y-position: each screenshot is placed below the previous one
    combined_image.paste(shot, (0, idx * IMAGE_HEIGHT))

# ==============================================
# SAVE COMBINED IMAGE
# ==============================================
# Save the stitched image to screenshots folder with USN as filename
output_path = os.path.join(output_dir, f"{usn}_result.png")
combined_image.save(output_path)
print(f"✅ Screenshot saved at: {output_path}")