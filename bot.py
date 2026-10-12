import random
import re
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage

with open("questions.json", "r", encoding="utf-8") as f:
    QUESTIONS = json.load(f)

TOKEN = os.environ.get("BOT_TOKEN")

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())


def normalize(text):
    text = text.strip().lower()
    text = text.replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return text


def ballov(n):
    n_abs = abs(n) % 100
    if 11 <= n_abs <= 19:
        word = "баллов"
    else:
        n_last = n_abs % 10
        if n_last == 1:
            word = "балл"
        elif 2 <= n_last <= 4:
            word = "балла"
        else:
            word = "баллов"
    return f"{n} {word}"


user_states = {}


def make_start_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("Начать", callback_data="начать"))
    return keyboard


def make_question_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("Пропустить", callback_data="пропустить"),
        InlineKeyboardButton("Завершить", callback_data="завершить")
    )
    return keyboard


def make_return_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("Вернуться к вопросу", callback_data="вернуться"),
        InlineKeyboardButton("Пропустить", callback_data="пропустить"),
        InlineKeyboardButton("Завершить", callback_data="завершить")
    )
    return keyboard


async def send_question(chat_id):
    state = user_states.get(chat_id)
    if not state:
        return
    q = QUESTIONS[state["step"]]
    attachment = q.get("attachment_tg")
    if attachment:
        photo = open(attachment, "rb")
        await bot.send_photo(
            chat_id,
            photo=photo,
            caption=q["text"],
            reply_markup=make_question_keyboard()
        )
        photo.close()
    else:
        await bot.send_message(
            chat_id,
            q["text"],
            reply_markup=make_question_keyboard()
        )


async def send_greeting(chat_id):
    await bot.send_message(
        chat_id,
        "Привет! Я твой цифровой тренажер «Чтобы помнили». "
        "Я помогу тебе закрепить самые сложные темы Великой Отечественной войны "
        "для реального ЕГЭ по истории. Тебя ждет интерактивный квест. "
        "Ответь на все вопросы и проверь свои силы перед экзаменом. Поехали!",
        reply_markup=make_start_keyboard()
    )


async def start_quest(chat_id):
    user_states[chat_id] = {"step": 0, "score": 0, "answered_wrong": False}
    await send_question(chat_id)


async def finish_quest(chat_id):
    state = user_states.get(chat_id)
    if state:
        await bot.send_message(
            chat_id,
            f"Квест завершён. Твой результат: {state['score']} из 17.",
            reply_markup=make_start_keyboard()
        )
        del user_states[chat_id]
    else:
        await bot.send_message(
            chat_id,
            "Квест завершён. Если хочешь пройти заново — нажми «Начать».",
            reply_markup=make_start_keyboard()
        )


async def skip_question(chat_id):
    state = user_states.get(chat_id)
    if not state:
        return
    state["step"] += 1
    state["answered_wrong"] = False
    if state["step"] < len(QUESTIONS):
        await bot.send_message(
            chat_id,
            f"Вопрос пропущен. Баллы не начислены. У вас {ballov(state['score'])}."
        )
        await send_question(chat_id)
    else:
        await bot.send_message(
            chat_id,
            f"Вопрос пропущен. Баллы не начислены. У вас {ballov(state['score'])}.\n\n"
            f"Поздравляем, квест пройден! Твой результат: {state['score']} из 17.",
            reply_markup=make_start_keyboard()
        )
        del user_states[chat_id]


async def handle_answer(chat_id, answer_text):
    state = user_states.get(chat_id)
    if not state:
        return

    q = QUESTIONS[state["step"]]
    user_norm = normalize(answer_text)

    is_correct = False
    for variant in q["correct_variants"]:
        if user_norm == normalize(variant):
            is_correct = True
            break

    if is_correct:
        if not state["answered_wrong"]:
            state["score"] += 1
            state["step"] += 1
            state["answered_wrong"] = False

            if state["step"] < len(QUESTIONS):
                await bot.send_message(
                    chat_id,
                    f"Правильно! У вас {ballov(state['score'])}."
                )
                await send_question(chat_id)
            else:
                await bot.send_message(
                    chat_id,
                    f"Правильно! У вас {ballov(state['score'])}.\n\n"
                    f"Поздравляем, квест пройден! Твой результат: {state['score']} из 17.",
                    reply_markup=make_start_keyboard()
                )
                del user_states[chat_id]
        else:
            state["step"] += 1
            state["answered_wrong"] = False

            if state["step"] < len(QUESTIONS):
                await bot.send_message(
                    chat_id,
                    f"Правильно! Баллы не начислены, так как вы уже ошибались в этом вопросе. У вас {ballov(state['score'])}."
                )
                await send_question(chat_id)
            else:
                await bot.send_message(
                    chat_id,
                    f"Правильно! Баллы не начислены, так как вы уже ошибались в этом вопросе. У вас {ballov(state['score'])}.\n\n"
                    f"Поздравляем, квест пройден! Твой результат: {state['score']} из 17.",
                    reply_markup=make_start_keyboard()
                )
                del user_states[chat_id]
    else:
        state["answered_wrong"] = True
        await bot.send_message(
            chat_id,
            f"Неправильно! Вам не будут начислены баллы. Вот пояснение исторической справки:\n\n{q['hint']}",
            reply_markup=make_return_keyboard()
        )


@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    await send_greeting(message.chat.id)


@dp.callback_query_handler(lambda c: True)
async def process_callback(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id
    data = callback_query.data.strip().lower()

    if "начать" in data:
        if chat_id in user_states:
            await bot.send_message(chat_id, "Ты уже проходишь квест. Продолжай!")
            await send_question(chat_id)
        else:
            await start_quest(chat_id)

    elif "завершить" in data:
        await finish_quest(chat_id)

    elif "пропустить" in data:
        await skip_question(chat_id)

    elif "вернуться" in data:
        state = user_states.get(chat_id)
        if state:
            await send_question(chat_id)

    await bot.answer_callback_query(callback_query.id)


@dp.message_handler()
async def process_message(message: types.Message):
    chat_id = message.chat.id
    text = message.text.strip()

    if chat_id not in user_states:
        await send_greeting(chat_id)
        return

    await handle_answer(chat_id, text)


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
