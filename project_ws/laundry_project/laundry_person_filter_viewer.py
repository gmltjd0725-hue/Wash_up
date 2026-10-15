import os

# GTK / Snap 충돌 방지
for key in [
    "GTK_PATH",
    "GTK_EXE_PREFIX",
    "GTK_DATA_PREFIX",
    "GDK_PIXBUF_MODULE_FILE",
]:
    os.environ.pop(key, None)

import cv2
import numpy as np
import rclpy

from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge


SATURATION_THRESHOLD = 102
VALUE_THRESHOLD = 191

BACKGROUND_FRAMES = 30
MIN_LAUNDRY_AREA = 2500

TEXT_GRAY = (128, 128, 128)


class LaundryPersonFilterViewer(Node):

    def __init__(self):

        super().__init__(
            "laundry_person_filter_viewer"
        )

        self.bridge = CvBridge()

        self.hog = cv2.HOGDescriptor()

        self.hog.setSVMDetector(
            cv2.HOGDescriptor_getDefaultPeopleDetector()
        )

        self.background_frames = []
        self.background = None

        self.create_subscription(
            Image,
            "/webcam/image_raw",
            self.image_callback,
            10
        )

        print()
        print("사람 제외 + 빨래 검출 시작")
        print("처음 약 2초 동안 카메라 앞을 비워두세요.")
        print()

    def image_callback(self, msg):

        frame = self.bridge.imgmsg_to_cv2(
            msg,
            desired_encoding="bgr8"
        )

        display = frame.copy()

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY
        )

        gray = cv2.GaussianBlur(
            gray,
            (7, 7),
            0
        )

        # 1. Background 저장
        if self.background is None:

            self.background_frames.append(
                gray.astype(np.float32)
            )

            count = len(
                self.background_frames
            )

            cv2.putText(
                display,
                f"BACKGROUND {count}/{BACKGROUND_FRAMES}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 0),
                2
            )

            if count >= BACKGROUND_FRAMES:

                self.background = np.mean(
                    self.background_frames,
                    axis=0
                ).astype(np.uint8)

                self.background_frames.clear()

                print("배경 저장 완료")
                print("이제 빨래를 보여주세요.")

            cv2.imshow(
                "Laundry + Person Filter",
                display
            )

            cv2.waitKey(1)

            return

        # 2. Person 검출
        persons, weights = self.hog.detectMultiScale(
            frame,
            winStride=(8, 8),
            padding=(8, 8),
            scale=1.05
        )

        # 3. Background Difference
        difference = cv2.absdiff(
            self.background,
            gray
        )

        _, foreground_mask = cv2.threshold(
            difference,
            25,
            255,
            cv2.THRESH_BINARY
        )

        kernel = np.ones(
            (5, 5),
            dtype=np.uint8
        )

        foreground_mask = cv2.morphologyEx(
            foreground_mask,
            cv2.MORPH_OPEN,
            kernel,
            iterations=1
        )

        foreground_mask = cv2.morphologyEx(
            foreground_mask,
            cv2.MORPH_CLOSE,
            kernel,
            iterations=3
        )

        # 4. Person 영역 제거
        for x, y, w, h in persons:

            cv2.rectangle(
                display,
                (x, y),
                (x + w, y + h),
                (255, 255, 255),
                2
            )

            cv2.putText(
                display,
                "PERSON",
                (x, max(25, y - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 0),
                2
            )

            foreground_mask[
                y:y + h,
                x:x + w
            ] = 0

        # 5. 외곽선 찾기
        contours, _ = cv2.findContours(
            foreground_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        valid_contours = []

        for contour in contours:

            area = cv2.contourArea(
                contour
            )

            if area >= MIN_LAUNDRY_AREA:
                valid_contours.append(
                    contour
                )

        # 6. Laundry 없음
        if not valid_contours:

            cv2.putText(
                display,
                "Laundry: NONE",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                TEXT_GRAY,
                2
            )

            cv2.imshow(
                "Laundry + Person Filter",
                display
            )

            cv2.waitKey(1)

            return

        # 7. 가장 큰 물체 = Laundry
        laundry_contour = max(
            valid_contours,
            key=cv2.contourArea
        )

        x, y, w, h = cv2.boundingRect(
            laundry_contour
        )

        laundry_mask = np.zeros(
            frame.shape[:2],
            dtype=np.uint8
        )

        cv2.drawContours(
            laundry_mask,
            [laundry_contour],
            -1,
            255,
            cv2.FILLED
        )

        # 8. HSV
        hsv = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2HSV
        )

        pixels = (
            laundry_mask == 255
        )

        s_values = hsv[:, :, 1][pixels]
        v_values = hsv[:, :, 2][pixels]

        if (
            s_values.size == 0
            or
            v_values.size == 0
        ):
            return

        saturation = float(
            np.median(s_values)
        )

        value = float(
            np.median(v_values)
        )

        # 9. LIGHT / DARK
        if (
            saturation <= SATURATION_THRESHOLD
            and
            value >= VALUE_THRESHOLD
        ):
            classification = "LIGHT"

        else:
            classification = "DARK"

        # 10. 화면 표시
        cv2.drawContours(
            display,
            [laundry_contour],
            -1,
            (255, 255, 255),
            3
        )

        cv2.rectangle(
            display,
            (x, y),
            (x + w, y + h),
            (255, 255, 255),
            2
        )

        cv2.putText(
            display,
            f"Laundry: {classification}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            TEXT_GRAY,
            2
        )

        cv2.putText(
            display,
            f"S={saturation:.0f}  V={value:.0f}",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            TEXT_GRAY,
            2
        )

        cv2.imshow(
            "Laundry + Person Filter",
            display
        )

        cv2.waitKey(1)


def main():

    rclpy.init()

    node = LaundryPersonFilterViewer()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        cv2.destroyAllWindows()

        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
