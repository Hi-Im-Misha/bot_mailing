from settings import TOKEN_BOT_mailling, TOKEN_yabdex_disk, YANDEX_DIR
import telebot
import requests
import json
import os
import time
import threading
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

bot = telebot.TeleBot(TOKEN_BOT_mailling)

YANDEX_HEADERS = {"Authorization": f"OAuth {TOKEN_yabdex_disk}"}

user_progress = {}  # {chat_id: index}
user_threads = {}   # {chat_id: thread_object}

# --------------------- Загрузка постов с Яндекс.Диска ---------------------

def get_yandex_download_url(yandex_path):
    url = "https://cloud-api.yandex.net/v1/disk/resources/download"
    params = {"path": yandex_path}
    response = requests.get(url, headers=YANDEX_HEADERS, params=params)
    if response.status_code == 200:
        return response.json().get("href")
    return None

def load_posts():
    yandex_json_path = f"{YANDEX_DIR}/posts.json"
    url = get_yandex_download_url(yandex_json_path)
    if not url:
        return []
    response = requests.get(url)
    if response.ok:
        try:
            return response.json()
        except:
            print("Ошибка чтения JSON")
    return []

posts = load_posts()

# --------------------- Telegram Logic ---------------------

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id

    if chat_id not in user_progress:
        user_progress[chat_id] = 0
        send_post(chat_id, 0)

        # Поток для отправки следующих постов
        t = threading.Thread(target=send_posts_periodically, args=(chat_id,))
        t.start()
        user_threads[chat_id] = t

def send_posts_periodically(chat_id):
    while True:
        time.sleep(10)
        current_index = user_progress.get(chat_id, 0) + 1
        if current_index < len(posts):
            send_post(chat_id, current_index)
            user_progress[chat_id] = current_index
        else:
            break

def send_post(chat_id, post_index):
    post = posts[post_index]
    photo_paths = post['photos']
    text_path = post['text']
    url = 'https://typerun.top/#rus_basic'

    # Загружаем описание
    if text_path.startswith("disk:/"):
        text = download_text_from_yandex(text_path)
    else:
        text = text_path

    # Загружаем фото с Яндекс.Диска
    local_photo_files = []
    for path in photo_paths:
        local_path = download_file_from_yandex(path)
        if local_path:
            local_photo_files.append(local_path)

    if not local_photo_files:
        bot.send_message(chat_id, "Фотографии не найдены.")
        return

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔗 Перейти на сайт", url=url))

    if len(local_photo_files) == 1:
        with open(local_photo_files[0], 'rb') as photo:
            bot.send_photo(chat_id, photo, caption=text, reply_markup=markup)
    else:
        media = []

        # Первая фотография с описанием
        with open(local_photo_files[0], 'rb') as photo_file:
            media.append(InputMediaPhoto(photo_file.read(), caption=text))

        # Остальные без описания
        for path in local_photo_files[1:]:
            with open(path, 'rb') as photo_file:
                media.append(InputMediaPhoto(photo_file.read()))

        msg_group = bot.send_media_group(chat_id, media)

        # Отправим кнопку отдельно, т.к. inline-кнопки не поддерживаются в media_group
        bot.send_message(chat_id, " ", reply_markup=markup)

    # Удаляем временные файлы
    for path in local_photo_files:
        try:
            os.remove(path)
        except:
            pass







def download_file_from_yandex(disk_path):
    """Скачивает файл с Яндекс.Диска в temp/ и возвращает локальный путь"""
    url = get_yandex_download_url(disk_path)
    if not url:
        print(f"Не удалось получить ссылку на {disk_path}")
        return None

    local_filename = os.path.join("temp", os.path.basename(disk_path))
    os.makedirs("temp", exist_ok=True)

    response = requests.get(url)
    if response.ok:
        with open(local_filename, 'wb') as f:
            f.write(response.content)
        return local_filename
    else:
        print(f"Ошибка загрузки {disk_path}")
        return None


def download_text_from_yandex(disk_path):
    """Загружает текстовый файл с Яндекс.Диска"""
    url = get_yandex_download_url(disk_path)
    if not url:
        print(f"Не удалось получить ссылку на текст: {disk_path}")
        return ""
    
    response = requests.get(url)
    if response.ok:
        return response.text.strip()
    else:
        print(f"Ошибка загрузки текста: {disk_path}")
        return ""



bot.polling(none_stop=True)
