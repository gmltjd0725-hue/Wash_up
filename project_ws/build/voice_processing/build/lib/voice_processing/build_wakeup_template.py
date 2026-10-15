import os
import glob

import numpy as np

from scipy.io import wavfile
from scipy.fftpack import dct


SAMPLE_DIR = os.path.expanduser(
    "~/project_ws/laundry_project/wakeup_samples"
)

OUTPUT_PATH = os.path.expanduser(
    "~/project_ws/laundry_project/wakeup_template.npz"
)

TARGET_FRAMES = 32
FEATURE_COUNT = 20


def trim_silence(audio):

    audio = audio.astype(np.float32)

    peak = np.max(np.abs(audio))

    if peak == 0:
        return audio

    normalized = audio / peak

    threshold = 0.08

    indices = np.where(
        np.abs(normalized) > threshold
    )[0]

    if len(indices) == 0:
        return audio

    start = max(
        0,
        indices[0] - 800
    )

    end = min(
        len(audio),
        indices[-1] + 800
    )

    return audio[start:end]


def resample_frames(features):

    old_length = len(features)

    if old_length < 2:
        raise ValueError(
            "특징 프레임이 너무 짧습니다."
        )

    old_positions = np.linspace(
        0.0,
        1.0,
        old_length
    )

    new_positions = np.linspace(
        0.0,
        1.0,
        TARGET_FRAMES
    )

    output = np.zeros(
        (
            TARGET_FRAMES,
            FEATURE_COUNT
        ),
        dtype=np.float32
    )

    for index in range(
        FEATURE_COUNT
    ):

        output[:, index] = np.interp(
            new_positions,
            old_positions,
            features[:, index]
        )

    return output


def extract_feature(audio, rate):

    audio = trim_silence(
        audio
    )

    if len(audio) < 1600:

        raise ValueError(
            "음성이 너무 짧습니다."
        )

    peak = np.max(
        np.abs(audio)
    )

    if peak > 0:

        audio = (
            audio
            / peak
        )

    # =========================
    # Pre-emphasis
    # =========================

    emphasized = np.append(
        audio[0],
        audio[1:]
        - 0.97 * audio[:-1]
    )

    frame_length = int(
        0.025 * rate
    )

    frame_step = int(
        0.010 * rate
    )

    frames = []

    start = 0

    while (
        start + frame_length
        <= len(emphasized)
    ):

        frame = emphasized[
            start:
            start + frame_length
        ]

        frame = (
            frame
            * np.hamming(
                frame_length
            )
        )

        frames.append(
            frame
        )

        start += frame_step

    frames = np.array(
        frames
    )

    if len(frames) < 2:

        raise ValueError(
            "프레임 수가 부족합니다."
        )

    # =========================
    # Spectrum
    # =========================

    spectrum = np.abs(
        np.fft.rfft(
            frames,
            n=512
        )
    )

    power = (
        spectrum ** 2
    ) / 512.0

    power = np.maximum(
        power,
        1e-10
    )

    log_power = np.log(
        power
    )

    # =========================
    # DCT 특징
    # =========================

    features = dct(
        log_power,
        type=2,
        axis=1,
        norm="ortho"
    )[:, :FEATURE_COUNT]

    # 각 프레임 정규화
    norms = np.linalg.norm(
        features,
        axis=1,
        keepdims=True
    )

    norms = np.maximum(
        norms,
        1e-8
    )

    features = (
        features
        / norms
    )

    # 시간 길이를 32프레임으로 통일
    features = resample_frames(
        features
    )

    return features.astype(
        np.float32
    )


def similarity(
    feature_a,
    feature_b
):

    frame_scores = np.sum(
        feature_a
        * feature_b,
        axis=1
    )

    return float(
        np.mean(
            frame_scores
        )
    )


def main():

    files = sorted(
        glob.glob(
            os.path.join(
                SAMPLE_DIR,
                "ya_*.wav"
            )
        )
    )

    if not files:

        print(
            "'야' 녹음 샘플이 없습니다."
        )

        return

    features = []

    for file_path in files:

        rate, audio = wavfile.read(
            file_path
        )

        if audio.ndim > 1:

            audio = np.mean(
                audio,
                axis=1
            )

        feature = extract_feature(
            audio,
            rate
        )

        features.append(
            feature
        )

        print(
            f"처리 완료: "
            f"{os.path.basename(file_path)}"
        )

    features = np.array(
        features,
        dtype=np.float32
    )

    # =========================
    # 샘플끼리 유사도 확인
    # =========================

    nearest_scores = []

    for i in range(
        len(features)
    ):

        scores = []

        for j in range(
            len(features)
        ):

            if i == j:
                continue

            scores.append(
                similarity(
                    features[i],
                    features[j]
                )
            )

        nearest_scores.append(
            max(scores)
        )

    minimum_score = float(
        np.min(
            nearest_scores
        )
    )

    threshold = max(
        0.80,
        minimum_score - 0.03
    )

    np.savez(
        OUTPUT_PATH,
        samples=features,
        threshold=np.array(
            [threshold],
            dtype=np.float32
        )
    )

    print()
    print(
        f"샘플 간 최소 기준: "
        f"{minimum_score:.3f}"
    )

    print(
        f"실시간 감지 기준: "
        f"{threshold:.3f}"
    )

    print(
        f"'야' 시간 특징 생성 완료: "
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
