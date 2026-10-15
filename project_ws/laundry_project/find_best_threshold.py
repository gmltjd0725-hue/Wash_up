import csv
from pathlib import Path


BASE_DIR = Path.home() / "project_ws/laundry_project"
CSV_PATH = BASE_DIR / "brightness_analysis.csv"


def load_data():

    rows = []

    with open(
        CSV_PATH,
        "r",
        encoding="utf-8-sig"
    ) as csv_file:

        reader = csv.DictReader(
            csv_file
        )

        for row in reader:

            rows.append({
                "label": row["label"],
                "median_v": float(
                    row["median_v"]
                ),
                "median_l": float(
                    row["median_l"]
                ),
            })

    return rows


def find_best_threshold(
    rows,
    key
):

    best_threshold = None
    best_correct = -1

    for threshold in range(
        0,
        256
    ):

        correct = 0

        for row in rows:

            value = row[key]

            if value >= threshold:
                prediction = "LIGHT"
            else:
                prediction = "DARK"

            if prediction == row["label"]:
                correct += 1

        if correct > best_correct:
            best_correct = correct
            best_threshold = threshold

    accuracy = (
        best_correct
        / len(rows)
        * 100.0
    )

    return (
        best_threshold,
        best_correct,
        accuracy
    )


rows = load_data()

print(
    f"[데이터] 총 {len(rows)}장"
)

print()


v_threshold, v_correct, v_accuracy = (
    find_best_threshold(
        rows,
        "median_v"
    )
)

print(
    "===== HSV V ====="
)

print(
    f"최적 경계값: {v_threshold}"
)

print(
    f"정답 개수: {v_correct}/{len(rows)}"
)

print(
    f"정확도: {v_accuracy:.2f}%"
)

print()


l_threshold, l_correct, l_accuracy = (
    find_best_threshold(
        rows,
        "median_l"
    )
)

print(
    "===== LAB L ====="
)

print(
    f"최적 경계값: {l_threshold}"
)

print(
    f"정답 개수: {l_correct}/{len(rows)}"
)

print(
    f"정확도: {l_accuracy:.2f}%"
)
