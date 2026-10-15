import os
import glob

import numpy as np

from scipy.io import wavfile
from build_wakeup_template import extract_feature, similarity


YA_DIR = os.path.expanduser(
    "~/project_ws/laundry_project/wakeup_samples"
)

NOISE_DIR = os.path.expanduser(
    "~/project_ws/laundry_project/noise_samples"
)

OUTPUT_PATH = os.path.expanduser(
    "~/project_ws/laundry_project/wakeup_classifier.npz"
)


def load_features(pattern):

    features = []

    for path in sorted(glob.glob(pattern)):

        rate, audio = wavfile.read(path)

        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        feature = extract_feature(
            audio,
            rate
        )

        features.append(feature)

    return np.array(
        features,
        dtype=np.float32
    )


def main():

    ya_samples = load_features(
        os.path.join(
            YA_DIR,
            "ya_*.wav"
        )
    )

    noise_samples = load_features(
        os.path.join(
            NOISE_DIR,
            "noise_*.wav"
        )
    )

    ya_margins = []
    noise_margins = []

    # =========================
    # '야' 샘플 검사
    # =========================

    for i, feature in enumerate(ya_samples):

        ya_score = max(
            similarity(feature, sample)
            for j, sample in enumerate(ya_samples)
            if i != j
        )

        noise_score = max(
            similarity(feature, sample)
            for sample in noise_samples
        )

        ya_margins.append(
            ya_score - noise_score
        )

    # =========================
    # 주변소리 샘플 검사
    # =========================

    for i, feature in enumerate(noise_samples):

        ya_score = max(
            similarity(feature, sample)
            for sample in ya_samples
        )

        noise_score = max(
            similarity(feature, sample)
            for j, sample in enumerate(noise_samples)
            if i != j
        )

        noise_margins.append(
            ya_score - noise_score
        )

    ya_margins = np.array(
        ya_margins,
        dtype=np.float32
    )

    noise_margins = np.array(
        noise_margins,
        dtype=np.float32
    )

    ya_min = float(
        np.min(ya_margins)
    )

    noise_max = float(
        np.max(noise_margins)
    )

    threshold = (
        ya_min + noise_max
    ) / 2.0

    np.savez(
        OUTPUT_PATH,
        ya_samples=ya_samples,
        noise_samples=noise_samples,
        margin_threshold=np.array(
            [threshold],
            dtype=np.float32
        )
    )

    print(
        f"'야' 최소 차이: {ya_min:.3f}"
    )

    print(
        f"주변소리 최대 차이: {noise_max:.3f}"
    )

    print(
        f"감지 차이 기준: {threshold:.3f}"
    )


if __name__ == "__main__":
    main()
