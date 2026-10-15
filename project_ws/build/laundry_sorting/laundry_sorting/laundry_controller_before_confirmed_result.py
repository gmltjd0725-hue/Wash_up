import json
import os
import subprocess
import time

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge

from laundry_sorting.hsv_classifier import HSVClassifier
from laundry_sorting.database import LaundryDatabase


class LaundryController(Node):

    def __init__(self):

        super().__init__("laundry_controller")

        # =========================
        # ROS2 Parameter
        # =========================

        self.declare_parameter(
            "saturation_threshold",
            0.0
        )

        self.declare_parameter(
            "value_threshold",
            0.0
        )

        saturation_threshold = (
            self.get_parameter(
                "saturation_threshold"
            )
            .get_parameter_value()
            .double_value
        )

        value_threshold = (
            self.get_parameter(
                "value_threshold"
            )
            .get_parameter_value()
            .double_value
        )

        # =========================
        # HSV Classifier
        # =========================

        self.classifier = HSVClassifier(
            saturation_threshold,
            value_threshold
        )

        # =========================
        # Database
        # =========================

        self.database = LaundryDatabase()

        # =========================
        # Image
        # =========================

        self.bridge = CvBridge()
        self.latest_frame = None

        # =========================
        # BIN OCR
        # =========================

        self.detected_bins = set()

        # =========================
        # Task
        # =========================

        self.current_command = None
        self.state = "IDLE"

        # =========================
        # Subscribers
        # =========================

        self.image_subscriber = self.create_subscription(
            Image,
            "/webcam/image_raw",
            self.image_callback,
            10
        )

        self.voice_subscriber = self.create_subscription(
            String,
            "/voice/command",
            self.voice_callback,
            10
        )

        self.detection_subscriber = self.create_subscription(
            String,
            "/laundry/detections",
            self.detection_callback,
            10
        )

        self.bin_subscriber = self.create_subscription(
            String,
            "/laundry/bin_detections",
            self.bin_detection_callback,
            10
        )

        self.get_logger().info(
            "Laundry Controller 시작"
        )

        self.change_state("IDLE")

    # =========================
    # STATE
    # =========================

    def change_state(self, state):

        self.state = state

        self.get_logger().info(
            f"STATE -> {state}"
        )

    # =========================
    # IMAGE
    # =========================

    def image_callback(self, msg):

        self.latest_frame = (
            self.bridge.imgmsg_to_cv2(
                msg,
                desired_encoding="bgr8"
            )
        )

    # =========================
    # BIN OCR
    # =========================

    def bin_detection_callback(self, msg):

        try:

            data = json.loads(
                msg.data
            )

        except json.JSONDecodeError:

            self.get_logger().error(
                "BIN Detection JSON 오류"
            )

            return

        bins = data.get(
            "bins",
            []
        )

        # OCR에서 실제 BIN을 찾았을 때만 기억
        for bin_name in bins:

            if bin_name in [
                "BIN_A",
                "BIN_B"
            ]:

                self.detected_bins.add(
                    bin_name
                )

    # =========================
    # VOICE
    # =========================

    def voice_callback(self, msg):

        try:

            command_data = json.loads(
                msg.data
            )

        except json.JSONDecodeError:

            self.get_logger().error(
                "Voice JSON 형식 오류"
            )

            return

        intent = command_data.get(
            "intent"
        )

        target = command_data.get(
            "target"
        )

        command = command_data.get(
            "command"
        )

        if intent != "SORT_LAUNDRY":

            self.get_logger().info(
                f"다른 Intent 무시: {intent}"
            )

            return

        self.change_state(
            "PARSING"
        )

        self.current_command = {
            "command": command,
            "intent": intent,
            "target": target
        }

        self.get_logger().info(
            f"Command: {command}"
        )

        self.get_logger().info(
            f"Target: {target}"
        )

        self.change_state(
            "SEARCHING"
        )

    # =========================
    # DETECTION
    # =========================

    def detection_callback(self, msg):

        if self.current_command is None:
            return

        if self.state != "SEARCHING":
            return

        if self.latest_frame is None:

            self.get_logger().warning(
                "Webcam frame 없음"
            )

            return

        try:

            detections = json.loads(
                msg.data
            )

        except json.JSONDecodeError:

            self.get_logger().error(
                "Detection JSON 오류"
            )

            return

        target = (
            self.current_command[
                "target"
            ]
        )

        target_detection = None

        # =========================
        # Target 검색
        # =========================

        if target is None:

            for detection in detections:

                if target_detection is None:

                    target_detection = (
                        detection
                    )

                elif (
                    detection["confidence"]
                    >
                    target_detection[
                        "confidence"
                    ]
                ):

                    target_detection = (
                        detection
                    )

        else:

            for detection in detections:

                if (
                    detection["class_name"]
                    == target
                ):

                    if target_detection is None:

                        target_detection = (
                            detection
                        )

                    elif (
                        detection["confidence"]
                        >
                        target_detection[
                            "confidence"
                        ]
                    ):

                        target_detection = (
                            detection
                        )

        if target_detection is None:
            return

        self.change_state(
            "TARGET_FOUND"
        )

        self.process_target(
            target_detection
        )

    # =========================
    # ROI + HSV
    # =========================

    def process_target(
        self,
        detection
    ):

        bbox = detection[
            "bbox"
        ]

        x1 = bbox["x1"]
        y1 = bbox["y1"]
        x2 = bbox["x2"]
        y2 = bbox["y2"]

        frame_height, frame_width = (
            self.latest_frame.shape[:2]
        )

        x1 = max(
            0,
            min(x1, frame_width)
        )

        x2 = max(
            0,
            min(x2, frame_width)
        )

        y1 = max(
            0,
            min(y1, frame_height)
        )

        y2 = max(
            0,
            min(y2, frame_height)
        )

        if x2 <= x1 or y2 <= y1:

            self.get_logger().error(
                "잘못된 Bounding Box"
            )

            return

        roi = self.latest_frame[
            y1:y2,
            x1:x2
        ]

        self.change_state(
            "CLASSIFYING"
        )

        try:

            result = (
                self.classifier.classify(
                    roi
                )
            )

        except Exception as e:

            self.get_logger().error(
                f"HSV 분석 실패: {e}"
            )

            return

        saturation = result[
            "saturation"
        ]

        value = result[
            "value"
        ]

        classification = result[
            "classification"
        ]

        self.get_logger().info(
            f"S = {saturation:.2f}"
        )

        self.get_logger().info(
            f"V = {value:.2f}"
        )

        self.get_logger().info(
            f"Classification = "
            f"{classification}"
        )

        # =========================
        # OCR BIN 선택
        # =========================

        self.change_state(
            "BIN_MATCHING"
        )

        if classification == "LIGHT":

            expected_bin = "BIN_A"

        elif classification == "DARK":

            expected_bin = "BIN_B"

        else:

            self.get_logger().error(
                "알 수 없는 분류 결과"
            )

            self.current_command = None

            self.change_state(
                "IDLE"
            )

            return

        self.get_logger().info(
            f"Required BIN = "
            f"{expected_bin}"
        )

        self.get_logger().info(
            f"OCR Detected BINs = "
            f"{sorted(self.detected_bins)}"
        )

        # 실제 OCR에서 해당 BIN을
        # 한 번이라도 확인했는지 검사
        if expected_bin not in self.detected_bins:

            self.get_logger().warning(
                f"{expected_bin} 글자를 "
                f"아직 인식하지 못했습니다."
            )

            self.current_command = None

            self.change_state(
                "IDLE"
            )

            return

        destination = expected_bin

        self.get_logger().info(
            f"BIN OCR Match = "
            f"{destination}"
        )

        self.get_logger().info(
            f"Destination = "
            f"{destination}"
        )

        # =========================
        # ROBOT SORT
        #
        # LIGHT -> PICK -> BIN_A
        # DARK  -> PICK -> BIN_B
        # =========================
        self.change_state(
            "ROBOT_SORTING"
        )

        try:

            self.run_robot_sort(
                classification
            )

        except subprocess.CalledProcessError as e:

            self.get_logger().error(
                f"ROBOT SORT 실패: {e}"
            )

            self.current_command = None

            self.change_state(
                "IDLE"
            )

            return

        except Exception as e:

            self.get_logger().error(
                f"ROBOT SORT 오류: {e}"
            )

            self.current_command = None

            self.change_state(
                "IDLE"
            )

            return

        self.change_state(
            "ROBOT_COMPLETE"
        )

        # =========================
        # DB
        # =========================

        self.change_state(
            "DB_SAVING"
        )

        success = (
            self.database.save_task(

                command=(
                    self.current_command[
                        "command"
                    ]
                ),

                target=(
                    self.current_command[
                        "target"
                    ]
                ),

                confidence=(
                    detection[
                        "confidence"
                    ]
                ),

                saturation=(
                    saturation
                ),

                value=(
                    value
                ),

                classification=(
                    classification
                ),

                destination=(
                    destination
                ),

                status="COMPLETE"
            )
        )

        if success:

            self.change_state(
                "COMPLETE"
            )

        else:

            self.get_logger().error(
                "DB 저장 실패"
            )

        self.current_command = None

        self.change_state(
            "IDLE"
        )

    # =========================
    # ROBOT SORT
    # =========================

    def run_robot_sort(self, classification):

        self.get_logger().info(
            "ROBOT PICK START"
        )

        subprocess.run(
            [
                "ros2",
                "run",
                "laundry_sorting",
                "laundry_pick_force_test"
            ],
            check=True
        )

        self.get_logger().info(
            "ROBOT PICK COMPLETE"
        )

        if classification == "LIGHT":

            bin_type = "LIGHT"

        elif classification == "DARK":

            bin_type = "DARK"

        else:

            raise RuntimeError(
                f"Unknown classification: {classification}"
            )

        self.get_logger().info(
            f"ROBOT BIN MOVE START: {bin_type}"
        )

        subprocess.run(
            [
                "ros2",
                "run",
                "laundry_sorting",
                "bin_move_test",
                bin_type
            ],
            check=True
        )

        self.get_logger().info(
            f"ROBOT BIN MOVE COMPLETE: {bin_type}"
        )


    def destroy_node(self):

        self.database.close()

        super().destroy_node()


def main(args=None):

    rclpy.init(
        args=args
    )

    node = LaundryController()

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
