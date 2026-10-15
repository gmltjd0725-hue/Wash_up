import os
import json

for key in [
    "GTK_PATH",
    "GTK_EXE_PREFIX",
    "GTK_DATA_PREFIX",
    "GDK_PIXBUF_MODULE_FILE",
]:
    os.environ.pop(key, None)

import cv2
import rclpy

from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String


class BinColorViewer(Node):

    def __init__(self):

        super().__init__(
            "bin_color_viewer"
        )

        self.bridge = CvBridge()

        self.result = {}

        self.create_subscription(
            Image,
            "/webcam/image_raw",
            self.image_callback,
            10
        )

        self.create_subscription(
            String,
            "/laundry/bin_color_detections",
            self.result_callback,
            10
        )

        self.get_logger().info(
            "BIN A/B + COLOR Viewer 시작"
        )

    def result_callback(
        self,
        msg
    ):

        try:

            self.result = json.loads(
                msg.data
            )

        except Exception:

            self.result = {}

    def put_line(
        self,
        image,
        text,
        y,
        color=(255, 255, 255),
        scale=0.72
    ):

        cv2.putText(
            image,
            text,
            (20, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            color,
            2,
            cv2.LINE_AA
        )

    def image_callback(
        self,
        msg
    ):

        frame = self.bridge.imgmsg_to_cv2(
            msg,
            desired_encoding="bgr8"
        )

        display = frame.copy()

        frame_h, frame_w = frame.shape[:2]

        roi_w = int(
            frame_w * 0.70
        )

        roi_h = int(
            frame_h * 0.60
        )

        x1 = (
            frame_w
            - roi_w
        ) // 2

        y1 = (
            frame_h
            - roi_h
        ) // 2

        x2 = x1 + roi_w
        y2 = y1 + roi_h

        status = self.result.get(
            "status",
            "UNKNOWN"
        )

        if status == "CONFIRMED":

            box_color = (
                0,
                255,
                0
            )

        elif status == "CONFLICT":

            box_color = (
                0,
                0,
                255
            )

        else:

            box_color = (
                0,
                255,
                255
            )

        cv2.rectangle(
            display,
            (x1, y1),
            (x2, y2),
            box_color,
            3
        )

        label_bbox = self.result.get(
            "label_bbox"
        )

        if (
            label_bbox is not None
            and
            len(label_bbox) == 4
        ):

            lx, ly, lw, lh = (
                label_bbox
            )

            cv2.rectangle(
                display,
                (lx, ly),
                (
                    lx + lw,
                    ly + lh
                ),
                (255, 255, 255),
                3
            )

        letter = self.result.get(
            "ocr_letter"
        )

        color = self.result.get(
            "color",
            "UNKNOWN"
        )

        bin_name = self.result.get(
            "bin"
        )

        laundry_type = self.result.get(
            "laundry_type"
        )

        hsv = self.result.get(
            "hsv"
        )

        lab = self.result.get(
            "lab"
        )

        self.put_line(
            display,
            f"OCR: {letter or '-'}",
            35
        )

        self.put_line(
            display,
            f"COLOR: {color}",
            70
        )

        if bin_name is None:

            result_text = "-"

        else:

            result_text = (
                f"{bin_name} / "
                f"{laundry_type}"
            )

        self.put_line(
            display,
            f"RESULT: {result_text}",
            105,
            box_color
        )

        self.put_line(
            display,
            f"STATUS: {status}",
            140,
            box_color
        )

        self.put_line(
            display,
            f"HSV: {hsv}",
            175,
            (200, 200, 200),
            0.60
        )

        self.put_line(
            display,
            f"LAB: {lab}",
            205,
            (200, 200, 200),
            0.60
        )

        cv2.imshow(
            "BIN A-B + COLOR VERIFY",
            display
        )

        key = (
            cv2.waitKey(1)
            & 0xFF
        )

        if key == ord("q"):

            if rclpy.ok():

                rclpy.shutdown()


def main(args=None):

    rclpy.init(
        args=args
    )

    node = BinColorViewer()

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
