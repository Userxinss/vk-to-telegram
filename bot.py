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
        "count": 1,
        "access_token": VK_TOKEN,
        "v": "5.199"
    }

    data = requests.get(url, params=params).json()

    if "error" in data:
        print(data)
        raise Exception("Ошибка VK API")

    # [0] закрепленный, [1] последний обычный
    return data["response"]["items"][0]


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
            print("ATTACHMENT:")
            print(item)

            if item["type"] == "video":
                print("НАШЕЛ ВИДЕО")
                return "VIDEO_FOUND"

    return None


def send_video_to_telegram(text, video_url):

    print("Скачиваю видео...")

    video_data = requests.get(video_url).content

    print("Отправляю видео в Telegram...")

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendVideo"

    files = {
        "video": (
            "video.mp4",
            video_data,
            "video/mp4"
        )
    }

    data = {
        "chat_id": TG_CHANNEL,
        "caption": text
    }

    response = requests.post(
        url,
        files=files,
        data=data
    )

    print(response.json())


def send_to_telegram(text, photos=None):

    if photos:

        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMediaGroup"

        media = []

        for i, photo in enumerate(photos):

            item = {
                "type": "photo",
                "media": photo
            }

            if i == 0:
                item["caption"] = text

            media.append(item)


        requests.post(url, json={
            "chat_id": TG_CHANNEL,
            "media": media
        })


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

    caption = "🏀 AP Basketball\n\n" + text

    photos = get_photos(post)

    video = get_video(post)


    if video:

        send_video_to_telegram(
            caption,
            video
        )

    elif photos:

        send_to_telegram(
            caption,
            photos
        )

    else:

        send_to_telegram(
            caption
        )


    save_last_post_id(post_id)


else:

    print("Пост уже отправлялся")
