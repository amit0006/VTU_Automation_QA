"""
VTU CAPTCHA Extraction Module (Legacy - EasyOCR)
This module uses EasyOCR to extract text from CAPTCHA images.

NOTE: This is a legacy script. The main automation pipeline (main.py) uses Gemini AI
for CAPTCHA OCR instead, which provides better accuracy.

This script:
1. Initializes EasyOCR reader for English text
2. Reads text from processed CAPTCHA image
3. Prints detected text

Usage:
    python extract.py
    
The script expects 'processed_captcha.png' to exist in the current directory.
"""

import easyocr

# Initialize EasyOCR reader for English text (supports mixed case)
reader = easyocr.Reader(['en'])

# Read text from processed CAPTCHA image
result = reader.readtext('processed_captcha.png')

# Print detected text with bounding box and confidence
for (bbox, text, prob) in result:
    print("Detected:", text)