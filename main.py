from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import cv2
import numpy as np
from PIL import Image
import io
import logging
import easyocr
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="ID Card OCR API", description="Extract text from ID card images using EasyOCR")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize EasyOCR Reader once (global)
reader = easyocr.Reader(['en'], gpu=False) #if use cpu then gpu=True

def preprocess_image(image_array):
    """
    Preprocess the image to improve OCR accuracy.
    """
    try:
        gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        kernel = np.ones((1, 1), np.uint8)
        processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        processed = cv2.morphologyEx(processed, cv2.MORPH_OPEN, kernel)

        # Convert back to RGB for EasyOCR
        processed_rgb = cv2.cvtColor(processed, cv2.COLOR_GRAY2RGB)

        return processed_rgb
    except Exception as e:
        logger.error(f"Error in image preprocessing: {str(e)}")
        raise

def extract_text_from_image(image_array):
    """
    Extract text from image using EasyOCR.
    """
    try:
        processed_image = preprocess_image(image_array)
        
        # Use EasyOCR to extract text
        results = reader.readtext(processed_image)

        # Join the detected texts
        extracted_text = "\n".join([text for (_, text, _) in results])
        return extracted_text.strip()
    except Exception as e:
        logger.error(f"Error in text extraction: {str(e)}")
        raise

@app.get("/")
async def root():
    return {"message": "ID Card OCR API is running", "status": "healthy"}

@app.post("/extract-text/")
async def extract_text(file: UploadFile = File(...)):
    """
    Upload an ID card image and extract text using EasyOCR.
    """
    try:
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        contents = await file.read()

        # Convert to PIL image
        image = Image.open(io.BytesIO(contents))
        image_array = np.array(image)

        # Ensure image is in RGB
        if image_array.ndim == 2:
            image_array = cv2.cvtColor(image_array, cv2.COLOR_GRAY2RGB)
        elif image_array.shape[2] == 4:
            image_array = cv2.cvtColor(image_array, cv2.COLOR_RGBA2RGB)

        # Extract text
        extracted_text = extract_text_from_image(image_array)
        lines = [line.strip() for line in extracted_text.split('\n') if line.strip()]

        response_data = {
            "filename": file.filename,
            "extracted_text": extracted_text,
            "parsed_lines": lines,
            "status": "success"
        }

        logger.info(f"Processed file: {file.filename}")
        return JSONResponse(content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing file {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ID Card OCR API"}

if __name__ == "__main__":
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
