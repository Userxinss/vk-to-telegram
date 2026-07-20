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

    data = requests.get(url, params=params).json()

    return data["response"]["items"][1]


def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"

    requests.post(url, json={
        "chat_id": TG_CHANNEL,
        "text": text
    })


def get_last_post_id():
    try:
        with open("last_post.txt", "r") as f:
            return f.read().strip()
    except:
        return ""


def save_last_post_id(post_id):
    with open("last_post.txt", "w") as f:
        f.write(str(post_id))


post = get_vk_post()

post_id = str(post["id"])

last_id = get_last_post_id()


if post_id != last_id:
    text = post.get("text", "")

    send_to_telegram(
        "🏀 Новый пост из VK:\n\n" + text
    )

    save_last_post_id(post_id)

else:
    print("Пост уже отправлялся")
