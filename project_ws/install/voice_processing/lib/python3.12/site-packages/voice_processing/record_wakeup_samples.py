import os
import time
import wave

import pyaudio


SAMPLE_COUNT = 10
RECORD_SECONDS = 1.5

RATE = 16000
CHANNELS = 1
CHUNK = 1024
FORMAT = pyaudio.paInt16

SAVE_DIR = os.path.expanduser(
    "~/project_ws/laundry_project/wakeup_samples"
)


def main():

    os.makedirs(
        SAVE_DIR,
        exist_ok=True
    )

    audio = pyaudio.PyAudio()

    print()
    print("=== '야' 음성 샘플 녹음 ===")
    print(f"총 {SAMPLE_COUNT}번 녹음합니다.")
    print()

    try:

        for index in range(
            1,
            SAMPLE_COUNT + 1
        ):

            input(
                f"[{index}/{SAMPLE_COUNT}] "
                "Enter를 누르고 '야'라고 말하세요."
            )

            stream = audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )

            print("녹음 시작 → 야!")

            frames = []

            total_chunks = int(
                RATE
                / CHUNK
                * RECORD_SECONDS
            )

            for _ in range(
                total_chunks
            ):

                data = stream.read(
                    CHUNK,
                    exception_on_overflow=False
                )

                frames.append(
                    data
                )

            stream.stop_stream()
            stream.close()

            file_path = os.path.join(
                SAVE_DIR,
                f"ya_{index:02d}.wav"
            )

            with wave.open(
                file_path,
                "wb"
            ) as wav_file:

                wav_file.setnchannels(
                    CHANNELS
                )

                wav_file.setsampwidth(
                    audio.get_sample_size(
                        FORMAT
                    )
                )

                wav_file.setframerate(
                    RATE
                )

                wav_file.writeframes(
                    b"".join(frames)
                )

            print(
                f"저장 완료: {file_path}"
            )

            time.sleep(0.5)

    finally:

        audio.terminate()

    print()
    print("10개 샘플 녹음 완료")


if __name__ == "__main__":
    main()
