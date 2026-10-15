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
    "~/project_ws/laundry_project/negative_voice_samples"
)


def main():

    os.makedirs(
        SAVE_DIR,
        exist_ok=True
    )

    audio = pyaudio.PyAudio()

    print("=== '야'가 아닌 음성 녹음 ===")
    print("'야'는 말하지 마세요.")

    try:

        for index in range(
            1,
            SAMPLE_COUNT + 1
        ):

            input(
                f"[{index}/{SAMPLE_COUNT}] "
                "Enter 후 '야'가 아닌 아무 말을 하세요."
            )

            stream = audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )

            print("녹음 중...")

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
                f"negative_{index:02d}.wav"
            )

            with wave.open(
                path,
                "wb"
            ) as wav_file:

                wav_file.setnchannels(CHANNELS)

                wav_file.setsampwidth(
                    audio.get_sample_size(FORMAT)
                )

                wav_file.setframerate(RATE)

                wav_file.writeframes(
                    b"".join(frames)
                )

            print(
                f"저장 완료: {path}"
            )

    finally:

        audio.terminate()

    print("다른 음성 10개 녹음 완료")


if __name__ == "__main__":
    main()
