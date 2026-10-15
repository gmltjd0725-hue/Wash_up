import time
import wave
from collections import deque

import numpy as np
import pyaudio

from stt import SpeechToText


RATE = 16000
CHANNELS = 1
CHUNK = 1024
FORMAT = pyaudio.paInt16

CALIBRATION_SECONDS = 3.0

PRE_ROLL_CHUNKS = 4
POST_TRIGGER_CHUNKS = 12

AUDIO_PATH = "/tmp/onset_wakeup_test.wav"


def calculate_rms(raw):

    signal = np.frombuffer(
        raw,
        dtype=np.int16
    ).astype(np.float32)

    if signal.size == 0:
        return 0.0

    return float(
        np.sqrt(
            np.mean(signal ** 2)
        )
    )


def normalize_text(text):

    return (
        text
        .lower()
        .replace(",", "")
        .replace(".", "")
        .replace("!", "")
        .replace("?", "")
        .replace(" ", "")
        .strip()
    )


def is_wakeup(text):

    candidates = [
        "야",
        "야아",
        "얘",

        "ya",
        "yaa",
        "yah",
        "yeah",

        "ja",
        "jaa",

        "や",
        "やあ",
    ]

    return normalize_text(text) in candidates


def main():

    audio = pyaudio.PyAudio()
    stt = SpeechToText()

    stream = audio.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    print()
    print("=== 자동 백색소음 측정 ===")
    print("3초 동안 아무 말하지 마세요.")

    baseline_values = []

    calibration_chunks = int(
        RATE
        / CHUNK
        * CALIBRATION_SECONDS
    )

    for _ in range(calibration_chunks):

        raw = stream.read(
            CHUNK,
            exception_on_overflow=False
        )

        baseline_values.append(
            calculate_rms(raw)
        )

    baseline = float(
        np.median(baseline_values)
    )

    trigger_threshold = max(
        baseline * 1.45,
        baseline + 180.0
    )

    print()
    print(
        f"백색소음 기준 RMS = "
        f"{baseline:.0f}"
    )

    print(
        f"음성 시작 기준 RMS = "
        f"{trigger_threshold:.0f}"
    )

    print()
    print("'야'라고 말해보세요.")
    print("다른 말도 섞어서 테스트해도 됩니다.")
    print("종료: Ctrl+C")
    print()

    pre_roll = deque(
        maxlen=PRE_ROLL_CHUNKS
    )

    try:

        while True:

            raw = stream.read(
                CHUNK,
                exception_on_overflow=False
            )

            rms = calculate_rms(raw)

            pre_roll.append(raw)

            if rms < trigger_threshold:
                continue

            print(
                f"[VOICE] 소리 시작 감지 "
                f"RMS={rms:.0f}"
            )

            frames = list(
                pre_roll
            )

            for _ in range(
                POST_TRIGGER_CHUNKS
            ):

                frames.append(
                    stream.read(
                        CHUNK,
                        exception_on_overflow=False
                    )
                )

            with wave.open(
                AUDIO_PATH,
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

            text = stt.transcribe(
                AUDIO_PATH
            )

            if not text:

                print(
                    "[WAKEUP] STT 실패"
                )

            else:

                normalized = normalize_text(
                    text
                )

                print(
                    f"[WAKEUP] STT 결과: "
                    f"{normalized}"
                )

                if is_wakeup(text):

                    print(
                        ">>> '야' 감지 성공 <<<"
                    )

                else:

                    print(
                        ">>> 다른 음성, 무시 <<<"
                    )

            pre_roll.clear()

            time.sleep(0.3)

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
