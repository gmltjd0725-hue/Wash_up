class CommandParser:

    def __init__(self):

        self.target_keywords = {
            "셔츠": "shirt",
            "티셔츠": "shirt",
            "바지": "pants",
            "양말": "socks",
            "수건": "towel",
        }

    def parse(self, text):

        if text is None:
            return self._unknown_result("")

        text = text.strip()

        if text == "":
            return self._unknown_result(text)

        normalized = (
            text
            .lower()
            .replace(" ", "")
            .replace(".", "")
            .replace(",", "")
            .replace("!", "")
            .replace("?", "")
        )

        # =========================
        # 빨래 관련 명령인지 확인
        # =========================

        if "빨래" not in normalized:
            return self._unknown_result(text)

        # =========================
        # 분류 / 구분 명령 확인
        # =========================

        sort_keywords = [
            "분류",
            "구분",
            "나눠",
            "나누어",
            "나눠줘",
        ]

        if not any(
            keyword in normalized
            for keyword in sort_keywords
        ):
            return self._unknown_result(text)

        # =========================
        # Target 찾기
        # =========================

        target = None

        for keyword, class_name in self.target_keywords.items():

            if keyword in normalized:

                target = class_name
                break

        return {
            "command": text,
            "intent": "SORT_LAUNDRY",
            "target": target
        }

    def _unknown_result(self, text):

        return {
            "command": text,
            "intent": "UNKNOWN",
            "target": None
        }
