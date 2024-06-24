from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from logic import *
import schedule
import threading
import time
from config import *

bot = TeleBot(API_TOKEN)
bonus_cost = 10  # стоимость бонуса
points_per_win = 5  # очки за победу

def gen_markup(id):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("Получить!", callback_data=id))
    return markup

def send_message():
    prize_id, img = manager.get_random_prize()[:2]
    manager.mark_prize_used(prize_id)
    hide_img(img)
    for user in manager.get_users():
        with open(f'hidden_img/{img}', 'rb') as photo:
            bot.send_photo(user, photo, reply_markup=gen_markup(id = prize_id))

def send_late_message(user_id, prize_id, img):
    with open(f'img/{img}', 'rb') as photo:
        bot.send_photo(user_id, photo, caption="Ты получил картинку за бонусы!")
    manager.deduct_user_points(user_id, cost=bonus_cost)
    manager.add_winner(user_id, prize_id)

def shedule_thread():
    schedule.every().minute.do(send_message)  # Здесь ты можешь задать периодичность отправки картинок
    while True:
        schedule.run_pending()
        time.sleep(1)

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.chat.id
    if user_id in manager.get_users():
        bot.reply_to(message, "Ты уже зарегистрирован!")
    else:
        manager.add_user(user_id, message.from_user.username)
        bot.reply_to(message, """Привет! Добро пожаловать! 
Тебя успешно зарегистрировали!
Каждую минуту будут приходить новые картинки и у тебя будет шанс их получить!
Для этого нужно быстрее всех нажать на кнопку 'Получить!'

Только три первых пользователя получат картинку!)""")

@bot.message_handler(commands=['rating'])
def handle_rating(message):
    res = manager.get_ratting()
    res = [f'| @{x[0]:<11} | {x[1]:<11}|\n{"_"*26}' for x in res]
    res = '\n'.join(res)
    res = f'|USER_NAME    |COUNT_PRIZE|\n{"_"*26}\n' + res
    bot.send_message(message.chat.id, res)

@bot.message_handler(commands=['get_bonus_image'])
def handle_get_bonus_image(message):
    user_id = message.chat.id
    if manager.get_user_points(user_id) >= bonus_cost:
        prize_id, img = manager.get_last_prize()
        if manager.get_winners_count(prize_id) < 3:
            send_late_message(user_id, prize_id, img)
        else:
            bot.send_message(user_id, "К сожалению, эту картинку уже нельзя получить даже за бонусы!")
    else:
        bot.send_message(user_id, "У тебя недостаточно бонусов!")

@bot.message_handler(commands=['add_image'])
def handle_add_image(message):
    if is_admin(message.chat.id):
        bot.send_message(message.chat.id, "Отправь изображение, которое хочешь добавить.")
        bot.register_next_step_handler(message, receive_image)
    else:
        bot.reply_to(message, "У тебя нет прав администратора.")

def receive_image(message):
    if message.photo:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        src = f'img/{file_info.file_path.split("/")[-1]}'
        with open(src, 'wb') as new_file:
            new_file.write(downloaded_file)
        manager.add_image(src)
        bot.reply_to(message, "Изображение добавлено.")
    else:
        bot.reply_to(message, "Это не изображение!")

def is_admin(user_id):
    return user_id in ADMIN_IDS

@bot.message_handler(commands=['set_frequency'])
def handle_set_frequency(message):
    if is_admin(message.chat.id):
        bot.send_message(message.chat.id, "Укажи новую частоту отправки сообщений в минутах.")
        bot.register_next_step_handler(message, set_frequency)
    else:
        bot.reply_to(message, "У тебя нет прав администратора.")

def set_frequency(message):
    try:
        new_frequency = int(message.text)
        schedule.clear()
        schedule.every(new_frequency).minutes.do(send_message)
        bot.reply_to(message, f"Частота сообщений установлена на {new_frequency} минут.")
    except ValueError:
        bot.reply_to(message, "Некорректное значение. Укажи частоту в минутах цифрами.")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    prize_id = call.data
    user_id = call.message.chat.id

    if manager.get_winners_count(prize_id) < 3:
        res = manager.add_winner(user_id, prize_id)
        if res:
            img = manager.get_prize_img(prize_id)
            with open(f'img/{img}', 'rb') as photo:
                bot.send_photo(user_id, photo, caption="Поздравляем! Ты получил картинку!")
        else:
            bot.send_message(user_id, 'Ты уже получил картинку!')
    else:
        bot.send_message(user_id, "К сожалению, ты не успел получить картинку! Попробуй в следующий раз!)")

def polling_thread():
    bot.polling(none_stop=True)

if __name__ == '__main__':
    manager = DatabaseManager(DATABASE)
    manager.create_tables()

    polling_thread = threading.Thread(target=polling_thread)
    polling_shedule = threading.Thread(target=shedule_thread)

    polling_thread.start()
    polling_shedule.start()
