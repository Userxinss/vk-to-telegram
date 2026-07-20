import os
import sys
import json
import time
import requests


VK_TOKEN = os.getenv("VK_TOKEN")
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHANNEL = os.getenv("TG_CHANNEL")
GROUP_ID = os.getenv("VK_GROUP_ID", "228742799")

VK_API_VERSION = "5.199"

STATE_FILE = "sent_posts.json"

MEDIA_GROUP_CAPTION_LIMIT = 1024
TEXT_MESSAGE_LIMIT = 4096
MAX_SAVED_POSTS = 100
MAX_MEDIA_GROUP_ITEMS = 10


# =====================
# HTTP
# =====================

def request_with_retry(method, url, retries=3, **kwargs):

    for attempt in range(retries):

        try:
            kwargs.setdefault("timeout", 60)

            return requests.request(
                method,
                url,
                **kwargs
            )

        except requests.RequestException as e:

            print("Ошибка запроса:", e)

            if attempt < retries - 1:
                time.sleep(3)

    raise Exception("Не удалось выполнить запрос")



# =====================
# VK
# =====================

def vk_api(method, params):

    url = f"https://api.vk.com/method/{method}"

    params.update(
        {
            "access_token": VK_TOKEN,
            "v": VK_API_VERSION
        }
    )


    response = request_with_retry(
        "GET",
        url,
        params=params
    )


    data = response.json()


    if "error" in data:

        print(data)

        raise Exception(
            data["error"]["error_msg"]
        )


    return data["response"]




def get_vk_post():

    data = vk_api(
        "wall.get",
        {
            "owner_id": f"-{GROUP_ID}",
            "count": 10
        }
    )


    for post in data["items"]:

        if not post.get("is_pinned"):

            return post


    raise Exception(
        "Пост не найден"
    )



def get_content(post):

    text = post.get(
        "text",
        ""
    )

    attachments = post.get(
        "attachments",
        []
    )


    # если это репост
    if (
        not text
        and not attachments
        and post.get("copy_history")
    ):

        original = post["copy_history"][0]

        text = original.get(
            "text",
            ""
        )

        attachments = original.get(
            "attachments",
            []
        )


    return text, attachments




def get_photos(attachments):

    photos = []


    for item in attachments:

        if item["type"] != "photo":
            continue


        sizes = item["photo"]["sizes"]


        best = max(
            sizes,
            key=lambda x:
            x.get("width",0) *
            x.get("height",0)
        )


        photos.append(
            best["url"]
        )


    return photos




def get_videos(attachments):

    videos = []


    for item in attachments:

        if item["type"] != "video":
            continue


        video = item["video"]


        owner_id = video["owner_id"]
        video_id = video["id"]

        access_key = video.get(
            "access_key"
        )


        video_id_string = (
            f"{owner_id}_{video_id}"
        )


        if access_key:
            video_id_string += (
                f"_{access_key}"
            )


        try:

            result = vk_api(
                "video.get",
                {
                    "videos": video_id_string
                }
            )


            files = result["items"][0]["files"]


            quality = [
                x for x in files
                if x.startswith("mp4_")
            ]


            if quality:

                best = max(
                    quality,
                    key=lambda x:
                    int(x.split("_")[1])
                )


                videos.append(
                    files[best]
                )


        except Exception as e:

            print(
                "Ошибка видео:",
                e
            )


    return videos



# =====================
# MEMORY
# =====================

def load_memory():

    try:

        with open(
            STATE_FILE,
            "r"
        ) as f:

            return json.load(f)


    except:

        return []




def save_memory(posts):

    posts = posts[-MAX_SAVED_POSTS:]


    with open(
        STATE_FILE,
        "w"
    ) as f:

        json.dump(
            posts,
            f
        )




# =====================
# TELEGRAM
# =====================

def build_caption(text):

    if len(text) > MEDIA_GROUP_CAPTION_LIMIT:

        text = (
            text[:MEDIA_GROUP_CAPTION_LIMIT-1]
            + "…"
        )


    return text



def send_media(
    text,
    photos,
    videos
):


    media = []

    files = {}


    for i, photo in enumerate(photos):

        item = {

            "type":"photo",

            "media":photo

        }


        if i == 0:

            item["caption"] = text


        media.append(item)



    for i, video_url in enumerate(videos):

        print(
            "Скачиваю видео..."
        )


        video = request_with_retry(
            "GET",
            video_url
        ).content


        filename = (
            f"video{i}.mp4"
        )


        files[filename] = (

            filename,

            video,

            "video/mp4"

        )


        item = {

            "type":"video",

            "media":
            f"attach://{filename}"

        }


        if not photos and i == 0:

            item["caption"] = text


        media.append(item)



    media = media[:MAX_MEDIA_GROUP_ITEMS]


    url = (
        f"https://api.telegram.org/"
        f"bot{TG_TOKEN}/sendMediaGroup"
    )


    response = request_with_retry(
        "POST",
        url,
        data={
            "chat_id":TG_CHANNEL,
            "media":json.dumps(media)
        },
        files=files
    )


    print(
        response.json()
    )



def send_text(text):

    url = (
        f"https://api.telegram.org/"
        f"bot{TG_TOKEN}/sendMessage"
    )


    requests.post(
        url,
        json={
            "chat_id":TG_CHANNEL,
            "text":text
        }
    )



# =====================
# START
# =====================


def main():

    post = get_vk_post()


    post_id = str(
        post["id"]
    )


    memory = load_memory()


    print(
        "Проверяем пост:",
        post_id
    )


    if post_id in memory:

        print(
            "Пост уже отправлялся"
        )

        return



    text, attachments = get_content(post)


    photos = get_photos(
        attachments
    )


    videos = get_videos(
        attachments
    )



    caption = build_caption(
        text
    )



    if photos or videos:

        send_media(
            caption,
            photos,
            videos
        )

    else:

        send_text(
            caption
        )



    memory.append(
        post_id
    )


    save_memory(
        memory
    )


    print(
        "Пост сохранен:",
        post_id
    )



if __name__ == "__main__":

    main()
