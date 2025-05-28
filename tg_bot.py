import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from settings import TOKEN_BOT
import requests
from datetime import datetime
import os
from telebot.types import InputMediaPhoto
import json

bot = telebot.TeleBot(TOKEN_BOT)
FILE_PATH = r'C:\mylife\Git_project\bot_mailing\shedule.json'

user_data = {}

@bot.message_handler(commands=['start'])
def handle_start(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("➕Создать пост", callback_data="create_post"),
        InlineKeyboardButton("🗂Редактировать пост", callback_data="show_posts"),
        InlineKeyboardButton("🗓Настроить расписание", callback_data="shedule")
    )
    bot.send_message(message.chat.id, START_DESCRIPTION, reply_markup=markup)


START_DESCRIPTION = (
    "👋 Добро пожаловать! Этот бот поможет вам создавать и управлять постами.\n\n"
    "📝 Возможности:\n"
    "• Создать пост (фото + описание + ссылка)\n"
    "• Просматривать созданные посты\n"
    "• Удалять посты с полным удалением файлов\n"
    "• Настроить расписание постов указав время, интервал и режим\n\n"

    "⏹️ Кнопки:\n"
    "• ➕Создать пост - Предложит отправить фотографии и описание после сохронит данные\n\n"
    "•  🗂Редактировать пост - При нажатии покажет кнопки с уже созданными постами а так же с кнопкой удалить\n\n"
    "•  🗓Настройки расписания - При нажатии покажет кнопки с настройками расписания времени, интервала и режима\n\n"
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
    
    
    elif call.data == "shedule":
        handle_shedule(call)
    elif call.data == 'set_interval':
        ask_for_interval(call)
    # elif call.data == 'select_mode':
    #     select_mode(call)
    # elif call.data == 'one_time':
    #     sever_mode(call)
    # elif call.data == 'continuous':
    #     sever_mode(call)
    elif call.data == 'start_shedule':
        ask_for_start_time(call)

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

    if 'description' not in user_data[user_id]:
        user_data[user_id]['description'] = message.text
        bot.send_message(
            message.chat.id,
            "🔗 Теперь отправьте ссылку для кнопки (например, https://example.com).\nЕсли вы не хотите добавлять кнопку, отправьте `-`."
        )
        return

    elif 'url' not in user_data[user_id]:
        text = message.text.strip()
        if text == "-":
            # Пользователь не хочет кнопку
            user_data[user_id]['url'] = None
            user_data[user_id]['button_text'] = None

            media_group = user_data[user_id].get("media_group", [])
            description = user_data[user_id].get("description", "")

            if media_group:
                save_media_and_text(
                    message.chat.id,
                    media_group,
                    description,
                    None,  # url
                    None   # button_text
                )
            else:
                bot.send_message(message.chat.id, "⚠️ Вы не отправили ни одной фотографии.")

            user_data.pop(user_id, None)
            return
        else:
            user_data[user_id]['url'] = text
            bot.send_message(message.chat.id, "📝 Введите название для кнопки (например, 'Перейти'):")
            return

    elif 'button_text' not in user_data[user_id]:
        user_data[user_id]['button_text'] = message.text

        media_group = user_data[user_id].get("media_group", [])
        description = user_data[user_id].get("description", "")
        url = user_data[user_id].get("url", "")
        button_text = user_data[user_id].get("button_text", "")

        if media_group:
            save_media_and_text(
                message.chat.id,
                media_group,
                description,
                url,
                button_text
            )
        else:
            bot.send_message(message.chat.id, "⚠️ Вы не отправили ни одной фотографии.")

        user_data.pop(user_id, None)






def send_photo_hint(chat_id):
    bot.send_message(chat_id, "После отправки всех фото отправьте текст поста.")

def is_in_post_mode(user_id):
    return user_id in user_data and user_data[user_id].get("post_mode", False)




# --------------------------------Save post-------------------------------------
def save_media_and_text(chat_id, media_group, text_message, url=None, button_text=None):
    posts_file = r"C:\mylife\Git_project\bot_mailing\posts.json"
    media_folder = r"C:\mylife\Git_project\bot_mailing\media"

    if not os.path.exists(media_folder):
        os.makedirs(media_folder)

    if os.path.exists(posts_file):
        with open(posts_file, "r", encoding="utf-8") as f:
            try:
                posts = json.load(f)
            except json.JSONDecodeError:
                posts = []
    else:
        posts = []

    post_id = posts[-1]["id"] + 1 if posts else 1

    saved_photos = []
    for idx, file_id in enumerate(media_group):
        file_info = bot.get_file(file_id)
        file_ext = os.path.splitext(file_info.file_path)[-1] or ".jpg"
        file_name = f"post_{post_id}_{idx + 1}{file_ext}"
        file_path = os.path.join(media_folder, file_name)

        downloaded_file = bot.download_file(file_info.file_path)
        with open(file_path, 'wb') as f:
            f.write(downloaded_file)

        saved_photos.append(file_path.replace("\\", "/"))

    post_data = {
        "id": post_id,
        "photos": saved_photos,
        "description": text_message,
    }

    if url and button_text:
        post_data["button"] = {
            "text": button_text,
            "url": url
        }

    posts.append(post_data)

    with open(posts_file, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=4, ensure_ascii=False)

    bot.send_message(chat_id, f"✅ Пост #{post_id} успешно сохранён!")




# --------------------------------Show posts-------------------------------------
def handle_show_posts(call):
    posts_file = r"C:\mylife\Git_project\bot_mailing\posts.json"

    if not os.path.exists(posts_file):
        bot.send_message(call.message.chat.id, "Нет сохранённых постов.")
        return

    with open(posts_file, "r", encoding="utf-8") as f:
        try:
            posts = json.load(f)
        except json.JSONDecodeError:
            posts = []

    if not posts:
        bot.send_message(call.message.chat.id, "Нет сохранённых постов.")
        return

    markup = InlineKeyboardMarkup(row_width=2)
    for post in posts:
        description_preview = post.get("description", "")[:20] or "Без описания"
        view_button = InlineKeyboardButton(f"👁 {description_preview}", callback_data=f"view_post_{post['id']}")
        delete_button = InlineKeyboardButton(f"❌ Удалить", callback_data=f"delete_post_{post['id']}")
        markup.add(view_button, delete_button)

    bot.send_message(call.message.chat.id, "📋 Список постов:", reply_markup=markup)







def handle_view_post(chat_id, post_id):
    posts_file = r"C:\mylife\Git_project\bot_mailing\posts.json"

    if not os.path.exists(posts_file):
        bot.send_message(chat_id, "Файл с постами не найден.")
        return

    with open(posts_file, "r", encoding="utf-8") as f:
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







# --------------------------------Del posts-------------------------------------

def handle_delete_post(chat_id, post_id):
    posts_file = r"C:\mylife\Git_project\bot_mailing\posts.json"

    if not os.path.exists(posts_file):
        bot.send_message(chat_id, "Файл с постами не найден.")
        return

    with open(posts_file, "r", encoding="utf-8") as f:
        posts = json.load(f)

    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        bot.send_message(chat_id, "Пост не найден.")
        return

    for photo_path in post["photos"]:
        try:
            if os.path.exists(photo_path):
                os.remove(photo_path)
        except Exception as e:
            print(f"Ошибка при удалении файла {photo_path}: {e}")

    posts = [p for p in posts if p["id"] != post_id]

    with open(posts_file, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=4, ensure_ascii=False)

    bot.send_message(chat_id, f"❌ Пост #{post_id} удалён.")







# --------------------------------Shedule-------------------------------------
def handle_shedule(call):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📆 Начало Рассылки", callback_data="start_shedule"),
        InlineKeyboardButton("⏳ Интервал поста", callback_data="set_interval")
        # InlineKeyboardButton("⚙️ Выбор режима", callback_data="select_mode")
    )

    bot.send_message(call.message.chat.id, "Настройки расписания:\n\n• Начало Рассылки - время c которого начнется рассылка\n\n• Интервал поста - интервал между которыми будет приходить пост\n\n• Выбор режима - отвечает за то будут ли посты приходить одноразово или постоянно\n\n\n ", reply_markup=markup)

def ask_for_start_time(call):
    msg = bot.send_message(call.message.chat.id, "✍️ Напишите время c которого начнется рассылка (например: 12:00):")
    bot.register_next_step_handler(msg, save_start_time)      

def ask_for_interval(call):
    msg = bot.send_message(call.message.chat.id, "✍️ Напишите интервал поста например: \n\n• 24:00 (1 день)\n\n• 00:30 (30 минут)\n\n• 00:01 (1 минута)")
    bot.register_next_step_handler(msg, save_interval)


def save_start_time(message):
    start_time = message.text

    try:
        try:
            with open(FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        
        data["start_time"] = start_time

        with open(FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        bot.send_message(message.chat.id, f"✅ Время начала сохранено: {start_time}")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при сохранении: {e}")



def save_interval(message):
    interval = message.text

    try:
        try:
            with open(FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        
        data["interval"] = interval
        with open(FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        bot.send_message(message.chat.id, f"✅ Интервал сохранён: {interval}")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при сохранении: {e}")



# def sever_mode(call):
#     try:
#         try:
#             with open(FILE_PATH, "r", encoding="utf-8") as f:
#                 data = json.load(f)
#         except (FileNotFoundError, json.JSONDecodeError):
#             data = {}
#         data["mode"] = call.data

#         with open(FILE_PATH, "w", encoding="utf-8") as f:
#             json.dump(data, f, indent=4, ensure_ascii=False)

#         bot.send_message(call.message.chat.id, f"✅ Режим сохранён: {call.data}")

#     except Exception as e:
#         bot.send_message(call.message.chat.id, f"❌ Ошибка при сохранении: {e}")


# def select_mode(call):
#     markup = InlineKeyboardMarkup()
#     markup.add(
#         InlineKeyboardButton("1️⃣Получать одноразово", callback_data="one_time"),
#         InlineKeyboardButton("🔂Получать постоянно", callback_data="continuous")
#     )

#     bot.edit_message_text("Выберите режим получения:", call.message.chat.id, call.message.message_id, reply_markup=markup)





bot.polling(none_stop=True)