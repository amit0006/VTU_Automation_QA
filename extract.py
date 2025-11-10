import easyocr

reader = easyocr.Reader(['en'])  # supports mixed case
result = reader.readtext('processed_captcha.png')
for (bbox, text, prob) in result:
    print("Detected:", text)