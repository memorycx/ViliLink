import requests

from common.Config import config

URL_SEND = config.URL_SEND
HEADERS = config.HEADERS_SEND
REPORT_PEOPLE_QQ = config.REPORT_PEOPLE_QQ


def send_message(text):
    data = {
        "user_id": REPORT_PEOPLE_QQ,
        "message": text
    }

    res = requests.post(URL_SEND, headers=HEADERS, json=data)

    return res.status_code

