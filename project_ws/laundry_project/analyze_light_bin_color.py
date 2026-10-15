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

path = (
    "/home/rokey/project_ws/"
    "laundry_project/bin_color_data/light_bin.jpg"
)

image = cv2.imread(path)

if image is None:
    raise RuntimeError("light_bin.jpg를 읽을 수 없습니다.")

roi = cv2.selectROI(
    "LIGHT BIN COLOR AREA",
    image,
    showCrosshair=True,
    fromCenter=False
)

x, y, w, h = roi

if w == 0 or h == 0:
    raise RuntimeError("영역이 선택되지 않았습니다.")

selected = image[y:y+h, x:x+w]

hsv = cv2.cvtColor(selected, cv2.COLOR_BGR2HSV)
lab = cv2.cvtColor(selected, cv2.COLOR_BGR2LAB)

hsv_median = np.median(
    hsv.reshape(-1, 3),
    axis=0
)

lab_median = np.median(
    lab.reshape(-1, 3),
    axis=0
)

print(
    f"HSV: H={hsv_median[0]:.0f}, "
    f"S={hsv_median[1]:.0f}, "
    f"V={hsv_median[2]:.0f}"
)

print(
    f"LAB: L={lab_median[0]:.0f}, "
    f"a={lab_median[1]:.0f}, "
    f"b={lab_median[2]:.0f}"
)

cv2.destroyAllWindows()
