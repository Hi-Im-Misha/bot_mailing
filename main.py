import os
import json
import telebot
from telebot.types import InputMediaPhoto
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from settings import main_token
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.triggers.cron import CronTrigger



BOT_TOKEN = main_token
POSTS_FILE_PATH = r"C:\mylife\Git_project\bot_mailing\posts.json"

bot = telebot.TeleBot(BOT_TOKEN)
scheduler = BackgroundScheduler()
scheduler.start()

user_chat_id = None
sent_posts = {}

@bot.message_handler(commands=['start'])
def handle_start(message):
    global user_chat_id
    user_chat_id = message.chat.id
    
    if user_chat_id not in sent_posts:
        sent_posts[user_chat_id] = set()
        bot.send_message(user_chat_id, "Вы подписаны на рассылку!")
        send_next_post(user_chat_id) 
    else:
        bot.send_message(user_chat_id, "Вы уже подписаны, посты будут приходить по расписанию.")




def load_posts():
    if not os.path.exists(POSTS_FILE_PATH):
        return []
    with open(POSTS_FILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def handle_view_post(chat_id, post_id):
    if not os.path.exists(POSTS_FILE_PATH):
        bot.send_message(chat_id, "Файл с постами не найден.")
        return

    with open(POSTS_FILE_PATH, "r", encoding="utf-8") as f:
        try:
            posts = json.load(f)
        except json.JSONDecodeError:
            bot.send_message(chat_id, "Ошибка при чтении постов.")
            return

    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        bot.send_message(chat_id, "Пост не найден.")
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
            bot.send_message(chat_id, "Файлы фотографий не найдены.")
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
    with open(r'C:\mylife\Git_project\bot_mailing\shedule.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    interval_str = data["interval"]
    print(interval_str)
    hours, minutes = map(int, interval_str.split(":"))
    return hours, minutes


bot.polling(none_stop=True)