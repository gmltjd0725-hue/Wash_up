import cv2
import numpy as np
import rclpy

from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge


SATURATION_THRESHOLD = 102
VALUE_THRESHOLD = 191


class VisionSVViewer(Node):

    def __init__(self):
        super().__init__("vision_sv_viewer")

        self.bridge = CvBridge()

        self.create_subscription(
            Image,
            "/webcam/image_raw",
            self.image_callback,
            10
        )

        print("LIGHT / DARK 실시간 확인 시작")

    def image_callback(self, msg):

        frame = self.bridge.imgmsg_to_cv2(
            msg,
            desired_encoding="bgr8"
        )

        height, width = frame.shape[:2]

        # 중앙 50% 영역
        x1 = width // 4
        y1 = height // 4
        x2 = width * 3 // 4
        y2 = height * 3 // 4

        roi = frame[
            y1:y2,
            x1:x2
        ]

        hsv = cv2.cvtColor(
            roi,
            cv2.COLOR_BGR2HSV
        )

        saturation = float(
            np.median(
                hsv[:, :, 1]
            )
        )

        value = float(
            np.median(
                hsv[:, :, 2]
            )
        )

        if (
            saturation <= SATURATION_THRESHOLD
            and
            value >= VALUE_THRESHOLD
        ):
            classification = "LIGHT"
        else:
            classification = "DARK"

        # ROI 네모
        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            (255, 255, 255),
            2
        )

        # 결과 표시
        cv2.putText(
            frame,
            f"S = {saturation:.0f}",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            f"V = {value:.0f}",
            (20, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            classification,
            (20, 115),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (255, 255, 255),
            3
        )

        cv2.imshow(
            "VLA Vision - LIGHT / DARK",
            frame
        )

        cv2.waitKey(1)


def main():

    rclpy.init()

    node = VisionSVViewer()

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
