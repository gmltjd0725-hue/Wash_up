import csv
from pathlib import Path

import cv2
import numpy as np


BASE_DIR = Path.home() / "project_ws/laundry_project"

LIGHT_DIR = BASE_DIR / "vision_data/light"
DARK_DIR = BASE_DIR / "vision_data/dark"

OUTPUT_CSV = BASE_DIR / "foreground_analysis.csv"


def read_image(image_path):

    data = np.fromfile(
        str(image_path),
        dtype=np.uint8
    )

    return cv2.imdecode(
        data,
        cv2.IMREAD_COLOR
    )


def get_foreground(image):

    height, width = image.shape[:2]

    mask = np.zeros(
        (height, width),
        dtype=np.uint8
    )

    bg_model = np.zeros(
        (1, 65),
        dtype=np.float64
    )

    fg_model = np.zeros(
        (1, 65),
        dtype=np.float64
    )

    margin_x = max(
        int(width * 0.05),
        1
    )

    margin_y = max(
        int(height * 0.05),
        1
    )

    rect = (
        margin_x,
        margin_y,
        width - (margin_x * 2),
        height - (margin_y * 2)
    )

    cv2.grabCut(
        image,
        mask,
        rect,
        bg_model,
        fg_model,
        5,
        cv2.GC_INIT_WITH_RECT
    )

    foreground_mask = np.where(
        (mask == cv2.GC_FGD)
        | (mask == cv2.GC_PR_FGD),
        1,
        0
    ).astype(np.uint8)

    return foreground_mask


def analyze_image(image):

    foreground_mask = get_foreground(
        image
    )

    hsv = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2HSV
    )

    lab = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2LAB
    )

    s = hsv[:, :, 1][
        foreground_mask == 1
    ]

    v = hsv[:, :, 2][
        foreground_mask == 1
    ]

    l = lab[:, :, 0][
        foreground_mask == 1
    ]

    if len(l) == 0:
        return None

    return {
        "mean_s": float(np.mean(s)),
        "median_s": float(np.median(s)),
        "mean_v": float(np.mean(v)),
        "median_v": float(np.median(v)),
        "mean_l": float(np.mean(l)),
        "median_l": float(np.median(l)),
    }


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
        f"[{label}] 이미지 수: {len(image_files)}"
    )

    for image_path in image_files:

        image = read_image(
            image_path
        )

        if image is None:

            print(
                f"[읽기 실패] {image_path.name}"
            )

            continue

        values = analyze_image(
            image
        )

        if values is None:

            print(
                f"[전경 추출 실패] {image_path.name}"
            )

            continue

        rows.append({
            "label": label,
            "filename": image_path.name,
            **values
        })


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


print()
print(
    f"[완료] 총 분석 이미지: {len(rows)}장"
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
        "median_s",
        "median_v",
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
