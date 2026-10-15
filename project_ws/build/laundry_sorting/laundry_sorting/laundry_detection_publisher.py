import json

import cv2
import numpy as np
import rclpy

from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge


BACKGROUND_FRAMES = 30
MIN_LAUNDRY_AREA = 2500

# HOG 후보 박스 안에서 피부색이 이 비율 이상이면 실제 PERSON
SKIN_RATIO_THRESHOLD = 0.02


class LaundryDetectionPublisher(Node):

    def __init__(self):

        super().__init__(
            "laundry_detection_publisher"
        )

        self.bridge = CvBridge()

        self.publisher = self.create_publisher(
            String,
            "/laundry/detections",
            10
        )

        self.create_subscription(
            Image,
            "/webcam/image_raw",
            self.image_callback,
            10
        )

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

        self.get_logger().info(
            "Laundry Detection Publisher 시작"
        )

        self.get_logger().info(
            "초기 배경 저장 중 - 카메라 앞을 비워주세요."
        )

    def get_skin_ratio(self, roi):

        if roi is None or roi.size == 0:
            return 0.0

        # =========================
        # YCrCb 피부색 검출
        # =========================

        ycrcb = cv2.cvtColor(
            roi,
            cv2.COLOR_BGR2YCrCb
        )

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
        # 1. 초기 배경 저장
        # =========================

        if self.background is None:

            self.background_frames.append(
                gray.astype(
                    np.float32
                )
            )

            if (
                len(self.background_frames)
                >= BACKGROUND_FRAMES
            ):

                self.background = np.mean(
                    self.background_frames,
                    axis=0
                ).astype(
                    np.uint8
                )

                self.background_frames.clear()

                self.get_logger().info(
                    "배경 저장 완료"
                )

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
        # 3. 배경 차분
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
            dtype=np.uint8
        )

        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_OPEN,
            kernel,
            iterations=1
        )

        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            kernel,
            iterations=3
        )

        # =========================
        # 4. HOG + 피부색 PERSON 검증
        # =========================

        frame_h, frame_w = (
            frame.shape[:2]
        )

        for (x, y, w, h), weight in zip(
            persons,
            weights
        ):

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

            # 피부색이 충분한 경우에만
            # 실제 PERSON으로 인정
            if (
                skin_ratio
                >= SKIN_RATIO_THRESHOLD
            ):

                mask[
                    y1:y2,
                    x1:x2
                ] = 0

        # =========================
        # 5. 외곽선 찾기
        # =========================

        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        valid_contours = []

        for contour in contours:

            area = cv2.contourArea(
                contour
            )

            if (
                area
                >= MIN_LAUNDRY_AREA
            ):

                valid_contours.append(
                    contour
                )

        if not valid_contours:
            return

        # =========================
        # 6. 가장 큰 남은 물체 = 빨래
        # =========================

        laundry_contour = max(
            valid_contours,
            key=cv2.contourArea
        )

        x, y, w, h = cv2.boundingRect(
            laundry_contour
        )

        # =========================
        # 7. ROS 메시지 전송
        # =========================

        detection = {
            "class_name": "laundry",
            "confidence": 1.0,
            "bbox": {
                "x1": int(x),
                "y1": int(y),
                "x2": int(x + w),
                "y2": int(y + h)
            }
        }

        msg_out = String()

        msg_out.data = json.dumps(
            [detection]
        )

        self.publisher.publish(
            msg_out
        )


def main(args=None):

    rclpy.init(
        args=args
    )

    node = LaundryDetectionPublisher()

    try:

        rclpy.spin(
            node
        )

    except KeyboardInterrupt:

        pass

    finally:

        node.destroy_node()

        if rclpy.ok():

            rclpy.shutdown()


if __name__ == "__main__":
    main()
