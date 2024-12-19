import telebot
from telebot import types
import sqlite3
import atexit
import time
import os
from PIL import Image, ImageDraw, ImageFont
import random
import string
import sys

TOKEN = os.getenv('TOKEN')  # Используйте имя переменной без префикса '$'
bot = telebot.TeleBot(TOKEN)

# Подключение к базе данных
conn = sqlite3.connect('volunteer_bot.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц, если они не существуют
cursor.execute('''
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    link TEXT,
    points INTEGER DEFAULT 0,
    description TEXT  -- Новое поле для описания мероприятия
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    group_name TEXT NOT NULL,
    faculty TEXT NOT NULL,
    event_id INTEGER,
    user_id INTEGER,
    needs_release INTEGER DEFAULT 0,
    FOREIGN KEY (event_id) REFERENCES events (id),
    UNIQUE (user_id, event_id)  -- Составной уникальный ключ
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS user_points (
    user_id INTEGER PRIMARY KEY,
    points INTEGER DEFAULT 0
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS user_states (
    user_id INTEGER PRIMARY KEY,
    has_passed_captcha INTEGER DEFAULT 0
)
''')

# Новая таблица для сохраненных анкет
cursor.execute('''
CREATE TABLE IF NOT EXISTS saved_applications (
    user_id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    group_name TEXT NOT NULL,
    faculty TEXT NOT NULL
)
''')

conn.commit()

# ID администраторов
ADMIN_IDS = [5656088749]  # Замените на ID ваших администраторов

# Глобальные переменные и списки
user_ids = []
last_message_time = {}
repeat_count = {}
user_captchas = {}
user_requests = {}

# Функция генерации капчи
def generate_captcha(text):
    width, height = 200, 100
    image = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)

    font = ImageFont.load_default()
    
    draw.text((50, 25), text, fill=(0, 0, 0), font=font)

    for _ in range(5):
        draw.line([(random.randint(0, width), random.randint(0, height)),
                    (random.randint(0, width), random.randint(0, height))],
                   fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)), width=2)

    return image
@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda message: message.text.lower() == "начать!")
def start(message):
    user_id = message.from_user.id

    cursor.execute('SELECT has_passed_captcha FROM user_states WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()

    if result and result[0] == 1:
        bot.send_message(message.chat.id, "Проверка пройдена!")
        show_main_menu(message)
        return

    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    captcha_image = generate_captcha(captcha_text)
    
    user_captchas[user_id] = captcha_text
    
    captcha_image_path = 'captcha.png'
    captcha_image.save(captcha_image_path)

    with open(captcha_image_path, 'rb') as captcha_file:
        bot.send_photo(message.chat.id, captcha_file)
    
    bot.send_message(message.chat.id, "Введите текст с капчи:")
    
    bot.register_next_step_handler(message, lambda msg: check_captcha(msg, captcha_text))

def check_captcha(message, correct_text):
    user_id = message.from_user.id

    if message.text.strip().upper() == correct_text:
        bot.send_message(message.chat.id, "Проверка пройдена!")
        
        cursor.execute('INSERT OR REPLACE INTO user_states (user_id, has_passed_captcha) VALUES (?, ?)', (user_id, 1))
        conn.commit()

        del user_captchas[user_id]
        show_main_menu(message)
    else:
        bot.send_message(message.chat.id, "Неправильный текст капчи. Попробуйте снова.")
        start(message)

def show_main_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    # Добавляем каждую кнопку на отдельной строке
    btn_show_events = types.KeyboardButton("🟢 Показать мероприятия")
    markup.add(btn_show_events)

    btn_apply_event = types.KeyboardButton("🟢 Записаться на мероприятие")
    markup.add(btn_apply_event)

    btn_my_points = types.KeyboardButton("🟢 Мои баллы")
    markup.add(btn_my_points)

    btn_send_report = types.KeyboardButton("📝 Отправить отчет")
    markup.add(btn_send_report)

    btn_edit_data = types.KeyboardButton("✏️ Редактировать данные")  
    markup.add(btn_edit_data)

    if message.from_user.id in ADMIN_IDS:
        btn_send_link = types.KeyboardButton("🟢 Отправить ссылку на получение часов")
        markup.add(btn_send_link)

        btn_add_event = types.KeyboardButton("🟢 Добавить мероприятие")
        markup.add(btn_add_event)

        btn_delete_event = types.KeyboardButton("🟢 Удалить мероприятие")
        markup.add(btn_delete_event)

        btn_send_points = types.KeyboardButton("🟢 Отправить баллы")
        markup.add(btn_send_points)

    btn_request_link = types.KeyboardButton("🔗 Запросить ссылку на волонтерские часы")
    markup.add(btn_request_link)

    btn_rating = types.KeyboardButton("🏆 Рейтинг")
    markup.add(btn_rating)

    bot.send_message(message.chat.id, "Добро пожаловать в студенческий волонтёрский центр! Выберите действие:", reply_markup=markup)

# Обработка команды "Редактировать данные"
@bot.message_handler(func=lambda message: message.text == "✏️ Редактировать данные")
def edit_saved_data(message):
   user_id = message.from_user.id
   cursor.execute('SELECT * FROM saved_applications WHERE user_id=?', (user_id,))
   saved_data = cursor.fetchone()

   if saved_data:
       show_edit_menu(message)
   else:
       bot.send_message(message.chat.id, "У вас нет сохранённых данных.")

def show_edit_menu(message):
   markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

   btn_edit_full_name = types.KeyboardButton("✏️ Изменить ФИО")
   markup.add(btn_edit_full_name)

   btn_edit_group = types.KeyboardButton("✏️ Изменить группу")
   markup.add(btn_edit_group)

   btn_edit_faculty = types.KeyboardButton("✏️ Изменить факультет")
   markup.add(btn_edit_faculty)

   btn_cancel = types.KeyboardButton("❌ Отменить")  
   markup.add(btn_cancel)

   bot.send_message(message.chat.id, "Выберите, что хотите изменить:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "❌ Отменить")
def cancel_action(message):
   bot.send_message(message.chat.id, "Вы вернулись в главное меню.")
   show_main_menu(message)

# Обработка изменения ФИО
@bot.message_handler(func=lambda message: message.text == "✏️ Изменить ФИО")
def change_full_name(message):
   user_id = message.from_user.id
   cursor.execute('SELECT full_name FROM saved_applications WHERE user_id=?', (user_id,))
   result = cursor.fetchone()

   if result:
       old_full_name = result[0]  
       bot.send_message(message.chat.id, f"Ваше текущее ФИО: {old_full_name}\nВведите новое ФИО (или оставьте пустым для пропуска):")
       bot.register_next_step_handler(message, lambda msg: update_full_name(msg, old_full_name))
   else:
       bot.send_message(message.chat.id, "У вас нет сохранённого ФИО.")

def update_full_name(message, old_full_name):
   new_full_name = message.text.strip() or old_full_name
   user_id = message.from_user.id

   cursor.execute('UPDATE saved_applications SET full_name=? WHERE user_id=?', (new_full_name, user_id))
   conn.commit()

   bot.send_message(message.chat.id, "Ваше ФИО успешно обновлено!")
   show_main_menu(message)

# Обработка изменения группы
@bot.message_handler(func=lambda message: message.text == "✏️ Изменить группу")
def change_group_name(message):
   user_id = message.from_user.id
   cursor.execute('SELECT group_name FROM saved_applications WHERE user_id=?', (user_id,))
   result = cursor.fetchone()

   if result:
       old_group_name = result[0]  
       bot.send_message(message.chat.id, f"Ваша текущая группа: {old_group_name}\nВведите новую группу (или оставьте пустым для пропуска):")
       bot.register_next_step_handler(message, lambda msg: update_group_name(msg, old_group_name))
   else:
       bot.send_message(message.chat.id, "У вас нет сохранённой группы.")

def update_group_name(message, old_group_name):
   new_group_name = message.text.strip() or old_group_name
   user_id = message.from_user.id

   cursor.execute('UPDATE saved_applications SET group_name=? WHERE user_id=?', (new_group_name, user_id))
   conn.commit()

   bot.send_message(message.chat.id, "Ваша группа успешно обновлена!")
   show_main_menu(message)

# Обработка изменения факультета
@bot.message_handler(func=lambda message: message.text == "✏️ Изменить факультет")
def change_faculty_name(message):
   user_id = message.from_user.id
   cursor.execute('SELECT faculty FROM saved_applications WHERE user_id=?', (user_id,))
   result = cursor.fetchone()

   if result:
       old_faculty = result[0]  
       bot.send_message(message.chat.id, f"Ваш текущий факультет: {old_faculty}\nВведите новый факультет (или оставьте пустым для пропуска):")
       bot.register_next_step_handler(message, lambda msg: update_faculty_name(msg, old_faculty))
   else:
       bot.send_message(message.chat.id, "У вас нет сохранённого факультета.")

def update_faculty_name(message, old_faculty):
   new_faculty = message.text.strip() or old_faculty
   user_id = message.from_user.id

   cursor.execute('UPDATE saved_applications SET faculty=? WHERE user_id=?', (new_faculty, user_id))
   conn.commit()

   bot.send_message(message.chat.id, "Ваш факультет успешно обновлён!")
   show_main_menu(message)


# Обработка команды "Показать мероприятия"
# Обработка команды "Показать мероприятия"
@bot.message_handler(func=lambda message: message.text == "🟢 Показать мероприятия")
def show_events(message):
    cursor.execute('SELECT name FROM events')
    events = cursor.fetchall()
    
    if events:
        markup = types.InlineKeyboardMarkup()  # Используем инлайн-клавиатуру
        
        for event in events:
            button = types.InlineKeyboardButton(event[0], callback_data=event[0])  
            markup.add(button)
        
        # Отправляем сообщение с инлайн-кнопками
        bot.send_message(message.chat.id, "Ближайшие мероприятия:", reply_markup=markup)
        
        # Создаем обычную клавиатуру с кнопкой отмены
        cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        cancel_button = types.KeyboardButton("❌ Отменить")
        cancel_markup.add(cancel_button)
        
        bot.send_message(message.chat.id, "Если хотите вернуться в главное меню, нажмите 'Отменить'.", reply_markup=cancel_markup)
    else:
        bot.send_message(message.chat.id, "Нет ближайших мероприятий.")

# Обработчик выбора мероприятия
@bot.callback_query_handler(func=lambda call: True)
def handle_event_selection(call):
    selected_event = call.data  # Получаем выбранное мероприятие
    
    cursor.execute('SELECT description FROM events WHERE name = ?', (selected_event,))
    event_info = cursor.fetchone()

    if event_info:
        bot.send_message(call.message.chat.id, f"Информация о мероприятии '{selected_event}':\n{event_info[0]}")
    else:
        bot.send_message(call.message.chat.id, "Выбранное мероприятие не найдено.")

# Обработка нажатия кнопки "Отменить"
@bot.message_handler(func=lambda message: message.text == "❌ Отменить")
def cancel_action(message):
    bot.send_message(message.chat.id, "Вы вернулись в главное меню.")
    show_main_menu(message)  # Возвращаем в главное меню

# Обработчик выбора мероприятия
@bot.callback_query_handler(func=lambda call: True)
def handle_event_selection(call):
   selected_event = call.data  
   
   cursor.execute('SELECT description FROM events WHERE name = ?', (selected_event,))
   event_info = cursor.fetchone()

   if event_info:
       bot.send_message(call.message.chat.id, f"Информация о мероприятии '{selected_event}':\n{event_info[0]}")
   else:
       bot.send_message(call.message.chat.id, "Выбранное мероприятие не найдено.")

@bot.message_handler(func=lambda message: message.text == "🟢 Записаться на мероприятие")
def get_event_for_application(message):
    cursor.execute('SELECT name FROM events')
    events = cursor.fetchall()

    if events:
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
        for event in events:
            markup.add(event[0])
        markup.add(types.KeyboardButton("❌ Отменить"))  # Добавляем кнопку отмены здесь 
        bot.send_message(message.chat.id, "Выберите мероприятие для записи:", reply_markup=markup)
        bot.register_next_step_handler(message, handle_event_selection)
    else:
        bot.send_message(message.chat.id, "Нет мероприятий для записи.")

def handle_event_selection(message):
    selected_event = message.text.strip()

    if selected_event == "❌ Отменить":
        cancel_action(message)
        return

    cursor.execute('SELECT id FROM events WHERE name = ?', (selected_event,))
    event_id_result = cursor.fetchone()

    if event_id_result:
        cursor.execute('SELECT * FROM saved_applications WHERE user_id=?', (message.from_user.id,))
        saved_data = cursor.fetchone()

        if saved_data:
            bot.send_message(message.chat.id, "У вас есть сохраненные данные. Нужно ли вам освобождение? (да/нет)")
            bot.register_next_step_handler(message, lambda msg: submit_application(msg, saved_data[1], saved_data[2], saved_data[3], event_id_result[0]))
        else:
            bot.send_message(message.chat.id, "Введите ваше ФИО:")
            bot.register_next_step_handler_by_chat_id(message.from_user.id, lambda msg: ask_for_group(msg, event_id_result[0]))
    else:
        bot.send_message(message.chat.id, "Выбранное мероприятие не найдено.")

def ask_for_group(message, event_id):
    full_name = message.text.strip()
    bot.send_message(message.chat.id, "Введите вашу группу:")
    bot.register_next_step_handler(message, lambda msg: ask_for_faculty(msg, full_name, event_id))

def ask_for_faculty(message, full_name, event_id):
    group_name = message.text.strip()
    bot.send_message(message.chat.id, "Введите ваш факультет:")
    bot.register_next_step_handler(message, lambda msg: submit_application(msg, full_name, group_name, msg.text.strip(), event_id))

def submit_application(message, full_name, group_name, faculty, event_id):
    user_id = message.from_user.id

    # Проверяем нажатие кнопки освобождения
    needs_release = 1 if message.text.lower() == 'да' else 0 

    cursor.execute('SELECT * FROM applications WHERE user_id=? AND event_id=?', (user_id, event_id))
    existing_application = cursor.fetchone()

    if existing_application:
        bot.send_message(user_id, "Вы уже подали заявку на это мероприятие.")
        return

    cursor.execute(
        'INSERT INTO applications (full_name , group_name , faculty , event_id , user_id , needs_release) VALUES (?, ?, ?, ?, ?, ?)',
        (full_name , group_name , faculty , event_id , user_id , needs_release)
    )
    
    conn.commit()

    cursor.execute('SELECT name FROM events WHERE id=?', (event_id,))
    event_name = cursor.fetchone()[0]

    cursor.execute('INSERT OR REPLACE INTO saved_applications (user_id , full_name , group_name , faculty) VALUES (?, ?, ?, ?)', 
                   (user_id , full_name , group_name , faculty))
    
    conn.commit()

    for admin in ADMIN_IDS:
        bot.send_message(
            admin,
            f"Новая заявка:\nФИО:{full_name}\nГруппа:{group_name}\nФакультет:{faculty}\nМероприятие:{event_name}\nНужно освобождение: {'Да' if needs_release else 'Нет'}"
        )
    
    bot.send_message(message.chat.id,"Ваша заявка отправлена!")



# Обработка команды "Запросить ссылку на мероприятие"
@bot.message_handler(func=lambda message: message.text == "🔗 Запросить ссылку на волонтерские часы")
def request_event_link(message):
   cursor.execute('SELECT name FROM events')
   events = cursor.fetchall()

   if events:
       markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
       for event in events:
           markup.add(event[0])
       markup.add(types.KeyboardButton("❌ Отменить"))  # Добавляем кнопку отмены здесь 
       bot.send_message(
           message.chat.id,"Выберите мероприятие для запроса ссылки:", reply_markup=markup)
       bot.register_next_step_handler(message , handle_request_link)
   else:
       bot.send_message(message.chat.id,"Нет мероприятий для запроса ссылки.")

def handle_request_link(message):
   selected_event = message.text.strip()
   if selected_event == "❌ Отменить":
       cancel_action(message)
       return

   cursor.execute('SELECT id FROM events WHERE name=?', (selected_event,))
   event_id_result = cursor.fetchone()

   if not event_id_result:
       bot.send_message(message.chat.id,"Выбранное мероприятие не найдено.")
       return

   event_id = event_id_result[0]

   cursor.execute('INSERT OR IGNORE INTO applications (user_id,event_id) VALUES (?, ?)', (message.from_user.id,event_id))

   for admin in ADMIN_IDS:
       bot.send_message(admin,f"Пользователь {message.from_user.first_name} запрашивает ссылку на мероприятие '{selected_event}'.")

   bot.send_message(message.chat.id,"Запрос на ссылку отправлен!")

# Обработка команды "Отправить ссылку"
@bot.message_handler(func=lambda message: message.text == "🟢 Отправить ссылку на получение часов")
def prompt_send_link(message):
   if message.from_user.id in ADMIN_IDS:
       cursor.execute('SELECT name FROM events')
       events = cursor.fetchall()

       if events:
           markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
           for event in events:
               markup.add(event[0])  
           markup.add(types.KeyboardButton("❌ Отменить"))  # Добавляем кнопку отмены здесь 
           bot.send_message(message.chat.id,"Выберите мероприятие для отправки ссылки:", reply_markup=markup)
           bot.register_next_step_handler(message , select_event_for_link)
       else:
           bot.send_message(message.chat.id,"Нет мероприятий для отправки ссылки.")

def select_event_for_link(message):
   selected_event = message.text.strip()
   
   if selected_event == "❌ Отменить":
       cancel_action(message)
       return

   cursor.execute('SELECT id FROM events WHERE name=?',(selected_event,))
   event_id_result = cursor.fetchone()

   if not event_id_result:
       bot.send_message(message.chat.id,"Выбранное мероприятие не найдено.")
       return

   event_id = event_id_result[0]
   
   cursor.execute('SELECT user_id FROM applications WHERE event_id=?', (event_id,))
   users = cursor.fetchall()

   if users:
       markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
       for user in users:
           user_info = bot.get_chat(user[0])  
           markup.add(user_info.first_name)  
       
       bot.send_message(message.chat.id,"Выберите пользователя для отправки ссылки:", reply_markup=markup)
       bot.register_next_step_handler(message , lambda msg: ask_for_link(msg,event_id))
   else:
       bot.send_message(message.chat.id,"Нет пользователей которые запрашивали ссылку на это мероприятие.")

def ask_for_link(message,event_id):
   selected_user_name = message.text.strip()
   
   cursor.execute('SELECT user_id FROM applications WHERE event_id=?', (event_id,))
   users = cursor.fetchall()
   
   selected_user_ids = [user[0] for user in users]
   
   selected_user = None
   
   for user in selected_user_ids:
       user_info = bot.get_chat(user)  
       if user_info.first_name == selected_user_name:
           selected_user = user  
           break

   if selected_user is None:
       bot.send_message(message.chat.id,"Пользователь не найден.")
       return

   bot.send_message(message.chat.id,"Введите ссылку на мероприятие:")
   bot.register_next_step_handler(message , lambda msg: send_link_to_user(msg , selected_user))

def send_link_to_user(message , selected_user):
   link = message.text.strip()
   
   bot.send_message(selected_user,f"Ссылка на мероприятие: {link}")
   
   bot.send_message(message.chat.id,"Ссылка успешно отправлена выбранному пользователю!")

# Обработка команды "Мои баллы"
@bot.message_handler(func=lambda message: message.text == "🟢 Мои баллы")
def show_user_points(message):
   user_id = message.from_user.id
   
   cursor.execute('SELECT points FROM user_points WHERE user_id=?', (user_id,))
   result = cursor.fetchone()

   if result:
       points = result[0]
       bot.send_message(message.chat.id,f"У вас {points} баллов.")
   else:
       bot.send_message(message.chat.id,"У вас еще нет начисленных баллов.")

# Обработка команды "Рейтинг"
@bot.message_handler(func=lambda message: message.text == "🏆 Рейтинг")
def show_rating(message):
    cursor.execute('''
        SELECT u.full_name AS full_name, COALESCE(SUM(up.points), 0) AS total_points
        FROM saved_applications u LEFT JOIN user_points up ON u.user_id = up.user_id
        GROUP BY u.user_id
        ORDER BY total_points DESC;
    ''')
    ratings = cursor.fetchall()

    if ratings:
        rating_list = "\n".join([f"{i + 1}. {r[0]} - {r[1]} баллов" for i, r in enumerate(ratings)])
        bot.send_message(
            message.chat.id, f"Рейтинг участников:\n{rating_list}"
        )
    else:
        bot.send_message(
            message.chat.id, "Нет данных для отображения рейтинга."
        )

# Обработка команды "Добавить мероприятие"
# Обработка команды "Добавить мероприятие"
@bot.message_handler(func=lambda message: message.text == "🟢 Добавить мероприятие")
def prompt_add_event(message):
    if message.from_user.id in ADMIN_IDS:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("❌ Отменить"))  # Добавляем кнопку отмены здесь 
        bot.send_message(message.chat.id, "Введите название мероприятия:", reply_markup=markup)
        bot.register_next_step_handler(message, save_event)

def save_event(message):
    if message.text.strip() == "❌ Отменить":
        cancel_action(message)
        return

    event_name = message.text.strip()

    if event_name:  
        bot.send_message(message.chat.id, "Введите ссылку на мероприятие (или оставьте пустым):")
        bot.register_next_step_handler(message, lambda msg: save_event_with_link(msg, event_name))
    else:
        bot.send_message(message.chat.id, "Название мероприятия не может быть пустым. Пожалуйста, введите название снова.")
        bot.register_next_step_handler(message, save_event)

def save_event_with_link(message, event_name):
    if message.text.strip() == "❌ Отменить":
        cancel_action(message)
        return

    link = message.text.strip() or None  
    bot.send_message(message.chat.id, "Введите информацию о мероприятии (или оставьте пустым):")
    bot.register_next_step_handler(message, lambda msg: save_event_with_description(msg, event_name, link))

def save_event_with_description(message, event_name, link):
    if message.text.strip() == "❌ Отменить":
        cancel_action(message)
        return

    description = message.text.strip() or None

    cursor.execute('INSERT INTO events (name, link, description) VALUES (?, ?, ?)', (event_name, link, description))
    conn.commit()

    for admin in ADMIN_IDS: 
        bot.send_message(admin, f"Новое мероприятие добавлено: '{event_name}'")

    bot.send_message(message.chat.id, f"Мероприятие '{event_name}' успешно добавлено!")
    show_main_menu(message)

# Функция для обработки отмены
@bot.message_handler(func=lambda message: message.text == "❌ Отменить")
def cancel_action(message):
   bot.send_message(message.chat.id, "Вы вернулись в главное меню.")
   show_main_menu(message)

# Обработка команды "Удалить мероприятие"
@bot.message_handler(func=lambda message: message.text == "🟢 Удалить мероприятие")
def delete_event(message):
	if message.from_user.id in ADMIN_IDS:
	    cursor.execute('SELECT name FROM events')
	    events=cursor.fetchall()

	    if events:
	        markup=types.ReplyKeyboardMarkup(one_time_keyboard=True)
	        for event in events:
	            markup.add(event[0])
	        markup.add(types.KeyboardButton("❌ Отменить"))  # Добавляем кнопку отмены здесь 
	        bot.send_message(
	            message.chat.id,"Выберите мероприятие для удаления:", reply_markup=markup)
	        bot.register_next_step_handler(
	            message , confirm_delete_event)
	    else:
	        bot.send_message(
	            message.chat.id,"Нет мероприятий для удаления.")

# Подтверждение удаления мероприятия
def confirm_delete_event(message):
	selected_event = message.text.strip()
	
	if selected_event == "❌ Отменить":
	    cancel_action(message)
	    return
	
	cursor.execute('DELETE FROM events WHERE name=?', (selected_event,))
	conn.commit()
	
	for admin in ADMIN_IDS: 
	    for user in user_ids:
	        bot.send_message(user, f"Мероприятие '{selected_event}' было удалено.")
	
	bot.send_message(
	    message.chat.id, f"Мероприятие '{selected_event}' успешно удалено."
	)

@bot.message_handler(func=lambda message: message.text == "🟢 Отправить баллы")
def send_points_menu(message):
    if message.from_user.id in ADMIN_IDS:
        cursor.execute('SELECT name FROM events')
        events = cursor.fetchall()

        if events:
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
            for event in events:
                markup.add(event[0])
            markup.add(types.KeyboardButton("❌ Отменить"))  # Добавляем кнопку отмены здесь 
            bot.send_message(message.chat.id, "Выберите мероприятие для отправки баллов:", reply_markup=markup)
            bot.register_next_step_handler(message, select_user_for_points)
        else:
            bot.send_message(message.chat.id, "Нет мероприятий для отправки баллов.")

def select_user_for_points(message):
    selected_event = message.text.strip()
    
    if selected_event == "❌ Отменить":
        cancel_action(message)  # Обработка отмены
        return
    
    cursor.execute('SELECT id FROM events WHERE name=?', (selected_event,))
    event_id_result = cursor.fetchone()

    if not event_id_result:
        bot.send_message(message.chat.id, "Мероприятие не найдено.")
        return

    event_id = event_id_result[0]
    
    cursor.execute('SELECT full_name FROM applications WHERE event_id=?', (event_id,))
    applicants = cursor.fetchall()

    if applicants:
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
        for app in applicants:
            markup.add(app[0])
        markup.add(types.KeyboardButton("❌ Отменить"))  # Добавляем кнопку отмены здесь 
        bot.send_message(message.chat.id, "Выберите пользователя для начисления баллов:", reply_markup=markup)
        bot.register_next_step_handler(message, lambda msg: set_points(msg, event_id))
    else:
        bot.send_message(message.chat.id, "Нет заявок на это мероприятие.")

def set_points(message, selected_event_id):
    if message.text.strip() == "❌ Отменить":
        cancel_action(message)  # Обработка отмены
        return
    
    selected_user_full_name = message.text.strip()
    
    cursor.execute('SELECT user_id FROM applications WHERE full_name=? AND event_id=?',
                   (selected_user_full_name.strip(), selected_event_id))
    
    user_data = cursor.fetchone()
    
    if user_data:
        user_id = user_data[0]
        
        bot.send_message(
            message.chat.id, "Введите количество баллов:")
        bot.register_next_step_handler(
            message, lambda msg: update_points(msg, selected_event_id, user_id))
    else:
        bot.send_message(message.chat.id, "Пользователь не найден.")

def update_points(message, event_id, user_id):
    if message.text.strip() == "❌ Отменить":
        cancel_action(message)  # Обработка отмены
        return

    try:
        points = int(message.text)  # Получаем количество баллов от пользователя

        cursor.execute('SELECT points FROM user_points WHERE user_id=?', (user_id,))
        result = cursor.fetchone()

        if result:
            cursor.execute('UPDATE user_points SET points=points+? WHERE user_id=?', (points, user_id))
        else:
            cursor.execute('INSERT INTO user_points (user_id, points) VALUES (?, ?)', (user_id, points))

        conn.commit()

        cursor.execute('SELECT name FROM events WHERE id=?', (event_id,))
        event_name = cursor.fetchone()[0]

        bot.send_message(user_id,
                         f"Вам начислено {points} баллов за участие в мероприятии '{event_name}'.")

        for admin in ADMIN_IDS:
            bot.send_message(admin,
                             f"Баллы за мероприятие '{event_name}' обновлены.")
        
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите корректное число. Попробуйте еще раз:")
        bot.register_next_step_handler(message, lambda msg: update_points(msg, event_id, user_id))  # Повторный ввод

def cancel_action(message):
    bot.send_message(message.chat.id, "Вы вернулись в главное меню.")
    show_main_menu(message)  # Возвращаем в главное меню


# Обработка команды "Отправить отчет"
@bot.message_handler(func=lambda message: message.text == "📝 Отправить отчет")
def prompt_send_report(message):
	cursor.execute('SELECT name FROM events')
	events = cursor.fetchall()

	if events:
		markup = types.ReplyKeyboardMarkup(one_time_keyboard=True)
		for event in events:
			markup.add(event[0])
		markup.add(types.KeyboardButton("❌ Отменить"))  # Добавляем кнопку отмены здесь 
		bot.send_message(
			message.chat.id,"Выберите мероприятие для отправки отчета:", reply_markup=markup)
		bot.register_next_step_handler(message , check_application_before_report)  
	else:
		bot.send_message(message.chat.id,"Нет мероприятий для выбора.")

def check_application_before_report(message):
    selected_event = message.text.strip()     
    if selected_event == "❌ Отменить":
        cancel_action(message)
        return
    
    cursor.execute('SELECT id FROM events WHERE name = ?', (selected_event,))
    event_id_result = cursor.fetchone()

    if not event_id_result:
        bot.send_message(message.chat.id, "Выбранное мероприятие не найдено.")
        return
    
    event_id = event_id_result[0]
    
    cursor.execute('SELECT * FROM applications WHERE event_id = ? AND user_id = ?', (event_id, message.from_user.id))
    
    application_exists = cursor.fetchone()
    
    if application_exists:  
        bot.send_message(
            message.chat.id,
            "Введите содержание вашего отчета или отправьте фото/видео:"
        )
        bot.register_next_step_handler(
            message,
            lambda msg: handle_report_content(msg, event_id)
        )
    else:  
        bot.send_message(message.chat.id, "Вы не можете отправить отчет на это мероприятие. Сначала подайте заявку.")

def handle_report_content(message, event_id):
    if message.content_type == 'text':
        report_content = message.text.strip()
        
        # Уведомление админа о новом текстовом отчете
        cursor.execute('SELECT name FROM events WHERE id = ?', (event_id,))
        event_name = cursor.fetchone()[0]
        
        for admin in ADMIN_IDS:
            bot.send_message(admin,
                             f"Новый отчет от пользователя {message.from_user.first_name}:\n"
                             f"Мероприятие ID: {event_id}\n"
                             f"Название мероприятия: {event_name}\n"
                             f"Содержание отчета:\n{report_content}")

        bot.send_message(message.chat.id, "Ваш текстовый отчет успешно отправлен админу!")


    elif message.content_type in ['photo', 'video']:
        media_file_id = message.photo[-1].file_id if message.content_type == 'photo' else message.video.file_id
        report_content = f"Отчет с медиафайлом. ID медиафайла: {media_file_id}"
        
        # Уведомление админа о новом отчете с медиафайлом
        cursor.execute('SELECT name FROM events WHERE id = ?', (event_id,))
        event_name = cursor.fetchone()[0]
        
        for admin in ADMIN_IDS:
            bot.send_message(admin,
                             f"Новый отчет от пользователя {message.from_user.first_name}:\n"
                             f"Мероприятие ID: {event_id}\n"
                             f"Название мероприятия: {event_name}\n"
                             f"Содержание отчета:\n{report_content}")
            
            # Отправляем администратору медиафайл
            if message.content_type == 'photo':
                file_info = bot.get_file(media_file_id)
                downloaded_file = bot.download_file(file_info.file_path)
                with open("temp_photo.jpg", 'wb') as new_file:
                    new_file.write(downloaded_file)
                with open("temp_photo.jpg", 'rb') as new_file:
                    bot.send_photo(admin, new_file)
            
            elif message.content_type == 'video':
                file_info = bot.get_file(media_file_id)
                downloaded_file = bot.download_file(file_info.file_path)
                with open("temp_video.mp4", 'wb') as new_file:
                    new_file.write(downloaded_file)
                with open("temp_video.mp4", 'rb') as new_file:
                    bot.send_video(admin, new_file)

        bot.send_message(message.chat.id, "Ваш отчет с медиафайлом успешно отправлен админу!")

# Обработка текстовых сообщений и кнопок меню
@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    current_time = time.time()
    
    # Проверка на слишком быстрые команды и повторяющиеся сообщения.
    if message.from_user.id in last_message_time:
        if current_time - last_message_time[message.from_user.id] < 1:  # Если сообщение отправлено менее чем за 1 секунду.
            handle_unusual_behavior(message.from_user.id)
            return
        
        if repeat_count.get(message.text) and repeat_count[message.text] >= 3:  # Если команда повторяется более 3 раз подряд.
            handle_unusual_behavior(message.from_user.id)
            return
        
        repeat_count[message.text] += 1
    
    last_message_time[message.from_user.id] = current_time

# Обработка необычного поведения
def handle_unusual_behavior(user_id):
    bot.send_message(user_id, "Вы отправляете сообщения слишком быстро или повторяете одну и ту же команду. Пожалуйста, сделайте паузу.")

if __name__ == "__main__":
    print("Бот запущен...")
    atexit.register(lambda: conn.close())  # Закрытие соединения с БД при завершении работы
    
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"Произошла ошибка: {e}")
            print("Перезапуск бота...")
            os.execv(sys.executable, ['python'] + sys.argv)  # Перезапускаем текущий скрипт
