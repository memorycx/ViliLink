"""维修通知的 HTTP 发送。"""

from __future__ import annotations

import requests

from common.config import Settings


class QQNotifier:
    def __init__(self, settings: Settings):
        self._settings = settings

    def send_private(self, text: str) -> bool:
        payload = {
            "user_id": self._settings.report_people_qq,
            "message": text,
        }
        try:
            response = requests.post(
                self._settings.url_send,
                headers=self._settings.headers_send,
                json=payload,
                timeout=self._settings.request_timeout,
            )
        except requests.RequestException:
            return False
        return response.status_code == 200
