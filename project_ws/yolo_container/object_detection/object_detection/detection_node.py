import json
import os

import numpy as np

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge

from ultralytics import YOLO


class DetectionNode(Node):

    def __init__(self):

        super().__init__("detection_node")

        self.bridge = CvBridge()

        model_path = os.getenv(
            "YOLO_MODEL_PATH",
            "/models/best.pt"
        )

        self.get_logger().info(
            f"YOLO Model: {model_path}"
        )

        self.model = YOLO(model_path)

        self.image_subscriber = self.create_subscription(
            Image,
            "/webcam/image_raw",
            self.image_callback,
            10
        )

        self.detection_publisher = self.create_publisher(
            String,
            "/laundry/detections",
            10
        )

        self.get_logger().info(
            "YOLO Detection Node 시작"
        )

    def image_callback(self, msg):

        frame = self.bridge.imgmsg_to_cv2(
            msg,
            desired_encoding="bgr8"
        )

        # YOLO 추론
        results = self.model(frame, verbose=False)

        if len(results) == 0:
            return

        result = results[0]

        detections = []

        if result.boxes is not None:

            for box in result.boxes:

                # 강의자료 방식
                x1, y1, x2, y2 = (
                    box.xyxy[0]
                    .cpu()
                    .numpy()
                )

                confidence = float(
                    box.conf[0]
                    .cpu()
                    .item()
                )

                class_id = int(
                    box.cls[0]
                    .cpu()
                    .item()
                )

                class_name = self.model.names[class_id]

                detection = {
                    "class_id": class_id,
                    "class_name": class_name,
                    "confidence": confidence,

                    "bbox": {
                        "x1": int(x1),
                        "y1": int(y1),
                        "x2": int(x2),
                        "y2": int(y2)
                    }
                }

                detections.append(detection)

        message = String()

        message.data = json.dumps(
            detections,
            ensure_ascii=False
        )

        self.detection_publisher.publish(message)


def main(args=None):

    rclpy.init(args=args)

    node = DetectionNode()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()