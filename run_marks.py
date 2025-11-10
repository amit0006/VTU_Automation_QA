import os
import subprocess
import pandas as pd
import certifi
os.environ['SSL_CERT_FILE'] = certifi.where()

# Folder containing screenshots
screenshots_dir = "screenshots"
results_data = []

print("\n📊 Starting marks extraction for all screenshots...\n")

# Loop through all PNG files in the screenshots folder
for filename in os.listdir(screenshots_dir):
    if filename.endswith("_result.png"):
        screenshot_path = os.path.join(screenshots_dir, filename)
        usn = filename.replace("_result.png", "")
        try:
            subprocess.run(["python", "marks.py", screenshot_path], check=True)
            print(f"✅ Marks extracted for {usn}")
        except Exception as e:
            print(f"❌ Failed to extract marks for {usn}: {e}")
            results_data.append({"USN": usn, "Result": "❌ Failed to extract marks"})

# Save summary
if results_data:
    df = pd.DataFrame(results_data)
    df.to_csv("vtu_results.csv", index=False)
    print("\n📁 All failures saved to 'vtu_results.csv'")
else:
    print("\n✅ All screenshots processed successfully. No failures.")
