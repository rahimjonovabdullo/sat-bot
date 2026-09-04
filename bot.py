import asyncio
import random
import string
import re
import json
import base64
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo

TOKEN = "8985729433:AAFZXxkXMnZeIIk63m0GvKukyBMAdxC8f9Y"
ADMIN_ID = 955037275
WEBAPP_URL = "https://rahimjonovabdullo.github.io/sat-test/"

DATA_DIR = "/data" if os.path.isdir("/data") else "."
TESTS_FILE = os.path.join(DATA_DIR, "tests.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


tests = load_json(TESTS_FILE, {})
users_raw = load_json(USERS_FILE, {})
users = {int(k): v for k, v in users_raw.items()}


def save_tests():
    save_json(TESTS_FILE, tests)


def save_users():
    save_json(USERS_FILE, {str(k): v for k, v in users.items()})


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
    await message.answer(
        "Javoblar kalitini yuboring.\n"
        "Masalan: 1C 2A 3B 4D 5B 6=15 7=20\n"
        "Bir nechta to'g'ri javob uchun vergul bilan: 6=15,20\n"
        "(4 variantli savol uchun harf, Grid-in uchun =qiymat)"
    )


@dp.message(AdminStates.waiting_key)
async def receive_key(message: types.Message, state: FSMContext):
    text = message.text
    matches = re.findall(r"(\d+)\s*(=\S+|[A-Da-d])", text)
    if not matches:
        await message.answer("Format tushunarsiz. Qaytadan urinib ko'ring.\nMasalan: 1C 2A 3B 4=15,20")
        return

    order, q_types, answers = [], {}, {}
    for qid_str, ans in matches:
        qid = int(qid_str)
        order.append(qid)
        if ans.startswith("="):
            q_types[qid] = "grid"
            variants = [v.strip() for v in ans[1:].split(",") if v.strip()]
            answers[qid] = variants
        else:
            q_types[qid] = "mc"
            answers[qid] = [ans.upper()]

    order = sorted(set(order))
    code = generate_code()
    tests[code] = {"order": order, "types": q_types, "answers": answers}
    save_tests()
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
    save_users()
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
        correct_variants = [str(a).strip().lower() for a in test["answers"][str(qid)] if True] if str(qid) in test["answers"] else [str(a).strip().lower() for a in test["answers"][qid]]
        qid_key = qid if qid in test["answers"] else str(qid)
        correct_variants = [str(a).strip().lower() for a in test["answers"][qid_key]]
        correct_display = " yoki ".join(str(a) for a in test["answers"][qid_key])
        if user_ans.lower() in correct_variants:
            correct_count += 1
            lines.append(f"{qid}. ✅ Javobingiz: {user_ans or '-'}")
        else:
            lines.append(f"{qid}. ❌ Javobingiz: {user_ans or '-'} | To'g'ri: {correct_display}")

    total = len(test["order"])
    lines.append(f"\nNatija: {correct_count}/{total} to'g'ri javob")
    await message.answer("\n".join(lines))

    if user_id in users:
        users[user_id]["total_correct"] += correct_count
        users[user_id]["total_questions"] += total
        users[user_id]["tests_done"] += 1
        save_users()


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
