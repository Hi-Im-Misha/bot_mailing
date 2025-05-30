import os
import json
import telebot
from telebot.types import InputMediaPhoto
from apscheduler.schedulers.background import BackgroundScheduler
from settings import main_token
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton



BOT_TOKEN = main_token
POSTS_FILE_PATH = "posts.json"
COUNT_FILE = "count.txt"
USERS_FILE = "users_id.txt"

bot = telebot.TeleBot(BOT_TOKEN)
scheduler = BackgroundScheduler()
scheduler.start()

user_chat_id = None
sent_posts = {}

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_chat_id = message.chat.id
    username = message.from_user.username or "unknown"

    print(f"Пользователь @{username} подключился. ID: {user_chat_id}")

    if is_new_user(username):
        save_user_id(username)
        increment_user_count()
        sent_posts[user_chat_id] = set()
        send_next_post(user_chat_id)
    else:
        last_post_id = max(sent_posts.get(user_chat_id, [])) if sent_posts.get(user_chat_id) else None
        if last_post_id:
            handle_view_post(user_chat_id, last_post_id)







def load_posts():
    if not os.path.exists(POSTS_FILE_PATH):
        return []
    with open(POSTS_FILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def handle_view_post(chat_id, post_id):
    if not os.path.exists(POSTS_FILE_PATH):
        print("Файл с постами не найден.")
        return

    with open(POSTS_FILE_PATH, "r", encoding="utf-8") as f:
        try:
            posts = json.load(f)
        except json.JSONDecodeError:
            print("Невалидный файл с постами.")
            return

    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        print("Пост не найден.")
        return

    media_group = []
    photo_files = []

    for photo_path in post["photos"]:
        if os.path.exists(photo_path):
            photo_file = open(photo_path, "rb")
            photo_files.append(photo_file)
            media_group.append(InputMediaPhoto(photo_file))

    markup = None
    if "button" in post and post["button"]:
        button = post["button"]
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(text=button["text"], url=button["url"]))

    try:
        if media_group:
            if len(media_group) == 1:
                bot.send_photo(chat_id, media_group[0].media, caption=post["description"], reply_markup=markup)
            else:
                if markup:
                    bot.send_media_group(chat_id, media_group)
                    bot.send_message(chat_id, post["description"], reply_markup=markup)
                else:
                    media_group[0].caption = post["description"]
                    bot.send_media_group(chat_id, media_group)
        else:
            print("Пост не содержит фотографий.")
    finally:
        for f in photo_files:
            f.close()



post_index = 0
def send_next_post(chat_id):
    global scheduler
    posts = load_posts()
    
    if not posts or chat_id is None:
        return
    
    for post in posts:
        post_id = post["id"]
        
        if post_id not in sent_posts[chat_id]:
            handle_view_post(chat_id, post_id)
            sent_posts[chat_id].add(post_id)
            break

    hours, minutes = load_schedule_times()
    
    if scheduler.get_job(f'post_job_{chat_id}'):
        scheduler.remove_job(f'post_job_{chat_id}')
    
    scheduler.add_job(send_next_post, 'interval', hours=hours, minutes=minutes, id=f'post_job_{chat_id}', args=[chat_id])



def load_schedule_times():
    print(load_schedule_times)
    with open('shedule.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    interval_str = data["interval"]
    print(interval_str)
    hours, minutes = map(int, interval_str.split(":"))
    return hours, minutes



def increment_user_count():
    print(increment_user_count)
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
    print(save_user_id)
    with open(USERS_FILE, "a") as f:
        f.write(f"@{user_id}\n")

def get_user_count():
    print(get_user_count)
    try:
        with open(COUNT_FILE, "r") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0

bot.polling(none_stop=True)