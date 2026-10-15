import glob
import os

import numpy as np
import pyaudio
from scipy.io import wavfile

from build_wakeup_template import extract_feature, similarity


RATE = 16000
CHUNK = 1024
LISTEN_SECONDS = 1.2

RMS_MIN = 400
RMS_MAX = 1050
MARGIN_THRESHOLD = 0.0015

YA_FILES = sorted(
    glob.glob(
        os.path.expanduser(
            "~/project_ws/laundry_project/wakeup_samples/ya_*.wav"
        )
    )
)[1:]

OTHER_FILES = sorted(
    glob.glob(
        os.path.expanduser(
            "~/project_ws/laundry_project/"
            "negative_voice_samples/negative_*.wav"
        )
    )
)


def load_features(files):

    features = []

    for path in files:

        rate, audio = wavfile.read(path)

        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        features.append(
            extract_feature(audio, rate)
        )

    return features


def main():

    ya_samples = load_features(
        YA_FILES
    )

    other_samples = load_features(
        OTHER_FILES
    )

    print()
    print("=== 최종 '야' 감지 테스트 ===")
    print("다른 말도 해보고 '야'도 말해보세요.")
    print("종료: Ctrl+C")
    print()

    audio = pyaudio.PyAudio()

    stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    total_chunks = int(
        RATE / CHUNK * LISTEN_SECONDS
    )

    try:

        while True:

            frames = []

            for _ in range(total_chunks):

                frames.append(
                    stream.read(
                        CHUNK,
                        exception_on_overflow=False
                    )
                )

            signal = np.frombuffer(
                b"".join(frames),
                dtype=np.int16
            ).astype(np.float32)

            rms = float(
                np.sqrt(
                    np.mean(signal ** 2)
                )
            )

            if not (
                RMS_MIN <= rms <= RMS_MAX
            ):
                print(
                    f"무시 RMS={rms:.0f}"
                )
                continue

            feature = extract_feature(
                signal,
                RATE
            )

            ya_score = max(
                similarity(
                    feature,
                    sample
                )
                for sample in ya_samples
            )

            other_score = max(
                similarity(
                    feature,
                    sample
                )
                for sample in other_samples
            )

            margin = (
                ya_score
                - other_score
            )

            print(
                f"RMS={rms:.0f} "
                f"margin={margin:.4f}"
            )

            if (
                margin
                >= MARGIN_THRESHOLD
            ):

                print(
                    ">>> '야' 감지 성공 <<<"
                )

    except KeyboardInterrupt:

        print(
            "\n테스트 종료"
        )

    finally:

        stream.stop_stream()
        stream.close()
        audio.terminate()


if __name__ == "__main__":
    main()
