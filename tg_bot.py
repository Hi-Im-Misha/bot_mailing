import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from settings import tg_bot_token, ADMIN_ID
import os
import json
import re
from telebot import TeleBot, types


bot = telebot.TeleBot(tg_bot_token)
SHEDULE_FILE_PATH = "shedule.json"
POSTS_FILE_PATH = "posts.json"
media_folder = "media"

user_data = {}

@bot.message_handler(commands=['start'])
def handle_start(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Доступ запрещён.")
        return
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("➕Создать пост", callback_data="create_post"),
        InlineKeyboardButton("🗂Показать / Удалить", callback_data="show_posts"),
        InlineKeyboardButton("🗓Настроить расписание", callback_data="shedule"),
        InlineKeyboardButton("👥Количество пользователей", callback_data="user_count")
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
    "• ➕Создать пост - Предложит отправить фотографии, описание и ссылку после сохронит пост\n\n"
    "•  🗂Показать / Удалить - При нажатии покажет кнопки с уже созданными постами а так же с кнопкой удалить\n\n"
    "•  🗓Настройки расписания - При нажатии покажет кнопки с настройками расписания времени, интервала\n\n"
    "•  👥Количество пользователей - При нажатии покажет количество пользователей\n\n"
    "❓ Просто следуйте инструкциям после команды!"
)


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    
    message = call.message
    
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

    elif call.data == 'user_count':
        ask_for_user_count(call)

    elif call.data == 'get_user_list':
        send_user_list(call)

    elif call.data == "no text":
        handle_no_text(call)

    elif call.data == "skip_button":
        handle_skip_button(call)

    elif call.data == "add_button":
        handle_add_button_without_description(call)

    elif call.data == "add_another_button":
        handle_add_another_button(call)

    elif call.data == "finish_post":
        handle_finish_post(call)





def is_in_post_mode(user_id):
    return user_id in user_data and user_data[user_id].get("post_mode", False)

def is_valid_url(url):
    return re.match(r'^https?://', url)

def handle_create_post(call):
    user_id = call.from_user.id
    user_data[user_id] = {
        "post_mode": True,
        "media_group": [],
        "media_group_ids": set(),
        "step": "waiting_description",
        "button": []
    }
    bot.send_message(call.message.chat.id, "Отправьте одно или несколько фото, видео, голосовое или кружок для поста")

@bot.message_handler(content_types=['photo', 'video', 'document', 'audio', 'voice', 'video_note'])
def handle_media(message):
    user_id = message.from_user.id
    if not is_in_post_mode(user_id):
        return

    file_id = None
    media_type = message.content_type

    if media_type == 'photo':
        file_id = message.photo[-1].file_id
    elif hasattr(message, media_type):
        file_id = getattr(message, media_type).file_id

    if file_id:
        user_data[user_id]["media_group"].append({"file_id": file_id, "type": media_type})

    mgid = message.media_group_id
    if not mgid or mgid not in user_data[user_id]["media_group_ids"]:
        if mgid:
            user_data[user_id]["media_group_ids"].add(mgid)
        send_photo_hint(message.chat.id)

@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id
    if not is_in_post_mode(user_id):
        return

    step = user_data[user_id].get("step")
    if step == "waiting_description":
        handle_description_step(message)
    elif step == "waiting_button_url":
        handle_url_step(message)
    elif step == "waiting_button_text":
        handle_button_text_step(message)

def handle_description_step(message):
    user_id = message.from_user.id
    user_data[user_id]['description'] = message.text
    user_data[user_id]['step'] = "waiting_button_url"

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Пропустить", callback_data="skip_button"))

    bot.send_message(
        message.chat.id,
        "\U0001F517 Теперь отправьте ссылку для кнопки (например, https://example.com).\n\nили нажмите 'Пропустить'.",
        reply_markup=keyboard
    )

def handle_url_step(message):
    user_id = message.from_user.id
    url = message.text.strip()

    if not is_valid_url(url):
        bot.send_message(message.chat.id, "❗️Ссылка должна начинаться с http:// или https://")
        return

    user_data[user_id]['_current_url'] = url
    user_data[user_id]['step'] = "waiting_button_text"
    bot.send_message(message.chat.id, "📝 Введите название кнопки:")

def handle_button_text_step(message):
    user_id = message.from_user.id
    button_text = message.text.strip()
    url = user_data[user_id].pop('_current_url', '')

    user_data[user_id]['button'].append({"text": button_text, "url": url})
    user_data[user_id]['step'] = None

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("➕ Добавить ещё кнопку", callback_data="add_another_button"),
        InlineKeyboardButton("✅ Завершить", callback_data="finish_post")
    )
    bot.send_message(message.chat.id, "Кнопка добавлена. Что дальше?", reply_markup=keyboard)

def handle_add_another_button(call):
    user_data[call.from_user.id]['step'] = "waiting_button_url"
    bot.send_message(call.message.chat.id, "🔗 Введите ссылку для новой кнопки:")

def handle_add_button_without_description(call):
    user_id = call.from_user.id
    user_data[user_id]['description'] = ""
    user_data[user_id]['step'] = "waiting_button_url"

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("Пропустить", callback_data="skip_url"))

    bot.send_message(
        call.message.chat.id,
        "🔗 Отлично! Теперь отправьте ссылку для кнопки (например, https://example.com).\n\nили нажмите 'Пропустить'.",
        reply_markup=keyboard
    )

def handle_finish_post(call):
    user_id = call.from_user.id
    data = user_data.get(user_id)

    if not data:
        bot.send_message(call.message.chat.id, "⚠️ Данные не найдены.")
        return

    media_group = data.get("media_group", [])
    description = data.get("description", "")
    button = data.get("button", [])

    if not media_group:
        bot.send_message(call.message.chat.id, "⚠️ Вы не отправили ни одной фотографии.")
        return

    urls = [btn["url"] for btn in button] if button else []
    texts = [btn["text"] for btn in button] if button else []

    save_media_and_text(
        chat_id=call.message.chat.id,
        media_group=media_group,
        text_message=description,
        url=urls,
        button_text=texts
    )
    user_data.pop(user_id, None)

def send_photo_hint(chat_id):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Без описания и без кнопки", callback_data="no text"),
        InlineKeyboardButton("Добавить кнопку без описания", callback_data="add_button")
    )
    bot.send_message(chat_id, "После отправки всех фото отправьте текст поста.\n\nили нажмите кнопку ниже", reply_markup=markup)



def handle_no_text(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    media_group = user_data.get(user_id, {}).get("media_group", [])

    if media_group:
        save_media_and_text(
            chat_id=chat_id,
            media_group=media_group,
            text_message=None,
            url=None,
            button_text=None
        )
    else:
        bot.send_message(chat_id, "⚠️ Вы не отправили ни одной фотографии.")

    user_data.pop(user_id, None)







# --------------------------------Save post-------------------------------------
def save_media_and_text(chat_id, media_group, text_message=None, url=None, button_text=None):

    if not os.path.exists(media_folder):
        os.makedirs(media_folder)

    if os.path.exists(POSTS_FILE_PATH):
        with open(POSTS_FILE_PATH, "r", encoding="utf-8") as f:
            try:
                posts = json.load(f)
            except json.JSONDecodeError:
                posts = []
    else:
        posts = []

    post_id = max([p["id"] for p in posts], default=0) + 1

    saved_photos = []
    for idx, item in enumerate(media_group):
        file_id = item["file_id"]
        media_type = item["type"]

        file_info = bot.get_file(file_id)

        if media_type == "photo":
            file_ext = ".jpg"
        elif media_type == "video":
            file_ext = ".mp4"
        elif media_type == "video_note":
            file_ext = ".mp4"
        elif media_type == "voice":
            file_ext = ".ogg"
        else:
            file_ext = os.path.splitext(file_info.file_path)[-1] or ""

        file_name = f"post_{post_id}_{idx + 1}{file_ext}"
        file_path = os.path.join(media_folder, file_name)

        downloaded_file = bot.download_file(file_info.file_path)
        with open(file_path, 'wb') as f:
            f.write(downloaded_file)

        saved_photos.append({
            "path": file_path.replace("\\", "/"),
            "type": media_type
        })

    post_data = {
        "id": post_id,
        "photos": saved_photos,
    }

    if text_message:
        post_data["description"] = text_message

    if isinstance(url, list) and isinstance(button_text, list):
        post_data["button"] = [
            {"text": t, "url": u}
            for t, u in zip(button_text, url)
            if t and u
        ]
    elif url and button_text:
        post_data["button"] = {
            "text": button_text,
            "url": url
        }



    posts.append(post_data)

    with open(POSTS_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=4, ensure_ascii=False)

    bot.send_message(chat_id, f"✅ Пост #{post_id} успешно сохранён!")







# --------------------------------Show posts-------------------------------------
def handle_show_posts(call):
    if not os.path.exists(POSTS_FILE_PATH):
        bot.send_message(call.message.chat.id, "Нет сохранённых постов.")
        return

    with open(POSTS_FILE_PATH, "r", encoding="utf-8") as f:
        try:
            posts = json.load(f)
        except json.JSONDecodeError:
            posts = []

    if not posts:
        bot.send_message(call.message.chat.id, "Нет сохранённых постов.")
        return

    markup = InlineKeyboardMarkup(row_width=2)
    for post in posts:
        description_preview = post.get("description", "")[:20] or f"Пост #{post['id']} - Без описания"
        view_button = InlineKeyboardButton(f"👁 {description_preview}", callback_data=f"view_post_{post['id']}")
        delete_button = InlineKeyboardButton(f"❌ Удалить", callback_data=f"delete_post_{post['id']}")
        markup.add(view_button, delete_button)

    bot.send_message(call.message.chat.id, "📋 Список постов:", reply_markup=markup)





def handle_view_post(chat_id, post_id):
    # --- Проверка наличия файла постов ---
    if not os.path.exists(POSTS_FILE_PATH):
        bot.send_message(chat_id, "Файл с постами не найден.")
        return

    # --- Загрузка постов из файла ---
    try:
        with open(POSTS_FILE_PATH, "r", encoding="utf-8") as f:
            posts = json.load(f)
    except json.JSONDecodeError:
        bot.send_message(chat_id, "Ошибка при чтении постов.")
        return

    # --- Поиск нужного поста ---
    post = next((p for p in posts if p.get("id") == post_id), None)
    if not post:
        bot.send_message(chat_id, "Пост не найден.")
        return

    # --- Подготовка медиафайлов ---
    media_items = []
    open_files = []
    voice_file = None
    video_note_file = None

    for item in post.get("photos", []):
        media_type = item.get("type")
        path = item.get("path")

        if not (media_type and os.path.exists(path)):
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
            file.close()  # Неизвестный тип — сразу закрываем

    # --- Подготовка описания и кнопок ---
    description = post.get("description", "").strip()
    markup = None

    button = post.get("button") or []
    if not button and "button" in post:
        single_btn = post["button"]
        if single_btn.get("text") and single_btn.get("url"):
            button = [single_btn]

    if button:
        markup = InlineKeyboardMarkup()
        if isinstance(button, list):
            for btn in button:
                if isinstance(btn, dict) and "text" in btn and "url" in btn:
                    markup.add(InlineKeyboardButton(text=btn["text"], url=btn["url"]))
        elif isinstance(button, dict) and "text" in button and "url" in button:
            markup.add(InlineKeyboardButton(text=button["text"], url=button["url"]))


    try:
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
    
    finally:
        for f in open_files:
            f.close()















# --------------------------------Del posts-------------------------------------

def handle_delete_post(chat_id, post_id):
    if not os.path.exists(POSTS_FILE_PATH):
        bot.send_message(chat_id, "Файл с постами не найден.")
        return

    with open(POSTS_FILE_PATH, "r", encoding="utf-8") as f:
        posts = json.load(f)

    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        bot.send_message(chat_id, "Пост не найден.")
        return

    for photo_info in post["photos"]:
        file_path = photo_info["path"] 
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Файл {file_path} успешно удалён.")
            else:
                print(f"Файл {file_path} не найден.")
        except Exception as e:
            print(f"Ошибка при удалении файла {file_path}: {e}")

    posts = [p for p in posts if p["id"] != post_id]

    with open(POSTS_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=4, ensure_ascii=False)

    bot.send_message(chat_id, f"❌ Пост #{post_id} удалён.")






# --------------------------------Shedule-------------------------------------
def handle_shedule(call):

    with open(SHEDULE_FILE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        interval = data.get("interval", "")


    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("⏳ Интервал поста", callback_data="set_interval")
    )

    bot.send_message(call.message.chat.id, 
        f"Настройки расписания:\n\n"
        "• Интервал поста - интервал, через который будут приходить посты\n\n"
        "Настройки сейчас:\n"
        f"Интервал: {interval},\n",
        reply_markup=markup
    )

def ask_for_interval(call):
    msg = bot.send_message(call.message.chat.id, "✍️ Напишите интервал поста например: \n\n• 24:00 (1 день)\n\n• 00:30 (30 минут)\n\n• 00:01 (1 минута)")
    bot.register_next_step_handler(msg, save_interval)


def save_schedule_times(message, stop_time):
    try:
        try:
            with open(SHEDULE_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}


        with open(SHEDULE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при сохранении: {e}")



def save_interval(message):
    interval = message.text.strip()
    if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", interval):
        bot.send_message(message.chat.id, "❌ Неверный формат! Пожалуйста, введите время в формате HH:MM (например, 12:30)")
        return

    try:
        try:
            with open(SHEDULE_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        
        data["interval"] = interval
        with open(SHEDULE_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        bot.send_message(message.chat.id, f"✅ Интервал сохранён: {interval}")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при сохранении: {e}")


# --------------------------------User count-------------------------------------
def ask_for_user_count(call):
    try:
        with open("count.txt", "r") as file:
            user_count = file.read().strip()

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("📂 Получить список пользователей", callback_data="get_user_list"))

        bot.send_message(call.message.chat.id, f"👥 Количество пользователей: {user_count}", reply_markup=keyboard)
    except FileNotFoundError:
        bot.send_message(call.message.chat.id, "Ошибка: файл count.txt не найден.")

def send_user_list(call):
    try:
        with open("users_id.txt", "rb") as file:
            bot.send_document(call.message.chat.id, file)
    except FileNotFoundError:
        bot.send_message(call.message.chat.id, "Ошибка: файл users_id.txt не найден.")

bot.polling(none_stop=True)