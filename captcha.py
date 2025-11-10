# This script takes the image of captcha from VTU website and save it into captcha.png
import time
from io import BytesIO
from PIL import Image
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Uncomment the following imports and code block if you want to run captcha.py standalone (open browser, load page, save captcha)
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from webdriver_manager.chrome import ChromeDriverManager

def save_captcha_from_driver(driver):
    """
    Given an existing Selenium driver, find the CAPTCHA image on the page,
    save it as 'captcha.png', and return True if successful.
    """
    from io import BytesIO
    from PIL import Image
    import time
    try:
        # Wait for CAPTCHA image element
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        
        captcha_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//img[contains(@src, 'captcha')]"))
        )
        time.sleep(2)  # Ensure image fully loads
        
        # Screenshot CAPTCHA
        captcha_png = captcha_element.screenshot_as_png
        
        # Save the image
        img = Image.open(BytesIO(captcha_png))
        img.save("captcha.png")
        print("✅ CAPTCHA saved as 'captcha.png'")
        return True
    except Exception as e:
        print(f"❌ Error saving CAPTCHA: {e}")
        return False


# Uncomment the following block if running captcha.py standalone
'''
def main():
    # Standalone mode: opens browser, navigates, saves captcha, closes browser
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-extensions")
    options.add_argument("--headless=new")  # New headless mode

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        start_time = time.time()
        driver.get("https://results.vtu.ac.in/DJcbcs25/index.php")
        success = save_captcha_from_driver(driver)
        if success:
            print(f"🚀 Execution Time: {round(time.time() - start_time, 2)} seconds")
    except Exception as e:
        print("❌ Error:", e)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
'''

# ==== Summary of lines needed for standalone running: ====
# 1. Imports: selenium.webdriver, Service, ChromeDriverManager (currently commented out)
# 2. main() function (commented block above)
# 3. if __name__ == "__main__": main()
# =========================================================
