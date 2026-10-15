import cv2
import numpy as np
import rclpy

from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge


WARMUP_FRAMES = 60
BACKGROUND_FRAMES = 30


class LaundryAreaTest(Node):

    def __init__(self):

        super().__init__("laundry_area_test")

        self.bridge = CvBridge()

        self.warmup_count = 0
        self.background_frames = []
        self.background = None

        self.create_subscription(
            Image,
            "/webcam/image_raw",
            self.image_callback,
            10
        )

        print("AREA 측정 시작")
        print("WARMUP + BACKGROUND 동안 화면을 완전히 비워두세요.")

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
        # 1. Warmup
        # =========================

        if self.warmup_count < WARMUP_FRAMES:

            self.warmup_count += 1

            cv2.putText(
                display,
                f"WARMUP {self.warmup_count}/{WARMUP_FRAMES}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 0),
                2
            )

            cv2.imshow(
                "Laundry AREA Test",
                display
            )

            cv2.waitKey(1)
            return

        # =========================
        # 2. Background
        # =========================

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

            cv2.imshow(
                "Laundry AREA Test",
                display
            )

            cv2.waitKey(1)
            return

        # =========================
        # 3. Background Difference
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
        # 4. 가장 큰 contour
        # =========================

        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:

            cv2.putText(
                display,
                "AREA=0",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 0, 0),
                2
            )

        else:

            contour = max(
                contours,
                key=cv2.contourArea
            )

            area = cv2.contourArea(
                contour
            )

            x, y, w, h = cv2.boundingRect(
                contour
            )

            cv2.rectangle(
                display,
                (x, y),
                (x + w, y + h),
                (0, 0, 0),
                2
            )

            cv2.putText(
                display,
                f"AREA={area:.0f}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 0, 0),
                2
            )

        cv2.imshow(
            "Laundry AREA Test",
            display
        )

        cv2.waitKey(1)


def main():

    rclpy.init()

    node = LaundryAreaTest()

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
