import csv
from pathlib import Path


BASE_DIR = Path.home() / "project_ws/laundry_project"
CSV_PATH = BASE_DIR / "brightness_analysis.csv"

THRESHOLD = 148


wrong_count = 0

with open(
    CSV_PATH,
    "r",
    encoding="utf-8-sig"
) as csv_file:

    reader = csv.DictReader(csv_file)

    for row in reader:

        label = row["label"]
        filename = row["filename"]
        median_l = float(row["median_l"])

        if median_l >= THRESHOLD:
            prediction = "LIGHT"
        else:
            prediction = "DARK"

        if prediction != label:

            wrong_count += 1

            print(
                f"{wrong_count:02d}. "
                f"{filename} | "
                f"정답={label} | "
                f"예측={prediction} | "
                f"LAB L={median_l:.2f}"
            )


print()
print(
    f"[오분류] 총 {wrong_count}장"
)
