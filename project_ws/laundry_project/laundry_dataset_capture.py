import os
import cv2
import rclpy

from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge


SAVE_DIR = os.path.expanduser(
    "~/project_ws/laundry_project/dataset/images"
)


class LaundryDatasetCapture(Node):

    def __init__(self):
        super().__init__("laundry_dataset_capture")

        os.makedirs(
            SAVE_DIR,
            exist_ok=True
        )

        self.bridge = CvBridge()
        self.latest_frame = None

        self.create_subscription(
            Image,
            "/webcam/image_raw",
            self.image_callback,
            10
        )

        existing = [
            name
            for name in os.listdir(SAVE_DIR)
            if name.endswith(".jpg")
        ]

        self.image_number = len(existing)

        print()
        print("빨래 데이터셋 촬영 시작")
        print("S = 사진 저장")
        print("Q = 종료")
        print()

    def image_callback(self, msg):

        frame = self.bridge.imgmsg_to_cv2(
            msg,
            desired_encoding="bgr8"
        )

        self.latest_frame = frame.copy()

        display = frame.copy()

        cv2.putText(
            display,
            f"Saved: {self.image_number}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 0, 0),
            3
        )

        cv2.putText(
            display,
            "S: SAVE   Q: QUIT",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 0),
            2
        )

        cv2.imshow(
            "Laundry Dataset Capture",
            display
        )

        key = cv2.waitKey(1) & 0xFF

        if key == ord("s"):

            filename = os.path.join(
                SAVE_DIR,
                f"laundry_{self.image_number:04d}.jpg"
            )

            cv2.imwrite(
                filename,
                self.latest_frame
            )

            print(
                f"저장: {filename}"
            )

            self.image_number += 1

        elif key == ord("q"):

            rclpy.shutdown()


def main():

    rclpy.init()

    node = LaundryDatasetCapture()

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
