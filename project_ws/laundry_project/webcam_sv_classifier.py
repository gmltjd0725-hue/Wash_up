import subprocess

import cv2

from sv_classifier import classify_laundry


# =========================
# RealSense RGB 설정
# =========================

CAMERA_INDEX = 6
CAMERA_DEVICE = "/dev/video6"

EXPOSURE = 90
WHITE_BALANCE = 4600


# =========================
# RealSense 카메라 설정
# =========================

def apply_camera_settings():

    settings = [
        f"auto_exposure=1",
        f"exposure_time_absolute={EXPOSURE}",
        f"white_balance_automatic=0",
        f"white_balance_temperature={WHITE_BALANCE}",
    ]

    for setting in settings:

        result = subprocess.run(
            [
                "v4l2-ctl",
                "-d",
                CAMERA_DEVICE,
                f"--set-ctrl={setting}",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:

            print(
                f"[VISION] 설정 실패: {setting}"
            )

            print(
                result.stderr.strip()
            )

        else:

            print(
                f"[VISION] 설정 적용: {setting}"
            )


# =========================
# 카메라 설정 적용
# =========================

apply_camera_settings()


# =========================
# 웹캠 시작
# =========================

camera = cv2.VideoCapture(
    CAMERA_INDEX,
    cv2.CAP_V4L2
)


if not camera.isOpened():

    raise RuntimeError(
        "RealSense RGB 카메라를 열 수 없습니다."
    )


print("[VISION] RealSense RGB 시작")
print("[VISION] 종료: q")


# =========================
# 실시간 영상
# =========================

while True:

    success, frame = camera.read()

    if not success:

        print(
            "[VISION] 프레임 읽기 실패"
        )

        break


    height, width = frame.shape[:2]


    # =========================
    # 중앙 ROI
    # =========================

    x1 = int(width * 0.25)
    y1 = int(height * 0.25)

    x2 = int(width * 0.75)
    y2 = int(height * 0.75)


    roi = frame[
        y1:y2,
        x1:x2
    ]


    # =========================
    # S / V 분류
    # =========================

    result = classify_laundry(
        roi
    )

    laundry_class = result[
        "class"
    ]

    s_value = result[
        "s"
    ]

    v_value = result[
        "v"
    ]


    # =========================
    # ROI 표시
    # =========================

    cv2.rectangle(
        frame,
        (x1, y1),
        (x2, y2),
        (255, 255, 255),
        2
    )


    # =========================
    # 결과 표시
    # =========================

    text = (
        f"{laundry_class} "
        f"S={s_value:.0f} "
        f"V={v_value:.0f}"
    )


    cv2.putText(
        frame,
        text,
        (x1, y1 - 15),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2
    )


    cv2.imshow(
        "Laundry S/V Classifier",
        frame
    )


    # =========================
    # q 종료
    # =========================

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break


# =========================
# 종료
# =========================

camera.release()

cv2.destroyAllWindows()

print("[VISION] RealSense RGB 종료")
