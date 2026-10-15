from difflib import SequenceMatcher

import json
import os
import wave
from collections import deque
from contextlib import contextmanager

import numpy as np
import pyaudio
import rclpy

from rclpy.node import Node
from std_msgs.msg import String

from voice_processing.wakeup import WakeupDetector
from voice_processing.stt import SpeechToText
from voice_processing.command_parser import CommandParser


@contextmanager
def suppress_audio_stderr():
    saved_stderr = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)

    try:
        os.dup2(devnull, 2)
        yield
    finally:
        os.dup2(saved_stderr, 2)
        os.close(saved_stderr)
        os.close(devnull)


class VoiceNode(Node):

    def __init__(self):
        super().__init__("voice_node")

        self.wakeup = WakeupDetector(
            wakeword_name="야",
            record_seconds=5
        )

        self.stt = SpeechToText()
        self.parser = CommandParser()

        self.command_publisher = self.create_publisher(
            String,
            "/voice/command",
            10
        )

        self.audio_path = "/tmp/laundry_command.wav"

        self.rate = 16000
        self.channels = 1
        self.chunk = 1024

        # 안내 후 이 시간 동안 말 시작을 기다림
        self.wait_for_speech_seconds = 5.0

        # 말이 끝난 뒤 이 시간 동안 조용하면 종료
        self.end_silence_seconds = 5.0

        # 실제 명령 녹음의 최대 시간
        self.max_command_seconds = 20.0

        # 첫 음절이 잘리지 않도록 앞부분 보관
        self.pre_roll_chunks = 4

        self.processing = False

        self.timer = self.create_timer(
            0.5,
            self.voice_loop
        )

        self.get_logger().info(
            "Voice Node 시작"
        )

        self.get_logger().info(
            "'야' 대기 중"
        )

    def calculate_rms(self, raw):
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

    def voice_loop(self):

        if self.processing:
            return

        self.processing = True

        try:
            detected = self.wakeup.wait_for_wakeup()

            if not detected:
                return

            self.get_logger().info(
                "'야' 감지"
            )

            self.wakeup.close()

            first_command = True
            retry_prompted = False

            while True:

                if first_command:
                    prompt = "명령을 말씀하세요."

                elif not retry_prompted:
                    prompt = "다시 명령을 말씀하세요."
                    retry_prompted = True

                else:
                    prompt = ""

                success = self.record_command(
                    prompt
                )

                first_command = False

                if not success:
                    continue

                text = self.stt.transcribe(
                    self.audio_path
                )

                if not text:
                    continue

                normalized = (
                    text
                    .replace(" ", "")
                    .replace(".", "")
                    .replace(",", "")
                    .replace("?", "")
                    .replace("!", "")
                )

                allowed_command = (
                    "밝은빨래와어두운빨래를구분해줘"
                )

                similarity = SequenceMatcher(
                    None,
                    normalized,
                    allowed_command
                ).ratio()

                # 정식 명령어와 80% 미만이면 무시
                if similarity < 0.80:
                    continue

                # 80% 이상이면 정식 명령어로 자동 보정
                text = (
                    "밝은 빨래와 어두운 빨래를 구분해줘"
                )

                self.get_logger().info(
                    f"STT 결과: {text}"
                )

                self.get_logger().info(
                    f"명령 유사도: {similarity * 100:.0f}%"
                )

                result = self.parser.parse(
                    text
                )

                intent = result.get(
                    "intent"
                )

                target = result.get(
                    "target"
                )

                if intent != "SORT_LAUNDRY":
                    continue

                self.get_logger().info(
                    f"Intent: {intent}"
                )

                self.get_logger().info(
                    f"Target: {target}"
                )

                message = String()

                message.data = json.dumps(
                    result,
                    ensure_ascii=False
                )

                self.command_publisher.publish(
                    message
                )

                self.get_logger().info(
                    f"/voice/command 전송: "
                    f"{message.data}"
                )

                break

        except Exception as e:
            self.get_logger().error(
                f"Voice 처리 오류: {e}"
            )

        finally:
            try:
                self.wakeup.close()
            except Exception:
                pass

            try:
                self.wakeup = WakeupDetector(
                    wakeword_name="야",
                    record_seconds=5
                )

                self.get_logger().info(
                    "'야' 다시 대기 중"
                )

            except Exception as e:
                self.get_logger().error(
                    f"Wakeup 재시작 실패: {e}"
                )

            self.processing = False


    def record_command(self, prompt):

        audio = None
        stream = None

        try:
            if prompt:
                self.get_logger().info(
                    prompt
                )

            with suppress_audio_stderr():
                audio = pyaudio.PyAudio()

                stream = audio.open(
                    format=pyaudio.paInt16,
                    channels=self.channels,
                    rate=self.rate,
                    input=True,
                    frames_per_buffer=self.chunk
                )

            # 주변 소음 기준 측정
            noise_values = []

            calibration_chunks = max(
                3,
                int(
                    self.rate
                    / self.chunk
                    * 0.5
                )
            )

            for _ in range(calibration_chunks):
                raw = stream.read(
                    self.chunk,
                    exception_on_overflow=False
                )

                noise_values.append(
                    self.calculate_rms(raw)
                )

            baseline = float(
                np.median(noise_values)
            )

            speech_start_threshold = max(
                baseline + 180.0,
                min(
                    baseline * 1.45,
                    baseline + 4000.0
                )
            )

            speech_continue_threshold = max(
                baseline * 1.15,
                baseline + 80.0
            )

            pre_roll = deque(
                maxlen=self.pre_roll_chunks
            )

            frames = None

            wait_chunks = int(
                self.rate
                / self.chunk
                * self.wait_for_speech_seconds
            )

            # 말 시작 대기
            for _ in range(wait_chunks):

                raw = stream.read(
                    self.chunk,
                    exception_on_overflow=False
                )

                pre_roll.append(
                    raw
                )

                rms = self.calculate_rms(
                    raw
                )

                if rms >= speech_start_threshold:
                    frames = list(
                        pre_roll
                    )
                    break

            if frames is None:

                # 재안내 이후에는 같은 로그를 계속 찍지 않음
                if prompt:
                    self.get_logger().warning(
                        "5초 동안 명령이 없었습니다."
                    )

                return False

            silence_chunks = 0

            silence_limit = int(
                self.rate
                / self.chunk
                * self.end_silence_seconds
            )

            max_chunks = int(
                self.rate
                / self.chunk
                * self.max_command_seconds
            )

            # 말이 끝날 때까지 녹음
            for _ in range(max_chunks):

                raw = stream.read(
                    self.chunk,
                    exception_on_overflow=False
                )

                frames.append(
                    raw
                )

                rms = self.calculate_rms(
                    raw
                )

                if rms < speech_continue_threshold:
                    silence_chunks += 1
                else:
                    silence_chunks = 0

                if silence_chunks >= silence_limit:
                    break

            with wave.open(
                self.audio_path,
                "wb"
            ) as wav_file:

                wav_file.setnchannels(
                    self.channels
                )

                wav_file.setsampwidth(
                    audio.get_sample_size(
                        pyaudio.paInt16
                    )
                )

                wav_file.setframerate(
                    self.rate
                )

                wav_file.writeframes(
                    b"".join(frames)
                )

            return True

        except Exception as e:
            self.get_logger().error(
                f"녹음 오류: {e}"
            )

            return False

        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass

            if audio is not None:
                with suppress_audio_stderr():
                    try:
                        audio.terminate()
                    except Exception:
                        pass


    def destroy_node(self):

        try:
            self.wakeup.close()
        except Exception:
            pass

        super().destroy_node()


def main(args=None):

    rclpy.init(args=args)

    node = VoiceNode()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
