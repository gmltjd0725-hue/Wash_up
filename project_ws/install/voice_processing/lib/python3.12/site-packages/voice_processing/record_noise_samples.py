import os
import wave

import pyaudio


SAMPLE_COUNT = 10
RECORD_SECONDS = 1.5

RATE = 16000
CHANNELS = 1
CHUNK = 1024
FORMAT = pyaudio.paInt16

SAVE_DIR = os.path.expanduser(
    "~/project_ws/laundry_project/noise_samples"
)


def main():

    os.makedirs(
        SAVE_DIR,
        exist_ok=True
    )

    audio = pyaudio.PyAudio()

    print("=== 주변소리 샘플 녹음 ===")
    print("'야'라고 말하지 마세요.")

    try:

        for index in range(1, SAMPLE_COUNT + 1):

            input(
                f"[{index}/{SAMPLE_COUNT}] "
                "Enter를 누르고 평소처럼 조용히 있으세요."
            )

            stream = audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )

            print("주변소리 녹음 중...")

            frames = []

            total_chunks = int(
                RATE / CHUNK * RECORD_SECONDS
            )

            for _ in range(total_chunks):

                data = stream.read(
                    CHUNK,
                    exception_on_overflow=False
                )

                frames.append(data)

            stream.stop_stream()
            stream.close()

            path = os.path.join(
                SAVE_DIR,
                f"noise_{index:02d}.wav"
            )

            with wave.open(path, "wb") as wav_file:

                wav_file.setnchannels(CHANNELS)

                wav_file.setsampwidth(
                    audio.get_sample_size(FORMAT)
                )

                wav_file.setframerate(RATE)

                wav_file.writeframes(
                    b"".join(frames)
                )

            print(f"저장 완료: {path}")

    finally:

        audio.terminate()

    print("주변소리 10개 녹음 완료")


if __name__ == "__main__":
    main()
