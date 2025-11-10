# # This script takes the screenshot of result page
import time
import pyautogui
import os
import sys
from PIL import Image

# Settings
WAIT_TIME = 1        # Time to switch to the browser window
SCROLL_PIXELS = 400
MAX_ATTEMPTS = 10    # <--- NEW: Maximum number of times to scroll and capture
IMAGE_WIDTH, IMAGE_HEIGHT = pyautogui.size()

# Get USN from command line
if len(sys.argv) < 2:
    print("❌ USN not provided.")
    sys.exit(1)

usn = sys.argv[1]

# Ensure 'screenshots/' folder exists
output_dir = os.path.join(os.getcwd(), "screenshots")
os.makedirs(output_dir, exist_ok=True)

print(f"⏳ You have {WAIT_TIME} seconds to open the result page for {usn}...")
time.sleep(WAIT_TIME)

# ========== Modified Section: Capture full scrollable page ==========
print("📸 Capturing full page screenshots...")

screenshots = []
prev_screenshot = None
attempts = 0 # Initialize attempt counter

while attempts < MAX_ATTEMPTS: # <--- CRITICAL FIX: Use Max Attempts
    attempts += 1
    
    # 1. Capture current view (before scroll)
    current_screenshot = pyautogui.screenshot()
    
    # 2. Add to list
    screenshots.append(current_screenshot)

    # 3. Stop check: Compare the current screenshot (before scrolling) 
    #    with the *previous* screenshot taken *after* scrolling.
    #    If they are identical, it means scrolling did nothing, so we stop.
    if prev_screenshot and current_screenshot.tobytes() == prev_screenshot.tobytes():
        print(f"🛑 Stopping capture: Scroll detected no change on attempt {attempts}.")
        # Remove the duplicate/no-change screenshot captured before breaking
        screenshots.pop() 
        break
    
    # 4. Scroll down
    pyautogui.scroll(-SCROLL_PIXELS)
    time.sleep(0.5) # Reduced sleep slightly for better performance
    
    # 5. Save the current screenshot as the one to compare against next time
    prev_screenshot = current_screenshot
    
    # Safety break condition based on max attempts
    if attempts == MAX_ATTEMPTS:
        print(f"⚠️ Reached Max Attempts ({MAX_ATTEMPTS}). Stopping capture.")


print(f"✅ Captured {len(screenshots)} unique sections for stitching.")

# Stitch all screenshots vertically
if not screenshots:
    print("❌ Error: No screenshots were captured. Exiting.")
    sys.exit(1)
    
# Determine the width and total height
IMAGE_WIDTH = screenshots[0].width
combined_height = IMAGE_HEIGHT * len(screenshots)
combined_image = Image.new('RGB', (IMAGE_WIDTH, combined_height))

for idx, shot in enumerate(screenshots):
    combined_image.paste(shot, (0, idx * IMAGE_HEIGHT))

# Save inside screenshots/ with USN as filename
output_path = os.path.join(output_dir, f"{usn}_result.png")
combined_image.save(output_path)
print(f"✅ Screenshot saved at: {output_path}")