import os
import requests

VK_TOKEN = os.getenv("VK_TOKEN")
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHANNEL = os.getenv("TG_CHANNEL")

print("Бот запущен")

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TG_CHANNEL,
        "text": text
    })

send_to_telegram("✅ VK → Telegram подключение работает!")
