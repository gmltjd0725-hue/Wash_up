import cv2
import numpy as np


# =========================
# S / V 기준
# =========================

S_THRESHOLD = 102
V_THRESHOLD = 191


# =========================
# 빨래 LIGHT / DARK 분류
# =========================

def classify_laundry(roi):
    """
    빨래 ROI 이미지를 받아
    HSV의 중앙값 S, V를 계산한 뒤
    LIGHT / DARK로 분류한다.
    """

    if roi is None:
        raise ValueError(
            "ROI 이미지가 없습니다."
        )

    if roi.size == 0:
        raise ValueError(
            "ROI 이미지가 비어 있습니다."
        )

    # =========================
    # BGR → HSV
    # =========================

    hsv = cv2.cvtColor(
        roi,
        cv2.COLOR_BGR2HSV
    )

    # =========================
    # S / V 추출
    # =========================

    s_channel = hsv[:, :, 1]
    v_channel = hsv[:, :, 2]

    # =========================
    # 대표값 계산
    # =========================

    median_s = float(
        np.median(s_channel)
    )

    median_v = float(
        np.median(v_channel)
    )

    # =========================
    # LIGHT / DARK 판정
    # =========================

    if (
        median_s <= S_THRESHOLD
        and median_v >= V_THRESHOLD
    ):
        laundry_class = "LIGHT"

    else:
        laundry_class = "DARK"

    # =========================
    # 결과 반환
    # =========================

    return {
        "class": laundry_class,
        "s": median_s,
        "v": median_v,
        "s_threshold": S_THRESHOLD,
        "v_threshold": V_THRESHOLD,
    }
