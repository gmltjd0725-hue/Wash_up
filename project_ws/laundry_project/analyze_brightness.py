import csv
from pathlib import Path

import cv2
import numpy as np


# =========================
# 경로 설정
# =========================

BASE_DIR = Path.home() / "project_ws/laundry_project"

LIGHT_DIR = BASE_DIR / "vision_data/light"
DARK_DIR = BASE_DIR / "vision_data/dark"

OUTPUT_CSV = BASE_DIR / "brightness_analysis.csv"


# =========================
# 한글 파일명 이미지 읽기
# =========================

def read_image(image_path):

    image_data = np.fromfile(
        str(image_path),
        dtype=np.uint8
    )

    image = cv2.imdecode(
        image_data,
        cv2.IMREAD_COLOR
    )

    return image


# =========================
# 이미지 특징 추출
# =========================

def analyze_image(image):

    # BGR → HSV
    hsv = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2HSV
    )

    # BGR → LAB
    lab = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2LAB
    )

    # HSV
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]

    # LAB
    l = lab[:, :, 0]

    return {
        "mean_s": float(np.mean(s)),
        "median_s": float(np.median(s)),

        "mean_v": float(np.mean(v)),
        "median_v": float(np.median(v)),

        "mean_l": float(np.mean(l)),
        "median_l": float(np.median(l)),
    }


# =========================
# 데이터 처리
# =========================

rows = []

folders = [
    ("LIGHT", LIGHT_DIR),
    ("DARK", DARK_DIR),
]

for label, folder in folders:

    image_files = sorted(
        folder.glob("*.png")
    )

    print(
        f"[{label}] 이미지 수: "
        f"{len(image_files)}"
    )

    for image_path in image_files:

        image = read_image(
            image_path
        )

        if image is None:

            print(
                f"[ERROR] 이미지 읽기 실패: "
                f"{image_path.name}"
            )

            continue

        values = analyze_image(
            image
        )

        row = {
            "label": label,
            "filename": image_path.name,
            **values
        }

        rows.append(
            row
        )


# =========================
# CSV 저장
# =========================

fieldnames = [
    "label",
    "filename",
    "mean_s",
    "median_s",
    "mean_v",
    "median_v",
    "mean_l",
    "median_l",
]

with open(
    OUTPUT_CSV,
    "w",
    newline="",
    encoding="utf-8-sig"
) as csv_file:

    writer = csv.DictWriter(
        csv_file,
        fieldnames=fieldnames
    )

    writer.writeheader()
    writer.writerows(
        rows
    )


# =========================
# 간단한 평균 결과 출력
# =========================

print()
print(
    f"[완료] 총 분석 이미지: "
    f"{len(rows)}장"
)

print(
    f"[CSV] {OUTPUT_CSV}"
)

for label in [
    "LIGHT",
    "DARK"
]:

    selected = [
        row
        for row in rows
        if row["label"] == label
    ]

    if not selected:
        continue

    print()
    print(
        f"===== {label} ====="
    )

    for key in [
        "mean_s",
        "median_s",
        "mean_v",
        "median_v",
        "mean_l",
        "median_l",
    ]:

        values = [
            row[key]
            for row in selected
        ]

        print(
            f"{key}: "
            f"{np.mean(values):.2f}"
        )
