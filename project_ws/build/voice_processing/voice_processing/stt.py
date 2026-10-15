import os

from dotenv import load_dotenv
from openai import OpenAI


# =========================
# .env 파일 불러오기
# =========================

ENV_PATH = os.path.expanduser(
    "~/project_ws/laundry_project/.env"
)

load_dotenv(ENV_PATH)


class SpeechToText:

    def __init__(self):

        # =========================
        # OpenAI API Key 확인
        # =========================

        api_key = os.getenv(
            "OPENAI_API_KEY"
        )

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY가 설정되지 않았습니다."
            )

        # =========================
        # OpenAI Client
        # =========================

        self.client = OpenAI(
            api_key=api_key
        )

        # 음성 → 텍스트 모델
        self.model = "gpt-4o-transcribe"

    def transcribe(self, audio_path):
        """
        녹음된 음성 파일을
        텍스트로 변환한다.
        """

        # =========================
        # 음성 파일 확인
        # =========================

        if not audio_path:

            print(
                "[STT] audio_path가 없습니다."
            )

            return ""

        if not os.path.exists(audio_path):

            print(
                f"[STT] 음성 파일이 없습니다: "
                f"{audio_path}"
            )

            return ""

        # =========================
        # STT 실행
        # =========================

        try:

            with open(
                audio_path,
                "rb"
            ) as audio_file:

                transcription = (
                    self.client.audio.transcriptions.create(
                        model=self.model,
                        file=audio_file,
                        language="ko"
                    )
                )

            text = (
                transcription.text.strip()
            )

            print(
                f"[STT] 인식 결과: {text}"
            )

            return text

        except Exception as e:

            print(
                f"[STT ERROR] {e}"
            )

            return ""