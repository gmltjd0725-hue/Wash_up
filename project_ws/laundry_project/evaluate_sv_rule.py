import csv
from pathlib import Path


BASE_DIR = Path.home() / "project_ws/laundry_project"
CSV_PATH = BASE_DIR / "foreground_analysis.csv"

S_THRESHOLD = 102
V_THRESHOLD = 191


correct = 0
total = 0

light_count = 0
dark_count = 0

wrong_rows = []


with open(
    CSV_PATH,
    "r",
    encoding="utf-8-sig"
) as csv_file:

    reader = csv.DictReader(csv_file)

    for row in reader:

        label = row["label"]
        filename = row["filename"]

        s = float(row["median_s"])
        v = float(row["median_v"])

        if (
            s <= S_THRESHOLD
            and v >= V_THRESHOLD
        ):
            prediction = "LIGHT"
            light_count += 1

        else:
            prediction = "DARK"
            dark_count += 1

        total += 1

        if prediction == label:
            correct += 1

        else:
            wrong_rows.append(
                (
                    filename,
                    label,
                    prediction,
                    s,
                    v
                )
            )


accuracy = (
    correct
    / total
    * 100.0
)


print(
    f"[데이터] 총 {total}장"
)

print()
print(
    "===== S/V 규칙 ====="
)

print(
    f"LIGHT = S <= {S_THRESHOLD} "
    f"AND V >= {V_THRESHOLD}"
)

print(
    f"DARK  = S > {S_THRESHOLD} "
    f"OR V < {V_THRESHOLD}"
)

print()
print(
    f"정답 개수: {correct}/{total}"
)

print(
    f"정확도: {accuracy:.2f}%"
)

print()
print(
    f"LIGHT 판정: {light_count}장"
)

print(
    f"DARK 판정: {dark_count}장"
)

print()
print(
    f"오분류: {len(wrong_rows)}장"
)

for index, (
    filename,
    label,
    prediction,
    s,
    v
) in enumerate(
    wrong_rows,
    start=1
):

    print(
        f"{index:02d}. "
        f"{filename} | "
        f"정답={label} | "
        f"예측={prediction} | "
        f"S={s:.2f} | "
        f"V={v:.2f}"
    )
