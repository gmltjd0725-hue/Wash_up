import os

import numpy as np
import pyaudio

from build_wakeup_template import extract_feature, similarity


RATE = 16000
CHANNELS = 1
CHUNK = 1024
LISTEN_SECONDS = 1.2
ENERGY_THRESHOLD = 0.015

TEMPLATE_PATH = os.path.expanduser(
    "~/project_ws/laundry_project/wakeup_template.npz"
)


def main():

    data = np.load(TEMPLATE_PATH)

    samples = data["samples"]
    threshold = float(data["threshold"][0])

    print()
    print("=== 새 '야' 감지 테스트 ===")
    print(f"감지 기준: {threshold:.3f}")
    print("'야'라고 말하거나 다른 말도 해보세요.")
    print("종료: Ctrl+C")
    print()

    audio = pyaudio.PyAudio()

    stream = audio.open(
        format=pyaudio.paInt16,
        channels=CHANNELS,
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

                raw = stream.read(
                    CHUNK,
                    exception_on_overflow=False
                )

                frames.append(raw)

            signal = np.frombuffer(
                b"".join(frames),
                dtype=np.int16
            ).astype(np.float32)

            energy = (
                np.sqrt(np.mean(signal ** 2))
                / 32768.0
            )

            if energy < ENERGY_THRESHOLD:
                continue

            feature = extract_feature(
                signal,
                RATE
            )

            scores = [
                similarity(
                    feature,
                    sample
                )
                for sample in samples
            ]

            score = max(scores)

            print(
                f"최고 유사도: {score:.3f}"
            )

            if score >= threshold:

                print(
                    ">>> '야' 감지 성공 <<<"
                )

    except KeyboardInterrupt:

        print("\n테스트 종료")

    finally:

        stream.stop_stream()
        stream.close()
        audio.terminate()


if __name__ == "__main__":
    main()
