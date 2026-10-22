
from pathlib import Path
import cv2
from ultralytics import YOLO

# ==========================================
# 1. PROJECT DIRECTORY
# ==========================================
ROOT = Path(__file__).resolve().parent

# ==========================================
# 2. LOAD best (4).pt
# ==========================================
MODEL_PATH = ROOT / "models" / "best (4).pt"

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"\nModel not found: {MODEL_PATH}\n"
        "Please ensure best (4).pt is inside the models folder."
    )

model = YOLO(str(MODEL_PATH))

# Confirm which model is loaded
print("\n" + "=" * 55)
print("SMART SHOPPING CART - WEBCAM DETECTION")
print("=" * 55)
print("ACTUAL MODEL PATH:", MODEL_PATH.resolve())
print("ACTUAL MODEL FILE:", MODEL_PATH.name)
print("DETECTED CLASSES:", model.names)
print("=" * 55)

# ==========================================
# 3. START WEBCAM
# ==========================================
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    raise RuntimeError(
        "Cannot open webcam. Try changing VideoCapture(0) "
        "to VideoCapture(1), and check camera permissions."
    )

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

print("\nWebcam started successfully.")
print("Show your phone and wallet to test detection.")
print("Press Q to quit.")

# ==========================================
# 4. REAL-TIME OBJECT DETECTION
# ==========================================
try:
    while True:
        success, frame = cap.read()

        if not success:
            print("\nCannot read webcam frame.")
            break

        # Run detection using best (4).pt
        results = model.predict(
    source=frame,
    conf=0.65,
    imgsz=640,
    verbose=False
)

        result = results[0]

        # Draw bounding boxes and class labels
        annotated_frame = result.plot()

        # Display the correct model name
        cv2.imshow(
            "Smart Shopping Cart - best (4).pt",
            annotated_frame
        )

        # Print detected classes and confidence scores
        for box in result.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            class_name = model.names[class_id]

            print(
                f"\rDetected: {class_name} | "
                f"Confidence: {confidence:.2f}     ",
                end="",
                flush=True
            )

        # Press Q to quit
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
    print("\n\nWebcam stopped.")
