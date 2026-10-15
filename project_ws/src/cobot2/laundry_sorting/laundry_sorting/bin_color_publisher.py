import json
import time
from pathlib import Path

import cv2
import numpy as np
import pytesseract
import rclpy

from rclpy.executors import ExternalShutdownException

from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String


REFERENCE_PATH = (
    Path.home()
    / "project_ws"
    / "laundry_project"
    / "bin_color_data"
    / "calibration"
    / "color_references.json"
)

PROCESS_INTERVAL = 0.8


class BinColorPublisher(Node):

    def __init__(self):

        super().__init__(
            "bin_color_publisher"
        )

        self.bridge = CvBridge()

        self.last_process_time = 0.0
        self.last_signature = None

        self.references = (
            self.load_references()
        )

        self.create_subscription(
            Image,
            "/webcam/image_raw",
            self.image_callback,
            10
        )

        self.publisher = self.create_publisher(
            String,
            "/laundry/bin_color_detections",
            10
        )

        self.get_logger().info(
            "BIN A/B + 실제 색상 검증 시작"
        )

        self.get_logger().info(
            "A=BIN_A/LIGHT_PINK | "
            "B=BIN_B/BROWN"
        )

    # ==========================================================
    # 실제 촬영한 PINK / BROWN 기준값만 사용
    # ==========================================================

    def load_references(self):

        if not REFERENCE_PATH.exists():

            raise RuntimeError(
                f"색상 기준 파일 없음: "
                f"{REFERENCE_PATH}"
            )

        data = json.loads(
            REFERENCE_PATH.read_text()
        )

        for name in [
            "LIGHT_PINK",
            "BROWN"
        ]:

            if name not in data:

                raise RuntimeError(
                    f"{name} 기준값 없음"
                )

        return {
            "LIGHT_PINK":
                data["LIGHT_PINK"],

            "BROWN":
                data["BROWN"]
        }

    # ==========================================================
    # 흰색 A/B 종이 찾기
    #
    # 실제 WHITE:
    # S≈2, V≈255
    #
    # 실제 LIGHT_PINK:
    # S≈49, V≈243
    #
    # 따라서 낮은 S의 진짜 흰 종이만 찾는다.
    # ==========================================================

    def find_label(self, roi):

        hsv = cv2.cvtColor(
            roi,
            cv2.COLOR_BGR2HSV
        )

        mask = cv2.inRange(
            hsv,
            np.array(
                [0, 0, 235]
            ),
            np.array(
                [179, 30, 255]
            )
        )

        kernel = np.ones(
            (5, 5),
            np.uint8
        )

        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            kernel,
            iterations=2
        )

        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        h, w = roi.shape[:2]

        roi_area = (
            h * w
        )

        candidates = []

        for contour in contours:

            area = cv2.contourArea(
                contour
            )

            if area < (
                roi_area * 0.01
            ):
                continue

            if area > (
                roi_area * 0.40
            ):
                continue

            x, y, bw, bh = (
                cv2.boundingRect(
                    contour
                )
            )

            if (
                bw < 35
                or
                bh < 35
            ):
                continue

            ratio = (
                bw / float(bh)
            )

            if not (
                0.45
                <= ratio
                <= 2.2
            ):
                continue

            candidates.append(
                (
                    area,
                    x,
                    y,
                    bw,
                    bh
                )
            )

        if not candidates:
            return None

        candidates.sort(
            reverse=True
        )

        _, x, y, w, h = (
            candidates[0]
        )

        return (
            x,
            y,
            w,
            h
        )

    # ==========================================================
    # A / B OCR
    # ==========================================================

    def detect_letter(
        self,
        image
    ):

        if (
            image is None
            or
            image.size == 0
        ):
            return None

        image = cv2.resize(
            image,
            None,
            fx=4.0,
            fy=4.0,
            interpolation=cv2.INTER_CUBIC
        )

        gray = cv2.cvtColor(
            image,
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

        votes = []

        for source in [
            gray,
            binary
        ]:

            for psm in [
                10,
                7
            ]:

                try:

                    text = (
                        pytesseract
                        .image_to_string(
                            source,
                            config=(
                                f"--psm {psm} "
                                "-l eng "
                                "-c "
                                "tessedit_char_whitelist=AB"
                            )
                        )
                    )

                except Exception:

                    continue

                text = (
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

                if (
                    "A" in text
                    and
                    "B" not in text
                ):

                    votes.append(
                        "A"
                    )

                elif (
                    "B" in text
                    and
                    "A" not in text
                ):

                    votes.append(
                        "B"
                    )

        a_count = (
            votes.count("A")
        )

        b_count = (
            votes.count("B")
        )

        if (
            a_count >= 1
            and
            a_count > b_count
        ):

            return "A"

        if (
            b_count >= 1
            and
            b_count > a_count
        ):

            return "B"

        return None

    # ==========================================================
    # 통 본체 색상 측정
    # ==========================================================

    def extract_color(
        self,
        roi,
        label_bbox
    ):

        hsv = cv2.cvtColor(
            roi,
            cv2.COLOR_BGR2HSV
        )

        lab = cv2.cvtColor(
            roi,
            cv2.COLOR_BGR2LAB
        )

        valid_mask = np.ones(
            roi.shape[:2],
            dtype=np.uint8
        )

        # A/B 흰 종이는
        # 통 색상 계산에서 제외
        if label_bbox is not None:

            x, y, w, h = (
                label_bbox
            )

            pad = 10

            x1 = max(
                0,
                x - pad
            )

            y1 = max(
                0,
                y - pad
            )

            x2 = min(
                roi.shape[1],
                x + w + pad
            )

            y2 = min(
                roi.shape[0],
                y + h + pad
            )

            valid_mask[
                y1:y2,
                x1:x2
            ] = 0

        valid = (
            valid_mask == 1
        )

        if (
            np.count_nonzero(valid)
            < 1000
        ):

            return None

        bgr_med = np.median(
            roi[valid],
            axis=0
        )

        hsv_med = np.median(
            hsv[valid],
            axis=0
        )

        lab_med = np.median(
            lab[valid],
            axis=0
        )

        return {

            "bgr": [
                float(x)
                for x in bgr_med
            ],

            "hsv": [
                float(x)
                for x in hsv_med
            ],

            "lab": [
                float(x)
                for x in lab_med
            ]
        }

    # ==========================================================
    # 캘리브레이션과 같은 거리 계산
    # ==========================================================

    def feature_vector(
        self,
        feature
    ):

        _, s, v = (
            feature["hsv"]
        )

        l, a, b = (
            feature["lab"]
        )

        blue, green, red = (
            feature["bgr"]
        )

        return np.array(
            [
                s,
                v,
                l,
                a,
                b,
                blue,
                green,
                red
            ],
            dtype=np.float32
        )

    def distance(
        self,
        f1,
        f2
    ):

        v1 = self.feature_vector(
            f1
        )

        v2 = self.feature_vector(
            f2
        )

        scale = np.array(
            [
                30.0,
                40.0,
                40.0,
                20.0,
                20.0,
                50.0,
                50.0,
                50.0
            ],
            dtype=np.float32
        )

        return float(
            np.linalg.norm(
                (v1 - v2)
                / scale
            )
        )

    # ==========================================================
    # PINK / BROWN 둘 중 어느 쪽에 가까운지
    # ==========================================================

    def classify_color(
        self,
        feature
    ):

        if feature is None:

            return (
                "UNKNOWN",
                {}
            )

        pink_distance = self.distance(
            feature,
            self.references[
                "LIGHT_PINK"
            ]
        )

        brown_distance = self.distance(
            feature,
            self.references[
                "BROWN"
            ]
        )

        scores = {

            "LIGHT_PINK":
                pink_distance,

            "BROWN":
                brown_distance
        }

        # 두 색상 거리가 너무 비슷하면
        # 억지로 확정하지 않음
        if (
            abs(
                pink_distance
                - brown_distance
            )
            < 0.40
        ):

            return (
                "UNKNOWN",
                scores
            )

        if (
            pink_distance
            < brown_distance
        ):

            return (
                "LIGHT_PINK",
                scores
            )

        return (
            "BROWN",
            scores
        )

    # ==========================================================
    # OCR이 최우선 관문
    # ==========================================================

    def verify(
        self,
        letter,
        color
    ):

        # ==========================================
        # OCR 우선
        #
        # A 한 글자만 검출되어도 BIN_A
        # B 한 글자만 검출되어도 BIN_B
        # ==========================================

        if letter == "A":

            return (
                "BIN_A",
                "LIGHT",
                "CONFIRMED"
            )

        if letter == "B":

            return (
                "BIN_B",
                "DARK",
                "CONFIRMED"
            )

        # ==========================================
        # OCR이 없어도 색상만으로 등록
        #
        # LIGHT_PINK -> BIN_A
        # BROWN      -> BIN_B
        # ==========================================

        if color == "LIGHT_PINK":

            return (
                "BIN_A",
                "LIGHT",
                "CONFIRMED"
            )

        if color == "BROWN":

            return (
                "BIN_B",
                "DARK",
                "CONFIRMED"
            )

        return (
            None,
            None,
            "UNKNOWN"
        )


    # ==========================================================
    # IMAGE
    # ==========================================================

    def image_callback(
        self,
        msg
    ):

        now = time.time()

        if (
            now
            - self.last_process_time
            < PROCESS_INTERVAL
        ):
            return

        self.last_process_time = (
            now
        )

        frame = (
            self.bridge
            .imgmsg_to_cv2(
                msg,
                desired_encoding="bgr8"
            )
        )

        frame_h, frame_w = (
            frame.shape[:2]
        )

        roi_w = int(
            frame_w * 0.70
        )

        roi_h = int(
            frame_h * 0.60
        )

        roi_x = (
            frame_w - roi_w
        ) // 2

        roi_y = (
            frame_h - roi_h
        ) // 2

        roi = frame[
            roi_y:roi_y + roi_h,
            roi_x:roi_x + roi_w
        ]

        if roi.size == 0:
            return

        label_local = (
            self.find_label(
                roi
            )
        )

        label_global = None
        label_roi = None

        if (
            label_local
            is not None
        ):

            lx, ly, lw, lh = (
                label_local
            )

            label_roi = roi[
                ly:ly + lh,
                lx:lx + lw
            ]

            label_global = [
                roi_x + lx,
                roi_y + ly,
                lw,
                lh
            ]

        else:

            # 흰 종이 사각형을 못 잡아도
            # 중앙 영역에서 OCR 보조 시도
            fw = int(
                roi_w * 0.55
            )

            fh = int(
                roi_h * 0.55
            )

            fx = (
                roi_w - fw
            ) // 2

            fy = (
                roi_h - fh
            ) // 2

            label_roi = roi[
                fy:fy + fh,
                fx:fx + fw
            ]

        letter = (
            self.detect_letter(
                label_roi
            )
        )

        feature = (
            self.extract_color(
                roi,
                label_local
            )
        )

        color, scores = (
            self.classify_color(
                feature
            )
        )

        (
            bin_name,
            laundry_type,
            status
        ) = self.verify(
            letter,
            color
        )

        hsv_result = None
        lab_result = None
        bgr_result = None

        if feature is not None:

            hsv_result = [
                round(x, 1)
                for x
                in feature["hsv"]
            ]

            lab_result = [
                round(x, 1)
                for x
                in feature["lab"]
            ]

            bgr_result = [
                round(x, 1)
                for x
                in feature["bgr"]
            ]

        result = {

            "ocr_letter":
                letter,

            "color":
                color,

            "bin":
                bin_name,

            "laundry_type":
                laundry_type,

            "status":
                status,

            "label_bbox":
                label_global,

            "roi_bbox": [
                roi_x,
                roi_y,
                roi_w,
                roi_h
            ],

            "bgr":
                bgr_result,

            "hsv":
                hsv_result,

            "lab":
                lab_result,

            "color_scores": {
                k: round(
                    v,
                    3
                )
                for k, v
                in scores.items()
            },

            "source":
                "OCR_PINK_BROWN_VERIFY"
        }

        message = String()

        message.data = json.dumps(
            result,
            ensure_ascii=False
        )

        try:
            self.publisher.publish(
                message
            )

        except Exception:
            # 종료 도중 context가 먼저 닫힌 경우만 정상 무시
            if not rclpy.ok():
                return
            raise

        signature = (
            letter,
            color,
            bin_name,
            status
        )

        # 판정이 바뀔 때만 로그
        if (
            signature
            != self.last_signature
        ):

            self.get_logger().info(
                f"OCR={letter or '-'} | "
                f"COLOR={color} | "
                f"RESULT={bin_name or '-'} | "
                f"STATUS={status}"
            )

            if scores:

                self.get_logger().info(
                    "DISTANCE "
                    f"PINK={scores['LIGHT_PINK']:.2f} | "
                    f"BROWN={scores['BROWN']:.2f}"
                )

            if feature is not None:

                self.get_logger().info(
                    f"BGR={bgr_result} | "
                    f"HSV={hsv_result} | "
                    f"LAB={lab_result}"
                )

            self.last_signature = (
                signature
            )


def main(args=None):

    rclpy.init(
        args=args
    )

    node = (
        BinColorPublisher()
    )

    try:

        rclpy.spin(
            node
        )

    except (KeyboardInterrupt, ExternalShutdownException):

        pass

    finally:

        node.destroy_node()

        if rclpy.ok():

            rclpy.shutdown()


if __name__ == "__main__":
    main()
