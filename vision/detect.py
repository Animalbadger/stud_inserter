from picamera2 import Picamera2
import cv2
import numpy as np
import time

WIDTH = 1280
HEIGHT = 720

THRESHOLD_VALUE = 30
MIN_AREA = 60
MAX_AREA = 6000


def get_holes():
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={"size": (WIDTH, HEIGHT)})
    picam2.configure(config)
    picam2.start()

    time.sleep(2)

    frame = picam2.capture_array()
    picam2.stop()

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

    print(f"Detected {len(holes)} holes")

    return holes