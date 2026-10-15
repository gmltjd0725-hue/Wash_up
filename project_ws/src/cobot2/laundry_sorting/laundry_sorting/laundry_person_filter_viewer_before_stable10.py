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

# HOG 후보 영역 안에서 피부색이 이 비율 이상이면 PERSON 인정
SKIN_RATIO_THRESHOLD = 0.02


class LaundryPersonFilterViewer(Node):

    def __init__(self):

        super().__init__(
            "laundry_person_filter_viewer"
        )

        self.bridge = CvBridge()

        # =========================
        # Person Detector
        # =========================

        self.hog = cv2.HOGDescriptor()

        self.hog.setSVMDetector(
            cv2.HOGDescriptor_getDefaultPeopleDetector()
        )

        # =========================
        # Background
        # =========================

        self.background_frames = []
        self.background = None

        self.create_subscription(
            Image,
            "/webcam/image_raw",
            self.image_callback,
            10
        )

        print()
        print("피부색 검증 PERSON + 빨래 검출 시작")
        print("처음 약 2초 동안 카메라 앞을 비워두세요.")
        print()

    def get_skin_ratio(self, roi):

        if roi is None or roi.size == 0:
            return 0.0

        # =========================
        # YCrCb 피부색 검사
        # =========================

        ycrcb = cv2.cvtColor(
            roi,
            cv2.COLOR_BGR2YCrCb
        )

        # 비교적 넓게 잡은 피부색 범위
        lower_skin = np.array(
            [0, 133, 77],
            dtype=np.uint8
        )

        upper_skin = np.array(
            [255, 180, 135],
            dtype=np.uint8
        )

        skin_mask = cv2.inRange(
            ycrcb,
            lower_skin,
            upper_skin
        )

        # 작은 노이즈 제거
        kernel = np.ones(
            (3, 3),
            dtype=np.uint8
        )

        skin_mask = cv2.morphologyEx(
            skin_mask,
            cv2.MORPH_OPEN,
            kernel,
            iterations=1
        )

        skin_pixels = cv2.countNonZero(
            skin_mask
        )

        total_pixels = (
            roi.shape[0]
            * roi.shape[1]
        )

        if total_pixels == 0:
            return 0.0

        return (
            skin_pixels
            / total_pixels
        )

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

        # =========================
        # 1. Background 저장
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
                    "이제 사람 또는 빨래를 보여주세요."
                )

            cv2.imshow(
                "Laundry + Skin Person Filter",
                display
            )

            cv2.waitKey(1)

            return

        # =========================
        # 2. HOG Person 후보 검출
        # =========================

        persons, weights = (
            self.hog.detectMultiScale(
                frame,
                winStride=(8, 8),
                padding=(8, 8),
                scale=1.05
            )
        )

        # =========================
        # 3. Background Difference
        # =========================

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

        # =========================
        # 4. HOG + 피부색 검증
        # =========================

        for (x, y, w, h), weight in zip(
            persons,
            weights
        ):

            confidence = float(
                weight
            )

            frame_h, frame_w = (
                frame.shape[:2]
            )

            x1 = max(
                0,
                x
            )

            y1 = max(
                0,
                y
            )

            x2 = min(
                frame_w,
                x + w
            )

            y2 = min(
                frame_h,
                y + h
            )

            person_roi = frame[
                y1:y2,
                x1:x2
            ]

            skin_ratio = self.get_skin_ratio(
                person_roi
            )

            # =========================
            # 실제 PERSON 인정
            # =========================

            if skin_ratio >= SKIN_RATIO_THRESHOLD:

                cv2.rectangle(
                    display,
                    (x1, y1),
                    (x2, y2),
                    (255, 255, 255),
                    2
                )

                cv2.putText(
                    display,
                    f"PERSON skin={skin_ratio:.3f}",
                    (
                        x1,
                        max(
                            25,
                            y1 - 10
                        )
                    ),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2
                )

                # 실제 사람으로 인정된 영역만 제거
                foreground_mask[
                    y1:y2,
                    x1:x2
                ] = 0

            # =========================
            # 피부색 부족 → 오검출
            # =========================

            else:

                cv2.rectangle(
                    display,
                    (x1, y1),
                    (x2, y2),
                    (255, 255, 255),
                    1
                )

                cv2.putText(
                    display,
                    f"REJECT skin={skin_ratio:.3f}",
                    (
                        x1,
                        max(
                            25,
                            y1 - 10
                        )
                    ),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 255, 255),
                    1
                )

        # =========================
        # 5. 남은 물체 외곽선
        # =========================

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

        # =========================
        # 6. Laundry 없음
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
                "Laundry + Skin Person Filter",
                display
            )

            cv2.waitKey(1)

            return

        # =========================
        # 7. 가장 큰 남은 물체 = Laundry
        # =========================

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

        # =========================
        # 8. Laundry HSV
        # =========================

        hsv = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2HSV
        )

        pixels = (
            laundry_mask == 255
        )

        s_values = hsv[:, :, 1][
            pixels
        ]

        v_values = hsv[:, :, 2][
            pixels
        ]

        if (
            s_values.size == 0
            or
            v_values.size == 0
        ):
            return

        saturation = float(
            np.median(
                s_values
            )
        )

        value = float(
            np.median(
                v_values
            )
        )

        # =========================
        # 9. LIGHT / DARK
        # =========================

        if (
            saturation <= SATURATION_THRESHOLD
            and
            value >= VALUE_THRESHOLD
        ):

            classification = "LIGHT"

        else:

            classification = "DARK"

        # =========================
        # 10. 화면 표시
        # =========================

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
            (128, 128, 128),
            2
        )

        cv2.putText(
            display,
            f"S={saturation:.0f}  V={value:.0f}",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (128, 128, 128),
            2
        )

        cv2.imshow(
            "Laundry + Skin Person Filter",
            display
        )

        cv2.waitKey(1)


def main():

    rclpy.init()

    node = LaundryPersonFilterViewer()

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
