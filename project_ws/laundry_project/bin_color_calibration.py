import json
from pathlib import Path

import cv2
import numpy as np
import rclpy

from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image


DATA_DIR = (
    Path.home()
    / "project_ws"
    / "laundry_project"
    / "bin_color_data"
    / "calibration"
)

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True
)

JSON_PATH = (
    DATA_DIR
    / "color_references.json"
)


class BinColorCalibration(Node):

    def __init__(self):

        super().__init__(
            "bin_color_calibration"
        )

        self.bridge = CvBridge()

        self.frame = None

        self.refs = {}

        # 이전에 저장한 WHITE / LIGHT_PINK /
        # BACKGROUND 기준값이 있으면 자동으로 불러온다.
        if JSON_PATH.exists():

            try:

                self.refs = json.loads(
                    JSON_PATH.read_text()
                )

                self.get_logger().info(
                    "기존 색상 기준 불러옴: "
                    + ", ".join(self.refs.keys())
                )

            except Exception as e:

                self.get_logger().warning(
                    f"기존 기준 로드 실패: {e}"
                )

                self.refs = {}

        self.create_subscription(
            Image,
            "/webcam/image_raw",
            self.image_callback,
            10
        )

        self.create_timer(
            0.03,
            self.loop
        )

        self.get_logger().info(
            "BIN Color Calibration 시작"
        )

        self.get_logger().info(
            "1=WHITE | 2=LIGHT_PINK | "
            "3=BACKGROUND | 4=BROWN | Q=QUIT"
        )

    def image_callback(
        self,
        msg
    ):

        self.frame = (
            self.bridge.imgmsg_to_cv2(
                msg,
                desired_encoding="bgr8"
            )
        )

    def get_roi(
        self,
        frame
    ):

        h, w = frame.shape[:2]

        roi_w = int(
            w * 0.60
        )

        roi_h = int(
            h * 0.55
        )

        x1 = (
            w - roi_w
        ) // 2

        y1 = (
            h - roi_h
        ) // 2

        x2 = x1 + roi_w
        y2 = y1 + roi_h

        roi = frame[
            y1:y2,
            x1:x2
        ]

        return (
            roi,
            x1,
            y1,
            x2,
            y2
        )

    def extract_features(
        self,
        roi
    ):

        hsv = cv2.cvtColor(
            roi,
            cv2.COLOR_BGR2HSV
        )

        lab = cv2.cvtColor(
            roi,
            cv2.COLOR_BGR2LAB
        )

        bgr_median = np.median(
            roi.reshape(-1, 3),
            axis=0
        )

        hsv_median = np.median(
            hsv.reshape(-1, 3),
            axis=0
        )

        lab_median = np.median(
            lab.reshape(-1, 3),
            axis=0
        )

        return {

            "bgr": [
                round(float(x), 1)
                for x in bgr_median
            ],

            "hsv": [
                round(float(x), 1)
                for x in hsv_median
            ],

            "lab": [
                round(float(x), 1)
                for x in lab_median
            ]
        }

    def feature_vector(
        self,
        feature
    ):

        _, s, v = feature["hsv"]

        l, a, b = feature["lab"]

        blue, green, red = (
            feature["bgr"]
        )

        # H는 저채도 색에서 매우 불안정하므로
        # 이번 비교에서는 사용하지 않음
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

        # 각 성분의 숫자 범위 차이를
        # 어느 정도 맞춰주기 위한 scale
        scale = np.array(
            [
                30.0,   # S
                40.0,   # V
                40.0,   # L
                20.0,   # LAB a
                20.0,   # LAB b
                50.0,   # B
                50.0,   # G
                50.0    # R
            ],
            dtype=np.float32
        )

        return float(
            np.linalg.norm(
                (v1 - v2)
                / scale
            )
        )

    def classify(
        self,
        feature
    ):

        needed = {
            "WHITE",
            "LIGHT_PINK",
            "BACKGROUND",
            "BROWN"
        }

        if (
            set(self.refs.keys())
            != needed
        ):

            return None, {}

        scores = {}

        for name, ref in (
            self.refs.items()
        ):

            scores[name] = self.distance(
                feature,
                ref
            )

        best = min(
            scores,
            key=scores.get
        )

        return (
            best,
            scores
        )

    def save_reference(
        self,
        name,
        roi
    ):

        feature = self.extract_features(
            roi
        )

        self.refs[name] = feature

        image_path = (
            DATA_DIR
            / f"{name.lower()}.jpg"
        )

        cv2.imwrite(
            str(image_path),
            roi
        )

        JSON_PATH.write_text(
            json.dumps(
                self.refs,
                indent=2,
                ensure_ascii=False
            )
        )

        self.get_logger().info(
            f"[CAPTURE {name}] "
            f"BGR={feature['bgr']} "
            f"HSV={feature['hsv']} "
            f"LAB={feature['lab']}"
        )

        if len(self.refs) == 4:

            self.print_reference_distance()

    def print_reference_distance(
        self
    ):

        names = [
            "WHITE",
            "LIGHT_PINK",
            "BACKGROUND",
            "BROWN"
        ]

        self.get_logger().info(
            "===== REFERENCE DISTANCE ====="
        )

        for i in range(
            len(names)
        ):

            for j in range(
                i + 1,
                len(names)
            ):

                a = names[i]
                b = names[j]

                d = self.distance(
                    self.refs[a],
                    self.refs[b]
                )

                self.get_logger().info(
                    f"{a} <-> {b} "
                    f"distance={d:.3f}"
                )

    def put_text(
        self,
        frame,
        text,
        y,
        color=(255, 255, 255),
        scale=0.65
    ):

        cv2.putText(
            frame,
            text,
            (15, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            color,
            2,
            cv2.LINE_AA
        )

    def loop(
        self
    ):

        if self.frame is None:
            return

        display = (
            self.frame.copy()
        )

        (
            roi,
            x1,
            y1,
            x2,
            y2
        ) = self.get_roi(
            display
        )

        feature = self.extract_features(
            roi
        )

        result, scores = self.classify(
            feature
        )

        cv2.rectangle(
            display,
            (x1, y1),
            (x2, y2),
            (0, 255, 255),
            3
        )

        self.put_text(
            display,
            "1=WHITE  2=PINK  3=BACKGROUND  4=BROWN  Q=QUIT",
            30
        )

        self.put_text(
            display,
            f"BGR: {feature['bgr']}",
            60
        )

        self.put_text(
            display,
            f"HSV: {feature['hsv']}",
            90
        )

        self.put_text(
            display,
            f"LAB: {feature['lab']}",
            120
        )

        if result is None:

            self.put_text(
                display,
                f"CAPTURED: {len(self.refs)}/3",
                155,
                (0, 255, 255),
                0.8
            )

        else:

            self.put_text(
                display,
                f"CLASS: {result}",
                155,
                (0, 255, 0),
                0.9
            )

            score_text = (
                "D "
                + " ".join(
                    [
                        f"{k}:{v:.2f}"
                        for k, v
                        in scores.items()
                    ]
                )
            )

            self.put_text(
                display,
                score_text,
                185,
                (255, 255, 255),
                0.50
            )

        cv2.imshow(
            "BIN COLOR CALIBRATION",
            display
        )

        key = (
            cv2.waitKey(1)
            & 0xFF
        )

        if key == ord("1"):

            self.save_reference(
                "WHITE",
                roi
            )

        elif key == ord("2"):

            self.save_reference(
                "LIGHT_PINK",
                roi
            )

        elif key == ord("3"):

            self.save_reference(
                "BACKGROUND",
                roi
            )

        elif key == ord("4"):

            self.save_reference(
                "BROWN",
                roi
            )

        elif key == ord("q"):

            if rclpy.ok():
                rclpy.shutdown()


def main():

    rclpy.init()

    node = BinColorCalibration()

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
