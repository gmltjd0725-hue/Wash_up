import os

for key in [
    "GTK_PATH",
    "GTK_EXE_PREFIX",
    "GTK_DATA_PREFIX",
    "GDK_PIXBUF_MODULE_FILE",
]:
    os.environ.pop(key, None)

import cv2
import numpy as np


CAMERA_ID = 6

camera = cv2.VideoCapture(CAMERA_ID)

if not camera.isOpened():
    raise RuntimeError("/dev/video6 카메라를 열 수 없습니다.")

camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

print("DARK BIN Detector 시작")
print("Q = 종료")

while True:

    ret, frame = camera.read()

    if not ret:
        continue

    hsv = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2HSV
    )

    lower = np.array([
        8,
        70,
        55
    ])

    upper = np.array([
        25,
        170,
        150
    ])

    mask = cv2.inRange(
        hsv,
        lower,
        upper
    )

    kernel = np.ones(
        (7, 7),
        np.uint8
    )

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_OPEN,
        kernel
    )

    mask = cv2.morphologyEx(
        mask,
        cv2.MORPH_CLOSE,
        kernel
    )

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    frame_h, frame_w = frame.shape[:2]
    frame_area = frame_h * frame_w

    best = None
    best_area = 0

    for contour in contours:

        area = cv2.contourArea(
            contour
        )

        if area < 3000:
            continue

        if area > frame_area * 0.55:
            continue

        x, y, w, h = cv2.boundingRect(
            contour
        )

        # 화면 가장자리 배경 제거
        margin = 10

        if (
            x <= margin
            or y <= margin
            or x + w >= frame_w - margin
            or y + h >= frame_h - margin
        ):
            continue

        rect_area = w * h

        if rect_area == 0:
            continue

        rectangularity = area / rect_area

        if rectangularity < 0.45:
            continue

        if w < 70 or h < 70:
            continue

        if area > best_area:

            best = (
                x,
                y,
                w,
                h
            )

            best_area = area

    if best is not None:

        x, y, w, h = best

        cx = x + w // 2
        cy = y + h // 2

        cv2.rectangle(
            frame,
            (x, y),
            (x + w, y + h),
            (255, 255, 255),
            2
        )

        cv2.circle(
            frame,
            (cx, cy),
            6,
            (255, 255, 255),
            -1
        )

        print(f"DARK BIN center=({cx}, {cy}) bbox=({x}, {y}, {w}, {h})")
        cv2.putText(
            frame,
            f"DARK BIN ({cx}, {cy})",
            (x, max(30, y - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

    cv2.imshow(
        "DARK BIN DETECTOR",
        frame
    )

    cv2.imshow(
        "DARK BIN MASK",
        mask
    )

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break


camera.release()
cv2.destroyAllWindows()
