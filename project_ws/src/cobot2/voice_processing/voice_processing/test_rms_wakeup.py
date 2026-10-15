import numpy as np
import pyaudio


RATE = 16000
CHUNK = 1024
LISTEN_SECONDS = 1.0

RMS_MIN = 400
RMS_MAX = 1050


def main():

    print()
    print("=== RMS '야' 감지 테스트 ===")
    print("'야'와 다른 말을 섞어서 말해보세요.")
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

            print(
                f"RMS = {rms:.0f}"
            )

            if RMS_MIN <= rms <= RMS_MAX:

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
