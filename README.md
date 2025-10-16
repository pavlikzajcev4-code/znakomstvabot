# Немного о самом боте
__Это бот предназначен для организации встреч, и для запуска нужно будет скачатm библиотекe "aiogram"__   
__(pip instal aiogram)__



# Как запустить бота?
**Как запустить бота?
Для начала клонируем репозиторий "" (нужно для всех версий)
Для виртуальных машин:** 

**1 переходим в режми "root" (sudo su "пароль от входа в компьютер") 2 скачиваем модуль "Python" (apt install python3) и прописываем команду "python3 bot.py".**

**для хостингов:  
 1 регистрируемся 2 переходим в "files" 3 нажимаем "upload file" и выбираем ранее загруженный файл 4 нажимаем на загруженный файл и на "run"**

**для серверов:  
 1 скачиваем python(sudo apt install python3-pip) 2 загружаем файл 3 запускаем скрипт python3 bot.py**
 # Импорт библиотек
```
import logging
import sqlite3
import qrcode
import urllib.parse
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from io import BytesIO
from aiogram.dispatcher import FSMContext
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils import executor
from aiogram.dispatcher.filters.state import State, StatesGroup
from config import BOT_TOKEN, BOT_USERNAME, ADMIN_ID, DB_PATH
```
__Для работы нужны такие библиотеки как:
aiogram — библиотека для разработки Telegram-ботов.__

__asyncio, psycopg2 — для асинхронного программирования и  взаимодействия с базой данных PostgreSQL соответственно.__ 

__aioschedule — модуль для планирования периодического запуска функций.__  

__datetime, timedelta — для работы с датами и временем.__

# Подключение и настройка базы данных
~~~
TOKEN = "BOT_TOKEN"
DB_CONFIG = {
    "dbname": "random_coffee",
    "user": "postgres",
    "password": "!Postgres321!",
    "host": "localhost"
}
~~~
__Здесь надо указать токен API для работы с ботом (токен от botfathet)__

# Настройка логирования
```
logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
```
__создаётся логирование__

# Работа с базой данных
```
def connect_db():
    return psycopg2.connect(**DB_CONFIG)
```
__функция использует заранее заданные конфигурации__    
___
  
    
```
def init_db():
    conn = connect_db()
    cursor = conn.cursor()
    ...
    conn.commit()
    cursor.close()
    conn.close()
```
__создаёт две таблицы:  
users(хранит информацию о зарегистрированных пользователях (ID, имя, город, описание, режим общения)   
meetings(хранит записи о проведенных встречах (парные комбинации участников, обратная связь, дополнительные заметки__  

# Регистрация нового пользователя
```
class Registration(StatesGroup):
    name = State()          
    city = State()
    description = State()   
    mode = State()
```  
__Тут пользователь указывает данные о себе__

# Обработчик команд 

```
@dp.message_handler(commands=["start"])
async def start_command(message: types.Message):
    await message.answer("Привет! Давай познакомимся. Как тебя зовут?")
    await Registration.name.set()
```
__обрабатывает команду "start" и выводит фразу(так-же регистрирует твоё имя)__  

___
```
@dp.message_handler(state=Registration.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Из какого ты города?")
    await Registration.city.set()
```
__регистрирует твой город__
___
```
@dp.message_handler(state=Registration.city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    await message.answer("Расскажи о себе (до 300 символов):")
    await Registration.description.set()
```
__регистрирует описание,которое ты указал__
___
```
@dp.message_handler(state=Registration.description)
async def process_description(message: types.Message, state: FSMContext):
    if len(message.text) > 300:
        await message.answer("Описание слишком длинное, попробуй короче (до 300 символов)")
        return
    await state.update_data(description=message.text)
    await message.answer("Выбери формат общения при помощи клавиатуры снизу👇", reply_markup=mode_keyboard)
    await Registration.mode.set()
```
__проверяет, правильно ли составлено описание__
___
```
@dp.message_handler(state=Registration.mode)
async def process_mode(message: types.Message, state: FSMContext):
    if message.text not in ["В моем городе", "Онлайн"]:
        await message.answer("Выбери один из предложенных вариантов")
        return

    user_data = await state.get_data()
    telegram_id = message.from_user.id
    conn = connect_db()
    cursor = conn.cursor()
    ...
    conn.commit()
    cursor.close()
    conn.close()

    await message.answer("Ты зарегистрирован! Ожидай отбор напарника на следующей неделе.", reply_markup=types.ReplyKeyboardRemove())
    await state.finish()
```
__Сначала проверяется правильность выбранного варианта общения. Если выбран неверный вариант, пользователю предлагают повторить попытку.
Затем собираются все данные, полученные в ходе предыдущих этапов, и вставляются в базу данных__
___
```
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
```

**получает список пользователей  
подбирает партнеров по интересам  
пытается подобрать партнера из города и если не получается,то ищет случайного онлайн-партнера**

# обработка пользователей и генерация пар
```
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
```
__Фильтрирует онлайн пользователей и генерирует пары среди онлайн пользователей, а потом пишет сообщения найденной паре__

# обработка команды 
```
@dp.message_handler(commands=["feedback"])
async def request_feedback(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    conn = connect_db()
    cursor = conn.cursor()
```
__обрабатывает команду "feedback" для отзывов о встрече от пользователей__

# Оценка последней встречи
```
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
```
__эта часть кода даёт оставить своё  мнение о последней встрече и в случае если встреч не было выдаёт ошибку__
# Получение информации и обновление данных о встречах
```
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
```
__выполняется запрос к базе данных и обновляются данные о встрече если при выполнении запросов происходит ошибка-то ошибка идёт в лог,а пользователю пишут соотвутсвующее сообщение__   

__так-же сюда включен модуль, основная заключается в регулярном выполнении функций, связанных с назначением новых встреч, контролем качества данных и поддержкой работоспособности всего приложения__
# Запуск самого бота
```
f __name__ == "__main__":
    init_db()
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler())
    executor.start_polling(dp, skip_updates=True)
```
