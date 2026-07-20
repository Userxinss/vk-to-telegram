import os
import requests

VK_TOKEN = os.getenv("VK_TOKEN")
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHANNEL = os.getenv("TG_CHANNEL")

GROUP_ID = "228742799"

def get_vk_post():
    url = "https://api.vk.com/method/wall.get"

    params = {
        "owner_id": f"-{GROUP_ID}",
        "count": 2,
        "access_token": VK_TOKEN,
        "v": "5.199"
    }

    response = requests.get(url, params=params)
    data = response.json()

    print(data)

    return data["response"]["items"][1]


def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"

    requests.post(url, json={
        "chat_id": TG_CHANNEL,
        "text": text
    })


post = get_vk_post()

text = post.get("text", "")

if text:
    send_to_telegram(
        "🏀 Новый пост из VK:\n\n" + text
    )
