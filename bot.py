"""
Бридж VK -> Telegram: берёт последний обычный (не закреплённый) пост
из паблика VK и репостит его в телеграм-канал.

Требуемые переменные окружения:
    VK_TOKEN     - токен доступа VK API
    TG_TOKEN     - токен телеграм-бота
    TG_CHANNEL   - id или @username телеграм-канала
    VK_GROUP_ID  - id группы VK (без минуса), опционально,
                   по умолчанию 228742799
"""

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

# Абсолютный путь рядом со скриптом - чтобы файл со state создавался
# в одном и том же месте независимо от того, откуда запущен скрипт
# (важно для GitHub Actions, где cwd = корень репозитория)
LAST_POST_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "last_post.txt"
)

# Лимиты Telegram Bot API
MEDIA_GROUP_CAPTION_LIMIT = 1024
TEXT_MESSAGE_LIMIT = 4096
MAX_MEDIA_GROUP_ITEMS = 10


# =====================
# ВСПОМОГАТЕЛЬНОЕ
# =====================

def request_with_retry(method, url, retries=3, backoff=2, **kwargs):
    """HTTP-запрос с повторными попытками при сетевых сбоях/таймаутах."""
    last_exc = None

    for attempt in range(1, retries + 1):
        try:
            kwargs.setdefault("timeout", 30)
            return requests.request(method, url, **kwargs)
        except requests.RequestException as e:
            last_exc = e
            print(f"Попытка {attempt}/{retries} не удалась ({url}): {e}")
            if attempt < retries:
                time.sleep(backoff * attempt)

    raise last_exc


def check_tg_response(response):
    """Проверяет, что Telegram реально принял сообщение (ok: true)."""
    try:
        data = response.json()
    except ValueError:
        print("Telegram вернул не-JSON ответ:", response.text)
        return False

    print(data)

    if not data.get("ok"):
        print("Telegram API вернул ошибку:", data)
        return False

    return True


# =====================
# VK API
# =====================

def vk_api(method_name, params):
    url = f"https://api.vk.com/method/{method_name}"
    params = {**params, "access_token": VK_TOKEN, "v": VK_API_VERSION}

    response = request_with_retry("GET", url, params=params)
    data = response.json()

    if "error" in data:
        print(data)
        raise Exception(
            f"Ошибка VK API ({method_name}): {data['error'].get('error_msg')}"
        )

    return data["response"]


def get_vk_post():
    """Возвращает последний НЕ закреплённый пост."""
    response = vk_api("wall.get", {"owner_id": f"-{GROUP_ID}", "count": 2})
    items = response.get("items", [])

    if not items:
        raise Exception("Постов не найдено")

    for item in items:
        if not item.get("is_pinned"):
            return item

    # если все полученные посты закреплены (маловероятно) - берём первый
    return items[0]


def resolve_post_content(post):
    """
    Возвращает (text, attachments) с учётом репостов.
    Если у поста нет собственного текста/вложений, но есть copy_history
    (то есть это репост чужой записи), берём данные оттуда.
    """
    text = post.get("text", "")
    attachments = post.get("attachments", [])

    if not text and not attachments and post.get("copy_history"):
        original = post["copy_history"][0]
        text = original.get("text", "")
        attachments = original.get("attachments", [])

    return text, attachments


def get_photos(attachments):
    """Возвращает URL самого большого доступного размера для каждого фото."""
    photos = []

    for item in attachments:
        if item["type"] != "photo":
            continue

        sizes = item["photo"].get("sizes", [])
        if not sizes:
            continue

        best = max(sizes, key=lambda s: s.get("width", 0) * s.get("height", 0))
        photos.append(best["url"])

    return photos


def get_videos(attachments):
    """Возвращает прямые mp4-ссылки на ВСЕ видео поста в лучшем качестве."""
    video_urls = []

    for item in attachments:
        if item["type"] != "video":
            continue

        video = item["video"]
        owner_id = video["owner_id"]
        video_id = video["id"]
        access_key = video.get("access_key")

        videos_param = f"{owner_id}_{video_id}"
        if access_key:
            videos_param += f"_{access_key}"

        try:
            response = vk_api("video.get", {"videos": videos_param})
            files = response["items"][0]["files"]
        except Exception as e:
            print("Ошибка получения видео:", e)
            continue

        quality_keys = [k for k in files if k.startswith("mp4_")]
        if not quality_keys:
            continue

        def quality_number(key):
            try:
                return int(key.split("_")[1])
            except (IndexError, ValueError):
                return 0

        best_key = max(quality_keys, key=quality_number)
        video_urls.append(files[best_key])

    return video_urls


# =====================
# ПОДПИСЬ
# =====================

def build_caption(text, post_url, limit):
    """Собирает подпись и обрезает её под лимит Telegram, добавляя ссылку."""
    prefix = "🏀 AP Basketball\n\n"
    suffix = f"\n\n🔗 {post_url}"
    max_text_len = limit - len(prefix) - len(suffix)

    if max_text_len < 0:
        return (prefix + suffix)[:limit]

    if len(text) > max_text_len:
        text = text[: max(max_text_len - 1, 0)].rstrip() + "…"

    return prefix + text + suffix


# =====================
# TELEGRAM
# =====================

def send_text(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    response = request_with_retry(
        "POST", url, json={"chat_id": TG_CHANNEL, "text": text}
    )
    return check_tg_response(response)


def send_single_photo(caption, photo_url):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
    response = request_with_retry(
        "POST",
        url,
        data={"chat_id": TG_CHANNEL, "photo": photo_url, "caption": caption},
    )
    return check_tg_response(response)


def send_single_video(caption, video_url):
    print("Скачиваю видео...")
    video_bytes = request_with_retry("GET", video_url).content

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendVideo"
    response = request_with_retry(
        "POST",
        url,
        data={"chat_id": TG_CHANNEL, "caption": caption},
        files={"video": ("video.mp4", video_bytes, "video/mp4")},
    )
    return check_tg_response(response)


def send_media_group(caption, photos, videos):
    """
    Отправляет альбом фото/видео.
    Telegram требует от 2 до 10 элементов в sendMediaGroup, поэтому:
      - 0 элементов сюда попасть не должно (проверяется в main)
      - 1 элемент отправляем через sendPhoto/sendVideo
      - 2-10 элементов - обычный sendMediaGroup
      - больше 10 - обрезаем (ограничение самого Telegram)
    """
    total_items = len(photos) + len(videos)

    if total_items == 0:
        return False

    if total_items == 1:
        if photos:
            return send_single_photo(caption, photos[0])
        return send_single_video(caption, videos[0])

    photos = photos[:MAX_MEDIA_GROUP_ITEMS]
    remaining_slots = MAX_MEDIA_GROUP_ITEMS - len(photos)
    videos = videos[:remaining_slots] if remaining_slots > 0 else []

    media = []
    files = {}

    for index, photo_url in enumerate(photos):
        item = {"type": "photo", "media": photo_url}
        if index == 0:
            item["caption"] = caption
        media.append(item)

    for v_index, video_url in enumerate(videos):
        print("Скачиваю видео...")
        video_bytes = request_with_retry("GET", video_url).content

        file_key = f"video{v_index}.mp4"
        files[file_key] = (file_key, video_bytes, "video/mp4")

        item = {"type": "video", "media": f"attach://{file_key}"}
        if not photos and v_index == 0:
            item["caption"] = caption
        media.append(item)

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMediaGroup"
    response = request_with_retry(
        "POST",
        url,
        data={"chat_id": TG_CHANNEL, "media": json.dumps(media)},
        files=files if files else None,
    )

    return check_tg_response(response)


# =====================
# ХРАНЕНИЕ ID ПОСЛЕДНЕГО ПОСТА
# =====================

def get_last_post_id():
    try:
        with open(LAST_POST_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def save_last_post_id(post_id):
    """Атомарная запись: сначала во временный файл, потом переименование."""
    tmp_path = LAST_POST_FILE + ".tmp"

    with open(tmp_path, "w") as f:
        f.write(str(post_id))

    os.replace(tmp_path, LAST_POST_FILE)


# =====================
# ОСНОВНАЯ ЛОГИКА
# =====================

def main():
    missing = [
        name
        for name, value in [
            ("VK_TOKEN", VK_TOKEN),
            ("TG_TOKEN", TG_TOKEN),
            ("TG_CHANNEL", TG_CHANNEL),
        ]
        if not value
    ]
    if missing:
        raise Exception(f"Не заданы переменные окружения: {', '.join(missing)}")

    post = get_vk_post()
    post_id = str(post["id"])
    last_id = get_last_post_id()

    if post_id == last_id:
        print("Пост уже отправлялся")
        return

    text, attachments = resolve_post_content(post)
    post_url = f"https://vk.com/wall-{GROUP_ID}_{post_id}"

    photos = get_photos(attachments)
    videos = get_videos(attachments)

    if photos or videos:
        caption = build_caption(text, post_url, MEDIA_GROUP_CAPTION_LIMIT)
        success = send_media_group(caption, photos, videos)
    else:
        caption = build_caption(text, post_url, TEXT_MESSAGE_LIMIT)
        success = send_text(caption)

    # Сохраняем id только при успешной отправке - иначе при следующем
    # запуске пост будет считаться отправленным и потеряется навсегда
    if success:
        save_last_post_id(post_id)
    else:
        print("Отправка не удалась, id поста не сохранён - попробуем снова позже")
        # ненулевой код возврата - чтобы GitHub Actions пометил ран как failed
        # и стало заметно, что что-то пошло не так (а не тихо потерялось)
        sys.exit(1)


if __name__ == "__main__":
    main()
