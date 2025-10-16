import logging
import asyncio
import psycopg2
import aioschedule
import random
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from datetime import datetime, timedelta

TOKEN = "7629647867:AAH2LyM8F6rJkJvA5_F49w4edVaT-sA7Xxg"
DB_CONFIG = {
    "dbname": "random_coffee",
    "user": "postgres",
    "password": "!Postgres321!",
    "host": "localhost"
}

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

#Подключение к бд
def connect_db():
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE,
            username TEXT,
            name TEXT,
            city TEXT,
            description TEXT,
            mode TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meetings(
            id SERIAL PRIMARY KEY,
            user1 BIGINT,
            user2 BIGINT,
            date TIMESTAMP DEFAULT NOW(),
            feedback1 TEXT,
            feedback2 TEXT,
            additional_feedback1 TEXT,
            additional_feedback2 TEXT,
            reminder_sent BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (user1) REFERENCES users(telegram_id),
            FOREIGN KEY (user2) REFERENCES users(telegram_id)
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

class Registration(StatesGroup):
    name = State()
    city = State()
    description = State()
    mode = State()

class Feedback(StatesGroup):
    waiting_for_rating = State()
    waiting_for_text = State()

#Клавиатура для выбора рейтинга
rating_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
rating_keyboard.add("🌟🌟🌟🌟🌟 СУПЕР!", "🌟🌟🌟🌟ХОРОШО", "🌟🌟🌟 НОРМАЛЬНО", "🌟🌟НУ, ТАКОЕ", "🌟ПЛОХО")


# Клавиатура для выбора режима общения
mode_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
mode_keyboard.add(KeyboardButton("В моем городе"), KeyboardButton("Онлайн"))

#Стартовое общение
@dp.message_handler(commands=["start"])
async def start_command(message: types.Message):
    await message.answer("Привет! Давай познакомимся. Как тебя зовут?")
    await Registration.name.set()

#Сохранение имени
@dp.message_handler(state=Registration.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Из какого ты города?")
    await Registration.city.set()

#Сохранение города
@dp.message_handler(state=Registration.city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer("Расскажи о себе (до 300 символов):")
    await Registration.description.set()

#Сохранение описание профиля
@dp.message_handler(state=Registration.description)
async def process_description(message: types.Message, state: FSMContext):
    if len(message.text) > 300:
        await message.answer("Описание слишком длинное, попробуй короче (до 300 символов)")
        return
    await state.update_data(description=message.text)
    await message.answer("Выбери формат общения\nпри помощи клавиатуры снизу👇", reply_markup=mode_keyboard)
    await Registration.mode.set()

#Сохранение режима общения
@dp.message_handler(state=Registration.mode)
async def process_mode(message: types.Message, state: FSMContext):
    if message.text not in ["В моем городе", "Онлайн"]:
        await message.answer("Выбери один из предложенных вариантов")
        return


    user_data = await state.get_data()
    telegram_id = message.from_user.id
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (telegram_id, username, name, city, description, mode)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (telegram_id) 
        DO UPDATE 
            SET username=excluded.username,
                name=excluded.name,
                city=excluded.city,
                description=excluded.description,
                mode=excluded.mode
    """, (telegram_id, message.from_user.username, user_data['name'], user_data['city'], user_data['description'], message.text))
    conn.commit()
    cursor.close()
    conn.close()

    await message.answer("Ты зарегистрирован! Ожидай отбор напарника на следующей неделе.", reply_markup=types.ReplyKeyboardRemove())
    await state.finish()

# Функционал подбора пар
async def match_pairs():
    conn = connect_db()
    cursor = conn.cursor()

    cursor.execute("SELECT telegram_id, username, city, mode FROM users")
    users = cursor.fetchall()

    offline_users = [u for u in users if u[3] == "В моем городе"]
    online_users = [u for u in users if u[3] == "Онлайн"]

    paired_users = set()
    pairs = []

    for user in offline_users:
        if user[0] in paired_users:
            continue

        same_city_users = [u for u in offline_users if u[2] == user[2] and u[0] != user[0] and u[0] not in paired_users]
        if same_city_users:
            partner = random.choice(same_city_users)
            pairs.append((user, partner))
            paired_users.update([user[0], partner[0]])
        else:
            if offline_users:
                partner = random.choice(online_users)
                pairs.append((user, partner))
                paired_users.update([user[0], partner[0]])
                await bot.send_message(user[0], f"Не удалось найти пару в вашем городе. Предлагаем встретиться онлайн с @{partner[1]}")
                await bot.send_message(partner[0], f"Ваша онлайн встреча на этой неделе.\nСвяжитесь с @{user[1]}\n\nОставьте отзыв после встречи нажав на /feedback")



    remaining_online_users = [u for u in online_users if u[0] not in paired_users]
    random.shuffle(remaining_online_users)

    while len(remaining_online_users) > 1:
        user1 = remaining_online_users.pop()
        user2 = remaining_online_users.pop()
        pairs.append((user1, user2))

    for (user1, user2) in pairs:
        cursor.execute("INSERT INTO meetings (user1, user2) VALUES (%s, %s)", (user1[0], user2[0]))
        conn.commit()
        await bot.send_message(user1[0], f"Ваша встреча на этой неделе:\nСвяжитесь с @{user2[1]}\n\nОставьте отзыв после встречи нажав на /feedback")
        await bot.send_message(user2[0], f"Ваша встреча на этой неделе:\nСвяжитесь с @{user1[1]}\n\nОставьте отзыв после встречи нажав на /feedback")

    cursor.close()
    conn.close()


#Запрос обратной связи
@dp.message_handler(commands=["feedback"])
async def request_feedback(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    conn = connect_db()
    cursor = conn.cursor()

    #Получаем последнюю встречу пользователя
    cursor.execute("""
        SELECT id FROM meetings WHERE (user1 = %s OR user2 = %s)
        AND (feedback1 IS NULL OR feedback2 IS NULL)
        ORDER BY date DESC LIMIT 1
    """, (user_id, user_id))
    meeting = cursor.fetchone()

    if meeting:
        await state.update_data(meeting_id=meeting[0])
        await message.answer("Как прошла ваша встреча? Оцените ее:", reply_markup=rating_keyboard)
        await Feedback.waiting_for_rating.set()
    else:
        await message.answer("Нет встреч, по которым можно оставить отзыв.")

    cursor.close()
    conn.close()

@dp.message_handler(state=Feedback.waiting_for_rating)
async def process_rating(message: types.Message, state: FSMContext):
    feedback = message.text
    await state.update_data(feedback=feedback)
    await message.answer("Спасибо! Теперь напишите короткий отзыв о встрече:")
    await Feedback.waiting_for_text.set()

@dp.message_handler(state=Feedback.waiting_for_text)
async def process_text_feedback(message: types.Message, state: FSMContext):
    additional_feedback = message.text
    user_id = message.from_user.id
    data = await state.get_data()
    meeting_id = data.get("meeting_id")
    feedback = data.get("feedback")

    if not meeting_id:
        await message.answer("Ошибка: не найдено актуальной встречи для отзыва")
        return



    try:
        with connect_db() as conn:
            with conn.cursor() as cursor:    
                #Проверяем, какой пользователь оставляет отзыв
                cursor.execute("SELECT user1, user2 FROM meetings WHERE id = %s", (meeting_id,))
                meeting = cursor.fetchone()

                if meeting:
                    if meeting[0] == user_id:
                        cursor.execute("""
                            UPDATE meetings
                            SET feedback1 = %s, additional_feedback1 = %s
                            WHERE id = %s
                        """, (feedback, additional_feedback, meeting_id))
                    elif meeting[1] == user_id:
                        cursor.execute("""
                            UPDATE meetings
                            SET feedback2 = %s, additional_feedback2 = %s
                            WHERE id = %s
                        """, (feedback, additional_feedback, meeting_id))

                    conn.commit()
                    await message.answer("Спасибо за ваш отзыв! Данные сохранены")
                else:
                    await message.answer("Ошибка: встреча не найдена")


    except psycopg2.Error as e:
        logging.error(f"Ошибка при работе с БД: {e}")
        await message.answer("Произошла ошибка при сохранении отзыва. Попробуйте позже")
    await state.finish()





async def scheduler():
    aioschedule.every(3).minutes.do(match_pairs)
#    aioschedule.every().friday.at("19:57").do(match_pairs)
    while True:
        await aioschedule.run_pending()
        await asyncio.sleep(60)

#Запуск бота
if __name__ == "__main__":
    init_db()
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler())
    executor.start_polling(dp, skip_updates=True)
