
import cv2
from pathlib import Path
from ultralytics import YOLO

# =====================================
# SMART TROLLEY - YOLO WEBCAM TEST
# =====================================

# Current test directory
BASE_DIR = Path(__file__).resolve().parent

# Trained YOLO11 model
MODEL_PATH = BASE_DIR / "models" / "best.pt"

# Camera settings
CAMERA_INDEX = 0
CONFIDENCE = 0.50
IMAGE_SIZE = 640

# Check model file
if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"Model not found: {MODEL_PATH}"
    )

# Load trained model
model = YOLO(str(MODEL_PATH))

print("\nSmart Trolley Product Detection")
print("--------------------------------")

# Display trained product classes
for class_id, name in model.names.items():
    print(f"{class_id}: {name}")

print(f"\nTotal classes: {len(model.names)}")

# Open Windows webcam
cap = cv2.VideoCapture(
    CAMERA_INDEX,
    cv2.CAP_DSHOW
)

if not cap.isOpened():
    raise RuntimeError("Cannot open webcam")

print("\nPress Q to exit.")

while True:

    success, frame = cap.read()

    if not success:
        break

    # YOLO detection
    results = model.predict(
        source=frame,
        conf=CONFIDENCE,
        imgsz=IMAGE_SIZE,
        iou=0.50,
        max_det=30,
        verbose=False
    )

    for box in results[0].boxes:
        class_id = int(box.cls[0])
        confidence = float(box.conf[0])

        product_name = model.names[class_id]

        print(
        f"Detected: {product_name} | "
        f"Confidence: {confidence:.2f}"
        )

    # Draw detection boxes
    annotated = results[0].plot()

    # Count current frame detections
    count = len(results[0].boxes)

    cv2.putText(
        annotated,
        f"Detected: {count}",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2
    )

    cv2.imshow(
        "Smart Trolley - Product Detection Test",
        annotated
    )

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
