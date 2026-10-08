from ultralytics import YOLO
import cv2

# ---------------------------------------------------
# 1. Load the YOLO model
# ---------------------------------------------------
# YOLO will automatically download the model
# the first time you run the program.
model = YOLO("yolo11n.pt")


# ---------------------------------------------------
# 2. Load the image
# ---------------------------------------------------
image_path = "test.jpg"

image = cv2.imread(image_path)

if image is None:
    print("ERROR: Image could not be loaded.")
    exit()


# ---------------------------------------------------
# 3. Run YOLO object detection
# ---------------------------------------------------
results = model(image)


# ---------------------------------------------------
# 4. Process detection results
# ---------------------------------------------------
for result in results:

    # Bounding boxes
    boxes = result.boxes

    for box in boxes:

        # Get coordinates
        x1, y1, x2, y2 = box.xyxy[0]

        # Convert to integer
        x1 = int(x1)
        y1 = int(y1)
        x2 = int(x2)
        y2 = int(y2)

        # Confidence
        confidence = float(box.conf[0])

        # Class ID
        class_id = int(box.cls[0])

        # Object name
        object_name = model.names[class_id]

        print(
            f"Detected: {object_name} "
            f"| Confidence: {confidence:.2f}"
        )

        # ------------------------------------------------
        # Draw bounding box
        # ------------------------------------------------
        cv2.rectangle(
            image,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            2
        )

        # ------------------------------------------------
        # Draw object name and confidence
        # ------------------------------------------------
        label = f"{object_name} {confidence:.2f}"

        cv2.putText(
            image,
            label,
            (x1, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )


# ---------------------------------------------------
# 5. Display the result
# ---------------------------------------------------
cv2.imshow("YOLO Object Detection", image)

cv2.waitKey(0)
cv2.destroyAllWindows()


# ---------------------------------------------------
# 6. Save the detected image
# ---------------------------------------------------
cv2.imwrite("detected_result.jpg", image)

print("Detection completed.")
print("Result saved as detected_result.jpg")