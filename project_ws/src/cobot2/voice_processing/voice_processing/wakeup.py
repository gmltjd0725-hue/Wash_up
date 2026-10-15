import json
import time
import wave
from collections import deque
from pathlib import Path

import numpy as np
import pyaudio

from .stt import SpeechToText


class WakeupDetector:

    def __init__(self, wakeword_name="야", record_seconds=5):

        self.wakeword_name = wakeword_name

        self.rate = 16000
        self.channels = 1
        self.chunk = 1024
        self.format = pyaudio.paInt16

        # 시작할 때 현재 장소의 주변소음 측정
        self.calibration_seconds = 3.0

        # 최근 약 4초 RMS를 이용해
        # 주변소음 변화도 계속 따라감
        self.noise_window_chunks = max(
            24,
            int(self.rate / self.chunk * 4.0)
        )

        self.noise_window = deque(
            maxlen=self.noise_window_chunks
        )

        # '야' 첫 음절이 잘리지 않도록 앞부분 보관
        self.pre_roll_chunks = 4

        # 호출어 후보 감지 후 약 0.8초 추가 녹음
        self.post_trigger_chunks = 12

        self.audio_path = "/tmp/ya_wakeup_check.wav"

        # 성공한 내 '야'의
        # "주변소음 대비 상대 RMS" 저장
        self.profile_path = (
            Path.home()
            / "project_ws"
            / "laundry_project"
            / "voice_data"
            / "ya_adaptive_profile.json"
        )

        self.profile_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.ya_profile = self.load_ya_profile()

        self.audio = pyaudio.PyAudio()
        self.stream = None

        self.stt = SpeechToText()

        print(
            f"[WAKEUP] 호출어 설정: {self.wakeword_name}"
        )

        if self.ya_profile is None:

            print(
                "[WAKEUP] 학습된 '야' 상대 RMS 없음"
            )

        else:

            print(
                "[WAKEUP] 학습된 '야' 상대 RMS 로드: "
                f"MEDIAN=+{self.ya_profile['delta_median']:.0f} "
                f"MIN=+{self.ya_profile['delta_min']:.0f} "
                f"MAX=+{self.ya_profile['delta_max']:.0f}"
            )

    # =========================================================
    # RMS
    # =========================================================

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

    # =========================================================
    # STT TEXT
    # =========================================================

    def normalize_text(self, text):

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

    def is_wakeup_text(self, text):

        normalized = self.normalize_text(text)

        print(
            f"[WAKEUP] STT 결과: {normalized}"
        )

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

        return normalized in candidates

    # =========================================================
    # 내 '야' 상대 RMS 저장 / 불러오기
    # =========================================================

    def load_ya_profile(self):

        if not self.profile_path.exists():
            return None

        try:

            data = json.loads(
                self.profile_path.read_text()
            )

            return {
                "delta_median":
                    float(data["delta_median"]),

                "delta_min":
                    float(data["delta_min"]),

                "delta_max":
                    float(data["delta_max"]),
            }

        except Exception:
            return None

    def save_ya_profile(self):

        if self.ya_profile is None:
            return

        self.profile_path.write_text(
            json.dumps(
                self.ya_profile,
                indent=2,
                ensure_ascii=False
            )
        )

    # =========================================================
    # MICROPHONE
    # =========================================================

    def start_microphone(self):

        if self.stream is not None:
            return

        self.stream = self.audio.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk
        )

    # =========================================================
    # 현재 주변소음
    # =========================================================

    def get_noise_stats(self):

        if not self.noise_window:

            return {
                "median": 0.0,
                "min": 0.0,
                "max": 0.0,
            }

        values = np.array(
            self.noise_window,
            dtype=np.float32
        )

        # 최근 데이터에 사람 목소리나 큰 충격음이 섞여도
        # 주변소음 기준이 갑자기 올라가지 않게
        # 낮은 쪽 65%만 주변소음 후보로 사용
        values = np.sort(values)

        keep_count = max(
            3,
            int(len(values) * 0.65)
        )

        ambient = values[:keep_count]

        return {
            "median":
                float(np.median(ambient)),

            "min":
                float(np.min(ambient)),

            "max":
                float(np.max(ambient)),
        }

    def calibrate_noise(self):

        print(
            "[WAKEUP] 현재 주변소음 측정 중..."
        )

        self.noise_window.clear()

        total_chunks = int(
            self.rate
            / self.chunk
            * self.calibration_seconds
        )

        for _ in range(total_chunks):

            raw = self.stream.read(
                self.chunk,
                exception_on_overflow=False
            )

            self.noise_window.append(
                self.calculate_rms(raw)
            )

        stats = self.get_noise_stats()

        print(
            "[WAKEUP] 주변소음 RMS "
            f"MEDIAN={stats['median']:.0f} "
            f"MIN={stats['min']:.0f} "
            f"MAX={stats['max']:.0f}"
        )

        return stats

    # =========================================================
    # 현재 주변소음 + 내 '야' 상대값
    # =========================================================

    def make_trigger_threshold(
        self,
        noise_stats
    ):

        baseline = noise_stats["median"]

        if self.ya_profile is None:

            # 최초 1회는 아직 내 '야' 값이 없으므로
            # 주변소음에 비례한 임시 기준으로 후보를 잡는다.
            # STT가 실제 '야'라고 확인하면 즉시 학습값으로 전환.
            margin = max(
                180.0,
                min(
                    baseline * 0.12 + 300.0,
                    3500.0
                )
            )

        else:

            # 이전에 성공한 내 '야'가
            # 주변소음보다 얼마나 컸는지 사용
            margin = max(
                180.0,
                min(
                    self.ya_profile[
                        "delta_median"
                    ] * 0.40,
                    6000.0
                )
            )

        threshold = baseline + margin

        # int16 최대값보다 높은 기준은
        # 절대로 넘을 수 없으므로 제한
        return min(
            threshold,
            32500.0
        )

    # =========================================================
    # STT가 실제 '야'라고 확인한 경우만 학습
    # =========================================================

    def learn_ya_profile(
        self,
        candidate_rms,
        noise_stats
    ):

        if not candidate_rms:
            return

        baseline = noise_stats["median"]

        # 앞뒤 무음은 제외하고
        # 실제로 소리가 올라온 구간 위주로 계산
        speech_floor = (
            baseline
            + max(
                80.0,
                baseline * 0.03
            )
        )

        voiced = [
            value
            for value in candidate_rms
            if value >= speech_floor
        ]

        if len(voiced) < 2:
            voiced = list(candidate_rms)

        ya_median = float(
            np.median(voiced)
        )

        ya_min = float(
            np.min(voiced)
        )

        ya_max = float(
            np.max(voiced)
        )

        # 핵심:
        # 절대 RMS가 아니라
        # 현재 주변소음과 내 '야'의 차이를 기억
        delta_median = max(
            180.0,
            ya_median - baseline
        )

        delta_min = max(
            80.0,
            ya_min - baseline
        )

        delta_max = max(
            delta_median,
            ya_max - baseline
        )

        print(
            "[WAKEUP] 내 '야' RMS "
            f"MEDIAN={ya_median:.0f} "
            f"MIN={ya_min:.0f} "
            f"MAX={ya_max:.0f}"
        )

        print(
            "[WAKEUP] 주변소음 대비 내 '야' 상대값 "
            f"MEDIAN=+{delta_median:.0f} "
            f"MIN=+{delta_min:.0f} "
            f"MAX=+{delta_max:.0f}"
        )

        new_profile = {
            "delta_median":
                delta_median,

            "delta_min":
                delta_min,

            "delta_max":
                delta_max,
        }

        if self.ya_profile is None:

            self.ya_profile = new_profile

        else:

            # 장소/목소리 변화에 천천히 적응.
            # 기존값 70% + 새 성공값 30%.
            alpha = 0.30

            for key in [
                "delta_median",
                "delta_min",
                "delta_max",
            ]:

                self.ya_profile[key] = (
                    self.ya_profile[key]
                    * (1.0 - alpha)
                    +
                    new_profile[key]
                    * alpha
                )

        self.save_ya_profile()

    # =========================================================
    # WAV
    # =========================================================

    def save_audio(self, frames):

        with wave.open(
            self.audio_path,
            "wb"
        ) as wav_file:

            wav_file.setnchannels(
                self.channels
            )

            wav_file.setsampwidth(
                self.audio.get_sample_size(
                    self.format
                )
            )

            wav_file.setframerate(
                self.rate
            )

            wav_file.writeframes(
                b"".join(frames)
            )

    # =========================================================
    # WAIT FOR "야"
    # =========================================================

    def wait_for_wakeup(self):

        try:

            self.start_microphone()

            noise_stats = (
                self.calibrate_noise()
            )

            trigger_threshold = (
                self.make_trigger_threshold(
                    noise_stats
                )
            )

            print(
                "[WAKEUP] 현재 음성 시작 기준: "
                f"{trigger_threshold:.0f}"
            )

            print(
                "[WAKEUP] '야' 대기 중"
            )

            pre_roll = deque(
                maxlen=self.pre_roll_chunks
            )

            last_printed_noise = (
                noise_stats["median"]
            )

            last_noise_print_time = (
                time.time()
            )

            while True:

                raw = self.stream.read(
                    self.chunk,
                    exception_on_overflow=False
                )

                rms = self.calculate_rms(raw)

                pre_roll.append(raw)

                # 현재 장소가 바뀌거나
                # 소음 크기가 바뀌는 것을 계속 추적
                self.noise_window.append(rms)

                noise_stats = (
                    self.get_noise_stats()
                )

                trigger_threshold = (
                    self.make_trigger_threshold(
                        noise_stats
                    )
                )

                # 주변소음이 크게 변한 경우에만 로그 출력
                now = time.time()

                noise_change = abs(
                    noise_stats["median"]
                    - last_printed_noise
                )

                change_limit = max(
                    300.0,
                    last_printed_noise * 0.15
                )

                if (
                    noise_change >= change_limit
                    and
                    now - last_noise_print_time >= 2.0
                ):

                    print(
                        "[WAKEUP] 주변소음 변화 -> "
                        f"MEDIAN={noise_stats['median']:.0f} "
                        f"MIN={noise_stats['min']:.0f} "
                        f"MAX={noise_stats['max']:.0f} | "
                        f"새 기준={trigger_threshold:.0f}"
                    )

                    last_printed_noise = (
                        noise_stats["median"]
                    )

                    last_noise_print_time = now

                if rms < trigger_threshold:
                    continue

                print(
                    "[WAKEUP] 음성 후보 감지 "
                    f"RMS={rms:.0f} | "
                    f"현재 주변소음="
                    f"{noise_stats['median']:.0f} | "
                    f"기준={trigger_threshold:.0f}"
                )

                frames = list(pre_roll)

                candidate_rms = [
                    self.calculate_rms(frame)
                    for frame in frames
                ]

                for _ in range(
                    self.post_trigger_chunks
                ):

                    next_raw = self.stream.read(
                        self.chunk,
                        exception_on_overflow=False
                    )

                    frames.append(next_raw)

                    next_rms = (
                        self.calculate_rms(
                            next_raw
                        )
                    )

                    candidate_rms.append(
                        next_rms
                    )

                    self.noise_window.append(
                        next_rms
                    )

                self.save_audio(frames)

                text = self.stt.transcribe(
                    self.audio_path
                )

                if not text:

                    print(
                        "[WAKEUP] STT 실패"
                    )

                    pre_roll.clear()
                    continue

                if self.is_wakeup_text(text):

                    # STT가 실제 '야'라고 확인된 경우에만
                    # 내 '야'의 상대 RMS를 학습
                    self.learn_ya_profile(
                        candidate_rms,
                        noise_stats
                    )

                    print(
                        "[WAKEUP] '야' 감지 성공"
                    )

                    self.stop_microphone()

                    return True

                print(
                    "[WAKEUP] 다른 음성/소음, 무시"
                )

                pre_roll.clear()

                time.sleep(0.2)

        except KeyboardInterrupt:

            print(
                "\n[WAKEUP] 사용자 종료"
            )

            return False

        except Exception as e:

            print(
                f"[WAKEUP ERROR] {e}"
            )

            return False

    # =========================================================
    # CLOSE
    # =========================================================

    def stop_microphone(self):

        if self.stream is not None:

            try:

                self.stream.stop_stream()
                self.stream.close()

            except Exception:
                pass

            self.stream = None

    def close(self):

        self.stop_microphone()

        if self.audio is not None:

            try:
                self.audio.terminate()

            except Exception:
                pass

            self.audio = None

        print(
            "[WAKEUP] 마이크 종료"
        )
