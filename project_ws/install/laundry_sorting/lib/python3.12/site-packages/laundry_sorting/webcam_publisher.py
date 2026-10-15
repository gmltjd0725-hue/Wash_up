import glob
import subprocess

import cv2
import rclpy

from rclpy.executors import ExternalShutdownException

from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge


REALSENSE_VENDOR = "8086"
REALSENSE_MODEL = "0b3a"

LAPTOP_VENDOR = "2232"
LAPTOP_MODEL = "1080"


def get_usb_ids(device):

    result = subprocess.run(
        [
            "udevadm",
            "info",
            "--query=property",
            f"--name={device}",
        ],
        capture_output=True,
        text=True,
    )

    vendor = None
    model = None

    for line in result.stdout.splitlines():

        if line.startswith("ID_VENDOR_ID="):
            vendor = line.split("=", 1)[1].lower()

        elif line.startswith("ID_MODEL_ID="):
            model = line.split("=", 1)[1].lower()

    return vendor, model


def get_formats(device):

    result = subprocess.run(
        [
            "v4l2-ctl",
            "-d",
            device,
            "--list-formats-ext",
        ],
        capture_output=True,
        text=True,
    )

    return result.stdout


def is_color_camera(device):

    formats = get_formats(device)

    return (
        "YUYV" in formats
        or "MJPG" in formats
    )


def find_camera():

    devices = sorted(
        glob.glob("/dev/video*")
    )

    # =========================
    # 1순위: RealSense RGB
    # =========================

    for device in devices:

        vendor, model = get_usb_ids(
            device
        )

        if (
            vendor == REALSENSE_VENDOR
            and model == REALSENSE_MODEL
            and is_color_camera(device)
        ):

            return (
                device,
                "REALSENSE"
            )

    # =========================
    # 2순위: 노트북 내장 카메라
    # =========================

    for device in devices:

        vendor, model = get_usb_ids(
            device
        )

        if (
            vendor == LAPTOP_VENDOR
            and model == LAPTOP_MODEL
            and is_color_camera(device)
        ):

            return (
                device,
                "LAPTOP"
            )

    return None, None


class WebcamPublisher(Node):

    def __init__(self):

        super().__init__(
            "webcam_publisher"
        )

        self.camera_device, self.camera_type = (
            find_camera()
        )

        if self.camera_device is None:

            raise RuntimeError(
                "사용 가능한 RGB 카메라를 찾을 수 없습니다."
            )

        self.get_logger().info(
            f"선택된 카메라: "
            f"{self.camera_type} "
            f"({self.camera_device})"
        )

        self.apply_camera_settings()

        self.camera = cv2.VideoCapture(
            self.camera_device,
            cv2.CAP_V4L2
        )

        if not self.camera.isOpened():

            raise RuntimeError(
                f"카메라를 열 수 없습니다: "
                f"{self.camera_device}"
            )

        self.bridge = CvBridge()

        self.publisher = self.create_publisher(
            Image,
            "/webcam/image_raw",
            10
        )

        self.timer = self.create_timer(
            1.0 / 30.0,
            self.timer_callback
        )

        self.get_logger().info(
            "Webcam Publisher 시작"
        )

    def set_control(
        self,
        setting
    ):

        result = subprocess.run(
            [
                "v4l2-ctl",
                "-d",
                self.camera_device,
                f"--set-ctrl={setting}",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:

            self.get_logger().info(
                f"카메라 설정 적용: {setting}"
            )

        else:

            self.get_logger().warning(
                f"카메라 설정 실패: {setting}"
            )

    def apply_camera_settings(self):

        # =========================
        # RealSense
        # =========================

        if self.camera_type == "REALSENSE":

            settings = [
                "auto_exposure=1",
                "brightness=10",
                "exposure_time_absolute=90",
                "white_balance_automatic=0",
                "white_balance_temperature=4600",
            ]

        # =========================
        # 노트북 내장 카메라
        # =========================

        else:

            settings = [
                "auto_exposure=3",
                "brightness=100",
                "white_balance_automatic=0",
                "white_balance_temperature=4600",
            ]

        for setting in settings:

            self.set_control(
                setting
            )

    def timer_callback(self):

        success, frame = (
            self.camera.read()
        )

        if not success:

            self.get_logger().warning(
                "카메라 프레임 읽기 실패"
            )

            return

        msg = self.bridge.cv2_to_imgmsg(
            frame,
            encoding="bgr8"
        )

        self.publisher.publish(
            msg
        )

    def destroy_node(self):

        if hasattr(
            self,
            "camera"
        ):

            self.camera.release()

        super().destroy_node()


def main(args=None):

    rclpy.init(
        args=args
    )

    node = WebcamPublisher()

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
