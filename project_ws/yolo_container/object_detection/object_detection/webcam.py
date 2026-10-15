import cv2

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image
from cv_bridge import CvBridge


class WebcamNode(Node):

    def __init__(self):

        super().__init__("webcam_node")

        self.publisher = self.create_publisher(
            Image,
            "/webcam/image_raw",
            10
        )

        self.bridge = CvBridge()

        self.cap = cv2.VideoCapture(0)

        if not self.cap.isOpened():
            self.get_logger().error(
                "USB Webcam을 열 수 없습니다."
            )
            return

        self.timer = self.create_timer(
            0.1,
            self.timer_callback
        )

        self.get_logger().info(
            "USB Webcam 시작"
        )

    def timer_callback(self):

        if not self.cap.isOpened():
            return

        ret, frame = self.cap.read()

        if not ret:
            self.get_logger().warning(
                "Webcam frame 읽기 실패"
            )
            return

        msg = self.bridge.cv2_to_imgmsg(
            frame,
            encoding="bgr8"
        )

        self.publisher.publish(msg)

    def destroy_node(self):

        if self.cap.isOpened():
            self.cap.release()

        super().destroy_node()


def main(args=None):

    rclpy.init(args=args)

    node = WebcamNode()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()