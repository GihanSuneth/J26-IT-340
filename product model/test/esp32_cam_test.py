
import cv2
import time

# Replace with your actual ESP32-CAM IP address.
CAMERA_URL = "http://192.168.8.101:81/stream"

print("Connecting to ESP32-CAM...")

cap = cv2.VideoCapture(CAMERA_URL)

if not cap.isOpened():
    print("ERROR: Cannot connect to ESP32-CAM.")
    print("Check camera IP and Wi-Fi.")
    raise SystemExit(1)

print("ESP32-CAM connected!")
print("Press Q to exit.")

previous_time = time.perf_counter()

try:
    while True:
        success, frame = cap.read()

        if not success:
            print("Failed to receive frame.")
            break

        current_time = time.perf_counter()
        elapsed = current_time - previous_time
        fps = 1 / elapsed if elapsed > 0 else 0
        previous_time = current_time

        cv2.putText(
            frame,
            f"ESP32-CAM | FPS: {fps:.1f}",
            (15, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )

        cv2.imshow("ESP32-CAM Live Test", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

finally:
    cap.release()
    cv2.destroyAllWindows()
