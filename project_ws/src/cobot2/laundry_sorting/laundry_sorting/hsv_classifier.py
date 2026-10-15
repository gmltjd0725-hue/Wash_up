import cv2
import numpy as np


class HSVClassifier:

    def __init__(
        self,
        saturation_threshold=102.0,
        value_threshold=191.0
    ):
        self.saturation_threshold = float(
            saturation_threshold
        )

        self.value_threshold = float(
            value_threshold
        )

    def analyze(self, roi):

        if roi is None:
            raise ValueError("ROI가 None입니다.")

        if roi.size == 0:
            raise ValueError("ROI가 비어 있습니다.")

        hsv = cv2.cvtColor(
            roi,
            cv2.COLOR_BGR2HSV
        )

        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]

        median_s = float(
            np.median(saturation)
        )

        median_v = float(
            np.median(value)
        )

        return median_s, median_v

    def classify(self, roi):

        median_s, median_v = self.analyze(
            roi
        )

        if (
            median_s <= self.saturation_threshold
            and
            median_v >= self.value_threshold
        ):
            return {
                "saturation": median_s,
                "value": median_v,
                "classification": "LIGHT",
                "destination": "BIN_A"
            }

        return {
            "saturation": median_s,
            "value": median_v,
            "classification": "DARK",
            "destination": "BIN_B"
        }
