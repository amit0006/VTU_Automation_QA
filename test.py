# This Script will remove the background noise and return the image of main captcha text (Updated Version).
import cv2
import numpy as np
import matplotlib.pyplot as plt

def preprocess_image(image_path, output_path="processed_captcha.png"):
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise ValueError("Image not found")

        # Noise reduction
        img = cv2.GaussianBlur(img, (5, 5), 0)
        _, img = cv2.threshold(img, 180, 255, cv2.THRESH_BINARY)
        kernel = np.ones((2, 2), np.uint8)
        img = cv2.dilate(img, kernel, iterations=1)
        img = cv2.resize(img, (200, 50))  # Resize to consistent input

        # Save processed image
        cv2.imwrite(output_path, img)
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

