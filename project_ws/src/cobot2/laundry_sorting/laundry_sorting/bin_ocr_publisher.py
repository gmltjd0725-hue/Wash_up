import json
import time

import cv2
import pytesseract
import rclpy

from cv_bridge import CvBridge
from pytesseract import TesseractError, Output
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String


OCR_SCALE = 3.0

# OCR도 2회 연속 확인
REQUIRED_OCR_CONFIRMATIONS = 2

# 색상도 2회 연속 확인
REQUIRED_COLOR_CONFIRMATIONS = 2


class BinOCRPublisher(Node):

    def __init__(self):

        super().__init__(
            "bin_ocr_publisher"
        )

        self.bridge = CvBridge()

        self.last_ocr_time = 0.0
        self.ocr_interval = 1.0

        # 최종 등록된 BIN
        self.registered_bins = set()

        # 어떤 방법으로 등록됐는지
        self.bin_sources = {
            "BIN_A": set(),
            "BIN_B": set(),
        }

        # OCR 연속 확인
        self.last_ocr_candidate = None
        self.ocr_confirm_count = 0

        # COLOR 연속 확인
        self.last_color_candidate = None
        self.color_confirm_count = 0

        self.latest_raw_text = ""
        self.latest_color = "UNKNOWN"

        self.finish_timer = None

        # ==================================
        # Camera
        # ==================================

        self.create_subscription(
            Image,
            "/webcam/image_raw",
            self.image_callback,
            10
        )

        # ==================================
        # BIN Color Publisher 결과
        # ==================================

        self.create_subscription(
            String,
            "/laundry/bin_color_detections",
            self.color_callback,
            10
        )

        # ==================================
        # 통합 BIN 결과
        # ==================================

        self.publisher = self.create_publisher(
            String,
            "/laundry/bin_detections",
            10
        )

        self.get_logger().info(
            "BIN OCR + COLOR Publisher 시작"
        )

        self.get_logger().info(
            "RULE: A OR LIGHT_PINK -> BIN_A"
        )

        self.get_logger().info(
            "RULE: B OR BROWN -> BIN_B"
        )

    # ============================================================
    # BIN 등록
    # ============================================================

    def register_source(
        self,
        bin_name,
        source,
        center=None,
        bbox=None
    ):

        if bin_name not in [
            "BIN_A",
            "BIN_B"
        ]:
            return

        first_registration = (
            bin_name
            not in self.registered_bins
        )

        new_source = (
            source
            not in self.bin_sources[
                bin_name
            ]
        )

        self.bin_sources[
            bin_name
        ].add(
            source
        )

        if first_registration:

            self.registered_bins.add(
                bin_name
            )

            self.get_logger().info(
                f"BIN 등록: {bin_name} "
                f"reason={source} "
                f"center={center} "
                f"bbox={bbox}"
            )

        elif new_source:

            reason = self.reason_text(
                bin_name
            )

            self.get_logger().info(
                f"BIN 확인 보강: "
                f"{bin_name} "
                f"reason={reason}"
            )

    # ============================================================
    # REASON
    # ============================================================

    def reason_text(
        self,
        bin_name
    ):

        sources = self.bin_sources.get(
            bin_name,
            set()
        )

        result = []

        if "OCR" in sources:
            result.append(
                "OCR"
            )

        if "COLOR" in sources:
            result.append(
                "COLOR"
            )

        if not result:
            return "-"

        return " + ".join(
            result
        )

    # ============================================================
    # 현재 통합 상태 발행
    # ============================================================

    def publish_status(
        self,
        candidate=None,
        center=None,
        bbox=None
    ):

        result = {

            "raw_text":
                self.latest_raw_text,

            "color":
                self.latest_color,

            "candidate":
                candidate,

            "center":
                center,

            "bbox":
                bbox,

            "bins":
                sorted(
                    self.registered_bins
                ),

            "reasons": {

                "BIN_A":
                    self.reason_text(
                        "BIN_A"
                    ),

                "BIN_B":
                    self.reason_text(
                        "BIN_B"
                    ),
            }
        }

        message = String()

        message.data = json.dumps(
            result,
            ensure_ascii=False
        )

        self.publisher.publish(
            message
        )

        self.check_finish()

    # ============================================================
    # COLOR 결과
    # ============================================================

    def color_callback(
        self,
        msg
    ):

        try:

            data = json.loads(
                msg.data
            )

        except Exception:

            return

        color = data.get(
            "color",
            "UNKNOWN"
        )

        self.latest_color = color

        candidate = None

        # ==================================
        # 사용자가 정한 OR 규칙
        # ==================================

        if color == "LIGHT_PINK":

            candidate = "BIN_A"

        elif color == "BROWN":

            candidate = "BIN_B"

        # ==================================
        # 색상 연속 확인
        # ==================================

        if candidate is None:

            self.last_color_candidate = None
            self.color_confirm_count = 0

        else:

            if (
                candidate
                == self.last_color_candidate
            ):

                self.color_confirm_count += 1

            else:

                self.last_color_candidate = (
                    candidate
                )

                self.color_confirm_count = 1

            if (
                self.color_confirm_count
                >= REQUIRED_COLOR_CONFIRMATIONS
            ):

                self.register_source(
                    candidate,
                    "COLOR"
                )

                self.last_color_candidate = None
                self.color_confirm_count = 0

        self.publish_status()

    # ============================================================
    # OCR
    # ============================================================

    def image_callback(
        self,
        msg
    ):

        now = time.time()

        if (
            now
            - self.last_ocr_time
            < self.ocr_interval
        ):
            return

        self.last_ocr_time = now

        frame = self.bridge.imgmsg_to_cv2(
            msg,
            desired_encoding="bgr8"
        )

        height, width = frame.shape[:2]

        # ==================================
        # 중앙 OCR 영역
        # ==================================

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

        roi = frame[
            y1:y2,
            x1:x2
        ]

        if roi.size == 0:
            return

        # ==================================
        # OCR 확대
        # ==================================

        roi = cv2.resize(
            roi,
            None,
            fx=OCR_SCALE,
            fy=OCR_SCALE,
            interpolation=cv2.INTER_CUBIC
        )

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
            cv2.THRESH_BINARY
            + cv2.THRESH_OTSU
        )

        config = (
            "--psm 7 "
            "-l eng "
            "-c "
            "tessedit_char_whitelist="
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ_"
        )

        try:

            ocr_data = (
                pytesseract
                .image_to_data(
                    binary,
                    config=config,
                    output_type=Output.DICT
                )
            )

            words = []

            for item in ocr_data[
                "text"
            ]:

                item = item.strip()

                if item:
                    words.append(
                        item
                    )

            text = " ".join(
                words
            )

        except TesseractError:
            return

        except Exception:
            return

        cleaned = (
            text
            .upper()
            .replace(
                " ",
                ""
            )
            .replace(
                "\n",
                ""
            )
            .replace(
                "\r",
                ""
            )
        )

        self.latest_raw_text = (
            cleaned
        )

        # ==================================
        # A/B 포함 판정
        # ==================================

        has_a = (
            "A" in cleaned
        )

        has_b = (
            "B" in cleaned
        )

        candidate = None
        candidate_center = None
        candidate_bbox = None

        if (
            has_a
            and
            not has_b
        ):

            candidate = "BIN_A"

        elif (
            has_b
            and
            not has_a
        ):

            candidate = "BIN_B"

        # ==================================
        # OCR 문자 위치
        # ==================================

        target_letter = None

        if candidate == "BIN_A":
            target_letter = "A"

        elif candidate == "BIN_B":
            target_letter = "B"

        if target_letter is not None:

            for i, word in enumerate(
                ocr_data["text"]
            ):

                word = (
                    word
                    .upper()
                    .replace(
                        " ",
                        ""
                    )
                    .strip()
                )

                if (
                    target_letter
                    not in word
                ):
                    continue

                sx = int(
                    ocr_data[
                        "left"
                    ][i]
                )

                sy = int(
                    ocr_data[
                        "top"
                    ][i]
                )

                sw = int(
                    ocr_data[
                        "width"
                    ][i]
                )

                sh = int(
                    ocr_data[
                        "height"
                    ][i]
                )

                bx = x1 + int(
                    sx / OCR_SCALE
                )

                by = y1 + int(
                    sy / OCR_SCALE
                )

                bw = max(
                    1,
                    int(
                        sw
                        / OCR_SCALE
                    )
                )

                bh = max(
                    1,
                    int(
                        sh
                        / OCR_SCALE
                    )
                )

                candidate_center = [
                    bx + bw // 2,
                    by + bh // 2
                ]

                candidate_bbox = [
                    bx,
                    by,
                    bw,
                    bh
                ]

                break

        # ==================================
        # OCR 연속 확인
        # ==================================

        if candidate is None:

            self.last_ocr_candidate = None
            self.ocr_confirm_count = 0

        else:

            if (
                candidate
                == self.last_ocr_candidate
            ):

                self.ocr_confirm_count += 1

            else:

                self.last_ocr_candidate = (
                    candidate
                )

                self.ocr_confirm_count = 1

            if (
                self.ocr_confirm_count
                >= REQUIRED_OCR_CONFIRMATIONS
            ):

                self.register_source(
                    candidate,
                    "OCR",
                    candidate_center,
                    candidate_bbox
                )

                self.last_ocr_candidate = None
                self.ocr_confirm_count = 0

        self.publish_status(
            candidate,
            candidate_center,
            candidate_bbox
        )

    # ============================================================
    # BIN_A + BIN_B 모두 완료?
    # ============================================================

    def check_finish(self):

        if (
            "BIN_A"
            not in self.registered_bins
        ):
            return

        if (
            "BIN_B"
            not in self.registered_bins
        ):
            return

        if self.finish_timer is not None:
            return

        # 마지막 화면이 잠깐 보이도록
        # 0.8초 후 종료
        self.finish_timer = (
            self.create_timer(
                0.8,
                self.finish_stage
            )
        )

    def finish_stage(self):

        self.get_logger().info(
            "BIN_A / BIN_B 등록 완료"
        )

        self.get_logger().info(
            "BIN_A REASON = "
            + self.reason_text(
                "BIN_A"
            )
        )

        self.get_logger().info(
            "BIN_B REASON = "
            + self.reason_text(
                "BIN_B"
            )
        )

        if rclpy.ok():

            rclpy.shutdown()


def main(args=None):

    rclpy.init(
        args=args
    )

    node = BinOCRPublisher()

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
