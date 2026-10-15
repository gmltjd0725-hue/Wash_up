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
BACKGROUND_FRAMES = 30
MIN_BIN_AREA = 3000

camera = cv2.VideoCapture(CAMERA_ID)

if not camera.isOpened():
    raise RuntimeError("/dev/video6 카메라를 열 수 없습니다.")

camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

background_frames = []
background = None

print("초기 배경 저장 중 - 빨래통을 화면에서 치워주세요.")
print("배경 저장 완료 후 DARK 빨래통을 보여주세요.")
print("Q = 종료")

while True:

    ret, frame = camera.read()

    if not ret:
        continue

    gray = cv2.cvtColor(
        frame,
        cv2.COLOR_BGR2GRAY
    )

    gray = cv2.GaussianBlur(
        gray,
        (7, 7),
        0
    )

    # 1. 빈 배경 저장
    if background is None:

        background_frames.append(
            gray.astype(np.float32)
        )

        cv2.imshow(
            "DARK BIN SHAPE DETECTOR",
            frame
        )

        if len(background_frames) >= BACKGROUND_FRAMES:

            background = np.mean(
                background_frames,
                axis=0
            ).astype(np.uint8)

            print("배경 저장 완료")

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

        continue

    # 2. 배경 차분 → 움직여 놓은 물체 형체
    difference = cv2.absdiff(
        background,
        gray
    )

    _, motion_mask = cv2.threshold(
        difference,
        25,
        255,
        cv2.THRESH_BINARY
    )

    kernel = np.ones(
        (5, 5),
        np.uint8
    )

    motion_mask = cv2.morphologyEx(
        motion_mask,
        cv2.MORPH_OPEN,
        kernel
    )

    motion_mask = cv2.morphologyEx(
        motion_mask,
        cv2.MORPH_CLOSE,
        kernel,
        iterations=3
    )

    contours, _ = cv2.findContours(
        motion_mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    valid = [
        c
        for c in contours
        if cv2.contourArea(c) >= MIN_BIN_AREA
    ]

    if valid:

        contour = max(
            valid,
            key=cv2.contourArea
        )

        x, y, w, h = cv2.boundingRect(
            contour
        )

        roi = frame[
            y:y+h,
            x:x+w
        ]

        hsv = cv2.cvtColor(
            roi,
            cv2.COLOR_BGR2HSV
        )

        median = np.median(
            hsv.reshape(-1, 3),
            axis=0
        )

        H = float(median[0])
        S = float(median[1])
        V = float(median[2])

        # 실제 측정한 DARK BIN 기준
        is_dark_bin = (
            8 <= H <= 25
            and
            70 <= S <= 170
            and
            55 <= V <= 150
        )

        cx = x + w // 2
        cy = y + h // 2

        if is_dark_bin:

            cv2.rectangle(
                frame,
                (x, y),
                (x + w, y + h),
                (255, 255, 255),
                2
            )

            cv2.putText(
                frame,
                f"DARK BIN ({cx}, {cy})",
                (x, max(30, y - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )

            print(
                f"DARK BIN center=({cx}, {cy}) "
                f"bbox=({x}, {y}, {w}, {h}) "
                f"HSV=({H:.0f},{S:.0f},{V:.0f})"
            )

    cv2.imshow(
        "DARK BIN SHAPE DETECTOR",
        frame
    )

    cv2.imshow(
        "MOTION MASK",
        motion_mask
    )

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break


camera.release()
cv2.destroyAllWindows()
