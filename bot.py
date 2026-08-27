import asyncio
import random
import string
import re
import json
import base64
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo

TOKEN = "8985729433:AAFZXxkXMnZeIIk63m0GvKukyBMAdxC8f9Y"
ADMIN_ID = 955037275
WEBAPP_URL = "https://rahimjonovabdullo.github.io/sat-test/"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

tests = {}
users = {}


class AdminStates(StatesGroup):
    waiting_key = State()


class RegStates(StatesGroup):
    waiting_name = State()


def generate_code():
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if code not in tests:
            return code


def build_webapp_url():
    public_tests = {code: {"order": t["order"], "types": t["types"]} for code, t in tests.items()}
    raw = json.dumps(public_tests).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("utf-8")
    return f"{WEBAPP_URL}?tests={encoded}"


def main_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Testni boshlash", web_app=WebAppInfo(url=build_webapp_url()))],
            [KeyboardButton(text="Reyting")],
        ],
        resize_keyboard=True
    )


@dp.message(Command("newtest"))
async def newtest_handler(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Bu buyruq faqat admin uchun.")
        return
    await state.set_state(AdminStates.waiting_key)
    await message.answer("Javoblar kalitini yuboring.\nMasalan: 1C 2A 3B 4D 5B 6=15 7=20")


@dp.message(AdminStates.waiting_key)
async def receive_key(message: types.Message, state: FSMContext):
    text = message.text
    matches = re.findall(r"(\d+)\s*(=\S+|[A-Da-d])", text)
    if not matches:
        await message.answer("Format tushunarsiz. Qaytadan urinib ko'ring.\nMasalan: 1C 2A 3B 4=15")
        return

    order, q_types, answers = [], {}, {}
    for qid_str, ans in matches:
        qid = int(qid_str)
        order.append(qid)
        if ans.startswith("="):
            q_types[qid] = "grid"
            answers[qid] = ans[1:]
        else:
            q_types[qid] = "mc"
            answers[qid] = ans.upper()

    order = sorted(set(order))
    code = generate_code()
    tests[code] = {"order": order, "types": q_types, "answers": answers}
    await state.clear()
    await message.answer(f"✅ Test yaratildi!\nKod: {code}\nSavollar soni: {len(order)}")


@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()
    if user_id in users:
        await message.answer(f"Xush kelibsiz, {users[user_id]['name']}!", reply_markup=main_menu_kb())
    else:
        await state.set_state(RegStates.waiting_name)
        await message.answer(
            "Assalomu alaykum! SAT botga xush kelibsiz.\nAvval Ism va Familiyangizni yozing:",
            reply_markup=ReplyKeyboardRemove()
        )


@dp.message(RegStates.waiting_name)
async def receive_name(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    full_name = message.text.strip()
    if len(full_name) < 3:
        await message.answer("Iltimos, to'liq ism familiyangizni yozing:")
        return

    users[user_id] = {"name": full_name, "total_correct": 0, "total_questions": 0, "tests_done": 0}
    await state.clear()
    await message.answer(
        f"Rahmat, {full_name}! Ro'yxatdan o'tdingiz.\nTestni boshlash uchun pastdagi tugmani bosing:",
        reply_markup=main_menu_kb()
    )


@dp.message(F.text == "Reyting")
async def reyting_handler(message: types.Message):
    if not users:
        await message.answer("Hozircha reytingda hech kim yo'q.")
        return
    ranked = sorted(users.values(), key=lambda u: u["total_correct"], reverse=True)
    lines = ["🏆 Reyting:\n"]
    for i, u in enumerate(ranked[:10], start=1):
        lines.append(f"{i}. {u['name']} — {u['total_correct']} ta to'g'ri javob ({u['tests_done']} ta test)")
    await message.answer("\n".join(lines))


@dp.message(F.web_app_data)
async def webapp_data_handler(message: types.Message):
    user_id = message.from_user.id
    try:
        data = json.loads(message.web_app_data.data)
        code = data.get("code", "").strip().upper()
        user_answers = data.get("answers", {})
    except Exception:
        await message.answer("Xatolik: ma'lumot noto'g'ri formatda.")
        return

    if code not in tests:
        await message.answer("Test topilmadi.")
        return

    test = tests[code]
    correct_count = 0
    lines = ["Test natijasi:\n"]
    for qid in test["order"]:
        user_ans = str(user_answers.get(str(qid), "")).strip()
        correct_ans = str(test["answers"][qid]).strip()
        if user_ans.lower() == correct_ans.lower():
            correct_count += 1
            lines.append(f"{qid}. ✅ Javobingiz: {user_ans or '-'}")
        else:
            lines.append(f"{qid}. ❌ Javobingiz: {user_ans or '-'} | To'g'ri: {correct_ans}")

    total = len(test["order"])
    lines.append(f"\nNatija: {correct_count}/{total} to'g'ri javob")
    await message.answer("\n".join(lines))

    if user_id in users:
        users[user_id]["total_correct"] += correct_count
        users[user_id]["total_questions"] += total
        users[user_id]["tests_done"] += 1


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
