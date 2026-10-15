import os
import re
import subprocess
import tempfile
import time

import cv2
import rclpy

from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge


class BinOCRViewer(Node):

    def __init__(self):
        super().__init__("bin_ocr_viewer")

        self.bridge = CvBridge()

        self.last_ocr_time = 0.0
        self.ocr_interval = 1.0

        self.detected_bin = "NONE"
        self.ocr_text = ""

        self.create_subscription(
            Image,
            "/webcam/image_raw",
            self.image_callback,
            10
        )

        print("BIN_A / BIN_B 글자 인식 시작")

    def run_ocr(self, roi):

        gray = cv2.cvtColor(
            roi,
            cv2.COLOR_BGR2GRAY
        )

        gray = cv2.GaussianBlur(
            gray,
            (3, 3),
            0
        )

        _, binary = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        temp_path = (
            "/tmp/bin_ocr_input.png"
        )

        cv2.imwrite(
            temp_path,
            binary
        )

        command = [
            "tesseract",
            temp_path,
            "stdout",
            "--psm",
            "6",
            "-l",
            "eng",
            "-c",
            "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ_"
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True
        )

        text = (
            result.stdout
            .upper()
            .replace(" ", "")
            .replace("\n", "")
            .strip()
        )

        text = re.sub(
            r"[^A-Z_]",
            "",
            text
        )

        self.ocr_text = text

        if "BIN_A" in text:
            self.detected_bin = "BIN_A"

        elif "BIN_B" in text:
            self.detected_bin = "BIN_B"

        else:
            self.detected_bin = "NONE"

        print(
            f"OCR={self.ocr_text} "
            f"-> {self.detected_bin}"
        )

    def image_callback(self, msg):

        frame = self.bridge.imgmsg_to_cv2(
            msg,
            desired_encoding="bgr8"
        )

        height, width = frame.shape[:2]

        # 중앙 영역
        x1 = width // 5
        y1 = height // 3
        x2 = width * 4 // 5
        y2 = height * 2 // 3

        roi = frame[
            y1:y2,
            x1:x2
        ]

        now = time.time()

        if (
            now - self.last_ocr_time
            >= self.ocr_interval
        ):
            self.run_ocr(
                roi
            )

            self.last_ocr_time = now

        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            f"OCR: {self.ocr_text}",
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            f"BIN: {self.detected_bin}",
            (20, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (255, 255, 255),
            2
        )

        cv2.imshow(
            "VLA Vision - BIN OCR",
            frame
        )

        cv2.waitKey(1)


def main():

    rclpy.init()

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
