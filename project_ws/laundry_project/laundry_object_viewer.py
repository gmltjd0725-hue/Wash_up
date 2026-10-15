import cv2
import numpy as np
import rclpy

from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge


SATURATION_THRESHOLD = 102
VALUE_THRESHOLD = 191

BACKGROUND_FRAMES = 30

# 너무 작은 변화 제거
MIN_CONTOUR_AREA = 3000

# 화면의 55% 이상을 차지하면
# 사람 같은 큰 물체로 보고 제외
MAX_OBJECT_AREA_RATIO = 0.55

# 화면 가장자리에서 이 픽셀 이내에 닿으면 제외
EDGE_MARGIN = 12


class LaundryObjectViewer(Node):

    def __init__(self):

        super().__init__(
            "laundry_object_viewer"
        )

        self.bridge = CvBridge()

        self.background_frames = []
        self.background = None

        self.create_subscription(
            Image,
            "/webcam/image_raw",
            self.image_callback,
            10
        )

        print()
        print("빨래 자동 검출 시작")
        print("처음 약 2초 동안 카메라 앞을 비워두세요.")
        print()

    def image_callback(self, msg):

        frame = self.bridge.imgmsg_to_cv2(
            msg,
            desired_encoding="bgr8"
        )

        display = frame.copy()

        height, width = frame.shape[:2]

        frame_area = (
            width * height
        )

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY
        )

        gray = cv2.GaussianBlur(
            gray,
            (7, 7),
            0
        )

        # =========================
        # 1. 배경 학습
        # =========================

        if self.background is None:

            self.background_frames.append(
                gray.astype(
                    np.float32
                )
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
                (255, 255, 255),
                2
            )

            if count >= BACKGROUND_FRAMES:

                self.background = np.mean(
                    self.background_frames,
                    axis=0
                ).astype(
                    np.uint8
                )

                self.background_frames.clear()

                print(
                    "배경 저장 완료"
                )

                print(
                    "이제 빨래를 화면 안쪽에 놓아주세요."
                )

            cv2.imshow(
                "VLA Laundry Object Detection",
                display
            )

            cv2.waitKey(1)

            return

        # =========================
        # 2. 배경 차이
        # =========================

        difference = cv2.absdiff(
            self.background,
            gray
        )

        _, mask = cv2.threshold(
            difference,
            25,
            255,
            cv2.THRESH_BINARY
        )

        kernel = np.ones(
            (5, 5),
            np.uint8
        )

        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_OPEN,
            kernel,
            iterations=2
        )

        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            kernel,
            iterations=3
        )

        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        # =========================
        # 3. 빨래 후보 필터
        # =========================

        valid_contours = []

        for contour in contours:

            area = cv2.contourArea(
                contour
            )

            if area < MIN_CONTOUR_AREA:
                continue

            # 지나치게 큰 물체 제외
            if (
                area
                >
                frame_area
                * MAX_OBJECT_AREA_RATIO
            ):
                continue

            x, y, w, h = cv2.boundingRect(
                contour
            )

            # 화면 가장자리에 붙어 있으면
            # 사람/팔이 들어온 것으로 보고 제외
            touches_edge = (
                x <= EDGE_MARGIN
                or
                y <= EDGE_MARGIN
                or
                x + w
                >= width - EDGE_MARGIN
                or
                y + h
                >= height - EDGE_MARGIN
            )

            if touches_edge:
                continue

            valid_contours.append(
                contour
            )

        # =========================
        # 4. 빨래 없음
        # =========================

        if not valid_contours:

            cv2.putText(
                display,
                "Laundry: NONE",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (255, 255, 255),
                2
            )

            cv2.imshow(
                "VLA Laundry Object Detection",
                display
            )

            cv2.waitKey(1)

            return

        # 남은 후보 중 가장 큰 물체
        contour = max(
            valid_contours,
            key=cv2.contourArea
        )

        x, y, w, h = cv2.boundingRect(
            contour
        )

        # =========================
        # 5. 빨래 실제 외곽선 Mask
        # =========================

        object_mask = np.zeros(
            frame.shape[:2],
            dtype=np.uint8
        )

        cv2.drawContours(
            object_mask,
            [contour],
            -1,
            255,
            thickness=cv2.FILLED
        )

        # =========================
        # 6. HSV 분석
        # =========================

        hsv = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2HSV
        )

        object_pixels = (
            object_mask == 255
        )

        saturation_values = (
            hsv[:, :, 1][
                object_pixels
            ]
        )

        value_values = (
            hsv[:, :, 2][
                object_pixels
            ]
        )

        if (
            saturation_values.size == 0
            or
            value_values.size == 0
        ):
            return

        saturation = float(
            np.median(
                saturation_values
            )
        )

        value = float(
            np.median(
                value_values
            )
        )

        # =========================
        # 7. LIGHT / DARK
        # =========================

        if (
            saturation
            <= SATURATION_THRESHOLD
            and
            value
            >= VALUE_THRESHOLD
        ):

            classification = "LIGHT"

        else:

            classification = "DARK"

        # =========================
        # 8. 화면 표시
        # =========================

        cv2.drawContours(
            display,
            [contour],
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
            (255, 255, 255),
            2
        )

        cv2.putText(
            display,
            f"S={saturation:.0f}  V={value:.0f}",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        cv2.imshow(
            "VLA Laundry Object Detection",
            display
        )

        cv2.waitKey(1)


def main():

    rclpy.init()

    node = LaundryObjectViewer()

    try:

        rclpy.spin(
            node
        )

    except KeyboardInterrupt:

        pass

    finally:

        cv2.destroyAllWindows()

        node.destroy_node()

        if rclpy.ok():

            rclpy.shutdown()


if __name__ == "__main__":
    main()
