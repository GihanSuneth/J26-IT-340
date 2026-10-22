
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO


# ==========================================================
# 1. PROJECT PATHS
# ==========================================================

# Outer project directory:
# smart_cart_model_test (1)/
ROOT = Path(__file__).resolve().parent.parent

# Your trained YOLO model
MODEL_PATH = (
    ROOT
    / "smart_cart_model_test"
    / "models"
    / "best (4).pt"
)


# ==========================================================
# 2. LOAD THE TRAINED YOLO MODEL
# ==========================================================

if not MODEL_PATH.is_file():
    raise FileNotFoundError(
        f"\nTrained model not found:\n{MODEL_PATH}\n"
        "Check that best (4).pt exists inside "
        "smart_cart_model_test/models."
    )

print("=" * 55)
print("SMARTTROLLEY - YOLO MODEL")
print("=" * 55)
print(f"Loading model: {MODEL_PATH.name}")

model = YOLO(str(MODEL_PATH))

print("Model loaded successfully!")
print("Model classes:", model.names)
print("=" * 55)


# ==========================================================
# 3. CREATE FASTAPI APPLICATION
# ==========================================================

app = FastAPI(
    title="SmartTrolley API",
    description="YOLO object detection API for SmartTrolley",
    version="1.0.0",
)


# ==========================================================
# 4. ALLOW CONNECTIONS FROM THE REACT FRONTEND
# ==========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ==========================================================
# 5. HOME / HEALTH CHECK
# ==========================================================

@app.get("/")
def home():
    return {
        "status": "success",
        "message": "SmartTrolley API is running!",
        "model": MODEL_PATH.name,
        "classes": model.names,
    }


# ==========================================================
# 6. GET TRAINED MODEL CLASS NAMES
# ==========================================================

@app.get("/classes")
def get_classes():
    return {
        "model": MODEL_PATH.name,
        "classes": model.names,
    }


# ==========================================================
# 7. PREDICT OBJECTS FROM AN UPLOADED IMAGE
# ==========================================================

@app.post("/predict")
async def predict(file: UploadFile = File(...)):

    # Check uploaded file type
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a valid image file.",
        )

    # Read uploaded image
    contents = await file.read()

    if not contents:
        raise HTTPException(
            status_code=400,
            detail="Uploaded image is empty.",
        )

    # Convert image bytes to an OpenCV image
    image_array = np.frombuffer(contents, dtype=np.uint8)
    frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    if frame is None:
        raise HTTPException(
            status_code=400,
            detail="Unable to decode the uploaded image.",
        )

    height, width = frame.shape[:2]

    try:
        # Run the trained YOLO model
        results = model.predict(
            source=frame,
            conf=0.35,
            imgsz=640,
            verbose=False,
        )

        detections = []

        for result in results:
            for box in result.boxes:

                class_id = int(box.cls[0].item())
                confidence = float(box.conf[0].item())

                x1, y1, x2, y2 = (
                    box.xyxy[0].tolist()
                )

                detections.append({
                    "class_id": class_id,
                    "label": str(model.names[class_id]),
                    "confidence": round(confidence, 4),
                    "box": [
                        round(x1, 2),
                        round(y1, 2),
                        round(x2, 2),
                        round(y2, 2),
                    ],
                })

        return {
            "status": "success",
            "model": MODEL_PATH.name,
            "image_width": width,
            "image_height": height,
            "count": len(detections),
            "detections": detections,
        }

    except Exception as error:
        print(f"Prediction error: {error}")

        raise HTTPException(
            status_code=500,
            detail="YOLO prediction failed. Check the backend terminal.",
        )


# ==========================================================
# 8. OPTIONAL API STARTUP MESSAGE
# ==========================================================

@app.on_event("startup")
def startup_message():
    print("\nSmartTrolley backend is ready.")
    print("API documentation: http://127.0.0.1:8000/docs")
    print("Waiting for images from the React frontend...\n")
