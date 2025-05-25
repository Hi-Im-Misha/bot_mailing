import os
import json
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
from settings import TOKEN_BOT, TOKEN_yabdex_disk

bot = telebot.TeleBot(TOKEN_BOT)

YANDEX_HEADERS = {"Authorization": f"OAuth {TOKEN_yabdex_disk}"}
DISK_JSON_PATH = "disk:/TelegramPosts/posts.json"
DISK_FOLDER = "disk:/TelegramPosts"
LOCAL_JSON = "posts.json"

photo_paths = {}

@bot.message_handler(commands=['start'])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Создать пост", callback_data="create_post"))
    bot.send_message(message.chat.id, "Нажмите кнопку, чтобы создать пост:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "create_post")
def handle_create_post(call):
    bot.send_message(call.message.chat.id, "Отправьте одно или несколько фото для поста.")
    photo_paths[call.message.chat.id] = []
    bot.register_next_step_handler(call.message, handle_photos)

def handle_photos(message):
    if message.photo:
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        file_path = file_info.file_path
        photo_url = f"https://api.telegram.org/file/bot{TOKEN_BOT}/{file_path}"
        photo_name = f"{DISK_FOLDER}/{message.chat.id}_{int(message.date)}.jpg"

        response = requests.get("https://cloud-api.yandex.net/v1/disk/resources/upload", headers=YANDEX_HEADERS, params={
            "path": photo_name,
            "overwrite": "true"
        })

        if response.status_code == 200:
            upload_url = response.json().get("href")
            photo_content = requests.get(photo_url).content
            upload_result = requests.put(upload_url, data=photo_content)

            if upload_result.status_code in [201, 202]:
                photo_paths[message.chat.id].append(photo_name)
                bot.send_message(message.chat.id, "Фото загружено! Можете отправить ещё фото или напишите описание.")
                bot.register_next_step_handler(message, handle_photos)
            else:
                bot.send_message(message.chat.id, "Ошибка при загрузке фото на Диск.")
        else:
            bot.send_message(message.chat.id, "Не удалось получить ссылку для загрузки фото.")
    elif message.text:
        handle_description(message, photo_paths.get(message.chat.id, []))
    else:
        bot.send_message(message.chat.id, "Отправьте фото или текст описания.")
        bot.register_next_step_handler(message, handle_photos)

def handle_description(message, photos):
    description = message.text.strip()
    new_post = {
        "id": int(message.date),
        "photos": photos,
        "text": description,
        "url": "https://example.com"
    }

    json_data = []
    meta_resp = requests.get("https://cloud-api.yandex.net/v1/disk/resources/download", headers=YANDEX_HEADERS, params={
        "path": DISK_JSON_PATH
    })

    if meta_resp.status_code == 200:
        download_link = meta_resp.json().get("href")
        try:
            existing = requests.get(download_link)
            if existing.status_code == 200:
                existing_json = existing.json()
                if isinstance(existing_json, list):
                    json_data = existing_json
        except Exception:
            pass

    json_data.append(new_post)

    with open(LOCAL_JSON, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)

    upload_resp = requests.get("https://cloud-api.yandex.net/v1/disk/resources/upload", headers=YANDEX_HEADERS, params={
        "path": DISK_JSON_PATH,
        "overwrite": "true"
    })

    if upload_resp.status_code == 200:
        upload_link = upload_resp.json().get("href")
        with open(LOCAL_JSON, "rb") as f:
            upload_result = requests.put(upload_link, data=f)

        if upload_result.status_code in [201, 202]:
            bot.send_message(message.chat.id, "Пост успешно сохранён на Яндекс.Диске!")
        else:
            bot.send_message(message.chat.id, f"Ошибка загрузки JSON: {upload_result.status_code}")
    else:
        bot.send_message(message.chat.id, f"Не удалось получить ссылку для загрузки JSON.")

    photo_paths.pop(message.chat.id, None)


bot.polling(none_stop=True)