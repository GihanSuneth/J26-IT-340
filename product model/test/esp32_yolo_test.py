
import cv2
import time
from pathlib import Path
from ultralytics import YOLO

# ==========================================
# CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent

# Your existing trained model
MODEL_PATH = BASE_DIR / "models" / "best.pt"

# Replace with your actual ESP32-CAM IP
CAMERA_URL = "http://192.168.8.101:81/stream"

CONFIDENCE = 0.50
IMAGE_SIZE = 320

# ==========================================
# LOAD YOLO11
# ==========================================

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"YOLO model not found: {MODEL_PATH}"
    )

print("Loading YOLO11 model...")

model = YOLO(str(MODEL_PATH))

print("Model loaded successfully!")
print(f"Total classes: {len(model.names)}")

# ==========================================
# CONNECT ESP32-CAM
# ==========================================

print("Connecting to ESP32-CAM...")

cap = cv2.VideoCapture(CAMERA_URL)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

if not cap.isOpened():
    raise RuntimeError(
        f"Cannot connect to camera: {CAMERA_URL}"
    )

print("ESP32-CAM connected!")
print("Press Q to exit.")

previous_time = time.perf_counter()

# ==========================================
# LIVE PRODUCT DETECTION
# ==========================================

try:
    while True:
        success, frame = cap.read()

        if not success:
            print("Camera frame unavailable.")
            break

        # Run your trained YOLO11 model
        results = model.predict(
            source=frame,
            conf=CONFIDENCE,
            imgsz=IMAGE_SIZE,
            iou=0.50,
            max_det=30,
            verbose=False
        )

        # Draw product bounding boxes
        annotated = results[0].plot()

        # Count detections
        count = len(results[0].boxes)

        # Calculate FPS
        current_time = time.perf_counter()
        elapsed = current_time - previous_time
        fps = 1 / elapsed if elapsed > 0 else 0
        previous_time = current_time

        # Display information
        cv2.putText(
            annotated,
            f"Products: {count}",
            (15, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )

        cv2.putText(
            annotated,
            f"FPS: {fps:.1f}",
            (15, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )

        cv2.imshow(
            "Smart Trolley - ESP32-CAM YOLO11",
            annotated
        )

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
    print("Camera closed.")
