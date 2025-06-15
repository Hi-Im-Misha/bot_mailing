import os
import json
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
from settings import main_token
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaVideo, InputMediaPhoto
from db import init_db, load_sent_posts, add_sent_post, migrate_from_json
import time
import requests


BOT_TOKEN = main_token
POSTS_FILE_PATH = "posts.json"
COUNT_FILE = "count.txt"
USERS_FILE = "users_id.txt"
SHEDULE_FILE_PATH = "shedule.json"
SENT_POSTS_FILE = "sent_posts.json"

bot = telebot.TeleBot(BOT_TOKEN)
scheduler = BackgroundScheduler()
scheduler.start()

conn = init_db()
migrate_from_json(conn, SENT_POSTS_FILE)
sent_posts = load_sent_posts(conn)


@bot.message_handler(commands=['start'])
def handle_start(message):
    user_chat_id = message.chat.id
    username = message.from_user.username or "unknown"

    print(f"Пользователь @{username} подключился. ID: {user_chat_id}")

    if is_new_user(username):
        print(username, "новый пользователь")
        save_user_id(username)
        increment_user_count()
    
    
    elif user_chat_id not in sent_posts:
        print("Создаем список отправленных постов для пользователя")
        sent_posts[user_chat_id] = set()
        send_next_post(user_chat_id)

    else:
        print("Пользователь уже подключился")
        last_post_id = max(sent_posts.get(user_chat_id, [])) if sent_posts.get(user_chat_id) else None
        
        all_post_ids = {post['id'] for post in load_posts()}
        user_sent_ids = sent_posts.get(user_chat_id, set())

        remaining_posts = all_post_ids - user_sent_ids
        if remaining_posts:
            print("Есть новые посты, отправляем следующий")
            send_next_post(user_chat_id)
        else:
            print("Все посты уже отправлены этому пользователю")
            handle_view_post(user_chat_id, last_post_id)





def load_posts():
    if not os.path.exists(POSTS_FILE_PATH):
        return []
    with open(POSTS_FILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ----------------показ поста-------------------
def handle_view_post(chat_id, post_id):
    posts = load_posts_for_view_post()
    if posts is None:
        bot.send_message(chat_id, "Ошибка при загрузке постов.")
        return False

    post = get_post_by_id(posts, post_id)
    if not post:
        print("Пост не найден")
        return False

    media_items, voice_file, video_note_file, open_files = prepare_media(post)
    description = post.get("description", "")
    button = post.get("button", [])
    markup = create_inline_markup(post)

    try:
        send_post_content(chat_id, description, markup, media_items, voice_file, video_note_file, post_id, button)
        return True
    except Exception as e:
        print(f"Ошибка при отправке поста: {e}")
        return False
    finally:
        for f in open_files:
            f.close()



def load_posts_for_view_post():
    if not os.path.exists(POSTS_FILE_PATH):
        print("Файл с постами не найден.")
        return []
    with open(POSTS_FILE_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def get_post_by_id(posts, post_id):
    return next((p for p in posts if p["id"] == post_id), None)


def prepare_media(post):
    media_items = []
    open_files = []

    voice_file = None
    video_note_file = None

    for item in post.get("photos", []):
        media_type = item.get("type")
        path = item.get("path")

        if not os.path.exists(path):
            continue

        file = open(path, "rb")
        open_files.append(file)

        if media_type == "photo":
            media_items.append(("photo", file))
        elif media_type == "video":
            media_items.append(("video", file))
        elif media_type == "voice":
            voice_file = file
        elif media_type == "video_note":
            video_note_file = file
        else:
            file.close()

    return media_items, voice_file, video_note_file, open_files


from telebot import types

def create_inline_markup(post):
    button_data = post.get("button")

    if not button_data:
        return None

    markup = types.InlineKeyboardMarkup()

    # Если это список кнопок
    if isinstance(button_data, list):
        for btn in button_data:
            if "text" in btn and "url" in btn:
                markup.add(types.InlineKeyboardButton(text=btn["text"], url=btn["url"]))

    # Если это один объект-кнопка
    elif isinstance(button_data, dict):
        if "text" in button_data and "url" in button_data:
            markup.add(types.InlineKeyboardButton(text=button_data["text"], url=button_data["url"]))

    # Если ничего не добавилось
    if not markup.keyboard:
        return None

    return markup

def send_post_content(chat_id, description, markup, media_items, voice_file, video_note_file, post_id, button):
    sent_any = False

    # === Если есть video_note ===
    if video_note_file:
        print("Отправляем video_note")
        bot.send_video_note(chat_id, video_note_file)
        sent_any = True

        # Если есть кнопки, но нет description — добавим сообщение "👇 Подробнее:"
        if button and not description:
            print("Есть кнопки, но нет описания — добавляем '👇 Подробнее:'")
            bot.send_message(chat_id, "👇 Подробнее:", reply_markup=markup)

        elif button and description:
            print("Есть кнопки и описание — добавляем его после video_note")
            bot.send_message(chat_id, description, reply_markup=markup)

        # Если есть description, то добавим его (с кнопками)
        elif description:
            print("Есть описание — добавляем его после video_note")
            bot.send_message(chat_id, description, reply_markup=markup)



    # === Если есть 1 медиафайл (фото или видео) ===
    if len(media_items) == 1:
        print("len(media_items) == 1")
        media_type, media_file = media_items[0]
        if media_type == "photo":
            bot.send_photo(chat_id, media_file, caption=description, reply_markup=markup)
        elif media_type == "video":
            bot.send_video(chat_id, media_file, caption=description, reply_markup=markup)
        sent_any = True

    # === Если есть несколько медиафайлов ===
    if len(media_items) > 1:
        print("len(media_items) > 1")
        media_group = []
        for m_type, f in media_items:
            if m_type == "photo":
                media_group.append(InputMediaPhoto(f))
            elif m_type == "video":
                media_group.append(InputMediaVideo(f))
        bot.send_media_group(chat_id, media_group)
        sent_any = True

        if description or markup:
            bot.send_message(chat_id, description, reply_markup=markup)

    # === Если есть голосовое сообщение ===
    if voice_file:
        print("voice_file")
        bot.send_voice(chat_id, voice_file)
        sent_any = True

    # === Если ничего не отправилось — сообщаем об этом ===
    if not sent_any and not description and not markup:
        print("Ни один файл не прошёл фильтр.")

# -------------------отправка постов------------------------
def send_next_post(chat_id):
    print(f"▶️ Запускаем для {chat_id}")
    global sent_posts
    posts = load_posts_for_view_post()
    if not posts or chat_id is None:
        return
    
    if chat_id not in sent_posts:
        sent_posts[chat_id] = set()

    for post in posts:
        post_id = post["id"]
        if post_id not in sent_posts[chat_id]:
            was_sent = handle_view_post(chat_id, post_id)
            if was_sent:
                sent_posts[chat_id].add(post_id)
                add_sent_post(conn, chat_id, post_id)
            break


    hours, minutes = load_schedule_times()
    
    if scheduler.get_job(f'post_job_{chat_id}'):
        scheduler.remove_job(f'post_job_{chat_id}')
    
    scheduler.add_job(send_next_post, 'interval', hours=hours, minutes=minutes, id=f'post_job_{chat_id}', args=[chat_id])


def load_schedule_times():
    with open(SHEDULE_FILE_PATH, 'r', encoding='utf-8') as file:
        data = json.load(file)
    interval_str = data["interval"]
    hours, minutes = map(int, interval_str.split(":"))
    return hours, minutes



def increment_user_count():
    count = get_user_count() + 1
    with open(COUNT_FILE, "w") as f:
        f.write(str(count))


def is_new_user(username):
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = f.read().splitlines()
        return f"@{username}" not in users
    except FileNotFoundError:
        return True


def save_user_id(user_id):
    with open(USERS_FILE, "a") as f:
        f.write(f"@{user_id}\n")

def get_user_count():
    try:
        with open(COUNT_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0



def start_sending_to_existing_users():
    for chat_id in sent_posts.keys():
        print(f"▶️ start_sending_to_existing_users {chat_id}")
        send_next_post(chat_id)

start_sending_to_existing_users()

while True:
    try:
        bot.polling(none_stop=True)
    except requests.exceptions.ReadTimeout:
        print("Read timeout, retrying...")
        time.sleep(5)
    except Exception as e:
        print(f"Polling failed: {e}")
        time.sleep(5)