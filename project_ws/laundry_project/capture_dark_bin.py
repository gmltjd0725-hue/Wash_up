import os

for key in [
    "GTK_PATH",
    "GTK_EXE_PREFIX",
    "GTK_DATA_PREFIX",
    "GDK_PIXBUF_MODULE_FILE",
]:
    os.environ.pop(key, None)

import cv2

camera = cv2.VideoCapture(6)

if not camera.isOpened():
    raise RuntimeError("/dev/video6 카메라를 열 수 없습니다.")

camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

save_path = (
    "/home/rokey/project_ws/"
    "laundry_project/bin_color_data/"
    "dark_bin.jpg"
)

print("중앙 사각형 안에 DARK용 빨래통을 넣으세요.")
print("S = 저장")
print("Q = 종료")

while True:

    ret, frame = camera.read()

    if not ret:
        continue

    h, w = frame.shape[:2]

    roi_w = int(w * 0.55)
    roi_h = int(h * 0.65)

    x1 = (w - roi_w) // 2
    y1 = (h - roi_h) // 2
    x2 = x1 + roi_w
    y2 = y1 + roi_h

    display = frame.copy()

    cv2.rectangle(
        display,
        (x1, y1),
        (x2, y2),
        (0, 255, 0),
        2
    )

    cv2.imshow(
        "DARK BIN PHOTO",
        display
    )

    key = cv2.waitKey(1) & 0xFF

    if key == ord("s"):

        dark_bin = frame[y1:y2, x1:x2]

        cv2.imwrite(
            save_path,
            dark_bin
        )

        print("DARK 빨래통 사진 저장 완료")
        break

    if key == ord("q"):
        break

camera.release()
cv2.destroyAllWindows()
