import os
import json
import telebot
from telebot.types import InputMediaPhoto
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from settings import main_token

BOT_TOKEN = main_token
POSTS_FILE = r"C:\mylife\Git_project\bot_mailing\posts.json"

bot = telebot.TeleBot(BOT_TOKEN)
scheduler = BackgroundScheduler()
scheduler.start()

user_chat_id = None

def load_posts():
    if not os.path.exists(POSTS_FILE):
        return []
    with open(POSTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

def send_post(chat_id, post):
    media_group = []
    photo_files = []

    # Создание клавиатуры с кнопкой
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Перейти на сайт", url="https://typerun.top/#rus_basic"))

    for photo_path in post.get("photos", []):
        if os.path.exists(photo_path):
            f = open(photo_path, "rb")
            photo_files.append(f)
            media_group.append(InputMediaPhoto(f, caption=post["description"]))

    try:
        if len(media_group) == 1:
            # Отправляем единственное фото с кнопкой
            bot.send_photo(chat_id, photo_files[0], caption=post["description"], reply_markup=keyboard)
        else:
            # Отправляем группу фото
            bot.send_media_group(chat_id, media_group)
            # Отдельно прикрепляем кнопку к описанию
            bot.send_message(chat_id, post["description"], reply_markup=keyboard)
    finally:
        for f in photo_files:
            f.close()





post_index = 0
def send_next_post():
    global post_index, user_chat_id
    if user_chat_id is None:
        return
    posts = load_posts()
    if not posts:
        return
    send_post(user_chat_id, posts[post_index % len(posts)])
    post_index += 1

@bot.message_handler(commands=['start'])
def handle_start(message):
    global user_chat_id
    user_chat_id = message.chat.id
    bot.send_message(user_chat_id, "Бот запущен! Посты будут приходить по расписанию.")


# def shedule():
    scheduler.add_job(send_next_post, 'cron', hour='12-23', minute=0)
scheduler.add_job(send_next_post, 'interval', seconds=10)

bot.polling(none_stop=True)