import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from settings import TOKEN_BOT, TOKEN_yabdex_disk
import requests
from datetime import datetime
import os
from telebot.types import InputMediaPhoto
import json


bot = telebot.TeleBot(TOKEN_BOT)

YANDEX_OAUTH_TOKEN = TOKEN_yabdex_disk
YANDEX_HEADERS = {"Authorization": f"OAuth {YANDEX_OAUTH_TOKEN}"}
YANDEX_DIR = "disk:/bot_tg"


user_data = {}

@bot.message_handler(commands=['start'])
def handle_start(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("➕Создать пост", callback_data="create_post"),
        InlineKeyboardButton("🗂Редактировать пост", callback_data="show_posts")
    )
    bot.send_message(message.chat.id, START_DESCRIPTION, reply_markup=markup)


START_DESCRIPTION = (
    "👋 Добро пожаловать! Этот бот поможет вам создавать и управлять постами.\n\n"
    "📝 Возможности:\n"
    "• Создать пост (фото + описание + ссылка)\n"
    "• Сохраняет все данные на Яндекс.Диске\n"
    "• Просматривать созданные посты\n"
    "• Удалять посты с полным удалением файлов\n\n"

    "🔧 Кнопки:\n"
    "• ➕Создать пост - Предложит отправить фотографии и описание после сохронит данные в яндекс диск в \nhttps://disk.yandex.ru/client/disk/bot_tg\n\n"
    "•  Редактировать пост - При нажатии покажет кнопки с уже созданными постами а так же с кнопкой удалить\n\n"
    "❓ Просто следуйте инструкциям после команды!"
)


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "create_post":
        handle_create_post(call)
    elif call.data == "show_posts":
        handle_show_posts(call)
    elif call.data.startswith("view_post_"):
        post_id = int(call.data.split("_")[-1])
        handle_view_post(call.message.chat.id, post_id)
    elif call.data.startswith("delete_post_"):
        post_id = int(call.data.split("_")[-1])
        handle_delete_post(call.message.chat.id, post_id)


def handle_create_post(call):
    user_id = call.from_user.id
    user_data[user_id] = {
        "post_mode": True,
        "media_group": [],
        "media_group_ids": set()
    }
    bot.send_message(call.message.chat.id, "Отправьте одно или несколько фото для поста")


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id

    if not is_in_post_mode(user_id):
        return

    file_id = message.photo[-1].file_id
    user_data[user_id]["media_group"].append(file_id)

    mgid = message.media_group_id
    if mgid:
        if mgid not in user_data[user_id]["media_group_ids"]:
            user_data[user_id]["media_group_ids"].add(mgid)
            send_photo_hint(message.chat.id)
    else:
        send_photo_hint(message.chat.id)


@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id

    if not is_in_post_mode(user_id):
        return

    text_message = message.text
    media_group = user_data[user_id]["media_group"]

    if media_group:
        send_media_and_text(message.chat.id, media_group, text_message)
    else:
        bot.send_message(message.chat.id, "Вы не отправили ни одной фотографии.")

    user_data.pop(user_id)



def is_in_post_mode(user_id):
    return user_id in user_data and user_data[user_id].get("post_mode", False)

def send_photo_hint(chat_id):
    bot.send_message(chat_id, "После отправки всех фото отправьте текст поста.")










# --------------------------------Show posts-------------------------------------
def handle_show_posts(call):
    posts = load_posts_from_yandex()

    if not posts:
        bot.send_message(call.message.chat.id, "Нет сохранённых постов.")
        return

    markup = InlineKeyboardMarkup()
    for post in posts:
        btn_view = InlineKeyboardButton(f"Пост #{post['id']}", callback_data=f"view_post_{post['id']}")
        btn_delete = InlineKeyboardButton(f"🗑 Удалить #{post['id']}", callback_data=f"delete_post_{post['id']}")
        markup.add(btn_view, btn_delete)

    bot.send_message(call.message.chat.id, "Выберите пост для просмотра или удаления:", reply_markup=markup)




def load_posts_from_yandex():
    yandex_json_path = f"{YANDEX_DIR}/posts.json"
    download_url = get_yandex_download_url(yandex_json_path)
    if not download_url:
        return []

    response = requests.get(download_url)
    if response.ok:
        try:
            return response.json()
        except json.JSONDecodeError:
            print("Ошибка разбора posts.json")
            return []
    return []

def handle_view_post(chat_id, post_id):
    posts = load_posts_from_yandex()
    post = next((p for p in posts if p["id"] == post_id), None)

    if not post:
        bot.send_message(chat_id, "Пост не найден.")
        return

    # Скачиваем текст
   # Скачиваем текст
    text = "Описание недоступно"
    download_url = get_yandex_download_url(post["text"])
    if download_url:
        response = requests.get(download_url)
        if response.ok:
            try:
                text = response.content.decode('utf-8', errors='ignore')  # <<-- вот здесь!
            except Exception as e:
                print(f"Ошибка декодирования текста: {e}")


    # Скачиваем и отправляем фото
    media = []
    for url_path in post["photos"]:
        file_url = get_yandex_download_url(url_path)
        if file_url:
            file_bytes = requests.get(file_url).content
            media.append(InputMediaPhoto(file_bytes))

    if media:
        if len(text) <= 1024:
            media[0].caption = text
            bot.send_media_group(chat_id, media)
        else:
            # Отправляем фото без подписи
            bot.send_media_group(chat_id, media)
            # Отдельно отправляем полный текст
            bot.send_message(chat_id, text)
    else:
        bot.send_message(chat_id, text)




# --------------------------------Del posts-------------------------------------

def handle_delete_post(chat_id, post_id):
    posts = load_posts_from_yandex()
    post = next((p for p in posts if p["id"] == post_id), None)

    if not post:
        bot.send_message(chat_id, "Пост не найден.")
        return

    # Удаление фото
    for photo_path in post["photos"]:
        delete_file_from_yandex(photo_path)

    # Удаление текстового файла
    delete_file_from_yandex(post["text"])

    # Обновление posts.json
    posts = [p for p in posts if p["id"] != post_id]

    local_json_path = "posts.json"
    yandex_json_path = f"{YANDEX_DIR}/posts.json"

    with open(local_json_path, 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=4)

    upload_file_to_yandex(local_json_path, yandex_json_path)
    os.remove(local_json_path)

    bot.send_message(chat_id, f"Пост #{post_id} и все связанные файлы удалены.")
def delete_file_from_yandex(yandex_path):
    url = "https://cloud-api.yandex.net/v1/disk/resources"
    params = {"path": yandex_path}
    response = requests.delete(url, headers=YANDEX_HEADERS, params=params)
    if response.status_code == 204:
        print(f"Удалён: {yandex_path}")
    else:
        print(f"Не удалось удалить {yandex_path}: {response.text}")


# --------------------------------YANDEX-------------------------------------
def send_media_and_text(chat_id, media_group, text_message):
    create_yandex_folder()

    local_dir = "temp_post"
    os.makedirs(local_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    text_file_path = os.path.join(local_dir, f"{timestamp}_description.txt")

    photo_paths = []
    for index, file_id in enumerate(media_group):
        file_info = bot.get_file(file_id)
        file_path_on_server = file_info.file_path
        downloaded_file = bot.download_file(file_path_on_server)

        local_photo_path = os.path.join(local_dir, f"{timestamp}_{index}.jpg")
        with open(local_photo_path, 'wb') as f:
            f.write(downloaded_file)
        photo_paths.append(local_photo_path)

    with open(text_file_path, "w", encoding="utf-8") as f:
        f.write(text_message)

    for path in photo_paths:
        upload_file_to_yandex(path, f"{YANDEX_DIR}/{os.path.basename(path)}")
    upload_file_to_yandex(text_file_path, f"{YANDEX_DIR}/{os.path.basename(text_file_path)}")

    save_post_info(photo_paths, text_file_path, timestamp)

    for path in photo_paths + [text_file_path]:
        os.remove(path)




def create_yandex_folder():
    url = "https://cloud-api.yandex.net/v1/disk/resources"
    params = {"path": YANDEX_DIR}
    response = requests.put(url, headers=YANDEX_HEADERS, params=params)
    if response.status_code == 201:
        print("Папка bot_tg создана.")
    elif response.status_code == 409:
        print("Папка уже существует.")
    else:
        print("Ошибка при создании папки:", response.text)


def upload_file_to_yandex(file_path, yandex_path):
    url = "https://cloud-api.yandex.net/v1/disk/resources/upload"
    params = {"path": yandex_path, "overwrite": "true"}
    response = requests.get(url, headers=YANDEX_HEADERS, params=params)
    if "href" in response.json():
        upload_url = response.json()["href"]
        with open(file_path, 'rb') as f:
            upload_response = requests.put(upload_url, files={'file': f})
            if upload_response.status_code == 201:
                print(f"Загружен файл: {yandex_path}")
            else:
                print(f"Ошибка загрузки: {upload_response.text}")
    else:
        print("Не удалось получить ссылку на загрузку:", response.text)




def save_post_info(photo_paths, text_file_path, timestamp):
    local_json_path = "posts.json"
    yandex_json_path = f"{YANDEX_DIR}/posts.json"

    posts = []
    download_url = get_yandex_download_url(yandex_json_path)
    if download_url:
        response = requests.get(download_url)
        if response.ok:
            try:
                posts = response.json()
            except json.JSONDecodeError:
                print("Файл posts.json повреждён или пуст.")
        else:
            print("Не удалось скачать posts.json:", response.text)

    post_entry = {
        "id": posts[-1]["id"] + 1 if posts else 1,
        "photos": [f"{YANDEX_DIR}/{os.path.basename(p)}" for p in photo_paths],
        "text": f"{YANDEX_DIR}/{os.path.basename(text_file_path)}"
    }
    posts.append(post_entry)

    with open(local_json_path, 'w', encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=4)

    upload_file_to_yandex(local_json_path, yandex_json_path)
    os.remove(local_json_path)



def get_yandex_download_url(yandex_path):
    url = "https://cloud-api.yandex.net/v1/disk/resources/download"
    params = {"path": yandex_path}
    response = requests.get(url, headers=YANDEX_HEADERS, params=params)
    if response.status_code == 200:
        return response.json().get("href")
    elif response.status_code == 404:
        print("Файл posts.json не найден на Диске. Будет создан новый.")
        return None
    else:
        print("Ошибка при получении ссылки на скачивание:", response.text)
        return None





bot.polling(none_stop=True)