import os
import json
import telebot
from apscheduler.schedulers.background import BackgroundScheduler
from settings import main_token
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaVideo, InputMediaPhoto


BOT_TOKEN = main_token
POSTS_FILE_PATH = "posts.json"
COUNT_FILE = "count.txt"
USERS_FILE = "users_id.txt"
SHEDULE_FILE_PATH = "shedule.json"
SENT_POSTS_FILE = "sent_posts.json"


bot = telebot.TeleBot(BOT_TOKEN)
scheduler = BackgroundScheduler()
scheduler.start()

user_chat_id = None

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_chat_id = message.chat.id
    username = message.from_user.username or "unknown"

    print(f"Пользователь @{username} подключился. ID: {user_chat_id}")

    if is_new_user(username):
        save_user_id(username)
        increment_user_count()
    
    
    elif user_chat_id not in sent_posts:
        print("Создаем список отправленных постов для пользователя")
        sent_posts[user_chat_id] = set()
        send_next_post(user_chat_id)

    else:
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
    markup = create_inline_markup(post)

    try:
        send_post_content(chat_id, description, markup, media_items, voice_file, video_note_file)
        return True
    except Exception as e:
        print(f"Ошибка при отправке поста: {e}")
        return False
    finally:
        for f in open_files:
            f.close()


def load_posts_for_view_post():
    print("load_posts_for_view_post")
    if not os.path.exists(POSTS_FILE_PATH):
        print("Файл с постами не найден.")
        return []
    with open(POSTS_FILE_PATH, "r", encoding="utf-8") as f:
        try:
            print("json.load(f)")
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


def create_inline_markup(post):
    if "button" in post and post["button"] and post["button"].get("text") != "-":
        button = post["button"]
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(text=button["text"], url=button["url"]))
        return markup
    return None



def send_post_content(chat_id, description, markup, media_items, voice_file, video_note_file):
    sent_any = False

    if video_note_file:
        bot.send_video_note(chat_id, video_note_file)
        sent_any = True

    if len(media_items) == 1:
        media_type, media_file = media_items[0]
        if media_type == "photo":
            bot.send_photo(chat_id, media_file, caption=description, reply_markup=markup)
        elif media_type == "video":
            bot.send_video(chat_id, media_file, caption=description, reply_markup=markup)
        sent_any = True

    elif len(media_items) > 1:
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

    if voice_file:
        bot.send_voice(chat_id, voice_file)
        sent_any = True

    # В случае, если был только video_note и при этом есть описание или кнопка
    if not media_items and not voice_file and video_note_file and (description or markup):
        bot.send_message(chat_id, description, reply_markup=markup)

    # Если вообще ничего не отправилось
    if not sent_any and not description and not markup:
        print("Ни один файл не прошёл фильтр.")




# -------------------отправка постов------------------------
def send_next_post(chat_id):
    print("send_next_post")
    global sent_posts
    posts = load_posts_for_view_post()
    print("posts", posts)
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
                save_sent_posts()
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




def load_sent_posts():
    if os.path.exists(SENT_POSTS_FILE):
        with open(SENT_POSTS_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return {int(k): set(v) for k, v in data.items()}
            except json.JSONDecodeError:
                return {}
    return {}

def save_sent_posts():
    with open(SENT_POSTS_FILE, "w", encoding="utf-8") as f:
        json.dump({str(k): list(v) for k, v in sent_posts.items()}, f, ensure_ascii=False, indent=2)


sent_posts = load_sent_posts() 
bot.polling(none_stop=True)