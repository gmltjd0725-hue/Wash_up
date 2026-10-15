import os
import json

for key in [
    "GTK_PATH",
    "GTK_EXE_PREFIX",
    "GTK_DATA_PREFIX",
    "GDK_PIXBUF_MODULE_FILE",
]:
    os.environ.pop(
        key,
        None
    )

import cv2
import rclpy

from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String


TEXT_GRAY = (
    230,
    230,
    230
)

GREEN = (
    0,
    255,
    0
)

YELLOW = (
    0,
    255,
    255
)


class BinOCRViewer(Node):

    def __init__(self):

        super().__init__(
            "bin_ocr_viewer"
        )

        self.bridge = CvBridge()

        self.detected_bins = set()

        self.raw_text = ""
        self.color = "UNKNOWN"

        self.reasons = {
            "BIN_A": "-",
            "BIN_B": "-"
        }

        self.create_subscription(
            Image,
            "/webcam/image_raw",
            self.image_callback,
            10
        )

        # OCR + COLOR가 합쳐진
        # 최종 등록 상태
        self.create_subscription(
            String,
            "/laundry/bin_detections",
            self.bin_callback,
            10
        )

        # 현재 색상을 더 빠르게
        # 화면에 표시하기 위한 구독
        self.create_subscription(
            String,
            "/laundry/bin_color_detections",
            self.color_callback,
            10
        )

        self.get_logger().info(
            "BIN OCR + COLOR Viewer 시작"
        )

    # ==========================================================
    # COLOR
    # ==========================================================

    def color_callback(
        self,
        msg
    ):

        try:

            data = json.loads(
                msg.data
            )

            self.color = data.get(
                "color",
                "UNKNOWN"
            )

        except Exception:

            pass

    # ==========================================================
    # 통합 BIN 상태
    # ==========================================================

    def bin_callback(
        self,
        msg
    ):

        try:

            data = json.loads(
                msg.data
            )

            bins = data.get(
                "bins",
                []
            )

            self.raw_text = data.get(
                "raw_text",
                ""
            )

            self.color = data.get(
                "color",
                self.color
            )

            reasons = data.get(
                "reasons",
                {}
            )

            self.reasons[
                "BIN_A"
            ] = reasons.get(
                "BIN_A",
                "-"
            )

            self.reasons[
                "BIN_B"
            ] = reasons.get(
                "BIN_B",
                "-"
            )

            self.detected_bins = set(
                bins
            )

            # 두 통 모두 등록되면
            # 기존처럼 창 자동 종료
            if (
                "BIN_A"
                in self.detected_bins
                and
                "BIN_B"
                in self.detected_bins
            ):

                self.get_logger().info(
                    "BIN_A / BIN_B 등록 완료"
                )

                cv2.destroyAllWindows()

                if rclpy.ok():

                    rclpy.shutdown()

        except Exception:

            pass

    # ==========================================================
    # 화면
    # ==========================================================

    def image_callback(
        self,
        msg
    ):

        frame = self.bridge.imgmsg_to_cv2(
            msg,
            desired_encoding="bgr8"
        )

        display = frame.copy()

        height, width = (
            frame.shape[:2]
        )

        roi_width = int(
            width * 0.70
        )

        roi_height = int(
            height * 0.60
        )

        x1 = (
            width - roi_width
        ) // 2

        y1 = (
            height - roi_height
        ) // 2

        x2 = x1 + roi_width
        y2 = y1 + roi_height

        cv2.rectangle(
            display,
            (x1, y1),
            (x2, y2),
            YELLOW,
            3
        )

        # ==================================
        # BIN_A
        # ==================================

        if (
            "BIN_A"
            in self.detected_bins
        ):

            a_status = "OK"
            a_color = GREEN

        else:

            a_status = "WAIT"
            a_color = YELLOW

        cv2.putText(
            display,
            f"BIN_A: {a_status}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            a_color,
            2
        )

        cv2.putText(
            display,
            f"REASON A: "
            f"{self.reasons['BIN_A']}",
            (20, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            TEXT_GRAY,
            2
        )

        # ==================================
        # BIN_B
        # ==================================

        if (
            "BIN_B"
            in self.detected_bins
        ):

            b_status = "OK"
            b_color = GREEN

        else:

            b_status = "WAIT"
            b_color = YELLOW

        cv2.putText(
            display,
            f"BIN_B: {b_status}",
            (20, 115),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            b_color,
            2
        )

        cv2.putText(
            display,
            f"REASON B: "
            f"{self.reasons['BIN_B']}",
            (20, 150),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            TEXT_GRAY,
            2
        )

        # ==================================
        # 현재 OCR / COLOR
        # ==================================

        cv2.putText(
            display,
            f"OCR: {self.raw_text[:25] or '-'}",
            (20, 195),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            TEXT_GRAY,
            2
        )

        cv2.putText(
            display,
            f"COLOR: {self.color}",
            (20, 230),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            TEXT_GRAY,
            2
        )

        cv2.putText(
            display,
            "A OR LIGHT_PINK -> BIN_A",
            (20, height - 55),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            TEXT_GRAY,
            2
        )

        cv2.putText(
            display,
            "B OR BROWN -> BIN_B",
            (20, height - 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            TEXT_GRAY,
            2
        )

        cv2.imshow(
            "BIN OCR + COLOR",
            display
        )

        cv2.waitKey(1)


def main(args=None):

    rclpy.init(
        args=args
    )

    node = BinOCRViewer()

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
