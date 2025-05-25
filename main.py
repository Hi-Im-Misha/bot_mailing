import telebot
from telebot.types import InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton
import json
import threading
import time
import os

API_TOKEN = '7608329374:AAFa1QF2GpXOWBYCg3KStKw1UIN8caSkNK0'
bot = telebot.TeleBot(API_TOKEN)

# Загружаем посты
with open(r'C:\mylife\Git_project\bot_mailing\post.json', 'r', encoding='utf-8') as f:
    posts = json.load(f)

subscribers = {}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    if chat_id not in subscribers:
        subscribers[chat_id] = 0
    send_post(chat_id, 0)


def send_post(chat_id, post_index):
    if post_index >= len(posts):
        return

    post = posts[post_index]
    photo_paths = post['photos']
    text = post['text']
    url = post['url']

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🔗 Перейти на сайт", url=url))

    if len(photo_paths) == 1:
        photo_path = photo_paths[0]
        if os.path.exists(photo_path):
            with open(photo_path, 'rb') as photo:
                bot.send_photo(chat_id, photo, caption=text, reply_markup=markup)
        else:
            print(f"Файл {photo_path} не найден.")
    
    elif len(photo_paths) > 1:
        print("Медиагруппа")
        media = []
        for path in photo_paths:
            if os.path.exists(path):
                with open(path, 'rb') as photo_file:
                    media.append(InputMediaPhoto(photo_file.read()))
            else:
                print(f"Файл {path} не найден.")
        
        if media:
            bot.send_media_group(chat_id, media)

        bot.send_message(chat_id, text, reply_markup=markup)


def post_scheduler():
    while True:
        time.sleep(10)
        for chat_id, index in list(subscribers.items()):
            next_index = index + 1
            if next_index < len(posts):
                send_post(chat_id, next_index)
                subscribers[chat_id] = next_index

threading.Thread(target=post_scheduler, daemon=True).start()

bot.infinity_polling()