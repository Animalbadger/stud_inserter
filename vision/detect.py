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
    config = picam2.create_preview_configuration(
        main={"size": (WIDTH, HEIGHT), "format": "RGB888"}
    )
    picam2.configure(config)
    picam2.start()

    time.sleep(2)
    holes = []

    try:
        cv2.namedWindow("Camera View", cv2.WINDOW_NORMAL)
        cv2.namedWindow("Threshold", cv2.WINDOW_NORMAL)
        cv2.createTrackbar("thresh", "Threshold", THRESHOLD_VALUE, 255, lambda _x: None)
        cv2.createTrackbar("min_area", "Threshold", MIN_AREA, 20000, lambda _x: None)
        cv2.createTrackbar("max_area", "Threshold", MAX_AREA, 50000, lambda _x: None)
        cv2.createTrackbar("circularity", "Threshold", 55, 100, lambda _x: None)  # 0.55
        cv2.createTrackbar("mode", "Threshold", 1, 2, lambda _x: None)  # 0=global, 1=adaptive, 2=otsu
        cv2.createTrackbar("inv", "Threshold", 1, 1, lambda _x: None)  # 1=invert (dark holes)
        cv2.createTrackbar("block", "Threshold", 25, 99, lambda _x: None)  # adaptive block size (odd)
        cv2.createTrackbar("C", "Threshold", 5, 30, lambda _x: None)  # adaptive constant
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

        while True:
            frame = picam2.capture_array()

            image_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 0)
            gray = clahe.apply(gray)

            t = cv2.getTrackbarPos("thresh", "Threshold")
            min_area = cv2.getTrackbarPos("min_area", "Threshold")
            max_area = cv2.getTrackbarPos("max_area", "Threshold")
            circ_min = cv2.getTrackbarPos("circularity", "Threshold") / 100.0
            mode = cv2.getTrackbarPos("mode", "Threshold")
            inv = cv2.getTrackbarPos("inv", "Threshold") == 1

            if mode == 1:
                block = cv2.getTrackbarPos("block", "Threshold")
                block = max(3, block | 1)  # ensure odd and >=3
                c = cv2.getTrackbarPos("C", "Threshold")
                thresh_type = cv2.THRESH_BINARY_INV if inv else cv2.THRESH_BINARY
                bw = cv2.adaptiveThreshold(
                    gray,
                    255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    thresh_type,
                    block,
                    c,
                )
            elif mode == 2:
                thresh_type = cv2.THRESH_BINARY_INV if inv else cv2.THRESH_BINARY
                _, bw = cv2.threshold(gray, 0, 255, thresh_type | cv2.THRESH_OTSU)
            else:
                thresh_type = cv2.THRESH_BINARY_INV if inv else cv2.THRESH_BINARY
                _, bw = cv2.threshold(gray, t, 255, thresh_type)

            # cleanup helps when white background gets grainy
            bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
            bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1)

            contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            holes = []
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < min_area or area > max_area:
                    continue

                peri = cv2.arcLength(cnt, True)
                if peri <= 0:
                    continue
                circularity = (4 * np.pi * area) / (peri * peri)
                if circularity < circ_min:
                    continue

                m = cv2.moments(cnt)
                if m["m00"] == 0:
                    continue

                cx = int(m["m10"] / m["m00"])
                cy = int(m["m01"] / m["m00"])
                holes.append((cx, cy))

            display = image_bgr.copy()
            bw_display = cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)

            # grid overlay
            h, w = display.shape[:2]
            grid_color_minor = (200, 200, 200)
            grid_color_major = (255, 255, 255)
            major_every = GRID_STEP_PX * 5
            for x in range(0, w, GRID_STEP_PX):
                color = grid_color_major if (x % major_every == 0) else grid_color_minor
                thickness = 2 if (x % major_every == 0) else 1
                cv2.line(display, (x, 0), (x, h - 1), color, thickness)
                cv2.line(bw_display, (x, 0), (x, h - 1), color, thickness)
            for y in range(0, h, GRID_STEP_PX):
                color = grid_color_major if (y % major_every == 0) else grid_color_minor
                thickness = 2 if (y % major_every == 0) else 1
                cv2.line(display, (0, y), (w - 1, y), color, thickness)
                cv2.line(bw_display, (0, y), (w - 1, y), color, thickness)

            # annotate detected holes
            for i, (cx, cy) in enumerate(holes, start=1):
                cv2.circle(display, (cx, cy), 8, (0, 0, 255), 2)
                cv2.circle(bw_display, (cx, cy), 8, (0, 0, 255), 2)

                # big "X" marker so it's obvious what's accepted as a hole
                x_len = 14
                cv2.line(
                    display,
                    (cx - x_len, cy - x_len),
                    (cx + x_len, cy + x_len),
                    (0, 0, 255),
                    2,
                )
                cv2.line(
                    display,
                    (cx - x_len, cy + x_len),
                    (cx + x_len, cy - x_len),
                    (0, 0, 255),
                    2,
                )
                cv2.line(
                    bw_display,
                    (cx - x_len, cy - x_len),
                    (cx + x_len, cy + x_len),
                    (0, 0, 255),
                    2,
                )
                cv2.line(
                    bw_display,
                    (cx - x_len, cy + x_len),
                    (cx + x_len, cy - x_len),
                    (0, 0, 255),
                    2,
                )

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
                cv2.putText(
                    bw_display,
                    f"H{i}",
                    (cx + 10, cy - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 0, 255),
                    2,
                    cv2.LINE_AA,
                )

            cv2.putText(
                display,
                f"holes={len(holes)}  mode={mode}  inv={int(inv)}  thresh={t}  area=[{min_area},{max_area}]  circ>={circ_min:.2f}",
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )

            cv2.imshow("Camera View", display)
            cv2.imshow("Threshold", bw_display)

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):  # Esc or q
                break

    finally:
        picam2.stop()
        cv2.destroyAllWindows()

    print(f"Detected {len(holes)} holes")
    return holes