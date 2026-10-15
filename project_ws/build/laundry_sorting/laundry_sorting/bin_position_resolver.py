import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class BinPositionResolver(Node):

    def __init__(self):

        super().__init__(
            "bin_position_resolver"
        )

        self.ocr_positions = {
            "BIN_A": None,
            "BIN_B": None,
        }

        self.color_positions = {
            "BIN_A": None,
            "BIN_B": None,
        }

        self.last_output = {
            "BIN_A": None,
            "BIN_B": None,
        }

        self.create_subscription(
            String,
            "/laundry/bin_detections",
            self.ocr_callback,
            10
        )

        self.create_subscription(
            String,
            "/laundry/bin_color_detections",
            self.color_callback,
            10
        )

        self.publisher = self.create_publisher(
            String,
            "/laundry/bin_positions",
            10
        )

        self.get_logger().info(
            "BIN Position Resolver 시작"
        )

    def ocr_callback(self, msg):

        try:
            data = json.loads(
                msg.data
            )
        except Exception:
            return

        candidate = data.get(
            "candidate"
        )

        center = data.get(
            "center"
        )

        bbox = data.get(
            "bbox"
        )

        if (
            candidate in self.ocr_positions
            and center is not None
        ):
            self.ocr_positions[candidate] = {
                "center": center,
                "bbox": bbox,
                "source": "OCR"
            }

            self.resolve(
                candidate
            )

    def color_callback(self, msg):

        try:
            data = json.loads(
                msg.data
            )
        except Exception:
            return

        bin_name = data.get(
            "bin"
        )

        center = data.get(
            "center"
        )

        bbox = data.get(
            "bbox"
        )

        if (
            bin_name in self.color_positions
            and center is not None
        ):
            self.color_positions[bin_name] = {
                "center": center,
                "bbox": bbox,
                "source": "COLOR"
            }

            self.resolve(
                bin_name
            )

    def resolve(self, bin_name):

        # 빨래통 본체 위치가 있으면 우선 사용.
        # 없으면 A/B OCR 글자 위치 사용.
        position = (
            self.color_positions[bin_name]
            or
            self.ocr_positions[bin_name]
        )

        if position is None:
            return

        result = {
            "bin": bin_name,
            "center": position["center"],
            "bbox": position["bbox"],
            "source": position["source"]
        }

        if result == self.last_output[bin_name]:
            return

        self.last_output[bin_name] = result

        message = String()

        message.data = json.dumps(
            result,
            ensure_ascii=False
        )

        self.publisher.publish(
            message
        )

        center = result["center"]

        self.get_logger().info(
            f"{bin_name} 위치 확정 "
            f"source={result['source']} "
            f"center=({center[0]}, {center[1]})"
        )


def main(args=None):

    rclpy.init(
        args=args
    )

    node = BinPositionResolver()

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
