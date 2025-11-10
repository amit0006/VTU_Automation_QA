"""
VTU CAPTCHA Image Preprocessing Module
This module preprocesses CAPTCHA images to improve OCR accuracy.
It applies noise reduction, thresholding, and morphological operations.

Process:
1. Convert to grayscale
2. Apply Gaussian blur for noise reduction
3. Apply binary thresholding
4. Apply dilation to enhance text
5. Resize to consistent dimensions
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt

def preprocess_image(image_path, output_path="processed_captcha.png"):
    """
    Preprocess CAPTCHA image to improve OCR accuracy.
    
    This function applies several image processing techniques:
    - Gaussian blur: Reduces noise
    - Binary thresholding: Converts to black and white
    - Dilation: Enhances text characters
    - Resizing: Normalizes image size
    
    Args:
        image_path: Path to the input CAPTCHA image
        output_path: Path to save the processed image (default: "processed_captcha.png")
        
    Returns:
        Path to the processed image if successful, None otherwise
    """
    try:
        # Load image in grayscale mode
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError("Image not found")

        # Step 1: Noise reduction using Gaussian blur
        img = cv2.GaussianBlur(img, (5, 5), 0)
        
        # Step 2: Binary thresholding (convert to pure black and white)
        # Threshold value 180: pixels above this become white (255), below become black (0)
        _, img = cv2.threshold(img, 180, 255, cv2.THRESH_BINARY)
        
        # Step 3: Dilation to enhance text characters (makes them thicker)
        kernel = np.ones((2, 2), np.uint8)
        img = cv2.dilate(img, kernel, iterations=1)
        
        # Step 4: Resize to consistent dimensions for better OCR
        img = cv2.resize(img, (200, 50))

        # Save processed image
        cv2.imwrite(output_path, img)
        
        # Optional: Uncomment to visualize the processed image
        # plt.imshow(img, cmap='gray')
        # plt.title("Processed CAPTCHA Image")
        # plt.axis('off')
        # plt.show()
        
        return output_path
    except Exception as e:
        print(f"❌ Error in preprocessing: {e}")
        return None

if __name__ == "__main__":
    preprocess_image("captcha.png")

