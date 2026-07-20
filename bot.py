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

    if "error" in data:
        print(data)
        raise Exception("Ошибка VK API")

    return data["response"]["items"][1]


def get_photos(post):
    photos = []

    if "attachments" in post:
        for item in post["attachments"]:
            if item["type"] == "photo":
                sizes = item["photo"]["sizes"]
                photos.append(sizes[-1]["url"])

    return photos


def get_video(post):
    if "attachments" in post:
        for item in post["attachments"]:
            if item["type"] == "video":

                video = item["video"]

                owner_id = video["owner_id"]
                video_id = video["id"]

                return f"https://vk.com/video{owner_id}_{video_id}"

    return None


def send_to_telegram(text, photos=None, video=None):

    # Если есть фотографии
    if photos:

        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMediaGroup"

        media = []

        for i, photo in enumerate(photos):

            item = {
                "type": "photo",
                "media": photo
            }

            # текст только на первой фотографии
            if i == 0:
                caption = text

                if video:
                    caption += "\n\n🎥 Видео:\n" + video

                item["caption"] = caption

            media.append(item)


        requests.post(url, json={
            "chat_id": TG_CHANNEL,
            "media": media
        })


    # Если только видео
    elif video:

        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"

        requests.post(url, json={
            "chat_id": TG_CHANNEL,
            "text": text + "\n\n🎥 Видео:\n" + video
        })


    # Только текст
    else:

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


# ==========================
# Основная логика
# ==========================


post = get_vk_post()

post_id = str(post["id"])

last_id = get_last_post_id()


if post_id != last_id:

    text = post.get("text", "")

    photos = get_photos(post)

    video = get_video(post)


    send_to_telegram(
        "🏀 AP Basketball\n\n" + text,
        photos,
        video
    )


    save_last_post_id(post_id)


else:

    print("Пост уже отправлялся")
