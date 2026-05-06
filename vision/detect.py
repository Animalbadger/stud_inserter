from picamera2 import Picamera2
import cv2
import numpy as np
import time

WIDTH = 1280
HEIGHT = 720

THRESHOLD_VALUE = 30
MIN_AREA = 60
MAX_AREA = 6000

GRID_STEP_PX = 25  # smaller = denser grid


def get_holes():
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={"size": (WIDTH, HEIGHT)})
    picam2.configure(config)
    picam2.start()

    time.sleep(2)
    holes = []

    try:
        while True:
            frame = picam2.capture_array()

            image_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 0)

            _, bw = cv2.threshold(gray, THRESHOLD_VALUE, 255, cv2.THRESH_BINARY_INV)
            contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            holes = []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < MIN_AREA or area > MAX_AREA:
                    continue

                m = cv2.moments(cnt)
                if m["m00"] == 0:
                    continue

                cx = int(m["m10"] / m["m00"])
                cy = int(m["m01"] / m["m00"])
                holes.append((cx, cy))

            display = image_bgr.copy()

            # grid overlay
            h, w = display.shape[:2]
            grid_color = (80, 80, 80)
            for x in range(0, w, GRID_STEP_PX):
                cv2.line(display, (x, 0), (x, h - 1), grid_color, 1)
            for y in range(0, h, GRID_STEP_PX):
                cv2.line(display, (0, y), (w - 1, y), grid_color, 1)

            # annotate detected holes
            for i, (cx, cy) in enumerate(holes, start=1):
                cv2.circle(display, (cx, cy), 8, (0, 0, 255), 2)
                cv2.putText(
                    display,
                    f"H{i}",
                    (cx + 10, cy - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    2,
                    cv2.LINE_AA,
                )

            cv2.imshow("Camera View", display)
            cv2.imshow("Threshold", bw)

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):  # Esc or q
                break

    finally:
        picam2.stop()
        cv2.destroyAllWindows()

    print(f"Detected {len(holes)} holes")
    return holes